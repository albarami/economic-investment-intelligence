"""Read local Overture Parquet. Geometry stays WKB bytes.

Stated limit: a swapped file that also holds rows inside the frame box as
read is not caught by the file-level axis rule.
"""

from __future__ import annotations

import json
import math
import re
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from decimal import ROUND_CEILING, ROUND_HALF_EVEN, Context, Decimal, InvalidOperation
from pathlib import Path
from typing import Any, cast

from shapely import point_on_surface
from shapely.geometry import Point
from shapely.geometry.base import BaseGeometry

from eii_custodian.publicdata.fetch.bounded import file_hash
from eii_custodian.publicdata.places import PlacesError

# PUB-47. The file metadata must name this pyspark schema version.
SCHEMA_PYSPARK = "2.0.0"
SOURCE_RELEASE = "2026-10-21.0"
_FOUR = Decimal("0.0001")
_SIX = Decimal("0.000001")
# Half-even is stated on the quantise call. This context's own rounding is
# different, so that argument is the one the call uses.
_STORED_CONTEXT = Context()
_STORED_CONTEXT.rounding = ROUND_CEILING
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
# DuckDB Foundation, Configuration, retrieved 2026-11-20:
# https://duckdb.org/docs/2.0/configuration/overview.html
# Reading/quote/body hash: docs/REFERENCE_NOTES.md, DuckDB S33/P15.
# Set off before any read; this citation establishes no real-file check.
_GEOPARQUET = "enable_geoparquet_conversion"
_PLACE_COLUMNS = (
    "id",
    "geometry",
    "confidence",
    "names",
    "sources",
    "basic_category",
)
_BUILDING_COLUMNS = ("id", "geometry")


@dataclass(frozen=True)
class RecordLevel:
    """The one source entry whose property is empty, or why there is not one."""

    entry: Mapping[str, object] | None
    reason: str


@dataclass(frozen=True)
class ReadPlace:
    """One decoded place row before attribution and the boundary test."""

    place_id: str
    name: str
    name_ar: str | None
    category: str
    lon: Decimal
    lat: Decimal
    confidence: Decimal | None
    confidence_kind: str
    source: RecordLevel
    wkb: bytes


@dataclass(frozen=True)
class FileReceipt:
    """Publisher, retrieval time and hash of one file the build reads."""

    source_key: str
    sha256: str
    retrieved_utc: str
    publisher: str


@dataclass(frozen=True)
class ReadBuilding:
    """One decoded footprint and the point on its surface."""

    building_id: str
    lon: Decimal
    lat: Decimal
    footprint_wkb: bytes


def record_level_source(sources: object) -> RecordLevel:
    """Return the single source entry whose property is empty.

    None and more than one are left out by the caller. The reason is
    ``ok``, ``absent`` or ``not_unique``.
    """
    if not isinstance(sources, list):
        return RecordLevel(None, "absent")
    found: list[Mapping[str, object]] = []
    for item in sources:
        if isinstance(item, dict) and _property_empty(item.get("property")):
            found.append(item)
    if len(found) == 0:
        return RecordLevel(None, "absent")
    if len(found) != 1:
        return RecordLevel(None, "not_unique")
    return RecordLevel(found[0], "ok")


def stored_confidence(value: float | int | Decimal) -> Decimal:
    """Round a source number to four decimal places.

    A finite ``Decimal`` is quantised to one ten-thousandth, half to even,
    on a context this function owns. A source double or an int is read from
    its shortest decimal text and quantised the same way. Not-a-number and
    the infinities are left as they are. A finite value that cannot be
    rounded to that scale is refused with ``range``.
    """
    if isinstance(value, Decimal) and value.is_finite():
        try:
            return value.quantize(
                _FOUR, rounding=ROUND_HALF_EVEN, context=_STORED_CONTEXT
            )
        except InvalidOperation as exc:
            raise PlacesError("range") from exc
    text = str(value)
    return Decimal(text).quantize(
        _FOUR, rounding=ROUND_HALF_EVEN, context=_STORED_CONTEXT
    )


def require_receipt(path: Path, receipt: FileReceipt | None) -> FileReceipt:
    """Hash the file bytes and refuse a missing or different receipt.

    The hash is taken before any Parquet read of the same path.
    """
    if receipt is None or not _receipt_complete(receipt):
        raise PlacesError("receipt_missing")
    if file_hash(path) != receipt.sha256:
        raise PlacesError("receipt_mismatch")
    return receipt


def axes_look_swapped(
    points: Sequence[tuple[float, float]],
    box: tuple[float, float, float, float],
) -> bool:
    """True when the file fits the frame box only with the axes exchanged.

    Stated limit: a swapped file that also holds rows inside the box as read
    is not caught by this rule.
    """
    if not points or any(_in_box(lon, lat, box) for lon, lat in points):
        return False
    return any(_in_box(lat, lon, box) for lon, lat in points)


def read_place_file(
    path: Path,
    arabic_tag: str,
    frame_box: tuple[float, float, float, float] | None = None,
) -> tuple[ReadPlace, ...]:
    """Compatibility tuple API; streaming callers use iter_place_file."""
    return tuple(iter_place_file(path, arabic_tag, frame_box))


def read_building_file(
    path: Path,
    frame_box: tuple[float, float, float, float] | None = None,
) -> tuple[ReadBuilding, ...]:
    """Compatibility tuple API; streaming callers use iter_building_file."""
    return tuple(iter_building_file(path, frame_box))


def iter_place_file(
    path: Path,
    arabic_tag: str,
    frame_box: tuple[float, float, float, float] | None = None,
    *,
    outside: list[int] | None = None,
) -> Iterator[ReadPlace]:
    """Validate the whole file before exposing any row to a caller."""
    if not isinstance(arabic_tag, str) or arabic_tag.strip() == "":
        raise PlacesError("arabic_tag")
    omitted = [0]

    def retain(row: ReadPlace) -> bool:
        if frame_box is not None and not _in_box(
            float(row.lon), float(row.lat), frame_box
        ):
            omitted[-1] += 1
            return False
        omitted.append(0)
        return True

    rows = tuple(
        _validated_rows(
            path,
            _PLACE_COLUMNS,
            lambda row: _place_row(row, arabic_tag),
            frame_box,
            retain if outside is not None else None,
        )
    )
    if outside is not None:
        outside.extend(omitted)
    yield from rows


def iter_building_file(
    path: Path,
    frame_box: tuple[float, float, float, float] | None = None,
) -> Iterator[ReadBuilding]:
    """Validate every footprint before exposing any row to a caller."""
    yield from _validated_rows(path, _BUILDING_COLUMNS, _building_row, frame_box)


def _source_rows(path: Path, names: Sequence[str]) -> Iterator[Sequence[object]]:
    """Keep the original projection and scan order, in bounded cursor batches."""
    connection = _connect()
    try:
        _require_schema(connection, path)
        columns = _column_names(connection, path)
        if any(name not in columns for name in names):
            raise PlacesError("missing_column")
        listed = ", ".join(names)
        cursor = connection.execute(
            f"SELECT {listed} FROM read_parquet(?)", [str(path)]
        )
        while batch := cursor.fetchmany(2048):
            yield from batch
    finally:
        connection.close()


def _validated_rows[T: (ReadPlace, ReadBuilding)](
    path: Path,
    names: Sequence[str],
    decode: Callable[[Sequence[object]], T],
    frame_box: tuple[float, float, float, float] | None,
    retain: Callable[[T], bool] | None = None,
) -> Iterator[T]:
    """One decode pass; raw, decode, deferred box/retain fault, swap, then rows.

    Retention touches only file-local state. No row or summary is published until
    every raw batch has been read and all file-wide validation has succeeded.
    """
    error: Exception | None = None
    deferred: Exception | None = None
    inside = False
    exchanged = False
    kept: list[T] = []
    for raw in _source_rows(path, names):
        if error is not None:
            continue
        try:
            row = decode(raw)
        except Exception as exc:
            error = exc
            continue
        if deferred is not None:
            continue
        try:
            if frame_box is not None:
                lon, lat = float(row.lon), float(row.lat)
                inside = inside or _in_box(lon, lat, frame_box)
                exchanged = exchanged or _in_box(lat, lon, frame_box)
            if retain is None or retain(row):
                kept.append(row)
        except Exception as exc:
            deferred = exc
    if error is not None:
        raise error
    if deferred is not None:
        raise deferred
    if not inside and exchanged:
        raise PlacesError("axis_swapped")
    yield from kept


def _connect() -> Any:
    """Open DuckDB with GeoParquet conversion off and no extension loaded."""
    import duckdb

    connection: Any = duckdb.connect()
    connection.execute(f"SET {_GEOPARQUET} = false")
    return connection


def building_source_rows(path: Path) -> Iterator[dict[str, Any]]:
    """Project verified building fields in bounded connection-cursor batches.

    This leaves the showcase reader and its rounding unchanged. Optional fields
    are read only for coverage counts; no numeric field mapping is activated.
    The connection seam and metadata queries are those used by both readers.
    """
    import duckdb

    connection = _connect()
    try:
        _require_schema(connection, path)
        _building_crs(connection, path)
        columns = _column_names(connection, path)
        if not {"id", "geometry"} <= columns:
            raise PlacesError("missing_column")
        names = ("id", "geometry", "height", "num_floors", "is_underground", "sources")
        projected = ", ".join(
            name if name in columns else "NULL AS " + name for name in names
        )
        cursor = connection.execute(
            f"SELECT {projected} FROM read_parquet(?)", [str(path)]
        )
        while True:
            batch = cursor.fetchmany(2048)
            if not batch:
                break
            for row in batch:
                yield dict(zip(names, row, strict=True))
    except duckdb.Error:
        raise PlacesError("parquet") from None
    finally:
        connection.close()


def geoparquet_metadata(connection: Any, path: Path) -> Any:
    """Decode the shared geo footer; callers own their structural refusals."""
    rows = connection.execute(
        "SELECT key, value FROM parquet_kv_metadata(?)", [str(path)]
    ).fetchall()
    metadata = {
        key.decode() if isinstance(key, bytes) else str(key): value
        for key, value in rows
    }
    return json.loads(metadata["geo"])


def _building_crs(connection: Any, path: Path) -> None:
    """GeoParquet's absent CRS means CRS84; explicit unknown/lat-first refuses."""
    try:
        geo = geoparquet_metadata(connection, path)
        if geo["primary_column"] != "geometry":
            raise ValueError
        column = geo["columns"]["geometry"]
        if column["encoding"] != "WKB":
            raise ValueError
        if "crs" not in column:
            return
        crs = column["crs"]
        if not isinstance(crs, dict) or crs.get("id") != {
            "authority": "OGC",
            "code": "CRS84",
        }:
            raise ValueError
        axes = crs.get("coordinate_system", {}).get("axis")
        if axes is not None and [axis["direction"] for axis in axes] != [
            "east",
            "north",
        ]:
            raise ValueError
    except (KeyError, TypeError, ValueError, AttributeError):
        raise PlacesError("crs") from None


# Public reuse names; legacy bindings and monkeypatch seams remain intact.
connect_parquet = _connect
require_crs84 = _building_crs


def _require_schema(connection: Any, path: Path) -> None:
    rows = connection.execute(
        "SELECT key, value FROM parquet_kv_metadata(?)",
        [str(path)],
    ).fetchall()
    found = ""
    for key, value in rows:
        text = key.decode("utf-8") if isinstance(key, bytes) else str(key)
        if text != "schema_versions":
            continue
        found = value.decode("utf-8") if isinstance(value, bytes) else str(value)
    if found == "":
        raise PlacesError("schema_versions")
    try:
        loaded = json.loads(found)
    except json.JSONDecodeError as exc:
        raise PlacesError("schema_versions") from exc
    if not isinstance(loaded, dict):
        raise PlacesError("schema_versions")
    if loaded.get("overture-schema-pyspark") != SCHEMA_PYSPARK:
        raise PlacesError("schema_versions")


def _column_names(connection: Any, path: Path) -> set[str]:
    described = connection.execute(
        "DESCRIBE SELECT * FROM read_parquet(?)",
        [str(path)],
    ).fetchall()
    return {str(row[0]) for row in described}


def _place_row(row: Sequence[object], arabic_tag: str) -> ReadPlace:
    place_id, geometry, confidence, names, sources, category = row
    shape = _shape(geometry)
    if not isinstance(shape, Point):
        raise PlacesError("geometry_type")
    _assert_axis(shape)
    if not isinstance(place_id, str) or place_id.strip() == "":
        raise PlacesError("place_id")
    if not isinstance(category, str):
        category = ""
    stored, kind = _confidence(confidence)
    return ReadPlace(
        place_id=place_id,
        name=_primary(names),
        name_ar=_arabic(names, arabic_tag),
        category=category,
        lon=_six(shape.x),
        lat=_six(shape.y),
        confidence=stored,
        confidence_kind=kind,
        source=record_level_source(sources),
        wkb=geometry_wkb(shape),
    )


def _building_row(row: Sequence[object]) -> ReadBuilding:
    building_id, geometry = row
    shape = _shape(geometry)
    if shape.geom_type not in {"Polygon", "MultiPolygon"}:
        raise PlacesError("geometry_type")
    _assert_axis(shape)
    if not isinstance(building_id, str) or building_id.strip() == "":
        raise PlacesError("building_id")
    pin = point_on_surface(shape)
    if not isinstance(pin, Point):
        raise PlacesError("geometry_type")
    _assert_axis(pin)
    return ReadBuilding(
        building_id=building_id,
        lon=_six(pin.x),
        lat=_six(pin.y),
        footprint_wkb=geometry_wkb(shape),
    )


def geometry_wkb(shape: BaseGeometry) -> bytes:
    """Return WKB bytes. The installed Shapely property is absent from the stub."""
    raw = cast(Any, shape).wkb
    if isinstance(raw, memoryview):
        raw = raw.tobytes()
    if not isinstance(raw, bytes):
        raise PlacesError("geometry_wkb")
    return raw


def geometry_bounds(shape: BaseGeometry) -> tuple[float, float, float, float]:
    """Return minx, miny, maxx, maxy. The stub does not declare bounds."""
    raw = cast(Any, shape).bounds
    if not isinstance(raw, tuple) or len(raw) != 4:
        raise PlacesError("axis_range")
    return (float(raw[0]), float(raw[1]), float(raw[2]), float(raw[3]))


def decode_wkb(value: bytes) -> BaseGeometry:
    """Decode WKB. ``from_wkb`` is not declared on the Shapely stub."""
    import shapely

    module = cast(Any, shapely)
    geos_error = cast(type[BaseException], module.errors.GEOSException)
    try:
        loaded = module.from_wkb(value)
    except geos_error as exc:
        raise PlacesError("geometry_wkb") from exc
    if not isinstance(loaded, BaseGeometry):
        raise PlacesError("geometry_wkb")
    return loaded


def _shape(value: object) -> BaseGeometry:
    if isinstance(value, memoryview):
        value = value.tobytes()
    if not isinstance(value, bytes):
        raise PlacesError("geometry_not_bytes")
    return decode_wkb(value)


def _assert_axis(shape: BaseGeometry) -> None:
    minx, miny, maxx, maxy = geometry_bounds(shape)
    if minx < -180 or maxx > 180 or miny < -90 or maxy > 90:
        raise PlacesError("axis_range")


def _primary(names: object) -> str:
    if not isinstance(names, dict):
        return ""
    primary = names.get("primary")
    if not isinstance(primary, str):
        return ""
    return primary


def _arabic(names: object, tag: str) -> str | None:
    if not isinstance(names, dict):
        return None
    common = names.get("common")
    if not isinstance(common, dict):
        return None
    value = common.get(tag)
    if not isinstance(value, str) or value.strip() == "":
        return None
    return value


def _confidence(value: object) -> tuple[Decimal | None, str]:
    if value is None or isinstance(value, bool):
        return None, "null"
    if isinstance(value, Decimal):
        if not value.is_finite():
            return None, "range"
    elif isinstance(value, int | float):
        if isinstance(value, float) and not math.isfinite(value):
            return None, "range"
    else:
        return None, "null"
    if value < 0 or value > 1:
        return None, "range"
    stored = stored_confidence(value)
    if stored == 0:
        stored = stored.copy_abs()
    return stored, "ok"


def _receipt_complete(receipt: FileReceipt) -> bool:
    return (
        receipt.source_key != ""
        and receipt.retrieved_utc != ""
        and receipt.publisher != ""
        and _SHA256.fullmatch(receipt.sha256) is not None
    )


def _refuse_swapped(
    points: Sequence[tuple[float, float]],
    box: tuple[float, float, float, float] | None,
) -> None:
    if box is not None and axes_look_swapped(points, box):
        raise PlacesError("axis_swapped")


def _in_box(lon: float, lat: float, box: tuple[float, float, float, float]) -> bool:
    west, south, east, north = box
    return west <= lon <= east and south <= lat <= north


def load_boundary_buildings(
    paths: Sequence[Path],
    receipts: Sequence[FileReceipt],
    boundary: BaseGeometry,
) -> tuple[tuple[ReadBuilding, ...], tuple[FileReceipt, ...], int]:
    """Read every buildings file. An outside footprint is counted, not kept."""
    listed = tuple(paths)
    recorded = tuple(receipts)
    if len(listed) != len(recorded):
        raise PlacesError("receipt_missing")
    box = geometry_bounds(boundary)
    seen: set[str] = set()
    kept: list[ReadBuilding] = []
    outside = 0
    for path, receipt in zip(listed, recorded, strict=True):
        require_receipt(path, receipt)
        duplicate = False
        box_outside = 0

        def retain(row: ReadBuilding) -> bool:
            nonlocal duplicate, box_outside
            if row.building_id in seen:
                duplicate = True
            seen.add(row.building_id)
            if not _in_box(float(row.lon), float(row.lat), box):
                box_outside += 1
                return False
            return True

        rows = tuple(
            _validated_rows(path, _BUILDING_COLUMNS, _building_row, box, retain)
        )
        if duplicate:
            raise PlacesError("building_duplicate")
        outside += box_outside
        for row in rows:
            if boundary.covers(Point(float(row.lon), float(row.lat))):
                kept.append(row)
            else:
                outside += 1
    return tuple(kept), recorded, outside


def write_place_points(
    directory: Path,
    places: Sequence[tuple[str, str, str, str]],
    buildings: Sequence[tuple[str, str, str, str]],
) -> None:
    """Write the points file. The caller has already dropped outside buildings."""
    rows = [
        {"source_id": source, "record_key": key, "lon": lon, "lat": lat}
        for source, key, lon, lat in (*places, *buildings)
    ]
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / "places_s2_t06"
    target.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(rows, sort_keys=True) + "\n"
    (target / "place_points.json").write_text(payload, encoding="utf-8")


def _six(value: float) -> Decimal:
    return Decimal(str(value)).quantize(_SIX, rounding=ROUND_HALF_EVEN)


def _property_empty(value: object) -> bool:
    if value is None:
        return True
    return isinstance(value, str) and value.strip() == ""
