from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from policy.detection_utils import detection_type, get_detection_field


POLICY_PATH = Path(__file__).resolve().parents[1] / "config" / "policy.yaml"


def load_policy() -> dict[str, Any]:
    with POLICY_PATH.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _as_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def calculate_risk(detections: list[Any]) -> dict[str, Any]:
    policy = load_policy()
    weights = policy.get("risk_weights", {})

    if not detections:
        return {
            "risk_score": 0.0,
            "risk_level": "low",
            "top_type": None,
        }

    scores = []
    for detection in detections:
        type_name = detection_type(detection)
        base_weight = _as_float(
            weights.get(type_name, get_detection_field(detection, "risk_weight")),
            0.5,
        )
        confidence = _as_float(get_detection_field(detection, "confidence"), 1.0)
        confidence = max(0.0, min(1.0, confidence))
        scores.append(base_weight * confidence)

    max_score = max(scores)
    type_count = len({detection_type(detection) for detection in detections if detection_type(detection)})
    bonus = min(0.15, max(0, type_count - 1) * 0.05)
    final_score = min(1.0, max_score + bonus)

    if final_score < 0.30:
        level = "low"
    elif final_score < 0.75:
        level = "medium"
    else:
        level = "high"

    top_detection = detections[scores.index(max_score)]
    return {
        "risk_score": round(final_score, 3),
        "risk_level": level,
        "top_type": detection_type(top_detection),
    }
