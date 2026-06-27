from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from dotenv import load_dotenv

from .config import load_model_config

load_dotenv()

DEFAULT_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"
DEFAULT_MODEL = "deepseek-v4-flash-260425"


class OpenAICompatibleClient:
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        chat_model: str | None = None,
        embedding_model: str | None = None,
        embedding_batch_size: int | None = None,
        timeout: float | None = None,
        use_env: bool = True,
    ):
        config = load_model_config()
        self.api_key = api_key if not use_env else (api_key or os.getenv("API_KEY"))
        self.base_url = (base_url or (os.getenv("BASE_URL", DEFAULT_BASE_URL) if use_env else DEFAULT_BASE_URL)).rstrip("/")
        self.chat_model = chat_model or (os.getenv("MODEL", DEFAULT_MODEL) if use_env else DEFAULT_MODEL)
        self.embedding_api_key = (os.getenv("EMBEDDING_API_KEY") if use_env else None) or self.api_key
        self.embedding_base_url = _normalize_base_url((os.getenv("EMBEDDING_BASE_URL") if use_env else None) or self.base_url)
        self.chat_temperature = config.chat_temperature
        self.chat_top_p = config.chat_top_p
        self.chat_max_tokens = config.chat_max_tokens
        self.chat_response_format = config.chat_response_format
        self.embedding_model = embedding_model or (os.getenv("EMBEDDING_MODEL") if use_env else None)
        self.embedding_batch_size = max(1, embedding_batch_size or config.embedding_batch_size)
        self.embedding_max_workers = max(1, int(os.getenv("EMBEDDING_MAX_WORKERS", "4")))
        self.timeout = timeout if timeout is not None else config.timeout

    @property
    def configured(self) -> bool:
        return bool(_is_real_value(self.api_key) and _is_real_value(self.base_url))

    @property
    def embedding_configured(self) -> bool:
        return bool(
            _is_real_value(self.embedding_api_key)
            and _is_real_value(self.embedding_base_url)
            and _is_real_value(self.embedding_model)
        )

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not self.embedding_configured:
            raise RuntimeError("Embedding model is not configured: set EMBEDDING_MODEL in .env")

        batches = [
            (start // self.embedding_batch_size, texts[start : start + self.embedding_batch_size])
            for start in range(0, len(texts), self.embedding_batch_size)
        ]
        total_batches = len(batches)
        batch_results: list[list[list[float]] | None] = [None] * total_batches
        max_workers = min(self.embedding_max_workers, total_batches) if total_batches else 1

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_map = {
                executor.submit(self._embed_batch, batch): (batch_index, batch)
                for batch_index, batch in batches
            }
            completed = 0
            for future in as_completed(future_map):
                batch_index, batch = future_map[future]
                batch_results[batch_index] = future.result()
                completed += 1
                print(
                    f"embedding batch {batch_index + 1}/{total_batches} done "
                    f"({completed}/{total_batches} completed): {len(batch)} texts",
                    file=sys.stderr,
                    flush=True,
                )

        embeddings: list[list[float]] = []
        for batch_result in batch_results:
            if batch_result is None:
                raise RuntimeError("embedding batch missing from completed results")
            embeddings.extend(batch_result)
        return embeddings

    def _embed_batch(self, batch: list[str]) -> list[list[float]]:
        payload = {"model": self.embedding_model, "input": batch}
        data = self._post(
            "/embeddings",
            payload,
            api_key=self.embedding_api_key,
            base_url=self.embedding_base_url,
        )
        embeddings = [item["embedding"] for item in data["data"]]
        if len(embeddings) != len(batch):
            raise RuntimeError(f"embedding response count mismatch: expected {len(batch)}, got {len(embeddings)}")
        return embeddings

    def complete_json(self, prompt: str) -> str:
        payload: dict[str, Any] = {
            "model": self.chat_model,
            "messages": [
                {"role": "system", "content": "You are a strict JSON classifier. Return only valid JSON."},
                {"role": "user", "content": prompt},
            ],
            "temperature": self.chat_temperature,
            "top_p": self.chat_top_p,
            "max_tokens": self.chat_max_tokens,
        }
        if self.chat_response_format:
            payload["response_format"] = {"type": self.chat_response_format}
        data = self._post("/chat/completions", payload)
        return data["choices"][0]["message"]["content"]

    def _post(
        self,
        path: str,
        payload: dict[str, Any],
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> dict[str, Any]:
        request_api_key = api_key or self.api_key
        request_base_url = (base_url or self.base_url).rstrip("/")

        if not (_is_real_value(request_api_key) and _is_real_value(request_base_url)):
            raise RuntimeError("OpenAI-compatible API is not configured: set API_KEY and BASE_URL in .env")

        url = f"{request_base_url}{path}"
        body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {request_api_key}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"OpenAI-compatible API HTTP {exc.code}: {detail}") from exc


def _is_real_value(value: str | None) -> bool:
    if not value:
        return False
    lowered = value.lower()
    placeholders = ("sk-xxx", "your-", "example.com", "api.example.com")
    if any(item in lowered for item in placeholders):
        return False
    return True


def _normalize_base_url(value: str) -> str:
    url = value.rstrip("/")
    for endpoint in ("/embeddings", "/chat/completions", "/responses"):
        if url.endswith(endpoint):
            return url[: -len(endpoint)]
    return url
