"""Only the three named fixture files enter the assignment."""

from dataclasses import dataclass
from fractions import Fraction
from typing import Any

from .params import CLASSES, closed, decimal


@dataclass(frozen=True)
class Node:
    id: str
    lat: Fraction
    lon: Fraction


@dataclass(frozen=True)
class Link:
    id: str
    source: str
    target: str
    length_m: Fraction
    road_class: str


@dataclass(frozen=True)
class Roads:
    nodes: tuple[Node, ...]
    links: tuple[Link, ...]
    units: dict[str, tuple[Fraction, Fraction]]


@dataclass(frozen=True)
class Flow:
    origin: str
    destination: str
    day_type: str
    hour: int
    summer: bool
    estimate: Fraction


class FlowUnitError(ValueError):
    """MTH-88 NO_DATA, distinct from malformed input."""


class NoPathError(ValueError):
    """Released flow has no directed path between its loading nodes."""


def unique(value: str, seen: set[str], field: str) -> None:
    if value in seen:
        raise ValueError(f"{field}: duplicate identifier")
    seen.add(value)


def parse_roads(value: Any) -> Roads:
    data = closed(value, {"note", "nodes", "links", "units"}, "roads")
    nodes = []
    node_ids: set[str] = set()
    for raw in data["nodes"]:
        row = closed(raw, {"id", "lat", "lon"}, "node")
        unique(row["id"], node_ids, "node")
        nodes.append(
            Node(row["id"], decimal(row["lat"], "lat"), decimal(row["lon"], "lon"))
        )
    links = []
    link_ids: set[str] = set()
    for raw in data["links"]:
        row = closed(
            raw, {"link_id", "source", "target", "length_m", "road_class"}, "link"
        )
        unique(row["link_id"], link_ids, "link")
        if row["road_class"] not in CLASSES:
            raise ValueError("road_class: unknown class")
        length = decimal(row["length_m"], "length_m")
        if length <= 0:
            raise ValueError("length_m: must be positive")
        if length.denominator != 1:
            raise ValueError("length_m: must be a whole number of metres")
        if any(
            row[key] not in {node.id for node in nodes} for key in ("source", "target")
        ):
            raise ValueError("link: unknown node")
        links.append(
            Link(
                row["link_id"], row["source"], row["target"], length, row["road_class"]
            )
        )
    units = {}
    unit_ids: set[str] = set()
    for raw in data["units"]:
        row = closed(raw, {"unit_id", "lat", "lon"}, "unit")
        unique(row["unit_id"], unit_ids, "unit")
        units[row["unit_id"]] = (decimal(row["lat"], "lat"), decimal(row["lon"], "lon"))
    if not nodes or not links:
        raise ValueError("roads: empty graph")
    return Roads(tuple(nodes), tuple(links), units)


def parse_flows(value: Any, roads: Roads) -> tuple[Flow, ...]:
    data = closed(value, {"note", "unit", "rows"}, "flows")
    if data["unit"] != "vehicle trips per hour":
        raise FlowUnitError("NO_DATA: flow_unit_not_vehicle_trips")
    flows = []
    seen = set()
    for raw in data["rows"]:
        row = closed(
            raw,
            {
                "origin_unit_id",
                "destination_unit_id",
                "day_type",
                "hour",
                "summer",
                "estimate",
            },
            "flow",
        )
        hour = row["hour"]
        if type(hour) is not int or not 0 <= hour < 24:
            raise ValueError("hour: outside stored day")
        if row["day_type"] != "weekday" or row["summer"] is not False:
            raise ValueError("flow: fixture requires weekday and summer false")
        if any(
            row[key] not in roads.units
            for key in ("origin_unit_id", "destination_unit_id")
        ):
            raise ValueError("flow: unknown unit")
        estimate = decimal(row["estimate"], "estimate")
        if estimate < 0 or estimate.denominator != 1:
            raise ValueError("estimate: must be a nonnegative whole count")
        key = (
            row["origin_unit_id"],
            row["destination_unit_id"],
            row["day_type"],
            hour,
            row["summer"],
        )
        if key in seen:
            raise ValueError("flow: duplicate key")
        seen.add(key)
        flows.append(
            Flow(
                row["origin_unit_id"],
                row["destination_unit_id"],
                row["day_type"],
                hour,
                row["summer"],
                estimate,
            )
        )
    return tuple(flows)
