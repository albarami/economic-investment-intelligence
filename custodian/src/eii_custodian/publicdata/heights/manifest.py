"""B7: the deterministic writer of the heights file and the manifest block.

Both files are written with sorted keys and rows and carry no wall-clock field
other than the receipts' recorded times, so two runs on identical inputs give
identical bytes (FE-98). A row with a column beyond the closed set, or a
`height_source` outside the closed list, is refused (ruling R4).
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

from eii_core.calc.building_heights import (
    FALLBACKS,
    HEIGHT_SOURCES,
    NONE_SOURCE,
    FallbackError,
    HeightChoice,
    HeightCounts,
)

from .model import OUTPUT_COLUMNS, HeightError, Rules
from .read import SourceResult

CARD_ID = "C47"
METHOD_ID = "MTH-125"
METHOD_LINE = (
    "signed error = fallback height - recorded height, in metres; the median "
    "of an even count is the mean of the two central values"
)
ESTIMATE_LABEL = "Heights are estimates."


def _number(value: Decimal | None) -> str | None:
    """Serialise the rounded Decimal as its own text; the asset writes no float."""
    if value is None:
        return None
    return str(value)


def check_row(row: dict[str, object]) -> None:
    """A row outside the closed columns or the closed source list is refused."""
    if set(row) != OUTPUT_COLUMNS:
        raise HeightError("output_columns")
    if row["height_source"] not in HEIGHT_SOURCES:
        raise HeightError("output_source")
    if row["height_source"] == NONE_SOURCE:
        if row["height_m"] is not None or not row["reason"]:
            raise HeightError("output_none")
    elif row["height_m"] is None or row["reason"] != "":
        raise HeightError("output_row")


def output_row(
    building_id: str,
    choice: HeightChoice,
    footprint_source_id: str,
    reason: str,
) -> dict[str, object]:
    """One output row; `none` carries the reason and never the number 0."""
    row: dict[str, object] = {
        "building_id": building_id,
        "footprint_source_id": footprint_source_id,
        "height_m": _number(choice.height),
        "height_source": choice.source,
        "reason": reason,
    }
    check_row(row)
    return row


def dump_sorted(payload: object) -> bytes:
    """Serialise with sorted keys; the bytes are the deterministic output."""
    return (json.dumps(payload, sort_keys=True, ensure_ascii=True) + "\n").encode(
        "utf-8"
    )


def _error_block(errors: dict[str, FallbackError]) -> dict[str, object]:
    block: dict[str, object] = {}
    for name in FALLBACKS:
        error = errors[name]
        block[name] = {
            "count": error.count,
            "mean_absolute_error_m": _number(error.mean_absolute),
            "mean_signed_error_m": _number(error.mean_signed),
            "median_absolute_error_m": _number(error.median_absolute),
            "reason": error.reason,
        }
    return block


def _attempts_of(
    source_id: str, terms_attempts: tuple[dict[str, object], ...]
) -> list[dict[str, object]]:
    """This source's unread-terms attempts of the run, in key order."""
    found = [
        dict(item)
        for item in terms_attempts
        if isinstance(item.get("key"), str)
        and (item["key"] == source_id or str(item["key"]).startswith(source_id + "/"))
    ]
    return sorted(found, key=lambda item: str(item["key"]))


def _credits(
    rules: Rules,
    results: dict[str, SourceResult],
    terms_attempts: tuple[dict[str, object], ...] = (),
) -> dict[str, object]:
    """The doc-04 credit text for 3D-GloBFP; WSF 3D keeps its recorded terms.

    An unread terms page of this run is carried as an attempt beside the
    recorded reading date and words, which stay as the registry holds them
    (S2-T08 part B, mismatch class 9).
    """
    globfp = results["bldg_3dglobfp"]
    credit = ""
    if globfp.retrieved_utc:
        credit = rules.credit_3dglobfp.replace("{date}", globfp.retrieved_utc[:10])
    return {
        "bldg_3dglobfp": {
            "credit": credit,
            "terms_attempts": _attempts_of("bldg_3dglobfp", terms_attempts),
            "terms_read_on": globfp.terms_read_on,
            "terms_words": globfp.terms_words,
        },
        "bldg_wsf3d": {
            "terms_attempts": _attempts_of("bldg_wsf3d", terms_attempts),
            "terms_read_on": results["bldg_wsf3d"].terms_read_on,
            "terms_words": results["bldg_wsf3d"].terms_words,
        },
    }


def manifest_block(
    rules: Rules,
    results: dict[str, SourceResult],
    counts: HeightCounts,
    errors: dict[str, FallbackError],
    input_files: list[dict[str, object]],
    *,
    terms_attempts: tuple[dict[str, object], ...] = (),
) -> dict[str, object]:
    """The height block of the asset manifest (FE-96)."""
    files: list[dict[str, object]] = list(input_files)
    for source_id in ("bldg_3dglobfp", "bldg_wsf3d"):
        files.extend(results[source_id].files)
    files.sort(key=lambda record: str(record["key"]))
    return {
        "card": CARD_ID,
        "counts": counts.by_source,
        "credits": _credits(rules, results, terms_attempts),
        "errors": _error_block(errors),
        "estimate_label": ESTIMATE_LABEL,
        "files": files,
        "match_3dglobfp": rules.match_3dglobfp,
        "match_wsf3d": rules.match_wsf3d,
        "method": METHOD_ID,
        "method_line": METHOD_LINE,
        "none_reasons": counts.none_reasons,
        "no_value_reasons": counts.no_value_reasons,
        "order": rules.order,
        "sources": {
            source_id: {
                "reason": results[source_id].reason,
                "state": results[source_id].state,
                "rows": list(results[source_id].rows),
            }
            for source_id in ("bldg_3dglobfp", "bldg_wsf3d")
        },
        "storey_height_m": {
            "basis": rules.basis,
            "label": rules.label,
            "value": rules.storey_value,
        },
        "tied_height_buildings": counts.tied_height_buildings,
    }


def write_outputs(out_dir: Path, files: dict[str, bytes]) -> None:
    """Write each prepared file under the heights output directory."""
    out_dir.mkdir(parents=True, exist_ok=True)
    for name in sorted(files):
        (out_dir / name).write_bytes(files[name])


__all__ = [
    "CARD_ID",
    "ESTIMATE_LABEL",
    "METHOD_ID",
    "METHOD_LINE",
    "check_row",
    "dump_sorted",
    "manifest_block",
    "output_row",
    "write_outputs",
]
