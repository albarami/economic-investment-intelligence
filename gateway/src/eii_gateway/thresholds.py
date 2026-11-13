"""Ranking signals only: decision 0014 item 6; no item is removed from review."""

from .types import Outcome

THRESHOLD = {"high": 0.90, "low": 0.10}


def outcome(kind: str, label: str, scores: dict[str, float]) -> Outcome:
    if kind == "yes_no":
        yes = scores["yes"]
        accepted = (label == "yes" and yes >= THRESHOLD["high"]) or (
            label == "no" and yes <= THRESHOLD["low"]
        )
    else:
        accepted = scores[label] >= THRESHOLD["high"]
    return "DECIDED" if accepted else "BELOW_THRESHOLD"
