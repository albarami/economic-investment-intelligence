"""R4: lengths are the engine's stored metres, measured one edge at a time."""

import json
import unittest
from fractions import Fraction as F
from pathlib import Path

from eii_product.areas_spike.engine import scaled_actor
from eii_product.areas_spike.traffic import Traffic

FIXTURES = (
    Path(__file__).resolve().parents[2]
    / "product/tests/fixtures/areas_spike/assignment"
)


class AssignmentLengthTests(unittest.TestCase):
    def test_every_link_length_matches_engine_metres(self) -> None:
        for name in ("worked", "hourly"):
            roads = json.loads((FIXTURES / f"{name}_roads.json").read_text())
            params = json.loads((FIXTURES / f"{name}_parameters.json").read_text())
            traffic = Traffic(
                roads, {k: F(v["value"]) for k, v in params["speeds"].items()}, ()
            )
            for index, link in enumerate(roads["links"]):
                road = traffic.road_fixture(traffic.speed_vector(None), link["source"])
                road["edges"] = [road["edges"][index]]
                actor, _temporary = scaled_actor(json.dumps(road, sort_keys=True), 1.0)
                nodes = {node["id"]: node for node in road["nodes"]}
                answer = actor.route(
                    {
                        "locations": [
                            {"lat": nodes[key]["lat"], "lon": nodes[key]["lon"]}
                            for key in (link["source"], link["target"])
                        ],
                        "costing": "auto",
                        "costing_options": {"auto": {"speed_types": []}},
                    }
                )
                measured = F(str(answer["trip"]["summary"]["length"])) * 1000
                print(
                    name,
                    link["link_id"],
                    "declared_m",
                    link["length_m"],
                    "engine_m",
                    measured,
                )
                self.assertEqual(measured, F(link["length_m"]), (name, link["link_id"]))
