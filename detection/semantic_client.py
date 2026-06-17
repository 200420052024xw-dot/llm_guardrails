from concurrent.futures import ThreadPoolExecutor, as_completed
import time

from core.schemas import SemanticDetectionRequest, SemanticDetectionResult, SemanticFinalResult
from detection.semantic import detect_confidential_sentence


class Detector:
    def __init__(self):
        self.max_semantic_workers = 3
        self.max_retries = 3
        self.retries_delay_seconds = 0.5

    def _semantic_retry(self, request_sentence: SemanticDetectionRequest) -> SemanticDetectionResult:
        last_exc: Exception | None = None

        for attempt in range(1, self.max_retries + 1):
            try:
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

    def start_detect(self, detect_request: list[SemanticDetectionRequest]) -> list[SemanticDetectionResult]:
        detect_results: list[SemanticDetectionResult] = []

        with ThreadPoolExecutor(max_workers=self.max_semantic_workers) as executor:
            future_map = {
                executor.submit(self._semantic_retry, sentence): sentence
                for sentence in detect_request
            }
            for future in as_completed(future_map):
                detect_results.append(future.result())

        return sorted(detect_results, key=lambda item: int(item.sentence_id[1:]))

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
