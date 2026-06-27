from __future__ import annotations

from functools import lru_cache


@lru_cache(maxsize=1)
def load_allowed_entities() -> set[tuple[str, str]]:
    """Load allowed entities. Now uses database only (PublicEntry)."""
    return set()


def is_allowed_entity(entity_type: str, value: str) -> bool:
    return (entity_type, value) in load_allowed_entities()
