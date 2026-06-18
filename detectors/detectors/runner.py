# detectors/runner.py
from detectors.normalizer import normalize_text
from detectors.pii_detector import detect_pii
from detectors.secret_detector import detect_secret
from detectors.dict_detector import detect_dictionary


def remove_low_confidence(detections: list[dict], threshold: float = 0.30) -> list[dict]:
    return [d for d in detections if d.get("confidence", 0) >= threshold]


def run_detectors(text: str) -> list[dict]:
    views = normalize_text(text)
    detections = []
    detections.extend(detect_pii(text, views))
    detections.extend(detect_secret(text, views))
    detections.extend(detect_dictionary(text, views))
    return remove_low_confidence(detections)


def dedupe_overlaps(detections: list[dict]) -> list[dict]:
    # 简单策略：按 start 排序，遇到重叠时保留 risk_weight 更高的
    detections = sorted(detections, key=lambda d: (d["start"], -(d.get("risk_weight", 0))))
    result = []
    for d in detections:
        overlap = False
        for old in result:
            if not (d["end"] <= old["start"] or d["start"] >= old["end"]):
                overlap = True
                if d.get("risk_weight", 0) > old.get("risk_weight", 0):
                    result.remove(old)
                    result.append(d)
                break
        if not overlap:
            result.append(d)
    return sorted(result, key=lambda d: d["start"])
