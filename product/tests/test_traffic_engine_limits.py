"""Installed-engine observations required by R10; no source downloads."""

import copy
import json
from pathlib import Path

import pytest

from eii_product.areas_spike.engine import scaled_actor
from eii_product.areas_spike.traffic import Traffic

FIXTURES = Path(__file__).parent / "fixtures" / "areas_spike" / "assignment"


def observed_speed(road_class, posted):
    traffic = Traffic.load(
        FIXTURES / "hourly_rows.json",
        FIXTURES / "hourly_roads.json",
        FIXTURES / "hourly_parameters.json",
    )
    road = copy.deepcopy(traffic.road_fixture(traffic.speed_vector(None), "SYN-N-0-0"))
    road["edges"] = road["edges"][:1]
    road["edges"][0].update(road_class=road_class, posted_speed=posted)
    actor, _temporary = scaled_actor(json.dumps(road, sort_keys=True), 1.0)
    result = actor.locate({"locations": [{"lat": 0, "lon": 0.005}], "verbose": True})
    speed = result[0]["edges"][0]["edge"]["speeds"]["default"]
    print(
        json.dumps(
            {"road_class": road_class, "posted": posted, "stored_speed_kph": speed},
            sort_keys=True,
        )
    )
    return speed


@pytest.mark.parametrize(
    "posted,expected", [("9", 35), ("10", 10), ("141", 140), ("255", 35), ("35.5", 35)]
)
def test_installed_speed_limits(posted, expected):
    # L-62: documentation suggested 255 -> 140; installed engine uses default 35.
    # Earlier expectation 35.5 -> 36 was wrong: installed engine truncates to 35.
    speed = observed_speed("residential", posted)
    assert isinstance(speed, int)
    assert speed == expected


@pytest.mark.parametrize(
    "road_class,expected",
    [
        ("motorway", 105),
        ("trunk", 90),
        ("primary", 75),
        ("secondary", 60),
        ("tertiary", 50),
        ("residential", 35),
    ],
)
def test_installed_default_by_road_class(road_class, expected):
    assert observed_speed(road_class, None) == expected
