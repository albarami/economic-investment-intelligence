"""Hand-made stand-ins for the height inputs (FE-95).

Invented GeoJSON tables and a tiny invented raster, written only into a test's
temporary folder; nothing real is fetched, and no binary file is committed.
Every identifier uses the SYN- form and every host is an allow-listed host
with an invented path.
"""

from __future__ import annotations

import json

import numpy as np
import rasterio
import yaml
from rasterio.transform import from_origin

from eii_custodian.publicdata.fetch.receipts import (
    cache_directory,
    commit_pair,
    sha256_hex,
    sidecar_for,
)
from eii_custodian.publicdata.fetch.registry import Entry

ALLOWED_HOST = "data.worldpop.org"
BLOCKED_HOST = "invented-unlisted.example"
NODATA = -99999


def square(x: float, y: float, size: float) -> list:
    """Return one ring of an axis-aligned square footprint."""
    return [
        [x, y],
        [x + size, y],
        [x + size, y + size],
        [x, y + size],
        [x, y],
    ]


def building_feature(
    building_id: str,
    ring: list,
    recorded: object = None,
    floors: object = None,
    source: str = "SYN-FOOT",
    extra: dict | None = None,
    geometry: dict | None = None,
) -> dict:
    """One feature of the invented building table."""
    properties = {
        "building_id": building_id,
        "recorded_height_m": recorded,
        "floor_count": floors,
        "footprint_source_id": source,
    }
    if extra:
        properties.update(extra)
    return {
        "type": "Feature",
        "geometry": geometry or {"type": "Polygon", "coordinates": [ring]},
        "properties": properties,
    }


def buildings_bytes(features: list) -> bytes:
    """The invented building table as GeoJSON bytes."""
    return json.dumps({"type": "FeatureCollection", "features": features}).encode(
        "utf-8"
    )


def globfp_bytes(features: list, field: str = "syn_height_m") -> bytes:
    """Invented 3D-GloBFP stand-in: (ring, height) pairs as GeoJSON."""
    return json.dumps(
        {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "Polygon", "coordinates": [ring]},
                    "properties": {field: height},
                }
                for ring, height in features
            ],
        }
    ).encode("utf-8")


def wsf_bytes(
    path,
    values: list,
    width: int,
    height: int,
    *,
    west: float = 0.0,
    north: float = 1.0,
    cell: float = 1.0,
    nodata: float = NODATA,
    epsg: int = 4326,
) -> bytes:
    """A tiny invented WGS 84 raster; returns its bytes for the cache pair."""
    data = np.array(values, dtype="float32").reshape(height, width)
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        width=width,
        height=height,
        count=1,
        dtype="float32",
        crs=f"EPSG:{epsg}",
        transform=from_origin(west, north, cell, cell),
        nodata=nodata,
    ) as target:
        target.write(data, 1)
    return path.read_bytes()


def rules_document(
    *,
    storey: str = "4",
    label: str = "ASSUMPTION",
    globfp_format: str = "GeoJSON",
    globfp_field: str = "syn_height_m",
    globfp_unit: str = "m",
    globfp_crs: str = "EPSG:4326",
    wsf_format: str = "GTiff",
    wsf_band: str = "1",
    wsf_unit: str = "m",
    wsf_nodata: str = str(NODATA),
    wsf_crs: str = "EPSG:4326",
) -> dict:
    """A hand-made declared structure with invented names (B6)."""
    return {
        "storey_height_m": {
            "value": storey,
            "label": label,
            "basis": "invented fixture basis text",
        },
        "order": "invented order wording",
        "match_3dglobfp": "invented 3D-GloBFP matching rule",
        "match_wsf3d": "invented WSF 3D matching rule",
        "credit_3dglobfp": "Invented credit line, retrieved {date}.",
        "sources": {
            "bldg_3dglobfp": {
                "format": globfp_format,
                "field": globfp_field,
                "unit": globfp_unit,
                "nodata": "",
                "crs": globfp_crs,
            },
            "bldg_wsf3d": {
                "format": wsf_format,
                "band": wsf_band,
                "unit": wsf_unit,
                "nodata": wsf_nodata,
                "crs": wsf_crs,
            },
        },
    }


def rules_file(path, **overrides):
    """Write a hand-made rules document and return its path."""
    return write_rules(path, rules_document(**overrides))


def write_rules(path, document: dict):
    """Write a mutated rules document and return its path."""
    path.write_text(yaml.safe_dump(document, sort_keys=True), encoding="utf-8")
    return path


def entry(source_id: str, key: str | None = None, **overrides) -> Entry:
    """One invented height-source registry row on an allow-listed host."""
    fields = {
        "key": key or source_id,
        "source_id": source_id,
        "slug": "",
        "kind": "https_file",
        "title_en": "Invented S2-T20 height row",
        "publisher": "SYN-publisher",
        "licence_id": "CC-BY-4.0",
        "licence_basis": "dataset",
        "decision_record": "",
        "fetch_host": ALLOWED_HOST,
        "url": f"https://{ALLOWED_HOST}/SYN/{source_id}.bin",
        "terms_url": "",
        "terms_words": "invented terms words for a test",
        "terms_read_on": "2026-11-14",
        "nightly_live_fetch": False,
        "public_splits": (),
        "commit_allowed": False,
        "release_tables": (),
        "caveat_keys": (),
        "columns": (),
        "row_count_min": None,
        "row_count_max": None,
        "period_first": "",
        "period_last": "",
        "period_field": "",
        "reconciliation": "none",
        "skip_reason": "",
        "extension": "bin",
        "landing_url": "",
    }
    fields.update(overrides)
    return Entry(**fields)


def store(cache, row: Entry, body: bytes, publisher: str = "SYN-publisher"):
    """Write one hash-addressed cache pair for a row and return its digest."""
    digest = sha256_hex(body)
    sidecar = sidecar_for(
        row,
        digest=digest,
        nbytes=len(body),
        fetch_url=row.url,
        fetch_host=row.fetch_host,
        retrieved_utc="2026-11-14T00:00:00Z",
        publisher=publisher,
        source_modified="",
        row_count=None,
        terms_sha256="",
    )
    commit_pair(cache_directory(cache, row.key), digest, row.extension, body, sidecar)
    return digest


def card_fixture(tmp_path):
    """The card's seven invented buildings and their two invented sources.

    Building i sits at x in [i + 0.1, i + 0.6], y in [0.1, 0.6]; its
    representative point lands near (i + 0.35, 0.35), inside WSF cell i.
    """
    specs = {
        "SYN-B-0001": (30, 8),
        "SYN-B-0002": (12, 3),
        "SYN-B-0003": (21, None),
        "SYN-B-0004": (None, 5),
        "SYN-B-0005": (None, None),
        "SYN-B-0006": (None, None),
        "SYN-B-0007": (None, None),
    }
    features = [
        building_feature(building_id, square(i + 0.1, 0.1, 0.5), recorded, floors)
        for i, (building_id, (recorded, floors)) in enumerate(sorted(specs.items()))
    ]
    globfp = globfp_bytes(
        [
            (square(0.05, 0.05, 0.6), 24),
            (square(1.05, 0.05, 0.6), 15),
            (square(2.05, 0.05, 0.6), 15),
            (square(3.05, 0.05, 0.6), 11),
            (square(6.05, 0.05, 0.6), 7),
        ]
    )
    wsf = wsf_bytes(
        tmp_path / "syn-wsf.tif",
        [[18, NODATA, 13, NODATA, 6, NODATA, 5, NODATA]],
        8,
        1,
    )
    return buildings_bytes(features), globfp, wsf
