import math
import re

from core.schemas import Detection
from detectors.types import TextViews

PRIVATE_KEY_RE = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----")
JWT_RE = re.compile(r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+")
BEARER_RE = re.compile(r"Bearer\s+([A-Za-z0-9._\-]{20,})", re.IGNORECASE)
PASSWORD_RE = re.compile(r"(?i)(password|passwd|pwd)\s*[:=]\s*['\"]?([^'\"\s]{6,})")
API_KEY_RE = re.compile(r"(?i)(api[_-]?key|secret[_-]?key|access[_-]?token|token)\s*[:=]\s*['\"]?([A-Za-z0-9_\-]{12,})")
CONNECTION_STRING_RE = re.compile(r"(?i)(mysql|postgres(?:ql)?|mongodb|redis)://[^\s]+")


class SecretDetector:
    name = "secrets"

    def detect(self, text: str, text_views: TextViews) -> list[Detection]:
        detections = []
        detections.extend(self._detect_private_keys(text))
        detections.extend(self._detect_jwts(text))
        detections.extend(self._detect_bearer_tokens(text))
        detections.extend(self._detect_passwords(text))
        detections.extend(self._detect_api_keys(text))
        detections.extend(self._detect_connection_strings(text))
        return detections

    def _detect_private_keys(self, text: str) -> list[Detection]:
        return [
            Detection(
                type="private_key",
                text=match.group(0),
                start=match.start(),
                end=match.end(),
                confidence=0.99,
                source="regex",
                risk_weight=0.95,
            )
            for match in PRIVATE_KEY_RE.finditer(text)
        ]

    def _detect_jwts(self, text: str) -> list[Detection]:
        return [
            Detection(
                type="jwt",
                text=match.group(0),
                start=match.start(),
                end=match.end(),
                confidence=0.92,
                source="regex",
                risk_weight=0.9,
            )
            for match in JWT_RE.finditer(text)
        ]

    def _detect_bearer_tokens(self, text: str) -> list[Detection]:
        return [
            Detection(
                type="bearer_token",
                text=match.group(0),
                start=match.start(),
                end=match.end(),
                confidence=0.9,
                source="regex",
                risk_weight=0.9,
            )
            for match in BEARER_RE.finditer(text)
        ]

    def _detect_passwords(self, text: str) -> list[Detection]:
        return [
            Detection(
                type="password",
                text=match.group(0),
                start=match.start(),
                end=match.end(),
                confidence=0.85,
                source="regex",
                risk_weight=0.85,
            )
            for match in PASSWORD_RE.finditer(text)
        ]

    def _detect_api_keys(self, text: str) -> list[Detection]:
        detections = []
        for match in API_KEY_RE.finditer(text):
            value = match.group(0)
            candidate = match.group(2)
            confidence = 0.75
            if shannon_entropy(candidate) > 3.5 and len(candidate) >= 16:
                confidence = 0.9
            detections.append(
                Detection(
                    type="api_key",
                    text=value,
                    start=match.start(),
                    end=match.end(),
                    confidence=confidence,
                    source="regex",
                    risk_weight=0.9,
                )
            )
        return detections

    def _detect_connection_strings(self, text: str) -> list[Detection]:
        return [
            Detection(
                type="connection_string",
                text=match.group(0),
                start=match.start(),
                end=match.end(),
                confidence=0.9,
                source="regex",
                risk_weight=0.9,
            )
            for match in CONNECTION_STRING_RE.finditer(text)
        ]


def shannon_entropy(value: str) -> float:
    if not value:
        return 0.0
    frequencies = {char: value.count(char) for char in set(value)}
    return -sum((count / len(value)) * math.log2(count / len(value)) for count in frequencies.values())
