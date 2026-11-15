"""The surviving mutants of the area file round trip are killed by tests.

Every fixture is invented: an invented road, invented area files and an
invented routing engine.  The expected bytes, digests and refusal words are
worked out by hand and written down as literals; none is read back from the
module under test.
"""

from __future__ import annotations

import hashlib
import json
import locale
from collections.abc import Iterator
from contextlib import contextmanager
from decimal import ROUND_HALF_UP, localcontext
from pathlib import Path
from typing import Any, cast

import pytest
from custodian.tests.test_places_area_files import (
    _FRAME,
    _REQUEST_TEXT,
    _RING,
    _areas,
    _HandEngine,
    _install_road,
    _manifest,
    _request,
    _square,
    _walk_10,
    _write_valid,
)
from shapely import to_wkb
from shapely.geometry import Polygon

from eii_custodian.publicdata.fetch.receipts import sha256_hex
from eii_custodian.publicdata.places.area_files import (
    ENGINE_PIN,
    METHOD_VERSION,
    ROAD_KEY,
    AreaRequest,
    FileAreaProvider,
    _call_engine,
    _load_road,
    _one_ring,
    _point_inside,
    _require_polygon,
    _sha,
    canonical_bytes,
    coordinate_text,
    manifest_agrees,
    produce_areas,
    verify_areas,
)
from eii_custodian.publicdata.places.areas import (
    AreaCutoff,
    AreaError,
    AreaMode,
    AreaResult,
    ReviewedPoint,
)

_NAME = "SYN-POINT.walk.10.json"
_RETRIEVED = "2026-11-14T00:00:00Z"
_INPUTS = hashlib.sha256(_REQUEST_TEXT.encode("utf-8")).hexdigest()
_ROAD_BODY = b"SYN-ROAD"


def _wrong(value: object) -> Any:
    """A value of the wrong type, for a call whose signature forbids it."""
    return cast(Any, value)


@contextmanager
def _ascii_locale() -> Iterator[None]:
    """Run a block under the C locale, whose text encoding is ASCII."""
    saved = locale.setlocale(locale.LC_CTYPE)
    locale.setlocale(locale.LC_CTYPE, "C")
    try:
        yield
    finally:
        locale.setlocale(locale.LC_CTYPE, saved)


def _road_folder(cache: Path) -> Path:
    return cache / ROAD_KEY


def _road_receipt(digest: str, publisher: str = "SYN Publisher") -> bytes:
    """A road receipt with the real bytes of its text, not escaped."""
    payload = {
        "sha256": digest,
        "retrieved_utc": _RETRIEVED,
        "publisher": publisher,
    }
    return json.dumps(payload, ensure_ascii=False).encode("utf-8")


def _area_body(**changes: object) -> bytes:
    """A stored area file with hand-chosen fields, in field-name order."""
    payload: dict[str, object] = {
        "cutoff_minutes": 10,
        "engine_version": ENGINE_PIN,
        "graph_hash": sha256_hex(_ROAD_BODY),
        "inputs_hash": _INPUTS,
        "lat": "25.300000",
        "lon": "51.500000",
        "method_version": METHOD_VERSION,
        "mode": "walk",
        "point_key": "SYN-POINT",
        "polygon_wkb_hex": _square().hex(),
    }
    payload.update(changes)
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _stored(cache: Path, **changes: object) -> tuple[Path, str, str]:
    """A road, one area file and a manifest that all agree; folder, name, road."""
    road = _install_road(cache)
    directory = _areas(cache)
    body = _area_body(**changes)
    (directory / _NAME).write_bytes(body)
    _manifest(directory, _NAME, sha256_hex(body), road)
    return directory, _NAME, road


def _listed(cache: Path, body: bytes, digest: str | None = None) -> str:
    """Store one area file under a manifest that names the given digest."""
    road = _install_road(cache)
    directory = _areas(cache)
    (directory / _NAME).write_bytes(body)
    _manifest(directory, _NAME, digest or sha256_hex(body), road)
    return road


def _box(west: float, south: float, east: float, north: float) -> bytes:
    """A little-endian polygon of the given bounds."""
    ring = ((west, south), (east, south), (east, north), (west, north), (west, south))
    return Polygon(ring).wkb


class _FormHand:
    """A stand-in engine of the pinned version that returns one fixed value."""

    version = ENGINE_PIN

    def __init__(self, value: object) -> None:
        self.value = value

    def polygon(self, request: AreaRequest, road: bytes) -> object:
        return self.value


class _RoadHand:
    """A stand-in engine that keeps every road body it is handed."""

    version = ENGINE_PIN

    def __init__(self, polygon: bytes) -> None:
        self.polygon_bytes = polygon
        self.roads: list[object] = []

    def prepare(self, road: object) -> None:
        self.roads.append(road)

    def polygon(self, request: AreaRequest, road: bytes) -> bytes:
        return self.polygon_bytes


def test_a_tie_in_the_sixth_decimal_is_rounded_to_even() -> None:
    """0.1234565 and 0.1234575 are ties; half to even takes them down and up."""
    assert coordinate_text(0.1234565) == "0.123456"
    assert coordinate_text(0.1234575) == "0.123458"
    with localcontext() as context:
        context.rounding = ROUND_HALF_UP
        assert coordinate_text(0.1234565) == "0.123456"
        assert coordinate_text(0.1234575) == "0.123458"


def test_the_canonical_bytes_sort_their_keys_and_escape_their_text() -> None:
    row = {"point_key": "SYN-POINT", "cutoff_minutes": 10, "name_ar": "مكان"}
    assert canonical_bytes(row) == (
        b'{"cutoff_minutes":10,"name_ar":"\\u0645\\u0643\\u0627\\u0646",'
        b'"point_key":"SYN-POINT"}'
    )


def test_a_manifest_of_the_wrong_form_is_not_agreed(tmp_path: Path) -> None:
    cache = tmp_path / "cache"
    road = _install_road(cache)
    directory = _areas(cache)
    (directory / "manifest.json").write_text(
        json.dumps({"files": "SYN-NOT-A-LIST", "road_sha256": road}), encoding="utf-8"
    )
    assert manifest_agrees(cache, (_request(),), road) is False


def test_a_verification_refuses_an_engine_of_another_version(tmp_path: Path) -> None:
    cache = tmp_path / "cache"
    _install_road(cache)
    _write_valid(cache)
    with pytest.raises(AreaError) as caught:
        verify_areas(
            _HandEngine(_square(), version="0.0.1"), cache=cache, frame_box=_FRAME
        )
    assert caught.value.reason == "engine_version"


def test_a_verification_with_no_manifest_is_refused_by_name(tmp_path: Path) -> None:
    cache = tmp_path / "cache"
    _install_road(cache)
    with pytest.raises(AreaError) as caught:
        verify_areas(_HandEngine(_square()), cache=cache, frame_box=_FRAME)
    assert caught.value.reason == "area_manifest_missing"


def test_a_verification_hands_the_road_body_to_the_engine(tmp_path: Path) -> None:
    cache = tmp_path / "cache"
    _install_road(cache)
    _write_valid(cache)
    engine = _RoadHand(_square())
    verify_areas(engine, cache=cache, frame_box=_FRAME)
    assert engine.roads == [_ROAD_BODY]


def test_a_verification_of_a_missing_file_is_refused_by_name(tmp_path: Path) -> None:
    cache = tmp_path / "cache"
    road = _install_road(cache)
    _manifest(_areas(cache), _NAME, "cd" * 32, road)
    with pytest.raises(AreaError) as caught:
        verify_areas(_HandEngine(_square()), cache=cache, frame_box=_FRAME)
    assert caught.value.reason == "area_file_missing"


def test_a_verification_of_a_wrong_digest_is_refused_by_name(tmp_path: Path) -> None:
    cache = tmp_path / "cache"
    _install_road(cache)
    _write_valid(cache)
    directory = _areas(cache)
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    manifest["files"][0]["sha256"] = "cd" * 32
    (directory / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(AreaError) as caught:
        verify_areas(_HandEngine(_square()), cache=cache, frame_box=_FRAME)
    assert caught.value.reason == "area_file_digest"


def test_a_provider_refuses_a_name_the_manifest_does_not_list(tmp_path: Path) -> None:
    cache = tmp_path / "cache"
    _stored(cache)
    with pytest.raises(AreaError) as caught:
        _provider_area(cache, "SYN-OTHER")
    assert caught.value.reason == "area_file_missing"


def test_a_provider_returns_the_stored_input_hash(tmp_path: Path) -> None:
    cache = tmp_path / "cache"
    _stored(cache)
    assert FileAreaProvider(cache, _FRAME).area(*_walk_10()) == AreaResult(
        wkb=_square(),
        method_version=METHOD_VERSION,
        graph_hash=sha256_hex(_ROAD_BODY),
        inputs_hash=_INPUTS,
        engine_version=ENGINE_PIN,
        stand_in=False,
    )


def test_a_road_folder_with_no_receipt_is_refused_by_name(tmp_path: Path) -> None:
    cache = tmp_path / "cache"
    road = _install_road(cache)
    (_road_folder(cache) / f"{road}.meta.json").unlink()
    with pytest.raises(AreaError) as caught:
        _load_road(cache)
    assert caught.value.reason == "road_file_unreceipted"


def test_a_road_receipt_is_read_as_utf_8(tmp_path: Path) -> None:
    cache = tmp_path / "cache"
    road = _install_road(cache)
    receipt = _road_folder(cache) / f"{road}.meta.json"
    receipt.write_bytes(_road_receipt(road, publisher="ناشر"))
    with _ascii_locale():
        assert _load_road(cache) == (_ROAD_BODY, road)


def test_the_form_check_leaves_a_short_body_to_the_polygon_check() -> None:
    """Only a body that is not bytes, or an empty one, is refused by form."""
    assert _call_engine(_FormHand(b"XXXX"), _request(), _ROAD_BODY) == b"XXXX"
    with pytest.raises(AreaError) as caught:
        _require_polygon(b"XXXX", _FRAME)
    assert caught.value.reason == "area_polygon_form"
    for value in (b"", _wrong(None), _wrong(7)):
        with pytest.raises(AreaError) as caught:
            _call_engine(_FormHand(value), _request(), _ROAD_BODY)
        assert caught.value.reason == "area_polygon_form"


def test_a_request_on_the_frame_edge_is_inside_it() -> None:
    west, south, east, north = _FRAME
    assert _point_inside("51.200000", "25.300000", _FRAME) is True
    assert (_point_inside(str(west), str(south), _FRAME)) is True
    assert (_point_inside(str(east), str(north), _FRAME)) is True
    assert (_point_inside(str(west), str(north), _FRAME)) is True
    assert (_point_inside(str(east), str(south), _FRAME)) is True
    outside = (
        _point_inside(str(west - 0.001), str(south + 0.5), _FRAME),
        _point_inside(str(east + 0.001), str(south + 0.5), _FRAME),
        _point_inside(str(west + 0.5), str(south - 0.001), _FRAME),
        _point_inside(str(west + 0.5), str(north + 0.001), _FRAME),
    )
    assert outside == (False, False, False, False)


def test_a_request_on_the_frame_edge_is_produced(tmp_path: Path) -> None:
    cache = tmp_path / "cache"
    _install_road(cache)
    west, south, east, north = _FRAME
    corners = (
        AreaRequest(
            "SYN-WEST", str(west), str(south), AreaMode.WALK, AreaCutoff.MINUTES_10
        ),
        AreaRequest(
            "SYN-EAST", str(east), str(north), AreaMode.WALK, AreaCutoff.MINUTES_10
        ),
    )
    produce_areas(_FormHand(_square()), corners, cache=cache, frame_box=_FRAME)
    names = sorted(path.name for path in _areas(cache).iterdir())
    assert names == ["SYN-EAST.walk.10.json", "SYN-WEST.walk.10.json", "manifest.json"]


def test_a_polygon_touching_the_frame_edge_is_inside_it() -> None:
    west, south, east, north = _FRAME
    touches = (
        _require_polygon(_box(west, 25.30, west + 0.1, 25.40), _FRAME),
        _require_polygon(_box(east - 0.1, 25.30, east, 25.40), _FRAME),
        _require_polygon(_box(51.50, south, 51.60, south + 0.1), _FRAME),
        _require_polygon(_box(51.50, north - 0.1, 51.60, north), _FRAME),
    )
    assert touches == (None, None, None, None)
    spills = (
        _box(west - 0.001, 25.30, west + 0.1, 25.40),
        _box(east - 0.1, 25.30, east + 0.001, 25.40),
        _box(51.50, south - 0.001, 51.60, south + 0.1),
        _box(51.50, north - 0.1, 51.60, north + 0.001),
    )
    for spill in spills:
        with pytest.raises(AreaError) as caught:
            _require_polygon(spill, _FRAME)
        assert caught.value.reason == "area_polygon_form"


def test_the_reference_flag_of_a_big_endian_polygon_is_read() -> None:
    """Byte two carries the flag; the byte after it and the byte before do not."""
    body = to_wkb(Polygon(_RING), byte_order=0)
    assert body[0] == 0
    assert int.from_bytes(body[1:5], "big") == 3
    high = bytes([body[0], 0x20, body[2], body[3], body[4]]) + body[5:]
    low = bytes([body[0], body[1], 0x20, body[3], body[4]]) + body[5:]
    assert (_one_ring(body), _one_ring(high), _one_ring(low)) == (True, False, True)


def test_a_stored_file_that_is_not_json_is_not_agreed(tmp_path: Path) -> None:
    cache = tmp_path / "cache"
    road = _listed(cache, b"SYN-NOT-JSON")
    assert manifest_agrees(cache, (_request(),), road) is False


def test_a_stored_file_that_is_not_an_object_is_not_agreed(tmp_path: Path) -> None:
    cache = tmp_path / "cache"
    road = _listed(cache, b'["SYN-POINT", "walk", 10]')
    assert manifest_agrees(cache, (_request(),), road) is False


def test_a_stored_file_with_an_extra_field_is_refused(tmp_path: Path) -> None:
    cache = tmp_path / "cache"
    _stored(cache, invented_field="SYN-EXTRA")
    with pytest.raises(AreaError) as caught:
        FileAreaProvider(cache, _FRAME).area(*_walk_10())
    assert caught.value.reason == "area_request_mismatch"


def test_a_manifest_digest_is_sixty_four_lowercase_hexadecimal_digits(
    tmp_path: Path,
) -> None:
    assert _sha("cd" * 32) is True
    assert _sha("CD" * 32) is False
    assert _sha("z" * 64) is False
    assert _sha("cd" * 31) is False
    assert _sha(_wrong(7)) is False
    cache = tmp_path / "cache"
    road = _install_road(cache)
    directory = _areas(cache)
    body = _area_body()
    (directory / _NAME).write_bytes(body)
    _manifest(directory, _NAME, "z" * 64, road)
    assert manifest_agrees(cache, (_request(),), road) is False


def _provider_area(cache: Path, point_key: str) -> AreaResult:
    return FileAreaProvider(cache, _FRAME).area(
        point_key, ReviewedPoint(51.50, 25.30), AreaMode.WALK, AreaCutoff.MINUTES_10
    )
