from core.sentence_splitter import build_semantic_detection_request
from core.schemas import ChatRequest, ChatResponse
from detection.semantic_client import Detector
from logs.logger import write_stage_record
from llm.call_llm import call_llm
from datetime import datetime

detector = Detector()

class Orchestrator:
    def __init__(self, default_model: str = "deepseek-v4-flash-260425"):
        self.default_model = default_model

    async def process(self, request: ChatRequest) -> ChatResponse:
        request_id = datetime.now().strftime("%Y%m%d_%H_%M_%S")
        write_stage_record(request_id,"01_chat_request",request)

        # 生成识别文本
        request_sentences, original_sentences = build_semantic_detection_request(request.original_text)
        write_stage_record(request_id,"02_text_split",request_sentences)

        # 请求识别接口
        detect_results = detector.start_detect(request_sentences)
        write_stage_record(request_id,"03_sentences_detect",detect_results)

        # 综合识别结果
        detection_analysis_result = detector.analyze_detect_results(request_id,request.original_text,detect_results,original_sentences)
        write_stage_record(request_id,"04_detection_analysis",detection_analysis_result)

        # 调用模型
        llm_response = None
        model = request.model or self.default_model
        if detection_analysis_result.action == "pass":
            llm_response = call_llm(detection_analysis_result.final_text, model=model)
        elif detection_analysis_result.action == "redact":
            llm_input = detection_analysis_result.final_text
            llm_response = call_llm(llm_input, model=model)

        return ChatResponse(
            request_id=request_id,
            action=detection_analysis_result.action,
            risk_score=detection_analysis_result.risk_score,
            message=detection_analysis_result.message,
            final_text=detection_analysis_result.final_text,
            llm_response=llm_response
        )
