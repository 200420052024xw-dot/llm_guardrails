from __future__ import annotations

from functools import lru_cache
from typing import Any
import os

from .config import DETECTION_ROOT, SemanticThresholds, load_model_config, load_thresholds
from .embedding_matcher import EmbeddingMatcher
from .fact_store import expand_fact_texts, file_sha256, load_facts
from .hash_embedding_client import HashEmbeddingClient
from .local_embedding_client import LocalEmbeddingClient
from .llm_semantic_classifier import LLMSemanticClassifier, OfflineRuleClassifier
from .openai_compatible_client import OpenAICompatibleClient
from .schema_adapter import build_result


class SemanticDetector:
    def __init__(self, embedding_matcher: EmbeddingMatcher, classifier: Any, thresholds: SemanticThresholds):
        self.embedding_matcher = embedding_matcher
        self.classifier = classifier
        self.thresholds = thresholds
        self.uses_model_classifier = isinstance(classifier, LLMSemanticClassifier)

    def detect_request(self, request: Any) -> Any:
        result, _ = self._detect_request_internal(request)
        return result

    def detect_request_with_trace(self, request: Any) -> tuple[Any, dict[str, Any]]:
        return self._detect_request_internal(request)

    def _detect_request_internal(self, request: Any) -> tuple[Any, dict[str, Any]]:
        sentence_id = str(_get_field(request, "sentence_id", ""))
        sentence = _select_sentence_text(request)
        request_input = {
            "sentence_id": sentence_id,
            "text": sentence,
            "rule_result": _get_field(request, "rule_result"),
        }
        sim_result = self.embedding_matcher.search(sentence, top_k=self.thresholds.top_k)
        top_hit = sim_result.get("top_hit")
        sim_score = float(top_hit["similarity"]) if top_hit else 0.0
        similarity_trace = {
            "input": {
                "sentence_id": sentence_id,
                "text": sentence,
                "top_k": self.thresholds.top_k,
                "matcher_threshold": self.thresholds.matcher_threshold,
            },
            "output": sim_result,
        }

        evidence_types: list[str] = []
        risk_types: list[str] = []
        messages: list[str] = []

        if top_hit and sim_score >= self.thresholds.medium_similarity:
            evidence_types.append("similarity_match")
            risk_types.append(str(top_hit.get("fact_type", "semantic_similarity")))
            messages.append(f"similarity={sim_score:.4f}, fact_id={top_hit.get('fact_id')}")

        cls_result: dict[str, Any] = {
            "risk_score": 0.0,
            "risk_types": [],
            "reason": "",
            "is_confidential_sentence": False,
        }
        model_trace: dict[str, Any]
        if sim_score < self.thresholds.similarity_high:
            model_input = {
                "sentence_id": sentence_id,
                "text": sentence,
                "classifier": type(self.classifier).__name__,
            }
            cls_result = self.classifier.classify(sentence)
            model_trace = {
                "called": True,
                "input": model_input,
                "output": cls_result,
            }
            evidence_types.append("model_detection" if self.uses_model_classifier else "rule_match")
            risk_types.extend(cls_result.get("risk_types", []))
            if cls_result.get("reason"):
                messages.append(str(cls_result["reason"]))
        else:
            model_trace = {
                "called": False,
                "input": {
                    "sentence_id": sentence_id,
                    "text": sentence,
                    "classifier": type(self.classifier).__name__,
                },
                "output": {
                    "reason": "high similarity matched; skipped model classification",
                    "similarity": sim_score,
                    "similarity_high": self.thresholds.similarity_high,
                },
            }
            messages.append("high similarity matched; skipped model classification")

        cls_score = float(cls_result.get("risk_score", 0.0))
        final_score = round(max(sim_score, cls_score), 4)
        confidential_level = self._decide_level(sim_score, cls_score)
        if confidential_level == "pass" and _get_field(request, "rule_result") == "sensitive":
            confidential_level = "sensitive"

        result = build_result(
            sentence_id=sentence_id,
            confidential_level=confidential_level,
            risk_score=final_score,
            risk_types=sorted(set(filter(None, risk_types))),
            evidence_types=sorted(set(evidence_types)),
            redacted_text=sentence if _get_field(request, "rule_result") == "sensitive" else None,
            message="; ".join(messages)[:500] or "no semantic confidentiality risk detected",
        )
        trace = {
            "semantic_input": request_input,
            "similarity_match": similarity_trace,
            "model_recognition": model_trace,
            "comprehensive_evaluation": {
                "input": {
                    "similarity_score": sim_score,
                    "classifier_score": cls_score,
                    "rule_result": _get_field(request, "rule_result"),
                    "thresholds": {
                        "similarity_high": self.thresholds.similarity_high,
                        "llm_high": self.thresholds.llm_high,
                        "joint_similarity": self.thresholds.joint_similarity,
                        "joint_llm": self.thresholds.joint_llm,
                        "medium_similarity": self.thresholds.medium_similarity,
                        "medium_llm": self.thresholds.medium_llm,
                    },
                    "risk_types": sorted(set(filter(None, risk_types))),
                    "evidence_types": sorted(set(evidence_types)),
                },
                "output": result,
            },
        }
        return result, trace

    def _decide_level(self, sim_score: float, cls_score: float) -> str:
        if (
            sim_score >= self.thresholds.similarity_high
            or cls_score >= self.thresholds.llm_high
            or (sim_score >= self.thresholds.joint_similarity and cls_score >= self.thresholds.joint_llm)
        ):
            return "confidential"
        if sim_score >= self.thresholds.medium_similarity or cls_score >= self.thresholds.medium_llm:
            return "sensitive"
        return "pass"


@lru_cache(maxsize=1)
def get_default_detector() -> SemanticDetector:
    thresholds = load_thresholds()
    model_config = load_model_config()
    api_client = OpenAICompatibleClient()

    local_embedding_path = os.getenv("LOCAL_EMBEDDING_MODEL_PATH")
    if local_embedding_path:
        embedding_client: Any = LocalEmbeddingClient(local_embedding_path)
        embedding_model = local_embedding_path
    elif api_client.embedding_configured:
        embedding_client = api_client
        embedding_model = api_client.embedding_model
    else:
        embedding_client = HashEmbeddingClient()
        embedding_model = "hash-embedding-client-v1"

    matcher = EmbeddingMatcher(embedding_client, threshold=thresholds.matcher_threshold)
    fact_path = DETECTION_ROOT / "data" / "simulated" / "confidential_facts.jsonl"
    facts = load_facts(fact_path)
    matcher.build_or_load_index(
        rows=expand_fact_texts(facts),
        index_path=model_config.vector_index_path,
        source_sha256=file_sha256(fact_path),
        embedding_model=embedding_model,
    )

    classifier: Any = LLMSemanticClassifier(api_client) if api_client.configured else OfflineRuleClassifier()
    return SemanticDetector(matcher, classifier, thresholds)


def detect_confidential_sentence(request: Any) -> Any:
    return get_default_detector().detect_request(request)


def detect_confidential_sentence_with_trace(request: Any) -> tuple[Any, dict[str, Any]]:
    return get_default_detector().detect_request_with_trace(request)


def _get_field(obj: Any, field: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(field, default)
    return getattr(obj, field, default)


def _select_sentence_text(request: Any) -> str:
    for field in ("text", "original", "decoded", "normalized", "compact", "lower", "upper"):
        value = _get_field(request, field)
        if value:
            return str(value)
    raise ValueError("SemanticDetectionRequest must contain text")
