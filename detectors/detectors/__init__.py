"""guard-gateway — content security detection gateway.

Detects PII, secrets/credentials, and dictionary-based sensitive content
in text, with text normalization and deduplication.
"""

from detectors.schemas import make_detection
from detectors.normalizer import normalize_text
from detectors.pii_detector import detect_pii, luhn_check, id_card_check
from detectors.secret_detector import detect_secret, shannon_entropy
from detectors.dict_detector import detect_dictionary, load_dictionary
from detectors.runner import run_detectors, remove_low_confidence, dedupe_overlaps

__all__ = [
    "make_detection",
    "normalize_text",
    "detect_pii",
    "detect_secret",
    "detect_dictionary",
    "run_detectors",
    "remove_low_confidence",
    "dedupe_overlaps",
    "luhn_check",
    "id_card_check",
    "shannon_entropy",
    "load_dictionary",
]
