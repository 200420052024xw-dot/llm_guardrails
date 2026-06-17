from datetime import datetime
from pathlib import Path
from typing import Any
import json


RECORD_ROOT = Path(__file__).resolve().parent / "record"


def get_record_dir(request_id: str) -> Path:
    record_dir = RECORD_ROOT / request_id
    record_dir.mkdir(parents=True, exist_ok=True)
    return record_dir


def write_stage_record(request_id: str, stage_name: str, payload: Any) -> Path:
    record_dir = get_record_dir(request_id)
    path = record_dir / f"{stage_name}.json"

    record = {
        "request_id": request_id,
        "stage_name": stage_name,
        "time": datetime.now().isoformat(timespec="seconds"),
        "payload": payload,
    }

    path.write_text(
        json.dumps(record, ensure_ascii=False, indent=2, default=_json_default),
        encoding="utf-8",
    )

    return path


def _json_default(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if hasattr(value, "dict"):
        return value.dict()
    if isinstance(value, Path):
        return str(value)
    return str(value)
