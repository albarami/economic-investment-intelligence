"""Bundled-builder trial using only the invented road fixture."""

import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

import pytest
from shapely.geometry import Point, shape
from valhalla import Actor, get_config

from eii_product.areas_spike.extract import generate

FIXTURES = Path(__file__).parent / "fixtures" / "areas_spike"


def test_pbf_reproduces_committed_fixture() -> None:
    expected = (FIXTURES / "road_network.osm.pbf").read_bytes()
    actual = generate(FIXTURES / "road_network.json")
    assert actual == expected
    manifest = json.loads((FIXTURES / "pbf_manifest.json").read_text())
    assert len(actual) == manifest["size_bytes"]
    assert hashlib.sha256(actual).hexdigest() == manifest["sha256"]


@pytest.fixture(scope="session")
def tile_config(tmp_path_factory: pytest.TempPathFactory) -> Path:
    folder = tmp_path_factory.mktemp("synthetic-tiles")
    config = get_config(tile_extract="", tile_dir=folder)
    config["mjolnir"]["concurrency"] = 1
    config["mjolnir"]["admin"] = str(folder / "absent-admin.sqlite")
    config["mjolnir"]["timezone"] = str(folder / "absent-timezone.sqlite")
    path = folder / "config.json"
    path.write_text(json.dumps(config))
    command = [
        sys.executable,
        "-m",
        "valhalla",
        "valhalla_build_tiles",
        "-c",
        str(path),
        str(FIXTURES / "road_network.osm.pbf"),
    ]
    start = time.monotonic()
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    print("builder exit:", result.returncode)
    print("builder seconds:", time.monotonic() - start)
    print(result.stdout)
    print(result.stderr)
    assert result.returncode == 0
    assert list(folder.rglob("*.gph"))
    return path


def test_bundled_builder_and_actor_read_graph(
    tile_config: Path, tmp_path: Path
) -> None:
    road = json.loads((FIXTURES / "road_network.json").read_text())
    nodes = {node["id"]: node for node in road["nodes"]}
    pin = nodes[road["pin"]]
    request = {
        "locations": [{"lat": pin["lat"], "lon": pin["lon"]}],
        "costing": "auto",
        "contours": [{"time": road["cutoff_seconds"] / 60}],
        "polygons": True,
    }
    actor = Actor(tile_config)
    answer = actor.isochrone(request)
    geometry = shape(answer["features"][0]["geometry"])
    near = nodes["SYN-N-4-5"]
    far = nodes["SYN-N-8-8"]
    assert geometry.contains(Point(near["lon"], near["lat"]))
    assert not geometry.contains(Point(far["lon"], far["lat"]))
    empty = Actor(get_config(tile_extract="", tile_dir=tmp_path))
    try:
        empty_answer = empty.isochrone(request)
    except RuntimeError as error:
        print("empty graph error:", str(error))
    else:
        print("empty graph answer:", json.dumps(empty_answer, sort_keys=True))
        assert empty_answer != answer
