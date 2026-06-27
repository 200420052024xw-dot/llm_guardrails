from core.sentence_splitter import build_semantic_detection_request
from core.schemas import SemanticDetectionResult
from detection import semantic_client
from detection.semantic_client import Detector


def _pass_semantic(request):
    return SemanticDetectionResult(
        sentence_id=request.sentence_id,
        confidential_level="sensitive" if request.rule_result == "sensitive" else "pass",
        risk_score=0.0,
        risk_types=[],
        evidence_types=[],
        redacted_text=request.text if request.rule_result == "sensitive" else None,
        message="fake semantic pass",
    )


def test_rule_redaction_survives_semantic_pass(monkeypatch):
    monkeypatch.setattr(semantic_client, "detect_confidential_sentence", _pass_semantic)
    detector = Detector()
    contexts, original_sentences = build_semantic_detection_request("phone is 13912345678")

    detect_results = detector.start_detect(contexts)
    final = detector.analyze_detect_results("req_1", "phone is 13912345678", detect_results, original_sentences)

    assert final.action == "redact"
    assert final.final_text == "phone is [PHONE_1]"
    assert final.sentence_results[0].confidential_level == "sensitive"
    assert final.sentence_results[0].risk_types == ["phone"]
    assert "rule_match" in final.sentence_results[0].evidence_types


def test_allowed_phone_can_remain_pass(monkeypatch):
    monkeypatch.setattr(semantic_client, "detect_confidential_sentence", _pass_semantic)
    detector = Detector(allowed_entities={("phone", "13800000000")})
    contexts, original_sentences = build_semantic_detection_request("phone is 13800000000")

    detect_results = detector.start_detect(contexts)
    final = detector.analyze_detect_results("req_2", "phone is 13800000000", detect_results, original_sentences)

    assert final.action == "pass"
    assert final.final_text == "phone is 13800000000"


def test_api_key_is_redacted_before_semantic(monkeypatch):
    seen_texts = []

    def fake_semantic(request):
        seen_texts.append(request.text)
        return _pass_semantic(request)

    monkeypatch.setattr(semantic_client, "detect_confidential_sentence", fake_semantic)
    detector = Detector()
    contexts, original_sentences = build_semantic_detection_request("API_KEY=sk-prod-abcdef123456")

    detect_results = detector.start_detect(contexts)
    final = detector.analyze_detect_results(
        "req_3",
        "API_KEY=sk-prod-abcdef123456",
        detect_results,
        original_sentences,
    )

    assert seen_texts == ["API_KEY=[API_KEY_1]"]
    assert final.action == "redact"
    assert final.final_text == "API_KEY=[API_KEY_1]"
    assert "api_key" in final.sentence_results[0].risk_types


def test_redacted_placeholder_confidential_does_not_block(monkeypatch):
    def fake_semantic(request):
        return SemanticDetectionResult(
            sentence_id=request.sentence_id,
            confidential_level="confidential",
            risk_score=0.92,
            risk_types=["api_key"],
            evidence_types=["model_detection"],
            redacted_text=None,
            message="fake model treated placeholder as api key",
        )

    monkeypatch.setattr(semantic_client, "detect_confidential_sentence", fake_semantic)
    detector = Detector()
    contexts, original_sentences = build_semantic_detection_request("API_KEY=sk-prod-abcdef123456")

    detect_results = detector.start_detect(contexts)
    final = detector.analyze_detect_results(
        "req_4",
        "API_KEY=sk-prod-abcdef123456",
        detect_results,
        original_sentences,
    )

    assert final.action == "redact"
    assert final.final_text == "API_KEY=[API_KEY_1]"
    assert final.sentence_results[0].confidential_level == "sensitive"
    assert "api_key" in final.sentence_results[0].risk_types


def test_redacted_sentence_with_real_semantic_risk_can_still_block(monkeypatch):
    def fake_semantic(request):
        return SemanticDetectionResult(
            sentence_id=request.sentence_id,
            confidential_level="confidential",
            risk_score=0.88,
            risk_types=["pricing_strategy"],
            evidence_types=["model_detection"],
            redacted_text=None,
            message="fake model found pricing strategy",
        )

    monkeypatch.setattr(semantic_client, "detect_confidential_sentence", fake_semantic)
    detector = Detector()
    text = "内部底价方案联系人 13912345678"
    contexts, original_sentences = build_semantic_detection_request(text)

    detect_results = detector.start_detect(contexts)
    final = detector.analyze_detect_results("req_5", text, detect_results, original_sentences)

    assert final.action == "block"
    assert final.final_text is None
    assert final.sentence_results[0].confidential_level == "confidential"
