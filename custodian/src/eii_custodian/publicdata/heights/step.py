"""B7: `build_heights` — read, match, call the calc functions, write.

A missing building table is a skip line, never a failure (B10). A refused
input raises `HeightError`, whose name is the check the FAIL line carries.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from eii_core.calc.building_heights import (
    FALLBACKS,
    HEIGHT_SOURCES,
    NONE_SOURCE,
    choose_height,
    fallback_errors,
    floor_height,
)
from eii_custodian.publicdata.fetch.receipts import sha256_hex as file_sha256
from eii_custodian.publicdata.fetch.registry import Entry
from eii_custodian.publicdata.fetch.report import skip_line

from .manifest import (
    dump_sorted,
    manifest_block,
    output_row,
    write_outputs,
)
from .match import (
    globfp_height,
    representative_point,
    wsf3d_height,
)
from .model import (
    BUILDINGS_RELATIVE,
    HEIGHTS_FILE,
    HEIGHTS_RELATIVE,
    MANIFEST_FILE,
    RULES_PATH,
    Building,
    HeightError,
    Rules,
    load_buildings,
    load_rules,
)
from .read import SourceResult, read_sources


def _none_reason(results: dict[str, SourceResult]) -> str:
    """The first absent source's reason in the order, or empty."""
    for source_id in ("bldg_3dglobfp", "bldg_wsf3d"):
        if results[source_id].state == "absent" and results[source_id].reason:
            return results[source_id].reason
    return ""


def _resolve(
    buildings: list[Building],
    rules: Rules,
    results: dict[str, SourceResult],
) -> tuple[list[dict[str, object]], list[dict[str, Decimal | None]]]:
    """Per building: the candidate dict for errors and the checked output row."""
    rows: list[dict[str, object]] = []
    candidates: list[dict[str, Decimal | None]] = []
    absent = _none_reason(results)
    for building in buildings:
        point = representative_point(building.geometry)
        candidate: dict[str, Decimal | None] = {
            "recorded": building.recorded,
            "floor_count": (
                floor_height(building.floor_count, rules.storey_height)
                if building.floor_count is not None
                else None
            ),
            "3dglobfp": globfp_height(
                point,
                building.geometry,
                results["bldg_3dglobfp"].globfp,
            ),
            "wsf3d": wsf3d_height(point, results["bldg_wsf3d"].wsf),
        }
        choice = choose_height(candidate)
        reason = ""
        if choice.source == NONE_SOURCE:
            reason = absent or choice.reason
        rows.append(
            output_row(
                building.building_id,
                choice,
                building.footprint_source_id,
                reason,
            )
        )
        candidates.append(candidate)
    return rows, candidates


def build_heights(
    cache: Path,
    entries: tuple[Entry, ...] | list[Entry],
    buildings_path: Path,
    out_dir: Path,
    lines: list[str],
    rules_path: Path | None = None,
) -> None:
    """Run the heights step: skip on an absent table, refuse on a bad input."""
    if not buildings_path.is_file():
        lines.append(skip_line("heights", "building_table_absent"))
        return
    rules = load_rules(rules_path if rules_path is not None else RULES_PATH)
    buildings = load_buildings(buildings_path)
    results = read_sources(cache, entries, rules)
    rows, candidates = _resolve(buildings, rules, results)
    counts = {name: 0 for name in HEIGHT_SOURCES}
    none_reasons: dict[str, int] = {}
    for row in rows:
        source = str(row["height_source"])
        counts[source] += 1
        if source == NONE_SOURCE:
            reason = str(row["reason"])
            none_reasons[reason] = none_reasons.get(reason, 0) + 1
    errors = fallback_errors(candidates)
    heights_body = dump_sorted(rows)
    input_files: list[dict[str, object]] = [
        {
            "key": "building_table",
            "path": BUILDINGS_RELATIVE,
            "role": "read",
            "sha256": file_sha256(buildings_path.read_bytes()),
        },
        {
            "key": "heights",
            "path": f"{HEIGHTS_RELATIVE}/{HEIGHTS_FILE}",
            "role": "written",
            "sha256": file_sha256(heights_body),
        },
    ]
    block = manifest_block(
        rules,
        results,
        counts,
        none_reasons,
        errors,
        input_files,
    )
    write_outputs(
        out_dir,
        {
            HEIGHTS_FILE: heights_body,
            MANIFEST_FILE: dump_sorted(block),
        },
    )
    lines.append(
        f"PASS heights rows={len(rows)} sources={sum(counts[s] for s in FALLBACKS)}"
    )


__all__ = [
    "BUILDINGS_RELATIVE",
    "HEIGHTS_RELATIVE",
    "HeightError",
    "build_heights",
]
