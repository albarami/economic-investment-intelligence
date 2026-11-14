"""L-74 snapshot limits and canonical ratios; setup uses independent arithmetic."""

import hashlib
import json
from fractions import Fraction as F
from pathlib import Path

import pytest

from eii_product.areas_spike.traffic import Traffic, engine_speed

FIXTURES = Path(__file__).parent / "fixtures/areas_spike/assignment"


def prepared(
    tmp_path, *, field=None, value=None, ratio="0.167", road_class="secondary"
):
    parameters = json.loads((FIXTURES / "worked_parameters.json").read_text())
    if field == "speed":
        parameters["speeds"][road_class]["value"] = value
    elif field == "floor":
        parameters["speed_floor_kph"]["value"] = value
    roads = json.loads((FIXTURES / "worked_roads.json").read_text())
    roads["links"][0]["road_class"] = road_class
    if road_class == "residential" and field != "speed":
        parameters["speeds"][road_class]["value"] = "35"
    payload = json.loads((FIXTURES / "worked_rows.json").read_text())
    payload["rows"] = [{**payload["rows"][0], "speed_ratio": ratio}]
    paths = [tmp_path / name for name in ("rows.json", "roads.json", "parameters.json")]
    paths[1].write_text(json.dumps(roads))
    paths[2].write_text(json.dumps(parameters))
    payload["header"]["sources"]["road_link"] = hashlib.sha256(
        paths[1].read_bytes()
    ).hexdigest()
    payload["header"]["method"]["parameters_sha256"] = hashlib.sha256(
        paths[2].read_bytes()
    ).hexdigest()
    paths[0].write_text(json.dumps(payload))
    return paths


@pytest.mark.parametrize(
    "field,value,message",
    [
        ("speed", "35.5", r"speeds.secondary:.*whole"),
        ("speed", "141", r"speeds.secondary:.*140"),
        ("speed", "9", r"speeds.secondary:.*speed_floor_kph"),
        ("floor", "10.5", r"speed_floor_kph:.*whole"),
        ("floor", "9", r"speed_floor_kph:.*10"),
    ],
)
def test_snapshot_refuses_engine_limit(tmp_path, field, value, message):
    with pytest.raises(ValueError, match=message):
        Traffic.load(*prepared(tmp_path, field=field, value=value, ratio="1.000"))


@pytest.mark.parametrize(
    "road_class,ratio,message",
    [
        ("secondary", "0.158", "released speed floor"),
        ("secondary", "0.159", "noncanonical speed_ratio"),
        ("residential", "0.285", "noncanonical speed_ratio"),
    ],
)
def test_noncanonical_or_below_floor_refused(tmp_path, road_class, ratio, message):
    with pytest.raises(ValueError, match=rf"^rows.json: {message}.*SYN-L-001$"):
        Traffic.load(*prepared(tmp_path, road_class=road_class, ratio=ratio))


@pytest.mark.parametrize(
    "road_class,ratio", [("secondary", "0.167"), ("residential", "0.286")]
)
def test_canonical_floor_boundary_accepted(tmp_path, road_class, ratio):
    traffic = Traffic.load(*prepared(tmp_path, road_class=road_class, ratio=ratio))
    assert traffic.link_speed("SYN-L-001", 8) == 10


def test_snapshot_floor_is_used(tmp_path):
    with pytest.raises(
        ValueError, match=r"^rows.json: released speed floor.*SYN-L-001$"
    ):
        Traffic.load(*prepared(tmp_path, field="floor", value="12"))


@pytest.mark.parametrize("name", ["hourly", "worked"])
def test_ratio_round_trip_for_every_whole_class_speed(name):
    params = json.loads((FIXTURES / f"{name}_parameters.json").read_text())
    floor = int(params["speed_floor_kph"]["value"])
    for entry in params["speeds"].values():
        free = int(entry["value"])
        for whole in range(floor, free + 1):
            ratio = F((F(whole, free) * 1000 + F(1, 2)) // 1, 1000)
            assert engine_speed(ratio * free) == whole


def test_late_link_floor_and_canonical_refusals(tmp_path):
    for ratio, message in (
        ("0.100", "released speed floor"),
        ("0.159", "noncanonical speed_ratio"),
    ):
        paths = prepared(tmp_path)
        payload = json.loads(paths[0].read_text())
        payload["rows"].append(
            {**payload["rows"][0], "link_id": "SYN-L-003", "speed_ratio": ratio}
        )
        paths[0].write_text(json.dumps(payload))
        with pytest.raises(ValueError, match=rf"^rows.json: {message}.*SYN-L-003$"):
            Traffic.load(*paths)


def test_maximum_free_speed_is_accepted(tmp_path):
    traffic = Traffic.load(
        *prepared(tmp_path, field="speed", value="140", ratio="1.000")
    )
    assert traffic.link_speed("SYN-L-001", 8) == 140


def test_fractional_link_length_refused_with_file_and_link(tmp_path):
    paths = prepared(tmp_path)
    roads = json.loads(paths[1].read_text())
    roads["links"][0]["length_m"] = "0.5"
    paths[1].write_text(json.dumps(roads))
    payload = json.loads(paths[0].read_text())
    payload["header"]["sources"]["road_link"] = hashlib.sha256(
        paths[1].read_bytes()
    ).hexdigest()
    paths[0].write_text(json.dumps(payload))
    with pytest.raises(ValueError, match=r"roads.json:.*whole.*SYN-L-001"):
        Traffic.load(*paths)
