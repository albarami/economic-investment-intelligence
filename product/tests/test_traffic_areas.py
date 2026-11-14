"""Per-direction traffic rows reach the installed engine; no real geography."""

import json
from fractions import Fraction
from pathlib import Path

from eii_product.areas_spike.traffic import Traffic

FIXTURES = Path(__file__).parent / "fixtures" / "areas_spike" / "assignment"


def test_worked_example_engine_route() -> None:
    traffic = Traffic.load(
        FIXTURES / "worked_rows.json",
        FIXTURES / "worked_roads.json",
        FIXTURES / "worked_parameters.json",
    )
    peak = traffic.route_for_measurement("SYN-N-0-0", "SYN-N-0-2", 8)
    free = traffic.route_for_measurement("SYN-N-0-0", "SYN-N-0-2", None)
    peak_product = traffic.route("SYN-N-0-0", "SYN-N-0-2", 8)
    free_product = traffic.route("SYN-N-0-0", "SYN-N-0-2", None)
    assert (peak_product["provenance"], peak_product["evidence_status"]) == (
        "Simulated",
        "observed",
    )
    assert (free_product["provenance"], free_product["evidence_status"]) == (
        "Public",
        "observed",
    )
    peak_names = {
        name
        for maneuver in peak["trip"]["legs"][0]["maneuvers"]
        for name in maneuver.get("street_names", [])
    }
    free_names = {
        name
        for maneuver in free["trip"]["legs"][0]["maneuvers"]
        for name in maneuver.get("street_names", [])
    }
    minutes = peak["trip"]["summary"]["time"] / 60
    print(
        json.dumps(
            {
                "peak_minutes": minutes,
                "free_minutes": free["trip"]["summary"]["time"] / 60,
                "peak_ways": sorted(peak_names),
                "free_ways": sorted(free_names),
            },
            sort_keys=True,
        )
    )
    assert peak_names == {"SYN-WAY-2", "SYN-WAY-3"}
    assert free_names == {"SYN-WAY-1"}
    assert peak_product["minutes"] == 12
    assert peak_product["junction_seconds"] == 0
    # Method card: a route agrees with its itemised total within n x 0.001 seconds for n links.
    assert abs(Fraction(str(peak["trip"]["summary"]["time"])) - 720) <= Fraction(
        "0.002"
    )


def load_hourly():
    return Traffic.load(
        FIXTURES / "hourly_rows.json",
        FIXTURES / "hourly_roads.json",
        FIXTURES / "hourly_parameters.json",
    )


def test_only_one_direction_is_congested():
    traffic = load_hourly()
    forward = [
        traffic.route_for_measurement("SYN-N-0-0", "SYN-N-0-1", hour)["trip"][
            "summary"
        ]["time"]
        for hour in (0, 8)
    ]
    reverse = [
        traffic.route_for_measurement("SYN-N-0-1", "SYN-N-0-0", hour)["trip"][
            "summary"
        ]["time"]
        for hour in (0, 8)
    ]
    assert forward[1] > forward[0]
    assert reverse[1] == reverse[0]
    assert traffic.speed_vector(8) == (10, 35, 23, 60)


def test_hourly_areas_marks_reuse_and_walk():
    from unittest.mock import patch

    from shapely.geometry import Point, Polygon

    import h3
    from eii_product.areas_spike import engine

    traffic = load_hourly()
    frame = tuple(sorted(h3.grid_disk(h3.latlng_to_cell(0, 0, 9), 12)))
    free = traffic.area("SYN-N-0-0", 3, None, frame)
    quiet = traffic.area("SYN-N-0-0", 3, 0, frame)
    peak = traffic.area("SYN-N-0-0", 3, 8, frame)
    evening = traffic.area("SYN-N-0-0", 3, 17, frame)
    assert free.caveat is None
    assert quiet.caveat == peak.caveat == evening.caveat == "traffic_simulated"
    assert free.exact == quiet.exact
    assert peak.exact != free.exact
    # L-62: speed changes beyond a floored link need not move this short outline.
    from itertools import combinations

    areas = [traffic.area("SYN-N-0-0", 3, hour, frame) for hour in range(24)]
    for first_hour, second_hour in combinations(range(24), 2):
        if traffic.speed_vector(first_hour) == traffic.speed_vector(second_hour):
            assert areas[first_hour].exact == areas[second_hour].exact
    # SYN-N-0-1 is an invented point; no real place is attributed a speed.
    assert Polygon([(lon, lat) for lat, lon in free.exact]).contains(Point(0.01, 0))
    assert not Polygon([(lon, lat) for lat, lon in peak.exact]).contains(Point(0.01, 0))
    first = traffic.area("SYN-N-0-0", 3, 11, frame)
    with patch.object(
        engine.subprocess,
        "run",
        side_effect=AssertionError("Rebuilt identical speed vector"),
    ):
        assert traffic.area("SYN-N-0-0", 3, 12, frame) == first
    walks = [
        traffic.area("SYN-N-0-0", 3, hour, frame, mode="walk") for hour in range(24)
    ]
    assert all(area.caveat is None for area in walks)
    assert all(area == walks[0] for area in walks)
    assert all(set(area.cells) <= set(frame) for area in (free, quiet, peak, evening))


def test_exact_rounding_and_released_floor():
    from fractions import Fraction

    from eii_product.areas_spike.traffic import engine_speed

    # F4: the adapter rounds only; the method owns the floor.
    assert engine_speed(Fraction("0.1")) == 0
    assert engine_speed(Fraction("9.5")) == 10
    assert engine_speed(Fraction("10")) == 10
    assert engine_speed(Fraction("34.5")) == 35
    assert engine_speed(Fraction("34.49")) == 34
    assert min(load_hourly().speed_vector(8)) == 10
