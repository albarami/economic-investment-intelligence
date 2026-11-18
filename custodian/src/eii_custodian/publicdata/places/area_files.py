"""Area-file form, hashes and the file provider. This module imports no engine."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal
from pathlib import Path
from typing import Protocol

from shapely.geometry import Polygon

from eii_custodian.publicdata.fetch.receipts import sha256_hex
from eii_custodian.publicdata.fetch.snapshots import (
    SnapshotError,
    read_snapshot,
    reviewed_selections,
)
from eii_custodian.publicdata.places import PlacesError
from eii_custodian.publicdata.places.areas import (
    AreaCutoff,
    AreaError,
    AreaMode,
    AreaResult,
    ReviewedPoint,
)
from eii_custodian.publicdata.places.read import decode_wkb, geometry_bounds

METHOD_VERSION = "places.area.v1"
ENGINE_PIN = "3.9.1"
AREAS_RELATIVE = Path("places_s2_t06") / "areas"
ROAD_KEY = "roads_osm"
MANIFEST_NAME = "manifest.json"
_SIX = Decimal("0.000001")
_WKB_LITTLE = 1
_WKB_BIG = 0
_WKB_SRID_FLAG = 0x20000000
_SHA = 64
_HEX = frozenset("0123456789abcdef")
_FILE_KEYS = (
    "cutoff_minutes",
    "engine_version",
    "graph_hash",
    "inputs_hash",
    "lat",
    "lon",
    "method_version",
    "mode",
    "point_key",
    "polygon_wkb_hex",
)


@dataclass(frozen=True)
class AreaRequest:
    """One closed request. Coordinates are decimal text of six places."""

    point_key: str
    lon: str
    lat: str
    mode: AreaMode
    cutoff: AreaCutoff


class PolygonEngine(Protocol):
    """A routing engine the producer calls. This module does not import one."""

    version: str

    def polygon(self, request: AreaRequest, road: bytes) -> bytes:
        """Return one polygon as WKB."""


def coordinate_text(value: float) -> str:
    """Return six decimal places, half to even, from the shortest decimal text."""
    quantized = Decimal(str(value)).quantize(_SIX, rounding=ROUND_HALF_EVEN)
    return f"{quantized:.6f}"


def canonical_bytes(payload: Mapping[str, object]) -> bytes:
    """Sorted keys, one line, UTF-8."""
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")


def request_payload(request: AreaRequest) -> dict[str, object]:
    """The canonical request the inputs hash covers."""
    return {
        "cutoff_minutes": request.cutoff.value,
        "method_version": METHOD_VERSION,
        "mode": request.mode.value,
        "point": {"lat": request.lat, "lon": request.lon},
        "point_key": request.point_key,
    }


def inputs_hash(request: AreaRequest) -> str:
    """SHA-256 of the canonical request."""
    return sha256_hex(canonical_bytes(request_payload(request)))


def area_filename(request: AreaRequest) -> str:
    """One name for one point, mode and cut-off."""
    return f"{request.point_key}.{request.mode.value}.{request.cutoff.value}.json"


def manifest_agrees(
    cache: Path, requests: Sequence[AreaRequest], road_sha: str
) -> bool:
    """True when the manifest names these requests and the road receipt."""
    path = _areas(cache) / MANIFEST_NAME
    if not path.is_file():
        return False
    try:
        listing, listed_road = _read_manifest(path.read_bytes())
    except AreaError:
        return False
    expected = {area_filename(request) for request in requests}
    if listed_road != road_sha or set(listing) != expected:
        return False
    stored_for = {area_filename(request): request for request in requests}
    for name, request in stored_for.items():
        body_path = path.parent / name
        if not body_path.is_file():
            return False
        if not _stored_request(body_path.read_bytes(), request):
            return False
    return True


def road_receipt(cache: Path) -> str:
    """The road file's receipt digest, or the road refusal the producer already uses."""
    _body, digest = _load_road(cache)
    return digest


def open_pinned_engine() -> PolygonEngine:
    """The pinned engine, or engine_package_missing when it cannot be imported."""
    try:
        from eii_custodian.publicdata.places.area_engine import PinnedEngine
    except ImportError as exc:
        raise AreaError("engine_package_missing") from exc
    return PinnedEngine()


def produce_areas(
    engine: PolygonEngine,
    requests: Sequence[AreaRequest],
    *,
    cache: Path,
    frame_box: tuple[float, float, float, float],
) -> Path:
    """Write one area file per request and the manifest. The engine is an argument."""
    road, graph_hash = _load_road(cache)
    for request in requests:
        if not _point_inside(request.lon, request.lat, frame_box):
            raise AreaError("point_outside_frame")
    if engine.version != ENGINE_PIN:
        raise AreaError("engine_version")
    _prepare(engine, road)
    directory = _areas(cache)
    directory.mkdir(parents=True, exist_ok=True)
    listed: list[tuple[str, str]] = []
    for request in requests:
        wkb = _call_engine(engine, request, road)
        _require_polygon(wkb, frame_box)
        body = canonical_bytes(_area_payload(request, wkb, graph_hash))
        name = area_filename(request)
        (directory / name).write_bytes(body)
        listed.append((name, sha256_hex(body)))
    manifest = directory / MANIFEST_NAME
    manifest.write_bytes(_manifest_bytes(listed, graph_hash))
    return manifest


def verify_areas(
    engine: PolygonEngine,
    *,
    cache: Path,
    frame_box: tuple[float, float, float, float],
) -> None:
    """Rebuild every area from the cache and compare bytes."""
    road, graph_hash = _load_road(cache)
    if engine.version != ENGINE_PIN:
        raise AreaError("engine_version")
    directory = _areas(cache)
    manifest = directory / MANIFEST_NAME
    if not manifest.is_file():
        raise AreaError("area_manifest_missing")
    listing, _road_sha = _read_manifest(manifest.read_bytes())
    _prepare(engine, road)
    for name, digest in sorted(listing.items()):
        path = directory / name
        if not path.is_file():
            raise AreaError("area_file_missing")
        stored = path.read_bytes()
        if sha256_hex(stored) != digest:
            raise AreaError("area_file_digest")
        request = _request_of(stored)
        wkb = _call_engine(engine, request, road)
        _require_polygon(wkb, frame_box)
        rebuilt = canonical_bytes(_area_payload(request, wkb, graph_hash))
        if rebuilt != stored:
            raise AreaError("area_rebuild_differs")


class FileAreaProvider:
    """Return stand_in false only after every area-file check holds."""

    def __init__(
        self,
        cache: Path,
        frame_box: tuple[float, float, float, float],
        requests: Sequence[AreaRequest] = (),
    ) -> None:
        self._cache = cache
        self._frame = frame_box
        self._requests = {
            (item.point_key, item.mode, item.cutoff): item for item in requests
        }

    def area(
        self,
        point_key: str,
        point: ReviewedPoint,
        mode: AreaMode,
        cutoff: AreaCutoff,
    ) -> AreaResult:
        """Read one area file. A failed check raises AreaError and returns nothing."""
        directory = _areas(self._cache)
        manifest = directory / MANIFEST_NAME
        if not manifest.is_file():
            raise AreaError("area_manifest_missing")
        listing, road_sha = _read_manifest(manifest.read_bytes())
        name = f"{point_key}.{mode.value}.{cutoff.value}.json"
        if name not in listing:
            raise AreaError("area_file_missing")
        path = directory / name
        if not path.is_file():
            raise AreaError("area_file_missing")
        body = path.read_bytes()
        if sha256_hex(body) != listing[name]:
            raise AreaError("area_file_digest")
        loaded = _object(body)
        stand_in = "stand_in" in loaded
        request = self._requests.get((point_key, mode, cutoff))
        if request is None:
            request = AreaRequest(
                point_key,
                coordinate_text(point.lon),
                coordinate_text(point.lat),
                mode,
                cutoff,
            )
        if not _request_matches(loaded, request):
            raise AreaError("area_request_mismatch")
        expected = inputs_hash(request)
        if (
            loaded.get("inputs_hash") != expected
            or loaded.get("method_version") != METHOD_VERSION
        ):
            raise AreaError("area_inputs_hash")
        receipt = _receipt_sha(self._cache)
        if loaded.get("graph_hash") != receipt or road_sha != receipt:
            raise AreaError("area_graph_unreceipted")
        if loaded.get("engine_version") != ENGINE_PIN:
            raise AreaError("area_engine_version")
        wkb = _wkb(loaded.get("polygon_wkb_hex"))
        _require_polygon(wkb, self._frame)
        if stand_in:
            raise AreaError("area_stand_in")
        return AreaResult(wkb, METHOD_VERSION, receipt, expected, ENGINE_PIN, False)


def _areas(cache: Path) -> Path:
    return cache / AREAS_RELATIVE


def _load_road(cache: Path) -> tuple[bytes, str]:
    digest = reviewed_selections(cache).get(ROAD_KEY)
    if digest is None:
        raise AreaError("road_file_missing")
    try:
        snapshot = read_snapshot(cache / ROAD_KEY, digest)
        if snapshot.sidecar.get("key") != ROAD_KEY:
            raise AreaError("road_file_unreceipted")
        return snapshot.body, snapshot.sha256
    except SnapshotError:
        raise AreaError("road_file_unreceipted") from None


def _receipt_sha(cache: Path) -> str:
    try:
        _body, digest = _load_road(cache)
    except AreaError as exc:
        raise AreaError("area_graph_unreceipted") from exc
    return digest


def _prepare(engine: PolygonEngine, road: bytes) -> None:
    prepare = getattr(engine, "prepare", None)
    if not callable(prepare):
        return
    try:
        prepare(road)
    except (OSError, RuntimeError, ValueError, KeyError, TypeError, IndexError) as exc:
        raise AreaError("engine_failed") from exc


def _call_engine(engine: PolygonEngine, request: AreaRequest, road: bytes) -> bytes:
    try:
        wkb = engine.polygon(request, road)
    except (OSError, RuntimeError, ValueError, KeyError, TypeError, IndexError) as exc:
        raise AreaError("engine_failed") from exc
    if not isinstance(wkb, bytes) or wkb == b"":
        raise AreaError("area_polygon_form")
    return wkb


def _point_inside(
    lon: str, lat: str, frame_box: tuple[float, float, float, float]
) -> bool:
    west, south, east, north = frame_box
    x = float(lon)
    y = float(lat)
    return west <= x <= east and south <= y <= north


def _require_polygon(wkb: bytes, frame_box: tuple[float, float, float, float]) -> None:
    try:
        shape = decode_wkb(wkb)
    except PlacesError as exc:
        raise AreaError("area_polygon_form") from exc
    if not isinstance(shape, Polygon) or shape.is_empty or not shape.is_valid:
        raise AreaError("area_polygon_form")
    if not _one_ring(wkb):
        raise AreaError("area_polygon_form")
    west, south, east, north = frame_box
    minx, miny, maxx, maxy = geometry_bounds(shape)
    if minx < west or maxx > east or miny < south or maxy > north:
        raise AreaError("area_polygon_form")


def _one_ring(wkb: bytes) -> bool:
    """True for a known byte order and no SRID flag. A hole stays inside the polygon."""
    order = wkb[0]
    if order == _WKB_LITTLE:
        kind = int.from_bytes(wkb[1:5], "little")
    elif order == _WKB_BIG:
        kind = int.from_bytes(wkb[1:5], "big")
    else:
        return False
    return (kind & _WKB_SRID_FLAG) == 0


def _stored_request(body: bytes, request: AreaRequest) -> bool:
    """True when the file's point, mode and cut-off are this run's request."""
    try:
        loaded = json.loads(body.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError):
        return False
    if not isinstance(loaded, dict):
        return False
    return (
        loaded.get("lon") == request.lon
        and loaded.get("lat") == request.lat
        and loaded.get("mode") == request.mode.value
        and loaded.get("cutoff_minutes") == request.cutoff.value
    )


def _area_payload(
    request: AreaRequest, wkb: bytes, graph_hash: str
) -> dict[str, object]:
    return {
        "cutoff_minutes": request.cutoff.value,
        "engine_version": ENGINE_PIN,
        "graph_hash": graph_hash,
        "inputs_hash": inputs_hash(request),
        "lat": request.lat,
        "lon": request.lon,
        "method_version": METHOD_VERSION,
        "mode": request.mode.value,
        "point_key": request.point_key,
        "polygon_wkb_hex": wkb.hex(),
    }


def _manifest_bytes(listed: Sequence[tuple[str, str]], road_sha: str) -> bytes:
    files = [{"name": name, "sha256": digest} for name, digest in sorted(listed)]
    return canonical_bytes({"files": files, "road_sha256": road_sha})


def _read_manifest(body: bytes) -> tuple[dict[str, str], str]:
    try:
        loaded = json.loads(body.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise AreaError("area_manifest_form") from exc
    if not isinstance(loaded, dict) or set(loaded) != {"files", "road_sha256"}:
        raise AreaError("area_manifest_form")
    road = loaded["road_sha256"]
    files = loaded["files"]
    if not _sha(road) or not isinstance(files, list):
        raise AreaError("area_manifest_form")
    found: dict[str, str] = {}
    for item in files:
        if not isinstance(item, dict) or set(item) != {"name", "sha256"}:
            raise AreaError("area_manifest_form")
        name = item["name"]
        digest = item["sha256"]
        if not isinstance(name, str) or name == "" or "/" in name or not _sha(digest):
            raise AreaError("area_manifest_form")
        if name in found:
            raise AreaError("area_manifest_form")
        found[name] = digest
    return found, road


def _object(body: bytes) -> dict[str, object]:
    try:
        loaded = json.loads(body.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise AreaError("area_request_mismatch") from exc
    if not isinstance(loaded, dict):
        raise AreaError("area_request_mismatch")
    return loaded


def _request_matches(loaded: Mapping[str, object], request: AreaRequest) -> bool:
    allowed = set(_FILE_KEYS) | {"stand_in"}
    if not set(loaded) <= allowed or not set(_FILE_KEYS) <= set(loaded):
        return False
    return (
        loaded.get("point_key") == request.point_key
        and loaded.get("lon") == request.lon
        and loaded.get("lat") == request.lat
        and loaded.get("mode") == request.mode.value
        and loaded.get("cutoff_minutes") == request.cutoff.value
    )


def _request_of(body: bytes) -> AreaRequest:
    loaded = _object(body)
    mode = loaded.get("mode")
    cutoff = loaded.get("cutoff_minutes")
    point_key = loaded.get("point_key")
    lon = loaded.get("lon")
    lat = loaded.get("lat")
    if mode not in {item.value for item in AreaMode}:
        raise AreaError("area_request_mismatch")
    if cutoff not in {item.value for item in AreaCutoff}:
        raise AreaError("area_request_mismatch")
    if (
        not isinstance(point_key, str)
        or not isinstance(lon, str)
        or not isinstance(lat, str)
    ):
        raise AreaError("area_request_mismatch")
    return AreaRequest(
        point_key,
        lon,
        lat,
        AreaMode(mode),
        AreaCutoff(cutoff),
    )


def _wkb(value: object) -> bytes:
    if not isinstance(value, str):
        raise AreaError("area_polygon_form")
    try:
        return bytes.fromhex(value)
    except ValueError as exc:
        raise AreaError("area_polygon_form") from exc


def _sha(value: object) -> bool:
    return isinstance(value, str) and len(value) == _SHA and set(value) <= _HEX
