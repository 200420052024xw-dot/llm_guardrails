from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import get_settings
from core.database import Base, engine
from core.logging_config import configure_logging
from core.middleware import SecurityAndRateLimitMiddleware
from core.routers import auth, chat, conversations, libraries, settings

configure_logging()


@asynccontextmanager
async def lifespan(_: FastAPI):
    if get_settings().session_cookie_secure and get_settings().app_encryption_key == "change-me-in-production":
        raise RuntimeError("APP_ENCRYPTION_KEY must be changed in production")
    if get_settings().auto_create_tables:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


app = FastAPI(
    title="LLM Guardrails Gateway",
    version="1.0.0",
    description="Multi-user LLM safety gateway.",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[get_settings().frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(SecurityAndRateLimitMiddleware)
app.include_router(auth.router, prefix="/api")
app.include_router(conversations.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(libraries.router, prefix="/api")
app.include_router(settings.router, prefix="/api")


@app.get("/api/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
