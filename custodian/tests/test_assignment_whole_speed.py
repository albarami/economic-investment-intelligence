"""L-74 R1, R2 and R8: exact independently calculated expectations."""

import json
from fractions import Fraction as F
from pathlib import Path

import pytest

from eii_custodian.assignment_spike.inputs import parse_roads
from eii_custodian.assignment_spike.params import parse_parameters
from eii_custodian.assignment_spike.paths import loading_nodes
from eii_custodian.assignment_spike.run import calculate

FIXTURES = Path(__file__).parent / "fixtures" / "assignment_spike"


def test_method_rounds_before_time_and_ratio():
    result = calculate(
        FIXTURES / "hourly_flows.json",
        FIXTURES / "hourly_roads.json",
        FIXTURES / "parameters_v1.json",
    )
    parameters = parse_parameters(
        json.loads((FIXTURES / "parameters_v1.json").read_text())
    )
    links = {link.id: link for link in result.roads.links}
    for row in result.calculations:
        link = links[row.link_id]
        free = parameters.speeds[link.road_class]
        x = free / (
            1
            + parameters.alpha
            * (row.volume / parameters.capacities[link.road_class]) ** parameters.beta
        )
        whole = max(parameters.speed_floor_kph, (x + F(1, 2)) // 1)
        assert row.speed_kph == whole
        assert row.minutes == link.length_m * F(3, 50) / whole
        assert F(row.speed_ratio) == F((whole / free * 1000 + F(1, 2)) // 1, 1000)


@pytest.mark.parametrize(
    "field,value,message",
    [
        ("speed", "35.5", r"speeds.residential:.*whole"),
        ("speed", "141", r"speeds.residential:.*140"),
        ("floor", "9", r"speed_floor_kph:.*10"),
    ],
)
def test_engine_parameter_limits(field, value, message):
    params = json.loads((FIXTURES / "worked_parameters.json").read_text())
    target = (
        params["speeds"]["residential"]
        if field == "speed"
        else params["speed_floor_kph"]
    )
    target["value"] = value
    with pytest.raises(ValueError, match=message):
        parse_parameters(params)


def test_loading_uses_spherical_distance_not_degrees():
    roads = parse_roads(
        {
            "note": "Invented points; no real place.",
            "nodes": [
                {"id": "SYN-N-A", "lat": "25.01", "lon": "0"},
                {"id": "SYN-N-B", "lat": "25", "lon": "0.0105"},
            ],
            "links": [
                {
                    "link_id": "SYN-L-001",
                    "source": "SYN-N-A",
                    "target": "SYN-N-B",
                    "length_m": "1000",
                    "road_class": "secondary",
                }
            ],
            "units": [{"unit_id": "SYN-U-01", "lat": "25", "lon": "0"}],
        }
    )
    assert loading_nodes(roads) == {"SYN-U-01": "SYN-N-B"}


def test_maximum_free_speed_is_accepted():
    params = json.loads((FIXTURES / "worked_parameters.json").read_text())
    params["speeds"]["secondary"]["value"] = "140"
    assert parse_parameters(params).speeds["secondary"] == 140


def test_whole_speed_half_up_boundaries():
    from eii_custodian.assignment_spike.delay import whole_speed

    assert whole_speed(F("10.499")) == 10
    assert whole_speed(F("10.5")) == 11
    assert whole_speed(F("11.5")) == 12
