"""Independent cases for the surviving package-only mutation probes (L-84)."""

import json
from dataclasses import replace
from fractions import Fraction as F
from math import atan2, cos, hypot, radians, sin
from pathlib import Path

import pytest

from eii_custodian.assignment_spike.__main__ import main
from eii_custodian.assignment_spike.assign import volumes
from eii_custodian.assignment_spike.delay import (
    length_weighted_slowdown,
    situation_mean,
)
from eii_custodian.assignment_spike.inputs import (
    Flow,
    Link,
    Roads,
    parse_flows,
    parse_roads,
)
from eii_custodian.assignment_spike.params import parse_parameters
from eii_custodian.assignment_spike.paths import shortest, spherical_distance
from eii_custodian.assignment_spike.run import calculate

FIXTURES = Path(__file__).parent / "fixtures/assignment_spike"


def read(name):
    return json.loads((FIXTURES / name).read_text())


def test_cli_usage_is_stderr(capsys):
    assert main([]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "Expected flows roads parameters output\n"


@pytest.mark.parametrize(
    "field,value,code,message",
    [
        ("unit", "people per hour", 3, "NO_DATA: flow_unit_not_vehicle_trips"),
        ("rows", None, 1, "flows: missing or unknown fields ['rows']"),
    ],
)
def test_cli_error_exit_and_stderr(tmp_path, capsys, field, value, code, message):
    flows = read("worked_flows.json")
    if value is None:
        del flows[field]
    else:
        flows[field] = value
    path = tmp_path / "flows.json"
    path.write_text(json.dumps(flows))
    output = tmp_path / "rows.json"
    assert (
        main(
            [
                str(path),
                str(FIXTURES / "worked_roads.json"),
                str(FIXTURES / "worked_parameters.json"),
                str(output),
            ]
        )
        == code
    )
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == message + "\n"
    assert not output.exists()


def test_one_trip_after_within_unit_flow_is_retained():
    roads = parse_roads(read("worked_roads.json"))
    params = parse_parameters(read("worked_parameters.json"))
    flows = (
        Flow("SYN-U-01", "SYN-U-01", "weekday", 8, False, F(1)),
        Flow("SYN-U-01", "SYN-U-02", "weekday", 8, False, F(1)),
    )
    assert volumes(roads, flows, params) == {("SYN-L-001", "weekday", 8, False): F(1)}


def test_subunit_length_slowdown_and_empty_messages():
    assert length_weighted_slowdown(((F("0.5"), F("0.5")),)) == "0.500"
    with pytest.raises(ValueError) as error:
        situation_mean(())
    assert str(error.value) == "NO_DATA: empty situation"
    with pytest.raises(ValueError) as error:
        length_weighted_slowdown(())
    assert str(error.value) == "NO_DATA: no road length"


@pytest.mark.parametrize(
    "section,field,label",
    [
        ("nodes", "lat", "lat"),
        ("nodes", "lon", "lon"),
        ("units", "lat", "lat"),
        ("units", "lon", "lon"),
        ("links", "length_m", "length_m"),
    ],
)
def test_road_decimal_error_names_exact_field(section, field, label):
    roads = read("worked_roads.json")
    roads[section][0][field] = "invalid"
    with pytest.raises(ValueError) as error:
        parse_roads(roads)
    assert str(error.value) == label + ": expected decimal text"


@pytest.mark.parametrize(
    "section,label", [("nodes", "node"), ("links", "link"), ("units", "unit")]
)
def test_road_object_error_names_exact_section(section, label):
    roads = read("worked_roads.json")
    roads[section][0]["unexpected"] = "invented"
    with pytest.raises(ValueError) as error:
        parse_roads(roads)
    assert str(error.value) == label + ": missing or unknown fields ['unexpected']"
    roads = read("worked_roads.json")
    roads[section].append(roads[section][0])
    with pytest.raises(ValueError) as error:
        parse_roads(roads)
    assert str(error.value) == label + ": duplicate identifier"


@pytest.mark.parametrize(
    "field,value,message",
    [
        ("road_class", "footway", "road_class: unknown class"),
        ("length_m", "0", "length_m: must be positive"),
        ("source", "SYN-N-missing", "link: unknown node"),
    ],
)
def test_road_value_error_names_exact_field(field, value, message):
    roads = read("worked_roads.json")
    roads["links"][0][field] = value
    with pytest.raises(ValueError) as error:
        parse_roads(roads)
    assert str(error.value) == message


def test_roads_schema_empty_and_positive_small_length():
    roads = read("worked_roads.json")
    roads["links"][0]["length_m"] = "0.5"
    with pytest.raises(
        ValueError, match=r"^length_m: must be a whole number of metres$"
    ):
        parse_roads(roads)
    roads["links"][0]["length_m"] = "1"
    assert parse_roads(roads).links[0].length_m == F(1)
    with pytest.raises(ValueError) as error:
        parse_roads({**roads, "extra": "invented"})
    assert str(error.value) == "roads: missing or unknown fields ['extra']"
    with pytest.raises(ValueError) as error:
        parse_roads({**roads, "links": []})
    assert str(error.value) == "roads: empty graph"


@pytest.mark.parametrize(
    "field,value,message",
    [
        ("hour", -1, "hour: outside stored day"),
        ("day_type", "weekend", "flow: fixture requires weekday and summer false"),
        ("origin_unit_id", "SYN-U-missing", "flow: unknown unit"),
        ("estimate", "invalid", "estimate: expected decimal text"),
        ("estimate", "-1", "estimate: must be a nonnegative whole count"),
    ],
)
def test_flow_error_names_exact_field(field, value, message):
    flows = read("worked_flows.json")
    flows["rows"][0][field] = value
    with pytest.raises(ValueError) as error:
        parse_flows(flows, parse_roads(read("worked_roads.json")))
    assert str(error.value) == message


def test_flow_schema_unit_and_duplicate_messages():
    roads = parse_roads(read("worked_roads.json"))
    flows = read("worked_flows.json")
    with pytest.raises(ValueError) as error:
        parse_flows({**flows, "extra": "invented"}, roads)
    assert str(error.value) == "flows: missing or unknown fields ['extra']"
    with pytest.raises(ValueError) as error:
        parse_flows({**flows, "unit": "people per hour"}, roads)
    assert str(error.value) == "NO_DATA: flow_unit_not_vehicle_trips"
    flows["rows"][0]["extra"] = "invented"
    with pytest.raises(ValueError) as error:
        parse_flows(flows, roads)
    assert str(error.value) == "flow: missing or unknown fields ['extra']"
    del flows["rows"][0]["extra"]
    flows["rows"].append(flows["rows"][0])
    with pytest.raises(ValueError) as error:
        parse_flows(flows, roads)
    assert str(error.value) == "flow: duplicate key"


@pytest.mark.parametrize(
    "field,message",
    [
        ("speed_floor_kph", "speed_floor_kph: must be a positive whole number"),
        ("beta", "beta: must be a positive whole number"),
        ("band_count", "band_count: must be a whole number"),
    ],
)
def test_parameter_integer_messages(field, message):
    params = read("parameters_v1.json")
    params[field]["value"] = "10.5"
    with pytest.raises(ValueError) as error:
        parse_parameters(params)
    assert str(error.value) == message


@pytest.mark.parametrize("field", ["speed_floor_kph", "beta", "band_count"])
def test_parameter_decimal_messages(field):
    params = read("parameters_v1.json")
    params[field]["value"] = "invalid"
    with pytest.raises(ValueError) as error:
        parse_parameters(params)
    assert str(error.value) == field + ": expected decimal text"


@pytest.mark.parametrize("section", [None, "speeds", "capacities"])
def test_parameter_schema_error_names(section):
    params = read("parameters_v1.json")
    target = params if section is None else params[section]
    target["extra"] = "invented"
    with pytest.raises(ValueError) as error:
        parse_parameters(params)
    assert (
        str(error.value)
        == (section or "parameters") + ": missing or unknown fields ['extra']"
    )


def test_band_configuration_messages_and_returned_count():
    params = read("parameters_v1.json")
    assert parse_parameters(params).band_count == 4
    params["band_edges"] = []
    with pytest.raises(ValueError) as error:
        parse_parameters(params)
    assert str(error.value) == "band_edges: must match band_count"
    params = read("parameters_v1.json")
    params["band_edges"].reverse()
    with pytest.raises(ValueError) as error:
        parse_parameters(params)
    assert str(error.value) == "band_edges: must be strictly increasing"


def test_spherical_distance_against_independent_atan2_formula():
    pairs = [(F(25), F(10), F(35), F(30))]
    for offset in ("0.00001", "0.0001", "0.001", "0.003", "0.01", "0.05", "0.2"):
        pairs.append((F("25.3"), F(0), F("25.3") + F(offset), F(offset)))
    for name in ("worked_roads.json", "hourly_roads.json"):
        roads = parse_roads(read(name))
        pairs.extend(
            (lat, lon, node.lat, node.lon)
            for lat, lon in roads.units.values()
            for node in roads.nodes
        )
    for lat, lon, other_lat, other_lon in pairs:
        a, b, delta = (
            radians(float(lat)),
            radians(float(other_lat)),
            radians(float(other_lon - lon)),
        )
        expected = 6371008.8 * atan2(
            hypot(cos(b) * sin(delta), cos(a) * sin(b) - sin(a) * cos(b) * cos(delta)),
            sin(a) * sin(b) + cos(a) * cos(b) * cos(delta),
        )
        # Method card: checked against an independent formula within 0.0000001 metres
        # at loading distances (floating-point evaluation only).
        assert spherical_distance(lat, lon, other_lat, other_lon) == pytest.approx(
            expected, rel=0, abs=1e-7
        )


def test_shortest_continues_after_duplicate_queue_entry():
    roads = parse_roads(read("worked_roads.json"))
    links = (
        Link("SYN-L-A", "SYN-N-A", "SYN-N-B", F(1), "secondary"),
        Link("SYN-L-B", "SYN-N-A", "SYN-N-C", F(1), "secondary"),
        Link("SYN-L-C", "SYN-N-C", "SYN-N-B", F(1), "secondary"),
        Link("SYN-L-D", "SYN-N-B", "SYN-N-D", F(1), "secondary"),
    )
    roads = replace(roads, links=links)
    times = dict(zip((link.id for link in links), map(F, (3, 1, 1, 10)), strict=True))
    assert shortest(roads, times, "SYN-N-A", "SYN-N-D") == (
        F(12),
        ("SYN-N-A", "SYN-N-C", "SYN-N-B", "SYN-N-D"),
        ("SYN-L-B", "SYN-L-C", "SYN-L-D"),
    )


def test_shortest_disconnected_cycle_visits_each_node_once(monkeypatch):
    from eii_custodian.assignment_spike import paths

    links = (
        Link("SYN-L-A", "SYN-N-A", "SYN-N-B", F(1), "secondary"),
        Link("SYN-L-B", "SYN-N-B", "SYN-N-A", F(1), "secondary"),
    )
    roads = Roads((), links, {})
    pop = paths.heappop
    calls = []

    def counted(queue):
        calls.append(None)
        assert len(calls) <= 2, "cycle must terminate after visiting its two nodes"
        return pop(queue)

    # Wrap the real heap operation so a broken visited set fails without hanging.
    monkeypatch.setattr(paths, "heappop", counted)
    with pytest.raises(ValueError) as error:
        shortest(roads, {link.id: F(1) for link in links}, "SYN-N-A", "SYN-N-missing")
    assert str(error.value) == "NO_DATA: disconnected origin and destination"


def test_method_header_closed_identifier():
    result = calculate(
        *(
            FIXTURES / name
            for name in (
                "worked_flows.json",
                "worked_roads.json",
                "worked_parameters.json",
            )
        )
    )
    method = result.payload["header"]["method"]
    assert set(method) == {"id", "parameters_sha256"}
    assert method["id"] == "C25"
