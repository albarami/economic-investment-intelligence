"""L-81 R6 measurement only: original engine outlines, no product changes.

Bisection brackets the entry to 0.01 seconds. A zero lower endpoint denotes
an infimum: the engine accepts positive cutoffs only. Containment is covers
on the original polygon without a coordinate buffer. The search assumes
monotonic containment; all sampled cutoffs are checked for contradictions.
"""

import importlib
import json
from fractions import Fraction
from functools import cache
from pathlib import Path
from typing import Any, Protocol, cast

from test_assignment_route_identity import fresh_traffic

from eii_product.areas_spike.traffic import Traffic

FIXTURES = (
    Path(__file__).resolve().parents[2]
    / "product/tests/fixtures/areas_spike/assignment"
)
# Method card: entry times are bracketed within 0.01 seconds.
RESOLUTION_SECONDS = Fraction("0.01")


class PolygonAPI(Protocol):
    def covers(self, other: object) -> bool: ...


class GeometryAPI(Protocol):
    def Point(self, x: float, y: float) -> object: ...
    def shape(self, context: dict[str, Any]) -> PolygonAPI: ...


geometry = cast(GeometryAPI, importlib.import_module("shapely.geometry"))


def crossing() -> Traffic:
    fixture = json.loads((FIXTURES / "junction_roads.json").read_text())
    links: list[dict[str, Any]] = []
    for edge in fixture["edges"]:
        for source, target in (
            (edge["source"], edge["target"]),
            (edge["target"], edge["source"]),
        ):
            links.append(
                {
                    "link_id": f"SYN-L-{len(links) + 1:03d}",
                    "source": source,
                    "target": target,
                    "length_m": str(edge["length_m"]),
                    "road_class": edge["road_class"],
                }
            )
    return Traffic(
        {"nodes": fixture["nodes"], "links": links},
        {"secondary": Fraction(60)},
        tuple(
            {
                "link_id": link["link_id"],
                "day_type": "weekday",
                "hour": 8,
                "summer": False,
                "speed_ratio": "0.333",
                "volume_band": "vb3",
            }
            for link in links
        ),
    )


def measure_fixture(traffic: Traffic, name: str) -> list[dict[str, Any]]:
    observations: list[dict[str, Any]] = []
    nodes = traffic.roads["nodes"]
    hours = [None, *sorted({row["hour"] for row in traffic.rows})]
    for hour in hours:
        actor = traffic.actor(hour)
        # A finite search ceiling, not an assertion that every node is reachable.
        ceiling = 2 * sum(
            (
                traffic.link_minutes(link["link_id"], hour) * 60
                for link in traffic.roads["links"]
            ),
            Fraction(0),
        )
        ceiling = min(ceiling, Fraction(120 * 60))
        for origin in nodes:

            @cache
            def outline(
                seconds: Fraction, actor: Any = actor, origin: dict[str, Any] = origin
            ) -> PolygonAPI:
                answer = actor.isochrone(
                    {
                        "locations": [
                            {"lat": float(origin["lat"]), "lon": float(origin["lon"])}
                        ],
                        "costing": "auto",
                        "contours": [{"time": float(seconds / 60)}],
                        "polygons": True,
                        "costing_options": {
                            "auto": {"speed_types": [], "walking_speed": 5.0}
                        },
                    }
                )
                return geometry.shape(answer["features"][0]["geometry"])

            for destination in nodes:
                record: dict[str, Any] = {
                    "fixture": name,
                    "hour": hour,
                    "origin": origin["id"],
                    "destination": destination["id"],
                }
                if origin["id"] == destination["id"]:
                    record.update(route_seconds="0", link_seconds="0", link_ids=[])
                else:
                    try:
                        route = traffic.route(origin["id"], destination["id"], hour)
                    except RuntimeError as error:
                        if str(error) != "No path could be found for input":
                            raise
                        record.update(
                            route_seconds=None,
                            link_seconds=None,
                            route_error=str(error),
                        )
                    else:
                        record.update(
                            route_seconds=str(
                                traffic.route_for_measurement(
                                    origin["id"], destination["id"], hour
                                )["trip"]["summary"]["time"]
                            ),
                            link_seconds=format(
                                float(sum(route["link_minutes"], Fraction(0)) * 60),
                                ".6f",
                            ),
                            link_ids=list(route["link_ids"]),
                        )
                point = geometry.Point(
                    float(destination["lon"]), float(destination["lat"])
                )
                low, high = Fraction(0), ceiling
                samples: dict[Fraction, bool] = {}

                def inside(
                    seconds: Fraction,
                    point: object = point,
                    samples: dict[Fraction, bool] = samples,
                ) -> bool:
                    contained = outline(seconds).covers(point)
                    samples[seconds] = contained
                    return contained

                if not inside(high):
                    record.update(
                        entry_low_seconds=format(float(high), ".6f"),
                        entry_high_seconds=None,
                    )
                else:
                    while high - low > RESOLUTION_SECONDS:
                        midpoint = (low + high) / 2
                        if inside(midpoint):
                            high = midpoint
                        else:
                            low = midpoint
                    record.update(
                        entry_low_seconds=format(float(low), ".6f"),
                        entry_high_seconds=format(float(high), ".6f"),
                    )
                seen_inside = False
                for seconds in sorted(samples):
                    if seen_inside and not samples[seconds]:
                        raise AssertionError(f"Nonmonotonic containment: {record}")
                    seen_inside = seen_inside or samples[seconds]
                observations.append(record)
    return observations


def measure_all() -> list[dict[str, Any]]:
    observations = measure_fixture(crossing(), "crossing")
    for name in ("hourly", "worked"):
        _result, traffic = fresh_traffic(name)
        observations.extend(measure_fixture(traffic, name))
    return observations


if __name__ == "__main__":
    for row in measure_all():
        print(json.dumps(row, sort_keys=True))
