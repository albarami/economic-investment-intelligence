"""B7: `build_heights` — read, match, call the calc functions, write.

A missing building table is a skip line, never a failure (B10). A refused
input raises `HeightError`, whose name is the check the FAIL line carries.
"""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
from pathlib import Path

from eii_core.calc.building_heights import (
    NONE_SOURCE,
    HeightChoice,
    choose_height,
    fallback_errors,
    floor_height,
    height_counts,
    largest_overlap,
)
from eii_custodian.publicdata.fetch.receipts import sha256_hex as file_sha256
from eii_custodian.publicdata.fetch.registry import Entry

from .calibration import gba_calibration
from .landmarks import apply_landmark_heights, load_landmark_heights
from .manifest import (
    dump_sorted,
    manifest_block,
    output_row,
    write_outputs,
)
from .match import (
    GlobfpIndex,
    globfp_candidates,
    globfp_index,
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


def _table_bounds(
    buildings: list[Building],
) -> tuple[float, float, float, float] | None:
    """The bounding box of every footprint, or none for an empty table."""
    if not buildings:
        return None
    boxes = [building.geometry.bounds for building in buildings]
    return (
        min(box[0] for box in boxes),
        min(box[1] for box in boxes),
        max(box[2] for box in boxes),
        max(box[-1] for box in boxes),
    )


def _resolve(
    buildings: list[Building],
    rules: Rules,
    results: dict[str, SourceResult],
    index: GlobfpIndex,
) -> tuple[
    list[dict[str, object]],
    list[dict[str, Decimal | None]],
    list[HeightChoice],
    list[list[tuple[Decimal, str, int, Decimal]]],
]:
    """Per building: the candidate dict, the choice and the match list."""
    rows: list[dict[str, object]] = []
    candidates: list[dict[str, Decimal | None]] = []
    choices: list[HeightChoice] = []
    globfp_matches: list[list[tuple[Decimal, str, int, Decimal]]] = []
    absent = _none_reason(results)
    for building in buildings:
        point = representative_point(building.geometry)
        try:
            floor_product = (
                floor_height(building.floor_count, rules.storey_height)
                if building.floor_count is not None
                else None
            )
        except ArithmeticError:
            raise HeightError("bad_floor_count") from None
        matches = globfp_candidates(point, building.geometry, index)
        winner = largest_overlap(matches)
        candidate: dict[str, Decimal | None] = {
            "recorded": building.recorded,
            "floor_count": floor_product,
            "3dglobfp": winner[-1] if winner is not None else None,
            "wsf3d": wsf3d_height(point, results["bldg_wsf3d"].wsf),
        }
        choice = choose_height(candidate)
        reason = ""
        if choice.source == NONE_SOURCE:
            reason = absent or choice.reason
            choice = replace(choice, reason=reason)
        rows.append(
            output_row(
                building.building_id,
                choice,
                building.footprint_source_id,
                reason,
            )
        )
        candidates.append(candidate)
        choices.append(choice)
        globfp_matches.append(matches)
    return rows, candidates, choices, globfp_matches


def build_heights(
    cache: Path,
    entries: tuple[Entry, ...] | list[Entry],
    buildings_path: Path,
    out_dir: Path,
    lines: list[str],
    rules_path: Path | None = None,
    *,
    terms_attempts: tuple[dict[str, object], ...] = (),
) -> None:
    """Run the heights step; refuse on a bad input or a missing building table.

    The step's own earlier outputs are removed before anything is read, so a
    later refusal never leaves an old heights file behind.
    """
    for name in (HEIGHTS_FILE, MANIFEST_FILE):
        (out_dir / name).unlink(missing_ok=True)
    if not buildings_path.is_file():
        raise HeightError("building_table_absent")
    rules = load_rules(rules_path if rules_path is not None else RULES_PATH)
    buildings, landmark_citations = apply_landmark_heights(
        load_buildings(buildings_path), load_landmark_heights()
    )
    results = read_sources(cache, entries, rules, bounds=_table_bounds(buildings))
    index = globfp_index(results["bldg_3dglobfp"].globfp)
    rows, candidates, choices, globfp_matches = _resolve(
        buildings, rules, results, index
    )
    counts = height_counts(choices, globfp_matches)
    errors = fallback_errors(candidates)
    heights_body = dump_sorted(rows)
    input_files: list[dict[str, object]] = [
        {
            "key": "building_table",
            "path": BUILDINGS_RELATIVE,
            "role": "read",
            "sha256": file_sha256(buildings_path.read_bytes()),
            "source_chain": (
                "the asset pipeline's own manifest entry of the same key and sha256"
            ),
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
        errors,
        input_files,
        terms_attempts=terms_attempts,
        landmark_citations=landmark_citations,
        gba_calibration=gba_calibration(buildings, results["bldg_gba"]),
    )
    write_outputs(
        out_dir,
        {
            HEIGHTS_FILE: heights_body,
            MANIFEST_FILE: dump_sorted(block),
        },
    )
    lines.append(
        f"PASS heights rows={len(rows)} fallback_buildings={counts.fallback_buildings}"
    )


__all__ = [
    "BUILDINGS_RELATIVE",
    "HEIGHTS_RELATIVE",
    "HeightError",
    "build_heights",
]
