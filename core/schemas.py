from typing import Any,Literal,Optional
from pydantic import BaseModel,Field

EvidenceType = Literal[
    "similarity_match", #相似度匹配
    "rule_match",   #规则匹配
    "model_detection", #模型识别
    "request_error"
]

# 模型请求
class ChatRequest(BaseModel):
    user_id:str = "None"
    original_text:str = Field(...,min_length=1)
    model:Optional[str]= None

# 3号输入
class SemanticDetectionRequest(BaseModel):
    sentence_id: str
    original: str #原文
    normalized: Optional[str]= None #全角字符转成半角
    decoded: Optional[str]= None #检测到URL后使用
    lower: str #小写版本
    upper: str #全大写版本
    compact: str #紧凑版本，通常是去掉空白字符后的文本

# 3号返回的结果
class SemanticDetectionResult(BaseModel):
    sentence_id: str
    confidential_level: Literal["pass", "sensitive", "confidential","error"] #放行、敏感可替换、保密
    risk_score: float = Field(..., ge=0.0, le=1.0)
    risk_types: list[str] = Field(default_factory=list) #安全类型：暂定
    evidence_types: list[EvidenceType] = Field(default_factory=list)
    redacted_text : Optional[str] = None #若为敏感可替换，则输出替换后的内容
    message: Optional[str] = None

# 公开的3号结果
class PublicSemanticRequest(BaseModel):
    sentence_id: str
    confidential_level: Literal["pass", "sensitive", "confidential"] #放行、敏感可替换、保密
    risk_score: float = Field(..., ge=0.0, le=1.0)
    risk_types: list[str] = Field(default_factory=list)  # 安全类型：暂定
    evidence_types: list[EvidenceType] = Field(default_factory=list)
    message: Optional[str] = None

class SemanticFinalResult(BaseModel):
    request_id : str
    action: Literal["pass","redact","block"] #最终判断是否可以调用LLM
    risk_score:float = Field(..., ge=0.0, le=1.0)
    message: str
    final_text:Optional[str] = None # allow/redact 时才有，block 时必须是 None
    sentence_results:list[SemanticDetectionResult] = Field(default_factory=list)

class ChatResponse(BaseModel):
    request_id: str
    action: Literal["pass","redact","block"]
    risk_score:float = Field(..., ge=0.0, le=1.0)
    message: str
    final_text:Optional[str] = None
    llm_response: Optional[str]= None
#todo 增加对外展示 semantic_results: list[PublicSemanticRequest] = Field(default_factory=list)


