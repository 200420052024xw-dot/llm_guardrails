from datetime import timezone

from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import get_settings
from core.database import get_db
from core.models import User, UserSession, utcnow
from core.security import hash_token


async def get_current_user(
    session_token: str | None = Cookie(default=None, alias=get_settings().session_cookie_name),
    db: AsyncSession = Depends(get_db),
) -> User:
    if not session_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="请先登录")
    record = await db.scalar(
        select(UserSession).where(UserSession.token_hash == hash_token(session_token))
    )
    if not record:
        raise HTTPException(status_code=401, detail="登录状态无效")
    expires = record.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if expires <= utcnow():
        await db.delete(record)
        await db.commit()
        raise HTTPException(status_code=401, detail="登录已过期")
    user = await db.get(User, record.user_id)
    if not user:
        raise HTTPException(status_code=401, detail="用户不存在")
    return user
