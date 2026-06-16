import re
import unicodedata
from urllib.parse import unquote

from detectors.types import TextViews

ZERO_WIDTH_RE = re.compile(r"[\u200b\u200c\u200d\ufeff]")
WHITESPACE_RE = re.compile(r"\s+")


def normalize_text(text: str) -> TextViews:
    original = text

    normalized = unicodedata.normalize("NFKC", original)
    normalized = ZERO_WIDTH_RE.sub("", normalized)

    decoded = unquote(normalized)
    lower = decoded.lower()
    compact = WHITESPACE_RE.sub("", lower)

    return {
        "original": original,
        "normalized": normalized,
        "decoded": decoded,
        "lower": lower,
        "compact": compact,
    }
