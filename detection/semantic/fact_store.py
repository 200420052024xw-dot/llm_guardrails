from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def load_facts(path: str | Path = "data/simulated/confidential_facts.jsonl") -> list[dict[str, Any]]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"fact file not found: {path}")

    facts: list[dict[str, Any]] = []
    with p.open(encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            if not line.strip():
                continue
            item = json.loads(line)
            for field in ("fact_id", "fact_type", "confidential_level", "fact_text"):
                if field not in item:
                    raise ValueError(f"{path}:{line_no} missing required field: {field}")
            facts.append(item)
    return facts


def expand_fact_texts(facts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for fact in facts:
        base = {
            "fact_id": fact["fact_id"],
            "fact_type": fact["fact_type"],
            "confidential_level": fact["confidential_level"],
        }
        rows.append({**base, "text": fact["fact_text"], "text_type": "fact_text"})
        for paraphrase in fact.get("paraphrases", []):
            rows.append({**base, "text": paraphrase, "text_type": "paraphrase"})
    return rows


def file_sha256(path: str | Path) -> str:
    p = Path(path)
    hasher = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()
