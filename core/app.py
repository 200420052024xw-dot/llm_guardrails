from fastapi import FastAPI, HTTPException

from core.orchestrator import Orchestrator
from core.schemas import ChatRequest, ChatResponse

app = FastAPI(
    title="LLM Guardrails Gateway",
    version="0.1.0",
    description="Input-side safety gateway for LLM requests.",
)

orchestrator = Orchestrator()


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    try:
        return await orchestrator.process(request)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Gateway internal error: {type(exc).__name__}",
        ) from exc
