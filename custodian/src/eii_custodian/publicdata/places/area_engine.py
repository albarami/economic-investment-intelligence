"""Turn one area request into one polygon. This is the only engine import."""

from __future__ import annotations

import json
import subprocess
import sys
from importlib.metadata import version
from pathlib import Path
from tempfile import TemporaryDirectory

from shapely.geometry import shape
from valhalla import Actor, get_config

from eii_custodian.publicdata.fetch.receipts import sha256_hex
from eii_custodian.publicdata.places.area_files import AreaRequest
from eii_custodian.publicdata.places.read import geometry_wkb

_COSTING = {"walk": "pedestrian", "drive": "auto"}


class PinnedEngine:
    """The installed pyvalhalla. One run builds its tiles once."""

    def __init__(self) -> None:
        self.version = version("pyvalhalla")
        self._digest: str | None = None
        self._actor: Actor | None = None
        self._config = ""
        self._storage: TemporaryDirectory[str] | None = None

    def prepare(self, road: bytes) -> None:
        """Build routing tiles from the road file once for this road."""
        digest = sha256_hex(road)
        if self._digest == digest and self._actor is not None:
            return
        self._close()
        storage = TemporaryDirectory(prefix="syn-area-")
        folder = Path(storage.name)
        road_path = folder / "road.osm.pbf"
        road_path.write_bytes(road)
        config = get_config(tile_extract="", tile_dir=str(folder))
        config["mjolnir"]["concurrency"] = 1
        config["mjolnir"]["admin"] = str(folder / "absent-admin.sqlite")
        config["mjolnir"]["timezone"] = str(folder / "absent-timezone.sqlite")
        path = folder / "config.json"
        path.write_text(json.dumps(config), encoding="utf-8")
        built = subprocess.run(
            [
                sys.executable,
                "-m",
                "valhalla",
                "valhalla_build_tiles",
                "-c",
                str(path),
                str(road_path),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if built.returncode != 0:
            storage.cleanup()
            raise RuntimeError("tile build failed")
        self._storage = storage
        self._config = str(path)
        self._actor = Actor(self._config)
        self._digest = digest

    def polygon(self, request: AreaRequest, road: bytes) -> bytes:
        """Return the isochrone as WKB. Tiles are built by prepare."""
        self.prepare(road)
        if self._actor is None:
            raise RuntimeError("tile build failed")
        costing = _COSTING[request.mode.value]
        answer = self._actor.isochrone(
            {
                "locations": [{"lat": float(request.lat), "lon": float(request.lon)}],
                "costing": costing,
                "contours": [{"time": request.cutoff.value}],
                "polygons": True,
            }
        )
        geometry = answer["features"][0]["geometry"]
        return geometry_wkb(shape(geometry))

    def _close(self) -> None:
        if self._storage is not None:
            self._storage.cleanup()
        self._storage = None
        self._actor = None
        self._digest = None
        self._config = ""
