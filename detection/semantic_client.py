from concurrent.futures import ThreadPoolExecutor, as_completed
import re
import time

from core.schemas import (
    RuleDetectionResult,
    SemanticDetectionRequest,
    SemanticDetectionResult,
    SemanticFinalResult,
)
from detection.rules import detect_rules
from detection.semantic import detect_confidential_sentence, detect_confidential_sentence_with_trace


REDACTION_PLACEHOLDER_RE = re.compile(r"\[(?:[A-Z][A-Z0-9_]*?)_\d+\]")
SEMANTIC_RISK_TYPES = {
    "project_progress",
    "technical_solution",
    "system_architecture",
    "vulnerability_status",
    "customer_intention",
    "pricing_strategy",
    "internal_decision",
    "personnel_arrangement",
    "procurement_plan",
    "deployment_plan",
    "evaluation_result",
    "incident_information",
}


class Detector:
    def __init__(self, allowed_entities=None, semantic_detector=None):
        self.max_semantic_workers = 3
        self.max_retries = 3
        self.retries_delay_seconds = 0.5
        self.allowed_entities = allowed_entities
        self.semantic_detector = semantic_detector

    def _semantic_retry(self, request_sentence: SemanticDetectionRequest) -> SemanticDetectionResult:
        last_exc: Exception | None = None

        for attempt in range(1, self.max_retries + 1):
            try:
                if self.semantic_detector is not None:
                    return self.semantic_detector.detect_request(request_sentence)
                return detect_confidential_sentence(request_sentence)
            except Exception as exc:
                last_exc = exc

                if attempt < self.max_retries:
                    time.sleep(self.retries_delay_seconds)

        return SemanticDetectionResult(
            sentence_id=request_sentence.sentence_id,
            confidential_level="error",
            risk_score=1.0,
            risk_types=["semantic_detect_error"],
            evidence_types=["request_error"],
            message=f"semantic detector failed: {type(last_exc).__name__}: {last_exc}",
        )

    def _semantic_retry_with_trace(
        self,
        request_sentence: SemanticDetectionRequest,
    ) -> tuple[SemanticDetectionResult, dict]:
        attempts: list[dict] = []
        last_exc: Exception | None = None

        for attempt in range(1, self.max_retries + 1):
            try:
                if self.semantic_detector is not None:
                    result, trace = self.semantic_detector.detect_request_with_trace(request_sentence)
                else:
                    result, trace = detect_confidential_sentence_with_trace(request_sentence)
                attempts.append({
                    "attempt": attempt,
                    "status": "success",
                    "input": request_sentence,
                    "output": result,
                })
                trace["retry"] = attempts
                return result, trace
            except Exception as exc:
                last_exc = exc
                attempts.append({
                    "attempt": attempt,
                    "status": "error",
                    "input": request_sentence,
                    "error": f"{type(exc).__name__}: {exc}",
                })

                if attempt < self.max_retries:
                    time.sleep(self.retries_delay_seconds)

        result = SemanticDetectionResult(
            sentence_id=request_sentence.sentence_id,
            confidential_level="error",
            risk_score=1.0,
            risk_types=["semantic_detect_error"],
            evidence_types=["request_error"],
            message=f"semantic detector failed: {type(last_exc).__name__}: {last_exc}",
        )
        return result, {
            "semantic_input": request_sentence,
            "retry": attempts,
            "output": result,
        }

    def _detect_one(self, context: dict[str, str]) -> SemanticDetectionResult:
        rule_result = detect_rules(context, self.allowed_entities)
        semantic_request = SemanticDetectionRequest(
            sentence_id=context["sentence_id"],
            text=rule_result.redacted_text or context["original"],
            rule_result=rule_result.level,
        )
        semantic_result = self._semantic_retry(semantic_request)
        return self._merge_rule_result(semantic_result, rule_result, semantic_request.text)

    def _detect_one_with_trace(self, context: dict[str, str]) -> tuple[SemanticDetectionResult, dict]:
        rule_result = detect_rules(context, self.allowed_entities)
        semantic_request = SemanticDetectionRequest(
            sentence_id=context["sentence_id"],
            text=rule_result.redacted_text or context["original"],
            rule_result=rule_result.level,
        )
        semantic_result, semantic_trace = self._semantic_retry_with_trace(semantic_request)
        merged_result = self._merge_rule_result(semantic_result, rule_result, semantic_request.text)

        trace = {
            "sentence_id": context["sentence_id"],
            "rule_match": {
                "input": context,
                "output": rule_result,
            },
            "semantic_request": {
                "input": {
                    "rule_result": rule_result,
                    "original_text": context["original"],
                },
                "output": semantic_request,
            },
            "similarity_match": semantic_trace.get("similarity_match"),
            "model_recognition": semantic_trace.get("model_recognition"),
            "comprehensive_evaluation": semantic_trace.get("comprehensive_evaluation"),
            "semantic_trace": semantic_trace,
            "merge_rule_semantic": {
                "input": {
                    "rule_result": rule_result,
                    "semantic_result": semantic_result,
                    "safe_text": semantic_request.text,
                },
                "output": merged_result,
            },
        }
        return merged_result, trace

    def start_detect(self, detect_request: list[dict[str, str]]) -> list[SemanticDetectionResult]:
        detect_results: list[SemanticDetectionResult] = []

        with ThreadPoolExecutor(max_workers=self.max_semantic_workers) as executor:
            future_map = {
                executor.submit(self._detect_one, sentence): sentence
                for sentence in detect_request
            }
            for future in as_completed(future_map):
                detect_results.append(future.result())

        return sorted(detect_results, key=lambda item: int(item.sentence_id[1:]))

    def start_detect_with_trace(
        self,
        detect_request: list[dict[str, str]],
    ) -> tuple[list[SemanticDetectionResult], list[dict]]:
        detect_results: list[SemanticDetectionResult] = []
        traces: list[dict] = []

        with ThreadPoolExecutor(max_workers=self.max_semantic_workers) as executor:
            future_map = {
                executor.submit(self._detect_one_with_trace, sentence): sentence
                for sentence in detect_request
            }
            for future in as_completed(future_map):
                result, trace = future.result()
                detect_results.append(result)
                traces.append(trace)

        detect_results = sorted(detect_results, key=lambda item: int(item.sentence_id[1:]))
        traces = sorted(traces, key=lambda item: int(item["sentence_id"][1:]))
        return detect_results, traces

    def _merge_rule_result(
        self,
        semantic_result: SemanticDetectionResult,
        rule_result: RuleDetectionResult,
        safe_text: str,
    ) -> SemanticDetectionResult:
        if rule_result.level == "pass":
            return semantic_result

        level = semantic_result.confidential_level
        if level == "pass":
            level = "sensitive"
        elif self._is_placeholder_only_confidential(semantic_result, rule_result, safe_text):
            level = "sensitive"

        risk_types = sorted(set(semantic_result.risk_types + rule_result.risk_types))
        evidence_types = sorted(set(semantic_result.evidence_types + ["rule_match"]))
        messages = [item for item in [semantic_result.message, rule_result.message] if item]

        return SemanticDetectionResult(
            sentence_id=semantic_result.sentence_id,
            confidential_level=level,
            risk_score=max(semantic_result.risk_score, 0.65),
            risk_types=risk_types,
            evidence_types=evidence_types,
            redacted_text=semantic_result.redacted_text or safe_text,
            message="; ".join(messages)[:500],
        )

    def _is_placeholder_only_confidential(
        self,
        semantic_result: SemanticDetectionResult,
        rule_result: RuleDetectionResult,
        safe_text: str,
    ) -> bool:
        if rule_result.level != "sensitive":
            return False
        if semantic_result.confidential_level != "confidential":
            return False
        if not REDACTION_PLACEHOLDER_RE.search(safe_text):
            return False
        if "similarity_match" in semantic_result.evidence_types:
            return False

        semantic_risks = set(semantic_result.risk_types) & SEMANTIC_RISK_TYPES
        return not semantic_risks

    def _build_redacted_text(
        self,
        original_sentences: dict[str, str],
        detect_results: list[SemanticDetectionResult],
    ) -> str:
        redacted_sentences = dict(original_sentences)
        for item in detect_results:
            if item.confidential_level == "sensitive" and item.redacted_text:
                redacted_sentences[item.sentence_id] = item.redacted_text
        return "".join(redacted_sentences.values())

    def analyze_detect_results(
        self,
        request_id: str,
        original_text: str,
        detect_results: list[SemanticDetectionResult],
        original_sentences: dict[str, str],
    ) -> SemanticFinalResult:
        risk_score = max((item.risk_score for item in detect_results), default=0.0)

        if any(item.confidential_level in {"confidential", "error"} for item in detect_results):
            return SemanticFinalResult(
                request_id=request_id,
                action="block",
                risk_score=risk_score,
                message="检测到疑似内部保密信息，本次请求已拦截，未发送至模型。",
                final_text=None,
                sentence_results=detect_results,
            )

        if any(item.confidential_level == "sensitive" for item in detect_results):
            redacted_text = self._build_redacted_text(original_sentences, detect_results)

            return SemanticFinalResult(
                request_id=request_id,
                action="redact",
                risk_score=risk_score,
                message="检测到疑似敏感内容，已脱敏后发送至模型。",
                final_text=redacted_text,
                sentence_results=detect_results,
            )

        return SemanticFinalResult(
            request_id=request_id,
            action="pass",
            risk_score=risk_score,
            message="未检测到保密信息，已发送至模型。",
            final_text=original_text,
            sentence_results=detect_results,
        )
