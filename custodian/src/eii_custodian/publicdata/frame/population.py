"""Reviewed indicator selection with exact municipality-key pairing."""

from pathlib import Path
from typing import Any

from .census import UNITS
from .checks import FrameError
from .crosswalk import municipality_keys, read_csv
from .mapping import inspect_source


def load_indicators(review: Path) -> dict[str, str]:
    result = {}
    for row in read_csv(review / "population_indicators.csv"):
        name, token = row["indicator"], row["mapped_indicator"]
        if name in result:
            raise FrameError("pop_muni: duplicate_indicator")
        if token and token not in UNITS:
            raise FrameError(f"pop_muni: invalid_indicator: {token}")
        result[name] = token
    return result


def population_rows(
    payload: list[dict[str, Any]],
    review: Path,
    names: list[dict[str, str]],
    report_file: Path | None,
) -> tuple[list[dict[str, Any]], str]:
    indicators = load_indicators(review)
    inspected = inspect_source("pop_muni", payload, indicators)
    # Validate names on every source row (PUB-27), then retain keys in lockstep.
    keys = municipality_keys(
        "pop_muni", payload, ("municipality", "lbldy"), names, report_file
    )
    if len(keys) != len(payload):
        raise FrameError("pop_muni: municipality_key_length_mismatch")
    if inspected.reason.startswith("unreviewed_indicator"):
        return [], inspected.reason
    kept_keys = [
        key
        for row, key in zip(payload, keys, strict=True)
        if indicators[row["indicator"]]
    ]
    if len(kept_keys) != len(inspected.rows):
        raise FrameError("pop_muni: municipality_key_length_mismatch")
    for row, key in zip(inspected.rows, kept_keys, strict=True):
        row.pop("municipality_name")
        row["municipality_code"] = key
    return inspected.rows, inspected.reason
