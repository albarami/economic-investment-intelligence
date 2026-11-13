"""Closed parameter contract. Decimal texts are converted directly to rationals."""

import re
from dataclasses import dataclass
from datetime import date
from fractions import Fraction
from itertools import pairwise
from typing import Any

ENGINE_MIN_KPH = 10
ENGINE_MAX_KPH = 140

CLASSES = {"motorway", "trunk", "primary", "secondary", "tertiary", "residential"}


def closed(value: Any, keys: set[str], field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{field}: expected object")
    if set(value) != keys:
        difference = sorted(set(value) ^ keys)
        raise ValueError(f"{field}: missing or unknown fields {difference}")
    return value


def decimal(value: Any, field: str) -> Fraction:
    if not isinstance(value, str) or not re.fullmatch(r"-?[0-9]+(?:\.[0-9]+)?", value):
        raise ValueError(f"{field}: expected decimal text")
    return Fraction(value)


def entry(value: Any, field: str, unit: str) -> Fraction:
    row = closed(value, {"value", "unit", "source", "read", "status"}, field)
    for name in ("source", "read", "status"):
        if not isinstance(row[name], str) or not row[name].strip():
            raise ValueError(f"{field}.{name}: required")
    try:
        date.fromisoformat(row["read"])
    except ValueError as error:
        raise ValueError(f"{field}.read: expected date") from error
    if row["unit"] != unit:
        raise ValueError(f"{field}.unit: expected {unit}")
    number = decimal(row["value"], field)
    if number <= 0:
        raise ValueError(f"{field}: must be positive")
    return number


@dataclass(frozen=True)
class Parameters:
    alpha: Fraction
    beta: int
    speeds: dict[str, Fraction]
    capacities: dict[str, Fraction]
    edges: tuple[Fraction, ...]
    band_count: int
    speed_floor_kph: Fraction


def parse_parameters(value: Any) -> Parameters:
    data = closed(
        value,
        {
            "alpha",
            "beta",
            "speeds",
            "capacities",
            "band_count",
            "band_edges",
            "speed_floor_kph",
        },
        "parameters",
    )
    alpha = entry(data["alpha"], "alpha", "none")
    floor = entry(data["speed_floor_kph"], "speed_floor_kph", "kilometres per hour")
    if floor.denominator != 1:
        raise ValueError("speed_floor_kph: must be a positive whole number")
    if floor < ENGINE_MIN_KPH:
        raise ValueError(f"speed_floor_kph: below engine minimum {ENGINE_MIN_KPH}")
    beta = entry(data["beta"], "beta", "none")
    if beta.denominator != 1:
        raise ValueError("beta: must be a positive whole number")
    speeds = closed(data["speeds"], CLASSES, "speeds")
    capacities = closed(data["capacities"], CLASSES, "capacities")
    speed_values = {
        key: entry(speeds[key], f"speeds.{key}", "kilometres per hour")
        for key in sorted(CLASSES)
    }
    for key, speed in speed_values.items():
        if speed.denominator != 1:
            raise ValueError(f"speeds.{key}: must be a whole number")
        if speed > ENGINE_MAX_KPH:
            raise ValueError(f"speeds.{key}: above engine maximum {ENGINE_MAX_KPH}")
        if speed < floor:
            raise ValueError(f"speeds.{key}: below speed_floor_kph")
    capacity_values = {
        key: entry(
            capacities[key],
            f"capacities.{key}",
            "vehicle trips per hour for one direction",
        )
        for key in sorted(CLASSES)
    }
    count = entry(data["band_count"], "band_count", "none")
    if count.denominator != 1:
        raise ValueError("band_count: must be a whole number")
    if not isinstance(data["band_edges"], list) or len(data["band_edges"]) != count - 1:
        raise ValueError("band_edges: must match band_count")
    edges = tuple(
        entry(edge, f"band_edges.{index}", "none")
        for index, edge in enumerate(data["band_edges"])
    )
    if any(a >= b for a, b in pairwise(edges)):
        raise ValueError("band_edges: must be strictly increasing")
    return Parameters(
        alpha, int(beta), speed_values, capacity_values, edges, int(count), floor
    )
