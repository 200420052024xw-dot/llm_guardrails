from datetime import datetime

from core.sentence_splitter import build_semantic_detection_request
from core.schemas import ChatRequest, ChatResponse
from detection.semantic_client import Detector
from llm.call_llm import call_llm
from logs.logger import write_stage_record


detector = Detector()


class Orchestrator:
    def __init__(self, default_model: str = "deepseek-v4-flash-260425"):
        self.default_model = default_model

    async def process(self, request: ChatRequest) -> ChatResponse:
        request_id = datetime.now().strftime("%Y%m%d_%H_%M_%S")
        write_stage_record(request_id, "01_chat_request", {
            "input": None,
            "output": request,
        })

        request_sentences, original_sentences = build_semantic_detection_request(request.original_text)
        write_stage_record(request_id, "02_text_split", {
            "input": {
                "original_text": request.original_text,
            },
            "output": {
                "semantic_detection_requests": request_sentences,
                "original_sentences": original_sentences,
            },
        })

        detect_results, detect_traces = detector.start_detect_with_trace(request_sentences)
        write_stage_record(request_id, "03_sentence_step_trace", {
            "input": request_sentences,
            "output": {
                "sentence_results": detect_results,
                "steps": detect_traces,
            },
        })
        write_stage_record(request_id, "04_rule_match", {
            "input": request_sentences,
            "output": [item.get("rule_match") for item in detect_traces],
        })
        write_stage_record(request_id, "05_similarity_match", {
            "input": [item.get("semantic_request", {}).get("output") for item in detect_traces],
            "output": [item.get("similarity_match") for item in detect_traces],
        })
        write_stage_record(request_id, "06_model_recognition", {
            "input": [item.get("semantic_request", {}).get("output") for item in detect_traces],
            "output": [item.get("model_recognition") for item in detect_traces],
        })

        detection_analysis_result = detector.analyze_detect_results(
            request_id,
            request.original_text,
            detect_results,
            original_sentences,
        )
        write_stage_record(request_id, "07_comprehensive_evaluation", {
            "input": {
                "original_text": request.original_text,
                "sentence_results": detect_results,
                "original_sentences": original_sentences,
                "sentence_evaluations": [
                    item.get("comprehensive_evaluation")
                    for item in detect_traces
                ],
            },
            "output": detection_analysis_result,
        })

        llm_response = None
        model = request.model or self.default_model
        if detection_analysis_result.action in {"pass", "redact"}:
            llm_input = detection_analysis_result.final_text
            llm_log_input = {
                "model": model,
                "text": llm_input,
                "action": detection_analysis_result.action,
            }
            try:
                llm_response = call_llm(llm_input or "", model=model)
            except Exception as exc:
                write_stage_record(request_id, "08_call_llm", {
                    "called": True,
                    "input": llm_log_input,
                    "output": {
                        "llm_response": None,
                        "error": f"{type(exc).__name__}: {exc}",
                    },
                })
                raise
            else:
                write_stage_record(request_id, "08_call_llm", {
                    "called": True,
                    "input": llm_log_input,
                    "output": {
                        "llm_response": llm_response,
                    },
                })
        else:
            write_stage_record(request_id, "08_call_llm", {
                "called": False,
                "input": {
                    "model": model,
                    "text": None,
                    "action": detection_analysis_result.action,
                },
                "output": {
                    "llm_response": None,
                    "reason": "LLM_NOT_CALLED: request blocked by guardrails",
                },
            })

        response = ChatResponse(
            request_id=request_id,
            action=detection_analysis_result.action,
            risk_score=detection_analysis_result.risk_score,
            message=detection_analysis_result.message,
            final_text=detection_analysis_result.final_text,
            llm_response=llm_response,
        )
        write_stage_record(request_id, "09_chat_response", {
            "input": {
                "detection_analysis_result": detection_analysis_result,
                "llm_response": llm_response,
            },
            "output": response,
        })
        return response
