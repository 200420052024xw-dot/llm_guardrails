import asyncio
import os
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.schemas import SemanticFinalResult
from core.sentence_splitter import build_semantic_detection_request
from core.vector_store import search_user_vectors, _get_embedding_client
from detection.semantic.semantic_detector import SemanticDetector
from detection.semantic.embedding_matcher import EmbeddingMatcher
from detection.semantic.config import SemanticThresholds, load_thresholds
from detection.semantic.llm_semantic_classifier import LLMSemanticClassifier, OfflineRuleClassifier
from detection.semantic.openai_compatible_client import OpenAICompatibleClient
from detection.semantic_client import Detector
from core.models import ConfidentialEntry, PublicEntry


class ChromaEmbeddingMatcher(EmbeddingMatcher):
    """EmbeddingMatcher that uses ChromaDB for vector search."""

    def __init__(self, user_id: str, embedding_client, threshold: float = 0.78):
        super().__init__(embedding_client, threshold)
        self.user_id = user_id

    def search(self, sentence: str, top_k: int = 3) -> dict[str, Any]:
        """Search using ChromaDB instead of in-memory vectors."""
        result = search_user_vectors(self.user_id, sentence, self.embedding_client, top_k)
        return result


async def evaluate_text(
    user_id: str,
    text: str,
    db: AsyncSession,
    model_config=None,
    request_id: str | None = None,
) -> tuple[SemanticFinalResult, list[dict]]:
    confidential = list(await db.scalars(select(ConfidentialEntry).where(ConfidentialEntry.user_id == user_id, ConfidentialEntry.enabled.is_(True))))
    public = list(await db.scalars(select(PublicEntry).where(PublicEntry.user_id == user_id, PublicEntry.enabled.is_(True))))
    facts = [
        {
            "fact_id": item.id,
            "fact_type": item.category,
            "confidential_level": item.confidential_level or "high",
            "fact_text": item.text,
            "fact_summary": item.summary or "",
            "paraphrases": item.paraphrases or [],
            "negative_samples": item.negative_samples or [],
            "keywords": item.keywords or [],
        }
        for item in confidential
    ]
    allowed_entities = {(item.entity_type, item.value) for item in public}
    return await asyncio.to_thread(_evaluate, user_id, text, facts, allowed_entities, model_config, request_id)


def _evaluate(user_id: str, text: str, facts: list[dict], allowed_entities: set[tuple[str, str]], model_config=None, request_id=None):
    kwargs = {}
    if model_config:
        kwargs = {"api_key": model_config["api_key"], "base_url": model_config["base_url"], "model": model_config["model"]}

    # Use ChromaDB vector store for similarity search
    embedding_client = _get_embedding_client()
    thresholds = load_thresholds()

    # Create matcher that uses ChromaDB
    matcher = ChromaEmbeddingMatcher(user_id, embedding_client, threshold=thresholds.matcher_threshold)

    # Create classifier
    api_client = OpenAICompatibleClient(**kwargs) if kwargs else OpenAICompatibleClient()
    classifier: Any = LLMSemanticClassifier(api_client) if api_client.configured else OfflineRuleClassifier()

    # Build semantic detector with ChromaDB matcher
    semantic_detector = SemanticDetector(matcher, classifier, thresholds)

    detector = Detector(
        allowed_entities=allowed_entities,
        semantic_detector=semantic_detector,
    )
    requests, originals = build_semantic_detection_request(text)
    results, traces = detector.start_detect_with_trace(requests)
    result = detector.analyze_detect_results(
        request_id or datetime.now().strftime("%Y%m%d_%H_%M_%S_%f"), text, results, originals
    )
    messages = {
        "pass": "未检测到敏感或保密信息，内容已安全发送。",
        "redact": "检测到敏感信息，已脱敏后发送给模型。",
        "block": "检测到保密信息，本次内容已阻止发送。",
    }
    return result.model_copy(update={"message": messages[result.action]}), traces
