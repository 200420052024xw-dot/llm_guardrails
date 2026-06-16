from __future__ import annotations

from typing import Any

from policy.detection_utils import detection_type
from policy.redactor import redact_text
from policy.risk_score import calculate_risk, load_policy


def make_message(action: str, types: list[str]) -> str:
    type_text = "、".join(types) if types else "无"
    if action == "allow":
        return "未检测到明显敏感信息，已放行。"
    if action == "redact":
        return f"检测到疑似敏感信息，已脱敏后发送。类型：{type_text}。"
    if action == "block":
        return f"检测到高风险敏感信息，为避免泄露，本次请求未发送给模型。类型：{type_text}。"
    return "已完成安全检测。"


def make_decision(text: str, detections: list[Any]) -> dict:
    policy = load_policy()
    block_types = set(policy.get("block_types", []))
    redact_types = set(policy.get("redact_types", []))
    thresholds = policy.get("thresholds", {})

    risk = calculate_risk(detections)
    detected_types = sorted({detection_type(detection) for detection in detections if detection_type(detection)})

    if not detections:
        return {
            "action": "allow",
            "risk_score": 0.0,
            "risk_level": "low",
            "redacted_text": text,
            "message": make_message("allow", []),
        }

    if any(type_name in block_types for type_name in detected_types):
        return {
            "action": "block",
            "risk_score": max(risk["risk_score"], 0.90),
            "risk_level": "high",
            "redacted_text": None,
            "message": make_message("block", detected_types),
        }

    redact_max = float(thresholds.get("redact_max", 0.75))
    allow_max = float(thresholds.get("allow_max", 0.30))

    if risk["risk_score"] >= redact_max:
        return {
            "action": "block",
            "risk_score": risk["risk_score"],
            "risk_level": "high",
            "redacted_text": None,
            "message": make_message("block", detected_types),
        }

    if risk["risk_score"] >= allow_max:
        redaction = redact_text(text, detections, redact_types)
        return {
            "action": "redact",
            "risk_score": risk["risk_score"],
            "risk_level": risk["risk_level"],
            "redacted_text": redaction["redacted_text"],
            "message": make_message("redact", detected_types),
        }

    return {
        "action": "allow",
        "risk_score": risk["risk_score"],
        "risk_level": risk["risk_level"],
        "redacted_text": text,
        "message": make_message("allow", detected_types),
    }


decision = make_decision
