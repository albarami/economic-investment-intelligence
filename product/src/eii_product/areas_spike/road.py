"""Typed input loaded from the invented road fixture; no routing implementation."""

import json
from pathlib import Path
from typing import TypedDict, cast


class Node(TypedDict):
    id: str
    lat: float
    lon: float


class Edge(TypedDict):
    source: str
    target: str
    length_m: float
    drive_kph: float


class RoadFixture(TypedDict):
    pin: str
    walk_kph: float
    cutoff_seconds: float
    radius_m: float
    nodes: list[Node]
    edges: list[Edge]


def load_road(path: Path) -> RoadFixture:
    return cast(RoadFixture, json.loads(path.read_text()))
