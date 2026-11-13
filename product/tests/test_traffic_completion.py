"""Completion guards for the released-row adapter."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

import h3
from eii_product.areas_spike import traffic as adapter
from eii_product.areas_spike.traffic import Traffic

FIXTURES = Path(__file__).parent / "fixtures" / "areas_spike" / "assignment"


def frame():
    return tuple(sorted(h3.grid_disk(h3.latlng_to_cell(0, 0, 9), 12)))


def load():
    return Traffic.load(
        FIXTURES / "hourly_rows.json",
        FIXTURES / "hourly_roads.json",
        FIXTURES / "hourly_parameters.json",
    )


@pytest.mark.parametrize("speed", [9, 141, 35.5, True, "35"])
def test_adapter_refuses_speed_outside_whole_range(speed):
    traffic = load()
    vector = (speed, *traffic.speed_vector(None)[1:])
    with pytest.raises(ValueError, match=r"speed.*whole.*10.*140"):
        traffic.road_fixture(vector, "SYN-N-0-0")


def test_adapter_keeps_range_endpoints():
    traffic = load()
    vector = (10, 140, 35, 60)
    assert (
        tuple(
            edge["drive_kph"]
            for edge in traffic.road_fixture(vector, "SYN-N-0-0")["edges"]
        )
        == vector
    )


def test_area_classes_for_every_stored_hour():
    traffic = load()
    free = traffic.area("SYN-N-0-0", 3, None, frame())
    assert (free.provenance, free.evidence_status) == ("Public", "observed")
    for hour in range(24):
        drive = traffic.area("SYN-N-0-0", 3, hour, frame())
        walk = traffic.area("SYN-N-0-0", 3, hour, frame(), mode="walk")
        assert (drive.provenance, drive.evidence_status) == ("Simulated", "observed")
        assert (walk.provenance, walk.evidence_status) == ("Public", "observed")


def test_walk_requests_free_flow_document_every_hour():
    traffic = load()
    with patch.object(adapter, "scaled_actor", wraps=adapter.scaled_actor) as spy:
        for hour in range(24):
            traffic.area("SYN-N-0-0", 3, hour, frame(), mode="walk")
    expected = json.dumps(
        traffic.road_fixture(traffic.speed_vector(None), "SYN-N-0-0"), sort_keys=True
    )
    assert len(spy.call_args_list) == 24
    assert all(call.args == (expected, 1.0) for call in spy.call_args_list)


@pytest.mark.parametrize("mode", ["walk", "drive"])
@pytest.mark.parametrize(
    "overrides,message",
    [
        ({"mode": "cycle"}, "Unknown mode"),
        ({"minutes": 0}, "Cutoff must be positive"),
        ({"minutes": -1}, "Cutoff must be positive"),
        ({"day_type": "invented"}, "Unknown day_type, hour or summer"),
        ({"hour": 24}, "Unknown day_type, hour or summer"),
        ({"hour": "8"}, "Unknown day_type, hour or summer"),
        ({"hour": 8.0}, "Unknown day_type, hour or summer"),
        ({"hour": True}, "Unknown day_type, hour or summer"),
        ({"summer": "false"}, "Unknown day_type, hour or summer"),
    ],
)
def test_area_refusals_on_drive_and_walk(mode, overrides, message):
    args = dict(pin="SYN-N-0-0", minutes=3, hour=8, frame=(), mode=mode)
    args.update(overrides)
    with pytest.raises(ValueError, match=message):
        load().area(**args)


def test_lookup_reaches_all_situation_filters(tmp_path):
    payload = json.loads((FIXTURES / "hourly_rows.json").read_text())
    base = next(
        row
        for row in payload["rows"]
        if row["link_id"] == "SYN-L-001" and row["hour"] == 8
    )
    payload["rows"].append({**base, "summer": True, "speed_ratio": "0.800"})
    path = tmp_path / "rows.json"
    path.write_text(json.dumps(payload))
    traffic = Traffic.load(
        path, FIXTURES / "hourly_roads.json", FIXTURES / "hourly_parameters.json"
    )
    assert traffic.speed_vector(8, "weekday", False)[0] == 10
    assert traffic.speed_vector(8, "weekday", True)[0] == 28
    # A row of another day cannot overwrite this day's value in the lookup.
    from dataclasses import replace

    traffic = replace(
        traffic,
        rows=(*traffic.rows, {**base, "day_type": "friday", "speed_ratio": "1.000"}),
    )
    assert traffic.speed_vector(8, "weekday", False)[0] == 10


def test_top_level_payload_must_be_object(tmp_path):
    path = tmp_path / "rows.json"
    path.write_text(json.dumps(["header", "rows"]))
    with pytest.raises(ValueError, match="traffic: missing or unknown field"):
        Traffic.load(
            path, FIXTURES / "hourly_roads.json", FIXTURES / "hourly_parameters.json"
        )


@pytest.mark.parametrize(
    "geometry",
    [
        {"type": "MultiPolygon", "coordinates": [[]]},
        {"type": "Polygon", "coordinates": [[], []]},
    ],
)
def test_geometry_must_be_polygon_with_one_ring(geometry):
    from unittest.mock import Mock

    actor = Mock()
    actor.isochrone.return_value = {"features": [{"geometry": geometry}]}
    with patch.object(Traffic, "actor", return_value=actor):
        with pytest.raises(
            ValueError, match="Engine geometry must be a Polygon with one ring"
        ):
            load().area("SYN-N-0-0", 3, 8, frame())
