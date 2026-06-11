# detectors/normalizer.py
import re
import unicodedata
from urllib.parse import unquote

ZERO_WIDTH_RE = re.compile(r"[​‌‍﻿]")


def normalize_text(text: str) -> dict:
    # 1. 原文保留，不要改
    original = text

    # 2. Unicode 归一化，全角转半角等
    normalized = unicodedata.normalize("NFKC", text)

    # 3. 去掉零宽字符
    normalized = ZERO_WIDTH_RE.sub("", normalized)

    # 4. URL decode，例如 sk%2Dabc -> sk-abc
    decoded = unquote(normalized)

    # 5. 小写版本，方便匹配 password、token 等关键词
    lower = decoded.lower()

    # 6. 紧凑版本，去掉空白，用来发现 s k - a b c 这种拆分
    compact = re.sub(r"\s+", "", lower)

    return {
        "original": original,
        "normalized": normalized,
        "decoded": decoded,
        "lower": lower,
        "compact": compact,
    }
