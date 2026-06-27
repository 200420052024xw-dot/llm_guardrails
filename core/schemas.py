from typing import Literal, Optional

from pydantic import BaseModel, Field


EvidenceType = Literal[
    "similarity_match",
    "rule_match",
    "model_detection",
    "request_error",
]

RuleRiskType = Literal[
    "phone",
    "email",
    "id_card",
    "bank_card",
    "api_key",
    "bearer_token",
    "jwt",
    "password",
    "private_key",
    "connection_string",
]


class ChatRequest(BaseModel):
    user_id: str = "None"
    original_text: str = Field(..., min_length=1)
    model: Optional[str] = None


class SemanticDetectionRequest(BaseModel):
    sentence_id: str
    text: str
    rule_result: Literal["pass", "sensitive"] = "pass"


class RuleDetectionResult(BaseModel):
    sentence_id: str
    level: Literal["pass", "sensitive"] = "pass"
    risk_types: list[RuleRiskType] = Field(default_factory=list)
    redacted_text: Optional[str] = None
    message: Optional[str] = None


class SemanticDetectionResult(BaseModel):
    sentence_id: str
    confidential_level: Literal["pass", "sensitive", "confidential", "error"]
    risk_score: float = Field(..., ge=0.0, le=1.0)
    risk_types: list[str] = Field(default_factory=list)
    evidence_types: list[EvidenceType] = Field(default_factory=list)
    redacted_text: Optional[str] = None
    message: Optional[str] = None


class PublicSemanticRequest(BaseModel):
    sentence_id: str
    confidential_level: Literal["pass", "sensitive", "confidential"]
    risk_score: float = Field(..., ge=0.0, le=1.0)
    risk_types: list[str] = Field(default_factory=list)
    evidence_types: list[EvidenceType] = Field(default_factory=list)
    message: Optional[str] = None


class SemanticFinalResult(BaseModel):
    request_id: str
    action: Literal["pass", "redact", "block"]
    risk_score: float = Field(..., ge=0.0, le=1.0)
    message: str
    final_text: Optional[str] = None
    sentence_results: list[SemanticDetectionResult] = Field(default_factory=list)


class ChatResponse(BaseModel):
    request_id: str
    action: Literal["pass", "redact", "block"]
    risk_score: float = Field(..., ge=0.0, le=1.0)
    message: str
    final_text: Optional[str] = None
    llm_response: Optional[str] = None
