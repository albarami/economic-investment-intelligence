"""Synthetic hour factors selecting scaled-drive tile sets (SYN-53)."""

import json
import math
from pathlib import Path
from typing import cast


def load_factors(path: Path) -> tuple[float, ...]:
    data = cast(dict[str, list[float]], json.loads(path.read_text()))
    factors = tuple(data["factors"])
    if len(factors) != 24:
        raise ValueError("One factor per hour is required")
    if any(not math.isfinite(value) or value <= 0 for value in factors):
        raise ValueError("Speed factors must be finite and positive")
    return factors
