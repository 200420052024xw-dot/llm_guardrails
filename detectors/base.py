from typing import Protocol

from core.schemas import Detection
from detectors.types import TextViews


class BaseDetector(Protocol):
    """Common interface for sensitive-content detectors."""

    name: str

    def detect(self, text: str, text_views: TextViews) -> list[Detection]:
        ...
