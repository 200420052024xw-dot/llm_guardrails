from pathlib import Path
from typing import Any

import yaml

from core.schemas import Detection
from detectors.types import TextViews

DEFAULT_DICTIONARY_PATH = Path(__file__).resolve().parents[1] / "config" / "dictionary.yaml"


class CustomDictionaryDetector:
    name = "custom_dictionary"

    def __init__(self, dictionary_path: Path = DEFAULT_DICTIONARY_PATH):
        self.dictionary_path = dictionary_path
        self.dictionary = load_dictionary(dictionary_path)

    def detect(self, text: str, text_views: TextViews) -> list[Detection]:
        detections = []
        lower_text = text.lower()

        for detection_type, config in self.dictionary.items():
            weight = float(config.get("weight", 0.5))

            for term in config.get("terms", []):
                term_text = str(term)
                term_lower = term_text.lower()
                start = 0

                while True:
                    index = lower_text.find(term_lower, start)
                    if index == -1:
                        break

                    end = index + len(term_text)
                    detections.append(
                        Detection(
                            type=detection_type,
                            text=text[index:end],
                            start=index,
                            end=end,
                            confidence=0.9,
                            source="custom_dictionary",
                            risk_weight=weight,
                        )
                    )
                    start = end

        return detections


def load_dictionary(dictionary_path: Path) -> dict[str, Any]:
    if not dictionary_path.exists():
        return {}

    with dictionary_path.open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file) or {}

    return data if isinstance(data, dict) else {}
