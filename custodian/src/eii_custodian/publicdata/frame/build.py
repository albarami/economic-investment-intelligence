"""Read-only frame entry point over S2-T01 hashed cache pairs.

Tests and real builds use build_frame and the same raw-source assembler.
"""

import json
from collections.abc import Mapping
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from decimal import Decimal
from pathlib import Path
from typing import Any

from eii_custodian.publicdata.fetch.registry import Entry
from eii_custodian.publicdata.fetch.snapshots import (
    SnapshotError,
    read_snapshot,
    reviewed_selections,
)

from .census import GEOGRAPHY
from .checks import FrameError
from .crosswalk import propose_reviews
from .mapping import CONFIRMED_SOURCES, inspect_source
from .population import load_indicators


@dataclass(frozen=True)
class FrameResult:
    tables: dict[str, list[dict[str, Any]]]
    report: list[str]
    sources: dict[str, dict[str, Any]]
    inventory: dict[str, dict[str, tuple[str, ...]]] = dataclass_field(
        default_factory=dict
    )


def read_cached(
    cache: Path, entry: Entry, *, digest: str
) -> tuple[Any, dict[str, Any]]:
    """Read a reviewed hash and verify its dated receipt and bytes."""
    try:
        selected = read_snapshot(cache / entry.key, digest)
    except SnapshotError as exc:
        raise FrameError(f"{entry.source_id}: {exc}") from None
    receipt = selected.sidecar
    for key, expected in (
        ("source_id", entry.source_id),
        ("key", entry.key),
        ("licence_id", entry.licence_id),
        ("licence_basis", entry.licence_basis),
    ):
        if receipt.get(key) != expected:
            raise FrameError(f"{entry.source_id}: receipt {key} mismatch")
    for field in ("publisher", "title_en", "fetch_url", "retrieved_utc", "sha256"):
        if not receipt.get(field):
            raise FrameError(f"{entry.source_id}: missing receipt {field}")
    if receipt.get("switched_off") is not False:
        raise FrameError(f"{entry.source_id}: source switched off")
    body = selected.body
    receipt["method"] = "frame.v1"
    if entry.extension == "zip":
        return body, receipt
    return json.loads(body, parse_float=Decimal), receipt


def records(payload: Any, source: str) -> list[dict[str, Any]]:
    if isinstance(payload, dict) and "features" in payload:
        rows = []
        for feature in payload["features"]:
            row = dict(feature["attributes"])
            if "geometry" in feature:
                row["geometry"] = feature["geometry"]
            rows.append(row)
        return rows
    if not isinstance(payload, list) or any(
        not isinstance(row, dict) for row in payload
    ):
        raise FrameError(f"{source}: unsupported source schema")
    return payload


def inspect_cache(
    cache: Path,
    registry: tuple[Entry, ...],
    review: Path,
    selections: Mapping[str, str],
) -> FrameResult:
    """Inspect confirmed cached exports; never substitute unconfirmed geometry.

    Inventories and missing review mappings are returned before the licensed
    geometry assembly. This inspection never emits release rows.
    """
    tables: dict[str, list[dict[str, Any]]] = {
        name: []
        for name in (
            "municipality",
            "zone",
            "district",
            "grid_cell",
            "gazetteer",
            *GEOGRAPHY,
        )
    }
    report = []
    sources = {}
    inventory = {}
    required = (CONFIRMED_SOURCES - {"bnd_geob"}) | {
        "bnd_hdx",
        "bnd_muni_2025",
        "est_census",
        "zone_population",
        "census_hh_type_2020",
    }
    for entry in sorted(registry, key=lambda e: e.source_id):
        name = entry.source_id
        if name not in required:
            continue
        if entry.skip_reason:
            report.append(f"{name}: {entry.skip_reason}")
            continue
        if name not in CONFIRMED_SOURCES:
            report.append(f"{name}: cache_shape_unconfirmed; no mapping attempted")
            continue
        payload, receipt = read_cached(
            cache, entry, digest=selections.get(entry.key, "")
        )
        sources[name] = receipt
        inspected = inspect_source(
            name, payload, load_indicators(review) if name == "pop_muni" else None
        )
        inventory[name] = inspected.inventory
        if inspected.reason:
            report.append(
                inspected.reason
                if inspected.reason.startswith(name + ":")
                else f"{name}: {inspected.reason}"
            )
    propose_reviews(review, None, set(), inventory, report)
    report.append("frame: required geometry unavailable; dependent tables not built")
    return FrameResult(tables, report, sources, inventory)


def build_frame(
    cache: Path,
    registry: tuple[Entry, ...],
    review: Path,
    output: Path | None = None,
    *,
    selections: Mapping[str, str] | None = None,
) -> FrameResult:
    """Build from confirmed raw shapes, with optional generated review output."""
    from .live import build_live_frame

    if output is not None:
        destination = output.resolve()
        if any(destination.is_relative_to(path.resolve()) for path in (cache, review)):
            raise FrameError("review output overlaps inputs")
    selected = reviewed_selections(cache) if selections is None else selections
    result = inspect_cache(cache, registry, review, selected)
    entries = {entry.source_id: entry for entry in registry}
    hdx = entries.get("bnd_hdx")
    if hdx is None or hdx.skip_reason:
        report = [line for line in result.report if "unlisted zone numbers" not in line]
        propose_reviews(review, output, set(), result.inventory, report)
        return FrameResult(result.tables, report, result.sources, result.inventory)
    return build_live_frame(cache, registry, review, output, result, selected)
