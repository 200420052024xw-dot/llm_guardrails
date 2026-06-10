"""
负责根据检测结果判断这段话能不能发给LLM

input:
text: str
detections: list[Detection]

output:
Decision(
    action="block",
    risk_score=0.9,
    risk_level="high",
    message="检测到高风险敏感信息"
)

Decision(
    action="redact",
    risk_score=0.6,
    risk_level="medium",
    redacted_text="我的电话138****5678",
    message="已自动脱敏"
)
"""

from core.schemas import Decision,Detection
from random import randint

def decision(user_input:str,detections: list[Detection]) -> Decision:
    num = randint(0, 2)

    if num == 0:
        return Decision(
            action="allow",
            risk_score=0.0,
            risk_level="low",
            message="未发现敏感信息"
        )

    elif num == 1:
        return Decision(
            action="redact",
            risk_score=0.6,
            risk_level="medium",
            redacted_text="我的电话138****5678",
            message="已自动脱敏"
        )

    else:
        return Decision(
            action="block",
            risk_score=0.9,
            risk_level="high",
            message="检测到高风险敏感信息"
        )