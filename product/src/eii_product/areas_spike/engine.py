"""pyvalhalla tiles per distinct fixture factor, followed by in-process routing.

The local generator builds an invented extract. A finite builder subprocess
prepares each tile set; cached Actors route without a server. Drive selects the
hour's scaled speeds; walk always uses unscaled tiles and the fixture walk speed.
The engine polygon is returned unchanged apart from coordinate-axis conversion.
Real networks, release graphs and many-tile-set performance are not proven here.
"""

import json
import subprocess
import sys
from functools import cache
from pathlib import Path
from tempfile import TemporaryDirectory

from valhalla import Actor, get_config

from .extract import generate
from .road import RoadFixture
from .shapes import Ring


@cache
def scaled_actor(
    road_json: str, factor: float
) -> tuple[Actor, TemporaryDirectory[str]]:
    temporary = TemporaryDirectory(prefix="synthetic-scaled-")
    folder = Path(temporary.name)
    road_path = folder / "road.json"
    road_path.write_text(road_json)
    extract = folder / "road.osm.pbf"
    extract.write_bytes(generate(road_path, factor))
    config = get_config(tile_extract="", tile_dir=folder)
    config["mjolnir"]["concurrency"] = 1
    config["mjolnir"]["admin"] = str(folder / "absent-admin.sqlite")
    config["mjolnir"]["timezone"] = str(folder / "absent-timezone.sqlite")
    path = folder / "config.json"
    path.write_text(json.dumps(config))
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "valhalla",
            "valhalla_build_tiles",
            "-c",
            str(path),
            str(extract),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError("Synthetic tile builder failed")
    return Actor(path), temporary


def scaled_isochrone(
    road: RoadFixture, mode: str, seconds: float, hour: int, factors: tuple[float, ...]
) -> Ring:
    if not road["edges"]:
        raise ValueError("Reachable geometry has no polygon")
    factor = factors[hour] if mode == "drive" else 1.0
    actor, _temporary = scaled_actor(json.dumps(road, sort_keys=True), factor)
    pin = next(node for node in road["nodes"] if node["id"] == road["pin"])
    costing = "auto" if mode == "drive" else "pedestrian"
    request = {
        "locations": [{"lat": pin["lat"], "lon": pin["lon"]}],
        "costing": costing,
        "contours": [{"time": seconds / 60}],
        "polygons": True,
        "costing_options": {
            costing: {"speed_types": [], "walking_speed": road["walk_kph"]}
        },
    }
    answer = actor.isochrone(request)
    geometry = answer["features"][0]["geometry"]
    if geometry["type"] != "Polygon":
        raise ValueError("Engine geometry must be a Polygon")
    if len(geometry["coordinates"]) != 1:
        raise ValueError("Engine polygon must have one ring")
    return tuple((lat, lon) for lon, lat in geometry["coordinates"][0])
