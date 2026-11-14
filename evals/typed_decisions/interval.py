"""Deterministic counts and Wilson score intervals for offline evidence only."""

import math
from statistics import NormalDist
from typing import TypedDict


class Summary(TypedDict):
    correct: int
    total: int
    rate: float | None
    ci95: list[float] | None


def interval(correct: int, total: int) -> Summary:
    """Return percent units; empty samples have no rate or interval."""
    if type(correct) is not int or type(total) is not int or not 0 <= correct <= total:
        raise ValueError("invalid counts")
    if total == 0:
        return {"correct": correct, "total": total, "rate": None, "ci95": None}
    z = NormalDist().inv_cdf(0.975)
    p = correct / total
    denominator = 1 + z * z / total
    centre = (p + z * z / (2 * total)) / denominator
    radius = (
        z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denominator
    )
    return {
        "correct": correct,
        "total": total,
        "rate": 100 * p,
        "ci95": [round(100 * (centre - radius), 1), round(100 * (centre + radius), 1)],
    }


def inside_stated(rate: float | None, bounds: list[float] | None) -> bool | None:
    """Compare the unrounded percent rate with admitted bounds, never replace them."""
    if rate is None or bounds is None:
        return None
    return bounds[0] <= rate <= bounds[1]


def reserve(planned_calls: int, mean_tokens: float) -> int:
    """Round the admitted mean-based planned use upwards to a whole token."""
    return math.ceil(planned_calls * mean_tokens)
