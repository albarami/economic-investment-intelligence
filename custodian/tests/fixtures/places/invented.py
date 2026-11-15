"""Hand-made Parquet of the Overture shape. Every place and building is invented."""

from __future__ import annotations

import json
import struct
from collections.abc import Mapping, Sequence
from pathlib import Path

_SCHEMA = {"overture-schema-pyspark": "2.0.0"}


def point_wkb(longitude: float, latitude: float) -> bytes:
    """WKB point, little-endian, longitude then latitude."""
    return struct.pack("<BIdd", 1, 1, longitude, latitude)


def place_row(**overrides: object) -> dict[str, object]:
    """One invented place inside the frame box."""
    longitude = float(overrides.get("lon", 51.5))
    latitude = float(overrides.get("lat", 25.3))
    row: dict[str, object] = {
        "id": "SYN-P-A",
        "geometry": point_wkb(longitude, latitude),
        "confidence": 0.8,
        "names": {"primary": "SYN Cafe", "common": {"ar": "مقهى تجريبي"}},
        "sources": [{"property": "", "dataset": "syn-source", "license": None}],
        "basic_category": "syn_restaurant",
        "lon": longitude,
        "lat": latitude,
    }
    if "place_id" in overrides and "id" not in overrides:
        row["id"] = overrides["place_id"]
    row.update(overrides)
    if "place_id" in row and "id" not in overrides:
        row["id"] = row["place_id"]
    if "lon" in overrides or "lat" in overrides:
        row["geometry"] = point_wkb(float(row["lon"]), float(row["lat"]))
    return row


def write_places(
    path: Path,
    rows: Sequence[Mapping[str, object]],
    *,
    schema_version: str = "2.0.0",
    drop: Sequence[str] = (),
) -> None:
    """Write a tiny places Parquet file and its schema_versions footer entry."""
    import duckdb

    kept = [
        name
        for name in (
            "id",
            "geometry",
            "confidence",
            "names",
            "sources",
            "basic_category",
        )
        if name not in drop
    ]
    connection = duckdb.connect()
    declared = ", ".join(f"{name} {_kind(name)}" for name in kept)
    connection.execute(f"CREATE TABLE places ({declared})")
    placeholders = ", ".join("?" for _ in kept)
    for row in rows:
        connection.execute(
            f"INSERT INTO places VALUES ({placeholders})",
            [_cell(row, name) for name in kept],
        )
    versions = dict(_SCHEMA)
    versions["overture-schema-pyspark"] = schema_version
    connection.execute(
        "COPY places TO ? (FORMAT PARQUET, KV_METADATA {schema_versions: ?})",
        [str(path), json.dumps(versions, sort_keys=True)],
    )
    connection.close()


def _kind(column: str) -> str:
    if column == "geometry":
        return "BLOB"
    if column == "confidence":
        return "DOUBLE"
    if column == "names":
        return 'STRUCT("primary" VARCHAR, common MAP(VARCHAR, VARCHAR))'
    if column == "sources":
        return "STRUCT(property VARCHAR, dataset VARCHAR, license VARCHAR)[]"
    return "VARCHAR"


def polygon_wkb(ring: Sequence[tuple[float, float]]) -> bytes:
    """WKB polygon. The ring is closed by the caller."""
    from shapely.geometry import Polygon

    return bytes(Polygon(ring).wkb)


def building_row(
    building_id: str, ring: Sequence[tuple[float, float]]
) -> dict[str, object]:
    """One invented footprint."""
    return {"id": building_id, "geometry": polygon_wkb(ring)}


def write_buildings(
    path: Path,
    rows: Sequence[Mapping[str, object]],
    *,
    schema_version: str = "2.0.0",
    drop: Sequence[str] = (),
) -> None:
    """Write a tiny buildings Parquet file."""
    import duckdb

    kept = [name for name in ("id", "geometry") if name not in drop]
    connection = duckdb.connect()
    declared = ", ".join(
        f"{name} {'BLOB' if name == 'geometry' else 'VARCHAR'}" for name in kept
    )
    connection.execute(f"CREATE TABLE buildings ({declared})")
    placeholders = ", ".join("?" for _ in kept)
    for row in rows:
        connection.execute(
            f"INSERT INTO buildings VALUES ({placeholders})",
            [row.get(name) for name in kept],
        )
    versions = dict(_SCHEMA)
    versions["overture-schema-pyspark"] = schema_version
    connection.execute(
        "COPY buildings TO ? (FORMAT PARQUET, KV_METADATA {schema_versions: ?})",
        [str(path), json.dumps(versions, sort_keys=True)],
    )
    connection.close()


def receipt_for(path: Path, source_key: str = "places_ovt"):
    """A receipt whose digest is the file's own bytes."""
    import hashlib

    from eii_custodian.publicdata.places.read import FileReceipt

    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return FileReceipt(source_key, digest, "2026-11-14T00:00:00Z", "SYN Publisher")


def _cell(row: Mapping[str, object], name: str) -> object:
    if name == "names":
        names = row.get("names")
        if not isinstance(names, dict):
            return {"primary": None, "common": {}}
        common = names.get("common")
        if not isinstance(common, dict):
            common = {}
        return {"primary": names.get("primary"), "common": common}
    if name == "sources":
        sources = row.get("sources")
        if not isinstance(sources, list):
            return []
        return sources
    if name == "geometry":
        return row.get("geometry")
    return row.get(name)
