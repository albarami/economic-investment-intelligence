"""Area files are refused unless every hash and the polygon prove the request."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from shapely.geometry import MultiPolygon, Point, Polygon
from shapely.wkb import loads as load_wkb

from eii_custodian.publicdata.fetch.receipts import sha256_hex
from eii_custodian.publicdata.places.area_files import (
    ENGINE_PIN,
    METHOD_VERSION,
    AreaRequest,
    FileAreaProvider,
    coordinate_text,
    produce_areas,
    verify_areas,
)
from eii_custodian.publicdata.places.areas import (
    AreaCutoff,
    AreaError,
    AreaMode,
    ReviewedPoint,
)

# Stated square inside the frame box. The digest below is of these exact bytes.
_RING = (
    (51.50, 25.30),
    (51.51, 25.30),
    (51.51, 25.31),
    (51.50, 25.31),
    (51.50, 25.30),
)
_ROAD = "ab" * 32
_FRAME = (50.7, 24.4, 51.7, 26.2)


def test_file_digest_not_the_manifests_is_refused(tmp_path: Path) -> None:
    """A file whose digest is not the manifest's is refused before it is trusted."""
    body = _area_bytes()
    name = "SYN-POINT.walk.10.json"
    areas = tmp_path / "places_s2_t06" / "areas"
    areas.mkdir(parents=True)
    (areas / name).write_bytes(body)
    planted = "cd" * 32
    assert planted != hashlib.sha256(body).hexdigest()
    _manifest(areas, name, planted)
    provider = FileAreaProvider(tmp_path, _FRAME)
    with pytest.raises(AreaError) as caught:
        provider.area(
            "SYN-POINT",
            ReviewedPoint(51.50, 25.30),
            AreaMode.WALK,
            AreaCutoff.MINUTES_10,
        )
    assert caught.value.reason == "area_file_digest"


def _area_bytes() -> bytes:
    polygon = Polygon(_RING).wkb.hex()
    payload = {
        "cutoff_minutes": 10,
        "engine_version": "3.9.1",
        "graph_hash": _ROAD,
        "inputs_hash": "ef" * 32,
        "lat": "25.300000",
        "lon": "51.500000",
        "method_version": "places.area.v1",
        "mode": "walk",
        "point_key": "SYN-POINT",
        "polygon_wkb_hex": polygon,
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _manifest(directory: Path, name: str, digest: str, road: str = _ROAD) -> None:
    payload = {
        "files": [{"name": name, "sha256": digest}],
        "road_sha256": road,
    }
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    (directory / "manifest.json").write_text(text, encoding="utf-8")


# The inputs hash is the SHA-256 of this exact request text.
_REQUEST_TEXT = (
    '{"cutoff_minutes":10,"method_version":"places.area.v1","mode":"walk",'
    '"point":{"lat":"25.300000","lon":"51.500000"},"point_key":"SYN-POINT"}'
)


class _HandEngine:
    """Invented polygons. version is read; polygon is the only call."""

    def __init__(self, polygon: bytes, version: str = ENGINE_PIN) -> None:
        self.version = version
        self.polygon_bytes = polygon
        self.calls = 0
        self.touched = False

    def polygon(self, request: AreaRequest, road: bytes) -> bytes:
        self.touched = True
        self.calls += 1
        assert road.startswith(b"SYN-ROAD")
        assert request.point_key == "SYN-POINT"
        return self.polygon_bytes


class _Untouched:
    """Reading version or calling polygon fails the test."""

    @property
    def version(self) -> str:
        raise AssertionError("engine touched")

    def polygon(self, request: AreaRequest, road: bytes) -> bytes:
        raise AssertionError("engine called")


def test_inputs_hash_is_the_stated_request() -> None:
    """The inputs hash is the SHA-256 of the stated canonical request."""
    stated = hashlib.sha256(_REQUEST_TEXT.encode("utf-8")).hexdigest()
    request = AreaRequest(
        "SYN-POINT", "51.500000", "25.300000", AreaMode.WALK, AreaCutoff.MINUTES_10
    )
    assert stated == hashlib.sha256(_REQUEST_TEXT.encode("utf-8")).hexdigest()
    from eii_custodian.publicdata.places.area_files import inputs_hash

    assert inputs_hash(request) == stated
    assert coordinate_text(51.5) == "51.500000"
    assert coordinate_text(25.3) == "25.300000"


def test_manifest_absent_and_wrong_form_are_refused(tmp_path: Path) -> None:
    """No manifest, and a manifest of another form, are each refused."""
    areas = _areas(tmp_path)
    (areas / "SYN-POINT.walk.10.json").write_bytes(_area_bytes())
    with pytest.raises(AreaError) as missing:
        _provider(tmp_path).area(*_walk_10())
    assert missing.value.reason == "area_manifest_missing"
    _manifest(areas, "SYN-POINT.walk.10.json", "ab" * 32)
    planted = areas / "manifest.json"
    planted.write_text('{"files":"SYN"}', encoding="utf-8")
    with pytest.raises(AreaError) as formed:
        _provider(tmp_path).area(*_walk_10())
    assert formed.value.reason == "area_manifest_form"


def test_missing_area_file_is_refused(tmp_path: Path) -> None:
    """A manifest that names a file which is not there stores no area."""
    areas = _areas(tmp_path)
    _manifest(areas, "SYN-POINT.walk.10.json", "ab" * 32)
    with pytest.raises(AreaError) as caught:
        _provider(tmp_path).area(*_walk_10())
    assert caught.value.reason == "area_file_missing"


def test_provider_accepts_one_consistent_file(tmp_path: Path) -> None:
    """A hand-made file whose hashes match the request, road and pin is read."""
    _install_road(tmp_path)
    _write_valid(tmp_path)
    result = _provider(tmp_path).area(*_walk_10())
    assert result.stand_in is False
    assert result.engine_version == ENGINE_PIN
    assert result.method_version == METHOD_VERSION
    assert result.graph_hash == sha256_hex(b"SYN-ROAD")
    assert Polygon(_RING).equals(load_wkb(result.wkb))
    assert "stand_in" not in (tmp_path / "places_s2_t06" / "areas").joinpath(
        "SYN-POINT.walk.10.json"
    ).read_text(encoding="utf-8")


def test_each_file_check_has_one_plant(tmp_path: Path) -> None:
    """Each remaining file reason is one planted change to an otherwise valid file."""
    _install_road(tmp_path)
    plants = {
        "area_request_mismatch": {"lon": "51.510000"},
        "area_inputs_hash": {"inputs_hash": "12" * 32},
        "area_graph_unreceipted": {"graph_hash": "34" * 32},
        "area_engine_version": {"engine_version": "9.9.9"},
        "area_polygon_form": {"polygon_wkb_hex": _outside_hex()},
        "area_stand_in": {"stand_in": True},
    }
    for reason, change in plants.items():
        cache = tmp_path / reason
        _install_road(cache)
        _write_valid(cache, **change)
        with pytest.raises(AreaError) as caught:
            FileAreaProvider(cache, _FRAME).area(*_walk_10())
        assert caught.value.reason == reason
    bare_cache = tmp_path / "missing-road"
    _install_road(bare_cache)
    _write_valid(bare_cache)
    (bare_cache / "roads_osm").rename(bare_cache / "roads_osm_removed")
    with pytest.raises(AreaError) as bare:
        FileAreaProvider(bare_cache, _FRAME).area(*_walk_10())
    assert bare.value.reason == "area_graph_unreceipted"


def test_road_refusals_happen_before_any_engine_call(tmp_path: Path) -> None:
    """A missing road file and a receipt of another digest never call the engine."""
    request = _request()
    with pytest.raises(AreaError) as missing:
        produce_areas(_Untouched(), (request,), cache=tmp_path, frame_box=_FRAME)
    assert missing.value.reason == "road_file_missing"
    _install_road(tmp_path)
    receipt = next((tmp_path / "roads_osm").glob("*.meta.json"))
    receipt.write_text('{"sha256": "' + ("ab" * 32) + '"}', encoding="utf-8")
    with pytest.raises(AreaError) as other:
        produce_areas(_Untouched(), (request,), cache=tmp_path, frame_box=_FRAME)
    assert other.value.reason == "road_file_unreceipted"


def test_point_and_engine_version_are_refused_before_a_polygon_call(
    tmp_path: Path,
) -> None:
    """A point outside the frame, and another engine version, make no polygon."""
    _install_road(tmp_path)
    outside = AreaRequest(
        "SYN-POINT", "10.000000", "25.300000", AreaMode.WALK, AreaCutoff.MINUTES_10
    )
    engine = _HandEngine(_square())
    with pytest.raises(AreaError) as caught:
        produce_areas(engine, (outside,), cache=tmp_path, frame_box=_FRAME)
    assert caught.value.reason == "point_outside_frame"
    assert engine.calls == 0
    other = _HandEngine(_square(), version="0.0.0")
    with pytest.raises(AreaError) as version:
        produce_areas(other, (_request(),), cache=tmp_path, frame_box=_FRAME)
    assert version.value.reason == "engine_version"
    assert other.calls == 0


def test_engine_error_and_polygon_form_are_refused(tmp_path: Path) -> None:
    """An engine error, an empty polygon and more than one part are refused."""
    _install_road(tmp_path)

    class _Fails(_HandEngine):
        def polygon(self, request: AreaRequest, road: bytes) -> bytes:
            raise RuntimeError("SYN-engine")

    with pytest.raises(AreaError) as failed:
        produce_areas(
            _Fails(_square()), (_request(),), cache=tmp_path, frame_box=_FRAME
        )
    assert failed.value.reason == "engine_failed"
    with pytest.raises(AreaError) as empty:
        produce_areas(_HandEngine(b""), (_request(),), cache=tmp_path, frame_box=_FRAME)
    assert empty.value.reason == "area_polygon_form"
    other = (
        (51.60, 25.30),
        (51.61, 25.30),
        (51.61, 25.31),
        (51.60, 25.31),
        (51.60, 25.30),
    )
    parts = MultiPolygon([Polygon(_RING), Polygon(other)])
    with pytest.raises(AreaError) as many:
        produce_areas(
            _HandEngine(parts.wkb), (_request(),), cache=tmp_path, frame_box=_FRAME
        )
    assert many.value.reason == "area_polygon_form"
    hole = (
        (51.502, 25.302),
        (51.504, 25.302),
        (51.504, 25.304),
        (51.502, 25.304),
        (51.502, 25.302),
    )
    holed = Polygon(_RING, [hole])
    produce_areas(
        _HandEngine(holed.wkb),
        (_request(),),
        cache=tmp_path,
        frame_box=_FRAME,
    )
    stored = _provider(tmp_path).area(*_walk_10())
    polygon = load_wkb(stored.wkb)
    assert polygon.covers(Point(51.505, 25.305))
    assert not polygon.covers(Point(51.503, 25.303))


def test_second_run_is_byte_identical_and_rebuild_catches_one_vertex(
    tmp_path: Path,
) -> None:
    """The same inputs write the same bytes. One moved vertex fails the rebuild."""
    _install_road(tmp_path)
    engine = _HandEngine(_square())
    first = produce_areas(engine, (_request(),), cache=tmp_path, frame_box=_FRAME)
    before = _snapshot(tmp_path)
    second = produce_areas(engine, (_request(),), cache=tmp_path, frame_box=_FRAME)
    assert second.read_bytes() == first.read_bytes()
    assert _snapshot(tmp_path) == before
    verify_areas(engine, cache=tmp_path, frame_box=_FRAME)
    path = tmp_path / "places_s2_t06" / "areas" / "SYN-POINT.walk.10.json"
    loaded = json.loads(path.read_text(encoding="utf-8"))
    moved = (
        (51.50, 25.30),
        (51.52, 25.30),
        (51.51, 25.31),
        (51.50, 25.31),
        (51.50, 25.30),
    )
    loaded["polygon_wkb_hex"] = Polygon(moved).wkb.hex()
    body = json.dumps(loaded, sort_keys=True, separators=(",", ":")).encode("utf-8")
    path.write_bytes(body)
    manifest = json.loads(first.read_text(encoding="utf-8"))
    manifest["files"][0]["sha256"] = sha256_hex(body)
    first.write_bytes(
        json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode("utf-8")
    )
    with pytest.raises(AreaError) as caught:
        verify_areas(engine, cache=tmp_path, frame_box=_FRAME)
    assert caught.value.reason == "area_rebuild_differs"


def _walk_10() -> tuple[str, ReviewedPoint, AreaMode, AreaCutoff]:
    return (
        "SYN-POINT",
        ReviewedPoint(51.50, 25.30),
        AreaMode.WALK,
        AreaCutoff.MINUTES_10,
    )


def _request() -> AreaRequest:
    return AreaRequest(
        "SYN-POINT", "51.500000", "25.300000", AreaMode.WALK, AreaCutoff.MINUTES_10
    )


def _square() -> bytes:
    return bytes(Polygon(_RING).wkb)


def _outside_hex() -> str:
    ring = ((51.0, 25.0), (52.0, 25.0), (52.0, 26.0), (51.0, 26.0), (51.0, 25.0))
    return Polygon(ring).wkb.hex()


def _areas(cache: Path) -> Path:
    path = cache / "places_s2_t06" / "areas"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _install_road(cache: Path) -> str:
    from custodian.tests.snapshot_fixture import road

    return road(cache, b"SYN-ROAD")


def _write_valid(cache: Path, **change: object) -> None:
    payload: dict[str, object] = {
        "cutoff_minutes": 10,
        "engine_version": ENGINE_PIN,
        "graph_hash": sha256_hex(b"SYN-ROAD"),
        "inputs_hash": hashlib.sha256(_REQUEST_TEXT.encode("utf-8")).hexdigest(),
        "lat": "25.300000",
        "lon": "51.500000",
        "method_version": METHOD_VERSION,
        "mode": "walk",
        "point_key": "SYN-POINT",
        "polygon_wkb_hex": _square().hex(),
    }
    payload.update(change)
    body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    areas = _areas(cache)
    name = "SYN-POINT.walk.10.json"
    (areas / name).write_bytes(body)
    _manifest(areas, name, sha256_hex(body), sha256_hex(b"SYN-ROAD"))


def _provider(cache: Path) -> FileAreaProvider:
    return FileAreaProvider(cache, _FRAME)


def _snapshot(cache: Path) -> dict[str, bytes]:
    directory = cache / "places_s2_t06" / "areas"
    return {path.name: path.read_bytes() for path in sorted(directory.iterdir())}
