from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path


ALLOWLIST_PATH = Path(__file__).resolve().parent.parent / "data" / "simulated" / "allowed_entities.jsonl"


@lru_cache(maxsize=1)
def load_allowed_entities(path: str | Path = ALLOWLIST_PATH) -> set[tuple[str, str]]:
    p = Path(path)
    if not p.exists():
        return set()

    values: set[tuple[str, str]] = set()
    for raw_line in p.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        item = json.loads(line)
        item_type = str(item.get("type", "")).strip()
        value = str(item.get("value", "")).strip()
        if item_type and value:
            values.add((item_type, value))
    return values


def is_allowed_entity(entity_type: str, value: str) -> bool:
    return (entity_type, value) in load_allowed_entities()
