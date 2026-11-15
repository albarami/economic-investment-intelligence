"""B6: read the cached height files under their declared structure (PUB-07).

The receipt and hash checks copy the frame's `read_cached`, minus its JSON
parse, because the bodies here are raster and vector files. A row that is
skipped or has no cached file is not a failure: its source is absent with the
row's own technical reason. A declared value still holding the marker
`to be confirmed` keeps its source absent with `structure_unconfirmed`; an
unreadable declared format is absent the same way, while a declared unit or
reference system that is wrong is refused.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal
from importlib import import_module
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import numpy.typing as npt
from affine import Affine
from shapely.geometry import shape
from shapely.geometry.base import BaseGeometry

from eii_custodian.publicdata.fetch.receipts import cache_directory, sha256_hex
from eii_custodian.publicdata.fetch.registry import Entry

from .model import (
    SOURCE_IDS,
    HeightError,
    Rules,
    SourceStructure,
    structure_unconfirmed,
)

EPSG_WGS84 = 4326
GLOBFP_FORMAT = "GeoJSON"
WSF_FORMAT = "GTiff"
UNIT_METRES = "m"
_NUMERIC_DTYPES = frozenset(
    {"float16", "float32", "float64", "uint8", "uint16", "uint32", "int16", "int32"}
)


@dataclass(frozen=True)
class WsfGrid:
    """One WSF 3D file kept for matching: its band array and transform."""

    transform: Affine
    data: npt.NDArray[Any]
    nodata: Decimal
    width: int
    height: int


@dataclass(frozen=True)
class SourceResult:
    """The files one source gave, or its absent reason and recorded terms."""

    source_id: str
    state: str
    reason: str
    globfp: tuple[tuple[str, tuple[tuple[BaseGeometry, Decimal], ...]], ...]
    wsf: tuple[tuple[str, WsfGrid], ...]
    files: tuple[dict[str, object], ...]
    terms_words: str
    terms_read_on: str
    retrieved_utc: str


def _local_file(cache: Path, path: Path) -> Path:
    """Reject schemes, GDAL virtual paths and cache escapes before decoding."""
    name = str(path)
    if urlsplit(name).scheme or name.startswith("/vsi"):
        raise HeightError("cache_path")
    candidate = path.resolve()
    if not candidate.is_relative_to(cache.resolve()):
        raise HeightError("cache_path")
    if not candidate.is_file():
        raise HeightError("cache_path")
    return candidate


def _verified_body(cache: Path, entry: Entry) -> tuple[Path, dict[str, object]] | None:
    """The receipt and hash checks of `read_cached`, minus the JSON parse.

    Returns None when the row has no cached file (`not_fetched`); every other
    defect is a refusal.
    """
    directory = cache_directory(cache, entry.key)
    receipts = sorted(directory.glob("*.meta.json"))
    if not receipts:
        return None
    if len(receipts) != 1:
        raise HeightError("cache_receipt")
    receipt = json.loads(receipts[0].read_text(encoding="utf-8"))
    for field, expected in (
        ("source_id", entry.source_id),
        ("key", entry.key),
        ("licence_id", entry.licence_id),
        ("licence_basis", entry.licence_basis),
    ):
        if receipt.get(field) != expected:
            raise HeightError("cache_receipt_mismatch")
    for field in ("publisher", "title_en", "fetch_url", "retrieved_utc", "sha256"):
        if not receipt.get(field):
            raise HeightError("cache_receipt_missing")
    if receipt.get("switched_off") is not False:
        raise HeightError("switched_off")
    digest = str(receipt["sha256"])
    if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
        raise HeightError("malformed_hash")
    body_path = directory / f"{digest}.{entry.extension}"
    if not body_path.is_file() or sha256_hex(body_path.read_bytes()) != digest:
        raise HeightError("content_hash_mismatch")
    return body_path, receipt


def _file_record(
    entry: Entry, receipt: dict[str, object], digest: str
) -> dict[str, object]:
    return {
        "key": entry.key,
        "licence_basis": entry.licence_basis,
        "licence_id": entry.licence_id,
        "retrieved_utc": receipt["retrieved_utc"],
        "role": "read",
        "sha256": digest,
        "terms_read_on": entry.terms_read_on,
        "terms_words": entry.terms_words,
        "url": receipt["fetch_url"],
    }


def _declared_check(structure: SourceStructure) -> None:
    """The declared unit and reference system are the only ones we read (R9g)."""
    if structure.unit != UNIT_METRES:
        raise HeightError("declared_unit")
    if structure.crs != f"EPSG:{EPSG_WGS84}":
        raise HeightError("declared_reference_system")


def _positive_height(value: object) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (int, Decimal)):
        raise HeightError("height_value")
    parsed = Decimal(value) if isinstance(value, int) else value
    if not parsed.is_finite() or parsed <= 0:
        raise HeightError("height_value")
    return parsed


def _parse_globfp(
    body: bytes, structure: SourceStructure
) -> tuple[tuple[BaseGeometry, Decimal], ...]:
    """GeoJSON features with the declared height property; nothing else reads."""
    try:
        payload = json.loads(body, parse_float=Decimal)
    except ValueError:
        raise HeightError("structure_mismatch") from None
    if not isinstance(payload, dict) or payload.get("type") != "FeatureCollection":
        raise HeightError("structure_mismatch")
    declared_crs = payload.get("crs")
    if (
        declared_crs is not None
        and "4326" not in str(declared_crs)
        and "CRS84" not in str(declared_crs)
    ):
        raise HeightError("reference_system")
    features = payload.get("features")
    if not isinstance(features, list):
        raise HeightError("structure_mismatch")
    rows: list[tuple[BaseGeometry, Decimal]] = []
    for feature in features:
        if not isinstance(feature, dict):
            raise HeightError("structure_mismatch")
        properties = feature.get("properties")
        if not isinstance(properties, dict) or structure.field not in properties:
            raise HeightError("structure_mismatch")
        geometry = feature.get("geometry")
        if not isinstance(geometry, dict) or geometry.get("type") not in (
            "Polygon",
            "MultiPolygon",
        ):
            raise HeightError("structure_mismatch")
        try:
            footprint = shape(geometry)
        except (ValueError, TypeError, KeyError, AttributeError):
            raise HeightError("structure_mismatch") from None
        if footprint.is_empty or not footprint.is_valid:
            raise HeightError("structure_mismatch")
        rows.append((footprint, _positive_height(properties[structure.field])))
    return tuple(rows)


def _parse_wsf(cache: Path, body_path: Path, structure: SourceStructure) -> WsfGrid:
    """The declared band of a WGS 84 raster with the declared no-data value."""
    checked = _local_file(cache, body_path)
    rasterio = import_module("rasterio")
    try:
        band = int(structure.band)
    except ValueError:
        raise HeightError("structure_mismatch") from None
    try:
        declared_nodata = Decimal(structure.nodata)
    except ArithmeticError:
        raise HeightError("structure_mismatch") from None
    with rasterio.open(checked) as source:
        if source.count != band:
            raise HeightError("structure_mismatch")
        if source.crs is None or source.crs.to_epsg() != EPSG_WGS84:
            raise HeightError("reference_system")
        if any(dtype not in _NUMERIC_DTYPES for dtype in source.dtypes):
            raise HeightError("structure_mismatch")
        if source.nodata is None or Decimal(str(source.nodata)) != declared_nodata:
            raise HeightError("structure_mismatch")
        return WsfGrid(
            transform=source.transform,
            data=source.read(band),
            nodata=Decimal(str(source.nodata)),
            width=source.width,
            height=source.height,
        )


def read_sources(
    cache: Path, entries: tuple[Entry, ...] | list[Entry], rules: Rules
) -> dict[str, SourceResult]:
    """Read every active row of the two height sources; absent rows are kept."""
    results: dict[str, SourceResult] = {}
    for source_id in SOURCE_IDS:
        structure = rules.structures[source_id]
        rows = sorted(
            (
                entry
                for entry in entries
                if entry.source_id == source_id
                and (entry.key == source_id or entry.key.startswith(source_id + "/"))
            ),
            key=lambda entry: entry.key,
        )
        terms = rows[0] if rows else None
        if (
            structure_unconfirmed(structure)
            or (source_id == "bldg_3dglobfp" and structure.format != GLOBFP_FORMAT)
            or (source_id == "bldg_wsf3d" and structure.format != WSF_FORMAT)
        ):
            results[source_id] = SourceResult(
                source_id=source_id,
                state="absent",
                reason="structure_unconfirmed",
                globfp=(),
                wsf=(),
                files=(),
                terms_words=terms.terms_words if terms else "",
                terms_read_on=terms.terms_read_on if terms else "",
                retrieved_utc="",
            )
            continue
        _declared_check(structure)
        globfp: list[tuple[str, tuple[tuple[BaseGeometry, Decimal], ...]]] = []
        wsf: list[tuple[str, WsfGrid]] = []
        files: list[dict[str, object]] = []
        absent_reasons: list[str] = []
        retrieved_utc = ""
        for row in rows:
            if row.skip_reason:
                absent_reasons.append(row.skip_reason)
                continue
            found = _verified_body(cache, row)
            if found is None:
                absent_reasons.append("not_fetched")
                continue
            body_path, receipt = found
            digest = str(receipt["sha256"])
            if not retrieved_utc:
                retrieved_utc = str(receipt["retrieved_utc"])
            files.append(_file_record(row, receipt, digest))
            file_name = row.slug or row.key
            if source_id == "bldg_3dglobfp":
                globfp.append(
                    (file_name, _parse_globfp(body_path.read_bytes(), structure))
                )
            else:
                wsf.append((file_name, _parse_wsf(cache, body_path, structure)))
        if not rows:
            absent_reasons.append("not_fetched")
        results[source_id] = SourceResult(
            source_id=source_id,
            state="read" if (globfp or wsf) else "absent",
            reason="" if (globfp or wsf) else absent_reasons[0],
            globfp=tuple(globfp),
            wsf=tuple(wsf),
            files=tuple(files),
            terms_words=rows[0].terms_words if rows else "",
            terms_read_on=rows[0].terms_read_on if rows else "",
            retrieved_utc=retrieved_utc,
        )
    return results


__all__ = [
    "SourceResult",
    "WsfGrid",
    "read_sources",
]
