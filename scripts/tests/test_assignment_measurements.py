"""L-84 S3: itemised junctions with fixed per-link millisecond bounds."""

import json
import unittest
from fractions import Fraction as F
from typing import Any

from test_assignment_route_identity import FIXTURES, fresh_traffic

from eii_custodian.assignment_spike.params import parse_parameters
from eii_product.areas_spike.engine import scaled_actor
from eii_product.areas_spike.traffic import Traffic

# Method card: a single link agrees within 0.001 seconds; a route
# agrees with its itemised total within n x 0.001 seconds for n links.
BOUND_SECONDS = F("0.001")


def single_summary(traffic: Traffic, index: int, hour: int) -> dict[str, Any]:
    link = traffic.roads["links"][index]
    road = traffic.road_fixture(traffic.speed_vector(hour), link["source"])
    road["edges"] = [road["edges"][index]]
    actor, _temporary = scaled_actor(json.dumps(road, sort_keys=True), 1.0)
    nodes = {node["id"]: node for node in road["nodes"]}
    answer: dict[str, Any] = actor.route(
        {
            "locations": [
                {"lat": nodes[key]["lat"], "lon": nodes[key]["lon"]}
                for key in (link["source"], link["target"])
            ],
            "costing": "auto",
            "costing_options": {"auto": {"speed_types": []}},
        }
    )
    summary: dict[str, Any] = answer["trip"]["summary"]
    return summary


class AssignmentMeasurementTests(unittest.TestCase):
    def test_assignment_single_links_and_day_measurements(self) -> None:
        singles, routes, floors = [], [], []
        for fixture in ("hourly", "worked"):
            result, traffic = fresh_traffic(fixture)
            parameter_name = (
                "parameters_v1.json"
                if fixture == "hourly"
                else "worked_parameters.json"
            )
            params = parse_parameters(
                json.loads((FIXTURES / parameter_name).read_text())
            )
            classes = {link.id: link.road_class for link in result.roads.links}
            floors.append(
                {
                    "fixture": fixture,
                    "exact_rule_speed_below_floor": sum(
                        params.speeds[classes[row.link_id]]
                        / (
                            1
                            + params.alpha
                            * (row.volume / params.capacities[classes[row.link_id]])
                            ** params.beta
                        )
                        < params.speed_floor_kph
                        for row in result.calculations
                    ),
                    "released_rows_at_floor": sum(
                        traffic.link_speed(row.link_id, row.hour)
                        == params.speed_floor_kph
                        for row in result.calculations
                    ),
                }
            )
            hours = (
                range(24)
                if fixture == "hourly"
                else sorted({row.hour for row in result.calculations})
            )
            for hour in hours:
                for index, link in enumerate(traffic.roads["links"]):
                    summary = single_summary(traffic, index, hour)
                    exact = traffic.link_minutes(link["link_id"], hour) * 60
                    engine = F(str(summary["time"]))
                    difference = abs(engine - exact)
                    row = {
                        "fixture": fixture,
                        "hour": hour,
                        "link": link["link_id"],
                        "link_seconds": str(exact),
                        "engine_seconds": str(engine),
                        "difference_seconds": str(difference),
                    }
                    self.assertEqual(
                        F(str(summary["length"])) * 1000, F(link["length_m"]), row
                    )
                    self.assertLessEqual(
                        difference, BOUND_SECONDS, "STOP R9: " + json.dumps(row)
                    )
                    singles.append(row)
                for origin in result.roads.nodes:
                    for destination in result.roads.nodes:
                        if origin == destination:
                            continue
                        try:
                            route = traffic.route(origin.id, destination.id, hour)
                        except RuntimeError as error:
                            with self.assertRaisesRegex(
                                ValueError, "NO_DATA: disconnected"
                            ):
                                result.shortest_minutes(
                                    origin.id, destination.id, "weekday", hour, False
                                )
                            self.assertEqual(fixture, "worked")
                            self.assertEqual(
                                str(error), "No path could be found for input"
                            )
                        else:
                            raw = traffic.route_for_measurement(
                                origin.id, destination.id, hour
                            )
                            engine = F(str(raw["trip"]["summary"]["time"]))
                            exact = sum(route["link_minutes"], F(0)) * 60
                            row = {
                                "fixture": fixture,
                                "hour": hour,
                                "origin": origin.id,
                                "destination": destination.id,
                                "links": route["link_ids"],
                                "link_seconds": str(exact),
                                "engine_seconds": str(engine),
                                "junction_seconds": str(route["junction_seconds"]),
                                "difference_seconds": str(
                                    abs(engine - exact - route["junction_seconds"])
                                ),
                            }
                            self.assertLessEqual(
                                abs(engine - exact - route["junction_seconds"]),
                                len(route["link_ids"]) * BOUND_SECONDS,
                                "STOP R9: " + json.dumps(row),
                            )
                            self.assertLessEqual(
                                abs(engine - route["minutes"] * 60),
                                len(route["link_ids"]) * BOUND_SECONDS,
                                row,
                            )
                            routes.append(row)
            for calculation in result.calculations:
                self.assertEqual(
                    calculation.speed_kph,
                    traffic.link_speed(calculation.link_id, calculation.hour),
                )
                self.assertEqual(
                    calculation.minutes,
                    traffic.link_minutes(calculation.link_id, calculation.hour),
                )
        self.assertEqual(
            {
                name: sum(row["fixture"] == name for row in singles)
                for name in ("hourly", "worked")
            },
            {"hourly": 96, "worked": 6},
        )
        self.assertEqual(
            {
                name: sum(row["fixture"] == name for row in routes)
                for name in ("hourly", "worked")
            },
            {"hourly": 144, "worked": 6},
        )
        print(
            json.dumps(
                {
                    "measurement": "assignment-whole-speed-agreement",
                    "bound_seconds": str(BOUND_SECONDS),
                    "single_links": len(singles),
                    "routes": len(routes),
                    "floors": floors,
                    "largest_single": max(
                        singles, key=lambda row: F(row["difference_seconds"])
                    ),
                    "largest_junction": max(
                        routes, key=lambda row: F(row["junction_seconds"])
                    ),
                    "largest_route": max(
                        routes, key=lambda row: F(row["difference_seconds"])
                    ),
                },
                sort_keys=True,
            )
        )

    def test_worked_free_flow_single_link(self) -> None:
        _result, traffic = fresh_traffic("worked")
        summary = single_summary(traffic, 0, 0)
        self.assertEqual(traffic.roads["links"][0]["link_id"], "SYN-L-001")
        self.assertEqual(traffic.link_minutes("SYN-L-001", None), F(10))
        # Method card: a single link agrees within 0.001 seconds.
        self.assertLessEqual(abs(F(str(summary["time"])) - 600), BOUND_SECONDS)
