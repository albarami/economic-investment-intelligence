"""L-84 S1: exact cross-plane link sums, including explicit unreachable pairs."""

import unittest
from fractions import Fraction
from pathlib import Path
from tempfile import TemporaryDirectory

from eii_custodian.assignment_spike.run import Result, calculate
from eii_product.areas_spike.traffic import Traffic

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "custodian/tests/fixtures/assignment_spike"


def fresh_traffic(name: str) -> tuple[Result, Traffic]:
    parameters = FIXTURES / (
        "parameters_v1.json" if name == "hourly" else "worked_parameters.json"
    )
    roads = FIXTURES / f"{name}_roads.json"
    result = calculate(FIXTURES / f"{name}_flows.json", roads, parameters)
    with TemporaryDirectory(prefix="synthetic-route-identity-") as temporary:
        rows = Path(temporary) / "rows.json"
        rows.write_bytes(result.to_bytes())
        traffic = Traffic.load(rows, roads, parameters)
    return result, traffic


class AssignmentRouteIdentityTests(unittest.TestCase):
    def test_all_ordered_pairs_exact_shortest_link_sums(self) -> None:
        for name in ("worked", "hourly"):
            result, traffic = fresh_traffic(name)
            hours = (
                range(24)
                if name == "hourly"
                else sorted({0, *(row.hour for row in result.calculations)})
            )
            links = {(link.source, link.target): link.id for link in result.roads.links}
            for hour in hours:
                for origin in result.roads.nodes:
                    for destination in result.roads.nodes:
                        if origin == destination:
                            continue
                        try:
                            exact, nodes = result.shortest_minutes(
                                origin.id, destination.id, "weekday", hour, False
                            )
                        except ValueError as error:
                            self.assertEqual(
                                str(error),
                                "NO_DATA: disconnected origin and destination",
                            )
                            with self.assertRaisesRegex(
                                RuntimeError, "No path could be found for input"
                            ):
                                traffic.route(origin.id, destination.id, hour)
                        else:
                            from itertools import pairwise

                            route = traffic.route(origin.id, destination.id, hour)
                            self.assertEqual(
                                sum(route["link_minutes"], Fraction(0)),
                                exact,
                                (name, hour, origin.id, destination.id),
                            )
                            self.assertEqual(
                                route["link_ids"],
                                tuple(links[pair] for pair in pairwise(nodes)),
                            )
                            raw = traffic.route_for_measurement(
                                origin.id, destination.id, hour
                            )
                            # Method card: a route agrees with its itemised
                            # total within n x 0.001 seconds for n links.
                            self.assertLessEqual(
                                abs(
                                    Fraction(str(raw["trip"]["summary"]["time"]))
                                    - route["minutes"] * 60
                                ),
                                len(route["link_ids"]) * Fraction("0.001"),
                            )

    def test_crossing_ordered_pairs_at_both_speeds(self) -> None:
        from assignment_area_measurement import crossing

        from eii_custodian.assignment_spike.inputs import Link, Node, Roads
        from eii_custodian.assignment_spike.paths import shortest

        traffic = crossing()
        graph = Roads(
            tuple(
                Node(n["id"], Fraction(str(n["lat"])), Fraction(str(n["lon"])))
                for n in traffic.roads["nodes"]
            ),
            tuple(
                Link(
                    e["link_id"],
                    e["source"],
                    e["target"],
                    Fraction(e["length_m"]),
                    e["road_class"],
                )
                for e in traffic.roads["links"]
            ),
            {},
        )
        for hour, speed in ((None, 60), (8, 20)):
            times = {
                link.id: link.length_m * 60 / (1000 * speed) for link in graph.links
            }
            for origin in graph.nodes:
                for destination in graph.nodes:
                    if origin == destination:
                        continue
                    cost, _nodes, links = shortest(
                        graph, times, origin.id, destination.id
                    )
                    route = traffic.route(origin.id, destination.id, hour)
                    self.assertEqual(route["link_ids"], links)
                    self.assertEqual(sum(route["link_minutes"], Fraction(0)), cost)

    def test_worked_free_flow_direct_path(self) -> None:
        _result, traffic = fresh_traffic("worked")
        route = traffic.route("SYN-N-0-0", "SYN-N-0-2", None)
        self.assertEqual(route["link_ids"], ("SYN-L-001",))
        self.assertEqual(route["minutes"], Fraction(10))
