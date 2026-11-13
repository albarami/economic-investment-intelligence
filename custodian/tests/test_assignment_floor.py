"""Owner's F1-F3 floor rule, with hand-written C25 expectations."""

import json
from fractions import Fraction as F
from pathlib import Path

import pytest

from eii_custodian.assignment_spike.delay import delay_factor
from eii_custodian.assignment_spike.params import CLASSES, parse_parameters
from eii_custodian.assignment_spike.run import calculate

FIXTURES = Path(__file__).parent / "fixtures" / "assignment_spike"


def parameters():
    return json.loads((FIXTURES / "worked_parameters.json").read_text())


def high_hour(tmp_path, params=None):
    flows = json.loads((FIXTURES / "worked_flows.json").read_text())
    flows["rows"] = [{**flows["rows"][0], "hour": 9, "estimate": "3000"}]
    flow_path = tmp_path / "flows.json"
    flow_path.write_text(json.dumps(flows))
    parameter_path = tmp_path / "parameters.json"
    parameter_path.write_text(json.dumps(parameters() if params is None else params))
    return calculate(flow_path, FIXTURES / "worked_roads.json", parameter_path)


def test_worked_floor_fixture(tmp_path):
    # F3: factor 10, unfloored speed 6; floor 10, time 60, ratio 0.167.
    result = high_hour(tmp_path)
    (row,) = result.calculations
    assert delay_factor(F(3000), F(1000), parse_parameters(parameters())) == F(10)
    assert row.volume == F(3000)
    assert row.speed_kph == F(10)
    assert row.minutes == F(60)
    assert row.speed_ratio == "0.167"
    assert row.volume_band == "vb3"
    assert result.shortest_minutes("SYN-N-0-0", "SYN-N-0-2", "weekday", 9, False) == (
        F(12),
        ("SYN-N-0-0", "SYN-N-1-1", "SYN-N-0-2"),
    )


def test_floor_parameter_changes_exact_result(tmp_path):
    params = parameters()
    params["speed_floor_kph"]["value"] = "12"
    (row,) = high_hour(tmp_path, params).calculations
    assert (row.speed_kph, row.minutes, row.speed_ratio, row.volume_band) == (
        F(12),
        F(50),
        "0.200",
        "vb3",
    )


@pytest.mark.parametrize("value", ["0", "-1", "10.5", 10, True])
def test_floor_must_be_positive_whole_decimal_text(value):
    params = parameters()
    params["speed_floor_kph"]["value"] = value
    with pytest.raises(ValueError, match="speed_floor_kph"):
        parse_parameters(params)


def test_floor_is_required():
    params = parameters()
    params.pop("speed_floor_kph", None)
    with pytest.raises(ValueError, match="speed_floor_kph"):
        parse_parameters(params)


@pytest.mark.parametrize("road_class", sorted(CLASSES))
def test_class_speed_cannot_be_below_floor(road_class):
    params = parameters()
    params["speeds"][road_class]["value"] = "9"
    with pytest.raises(ValueError, match="speeds." + road_class + ".*speed_floor_kph"):
        parse_parameters(params)


def test_class_speed_can_equal_floor():
    params = parameters()
    params["speeds"]["secondary"]["value"] = "10"
    assert parse_parameters(params).speeds["secondary"] == F(10)


@pytest.mark.parametrize("estimate", ["25000", "50000"])
def test_high_volume_keeps_positive_floored_ratio(tmp_path, estimate):
    flows = json.loads((FIXTURES / "worked_flows.json").read_text())
    flows["rows"] = [{**flows["rows"][0], "estimate": estimate}]
    path = tmp_path / "flows.json"
    path.write_text(json.dumps(flows))
    (row,) = calculate(
        path, FIXTURES / "worked_roads.json", FIXTURES / "worked_parameters.json"
    ).calculations
    assert (row.speed_kph, row.minutes, row.speed_ratio) == (F(10), F(60), "0.167")


def test_volume_band_uses_volume_not_speed_implied_volume(tmp_path):
    params = parameters()
    params["band_edges"][1]["value"] = "2.5"
    (row,) = high_hour(tmp_path, params).calculations
    assert (row.volume_band, row.speed_kph, row.minutes, row.speed_ratio) == (
        "vb3",
        F(10),
        F(60),
        "0.167",
    )


def test_parameter_provenance_words():
    assert (
        parameters()["speed_floor_kph"]["status"]
        == "invented method-card fixture, equal to the version-1 value"
    )
    params = json.loads((FIXTURES / "parameters_v1.json").read_text())
    for entry in params["speeds"].values():
        assert entry["status"].startswith("ASSUMPTION: not measured for Qatar;")
