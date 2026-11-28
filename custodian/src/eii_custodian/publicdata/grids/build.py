"""Assemble the two Public tables and the weather cache from verified receipts."""

from __future__ import annotations

import json
import os
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast
from urllib.parse import urlsplit

from shapely.geometry.base import BaseGeometry

from eii_custodian.publicdata.fetch.receipts import (
    cache_directory,
    file_metadata,
)
from eii_custodian.publicdata.fetch.registry import Entry
from eii_custodian.publicdata.fetch.snapshots import (
    SnapshotError,
    read_snapshot,
    reviewed_selections,
)

from .contracts import GridError
from .night_lights import FrameGeometry, aggregate, read_night_lights
from .population import (
    PopulationRows,
    PopulationTable,
    grid_signature,
    read_population,
    spec_from_entry,
)
from .weather import validate_weather

GRIDS_RELATIVE = "grids"
MANIFEST_NAME = "manifest.json"
WEATHER_NAME = "weather_openmeteo.json"
NIGHT_TABLE = "pub_night_lights"
POPULATION_TABLE = "pub_pop_agesex_grid"
FACT_LINEAGE = "fact_lineage"
SOURCE_REGISTRY = "source_registry"
METHODS = {
    "ntl_blackmarble": ("C36", "MTH-109"),
    "worldpop_qat_agesex": ("C38", "MTH-111"),
    "weather_openmeteo": ("weather.v1", "weather.v1"),
}


@dataclass(frozen=True)
class GridResult:
    """Rows, lineage, per-file receipts and named coverage reasons."""

    tables: dict[str, Sequence[dict[str, Any]]]
    sources: dict[str, dict[str, Any]]
    manifest: dict[str, Any]
    coverage: dict[str, str] = field(default_factory=dict)


def active(entries: tuple[Entry, ...] | list[Entry], source_id: str) -> list[Entry]:
    """Return the file entries of one source: keyed per file, not skipped."""
    return [
        entry
        for entry in entries
        if entry.source_id == source_id and "/" in entry.key and not entry.skip_reason
    ]


def _entry_directory(cache: Path, entry: Entry) -> Path:
    """Return one key's folder under the cache, or refuse a key that leaves it."""
    path = Path(entry.key)
    if path.is_absolute() or ".." in path.parts:
        raise GridError(f"{entry.source_id}: key escapes the cache")
    return cache_directory(cache, entry.key)


def cached_bytes(cache: Path, entry: Entry) -> tuple[bytes, dict[str, Any]]:
    """Read only the explicitly reviewed archive identity, never the latest file."""
    directory = _entry_directory(cache, entry)
    try:
        identity = reviewed_selections(cache).get(entry.key)
        if identity is None:
            raise SnapshotError("snapshot_selection_invalid")
        snapshot = read_snapshot(directory, identity)
        loaded = snapshot.sidecar
        body = snapshot.body
    except (SnapshotError, OSError) as exc:
        reason = str(exc) if isinstance(exc, SnapshotError) else "snapshot_missing"
        raise GridError(f"{entry.source_id}: {reason}") from None
    for name, expected in (
        ("source_id", entry.source_id),
        ("key", entry.key),
        ("licence_id", entry.licence_id),
        ("licence_basis", entry.licence_basis),
        ("file", file_metadata(entry) or None),
    ):
        if loaded.get(name) != expected:
            raise GridError(f"{entry.source_id}: receipt {name} mismatch")
    for name in ("publisher", "fetch_url", "retrieved_utc", "sha256"):
        if not loaded.get(name):
            raise GridError(f"{entry.source_id}: missing receipt {name}")
    if loaded.get("switched_off") is not False:
        raise GridError(f"{entry.source_id}: source switched off")
    # read_snapshot validates the index digest and equality with the receipt.
    return body, loaded


def build_grids(
    cache: Path,
    entries: tuple[Entry, ...] | list[Entry],
    cells: dict[int, BaseGeometry],
) -> GridResult:
    """Build both Public tables and the weather cache; write only under the cache."""
    night: list[dict[str, Any]] = []
    population: list[PopulationRows] = []
    lineage: list[dict[str, Any]] = []
    registry_rows: list[dict[str, Any]] = []
    files: list[dict[str, Any]] = []
    coverage: dict[str, str] = {}
    sources: dict[str, dict[str, Any]] = {}
    geometries = cast("dict[int, FrameGeometry]", cells)
    bounds = None
    if cells:
        cell_bounds = [geometry.bounds for geometry in geometries.values()]
        bounds = (
            min(bound[0] for bound in cell_bounds),
            min(bound[1] for bound in cell_bounds),
            max(bound[2] for bound in cell_bounds),
            max(bound[3] for bound in cell_bounds),
        )
    for entry in active(entries, "ntl_blackmarble"):
        if not _cached(cache, entry):
            coverage[f"{entry.key}:omitted"] = "NO_CACHE"
            continue
        if not entry.doi or not entry.acknowledgement:
            raise GridError("ntl_blackmarble: DOI or acknowledgement missing")
        body, receipt = cached_bytes(cache, entry)
        path = _store(cache, entry, body)
        pixels = read_night_lights(cache, path, entry.period, bounds)
        result = aggregate(pixels, geometries, entry.period)
        night.extend(_fact(result.rows, entry, receipt))
        for cell, reason in result.missing.items():
            coverage[f"{entry.key}:{cell}"] = reason
        for reason, count in result.excluded.items():
            coverage[f"{entry.key}:quality:{reason}"] = str(count)
        lineage.append(_lineage(entry, receipt, NIGHT_TABLE))
        registry_rows.append(_registry_row(entry, receipt))
        files.append(_file_row(entry, receipt, len(body)))
        sources[entry.key] = _source_row(entry, receipt)
    population_rows = active(entries, "worldpop_qat_agesex")
    _year_files(population_rows)
    population_grids: dict[str, tuple[Any, ...]] = {}
    refused_unconfirmed = False
    for entry in population_rows:
        if not _cached(cache, entry):
            coverage[f"{entry.key}:omitted"] = "NO_CACHE"
            continue
        if entry.cell_units != "people_per_cell" or not entry.doi_confirmed:
            coverage[entry.source_id] = "units or DOI unconfirmed"
            if not refused_unconfirmed:
                print(f"{entry.source_id}: units or DOI unconfirmed")
                refused_unconfirmed = True
            continue
        body, receipt = cached_bytes(cache, entry)
        path = _store(cache, entry, body)
        rows = read_population(
            cache, path, spec_from_entry(entry), Path(entry.url).name
        )
        signature = grid_signature(cache, path)
        previous = population_grids.setdefault(entry.year, signature)
        if previous != signature:
            raise GridError("worldpop_qat_agesex: grid agreement mismatch")
        population.append(rows.with_facts(_fact_columns(entry, receipt)))
        lineage.append(_lineage(entry, receipt, POPULATION_TABLE))
        registry_rows.append(_registry_row(entry, receipt))
        files.append(_file_row(entry, receipt, len(body)))
        sources[entry.key] = _source_row(entry, receipt)
    _weather(cache, entries, files, sources, registry_rows, coverage)
    manifest = {
        "method": {name: pair[0] for name, pair in METHODS.items()},
        "method_version": {name: pair[1] for name, pair in METHODS.items()},
        "files": files,
        "tables": {
            NIGHT_TABLE: len(night),
            POPULATION_TABLE: sum(len(part) for part in population),
            FACT_LINEAGE: len(lineage),
            SOURCE_REGISTRY: len(registry_rows),
        },
    }
    if files:
        _write(cache / GRIDS_RELATIVE / MANIFEST_NAME, manifest)
    return GridResult(
        {
            NIGHT_TABLE: night,
            POPULATION_TABLE: PopulationTable(population) if population else [],
            FACT_LINEAGE: lineage,
            SOURCE_REGISTRY: registry_rows,
        },
        sources,
        manifest,
        coverage,
    )


def _cached(cache: Path, entry: Entry) -> bool:
    """True when the row holds at least one receipt in its cache directory."""
    return bool(sorted((_entry_directory(cache, entry) / "index").glob("*.json")))


def _year_files(entries: list[Entry]) -> None:
    """One year is one row per sex and code, with no both-sexes or total file."""
    by_year: dict[str, list[Entry]] = {}
    for entry in entries:
        if _both_sexes_or_total(entry):
            raise GridError("worldpop_qat_agesex: both-sexes or total file")
        by_year.setdefault(entry.year, []).append(entry)
    for rows in by_year.values():
        pairs = [(row.sex, row.age_code) for row in rows]
        if len(pairs) != len(set(pairs)):
            raise GridError("worldpop_qat_agesex: repeated sex and age code")
        sexes = {sex for sex, _code in pairs}
        codes = {code for _sex, code in pairs}
        if {(sex, code) for sex in sexes for code in codes} != set(pairs):
            raise GridError("worldpop_qat_agesex: not one row per sex and code")


def _both_sexes_or_total(entry: Entry) -> bool:
    """True for a both-sexes file or a total file, from the published names."""
    if entry.sex not in {"f", "m"}:
        return True
    name = urlsplit(entry.url).path.rsplit("/", 1)[-1]
    return name.startswith(("qat_t_", "qat_T_F_", "qat_T_M_"))


def _weather(
    cache: Path,
    entries: tuple[Entry, ...] | list[Entry],
    files: list[dict[str, Any]],
    sources: dict[str, dict[str, Any]],
    registry_rows: list[dict[str, Any]],
    coverage: dict[str, str],
) -> dict[str, Any] | None:
    found = active(entries, "weather_openmeteo")
    if not found:
        return None
    entry = found[0]
    if not _cached(cache, entry):
        coverage[f"{entry.key}:omitted"] = "NO_CACHE"
        return None
    if entry.point is None:
        raise GridError("weather_openmeteo: point not recorded")
    body, receipt = cached_bytes(cache, entry)
    loaded = json.loads(body.decode("utf-8"))
    if not isinstance(loaded, dict):
        raise GridError("weather_openmeteo: unreadable response")
    validated = validate_weather(
        loaded, entry.point, entry.period_first, entry.period_last
    )
    validated["source_key"] = entry.key
    validated["source_sha256"] = receipt["sha256"]
    validated["variables"] = list(entry.variables)
    files.append(_file_row(entry, receipt, len(body)))
    registry_rows.append(_registry_row(entry, receipt))
    sources[entry.key] = _source_row(entry, receipt)
    _write(cache / GRIDS_RELATIVE / WEATHER_NAME, validated)
    return validated


def _store(cache: Path, entry: Entry, body: bytes) -> Path:
    """Return the verified cache path of one file entry."""
    del body
    identity = reviewed_selections(cache).get(entry.key)
    if identity is None:
        raise GridError(f"{entry.source_id}: snapshot_selection_invalid")
    return read_snapshot(_entry_directory(cache, entry), identity).path


def _fact(
    rows: list[dict[str, Any]], entry: Entry, receipt: dict[str, Any]
) -> list[dict[str, Any]]:
    """Add the lineage columns every Public fact row carries."""
    for row in rows:
        row.update(_fact_columns(entry, receipt))
    return rows


def _fact_columns(entry: Entry, receipt: dict[str, Any]) -> dict[str, Any]:
    """Constant Public lineage, shared across the cells of one native file."""
    method, version = METHODS[entry.source_id]
    return dict(
        source_id=entry.source_id,
        source_key=entry.key,
        source_sha256=receipt["sha256"],
        method=method,
        method_version=version,
        provenance="Public",
        evidence_status="Observed",
        caveat_keys=list(entry.caveat_keys),
    )


def _lineage(entry: Entry, receipt: dict[str, Any], table: str) -> dict[str, Any]:
    """Return the chain of one table back to one whole fetched file."""
    method, version = METHODS[entry.source_id]
    return {
        "table": table,
        "method": method,
        "method_version": version,
        "source_key": entry.key,
        "publisher": receipt["publisher"],
        "dataset": entry.landing_url or entry.url,
        "licence_id": entry.licence_id,
        "licence_url": entry.licence_url,
        "retrieved_utc": receipt["retrieved_utc"],
        "source_sha256": receipt["sha256"],
        "release": entry.release,
        "period": entry.period or entry.year or entry.period_first,
        "period_first": entry.period_first or entry.year or entry.period,
        "period_last": entry.period_last or entry.year or entry.period,
        "provenance": "Public",
        "evidence_status": "Observed",
        "caveat_keys": list(entry.caveat_keys),
        "doi": entry.doi,
        "acknowledgement": entry.acknowledgement,
    }


def _registry_row(entry: Entry, receipt: dict[str, Any]) -> dict[str, Any]:
    """Return the source-registry chain of one fetched file."""
    method, version = METHODS[entry.source_id]
    return {
        "source_key": entry.key,
        "source_id": entry.source_id,
        "publisher": receipt["publisher"],
        "dataset": entry.landing_url or entry.url,
        "licence_id": entry.licence_id,
        "licence_url": entry.licence_url,
        "retrieved_utc": receipt["retrieved_utc"],
        "source_sha256": receipt["sha256"],
        "release": entry.release,
        "period": entry.period or entry.year or entry.period_first,
        "period_first": entry.period_first or entry.year or entry.period,
        "period_last": entry.period_last or entry.year or entry.period,
        "method": method,
        "method_version": version,
        "provenance": "Public",
        "evidence_status": "Observed",
        "caveat_keys": list(entry.caveat_keys),
    }


def _file_row(entry: Entry, receipt: dict[str, Any], nbytes: int) -> dict[str, Any]:
    """Return the per-file receipt line of the manifest."""
    method, version = METHODS[entry.source_id]
    return {
        "key": entry.key,
        "source_id": entry.source_id,
        "publisher": receipt["publisher"],
        "licence_id": entry.licence_id,
        "licence_basis": entry.licence_basis,
        "retrieved_utc": receipt["retrieved_utc"],
        "sha256": receipt["sha256"],
        "bytes": nbytes,
        "period": entry.period or entry.year or entry.period_first,
        "period_first": entry.period_first or entry.year or entry.period,
        "period_last": entry.period_last or entry.year or entry.period,
        "tile": entry.tile,
        "sex": entry.sex,
        "age_code": entry.age_code,
        "release": entry.release,
        "year": entry.year,
        "cell_units": entry.cell_units,
        "doi": entry.doi,
        "doi_confirmed": entry.doi_confirmed,
        "variables": list(entry.variables),
        "method": method,
        "method_version": version,
    }


def _source_row(entry: Entry, receipt: dict[str, Any]) -> dict[str, Any]:
    """Return the complete source chain of one fetched file."""
    method, version = METHODS[entry.source_id]
    return {
        "source_id": entry.source_id,
        "source_key": entry.key,
        "publisher": receipt["publisher"],
        "dataset": entry.landing_url or entry.url,
        "fetch_url": receipt["fetch_url"],
        "landing_url": entry.landing_url,
        "licence_id": entry.licence_id,
        "licence_basis": entry.licence_basis,
        "licence_url": entry.licence_url,
        "retrieved_utc": receipt["retrieved_utc"],
        "source_sha256": receipt["sha256"],
        "release": entry.release,
        "period": entry.period or entry.year or entry.period_first,
        "period_first": entry.period_first or entry.year or entry.period,
        "period_last": entry.period_last or entry.year or entry.period,
        "doi": entry.doi,
        "doi_confirmed": entry.doi_confirmed,
        "acknowledgement": entry.acknowledgement,
        "cell_units": entry.cell_units,
        "cache_role": entry.cache_role,
        "variables": list(entry.variables),
        "method": method,
        "method_version": version,
        "provenance": "Public",
        "evidence_status": "Observed",
        "caveat_keys": list(entry.caveat_keys),
    }


def _write(path: Path, payload: dict[str, Any]) -> None:
    """Replace one generated file below the cache, or leave no partial file."""
    path.parent.mkdir(exist_ok=True)
    partial = path.with_name(f".{path.name}.partial")
    text = json.dumps(payload, sort_keys=True, ensure_ascii=True) + "\n"
    try:
        partial.write_text(text, encoding="utf-8")
        os.replace(partial, path)
    except OSError:
        partial.unlink(missing_ok=True)
        raise
