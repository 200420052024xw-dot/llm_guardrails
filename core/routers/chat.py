import asyncio
import json
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from openai import AsyncOpenAI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.api_schemas import SendMessage
from core.auth import get_current_user
from core.database import SessionLocal, get_db
from core.guardrail_service import evaluate_text
from core.models import Conversation, Message, ModelConfigRecord, User, utcnow
from core.pipeline_logger import write_pipeline_stage
from core.routers.conversations import owned_conversation
from core.security import decrypt_secret

router = APIRouter(prefix="/conversations", tags=["chat"])
LABELS = {"pass": "安全通过", "redact": "已脱敏处理", "block": "已阻止发送"}


def sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/{conversation_id}/messages/stream")
async def stream_message(
    conversation_id: str,
    payload: SendMessage,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    conversation = await owned_conversation(conversation_id, user.id, db)
    user_id = user.id
    model_record = await db.get(ModelConfigRecord, user.id)
    if not model_record:
        raise HTTPException(status_code=409, detail="请先在设置中配置模型后再发送消息")
    model_config = {"api_key": decrypt_secret(model_record.api_key_encrypted), "base_url": model_record.base_url, "model": model_record.model}
    request_id = str(uuid4())
    write_pipeline_stage(
        request_id, "input", "success",
        user_id=user_id, conversation_id=conversation_id,
        input_data={"text": payload.content},
    )
    try:
        decision, traces = await evaluate_text(user_id, payload.content, db, model_config, request_id)
    except Exception as exc:
        write_pipeline_stage(
            request_id, "llm_analysis", "error",
            user_id=user_id, conversation_id=conversation_id,
            input_data={"text": payload.content}, error=f"{type(exc).__name__}: {exc}",
        )
        raise
    write_pipeline_stage(
        request_id, "rule_match", "success",
        user_id=user_id, conversation_id=conversation_id,
        input_data={"text": payload.content},
        output_data=[trace.get("rule_match") for trace in traces],
    )
    write_pipeline_stage(
        request_id, "vector_search", "success",
        user_id=user_id, conversation_id=conversation_id,
        input_data=[trace.get("semantic_request", {}).get("output") for trace in traces],
        output_data=[trace.get("similarity_match") for trace in traces],
    )
    write_pipeline_stage(
        request_id, "llm_analysis", "success",
        user_id=user_id, conversation_id=conversation_id,
        input_data=[trace.get("model_recognition", {}).get("input") for trace in traces],
        output_data={
            "model_recognition": [trace.get("model_recognition") for trace in traces],
            "evaluation": [trace.get("comprehensive_evaluation") for trace in traces],
            "final_decision": decision,
        },
    )
    user_message = Message(
        conversation_id=conversation.id,
        role="user",
        content=payload.content,
        safe_content=decision.final_text,
        action=decision.action,
        risk_score=decision.risk_score,
        guardrail_message=decision.message,
        risk_types=sorted({risk for item in decision.sentence_results for risk in item.risk_types}),
    )
    db.add(user_message)
    if conversation.title == "新对话":
        conversation.title = payload.content.strip()[:30]
    conversation.updated_at = utcnow()
    await db.commit(); await db.refresh(user_message)

    async def generate():
        yield sse("decision", {
            "message_id": user_message.id,
            "action": decision.action,
            "label": LABELS[decision.action],
            "risk_score": decision.risk_score,
            "message": decision.message,
            "safe_input": decision.final_text if decision.action == "redact" else None,
            "risk_types": user_message.risk_types,
        })
        if decision.action == "block":
            blocked_assistant = Message(
                conversation_id=conversation_id,
                role="assistant",
                content=decision.message,
                safe_content=decision.final_text,
                action=decision.action,
                risk_score=decision.risk_score,
                guardrail_message=decision.message,
                risk_types=user_message.risk_types,
                status="complete",
            )
            async with SessionLocal() as blocked_db:
                blocked_db.add(blocked_assistant)
                await blocked_db.commit()
                await blocked_db.refresh(blocked_assistant)
            write_pipeline_stage(
                request_id, "call_llm", "skipped",
                user_id=user_id, conversation_id=conversation_id,
                input_data=None,
                output_data={"reason": "blocked_by_guardrails"},
            )
            yield sse("complete", {"message_id": blocked_assistant.id, "blocked": True})
            return
        assistant = Message(
            conversation_id=conversation_id,
            role="assistant",
            content="",
            safe_content=decision.final_text,
            action=decision.action,
            risk_score=decision.risk_score,
            guardrail_message=decision.message,
            risk_types=user_message.risk_types,
            status="streaming",
        )
        async with SessionLocal() as stream_db:
            stream_db.add(assistant); await stream_db.commit(); await stream_db.refresh(assistant)
            chunks: list[str] = []
            try:
                history_rows = list(await stream_db.scalars(select(Message).where(Message.conversation_id == conversation_id).order_by(Message.created_at, Message.id)))
                messages = [{"role": "system", "content": "You are a helpful assistant."}]
                for item in history_rows:
                    if item.role == "user" and item.action != "block":
                        messages.append({"role": "user", "content": item.safe_content or item.content})
                    elif item.role == "assistant" and item.content:
                        messages.append({"role": "assistant", "content": item.content})
                write_pipeline_stage(
                    request_id, "call_llm", "started",
                    user_id=user_id, conversation_id=conversation_id,
                    input_data={"model": model_config["model"], "messages": messages},
                )
                client = AsyncOpenAI(api_key=model_config["api_key"], base_url=model_config["base_url"], timeout=60)
                response = await client.chat.completions.create(model=model_config["model"], messages=messages, stream=True)
                async for part in response:
                    if await request.is_disconnected():
                        assistant.status = "interrupted"; break
                    text = part.choices[0].delta.content or ""
                    if text:
                        chunks.append(text); yield sse("delta", {"text": text})
                assistant.content = "".join(chunks)
                if assistant.status != "interrupted": assistant.status = "complete"
                await stream_db.commit()
                write_pipeline_stage(
                    request_id, "call_llm", assistant.status,
                    user_id=user_id, conversation_id=conversation_id,
                    output_data={"assistant_message_id": assistant.id, "text": assistant.content},
                )
                yield sse("complete", {"message_id": assistant.id, "blocked": False})
            except asyncio.CancelledError:
                assistant.content = "".join(chunks); assistant.status = "interrupted"; await stream_db.commit()
                write_pipeline_stage(
                    request_id, "call_llm", "interrupted",
                    user_id=user_id, conversation_id=conversation_id,
                    output_data={"partial_text": assistant.content},
                )
                raise
            except Exception as exc:
                assistant.content = "".join(chunks); assistant.status = "error"; await stream_db.commit()
                write_pipeline_stage(
                    request_id, "call_llm", "error",
                    user_id=user_id, conversation_id=conversation_id,
                    output_data={"partial_text": assistant.content},
                    error=f"{type(exc).__name__}: {exc}",
                )
                yield sse("error", {"code": "MODEL_REQUEST_FAILED", "message": f"模型调用失败：{type(exc).__name__}", "retryable": True})

    return StreamingResponse(generate(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
