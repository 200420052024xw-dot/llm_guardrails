from __future__ import annotations

import sys
from functools import lru_cache
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from typing import Any


@lru_cache(maxsize=1)
def load_contract_models(schema_path: str | Path | None = None) -> tuple[type[Any], type[Any]]:
    if schema_path is None:
        try:
            from core.schemas import SemanticDetectionRequest, SemanticDetectionResult

            return SemanticDetectionRequest, SemanticDetectionResult
        except ModuleNotFoundError:
            pass

    root = Path(__file__).resolve().parent.parent
    path = Path(schema_path) if schema_path else root / "schemas(3).py"
    if not path.exists():
        raise FileNotFoundError(f"schema file not found: {path}")

    spec = spec_from_file_location("_semantic_contract_schemas", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load schema file: {path}")

    module = module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

    return module.SemanticDetectionRequest, module.SemanticDetectionResult


def build_result(**kwargs: Any) -> Any:
    _, result_model = load_contract_models()
    return result_model(**kwargs)
