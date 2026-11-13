"""L-81 R7 pinned junction costs, without changes to engine costing.

Option probes use the official routing API reference, automobile costing options,
read on 2026-11-13: https://valhalla.github.io/valhalla/api/route/api-reference/.
They are measurement requests only; none changes the product's request options.
"""

import copy
import json
import unittest
from fractions import Fraction
from functools import partial
from pathlib import Path
from typing import Any

from test_assignment_route_identity import fresh_traffic
from valhalla import Actor

from eii_product.areas_spike.engine import scaled_actor
from eii_product.areas_spike.road import Node, load_road

FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "product/tests/fixtures/areas_spike/assignment/junction_roads.json"
)
# Method card: a single link agrees within 0.001 seconds; pinned junction
# delays agree within 0.001 seconds or the engine needs requalification.
BOUND_SECONDS = Fraction("0.001")
OPTIONS: dict[str, dict[str, Any]] = {
    "default": {},
    "zero_maneuver_penalty": {"maneuver_penalty": 0},
    "shortest": {"shortest": True},
    "shortest_without_hierarchy": {
        "shortest": True,
        "disable_hierarchy_pruning": True,
    },
}


def route_summary(
    actor: Actor,
    nodes: dict[str, Node],
    options: dict[str, Any],
    origin: str,
    destination: str,
) -> dict[str, Any]:
    answer = actor.route(
        {
            "locations": [
                {"lat": nodes[key]["lat"], "lon": nodes[key]["lon"]}
                for key in (origin, destination)
            ],
            "costing": "auto",
            "costing_options": {"auto": {"speed_types": [], **options}},
        }
    )
    result: dict[str, Any] = answer["trip"]["summary"]
    return result


class AssignmentJunctionTests(unittest.TestCase):
    def test_junction_delays_match_pinned_measurements(self) -> None:
        observations: list[dict[str, Any]] = []
        for speed in (60, 20):
            road = copy.deepcopy(load_road(FIXTURE))
            for edge in road["edges"]:
                edge["drive_kph"] = speed
            actor, _temporary = scaled_actor(json.dumps(road, sort_keys=True), 1.0)
            nodes = {node["id"]: node for node in road["nodes"]}
            for label, options in OPTIONS.items():
                summary = partial(route_summary, actor, nodes, options)

                for edge in road["edges"]:
                    single = summary(edge["source"], edge["target"])
                    assert Fraction(str(single["length"])) * 1000 == edge["length_m"]
                    assert (
                        abs(
                            Fraction(str(single["time"]))
                            - Fraction(edge["length_m"]) * Fraction("3.6") / speed
                        )
                        <= BOUND_SECONDS
                    )
                for origin, straight, turn, opposite in (
                    ("W", "E", "N", "S"),
                    ("E", "W", "S", "N"),
                    ("N", "S", "E", "W"),
                    ("S", "N", "W", "E"),
                ):
                    for movement, end in (
                        ("straight", straight),
                        ("turn", turn),
                        ("opposite_turn", opposite),
                    ):
                        source, destination = "SYN-N-" + origin, "SYN-N-" + end
                        first = Fraction(str(summary(source, "SYN-N-C")["time"]))
                        second = Fraction(str(summary("SYN-N-C", destination)["time"]))
                        combined = Fraction(str(summary(source, destination)["time"]))
                        # Each crossing arm is 1113 whole metres, in either direction.
                        exact = sum(
                            (
                                Fraction(edge["length_m"]) * Fraction("3.6") / speed
                                for edge in road["edges"]
                                if {edge["source"], edge["target"]}
                                in ({source, "SYN-N-C"}, {"SYN-N-C", destination})
                            ),
                            Fraction(0),
                        )
                        observation = {
                            "measurement": "junction-time",
                            "options": label,
                            "speed_kph": speed,
                            "movement": movement,
                            "path": [source, "SYN-N-C", destination],
                            "single_seconds": [str(first), str(second)],
                            "sum_seconds": str(exact),
                            "route_seconds": str(combined),
                            "added_seconds": str(combined - exact),
                        }
                        print(json.dumps(observation, sort_keys=True))
                        observations.append(observation)
        # Installed engine measurement on 2026-11-13: straight +0.017 s;
        # north turn +2.105 s. The area measurement also found the south turn:
        # 138.954 - 133.560 = 5.394 s at free flow. Pin that stated limit too.
        expected = {
            "straight": Fraction("0.017"),
            "turn": Fraction("2.105"),
            "opposite_turn": Fraction("5.394"),
        }
        for row in observations:
            self.assertLessEqual(
                abs(Fraction(row["added_seconds"]) - expected[row["movement"]]),
                BOUND_SECONDS,
                "STOP R7: junction delay differs from L-81: " + json.dumps(row),
            )

    def test_assignment_middle_delays_match_pinned_measurements(self) -> None:
        # Measured once on the installed engine before these pins were added:
        # hourly free/reverse: 181.277 - 181.26 = 0.017 s;
        # hourly h=8 forward: 574.906 - 330561/575 = 199/11500 s.
        # worked h=8 and h=9: 720 - 720 = 0 s; free direct: 600 - 600 = 0 s.
        for name, hour, reverse, expected in (
            ("hourly", None, False, Fraction("0.017")),
            ("hourly", None, True, Fraction("0.017")),
            ("hourly", 8, False, Fraction(199, 11500)),
            ("hourly", 8, True, Fraction("0.017")),
            ("worked", None, False, Fraction(0)),
            ("worked", 8, False, Fraction(0)),
            ("worked", 9, False, Fraction(0)),
        ):
            _result, traffic = fresh_traffic(name)
            origin, destination = "SYN-N-0-0", "SYN-N-0-2"
            if reverse:
                origin, destination = destination, origin
            route = traffic.route(origin, destination, hour)
            self.assertEqual(
                len(route["link_ids"]), 1 if name == "worked" and hour is None else 2
            )
            raw = traffic.route_for_measurement(origin, destination, hour)
            engine = Fraction(str(raw["trip"]["summary"]["time"]))
            links = sum(route["link_minutes"], Fraction(0)) * 60
            row = {
                "fixture": name,
                "origin": origin,
                "destination": destination,
                "hour": hour,
                "engine_seconds": str(engine),
                "link_seconds": str(links),
                "added_seconds": str(engine - links),
                "pinned_seconds": str(expected),
            }
            print(json.dumps(row, sort_keys=True))
            self.assertLessEqual(abs(engine - links - expected), BOUND_SECONDS, row)

    def test_worked_middle_free_flow_pinned_measurement(self) -> None:
        # Isolate the two links through the middle node: the full free-flow
        # graph chooses the direct link and therefore never visits this junction.
        # No speed, length, coordinate or costing option changes.
        _result, traffic = fresh_traffic("worked")
        road = traffic.road_fixture(traffic.speed_vector(None), "SYN-N-0-0")
        road["edges"] = road["edges"][1:]
        actor, _temporary = scaled_actor(json.dumps(road, sort_keys=True), 1.0)
        nodes = {node["id"]: node for node in road["nodes"]}
        summary = route_summary(actor, nodes, {}, "SYN-N-0-0", "SYN-N-0-2")
        exact = sum(
            (
                Fraction(edge["length_m"])
                * Fraction("3.6")
                / Fraction(edge["drive_kph"])
                for edge in road["edges"]
            ),
            Fraction(0),
        )
        engine = Fraction(str(summary["time"]))
        print(
            json.dumps(
                {
                    "fixture": "worked-middle-isolated",
                    "hour": None,
                    "engine_seconds": str(engine),
                    "link_seconds": str(exact),
                    "added_seconds": str(engine - exact),
                }
            )
        )
        # Measured middle-node free-flow route: 720 - 720 = 0 seconds.
        self.assertEqual(exact, Fraction(720))
        self.assertLessEqual(abs(engine - exact), BOUND_SECONDS)
