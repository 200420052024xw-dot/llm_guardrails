from __future__ import annotations

from core.schemas import RuleDetectionResult, RuleRiskType

from .allowlist_store import is_allowed_entity
from .patterns import PATTERNS, PII_TYPES, has_rule_candidate, valid_id_card, valid_luhn
from .redactor import RuleMatch, redact_text


def detect_rules(
    context: dict[str, str],
    allowed_entities: set[tuple[str, str]] | None = None,
) -> RuleDetectionResult:
    sentence_id = context["sentence_id"]
    original = context["original"]
    decoded = context["decoded"]

    if not has_rule_candidate(decoded):
        return RuleDetectionResult(sentence_id=sentence_id)

    matches = _find_matches(original, allowed_entities)
    if not matches:
        return RuleDetectionResult(sentence_id=sentence_id)

    redacted_text = redact_text(original, matches)
    risk_types: list[RuleRiskType] = sorted({match.type for match in matches})  # type: ignore[list-item]

    return RuleDetectionResult(
        sentence_id=sentence_id,
        level="sensitive",
        risk_types=risk_types,
        redacted_text=redacted_text,
        message="rule matched: " + ", ".join(risk_types),
    )


def _find_matches(
    text: str,
    allowed_entities: set[tuple[str, str]] | None = None,
) -> list[RuleMatch]:
    matches: list[RuleMatch] = []
    occupied: list[tuple[int, int]] = []

    for pattern in PATTERNS:
        for match in pattern.regex.finditer(text):
            start, end = match.span(pattern.value_group)
            value = match.group(pattern.value_group)
            if start < 0 or end <= start:
                continue
            if _overlaps(start, end, occupied):
                continue
            if pattern.type == "id_card" and not valid_id_card(value):
                continue
            if pattern.type == "bank_card" and not valid_luhn(value):
                continue
            is_public = (
                (pattern.type, value) in allowed_entities
                if allowed_entities is not None
                else is_allowed_entity(pattern.type, value)
            )
            if pattern.type in PII_TYPES and is_public:
                continue
            matches.append(RuleMatch(pattern.type, value, start, end))
            occupied.append((start, end))

    return matches


def _overlaps(start: int, end: int, occupied: list[tuple[int, int]]) -> bool:
    return any(start < used_end and end > used_start for used_start, used_end in occupied)
