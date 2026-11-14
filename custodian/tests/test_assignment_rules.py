"""C25 rules not covered by the worked example; exact synthetic fixtures."""

import copy
import hashlib
import json
from fractions import Fraction as F
from pathlib import Path

import pytest

from eii_custodian.assignment_spike.assign import free_times, volumes
from eii_custodian.assignment_spike.delay import (
    length_weighted_slowdown,
    rounded_ratio,
    situation_mean,
    volume_band,
)
from eii_custodian.assignment_spike.inputs import parse_flows, parse_roads
from eii_custodian.assignment_spike.params import CLASSES, parse_parameters
from eii_custodian.assignment_spike.paths import loading_nodes, shortest
from eii_custodian.assignment_spike.run import calculate

FIXTURES = Path(__file__).parent / "fixtures" / "assignment_spike"


def read(name):
    data = json.loads((FIXTURES / name).read_text())
    if name == "worked_flows.json":
        # Each rule fixture changes the original single-hour example only.
        data["rows"] = data["rows"][:1]
    return data


def run_changed(tmp_path, *, parameters=None, roads=None, flows=None):
    inputs = []
    for name, value in [
        ("worked_flows.json", flows),
        ("worked_roads.json", roads),
        ("worked_parameters.json", parameters),
    ]:
        path = tmp_path / name
        path.write_text(json.dumps(read(name) if value is None else value))
        inputs.append(path)
    return calculate(*inputs)


def test_nearest_tie_lower_node_identifier():
    roads = read("worked_roads.json")
    roads["nodes"] = [
        {"id": "SYN-N-0-0", "lat": "0", "lon": "-0.01"},
        {"id": "SYN-N-0-2", "lat": "0", "lon": "0.01"},
        {"id": "SYN-N-1-1", "lat": "0.02", "lon": "0"},
    ]
    roads["nodes"].reverse()  # Input order must not decide.
    roads["units"][0].update(lat="0", lon="0")
    assert loading_nodes(parse_roads(roads))["SYN-U-01"] == "SYN-N-0-0"
    roads["units"][0]["lon"] = "0.009"
    assert loading_nodes(parse_roads(roads))["SYN-U-01"] == "SYN-N-0-2"


def test_equal_cost_paths_use_lexicographic_node_sequence():
    roads = read("worked_roads.json")
    roads["links"][0]["length_m"] = "12000"
    graph = parse_roads(roads)
    params = parse_parameters(read("worked_parameters.json"))
    answer = shortest(graph, free_times(graph, params), "SYN-N-0-0", "SYN-N-0-2")
    assert answer == (F("12"), ("SYN-N-0-0", "SYN-N-0-2"), ("SYN-L-001",))
    assigned = volumes(graph, parse_flows(read("worked_flows.json"), graph), params)
    assert assigned == {("SYN-L-001", "weekday", 8, False): F("500")}


def test_inside_unit_and_zero_volume_links_have_no_row(tmp_path):
    flows = read("worked_flows.json")
    flows["rows"][0]["destination_unit_id"] = "SYN-U-01"
    assert run_changed(tmp_path, flows=flows).payload["rows"] == []
    flows["rows"][0]["destination_unit_id"] = "SYN-U-02"
    flows["rows"][0]["estimate"] = "0"
    assert run_changed(tmp_path, flows=flows).payload["rows"] == []


@pytest.mark.parametrize(
    ("ratio", "band"),
    [("0", "vb1"), ("0.249", "vb1"), ("0.25", "vb2"), ("0.75", "vb3"), ("4", "vb3")],
)
def test_band_edges_and_open_last_band(ratio, band):
    assert (
        volume_band(F(ratio), parse_parameters(read("worked_parameters.json"))) == band
    )


@pytest.mark.parametrize(
    ("value", "expected"),
    [("0.8125", "0.813"), ("0.8124", "0.812"), ("0.9995", "1.000")],
)
def test_exact_half_up(value, expected):
    assert rounded_ratio(F(value)) == expected


def test_mth90_pure_functions():
    assert situation_mean((F("12.5"), F("10"))) == F("11.25")
    assert length_weighted_slowdown(((F("3"), F("0.750")), (F("1"), None))) == "0.813"
    with pytest.raises(ValueError, match="NO_DATA"):
        situation_mean(())
    with pytest.raises(ValueError, match="NO_DATA"):
        length_weighted_slowdown(())


@pytest.mark.parametrize(
    ("key", "value", "minutes"), [("alpha", "2", "15"), ("beta", "1", "15")]
)
def test_delay_parameter_used(tmp_path, key, value, minutes):
    params = read("worked_parameters.json")
    params[key]["value"] = value
    row = run_changed(tmp_path, parameters=params).calculations[0]
    # 10 * (1 + 2*(1/2)^2), or 10 * (1 + (1/2)^1).
    assert row.minutes == F(minutes)
    assert row.speed_kph == F("40")


@pytest.mark.parametrize("road_class", sorted(CLASSES))
@pytest.mark.parametrize("parameter", ["speeds", "capacities"])
def test_every_class_parameter_used(tmp_path, road_class, parameter):
    params, roads = read("worked_parameters.json"), read("worked_roads.json")
    for link in roads["links"]:
        link["road_class"] = road_class
    if parameter == "speeds":
        params[parameter][road_class]["value"] = "30"
        # t0=20; delay=1.25 -> 25 minutes, speed=24.
        minutes, speed = "25", "24"
    else:
        params[parameter][road_class]["value"] = "500"
        # t0=10; delay=1+(500/500)^2 -> 20 minutes, speed=30.
        minutes, speed = "20", "30"
    row = run_changed(tmp_path, parameters=params, roads=roads).calculations[0]
    assert row.minutes == F(minutes)
    assert row.speed_kph == F(speed)


@pytest.mark.parametrize(
    ("index", "value", "band"), [(0, "0.60", "vb1"), (1, "0.40", "vb3")]
)
def test_each_band_edge_used(tmp_path, index, value, band):
    params = read("worked_parameters.json")
    params["band_edges"][index]["value"] = value
    assert run_changed(tmp_path, parameters=params).calculations[0].volume_band == band


def test_speed_changes_path_and_volume(tmp_path):
    params, roads = read("worked_parameters.json"), read("worked_roads.json")
    roads["links"][0]["road_class"] = "residential"
    params["speeds"]["residential"]["value"] = "30"
    assert [
        (row.link_id, row.volume)
        for row in run_changed(tmp_path, parameters=params, roads=roads).calculations
    ] == [("SYN-L-002", F("500")), ("SYN-L-003", F("500"))]


def test_repeated_flow_key_refused(tmp_path):
    flows = read("worked_flows.json")
    flows["rows"].append(copy.deepcopy(flows["rows"][0]))
    with pytest.raises(ValueError, match=r"flow.*duplicate"):
        run_changed(tmp_path, flows=flows)


def test_exact_output_and_digests():
    args = [
        FIXTURES / name
        for name in ("worked_flows.json", "worked_roads.json", "worked_parameters.json")
    ]
    result = calculate(*args)
    assert result.to_bytes() == calculate(*args).to_bytes()
    header = result.payload["header"]
    assert (
        header["method"]["parameters_sha256"]
        == hashlib.sha256(args[2].read_bytes()).hexdigest()
    )
    assert header["sources"] == {
        "flow_hourly": hashlib.sha256(args[0].read_bytes()).hexdigest(),
        "road_link": hashlib.sha256(args[1].read_bytes()).hexdigest(),
    }
    assert header["provenance"] == "Simulated"
    assert header["evidence_status"] == "observed"
    assert header["caveat"] == "traffic_simulated"
    assert (
        header["withheld_note"]
        == "Flows withheld by the disclosure controls are left out."
    )


def test_disconnected_graph_refused():
    graph = parse_roads(read("worked_roads.json"))
    with pytest.raises(ValueError, match="disconnected"):
        shortest(
            graph,
            free_times(graph, parse_parameters(read("worked_parameters.json"))),
            "SYN-N-0-2",
            "SYN-N-0-0",
        )


def test_situation_whole_speed_fixture():
    from eii_custodian.assignment_spike import delay

    assert callable(getattr(delay, "situation_whole_speed", None))
    assert situation_mean((F("12.5"), F("10"))) == F("11.25")
    speed = delay.situation_whole_speed(F("10000"), (F("12.5"), F("10")))
    assert speed == 53
    assert F("10000") * 60 / (1000 * speed) == F(600, 53)
    # 1 km in 24/13 minutes is exactly 32.5 km/h: half-up, not half-even.
    assert delay.situation_whole_speed(F("1000"), (F(24, 13),)) == 33
    with pytest.raises(ValueError, match="NO_DATA: empty situation"):
        delay.situation_whole_speed(F("10000"), ())


def test_meridian_loading_tie_uses_lower_identifier():
    from eii_custodian.assignment_spike.inputs import Link, Node, Roads

    graph = Roads(
        (Node("SYN-N-B", F("25.31"), F(0)), Node("SYN-N-A", F("25.29"), F(0))),
        (Link("SYN-L-A", "SYN-N-A", "SYN-N-B", F(1), "secondary"),),
        {"SYN-U-A": (F("25.3"), F(0))},
    )
    assert loading_nodes(graph)["SYN-U-A"] == "SYN-N-A"


def test_parallel_link_tie_loads_lower_link_identifier():
    roads = read("worked_roads.json")
    roads["links"].insert(0, {**roads["links"][0], "link_id": "SYN-L-000"})
    graph = parse_roads(roads)
    assert volumes(
        graph,
        parse_flows(read("worked_flows.json"), graph),
        parse_parameters(read("worked_parameters.json")),
    ) == {("SYN-L-000", "weekday", 8, False): F(500)}


def test_disconnected_flow_command_no_data(tmp_path, capsys):
    from eii_custodian.assignment_spike.__main__ import main

    flows = read("worked_flows.json")
    flows["rows"][0].update(origin_unit_id="SYN-U-02", destination_unit_id="SYN-U-01")
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
        == 3
    )
    assert capsys.readouterr().err == "NO_DATA: no_path SYN-N-0-2 -> SYN-N-0-0\n"
    assert not output.exists()
