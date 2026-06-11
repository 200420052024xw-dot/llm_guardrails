# detectors/pii_detector.py
import re
from detectors.schemas import make_detection

PHONE_RE = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
ID_CARD_RE = re.compile(r"(?<!\d)([1-9]\d{5})(18|19|20)\d{2}(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])\d{3}[0-9Xx](?!\d)")
BANK_CARD_RE = re.compile(r"(?<!\d)\d{13,19}(?!\d)")


def luhn_check(number: str) -> bool:
    total = 0
    reverse_digits = number[::-1]
    for i, ch in enumerate(reverse_digits):
        d = int(ch)
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def detect_pii(text: str, views: dict) -> list[dict]:
    detections = []

    for m in PHONE_RE.finditer(text):
        value = m.group(0)
        confidence = 0.95
        # 常见测试号降置信度
        if value in {"13800000000", "18888888888", "13000000000"}:
            confidence = 0.30
        detections.append(make_detection("phone", value, m.start(), m.end(), confidence, "regex", 0.55))

    for m in EMAIL_RE.finditer(text):
        value = m.group(0)
        confidence = 0.90
        if value.lower().endswith("@example.com"):
            confidence = 0.25
        detections.append(make_detection("email", value, m.start(), m.end(), confidence, "regex", 0.45))

    for m in ID_CARD_RE.finditer(text):
        value = m.group(0)
        detections.append(make_detection("id_card", value, m.start(), m.end(), 0.90, "regex", 0.80))

    for m in BANK_CARD_RE.finditer(text):
        value = m.group(0)
        # 银行卡容易和普通数字混淆，所以用 Luhn 校验提高准确率
        if luhn_check(value):
            detections.append(make_detection("bank_card", value, m.start(), m.end(), 0.85, "regex", 0.75))

    return detections


ID_WEIGHTS = [7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2]
ID_CHECK_CODES = "10X98765432"


def id_card_check(id_number: str) -> bool:
    id_number = id_number.upper()
    if len(id_number) != 18:
        return False
    if not id_number[:17].isdigit():
        return False
    total = sum(int(id_number[i]) * ID_WEIGHTS[i] for i in range(17))
    check = ID_CHECK_CODES[total % 11]
    return check == id_number[-1]
