from __future__ import annotations

import json
import re
from typing import Any, Protocol


RISK_TYPES = [
    "project_progress",
    "technical_solution",
    "system_architecture",
    "vulnerability_status",
    "customer_intention",
    "pricing_strategy",
    "internal_decision",
    "personnel_arrangement",
    "procurement_plan",
    "deployment_plan",
    "evaluation_result",
    "incident_information",
]


class JsonCompletionClient(Protocol):
    def complete_json(self, prompt: str) -> str:
        ...


class LLMSemanticClassifier:
    def __init__(self, llm_client: JsonCompletionClient):
        self.llm_client = llm_client

    def classify(self, sentence: str) -> dict[str, Any]:
        raw = self.llm_client.complete_json(build_prompt(sentence))
        try:
            data = _loads_json_object(raw)
        except Exception:
            return {
                "is_confidential_sentence": True,
                "risk_score": 0.75,
                "risk_types": ["classifier_parse_error"],
                "reason": "分类器输出解析失败，按保守策略处理",
            }
        return normalize_classifier_result(data)


class OfflineRuleClassifier:
    """Fallback for local development when no compatible model API is configured."""

    high_patterns = [
        (r"基本定|签字|拍板|定了|内部决策", "internal_decision"),
        (r"试点|点位|部署|上线|灰度|投产", "deployment_plan"),
        (r"不理想|兼容性|漏洞|缺陷|故障|事故", "evaluation_result"),
        (r"报价|折扣|底价|采购", "pricing_strategy"),
        (r"客户.*意向|准备中标|竞标", "customer_intention"),
    ]
    low_patterns = [
        r"什么是",
        r"请解释",
        r"一般",
        r"通常",
        r"有哪些测试",
        r"流程",
        r"概念",
    ]

    def classify(self, sentence: str) -> dict[str, Any]:
        compact = "".join(sentence.split())
        if any(re.search(pattern, compact) for pattern in self.low_patterns):
            return {
                "is_confidential_sentence": False,
                "risk_score": 0.15,
                "risk_types": [],
                "reason": "通用知识或流程问题",
            }

        risk_types: list[str] = []
        for pattern, risk_type in self.high_patterns:
            if re.search(pattern, compact):
                risk_types.append(risk_type)
        if risk_types:
            return {
                "is_confidential_sentence": True,
                "risk_score": 0.82,
                "risk_types": sorted(set(risk_types)),
                "reason": "疑似表达内部未公开事实",
            }

        return {
            "is_confidential_sentence": False,
            "risk_score": 0.35,
            "risk_types": [],
            "reason": "未发现明确内部未公开事实模式",
        }


def build_prompt(sentence: str) -> str:
    risk_lines = "\n".join(f"- {item}" for item in RISK_TYPES)
    return f"""你是一个保密信息识别器。请判断下面句子是否表达了单位内部未公开事实。

重点关注以下类型：
{risk_lines}

如果句子中出现类似 [PHONE_1]、[EMAIL_1]、[API_KEY_1]、[PASSWORD_1] 的内容，它们是前置规则检测已经替换过的脱敏占位符，不是真实敏感值。
占位符本身不能作为保密事实、密钥泄露或个人信息泄露的判断依据。请只根据占位符以外的上下文判断是否存在内部未公开事实。

只输出 JSON，不要输出解释性文本。JSON 格式如下：
{{
  "is_confidential_sentence": true,
  "risk_score": 0.0,
  "risk_types": ["类型代码"],
  "reason": "一句简短原因"
}}

待判断句子：
{sentence}
"""


def normalize_classifier_result(data: dict[str, Any]) -> dict[str, Any]:
    score = float(data.get("risk_score", 0.0))
    score = min(1.0, max(0.0, score))
    risk_types = data.get("risk_types", [])
    if not isinstance(risk_types, list):
        risk_types = []
    risk_types = [str(item) for item in risk_types if item]
    return {
        "is_confidential_sentence": bool(data.get("is_confidential_sentence", score >= 0.6)),
        "risk_score": score,
        "risk_types": risk_types,
        "reason": str(data.get("reason", ""))[:200],
    }


def _loads_json_object(raw: str) -> dict[str, Any]:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text).strip()
        text = re.sub(r"```$", "", text).strip()
    if not text.startswith("{"):
        match = re.search(r"\{.*\}", text, flags=re.S)
        if not match:
            raise ValueError("no JSON object found")
        text = match.group(0)
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("classifier output is not an object")
    return data
