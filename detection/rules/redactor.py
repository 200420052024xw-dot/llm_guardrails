from __future__ import annotations

from dataclasses import dataclass


REDACTION_LABELS = {
    "phone": "PHONE",
    "email": "EMAIL",
    "id_card": "ID_CARD",
    "bank_card": "BANK_CARD",
    "api_key": "API_KEY",
    "bearer_token": "TOKEN",
    "jwt": "JWT",
    "password": "PASSWORD",
    "private_key": "PRIVATE_KEY",
    "connection_string": "CONNECTION_STRING",
}


@dataclass(frozen=True)
class RuleMatch:
    type: str
    value: str
    start: int
    end: int


def redact_text(text: str, matches: list[RuleMatch]) -> str:
    counters: dict[str, int] = {}
    redacted = text

    for match in sorted(matches, key=lambda item: item.start, reverse=True):
        counters[match.type] = counters.get(match.type, 0) + 1
        label = REDACTION_LABELS.get(match.type, match.type.upper())
        replacement = f"[{label}_{counters[match.type]}]"
        redacted = redacted[: match.start] + replacement + redacted[match.end :]

    return redacted
