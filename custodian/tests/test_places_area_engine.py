"""The pinned engine runs once, on an invented road file of this task."""

from __future__ import annotations

import json
import tomllib
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from custodian.tests.repository_root import repository_root
from shapely.geometry import Point
from shapely.wkb import loads as load_wkb

from eii_custodian.publicdata.fetch.receipts import sha256_hex
from eii_custodian.publicdata.places.area_engine import PinnedEngine
from eii_custodian.publicdata.places.area_files import (
    ENGINE_PIN,
    AreaRequest,
    produce_areas,
)
from eii_custodian.publicdata.places.areas import AreaCutoff, AreaMode

_FIXTURES = Path(__file__).parent / "fixtures" / "places"
# SHA-256 of the committed invented grid, stated from that file's bytes.
_ROAD_SHA = "5161a258ef2b03de23cfecc52ce96517fb4578bfd068053231cfc25d003e7025"
_FRAME = (50.7, 24.4, 51.7, 26.2)


def test_engine_pin_is_the_pin_file() -> None:
    """ENGINE_PIN is the pyvalhalla pin in pins.toml, not a second hand-kept number."""
    pins = tomllib.loads(
        (repository_root(Path(__file__)) / "pins.toml").read_text(encoding="utf-8")
    )
    recorded = next(
        row["pin"] for row in pins["component"] if row["name"] == "pyvalhalla"
    )
    assert ENGINE_PIN == recorded


def test_syn_road_regenerates_the_committed_file() -> None:
    """The invented road generator reproduces the committed file byte for byte."""
    from custodian.tests.fixtures.places.syn_road import grid_pbf

    assert grid_pbf() == (_FIXTURES / "syn_roads.osm.pbf").read_bytes()


def test_pinned_engine_writes_one_polygon_from_the_invented_road(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """pyvalhalla 3.9.1 turns the invented grid into one polygon inside the frame."""
    road = (_FIXTURES / "syn_roads.osm.pbf").read_bytes()
    manifest = json.loads((_FIXTURES / "syn_roads_manifest.json").read_text())
    assert len(road) == manifest["bytes"]
    assert sha256_hex(road) == _ROAD_SHA
    assert manifest["sha256"] == _ROAD_SHA
    engine = PinnedEngine()
    assert engine.version == "3.9.1"
    assert engine.version == ENGINE_PIN
    directory = tmp_path / "roads_osm"
    directory.mkdir()
    (directory / f"{_ROAD_SHA}.pbf").write_bytes(road)
    (directory / f"{_ROAD_SHA}.meta.json").write_text(
        json.dumps({"sha256": _ROAD_SHA}), encoding="utf-8"
    )
    walk = AreaRequest(
        "SYN-POINT", "51.410000", "25.209000", AreaMode.WALK, AreaCutoff.MINUTES_5
    )
    drive = AreaRequest(
        "SYN-POINT", "51.410000", "25.209000", AreaMode.DRIVE, AreaCutoff.MINUTES_5
    )
    opened: list[str] = []

    class _Counting(TemporaryDirectory[str]):
        def __init__(self, prefix: str = "syn-area-") -> None:
            super().__init__(prefix=prefix)
            opened.append(self.name)

    monkeypatch.setattr(
        "eii_custodian.publicdata.places.area_engine.TemporaryDirectory", _Counting
    )
    produce_areas(engine, (walk, drive), cache=tmp_path, frame_box=_FRAME)
    assert len(opened) == 1
    stored = json.loads(
        (tmp_path / "places_s2_t06" / "areas" / "SYN-POINT.walk.5.json").read_text(
            encoding="utf-8"
        )
    )
    polygon = load_wkb(bytes.fromhex(stored["polygon_wkb_hex"]))
    assert polygon.geom_type == "Polygon"
    assert polygon.contains(Point(51.41, 25.209))
    assert stored["engine_version"] == "3.9.1"
    assert stored["graph_hash"] == _ROAD_SHA
    assert "stand_in" not in stored
    driven = json.loads(
        (tmp_path / "places_s2_t06" / "areas" / "SYN-POINT.drive.5.json").read_text(
            encoding="utf-8"
        )
    )
    drive_polygon = load_wkb(bytes.fromhex(driven["polygon_wkb_hex"]))
    assert drive_polygon.geom_type == "Polygon"
    assert drive_polygon.contains(Point(51.41, 25.209))
    assert driven["mode"] == "drive"
