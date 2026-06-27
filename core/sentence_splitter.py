from urllib.parse import unquote
import re
import unicodedata

from core.exceptions import EmptyInputError


SENTENCE_ENDINGS = {"\u3002", "\uff01", "\uff1f", "!", "?", ";", "\uff1b"}
ZERO_WIDTH_RE = re.compile(r"[\u200b\u200c\u200d\ufeff]")
WHITESPACE_RE = re.compile(r"\s+")


def split_sentence(text: str) -> dict[str, str]:
    text = (text or "").strip()
    if not text:
        raise EmptyInputError("split_sentence received empty text")

    results: dict[str, str] = {}
    buffer: list[str] = []

    def flush() -> None:
        sentence = "".join(buffer).strip()
        buffer.clear()

        if sentence:
            sentence_id = f"s{len(results) + 1}"
            results[sentence_id] = sentence

    for char in text:
        buffer.append(char)

        if char in SENTENCE_ENDINGS or char == "\n":
            flush()

    flush()
    return results


def build_semantic_detection_request(text: str) -> tuple[list[dict[str, str]], dict[str, str]]:
    sentences = split_sentence(text)
    requests: list[dict[str, str]] = []

    for sentence_id, original_sentence in sentences.items():
        normalized = unicodedata.normalize("NFKC", original_sentence)
        normalized = ZERO_WIDTH_RE.sub("", normalized)
        decoded = unquote(normalized)
        lower = decoded.lower()
        compact = WHITESPACE_RE.sub("", lower)

        requests.append({
            "sentence_id": sentence_id,
            "original": original_sentence,
            "normalized": normalized,
            "decoded": decoded,
            "lower": lower,
            "compact": compact,
        })

    return requests, sentences
