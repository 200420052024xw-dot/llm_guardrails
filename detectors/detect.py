"""
检测文本里有没有敏感内容，并返回Detection列表

input:
text:".........."

output:
[
    Detection(
        type="phone",
        text="13812345678",
        start=5,
        end=16,
        risk_weight=0.6,
        confidence=1.0,
        source="regex"
    ),

    Detection(
        type="idcard",
        text="110101199901011234",
        start=22,
        end=40,
        risk_weight=0.9,
        confidence=1.0,
        source="regex"
    )
]
"""
from core.schemas import Detection
from random import randint

def detector(text: str) -> list[Detection]:
    num = randint(0, 2)

    if num == 0:
        return []

    elif num == 1:
        return [
            Detection(
                type="phone",
                text="13812345678",
                start=5,
                end=16,
                risk_weight=0.6,
                confidence=1.0,
                source="regex"
            )
        ]

    else:
        return [
            Detection(
                type="phone",
                text="13812345678",
                start=5,
                end=16,
                risk_weight=0.6,
                confidence=1.0,
                source="regex"
            ),
            Detection(
                type="idcard",
                text="110101199901011234",
                start=22,
                end=40,
                risk_weight=0.9,
                confidence=1.0,
                source="regex"
            )
        ]