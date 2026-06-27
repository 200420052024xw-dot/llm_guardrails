from __future__ import annotations

from dataclasses import dataclass
import re


PII_TYPES = {"phone", "email", "id_card", "bank_card"}
SECRET_TYPES = {
    "api_key",
    "bearer_token",
    "jwt",
    "password",
    "private_key",
    "connection_string",
}


@dataclass(frozen=True)
class RulePattern:
    type: str
    regex: re.Pattern[str]
    value_group: int = 0


PATTERNS: tuple[RulePattern, ...] = (
    RulePattern(
        "private_key",
        re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]+?-----END [A-Z ]*PRIVATE KEY-----"),
    ),
    RulePattern(
        "connection_string",
        re.compile(r"(?i)\b(?:postgresql|postgres|mysql|mongodb|redis)://[^\s'\"<>]+"),
    ),
    RulePattern("bearer_token", re.compile(r"(?i)\bBearer\s+([A-Za-z0-9._~+/=-]{16,})\b"), 1),
    RulePattern("jwt", re.compile(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b")),
    RulePattern(
        "api_key",
        re.compile(
            r"(?i)\b(?:api[_-]?key|secret[_-]?key|access[_-]?token|sk)\s*[:=]\s*([A-Za-z0-9_\-]{12,})\b"
        ),
        1,
    ),
    RulePattern("api_key", re.compile(r"\bsk-[A-Za-z0-9_\-]{12,}\b")),
    RulePattern("password", re.compile(r"(?i)\b(?:password|passwd|pwd)\s*[:=]\s*(\S{6,})"), 1),
    RulePattern("phone", re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")),
    RulePattern("email", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
    RulePattern("id_card", re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)")),
    RulePattern("bank_card", re.compile(r"(?<!\d)\d{16,19}(?!\d)")),
)


def has_rule_candidate(text: str) -> bool:
    lowered = text.lower()
    return (
        any(ch.isdigit() for ch in text)
        or "@" in text
        or "=" in text
        or ":" in text
        or "bearer" in lowered
        or "token" in lowered
        or "key" in lowered
        or "password" in lowered
        or "passwd" in lowered
        or "pwd" in lowered
        or "begin" in lowered
    )


def valid_id_card(value: str) -> bool:
    if not re.fullmatch(r"\d{17}[\dXx]", value):
        return False
    weights = [7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2]
    checks = "10X98765432"
    total = sum(int(value[i]) * weights[i] for i in range(17))
    return checks[total % 11] == value[-1].upper()


def valid_luhn(value: str) -> bool:
    digits = [int(ch) for ch in value if ch.isdigit()]
    if len(digits) != len(value):
        return False
    checksum = 0
    parity = len(digits) % 2
    for index, digit in enumerate(digits):
        if index % 2 == parity:
            digit *= 2
            if digit > 9:
                digit -= 9
        checksum += digit
    return checksum % 10 == 0
