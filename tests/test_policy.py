from types import SimpleNamespace

from policy.decision import decision, make_decision


def test_allow_when_no_detection():
    result = make_decision("你好，请帮我写一首诗", [])

    assert result["action"] == "allow"
    assert result["risk_score"] == 0.0
    assert result["risk_level"] == "low"
    assert result["redacted_text"] == "你好，请帮我写一首诗"
    assert result["message"]


def test_decision_alias_matches_make_decision():
    text = "你好，请帮我写一首诗"

    assert decision is make_decision
    assert decision(text, []) == make_decision(text, [])


def test_redact_phone():
    text = "客户电话13812345678"
    detections = [
        {
            "type": "phone",
            "text": "13812345678",
            "start": 4,
            "end": 15,
            "confidence": 0.95,
            "source": "regex",
            "risk_weight": 0.55,
        }
    ]

    result = make_decision(text, detections)

    assert result["action"] == "redact"
    assert "[PHONE_" in result["redacted_text"]
    assert "13812345678" not in result["redacted_text"]


def test_redact_phone_with_detection_object():
    text = "客户电话13812345678"
    detections = [
        SimpleNamespace(
            type="phone",
            text="13812345678",
            start=4,
            end=15,
            confidence=0.95,
            source="regex",
            risk_weight=0.55,
        )
    ]

    result = make_decision(text, detections)

    assert result["action"] == "redact"
    assert "[PHONE_" in result["redacted_text"]
    assert "13812345678" not in result["redacted_text"]


def test_block_api_key():
    text = "api_key=sk-prod-abcdef123456"
    detections = [
        {
            "type": "api_key",
            "text": text,
            "start": 0,
            "end": len(text),
            "confidence": 0.90,
            "source": "regex_entropy",
            "risk_weight": 0.90,
        }
    ]

    result = make_decision(text, detections)

    assert result["action"] == "block"
    assert result["risk_level"] == "high"
    assert result["redacted_text"] is None


def test_redact_multiple_spans():
    text = "客户星河集团，电话13812345678"
    detections = [
        {
            "type": "customer_name",
            "text": "星河集团",
            "start": 2,
            "end": 6,
            "confidence": 0.90,
            "source": "dict",
            "risk_weight": 0.65,
        },
        {
            "type": "phone",
            "text": "13812345678",
            "start": 9,
            "end": 20,
            "confidence": 0.95,
            "source": "regex",
            "risk_weight": 0.55,
        },
    ]

    result = make_decision(text, detections)

    assert result["action"] == "redact"
    assert "星河集团" not in result["redacted_text"]
    assert "13812345678" not in result["redacted_text"]


def test_block_by_high_risk_score():
    text = "身份证号110101199001011234"
    detections = [
        {
            "type": "id_card",
            "text": "110101199001011234",
            "start": 4,
            "end": 22,
            "confidence": 1.0,
            "source": "regex",
            "risk_weight": 0.80,
        }
    ]

    result = make_decision(text, detections)

    assert result["action"] == "block"
    assert result["risk_score"] >= 0.75
    assert result["redacted_text"] is None
