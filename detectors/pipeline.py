from core.schemas import Detection
from detectors.base import BaseDetector
from detectors.custom import CustomDictionaryDetector
from detectors.pii import PiiDetector
from detectors.secrets import SecretDetector
from detectors.text_normalizer import normalize_text

DEFAULT_CONFIDENCE_THRESHOLD = 0.30


class DetectionPipeline:
    def __init__(self, detectors: list[BaseDetector] | None = None):
        self.detectors = detectors or [
            PiiDetector(),
            SecretDetector(),
            CustomDictionaryDetector(),
        ]

    def detect(self, text: str) -> list[Detection]:
        text_views = normalize_text(text)
        detections = []

        for detector in self.detectors:
            detections.extend(detector.detect(text, text_views))

        detections = filter_by_confidence(detections)
        detections = dedupe_overlapping_detections(detections)
        return detections


def filter_by_confidence(
    detections: list[Detection],
    threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
) -> list[Detection]:
    return [detection for detection in detections if detection.confidence >= threshold]


def dedupe_overlapping_detections(detections: list[Detection]) -> list[Detection]:
    sorted_detections = sorted(
        detections,
        key=lambda detection: (
            detection.start,
            -detection.risk_weight,
            -(detection.end - detection.start),
        ),
    )

    result = []
    for detection in sorted_detections:
        overlapping = [
            existing
            for existing in result
            if not (detection.end <= existing.start or detection.start >= existing.end)
        ]

        if not overlapping:
            result.append(detection)
            continue

        existing = overlapping[0]
        if _is_better_detection(detection, existing):
            result.remove(existing)
            result.append(detection)

    return sorted(result, key=lambda detection: detection.start)


def _is_better_detection(candidate: Detection, existing: Detection) -> bool:
    candidate_score = (
        candidate.risk_weight,
        candidate.confidence,
        candidate.end - candidate.start,
    )
    existing_score = (
        existing.risk_weight,
        existing.confidence,
        existing.end - existing.start,
    )
    return candidate_score > existing_score


_default_pipeline = DetectionPipeline()


def detect_sensitive_content(text: str) -> list[Detection]:
    return _default_pipeline.detect(text)
