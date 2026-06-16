from __future__ import annotations

from typing import Any

from policy.detection_utils import detection_end, detection_start, detection_type


TOKEN_PREFIX = {
    "phone": "PHONE",
    "email": "EMAIL",
    "person": "PERSON",
    "id_card": "ID_CARD",
    "bank_card": "BANK_CARD",
    "internal_project": "PROJECT",
    "customer_name": "CUSTOMER",
    "internal_system": "SYSTEM",
    "classification_label": "CLASSIFICATION",
    "pricing": "PRICE",
    "password": "SECRET",
    "api_key": "SECRET",
    "private_key": "SECRET",
    "jwt": "SECRET",
    "bearer_token": "SECRET",
    "connection_string": "SECRET",
}


def filter_redactable(detections: list[Any], redact_types: set[str], text_length: int) -> list[dict[str, Any]]:
    result = []
    for detection in detections:
        type_name = detection_type(detection)
        if type_name not in redact_types:
            continue
        start = detection_start(detection)
        end = detection_end(detection)
        if start is None or end is None:
            continue
        if start < 0 or end > text_length or start >= end:
            continue
        result.append({"type": type_name, "start": start, "end": end})
    return result


def remove_overlaps(detections: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sorted_detections = sorted(
        detections,
        key=lambda detection: (
            detection["start"],
            -(detection["end"] - detection["start"]),
        ),
    )

    result = []
    for detection in sorted_detections:
        has_overlap = any(
            not (
                detection["end"] <= existing["start"]
                or detection["start"] >= existing["end"]
            )
            for existing in result
        )
        if not has_overlap:
            result.append(detection)
    return result


def redact_text(text: str, detections: list[Any], redact_types: set[str]) -> dict[str, Any]:
    targets = filter_redactable(detections, redact_types, len(text))
    targets = remove_overlaps(targets)

    counters = {}
    replacements = []
    mapping = {}

    for detection in sorted(targets, key=lambda item: item["start"]):
        type_name = detection["type"]
        prefix = TOKEN_PREFIX.get(type_name, "SENSITIVE")
        counters[prefix] = counters.get(prefix, 0) + 1
        token = f"[{prefix}_{counters[prefix]}]"
        replacements.append((detection["start"], detection["end"], token))
        mapping[token] = text[detection["start"] : detection["end"]]

    redacted = text
    for start, end, token in sorted(replacements, key=lambda item: item[0], reverse=True):
        redacted = redacted[:start] + token + redacted[end:]

    return {
        "redacted_text": redacted,
        "mapping": mapping,
    }
