from typing import Any,Literal,Optional
from pydantic import BaseModel,Field

RiskLevel = Literal["low", "medium", "high"]

# 模型请求
class ChatRequest(BaseModel):
    user_id:str = "None"
    text:str = Field(...,min_length=1)
    model:Optional[str]= None

class Detection(BaseModel):
    type:str
    text:str
    start: int =Field(...,ge=0)
    end: int =Field(...,ge=0)
    risk_weight: float = Field(default=0.0,ge=0.0,le=1.0)#风险值
    confidence: float = Field(...,ge=0.0) #检测置信度
    source:str   #此部分待定填充内容

class Decision(BaseModel):
    action:Literal["allow","redact","block"]
    risk_score: float = Field(...,ge=0.0)
    risk_level: Optional[RiskLevel] = None
    redacted_text: Optional[str]= None # 脱敏后的文本
    message: str

    def _score_to_level(self,risk_score: float) -> Optional[RiskLevel]:
        if self.risk_level is None:
            if self.risk_score < 0.3:
                self.risk_level = "low"
            elif self.risk_score < 0.7:
                self.risk_level = "medium"
            else:
                self.risk_level = "high"

    def model_post_init(self, context: Any, /) -> None:
        self._score_to_level(self.risk_score)

class ChatResponse(BaseModel):
    request_id: str
    action: Literal["allow","redact","block"]
    risk_score: float
    message: str
    llm_response: Optional[str]= None
    guard_result: dict[str, Any]


