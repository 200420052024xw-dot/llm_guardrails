import re

from core.schemas import Detection
from detectors.types import TextViews

PHONE_RE = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
ID_CARD_RE = re.compile(
    r"(?<!\d)([1-9]\d{5})(18|19|20)\d{2}(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])\d{3}[0-9Xx](?!\d)"
)
BANK_CARD_RE = re.compile(r"(?<!\d)\d{13,19}(?!\d)")

TEST_PHONE_NUMBERS = {"13800000000", "18888888888", "13000000000"}
TEST_EMAIL_DOMAINS = {"@example.com"}

ID_WEIGHTS = [7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2]
ID_CHECK_CODES = "10X98765432"


class PiiDetector:
    name = "pii"

    def detect(self, text: str, text_views: TextViews) -> list[Detection]:
        detections = []
        detections.extend(self._detect_phone_numbers(text))
        detections.extend(self._detect_emails(text))
        detections.extend(self._detect_id_cards(text))
        detections.extend(self._detect_bank_cards(text))
        return detections

    def _detect_phone_numbers(self, text: str) -> list[Detection]:
        detections = []
        for match in PHONE_RE.finditer(text):
            value = match.group(0)
            confidence = 0.3 if value in TEST_PHONE_NUMBERS else 0.95
            detections.append(
                Detection(
                    type="phone",
                    text=value,
                    start=match.start(),
                    end=match.end(),
                    confidence=confidence,
                    source="regex",
                    risk_weight=0.55,
                )
            )
        return detections

    def _detect_emails(self, text: str) -> list[Detection]:
        detections = []
        for match in EMAIL_RE.finditer(text):
            value = match.group(0)
            value_lower = value.lower()
            confidence = 0.9
            if any(value_lower.endswith(domain) for domain in TEST_EMAIL_DOMAINS):
                confidence = 0.25
            detections.append(
                Detection(
                    type="email",
                    text=value,
                    start=match.start(),
                    end=match.end(),
                    confidence=confidence,
                    source="regex",
                    risk_weight=0.45,
                )
            )
        return detections

    def _detect_id_cards(self, text: str) -> list[Detection]:
        detections = []
        for match in ID_CARD_RE.finditer(text):
            value = match.group(0)
            if not is_valid_id_card(value):
                continue
            detections.append(
                Detection(
                    type="id_card",
                    text=value,
                    start=match.start(),
                    end=match.end(),
                    confidence=0.9,
                    source="regex",
                    risk_weight=0.8,
                )
            )
        return detections

    def _detect_bank_cards(self, text: str) -> list[Detection]:
        detections = []
        for match in BANK_CARD_RE.finditer(text):
            value = match.group(0)
            if not passes_luhn_check(value):
                continue
            detections.append(
                Detection(
                    type="bank_card",
                    text=value,
                    start=match.start(),
                    end=match.end(),
                    confidence=0.85,
                    source="regex",
                    risk_weight=0.75,
                )
            )
        return detections


def passes_luhn_check(number: str) -> bool:
    total = 0
    for index, char in enumerate(reversed(number)):
        digit = int(char)
        if index % 2 == 1:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return total % 10 == 0


def is_valid_id_card(id_number: str) -> bool:
    id_number = id_number.upper()
    if len(id_number) != 18:
        return False
    if not id_number[:17].isdigit():
        return False
    total = sum(int(id_number[index]) * ID_WEIGHTS[index] for index in range(17))
    expected_check_code = ID_CHECK_CODES[total % 11]
    return expected_check_code == id_number[-1]
