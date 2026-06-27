from __future__ import annotations

from typing import Any


def expand_fact_texts(facts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Expand facts into individual text rows for vectorization."""
    rows: list[dict[str, Any]] = []
    for fact in facts:
        base = {
            "fact_id": fact["fact_id"],
            "fact_type": fact["fact_type"],
            "confidential_level": fact.get("confidential_level", "high"),
        }
        rows.append({**base, "text": fact["fact_text"], "text_type": "fact_text"})
        for paraphrase in fact.get("paraphrases", []):
            rows.append({**base, "text": paraphrase, "text_type": "paraphrase"})
    return rows
