from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl, field_validator


class Credentials(BaseModel):
    username: str = Field(min_length=3, max_length=64, pattern=r"^[a-zA-Z0-9_\-\u4e00-\u9fff]+$")
    password: str = Field(min_length=8, max_length=72)


class PasswordOnly(BaseModel):
    password: str = Field(min_length=1, max_length=72)

class ChangePassword(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=72)


class UserOut(BaseModel):
    id: str
    username: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ConversationCreate(BaseModel):
    title: str = Field(default="新对话", max_length=120)


class ConversationUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=120)


class ConversationOut(BaseModel):
    id: str
    title: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MessageOut(BaseModel):
    id: str
    role: str
    content: str
    safe_content: str | None
    action: str | None
    risk_score: float | None
    guardrail_message: str | None
    risk_types: list
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class SendMessage(BaseModel):
    content: str = Field(min_length=1, max_length=20000)


class ConfidentialEntryIn(BaseModel):
    text: str = Field(min_length=1, max_length=10000)
    category: str = Field(default="confidential", max_length=64)
    confidential_level: str = Field(default="high", max_length=16)
    summary: str | None = Field(default=None, max_length=2000)
    paraphrases: list[str] = Field(default_factory=list)
    negative_samples: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    enabled: bool = True


class ConfidentialEntryOut(ConfidentialEntryIn):
    id: str
    created_at: datetime
    model_config = {"from_attributes": True}


class PublicEntryIn(BaseModel):
    entity_type: Literal["phone", "email", "id_card", "bank_card"]
    value: str = Field(min_length=1, max_length=500)
    label: str = Field(default="", max_length=120)
    enabled: bool = True


class PublicEntryOut(PublicEntryIn):
    id: str
    created_at: datetime
    model_config = {"from_attributes": True}


class ModelConfigIn(BaseModel):
    api_key: str | None = Field(default=None, min_length=1, max_length=1000)
    base_url: str = Field(min_length=8, max_length=500)
    model: str = Field(min_length=1, max_length=120)

    @field_validator("base_url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        parsed = HttpUrl(value)
        if parsed.scheme not in {"http", "https"}:
            raise ValueError("base_url must use http or https")
        return value.rstrip("/")


class ModelConfigOut(BaseModel):
    configured: bool
    api_key_masked: str | None = None
    base_url: str | None = None
    model: str | None = None


class ModelSecretOut(BaseModel):
    api_key: str
