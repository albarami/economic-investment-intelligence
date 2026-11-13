"""Read the C25 file, then route with cached, independent directional speeds.

The parameter snapshot is a method artefact, matched by its header digest; it
supplies free-flow speeds only. No assignment code is imported by this plane.
"""

import hashlib
import json
import re
from dataclasses import dataclass
from fractions import Fraction
from itertools import pairwise
from pathlib import Path
from typing import Any, Self

from valhalla.midgard.utils import decode_polyline

from .engine import scaled_actor
from .road import Edge, RoadFixture
from .shapes import Ring
from .snap import snap_polygon

ENGINE_MIN_KPH = 10
ENGINE_MAX_KPH = 140


def closed(value: Any, keys: set[str], field: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        raise ValueError(f"{field}: missing or unknown field")
    return value


def engine_speed(exact: Fraction) -> int:
    """Half-up whole kph; the method, not the adapter, applies the floor."""
    return (2 * exact.numerator + exact.denominator) // (2 * exact.denominator)


@dataclass(frozen=True)
class TrafficArea:
    exact: Ring
    cells: tuple[str, ...]
    provenance: str
    evidence_status: str = "observed"
    caveat: str | None = None


@dataclass(frozen=True)
class Traffic:
    roads: dict[str, Any]
    speeds: dict[str, Fraction]
    rows: tuple[dict[str, Any], ...]

    @classmethod
    def load(cls, rows_path: Path, roads_path: Path, parameters_path: Path) -> Self:
        payload = closed(
            json.loads(rows_path.read_bytes()), {"header", "rows"}, "traffic"
        )
        header = closed(
            payload["header"],
            {
                "method",
                "sources",
                "provenance",
                "evidence_status",
                "caveat",
                "withheld_note",
            },
            "header",
        )
        method = closed(header["method"], {"id", "parameters_sha256"}, "method")
        sources = closed(header["sources"], {"flow_hourly", "road_link"}, "sources")
        for field, value in {
            **sources,
            "parameters_sha256": method["parameters_sha256"],
        }.items():
            if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
                raise ValueError(f"{field}: expected SHA-256")
        expected = {
            "provenance": "Simulated",
            "evidence_status": "observed",
            "caveat": "traffic_simulated",
            "withheld_note": "Flows withheld by the disclosure controls are left out.",
        }
        for field, value in expected.items():
            if header[field] != value:
                raise ValueError(f"header.{field}: incorrect value")
        if method["id"] != "C25":
            raise ValueError("method: expected C25")
        road_bytes = roads_path.read_bytes()
        parameter_bytes = parameters_path.read_bytes()
        if sources["road_link"] != hashlib.sha256(road_bytes).hexdigest():
            raise ValueError("road_link: digest mismatch")
        if method["parameters_sha256"] != hashlib.sha256(parameter_bytes).hexdigest():
            raise ValueError("parameters_sha256: digest mismatch")
        roads = json.loads(road_bytes)
        for link in roads["links"]:
            if Fraction(link["length_m"]).denominator != 1:
                raise ValueError(
                    f"{roads_path.name}: length_m must be whole metres for {link['link_id']}"
                )
        parameters = json.loads(parameter_bytes)
        speeds = {
            key: Fraction(value["value"]) for key, value in parameters["speeds"].items()
        }
        floor = Fraction(parameters["speed_floor_kph"]["value"])
        if floor.denominator != 1:
            raise ValueError("speed_floor_kph: must be a whole number")
        if floor < ENGINE_MIN_KPH:
            raise ValueError(f"speed_floor_kph: below engine minimum {ENGINE_MIN_KPH}")
        for key, free_speed in speeds.items():
            if free_speed.denominator != 1:
                raise ValueError(f"speeds.{key}: must be a whole number")
            if free_speed > ENGINE_MAX_KPH:
                raise ValueError(f"speeds.{key}: above engine maximum {ENGINE_MAX_KPH}")
            if free_speed < floor:
                raise ValueError(f"speeds.{key}: below speed_floor_kph")
        band_keys = {
            f"vb{index}"
            for index in range(1, int(parameters["band_count"]["value"]) + 1)
        }
        seen = set()
        for raw in payload["rows"]:
            row = closed(
                raw,
                {"link_id", "day_type", "hour", "summer", "speed_ratio", "volume_band"},
                "traffic row",
            )
            cls.check_hour(row["day_type"], row["hour"], row["summer"])
            if row["link_id"] not in {link["link_id"] for link in roads["links"]}:
                raise ValueError("link_id: unknown link")
            if (
                not isinstance(row["speed_ratio"], str)
                or not re.fullmatch(r"[0-9]\.[0-9]{3}", row["speed_ratio"])
                or not 0 < Fraction(row["speed_ratio"]) <= 1
            ):
                raise ValueError("speed_ratio: outside contract")
            if row["volume_band"] not in band_keys:
                raise ValueError("volume_band: unknown band")
            key = (row["link_id"], row["day_type"], row["hour"], row["summer"])
            if key in seen:
                raise ValueError("traffic row: duplicate key")
            seen.add(key)
        traffic = cls(roads, speeds, tuple(payload["rows"]))
        links = {link["link_id"]: link for link in roads["links"]}
        for row in traffic.rows:
            speed = traffic.link_speed(
                row["link_id"], row["hour"], row["day_type"], row["summer"]
            )
            if speed < floor:
                raise ValueError(
                    f"{rows_path.name}: released speed floor violated by {row['link_id']}"
                )
            free = speeds[links[row["link_id"]]["road_class"]]
            canonical = Fraction(engine_speed(Fraction(speed) / free * 1000), 1000)
            if Fraction(row["speed_ratio"]) != canonical:
                raise ValueError(
                    f"{rows_path.name}: noncanonical speed_ratio for {row['link_id']}"
                )
        return traffic

    @staticmethod
    def check_hour(day_type: str, hour: int, summer: bool) -> None:
        if (
            day_type != "weekday"
            or type(summer) is not bool
            or type(hour) is not int
            or not 0 <= hour < 24
        ):
            raise ValueError("Unknown day_type, hour or summer")

    def link_speed(
        self,
        link_id: str,
        hour: int | None,
        day_type: str = "weekday",
        summer: bool = False,
    ) -> int:
        """The only product link speed: released ratio times class speed, half-up."""
        if hour is not None:
            self.check_hour(day_type, hour, summer)
        ratios = {
            row["link_id"]: Fraction(row["speed_ratio"])
            for row in self.rows
            if (row["day_type"], row["hour"], row["summer"]) == (day_type, hour, summer)
        }
        link = next(link for link in self.roads["links"] if link["link_id"] == link_id)
        return engine_speed(
            self.speeds[link["road_class"]] * ratios.get(link_id, Fraction(1))
        )

    def link_minutes(
        self,
        link_id: str,
        hour: int | None,
        day_type: str = "weekday",
        summer: bool = False,
    ) -> Fraction:
        """Exact rational minutes over the same whole speed used by the engine."""
        link = next(link for link in self.roads["links"] if link["link_id"] == link_id)
        return (
            Fraction(link["length_m"])
            * 60
            / (1000 * self.link_speed(link_id, hour, day_type, summer))
        )

    def speed_vector(
        self, hour: int | None, day_type: str = "weekday", summer: bool = False
    ) -> tuple[int, ...]:
        return tuple(
            self.link_speed(link["link_id"], hour, day_type, summer)
            for link in self.roads["links"]
        )

    def road_fixture(self, vector: tuple[int, ...], pin: str) -> RoadFixture:
        if any(
            type(speed) is not int or not ENGINE_MIN_KPH <= speed <= ENGINE_MAX_KPH
            for speed in vector
        ):
            raise ValueError(
                f"speed: expected whole number from {ENGINE_MIN_KPH} to {ENGINE_MAX_KPH}"
            )
        edges: list[Edge] = [
            {
                "source": link["source"],
                "target": link["target"],
                "length_m": float(link["length_m"]),
                "drive_kph": float(speed),
                "road_class": link["road_class"],
                "oneway": True,
            }
            for link, speed in zip(self.roads["links"], vector, strict=True)
        ]
        return {
            "pin": pin,
            "walk_kph": 5.0,
            "cutoff_seconds": 0.0,
            "radius_m": 0.0,
            "nodes": [
                {"id": node["id"], "lat": float(node["lat"]), "lon": float(node["lon"])}
                for node in self.roads["nodes"]
            ],
            "edges": edges,
        }

    def actor(
        self, hour: int | None, day_type: str = "weekday", summer: bool = False
    ) -> Any:
        road = self.road_fixture(
            self.speed_vector(hour, day_type, summer), self.roads["nodes"][0]["id"]
        )
        return scaled_actor(json.dumps(road, sort_keys=True), 1.0)[0]

    def route_for_measurement(
        self,
        origin: str,
        destination: str,
        hour: int | None,
        day_type: str = "weekday",
        summer: bool = False,
    ) -> dict[str, Any]:
        """Raw engine response, exclusively for spike measurements."""
        nodes = {node["id"]: node for node in self.roads["nodes"]}
        answer: dict[str, Any] = self.actor(hour, day_type, summer).route(
            {
                "locations": [
                    {"lat": float(nodes[key]["lat"]), "lon": float(nodes[key]["lon"])}
                    for key in (origin, destination)
                ],
                "costing": "auto",
                "costing_options": {"auto": {"speed_types": []}},
            }
        )
        return answer

    def route(
        self,
        origin: str,
        destination: str,
        hour: int | None,
        day_type: str = "weekday",
        summer: bool = False,
    ) -> dict[str, Any]:
        """One exact trip total with link minutes and an itemised junction cost."""
        answer = self.route_for_measurement(origin, destination, hour, day_type, summer)
        # The fixture has straight links: consecutive shape vertices are nodes.
        # Maneuver names are insufficient: the engine merges straight movements.
        node_at = {
            (round(float(node["lon"]), 6), round(float(node["lat"]), 6)): node["id"]
            for node in self.roads["nodes"]
        }
        link_between = {
            (link["source"], link["target"]): link["link_id"]
            for link in self.roads["links"]
        }
        link_ids = tuple(
            link_between[
                node_at[(round(start[0], 6), round(start[1], 6))],
                node_at[(round(end[0], 6), round(end[1], 6))],
            ]
            for leg in answer["trip"]["legs"]
            for start, end in pairwise(decode_polyline(leg["shape"]))
        )
        link_minutes = tuple(
            self.link_minutes(link, hour, day_type, summer) for link in link_ids
        )
        link_total = sum(link_minutes, Fraction(0))
        residual = Fraction(str(answer["trip"]["summary"]["time"])) - link_total * 60
        # Method card: a route agrees with its itemised total within
        # n x 0.001 seconds for n links (printed engine resolution).
        resolution = len(link_ids) * Fraction("0.001")
        if residual < -resolution:
            raise ValueError(
                "engine time below exact link sum beyond printed resolution"
            )
        if len(link_ids) == 1 and residual > resolution:
            raise ValueError(
                "engine time above exact link time on a route without junctions"
            )
        junction = (
            Fraction(0)
            if abs(residual) <= resolution
            else Fraction(engine_speed(residual * 1000), 1000)
        )
        return {
            "link_ids": link_ids,
            "link_minutes": link_minutes,
            "junction_seconds": junction,
            "minutes": link_total + junction / 60,
            "line": tuple(
                (lat, lon)
                for leg in answer["trip"]["legs"]
                for lon, lat in decode_polyline(leg["shape"])
            ),
            "provenance": "Public" if hour is None else "Simulated",
            "evidence_status": "observed",
            "caveat": None if hour is None else "traffic_simulated",
        }

    def area(
        self,
        pin: str,
        minutes: float,
        hour: int | None,
        frame: tuple[str, ...],
        *,
        mode: str = "drive",
        day_type: str = "weekday",
        summer: bool = False,
    ) -> TrafficArea:
        self.check_hour(day_type, 0 if hour is None else hour, summer)
        if mode not in {"drive", "walk"}:
            raise ValueError("Unknown mode")
        if minutes <= 0:
            raise ValueError("Cutoff must be positive")
        node = next(node for node in self.roads["nodes"] if node["id"] == pin)
        costing = "auto" if mode == "drive" else "pedestrian"
        actor = self.actor(None if mode == "walk" else hour, day_type, summer)
        answer = actor.isochrone(
            {
                "locations": [{"lat": float(node["lat"]), "lon": float(node["lon"])}],
                "costing": costing,
                "contours": [{"time": minutes}],
                "polygons": True,
                "costing_options": {costing: {"speed_types": [], "walking_speed": 5.0}},
            }
        )
        geometry = answer["features"][0]["geometry"]
        if geometry["type"] != "Polygon" or len(geometry["coordinates"]) != 1:
            raise ValueError("Engine geometry must be a Polygon with one ring")
        ring = tuple((lat, lon) for lon, lat in geometry["coordinates"][0])
        return TrafficArea(
            ring,
            snap_polygon(ring, frame),
            "Simulated" if hour is not None and mode == "drive" else "Public",
            caveat="traffic_simulated"
            if hour is not None and mode == "drive"
            else None,
        )
