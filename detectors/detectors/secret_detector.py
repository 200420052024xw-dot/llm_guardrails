# detectors/secret_detector.py
import re
import math
from detectors.schemas import make_detection

PRIVATE_KEY_RE = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----")
JWT_RE = re.compile(r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+")
BEARER_RE = re.compile(r"Bearer\s+([A-Za-z0-9._\-]{20,})", re.IGNORECASE)
PASSWORD_RE = re.compile(r"(?i)(password|passwd|pwd)\s*[:=]\s*['\"]?([^'\"\s]{6,})")
API_KEY_RE = re.compile(r"(?i)(api[_-]?key|secret[_-]?key|access[_-]?token|token)\s*[:=]\s*['\"]?([A-Za-z0-9_\-]{12,})")
CONN_RE = re.compile(r"(?i)(mysql|postgres(?:ql)?|mongodb|redis)://[^\s]+")


def shannon_entropy(s: str) -> float:
    if not s:
        return 0.0
    freq = {ch: s.count(ch) for ch in set(s)}
    return -sum((c / len(s)) * math.log2(c / len(s)) for c in freq.values())


def detect_secret(text: str, views: dict) -> list[dict]:
    detections = []

    for m in PRIVATE_KEY_RE.finditer(text):
        detections.append(make_detection("private_key", m.group(0), m.start(), m.end(), 0.99, "regex", 0.95))

    for m in JWT_RE.finditer(text):
        detections.append(make_detection("jwt", m.group(0), m.start(), m.end(), 0.92, "regex", 0.90))

    for m in BEARER_RE.finditer(text):
        detections.append(make_detection("bearer_token", m.group(0), m.start(), m.end(), 0.90, "regex", 0.90))

    for m in PASSWORD_RE.finditer(text):
        value = m.group(0)
        detections.append(make_detection("password", value, m.start(), m.end(), 0.85, "regex", 0.85))

    for m in API_KEY_RE.finditer(text):
        value = m.group(0)
        candidate = m.group(2)
        confidence = 0.75
        if shannon_entropy(candidate) > 3.5 and len(candidate) >= 16:
            confidence = 0.90
        detections.append(make_detection("api_key", value, m.start(), m.end(), confidence, "regex", 0.90))

    for m in CONN_RE.finditer(text):
        detections.append(make_detection("connection_string", m.group(0), m.start(), m.end(), 0.90, "regex", 0.90))

    return detections
