from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def get_detection_field(detection: Any, field: str, default: Any = None) -> Any:
    if isinstance(detection, Mapping):
        return detection.get(field, default)
    return getattr(detection, field, default)


def detection_type(detection: Any) -> str | None:
    value = get_detection_field(detection, "type")
    return value if isinstance(value, str) else None


def detection_start(detection: Any) -> int | None:
    value = get_detection_field(detection, "start")
    return value if isinstance(value, int) else None


def detection_end(detection: Any) -> int | None:
    value = get_detection_field(detection, "end")
    return value if isinstance(value, int) else None
