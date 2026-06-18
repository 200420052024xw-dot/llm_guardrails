# detectors/dict_detector.py
import yaml
from pathlib import Path
from detectors.schemas import make_detection

DICT_PATH = Path("config/dictionary.yaml")


def load_dictionary() -> dict:
    with DICT_PATH.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def detect_dictionary(text: str, views: dict) -> list[dict]:
    data = load_dictionary()
    detections = []
    lower_text = text.lower()

    for type_name, cfg in data.items():
        weight = float(cfg.get("weight", 0.5))
        for term in cfg.get("terms", []):
            term_lower = term.lower()
            start = 0
            while True:
                idx = lower_text.find(term_lower, start)
                if idx == -1:
                    break
                end = idx + len(term)
                detections.append(make_detection(type_name, text[idx:end], idx, end, 0.90, "regex", weight))
                start = end
    return detections
