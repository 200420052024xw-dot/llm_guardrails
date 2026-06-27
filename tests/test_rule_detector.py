from core.sentence_splitter import build_semantic_detection_request
from detection.rules import detect_rules


def _context(text: str):
    contexts, _ = build_semantic_detection_request(text)
    return contexts[0]


ALLOWED = {("phone", "13800000000")}


def test_allowed_phone_passes_without_redaction():
    result = detect_rules(_context("phone is 13800000000"), allowed_entities=ALLOWED)

    assert result.level == "pass"
    assert result.redacted_text is None
    assert result.risk_types == []


def test_unknown_phone_is_redacted():
    result = detect_rules(_context("phone is 13912345678"))

    assert result.level == "sensitive"
    assert result.risk_types == ["phone"]
    assert result.redacted_text == "phone is [PHONE_1]"


def test_api_key_is_redacted():
    result = detect_rules(_context("API_KEY=sk-prod-abcdef123456"))

    assert result.level == "sensitive"
    assert "api_key" in result.risk_types
    assert result.redacted_text == "API_KEY=[API_KEY_1]"


def test_multiple_rule_spans_are_redacted_from_original_offsets():
    result = detect_rules(_context("phone 13912345678, email user@example.com"))

    assert result.level == "sensitive"
    assert result.redacted_text == "phone [PHONE_1], email [EMAIL_1]"
