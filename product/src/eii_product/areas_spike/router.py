"""In-process primary routing, preserving the engine polygon exactly."""

import math

from .road import RoadFixture
from .shapes import Area, Ring
from .snap import snap_polygon


def isochrone(
    road: RoadFixture, mode: str, seconds: float, hour: int, factors: tuple[float, ...]
) -> Ring:
    if mode not in ("walk", "drive"):
        raise ValueError("Unknown routing mode")
    if not 0 <= hour < len(factors):
        raise ValueError("Unknown hour")
    if not math.isfinite(seconds) or seconds <= 0:
        raise ValueError("Cutoff must be finite and positive")
    from .engine import scaled_isochrone

    return scaled_isochrone(road, mode, seconds, hour, factors)


def routed_area(
    road: RoadFixture,
    mode: str,
    seconds: float,
    hour: int,
    factors: tuple[float, ...],
    frame: tuple[str, ...],
) -> Area:
    exact = isochrone(road, mode, seconds, hour, factors)
    return Area(exact, snap_polygon(exact, frame))
