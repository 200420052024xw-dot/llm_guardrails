import json
import logging
from datetime import datetime, timezone
from typing import Any


logger = logging.getLogger("guardrails.pipeline")


def write_pipeline_stage(
    request_id: str,
    stage: str,
    status: str,
    *,
    user_id: str,
    conversation_id: str,
    input_data: Any = None,
    output_data: Any = None,
    error: str | None = None,
) -> None:
    record = {
        "time": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        "request_id": request_id,
        "user_id": user_id,
        "conversation_id": conversation_id,
        "stage": stage,
        "status": status,
        "input": input_data,
        "output": output_data,
    }
    if error:
        record["error"] = error
    logger.info(json.dumps(record, ensure_ascii=False, default=_json_default))


def _json_default(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if isinstance(value, set):
        return sorted(value)
    return str(value)
