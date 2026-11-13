"""Closed schemas and planted invalid inputs for the assignment."""

import json
from pathlib import Path

import pytest

from eii_custodian.assignment_spike.inputs import parse_flows, parse_roads
from eii_custodian.assignment_spike.params import parse_parameters

FIXTURES = Path(__file__).parent / "fixtures" / "assignment_spike"


def read(name):
    return json.loads((FIXTURES / name).read_text())


@pytest.mark.parametrize(
    "key", ["alpha", "beta", "speeds", "capacities", "band_count", "band_edges"]
)
@pytest.mark.parametrize("operation", ["missing", "unknown"])
def test_parameter_keys_closed(key, operation):
    params = read("parameters_v1.json")
    if operation == "missing":
        del params[key]
    else:
        params[f"{key}_unknown"] = params[key]
    with pytest.raises(ValueError, match=key):
        parse_parameters(params)


@pytest.mark.parametrize("field", ["source", "read", "status", "unit", "value"])
@pytest.mark.parametrize("operation", ["missing", "empty"])
def test_parameter_metadata_required(field, operation):
    params = read("parameters_v1.json")
    if operation == "missing":
        del params["alpha"][field]
    else:
        params["alpha"][field] = ""
    with pytest.raises(ValueError, match="alpha"):
        parse_parameters(params)


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("alpha", "0"),
        ("alpha", "-1"),
        ("alpha", 0.15),
        ("alpha", "NaN"),
        ("alpha", "1/2"),
        ("beta", "1.5"),
        ("beta", "0"),
        ("band_count", "2.5"),
    ],
)
def test_bad_numeric_parameter(key, value):
    params = read("parameters_v1.json")
    params[key]["value"] = value
    with pytest.raises(ValueError, match=key):
        parse_parameters(params)


@pytest.mark.parametrize("section", ["speeds", "capacities"])
@pytest.mark.parametrize("operation", ["missing", "unknown", "zero"])
def test_road_class_parameters(section, operation):
    params = read("parameters_v1.json")
    if operation == "missing":
        del params[section]["motorway"]
    elif operation == "unknown":
        params[section]["footway"] = params[section]["motorway"]
    else:
        params[section]["motorway"]["value"] = "0"
    with pytest.raises(ValueError, match=section):
        parse_parameters(params)


@pytest.mark.parametrize(
    "edges",
    [["0.95", "0.85", "1"], ["0.85", "0.85", "1"], ["0", "0.95", "1"], ["0.85"]],
)
def test_band_configuration_refused(edges):
    params = read("parameters_v1.json")
    params["band_edges"] = [
        {**params["band_edges"][0], "value": value} for value in edges
    ]
    with pytest.raises(ValueError, match="band_edges"):
        parse_parameters(params)


@pytest.mark.parametrize(
    "field",
    ["origin_unit_id", "destination_unit_id", "day_type", "hour", "summer", "estimate"],
)
@pytest.mark.parametrize("operation", ["missing", "unknown"])
def test_flow_rows_closed(field, operation):
    flows = read("worked_flows.json")
    if operation == "missing":
        del flows["rows"][0][field]
    else:
        flows["rows"][0][field + "_extra"] = "invented"
    with pytest.raises(ValueError, match=field):
        parse_flows(flows, parse_roads(read("worked_roads.json")))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("hour", "-1"),
        ("hour", "24"),
        ("hour", "1.5"),
        ("hour", "8"),
        ("estimate", "-1"),
        ("estimate", 500),
        ("day_type", "weekend"),
        ("summer", True),
        ("summer", 0),
        ("origin_unit_id", "SYN-U-99"),
        ("destination_unit_id", "SYN-U-99"),
    ],
)
def test_flow_values_refused(field, value):
    flows = read("worked_flows.json")
    flows["rows"][0][field] = value
    with pytest.raises(ValueError):
        parse_flows(flows, parse_roads(read("worked_roads.json")))


def test_wrong_flow_unit_returns_no_data():
    flows = read("worked_flows.json")
    flows["unit"] = "people per hour"
    with pytest.raises(ValueError, match="NO_DATA: flow_unit_not_vehicle_trips"):
        parse_flows(flows, parse_roads(read("worked_roads.json")))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("road_class", "footway"),
        ("length_m", "0"),
        ("length_m", "-1"),
        ("length_m", 10000),
        ("source", "SYN-N-9-9"),
        ("target", "SYN-N-9-9"),
    ],
)
def test_road_values_refused(field, value):
    roads = read("worked_roads.json")
    roads["links"][0][field] = value
    with pytest.raises(ValueError):
        parse_roads(roads)


def test_parameter_object_and_date():
    with pytest.raises(ValueError, match="parameters"):
        parse_parameters([])
    params = read("parameters_v1.json")
    params["alpha"]["read"] = "invented"
    with pytest.raises(ValueError, match=r"alpha\.read"):
        parse_parameters(params)
