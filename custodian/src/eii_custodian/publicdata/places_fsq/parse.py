"""Read one local places file into source fields. Nothing is translated."""

from __future__ import annotations

import math
import re
import struct
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

from eii_custodian.publicdata.places_fsq.errors import PlacesFsqError
from eii_custodian.publicdata.places_fsq.select import FrameBox

_SIX = Decimal("0.000001")
_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
_AXIS_TOLERANCE = 1e-7
_LON = (-180.0, 180.0)
_LAT = (-90.0, 90.0)
_REQUIRED = (
    "fsq_place_id",
    "name",
    "latitude",
    "longitude",
    "country",
    "date_created",
    "date_refreshed",
    "date_closed",
    "fsq_category_ids",
    "fsq_category_labels",
    "geometry",
)
_OPTIONAL = frozenset(
    {
        "address",
        "locality",
        "region",
        "postcode",
        "admin_region",
        "post_town",
        "po_box",
        "tel",
        "website",
        "email",
        "facebook_id",
        "instagram",
        "twitter",
        "placemaker_url",
        "bbox",
    }
)
_POINT = 1


@dataclass(frozen=True)
class ParsedRow:
    """One source row. name_ar is null because the file has no such field."""

    fsq_place_id: str
    name: str
    name_ar: None
    category_ids: str
    category_labels: str
    lon: Decimal
    lat: Decimal
    country: str | None
    date_created: date | None
    date_refreshed: date | None
    date_closed: date | None


@dataclass(frozen=True)
class RowAccount:
    """Rows kept when both tests pass, and the mixed rows left out."""

    kept: tuple[ParsedRow, ...]
    point_not_country: int
    country_not_point: int


def parse_file(path: Path) -> tuple[ParsedRow, ...]:
    """Parse a local Parquet file of the source's shape."""
    _local(path)
    columns = _column_types(path)
    _schema(columns)
    raw = _rows(path)
    return tuple(_row(item) for item in raw)


def account_rows(rows: Sequence[ParsedRow], frame: FrameBox) -> RowAccount:
    """Keep a row only when the point is in the frame and the country is Qatar."""
    kept: list[ParsedRow] = []
    point_only = 0
    country_only = 0
    for row in rows:
        in_frame = _in_frame(row, frame)
        in_country = row.country == "QA"
        if in_frame and in_country:
            kept.append(row)
        elif in_frame:
            point_only += 1
        elif in_country:
            country_only += 1
    return RowAccount(tuple(kept), point_only, country_only)


def _local(path: Path) -> None:
    text = str(path)
    if "://" in text or ":/" in text or text.startswith("http"):
        raise PlacesFsqError("remote_path")


def _schema(columns: Mapping[str, str]) -> None:
    for name in _REQUIRED:
        if name not in columns:
            raise PlacesFsqError(name)
    for name in columns:
        if name not in _REQUIRED and name not in _OPTIONAL:
            raise PlacesFsqError(name)
    if columns["longitude"] != "DOUBLE":
        raise PlacesFsqError("longitude")
    if columns["latitude"] != "DOUBLE":
        raise PlacesFsqError("latitude")
    if columns["geometry"] != "BLOB":
        raise PlacesFsqError("geometry")
    for name in ("date_created", "date_refreshed", "date_closed"):
        if columns[name] != "VARCHAR":
            raise PlacesFsqError(name)
    for name in ("fsq_category_ids", "fsq_category_labels"):
        if columns[name] != "VARCHAR[]":
            raise PlacesFsqError(name)


def _row(item: Mapping[str, Any]) -> ParsedRow:
    longitude = _float(item.get("longitude"), "longitude")
    latitude = _float(item.get("latitude"), "latitude")
    _range(longitude, _LON, "longitude")
    _range(latitude, _LAT, "latitude")
    point = _wkb_point(item.get("geometry"))
    swapped = _close(point[0], latitude) and _close(point[1], longitude)
    same = _close(point[0], longitude) and _close(point[1], latitude)
    if swapped and not same:
        raise PlacesFsqError("axes_swapped")
    if not same:
        raise PlacesFsqError("geometry")
    categories = _categories(
        item.get("fsq_category_ids"), item.get("fsq_category_labels")
    )
    identifier = item.get("fsq_place_id")
    name = item.get("name")
    if not isinstance(identifier, str) or identifier == "":
        raise PlacesFsqError("fsq_place_id")
    if not isinstance(name, str):
        raise PlacesFsqError("name")
    country = item.get("country")
    if country is not None and not isinstance(country, str):
        raise PlacesFsqError("country")
    return ParsedRow(
        fsq_place_id=identifier,
        name=name,
        name_ar=None,
        category_ids=categories[0],
        category_labels=categories[1],
        lon=_decimal(longitude),
        lat=_decimal(latitude),
        country=country,
        date_created=_date(item.get("date_created"), "date_created"),
        date_refreshed=_date(item.get("date_refreshed"), "date_refreshed"),
        date_closed=_date(item.get("date_closed"), "date_closed"),
    )


def _categories(ids: object, labels: object) -> tuple[str, str]:
    left = _members(ids, "category_ids")
    right = _members(labels, "category_labels")
    if len(left) != len(right):
        raise PlacesFsqError("category_list_length")
    return ";".join(left), ";".join(right)


def _members(value: object, reason: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise PlacesFsqError(reason)
    found: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise PlacesFsqError(reason)
        if ";" in item:
            raise PlacesFsqError(reason)
        found.append(item)
    return tuple(found)


def _date(value: object, reason: str) -> date | None:
    if value is None:
        return None
    if not isinstance(value, str) or _DATE.fullmatch(value) is None:
        raise PlacesFsqError(reason)
    year, month, day = (int(part) for part in value.split("-"))
    try:
        return date(year, month, day)
    except ValueError as exc:
        raise PlacesFsqError(reason) from exc


def _float(value: object, reason: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PlacesFsqError(reason)
    return float(value)


def _range(value: float, bounds: tuple[float, float], reason: str) -> None:
    if value < bounds[0] or value > bounds[1]:
        raise PlacesFsqError(reason)


def _close(left: float, right: float) -> bool:
    return math.isclose(left, right, rel_tol=0.0, abs_tol=_AXIS_TOLERANCE)


def _decimal(value: float) -> Decimal:
    return Decimal(str(value)).quantize(_SIX)


def _wkb_point(value: object) -> tuple[float, float]:
    if not isinstance(value, (bytes, bytearray)) or len(value) < 21:
        raise PlacesFsqError("geometry")
    order = value[0]
    if order == 1:
        endian = "<"
    elif order == 0:
        endian = ">"
    else:
        raise PlacesFsqError("geometry")
    kind = struct.unpack_from(endian + "I", value, 1)[0]
    base = kind & 0xFF
    if base != _POINT:
        raise PlacesFsqError("geometry")
    offset = 9 if kind & 0x20000000 else 5
    if len(value) < offset + 16:
        raise PlacesFsqError("geometry")
    east, north = struct.unpack_from(endian + "dd", value, offset)
    return (east, north)


def _in_frame(row: ParsedRow, frame: FrameBox) -> bool:
    lon = float(row.lon)
    lat = float(row.lat)
    return frame.west <= lon <= frame.east and frame.south <= lat <= frame.north


def _column_types(path: Path) -> dict[str, str]:
    connection = _connect()
    described = connection.execute(
        "SELECT column_name, column_type FROM (DESCRIBE SELECT * FROM read_parquet(?))",
        [str(path)],
    ).fetchall()
    connection.close()
    found: dict[str, str] = {}
    for name, kind in described:
        if isinstance(name, str) and isinstance(kind, str):
            found[name] = kind
    return found


def _rows(path: Path) -> list[dict[str, Any]]:
    connection = _connect()
    relation = connection.execute(
        """
        SELECT fsq_place_id, name, latitude, longitude, country,
               date_created, date_refreshed, date_closed,
               fsq_category_ids, fsq_category_labels, geometry
        FROM read_parquet(?)
        """,
        [str(path)],
    )
    names = [item[0] for item in relation.description]
    found = [dict(zip(names, row, strict=True)) for row in relation.fetchall()]
    connection.close()
    return found


def _connect() -> Any:
    import duckdb

    connection = duckdb.connect()
    connection.execute("SET enable_geoparquet_conversion = false")
    return connection
