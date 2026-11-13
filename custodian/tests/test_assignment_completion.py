"""Discriminating C25 fixtures and named refusals from completion rulings."""

import copy
import json
import subprocess
import sys
from dataclasses import replace
from fractions import Fraction as F
from pathlib import Path
from unittest.mock import patch

import pytest

from eii_custodian.assignment_spike.assign import free_times, volumes
from eii_custodian.assignment_spike.delay import rounded_ratio, volume_band
from eii_custodian.assignment_spike.inputs import parse_flows, parse_roads
from eii_custodian.assignment_spike.params import parse_parameters
from eii_custodian.assignment_spike.paths import loading_nodes, shortest
from eii_custodian.assignment_spike.run import calculate

FIXTURES = Path(__file__).parent / "fixtures" / "assignment_spike"


def read(name):
    data = json.loads((FIXTURES / name).read_text())
    if name == "worked_flows.json":
        # Each rule fixture changes the original single-hour example only.
        data["rows"] = data["rows"][:1]
    return data


def flows():
    data = read("worked_flows.json")
    data["rows"][0]["hour"] = 8
    return data


def run_files(tmp_path, flow=None, road=None, parameters=None):
    paths = []
    for name, data in [
        ("flows.json", flows() if flow is None else flow),
        ("roads.json", read("worked_roads.json") if road is None else road),
        (
            "parameters.json",
            read("worked_parameters.json") if parameters is None else parameters,
        ),
    ]:
        path = tmp_path / name
        path.write_text(json.dumps(data))
        paths.append(path)
    return paths


def branched(lengths=("1000", "2000", "1000", "1000")):
    # After the common first hop, the smallest node path has more hops AND larger link ids.
    data = read("worked_roads.json")
    data["nodes"] = [
        {"id": f"SYN-N-0-{n}", "lat": "0", "lon": str(n)} for n in (0, 1, 2, 4)
    ]
    data["links"] = [
        {
            "link_id": key,
            "source": f"SYN-N-0-{a}",
            "target": f"SYN-N-0-{b}",
            "length_m": length,
            "road_class": "secondary",
        }
        for key, a, b, length in zip(
            ("SYN-L-001", "SYN-L-002", "SYN-L-009", "SYN-L-010"),
            (0, 1, 1, 2),
            (1, 4, 2, 4),
            lengths,
            strict=True,
        )
    ]
    return parse_roads(data)


def test_late_path_tie_ignores_hops_link_ids_and_discovery_order():
    graph = branched()
    params = parse_parameters(read("worked_parameters.json"))
    assert shortest(graph, free_times(graph, params), "SYN-N-0-0", "SYN-N-0-4") == (
        F(3),
        ("SYN-N-0-0", "SYN-N-0-1", "SYN-N-0-2", "SYN-N-0-4"),
        ("SYN-L-001", "SYN-L-009", "SYN-L-010"),
    )


def test_fractional_path_tie_not_float_sum():
    graph = branched(("100", "300", "100", "200"))
    params = parse_parameters(read("worked_parameters.json"))
    answer = shortest(graph, free_times(graph, params), "SYN-N-0-1", "SYN-N-0-4")
    assert answer == (
        F("0.3"),
        ("SYN-N-0-1", "SYN-N-0-2", "SYN-N-0-4"),
        ("SYN-L-009", "SYN-L-010"),
    )


def test_nearest_tie_requires_exact_arithmetic_and_text_order():
    data = read("worked_roads.json")
    # Exact squared distances both 0.01; binary .3-.2 differs from .3-.4.
    names = ("SYN-N-0-9", "SYN-N-0-10", "SYN-N-1-1")
    for node, name, lon in zip(data["nodes"], names, ("0.2", "0.4", "1"), strict=True):
        node.update(id=name, lat="0", lon=lon)
    data["links"] = [
        {
            "link_id": "SYN-L-001",
            "source": names[0],
            "target": names[1],
            "length_m": "100",
            "road_class": "secondary",
        }
    ]
    data["units"][0].update(lat="0", lon="0.3")
    assert loading_nodes(parse_roads(data))["SYN-U-01"] == "SYN-N-0-10"


def test_distinct_pairs_sum_on_shared_link(tmp_path):
    data = flows()
    data["rows"].append(
        {**data["rows"][0], "origin_unit_id": "SYN-U-03", "estimate": "250"}
    )
    roads = read("worked_roads.json")
    roads["links"][0]["length_m"] = "20000"  # Both pairs use M to D.
    result = calculate(*run_files(tmp_path, data, roads))
    shared = next(row for row in result.calculations if row.link_id == "SYN-L-003")
    # 500 + 250 = 750; exact speed 192/5 rounds to 38; 360/38 minutes.
    assert shared.volume == F(750)
    assert shared.minutes == F(180, 19)
    assert shared.speed_kph == F(38)
    assert shared.speed_ratio == "0.633"
    assert shared.volume_band == "vb3"


def test_band_uses_unrounded_volume_capacity(tmp_path):
    data, params = flows(), read("worked_parameters.json")
    data["rows"][0]["estimate"] = "999"
    params["capacities"]["secondary"]["value"] = "4000"
    row = calculate(*run_files(tmp_path, data, parameters=params)).calculations[0]
    assert row.volume_band == "vb1"
    assert row.minutes == F(75, 7)  # 600 / round_half_up(60 / (1 + (999/4000)^2))


def test_exact_decisions_one_part_in_ten_to_twenty():
    epsilon = F(1, 10**20)
    assert rounded_ratio(F("0.8125") - epsilon) == "0.812"
    assert rounded_ratio(F("0.8125")) == "0.813"
    params = parse_parameters(read("worked_parameters.json"))
    assert volume_band(F("0.25") - epsilon, params) == "vb1"
    assert volume_band(F("0.25"), params) == "vb2"


def test_band_count_changed_alone_refused():
    params = read("worked_parameters.json")
    params["band_count"]["value"] = "1"
    with pytest.raises(ValueError, match="band_count"):
        parse_parameters(params)


def test_loading_ignores_isolated_node():
    roads = read("worked_roads.json")
    roads["nodes"].append({"id": "SYN-N-0-1", "lat": "0", "lon": "0.001"})
    roads["units"][0].update(lat="0", lon="0.001")
    assert loading_nodes(parse_roads(roads))["SYN-U-01"] == "SYN-N-0-0"


def test_within_unit_never_calls_path_search():
    data = flows()
    data["rows"][0]["destination_unit_id"] = "SYN-U-01"
    graph = parse_roads(read("worked_roads.json"))
    with patch(
        "eii_custodian.assignment_spike.assign.shortest",
        side_effect=AssertionError("within-unit search"),
    ):
        assert (
            volumes(
                graph,
                parse_flows(data, graph),
                parse_parameters(read("worked_parameters.json")),
            )
            == {}
        )


def test_different_units_loading_same_node_have_no_rows(tmp_path):
    roads = read("worked_roads.json")
    roads["units"][1].update(lat="0", lon="0")
    assert calculate(*run_files(tmp_path, road=roads)).payload["rows"] == []


@pytest.mark.parametrize("hour", ["8", 8.0, 8.5, True, False, -1, 24])
def test_hour_is_json_integer_only(hour):
    data = flows()
    data["rows"][0]["hour"] = hour
    with pytest.raises(ValueError, match="hour"):
        parse_flows(data, parse_roads(read("worked_roads.json")))


def test_numeric_hour_order_and_all_shortest_situation_keys(tmp_path):
    data = flows()
    data["rows"] = [{**data["rows"][0], "hour": hour} for hour in (10, 2, 23, 0)]
    result = calculate(*run_files(tmp_path, data))
    assert [row["hour"] for row in result.payload["rows"]] == [0, 2, 10, 23]
    base = result.calculations[0]
    result = replace(
        result,
        calculations=(
            replace(base, hour=8, minutes=F(5)),
            replace(base, hour=8, day_type="weekend", minutes=F(7)),
            replace(base, hour=8, summer=True, minutes=F(9)),
            replace(base, hour=9, minutes=F(3)),
        ),
    )
    for day, hour, summer, expected in [
        ("weekday", 8, False, 5),
        ("weekend", 8, False, 7),
        ("weekday", 8, True, 9),
        ("weekday", 9, False, 3),
    ]:
        assert (
            result.shortest_minutes("SYN-N-0-0", "SYN-N-0-2", day, hour, summer)[0]
            == expected
        )


def test_duplicate_flow_key_refused():
    data = flows()
    data["rows"].append(copy.deepcopy(data["rows"][0]))
    with pytest.raises(ValueError, match=r"flow.*duplicate"):
        parse_flows(data, parse_roads(read("worked_roads.json")))


@pytest.mark.parametrize(
    "section,field", [("nodes", "node"), ("links", "link"), ("units", "unit")]
)
def test_duplicate_identifiers_refused(section, field):
    data = read("worked_roads.json")
    data[section].append(copy.deepcopy(data[section][0]))
    with pytest.raises(ValueError, match=field + ".*duplicate"):
        parse_roads(data)


@pytest.mark.parametrize("index,key", [(0, "hour"), (1, "lat"), (2, "value")])
def test_duplicate_json_keys_refused(tmp_path, index, key):
    paths = run_files(tmp_path)
    text = paths[index].read_text()
    # Duplicate the first selected key, including equal-valued duplicates.
    import re

    text = re.sub(
        r'("' + key + r'": ([^,}]+))', r'\1, "' + key + r'": \2', text, count=1
    )
    paths[index].write_text(text)
    with pytest.raises(ValueError, match="duplicate.*" + key):
        calculate(*paths)


def test_flow_count_is_whole():
    data = flows()
    data["rows"][0]["estimate"] = "500.5"
    with pytest.raises(ValueError, match="estimate"):
        parse_flows(data, parse_roads(read("worked_roads.json")))


@pytest.mark.parametrize("target", ["parameter", "road"])
def test_decimal_text_is_ascii_only(target):
    if target == "parameter":
        data = read("worked_parameters.json")
        data["alpha"]["value"] = "\u0661"
        with pytest.raises(ValueError, match="alpha"):
            parse_parameters(data)
    else:
        data = read("worked_roads.json")
        data["links"][0]["length_m"] = "\u0661"
        with pytest.raises(ValueError, match="length_m"):
            parse_roads(data)


@pytest.mark.parametrize(
    "key,value", [("beta", 4), ("beta", True), ("beta", "4.5"), ("band_count", "0")]
)
def test_remaining_parameter_numeric_refusals(key, value):
    data = read("worked_parameters.json")
    data[key]["value"] = value
    with pytest.raises(ValueError, match=key):
        parse_parameters(data)


@pytest.mark.parametrize("section", ["speed", "edge"])
@pytest.mark.parametrize("field", ["source", "read", "status"])
def test_nested_metadata_required(section, field):
    data = read("worked_parameters.json")
    entry = data["speeds"]["secondary"] if section == "speed" else data["band_edges"][0]
    del entry[field]
    with pytest.raises(
        ValueError,
        match=("speeds.secondary" if section == "speed" else "band_edges.0")
        + ".*"
        + field,
    ):
        parse_parameters(data)


@pytest.mark.parametrize(
    "section,key",
    [
        ("roads", "nodes"),
        ("node", "lat"),
        ("link", "source"),
        ("unit", "lat"),
        ("flows", "rows"),
    ],
)
@pytest.mark.parametrize("operation", ["missing", "unknown"])
def test_all_input_objects_closed(section, key, operation):
    data = flows() if section == "flows" else read("worked_roads.json")
    target = (
        data
        if section in {"roads", "flows"}
        else data[{"node": "nodes", "link": "links", "unit": "units"}[section]][0]
    )
    if operation == "missing":
        del target[key]
    else:
        target["unknown"] = "invented"
    with pytest.raises(ValueError, match=section):
        if section == "flows":
            parse_flows(data, parse_roads(read("worked_roads.json")))
        else:
            parse_roads(data)


@pytest.mark.parametrize("wrong_unit,expected", [(True, 3), (False, 1)])
def test_command_distinguishes_no_data_from_malformed(tmp_path, wrong_unit, expected):
    data = flows()
    if wrong_unit:
        data["unit"] = "people per hour"
    else:
        data["rows"][0]["estimate"] = "broken"
    paths = run_files(tmp_path, data)
    output = tmp_path / "rows.json"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "eii_custodian.assignment_spike",
            *map(str, paths),
            str(output),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == expected
    assert (
        "flow_unit_not_vehicle_trips" if wrong_unit else "estimate"
    ) in result.stderr
    assert not output.exists()


def test_version_one_third_band_edge_changes_exact_row(tmp_path):
    data, params = flows(), read("parameters_v1.json")
    data["rows"][0]["estimate"] = "1000"
    assert (
        calculate(*run_files(tmp_path, data, parameters=params))
        .calculations[0]
        .volume_band
        == "vb4"
    )
    params["band_edges"][2]["value"] = "1.01"
    assert (
        calculate(*run_files(tmp_path, data, parameters=params))
        .calculations[0]
        .volume_band
        == "vb3"
    )


def test_command_return_codes_and_output(tmp_path):
    from eii_custodian.assignment_spike.__main__ import main

    assert main([]) == 2
    paths = run_files(tmp_path)
    output = tmp_path / "rows.json"
    assert main([*map(str, paths), str(output)]) == 0
    assert output.read_bytes() == calculate(*paths).to_bytes()


def test_empty_graph_refused():
    data = read("worked_roads.json")
    data["links"] = []
    with pytest.raises(ValueError, match="roads: empty graph"):
        parse_roads(data)
    data["nodes"] = []
    with pytest.raises(ValueError, match="roads: empty graph"):
        parse_roads(data)


def test_band_edges_must_be_list():
    data = read("worked_parameters.json")
    data["band_edges"] = tuple(data["band_edges"])
    with pytest.raises(ValueError, match="band_edges: must match band_count"):
        parse_parameters(data)


@pytest.mark.parametrize("field", ["source", "read", "status"])
def test_metadata_must_be_text(field):
    data = read("worked_parameters.json")
    data["alpha"][field] = 1
    with pytest.raises(ValueError, match="alpha." + field):
        parse_parameters(data)


def test_serialized_rows_are_canonical_bytes(tmp_path):
    result = calculate(*run_files(tmp_path))
    expected = (
        json.dumps(result.payload, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode()
    assert result.to_bytes() == expected
