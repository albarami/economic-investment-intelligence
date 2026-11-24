"""Invented routing extract; reuse the area spike's wheel-only tile builder."""

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from eii_product.areas_spike.engine import scaled_actor

TILES = "artefacts/routing/tiles.tar"


def invented_extract(destination: Path) -> dict[str, str]:
    road = json.loads(
        Path("product/tests/fixtures/areas_spike/road_network.json").read_bytes()
    )
    for node in road["nodes"]:
        node["lat"] += 1
        node["lon"] += 1
    return extract_from_road(road, destination)


def extract_from_road(road: dict[str, Any], destination: Path) -> dict[str, str]:
    """Build an extract from the caller's invented, possibly shifted road."""
    _actor, storage = scaled_actor(json.dumps(road, sort_keys=True), 1.0)
    destination.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "valhalla.valhalla_build_extract",
            "-i",
            json.dumps(
                {
                    "mjolnir": {
                        "tile_dir": storage.name,
                        "tile_extract": str(destination),
                    }
                }
            ),
        ],
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return {
        "path": TILES,
        "sha256": hashlib.sha256(destination.read_bytes()).hexdigest(),
    }
