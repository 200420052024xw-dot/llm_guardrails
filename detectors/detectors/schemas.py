# detectors/schemas.py

def make_detection(
    type_: str,
    text: str,
    start: int,
    end: int,
    confidence: float,
    source: str,
    risk_weight: float,
) -> dict:
    return {
        "type": type_,
        "text": text,
        "start": start,
        "end": end,
        "confidence": confidence,
        "source": source,
        "risk_weight": risk_weight,
    }
