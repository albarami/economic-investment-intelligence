"""One canonical file crosses the plane boundary; no hidden input discovery."""

import hashlib
import json
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any

from .assign import free_times, volumes
from .delay import delay_factor, rounded_ratio, volume_band, whole_speed
from .inputs import Roads, parse_flows, parse_roads
from .params import parse_parameters
from .paths import shortest

WITHHELD_NOTE = "Flows withheld by the disclosure controls are left out."


@dataclass(frozen=True)
class Calculation:
    link_id: str
    day_type: str
    hour: int
    summer: bool
    volume: Fraction
    minutes: Fraction
    speed_kph: Fraction
    speed_ratio: str
    volume_band: str


@dataclass(frozen=True)
class Result:
    roads: Roads
    times: dict[str, Fraction]
    calculations: tuple[Calculation, ...]
    payload: dict[str, Any]

    def shortest_minutes(
        self, origin: str, destination: str, day_type: str, hour: int, summer: bool
    ) -> tuple[Fraction, tuple[str, ...]]:
        times = {
            **self.times,
            **{
                row.link_id: row.minutes
                for row in self.calculations
                if (row.day_type, row.hour, row.summer) == (day_type, hour, summer)
            },
        }
        cost, nodes, _links = shortest(self.roads, times, origin, destination)
        return cost, nodes

    def to_bytes(self) -> bytes:
        return (
            json.dumps(self.payload, sort_keys=True, separators=(",", ":")) + "\n"
        ).encode()


def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"JSON: duplicate key {key}")
        result[key] = value
    return result


def calculate(flows_path: Path, roads_path: Path, parameters_path: Path) -> Result:
    flows_bytes = flows_path.read_bytes()
    roads_bytes = roads_path.read_bytes()
    parameter_bytes = parameters_path.read_bytes()
    roads = parse_roads(json.loads(roads_bytes, object_pairs_hook=unique_object))
    flows = parse_flows(json.loads(flows_bytes, object_pairs_hook=unique_object), roads)
    parameters = parse_parameters(
        json.loads(parameter_bytes, object_pairs_hook=unique_object)
    )
    times = free_times(roads, parameters)
    links = {link.id: link for link in roads.links}
    calculations = []
    for (link_id, day_type, hour, summer), volume in sorted(
        volumes(roads, flows, parameters).items()
    ):
        link = links[link_id]
        factor = delay_factor(
            volume, parameters.capacities[link.road_class], parameters
        )
        speed = max(
            parameters.speed_floor_kph,
            Fraction(whole_speed(parameters.speeds[link.road_class] / factor)),
        )
        ratio = rounded_ratio(speed / parameters.speeds[link.road_class])
        calculations.append(
            Calculation(
                link_id,
                day_type,
                hour,
                summer,
                volume,
                link.length_m * 60 / (1000 * speed),
                speed,
                ratio,
                volume_band(
                    volume / parameters.capacities[link.road_class], parameters
                ),
            )
        )
    payload = {
        "header": {
            "method": {
                "id": "C25",
                "parameters_sha256": hashlib.sha256(parameter_bytes).hexdigest(),
            },
            "sources": {
                "flow_hourly": hashlib.sha256(flows_bytes).hexdigest(),
                "road_link": hashlib.sha256(roads_bytes).hexdigest(),
            },
            "provenance": "Simulated",
            "evidence_status": "observed",
            "caveat": "traffic_simulated",
            "withheld_note": WITHHELD_NOTE,
        },
        "rows": [
            {
                key: getattr(row, key)
                for key in (
                    "link_id",
                    "day_type",
                    "hour",
                    "summer",
                    "speed_ratio",
                    "volume_band",
                )
            }
            for row in calculations
        ],
    }
    return Result(roads, times, tuple(calculations), payload)
