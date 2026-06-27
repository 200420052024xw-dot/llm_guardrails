from functools import lru_cache
from urllib.parse import quote_plus

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "LLM Guardrails"
    database_url: str | None = None
    db_host: str | None = None
    db_port: int = 3306
    db_user: str | None = None
    db_password: str | None = None
    db_name: str | None = None
    app_encryption_key: str = "change-me-in-production"
    session_cookie_name: str = "guardrails_session"
    session_cookie_secure: bool = False
    session_days: int = 7
    auto_create_tables: bool = True
    frontend_origin: str = "http://localhost:5173"
    allow_private_model_hosts: bool = False
    log_dir: str = "logs"
    log_level: str = "INFO"
    log_max_bytes: int = 10 * 1024 * 1024
    log_backup_count: int = 10

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def resolved_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        if self.db_host and self.db_user and self.db_password is not None and self.db_name:
            user = quote_plus(self.db_user)
            password = quote_plus(self.db_password)
            database = quote_plus(self.db_name)
            return f"mysql+asyncmy://{user}:{password}@{self.db_host}:{self.db_port}/{database}?charset=utf8mb4"
        return "sqlite+aiosqlite:///./llm_guardrails.db"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
