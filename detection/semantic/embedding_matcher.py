from __future__ import annotations

import math
from typing import Any, Protocol


class EmbeddingClient(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]:
        ...


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    return float(dot / (norm_a * norm_b + 1e-8))


class EmbeddingMatcher:
    """Base embedding matcher. Subclass to override search behavior."""

    def __init__(self, embedding_client: EmbeddingClient, threshold: float = 0.78):
        self.embedding_client = embedding_client
        self.threshold = threshold

    def search(self, sentence: str, top_k: int = 3) -> dict[str, Any]:
        """Search for similar vectors. Override in subclass for custom behavior."""
        return {"matched": False, "top_hit": None, "top_k": []}
