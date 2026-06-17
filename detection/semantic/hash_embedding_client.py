from __future__ import annotations

import hashlib
import math


class HashEmbeddingClient:
    """Offline deterministic embedding for local tests only."""

    def __init__(self, dimensions: int = 256):
        self.dimensions = dimensions

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(text) for text in texts]

    def _embed_one(self, text: str) -> list[float]:
        normalized = "".join(text.lower().split())
        tokens = self._char_ngrams(normalized)
        vec = [0.0] * self.dimensions
        for token in tokens:
            digest = hashlib.md5(token.encode("utf-8")).digest()
            idx = int.from_bytes(digest[:4], "big") % self.dimensions
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vec[idx] += sign
        norm = math.sqrt(sum(x * x for x in vec)) or 1.0
        return [x / norm for x in vec]

    @staticmethod
    def _char_ngrams(text: str) -> list[str]:
        if not text:
            return [""]
        grams = list(text)
        for size in (2, 3):
            grams.extend(text[i : i + size] for i in range(max(0, len(text) - size + 1)))
        return grams
