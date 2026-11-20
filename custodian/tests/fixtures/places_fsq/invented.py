"""Hand-made Parquet of the source's shape. Every place is invented."""

from __future__ import annotations

import struct
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

_COLUMNS = (
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


def point_wkb(longitude: float, latitude: float) -> bytes:
    """WKB point with longitude first, as the source stores it."""
    return struct.pack("<BIdd", 1, 1, longitude, latitude)


def bucket_listing(
    *keys: str,
    prefix: str = "fsq-os-places/",
    truncated: str = "false",
    namespace: str = "http://s3.amazonaws.com/doc/2006-03-01/",
) -> bytes:
    """Invented bucket objects and sizes; no fetched values or ETags."""
    objects = "".join(
        f"<Contents><Key>{escape(key)}</Key><Size>17</Size></Contents>" for key in keys
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f'<ListBucketResult xmlns="{namespace}"><Name>SYN-bucket</Name>'
        f"<Prefix>{escape(prefix)}</Prefix><MaxKeys>1000</MaxKeys>"
        f"<IsTruncated>{escape(truncated)}</IsTruncated><Marker/>"
        f"{objects}</ListBucketResult>"
    ).encode()


def listing(*releases: str) -> bytes:
    """A tiny bucket listing containing each supplied release's metadata."""
    return bucket_listing(
        *(f"fsq-os-places/{release}places/_metadata" for release in releases)
    )


def write_places(
    path: Path,
    rows: Sequence[Mapping[str, object]],
    extra: Mapping[str, str] | None = None,
    drop: Sequence[str] = (),
    types: Mapping[str, str] | None = None,
) -> None:
    """Write a tiny Parquet file. extra maps a planted column to a SQL type."""
    import duckdb

    added = extra or {}
    overrides = types or {}
    connection = duckdb.connect()
    kept = [column for column in _COLUMNS if column not in drop]
    names = kept + list(added)
    declared = ", ".join(f"{name} {overrides.get(name, _kind(name))}" for name in kept)
    if added:
        declared = (
            declared
            + ", "
            + ", ".join(f"{name} {kind}" for name, kind in added.items())
        )
    connection.execute(f"CREATE TABLE places ({declared})")
    placeholders = ", ".join("?" for _ in names)
    for row in rows:
        connection.execute(
            f"INSERT INTO places VALUES ({placeholders})",
            [_value(row, name) for name in names],
        )
    connection.execute("COPY places TO ? (FORMAT PARQUET)", [str(path)])
    connection.close()


def place(**overrides: object) -> dict[str, object]:
    """One invented place inside the frame, with both category lists empty."""
    longitude = float(overrides.get("longitude", 51.5))
    latitude = float(overrides.get("latitude", 25.3))
    row: dict[str, object] = {
        "fsq_place_id": "abcdabcdabcdabcdabcdabcd",
        "name": "Invented Cafe",
        "latitude": latitude,
        "longitude": longitude,
        "country": "QA",
        "date_created": "2020-01-02",
        "date_refreshed": "2024-06-01",
        "date_closed": None,
        "fsq_category_ids": [],
        "fsq_category_labels": [],
        "geometry": point_wkb(longitude, latitude),
    }
    row.update(overrides)
    return row


def _kind(column: str) -> str:
    if column in {"latitude", "longitude"}:
        return "DOUBLE"
    if column in {"fsq_category_ids", "fsq_category_labels"}:
        return "VARCHAR[]"
    if column == "geometry":
        return "BLOB"
    return "VARCHAR"


def _value(row: Mapping[str, object], name: str) -> Any:
    if name in row:
        return row[name]
    if name in {"fsq_category_ids", "fsq_category_labels"}:
        return []
    return None
