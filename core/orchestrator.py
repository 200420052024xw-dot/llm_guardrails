import uuid

from core.schemas import ChatRequest, ChatResponse
from detectors.detect import detector
from llm.call_llm import call_llm
from policy.decision import decision


class Orchestrator:
    def __init__(self, default_model: str = "deepseek-v4-flash-260425"):
        self.default_model = default_model

    async def process(self, request: ChatRequest) -> ChatResponse:
        request_id = str(uuid.uuid4())
        detections = detector(request.text)
        result = decision(request.text, detections)

        llm_response = None
        model = request.model or self.default_model

        if result.action == "allow":
            llm_response = call_llm(request.text, model=model)
        elif result.action == "redact":
            llm_input = result.redacted_text or request.text
            llm_response = call_llm(llm_input, model=model)

        return ChatResponse(
            request_id=request_id,
            action=result.action,
            risk_score=result.risk_score,
            message=result.message,
            llm_response=llm_response,
            guard_result={
                "detections": [item.model_dump() for item in detections],
                "decision": result.model_dump(),
            },
        )
