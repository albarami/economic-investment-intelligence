"""The product's one link speed and exact link time, from released rows only."""

import json
from fractions import Fraction as F
from pathlib import Path
from unittest.mock import patch

import pytest

from eii_product.areas_spike.traffic import Traffic, engine_speed

FIXTURES = Path(__file__).parent / "fixtures" / "areas_spike" / "assignment"


def load():
    return Traffic.load(
        FIXTURES / "worked_rows.json",
        FIXTURES / "worked_roads.json",
        FIXTURES / "worked_parameters.json",
    )


def test_released_floor_violation_names_file_and_link(tmp_path):
    payload = json.loads((FIXTURES / "hourly_rows.json").read_text())
    row = next(
        row
        for row in payload["rows"]
        if row["link_id"] == "SYN-L-003" and row["hour"] == 8
    )
    row["speed_ratio"] = "0.100"
    path = tmp_path / "broken_rows.json"
    path.write_text(json.dumps(payload))
    with pytest.raises(
        ValueError,
        match=r"^broken_rows.json: released speed floor violated by SYN-L-003$",
    ):
        Traffic.load(
            path, FIXTURES / "hourly_roads.json", FIXTURES / "hourly_parameters.json"
        )


def test_rounding_does_not_raise_speed_to_floor():
    assert engine_speed(F("0.1")) == 0
    assert engine_speed(F("9.49")) == 9
    assert engine_speed(F("9.5")) == 10
    assert engine_speed(F("34.5")) == 35
    assert engine_speed(F("34.49")) == 34


def test_one_link_speed_and_exact_time():
    traffic = load()
    assert traffic.link_speed("SYN-L-001", 8) == 48
    assert traffic.link_minutes("SYN-L-001", 8) == F("12.5")
    assert traffic.link_speed("SYN-L-001", 9) == 10
    assert traffic.link_minutes("SYN-L-001", 9) == F(60)
    assert traffic.link_speed("SYN-L-001", None) == 60
    assert traffic.link_minutes("SYN-L-001", None) == F(10)
    # An absent row means free flow, even at a stored hour.
    assert traffic.link_speed("SYN-L-002", 8) == 60
    assert traffic.link_minutes("SYN-L-002", 8) == F(6)


def test_tiles_and_link_time_use_link_speed():
    traffic = load()
    with patch.object(Traffic, "link_speed", return_value=12) as speed:
        assert traffic.speed_vector(8) == (12, 12, 12)
        assert traffic.link_minutes("SYN-L-001", 8) == F(50)
    assert speed.call_count == 4


def test_route_exposes_product_link_times():
    traffic = load()
    route = traffic.route("SYN-N-0-0", "SYN-N-0-2", 8)
    assert route["link_ids"] == ("SYN-L-002", "SYN-L-003")
    assert route["minutes"] == F(12)
    with patch.object(Traffic, "link_minutes", wraps=traffic.link_minutes) as minutes:
        assert traffic.route("SYN-N-0-0", "SYN-N-0-2", 8)["minutes"] == F(12)
    assert minutes.call_count == 2


def test_route_counts_links_merged_into_one_maneuver():
    traffic = Traffic.load(
        FIXTURES / "hourly_rows.json",
        FIXTURES / "hourly_roads.json",
        FIXTURES / "hourly_parameters.json",
    )
    route = traffic.route("SYN-N-0-2", "SYN-N-0-0", 0)
    assert route["link_ids"] == ("SYN-L-004", "SYN-L-002")
    # Link sum: 1113 * 60 / 1000 * (1/60 + 1/35); L-84 adds the measured turn.
    assert sum(route["link_minutes"], F(0)) == F(3021, 1000)
    assert route["junction_seconds"] == F("0.017")
    assert route["minutes"] == F(3021, 1000) + F("0.017") / 60


@pytest.mark.parametrize("hour", ["8", 8.0, True, False, -1, 24])
def test_link_functions_refuse_invalid_hour(hour):
    traffic = load()
    for function in (traffic.link_speed, traffic.link_minutes):
        with pytest.raises(ValueError, match="Unknown day_type, hour or summer"):
            function("SYN-L-001", hour)


def test_route_uses_requested_hour_for_link_times():
    traffic = Traffic.load(
        FIXTURES / "hourly_rows.json",
        FIXTURES / "hourly_roads.json",
        FIXTURES / "hourly_parameters.json",
    )
    peak = traffic.route("SYN-N-0-0", "SYN-N-0-1", 8)
    free = traffic.route("SYN-N-0-0", "SYN-N-0-1", None)
    assert peak["link_ids"] == ("SYN-L-001",)
    assert peak["minutes"] == traffic.link_minutes("SYN-L-001", 8)
    assert peak["minutes"] > free["minutes"]


def test_link_speed_uses_its_own_road_class():
    traffic = Traffic.load(
        FIXTURES / "hourly_rows.json",
        FIXTURES / "hourly_roads.json",
        FIXTURES / "hourly_parameters.json",
    )
    assert traffic.link_speed("SYN-L-001", None) == 35
    assert traffic.link_speed("SYN-L-003", None) == 60
    assert traffic.link_speed("SYN-L-003", 8) == 23


def test_link_minutes_preserves_summer_lookup():
    from dataclasses import replace

    traffic = load()
    traffic = replace(
        traffic,
        rows=(
            *traffic.rows,
            {**traffic.rows[0], "summer": True, "speed_ratio": "0.500"},
        ),
    )
    assert traffic.link_minutes("SYN-L-001", 8, "weekday", True) == F(20)
    assert traffic.link_minutes("SYN-L-001", 8, "weekday", False) == F("12.5")
