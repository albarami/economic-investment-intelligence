"""Exact adapter contracts and engine-boundary probes for L-84 mutation survivors."""

import json
from copy import deepcopy
from dataclasses import replace
from fractions import Fraction as F
from unittest.mock import Mock, patch

import pytest
from product.tests.test_traffic_canonical import prepared
from product.tests.test_traffic_speed_document import traffic_fixture

import h3
from eii_product.areas_spike.traffic import Traffic


def changed(tmp_path, path, value):
    paths = prepared(tmp_path)
    payload = json.loads(paths[0].read_text())
    target = payload
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    paths[0].write_text(json.dumps(payload))
    return paths


@pytest.mark.parametrize(
    "path,message",
    [
        (("header", "extra"), "header: missing or unknown field"),
        (("header", "method", "extra"), "method: missing or unknown field"),
        (("header", "sources", "extra"), "sources: missing or unknown field"),
        (("rows", 0, "extra"), "traffic row: missing or unknown field"),
    ],
)
def test_closed_errors_identify_exact_section(tmp_path, path, message):
    with pytest.raises(ValueError) as error:
        Traffic.load(*changed(tmp_path, path, "invented"))
    assert str(error.value) == message


@pytest.mark.parametrize(
    "path,value,message",
    [
        (
            ("header", "method", "parameters_sha256"),
            "invalid",
            "parameters_sha256: expected SHA-256",
        ),
        (("header", "method", "id"), "invalid", "method: expected C25"),
        (("header", "sources", "road_link"), "0" * 64, "road_link: digest mismatch"),
        (
            ("header", "method", "parameters_sha256"),
            "0" * 64,
            "parameters_sha256: digest mismatch",
        ),
        (("rows", 0, "link_id"), "SYN-L-missing", "link_id: unknown link"),
        (("rows", 0, "speed_ratio"), "0.000", "speed_ratio: outside contract"),
        (("rows", 0, "speed_ratio"), "2.000", "speed_ratio: outside contract"),
        (("rows", 0, "volume_band"), "vb0", "volume_band: unknown band"),
        (("rows", 0, "volume_band"), "vb4", "volume_band: unknown band"),
    ],
)
def test_row_and_header_errors_are_exact(tmp_path, path, value, message):
    with pytest.raises(ValueError) as error:
        Traffic.load(*changed(tmp_path, path, value))
    assert str(error.value) == message


def test_duplicate_and_fractional_floor_errors_are_exact(tmp_path):
    paths = prepared(tmp_path)
    payload = json.loads(paths[0].read_text())
    payload["rows"].append(payload["rows"][0])
    paths[0].write_text(json.dumps(payload))
    with pytest.raises(ValueError) as error:
        Traffic.load(*paths)
    assert str(error.value) == "traffic row: duplicate key"
    with pytest.raises(ValueError) as error:
        Traffic.load(*prepared(tmp_path, field="floor", value="10.5"))
    assert str(error.value) == "speed_floor_kph: must be a whole number"


def test_class_speed_equal_to_floor_is_accepted(tmp_path):
    traffic = Traffic.load(
        *prepared(tmp_path, field="speed", value="10", ratio="1.000")
    )
    assert traffic.link_speed("SYN-L-001", 8) == 10


def test_actor_defaults_match_explicit_weekday_non_summer():
    traffic = traffic_fixture()
    assert traffic.actor(8) is traffic.actor(8, "weekday", False)


def test_measurement_route_passes_exact_engine_costing():
    traffic = traffic_fixture()
    actor = Mock(wraps=traffic.actor(8))
    with patch.object(Traffic, "actor", return_value=actor):
        traffic.route_for_measurement("SYN-N-0-0", "SYN-N-0-2", 8)
    assert actor.route.call_args.args == (
        {
            "locations": [{"lat": 0.0, "lon": 0.0}, {"lat": 0.0, "lon": 0.02}],
            "costing": "auto",
            "costing_options": {"auto": {"speed_types": []}},
        },
    )


def test_negative_disagreement_message_is_exact():
    traffic = traffic_fixture()
    raw = deepcopy(traffic.route_for_measurement("SYN-N-0-1", "SYN-N-0-2", 8))
    raw["trip"]["summary"]["time"] = F(20034, 115) - F("0.01")
    with patch.object(Traffic, "route_for_measurement", return_value=raw):
        with pytest.raises(ValueError) as error:
            traffic.route("SYN-N-0-1", "SYN-N-0-2", 8)
    assert (
        str(error.value) == "engine time below exact link sum beyond printed resolution"
    )


@pytest.mark.parametrize("mode,costing", [("drive", "auto"), ("walk", "pedestrian")])
def test_area_forwards_summer_and_exact_engine_request_at_subminute_cutoff(
    mode, costing
):
    traffic = traffic_fixture()
    traffic = replace(
        traffic,
        rows=(
            *traffic.rows,
            *({**row, "summer": True, "speed_ratio": "1.000"} for row in traffic.rows),
        ),
    )
    selected_hour = 8 if mode == "drive" else None
    actor = Mock(wraps=traffic.actor(selected_hour, "weekday", True))
    frame = tuple(sorted(h3.grid_disk(h3.latlng_to_cell(0, 0, 12), 12)))
    with patch.object(Traffic, "actor", return_value=actor) as supplied:
        traffic.area("SYN-N-0-0", 0.5, 8, frame, mode=mode, summer=True)
    supplied.assert_called_once_with(selected_hour, "weekday", True)
    assert actor.isochrone.call_args.args == (
        {
            "locations": [{"lat": 0.0, "lon": 0.0}],
            "costing": costing,
            "contours": [{"time": 0.5}],
            "polygons": True,
            "costing_options": {costing: {"speed_types": [], "walking_speed": 5.0}},
        },
    )


@pytest.mark.parametrize(
    "kwargs,message",
    [
        ({"mode": "invalid"}, "Unknown mode"),
        ({"minutes": 0}, "Cutoff must be positive"),
    ],
)
def test_area_refusal_messages_are_exact(kwargs, message):
    args = dict(pin="SYN-N-0-0", minutes=3, hour=8, frame=())
    args.update(kwargs)
    with pytest.raises(ValueError) as error:
        traffic_fixture().area(**args)
    assert str(error.value) == message


def test_invalid_engine_geometry_message_is_exact():
    actor = Mock()
    actor.isochrone.return_value = {
        "features": [{"geometry": {"type": "MultiPolygon", "coordinates": []}}]
    }
    with patch.object(Traffic, "actor", return_value=actor):
        with pytest.raises(ValueError) as error:
            traffic_fixture().area("SYN-N-0-0", 3, 8, ())
    assert str(error.value) == "Engine geometry must be a Polygon with one ring"


def test_hour_refusal_message_is_exact():
    with pytest.raises(ValueError) as error:
        Traffic.check_hour("invalid", 8, False)
    assert str(error.value) == "Unknown day_type, hour or summer"


def test_road_document_preserves_metadata_and_edge_contract():
    road = traffic_fixture().road_fixture((35, 35, 60, 60), "SYN-N-0-1")
    assert set(road) == {
        "pin",
        "walk_kph",
        "cutoff_seconds",
        "radius_m",
        "nodes",
        "edges",
    }
    assert road["pin"] == "SYN-N-0-1"
    assert road["walk_kph"] == 5.0
    assert road["cutoff_seconds"] == 0.0
    assert road["radius_m"] == 0.0
    assert road["edges"][0] == {
        "source": "SYN-N-0-0",
        "target": "SYN-N-0-1",
        "length_m": 1113.0,
        "drive_kph": 35.0,
        "road_class": "residential",
        "oneway": True,
    }


@pytest.mark.parametrize("vector", [(35, 35, 60), (35, 35, 60, 60, 60)])
def test_road_document_refuses_mismatched_vector_length(vector):
    with pytest.raises(ValueError, match="zip"):
        traffic_fixture().road_fixture(vector, "SYN-N-0-0")
