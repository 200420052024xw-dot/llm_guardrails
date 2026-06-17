from __future__ import annotations

import json
import math
from pathlib import Path
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
    def __init__(self, embedding_client: EmbeddingClient, threshold: float = 0.78):
        self.embedding_client = embedding_client
        self.threshold = threshold
        self.rows: list[dict[str, Any]] = []
        self.embeddings: list[list[float]] = []

    def build(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows
        texts = [r["text"] for r in rows]
        self.embeddings = self.embedding_client.embed(texts) if texts else []

    def load_index(self, index_path: str | Path, source_sha256: str, embedding_model: str) -> bool:
        p = Path(index_path)
        if not p.exists():
            return False

        with p.open(encoding="utf-8") as f:
            data = json.load(f)

        if data.get("version") != 1:
            return False
        if data.get("source_sha256") != source_sha256:
            return False
        if data.get("embedding_model") != embedding_model:
            return False

        rows = data.get("rows", [])
        embeddings = data.get("embeddings", [])
        if not isinstance(rows, list) or not isinstance(embeddings, list) or len(rows) != len(embeddings):
            return False

        self.rows = rows
        self.embeddings = embeddings
        return True

    def save_index(self, index_path: str | Path, source_sha256: str, embedding_model: str) -> None:
        p = Path(index_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        safe_rows = [
            {
                "fact_id": row["fact_id"],
                "fact_type": row["fact_type"],
                "text_type": row["text_type"],
                "confidential_level": row["confidential_level"],
            }
            for row in self.rows
        ]
        data = {
            "version": 1,
            "source_sha256": source_sha256,
            "embedding_model": embedding_model,
            "rows_count": len(safe_rows),
            "rows": safe_rows,
            "embeddings": self.embeddings,
        }
        with p.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)

    def build_or_load_index(
        self,
        rows: list[dict[str, Any]],
        index_path: str | Path,
        source_sha256: str,
        embedding_model: str,
    ) -> str:
        if self.load_index(index_path, source_sha256=source_sha256, embedding_model=embedding_model):
            return "loaded"
        self.build(rows)
        self.save_index(index_path, source_sha256=source_sha256, embedding_model=embedding_model)
        return "built"

    def search(self, sentence: str, top_k: int = 3) -> dict[str, Any]:
        if not self.rows or not self.embeddings:
            return {"matched": False, "top_hit": None, "top_k": []}

        query_vec = self.embedding_client.embed([sentence])[0]
        scores = [cosine(query_vec, vec) for vec in self.embeddings]
        order = sorted(range(len(scores)), key=lambda idx: scores[idx], reverse=True)[:top_k]

        hits: list[dict[str, Any]] = []
        for idx in order:
            row = self.rows[idx]
            hits.append(
                {
                    "fact_id": row["fact_id"],
                    "fact_type": row["fact_type"],
                    "text_type": row["text_type"],
                    "confidential_level": row["confidential_level"],
                    "similarity": round(scores[idx], 6),
                }
            )
        best = hits[0] if hits else None
        return {
            "matched": bool(best and best["similarity"] >= self.threshold),
            "top_hit": best,
            "top_k": hits,
        }
