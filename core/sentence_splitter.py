from core.schemas import SemanticDetectionRequest
from core.exceptions import EmptyInputError
from urllib.parse import unquote
from typing import TypedDict
import unicodedata
import re

SENTENCE_ENDINGS = {"。", "！", "？", "!", "?", ";", "；", "."}
ZERO_WIDTH_RE = re.compile(r"[\u200b\u200c\u200d\ufeff]")
WHITESPACE_RE = re.compile(r"\s+")

def split_sentence(text:str)->dict[str,str]:
    text = (text or "").strip()
    if not text:
        raise EmptyInputError("split_sentence 接收到空文本")

    results : dict[str,str] = {}
    buffer : list[str] = []

    def flush() -> None:
        sentence = "".join(buffer).strip()
        buffer.clear()

        if sentence:
            sentence_id = f"s{len(results) + 1}"
            results[sentence_id] = sentence

    for char in text:
        buffer.append(char)

        if char in SENTENCE_ENDINGS or char=="\n":
            flush()

    flush()
    return results

def build_semantic_detection_request(text:str):
    sentences = split_sentence(text)
    requests : list[SemanticDetectionRequest] = []

    for sentence_id, original_sentence in sentences.items():
        original = original_sentence
        normalized = unicodedata.normalize("NFKC", original)
        normalized = ZERO_WIDTH_RE.sub("", normalized)
        decoded = unquote(normalized)
        lower = decoded.lower()
        upper = decoded.upper()
        compact = WHITESPACE_RE.sub("", lower)

        requests.append(SemanticDetectionRequest(
            sentence_id=sentence_id,
            original=original_sentence,
            normalized= normalized,
            decoded=decoded,
            lower=lower,
            upper=upper,
            compact=compact,
        ))

    return requests,sentences

