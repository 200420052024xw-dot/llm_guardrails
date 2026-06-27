from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.api_schemas import ChangePassword, Credentials, PasswordOnly, UserOut
from core.auth import get_current_user
from core.config import get_settings
from core.database import get_db
from core.models import User, UserSession
from core.security import (
    hash_password,
    hash_token,
    new_session_token,
    session_expiry,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def set_session_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        settings.session_cookie_name,
        token,
        max_age=settings.session_days * 86400,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        path="/",
    )


async def create_login(user: User, db: AsyncSession, response: Response) -> None:
    token = new_session_token()
    db.add(UserSession(user_id=user.id, token_hash=hash_token(token), expires_at=session_expiry()))
    await db.commit()
    set_session_cookie(response, token)


@router.post("/register", response_model=UserOut, status_code=201)
async def register(data: Credentials, response: Response, db: AsyncSession = Depends(get_db)):
    username = data.username.strip()
    if await db.scalar(select(User).where(User.username == username)):
        raise HTTPException(status_code=409, detail="用户名已存在")
    user = User(username=username, password_hash=hash_password(data.password))
    db.add(user)
    await db.flush()
    await create_login(user, db, response)
    return user


@router.post("/login", response_model=UserOut)
async def login(data: Credentials, response: Response, db: AsyncSession = Depends(get_db)):
    user = await db.scalar(select(User).where(User.username == data.username.strip()))
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    await create_login(user, db, response)
    return user


@router.post("/logout", status_code=204)
async def logout(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    settings = get_settings()
    token = request.cookies.get(settings.session_cookie_name)
    if token:
        await db.execute(delete(UserSession).where(UserSession.token_hash == hash_token(token)))
        await db.commit()
    response.delete_cookie(settings.session_cookie_name, path="/")


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)):
    return user


@router.post("/verify-password", status_code=204)
async def verify_password_endpoint(
    data: PasswordOnly,
    user: User = Depends(get_current_user),
):
    if not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="密码错误")


@router.post("/change-password", status_code=204)
async def change_password(
    data: ChangePassword,
    response: Response,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not verify_password(data.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="当前密码错误")
    user.password_hash = hash_password(data.new_password)
    await db.execute(delete(UserSession).where(UserSession.user_id == user.id))
    await db.flush()
    await create_login(user, db, response)
