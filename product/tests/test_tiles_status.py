"""Pure tests for the tile status rule (no HTTP server)."""

from __future__ import annotations

import tempfile
from pathlib import Path

from eii_product.api.tiles import tile_status


def test_tile_status_rule() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        fixture = root / "spike.tile"
        fixture.write_bytes(b"x")
        assert tile_status(root, "spike.tile") == "ok"

        assert tile_status(root, "absent.tile") == "missing"

        empty = root / "empty.tile"
        empty.write_bytes(b"")
        assert tile_status(root, "empty.tile") == "invalid"

        (root / "folder.tile").mkdir()
        assert tile_status(root, "folder.tile") == "invalid"


def test_tile_status_accepts_closed_pmtiles_names() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        archive = root / "basemap.pmtiles"
        archive.write_bytes(b"x")
        assert tile_status(root, "basemap.pmtiles") == "ok"
        assert tile_status(root, "absent.pmtiles") == "missing"
        (root / "folder.pmtiles").mkdir()
        assert tile_status(root, "folder.pmtiles") == "invalid"
        for bad in ("Upper.pmtiles", "x.pmtilesx", "other.txt", ".pmtiles"):
            assert tile_status(root, bad) == "missing", bad
