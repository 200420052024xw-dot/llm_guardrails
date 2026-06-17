from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


DETECTION_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class ModelConfig:
    chat_temperature: float = 0.0
    chat_top_p: float = 1.0
    chat_max_tokens: int = 512
    chat_response_format: str = "json_object"
    embedding_batch_size: int = 64
    vector_index_path: str = str(DETECTION_ROOT / "data" / "simulated" / "confidential_facts.vector_index.json")
    timeout: float = 30.0


@dataclass(frozen=True)
class SemanticThresholds:
    matcher_threshold: float = 0.78
    similarity_high: float = 0.82
    llm_high: float = 0.80
    joint_similarity: float = 0.70
    joint_llm: float = 0.65
    medium_similarity: float = 0.65
    medium_llm: float = 0.60
    top_k: int = 3


def load_model_config(path: str | Path = DETECTION_ROOT / "config" / "model_config.yaml") -> ModelConfig:
    values = _load_flat_yaml(path)
    defaults = ModelConfig()
    vector_index_path = str(values.get("vector_index_path", defaults.vector_index_path))
    if not Path(vector_index_path).is_absolute():
        vector_index_path = str(DETECTION_ROOT / vector_index_path)

    return ModelConfig(
        chat_temperature=float(values.get("chat_temperature", defaults.chat_temperature)),
        chat_top_p=float(values.get("chat_top_p", defaults.chat_top_p)),
        chat_max_tokens=max(1, int(values.get("chat_max_tokens", defaults.chat_max_tokens))),
        chat_response_format=str(values.get("chat_response_format", defaults.chat_response_format)),
        embedding_batch_size=max(1, int(values.get("embedding_batch_size", defaults.embedding_batch_size))),
        vector_index_path=vector_index_path,
        timeout=float(values.get("timeout", defaults.timeout)),
    )


def load_thresholds(path: str | Path = DETECTION_ROOT / "config" / "semantic_thresholds.yaml") -> SemanticThresholds:
    values = _load_flat_yaml(path)
    if not values:
        return SemanticThresholds()

    parsed_values: dict[str, float | int] = {}
    for key, value in values.items():
        try:
            parsed_values[key] = int(value) if key == "top_k" else float(value)
        except ValueError:
            continue
    return SemanticThresholds(**{**SemanticThresholds().__dict__, **parsed_values})


def _load_flat_yaml(path: str | Path) -> dict[str, str]:
    p = Path(path)
    if not p.exists():
        return {}

    values: dict[str, str] = {}
    for raw_line in p.read_text(encoding="utf-8").splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if not key:
            continue
        values[key] = value
    return values
