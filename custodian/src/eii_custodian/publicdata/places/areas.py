"""Area provider seam. This module holds no routing engine."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol


class AreaMode(Enum):
    """Closed travel mode. Walk and drive are the only values."""

    WALK = "walk"
    DRIVE = "drive"


class AreaCutoff(Enum):
    """Closed cut-off in minutes. Five and ten are the only values."""

    MINUTES_5 = 5
    MINUTES_10 = 10


class AreaError(Exception):
    """The provider could not return an exact polygon."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


@dataclass(frozen=True)
class ReviewedPoint:
    """The point a reviewed key names. Longitude is first."""

    lon: float
    lat: float


@dataclass(frozen=True)
class AreaResult:
    """One exact polygon, with the versions and hashes that produced it."""

    wkb: bytes
    method_version: str
    graph_hash: str
    inputs_hash: str
    engine_version: str
    stand_in: bool


class AreaProvider(Protocol):
    """Return the exact polygon for one reviewed point, mode and cut-off."""

    def area(
        self,
        point_key: str,
        point: ReviewedPoint,
        mode: AreaMode,
        cutoff: AreaCutoff,
    ) -> AreaResult:
        """Return the polygon, or raise AreaError. No circle or box is a result."""
