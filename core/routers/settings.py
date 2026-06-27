import asyncio
import ipaddress
import logging
import socket
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException
from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AsyncOpenAI,
    AuthenticationError,
    BadRequestError,
    NotFoundError,
    PermissionDeniedError,
    RateLimitError,
)
from sqlalchemy.ext.asyncio import AsyncSession

from core.api_schemas import ModelConfigIn, ModelConfigOut, ModelSecretOut
from core.auth import get_current_user
from core.config import get_settings
from core.database import get_db
from core.models import ModelConfigRecord, User
from core.security import decrypt_secret, encrypt_secret

router = APIRouter(prefix="/settings/model", tags=["settings"])
logger = logging.getLogger(__name__)


def _validate_model_endpoint(value: str) -> None:
    if get_settings().allow_private_model_hosts:
        return
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.hostname:
        raise HTTPException(status_code=400, detail="模型地址必须使用公开 HTTPS 服务。")
    try:
        addresses = {item[4][0] for item in socket.getaddrinfo(parsed.hostname, parsed.port or 443)}
    except socket.gaierror as exc:
        raise HTTPException(status_code=400, detail="模型地址无法解析，请检查域名。") from exc
    if not addresses or any(not ipaddress.ip_address(address).is_global for address in addresses):
        raise HTTPException(status_code=400, detail="模型地址不能指向本机或私有网络。")


def mask_key(value: str) -> str:
    if len(value) <= 8:
        return "•" * len(value)
    return f"{value[:3]}{'•' * 8}{value[-4:]}"


@router.get("", response_model=ModelConfigOut)
async def get_model_config(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    record = await db.get(ModelConfigRecord, user.id)
    if not record:
        return ModelConfigOut(configured=False)
    return ModelConfigOut(
        configured=True,
        api_key_masked=mask_key(decrypt_secret(record.api_key_encrypted)),
        base_url=record.base_url,
        model=record.model,
    )


@router.get("/secret", response_model=ModelSecretOut)
async def get_model_secret(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    record = await db.get(ModelConfigRecord, user.id)
    if not record:
        raise HTTPException(status_code=404, detail="尚未配置 API Key。")
    return ModelSecretOut(api_key=decrypt_secret(record.api_key_encrypted))


@router.put("", response_model=ModelConfigOut)
async def save_model_config(data: ModelConfigIn, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await asyncio.to_thread(_validate_model_endpoint, data.base_url)
    record = await db.get(ModelConfigRecord, user.id)
    if not record:
        if not data.api_key:
            raise HTTPException(status_code=400, detail="首次配置时必须填写 API Key。")
        record = ModelConfigRecord(user_id=user.id, api_key_encrypted="", base_url=data.base_url, model=data.model)
        db.add(record)
    if data.api_key:
        record.api_key_encrypted = encrypt_secret(data.api_key)
    record.base_url = data.base_url
    record.model = data.model
    await db.commit()
    key = data.api_key or decrypt_secret(record.api_key_encrypted)
    logger.info("model configuration saved user_id=%s model=%s", user.id, data.model)
    return ModelConfigOut(configured=True, api_key_masked=mask_key(key), base_url=data.base_url, model=data.model)


@router.delete("", status_code=204)
async def delete_model_config(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    record = await db.get(ModelConfigRecord, user.id)
    if record:
        await db.delete(record)
        await db.commit()
        logger.info("model configuration deleted user_id=%s", user.id)


@router.post("/test")
async def test_model_config(
    data: ModelConfigIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await asyncio.to_thread(_validate_model_endpoint, data.base_url)
    api_key = data.api_key
    if not api_key:
        record = await db.get(ModelConfigRecord, user.id)
        if not record:
            raise HTTPException(status_code=400, detail="请先填写 API Key。")
        api_key = decrypt_secret(record.api_key_encrypted)
    try:
        client = AsyncOpenAI(api_key=api_key, base_url=data.base_url, timeout=15)
        response = await client.chat.completions.create(
            model=data.model,
            messages=[{"role": "user", "content": "Reply with OK only."}],
            max_tokens=4,
        )
        content = response.choices[0].message.content or ""
        return {"ok": True, "message": f"连接成功，模型返回：{content[:120]}"}
    except Exception as exc:
        logger.exception("model connection test failed user_id=%s model=%s", user.id, data.model)
        raise HTTPException(status_code=400, detail=_model_error_detail(exc)) from exc


def _model_error_detail(exc: Exception) -> str:
    if isinstance(exc, AuthenticationError):
        return "认证失败（HTTP 401）：API Key 无效或已过期。"
    if isinstance(exc, PermissionDeniedError):
        return "权限不足（HTTP 403）：API Key 没有访问该模型的权限。"
    if isinstance(exc, NotFoundError):
        return "资源不存在（HTTP 404）：请检查 Base URL 和模型名称。"
    if isinstance(exc, RateLimitError):
        return "请求受限（HTTP 429）：额度不足或调用频率过高，请稍后重试。"
    if isinstance(exc, APITimeoutError):
        return "连接超时：模型服务在 15 秒内没有响应。"
    if isinstance(exc, APIConnectionError):
        return f"无法连接模型服务：{str(exc)[:300]}"
    if isinstance(exc, BadRequestError):
        return f"请求参数错误（HTTP 400）：{str(exc)[:500]}"
    if isinstance(exc, APIStatusError):
        return f"模型服务返回 HTTP {exc.status_code}：{str(exc)[:500]}"
    return f"连接失败（{type(exc).__name__}）：{str(exc)[:500]}"
