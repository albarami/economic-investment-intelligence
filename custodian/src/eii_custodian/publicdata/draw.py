"""Uniform source-checkable figure draw; no stored values in review metadata."""

from __future__ import annotations

import json
import os
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from random import Random
from typing import TypedDict


@dataclass(frozen=True)
class Figure:
    figure_id: str
    source_id: str
    url: str
    filter: str
    value: str
    kind: str
    provenance: str = "Public"


class Sheet(TypedDict):
    seed: int
    figures: list[dict[str, str]]


def validate_figure(figure: Figure) -> None:
    """Eligible figures have finite stored values and complete source links."""
    if (
        figure.provenance != "Public"
        or figure.kind not in {"count", "money", "ratio"}
        or not all(
            isinstance(value, str) and value.strip()
            for value in (
                figure.figure_id,
                figure.source_id,
                figure.url,
                figure.filter,
                figure.value,
            )
        )
        or not figure.url.startswith("https://")
    ):
        raise ValueError("figure_invalid")
    try:
        valid = Decimal(figure.value).is_finite()
    except InvalidOperation:
        valid = False
    if not valid:
        raise ValueError("figure_invalid")


def sample(figure_index: Sequence[str], seed: int) -> list[str]:
    """Unweighted sampling without replacement; stable across reader order."""
    if type(seed) is not int:
        raise ValueError("figure_seed_invalid")
    if len(set(figure_index)) != len(figure_index):
        raise ValueError("figure_identity_duplicate")
    if len(figure_index) < 20:
        raise ValueError("figure_review_insufficient")
    return Random(seed).sample(sorted(figure_index), 20)


def _flush(path: Path, log: dict[str, object]) -> None:
    with path.open("w", encoding="utf-8") as stream:
        json.dump(log, stream, sort_keys=True)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def draw(
    tables: Mapping[str, Callable[[], Sequence[Figure]]], seed: int, log_path: Path
) -> list[Figure]:
    """Durably record seed before invoking even the first table reader.

    Readers enumerate stored Public numeric fields; administrative counts,
    hashes and keys are explicitly excluded. An inaccessible table refuses the
    whole draw instead of silently reducing its eligible universe. Full values
    stay with the caller under its documented data directory, never in this log.
    """
    if type(seed) is not int:
        raise ValueError("figure_seed_invalid")
    loaded = (
        json.loads(log_path.read_text(encoding="utf-8")) if log_path.exists() else {}
    )
    if not isinstance(loaded, dict):
        raise ValueError("figure_log_invalid")
    log: dict[str, object] = dict(loaded)
    # A failed repeat must not retain the previous draw as if it succeeded.
    log.pop("figure_ids", None)
    log["figure_seed"] = seed
    _flush(log_path, log)
    universe: dict[str, Figure] = {}
    for table in sorted(tables):
        try:
            rows = tables[table]()
        except OSError:
            raise ValueError("figure_table_unreachable:" + table) from None
        for figure in rows:
            if figure.kind in {"administrative_count", "hash", "key"}:
                continue
            validate_figure(figure)
            if figure.figure_id in universe:
                raise ValueError("figure_identity_duplicate")
            universe[figure.figure_id] = figure
    selected = sample(list(universe), seed)
    log["figure_ids"] = selected
    _flush(log_path, log)
    return [universe[key] for key in selected]


def reviewer_sheet(seed: int, figures: Sequence[Figure]) -> Sheet:
    """Commit-safe identifiers and links only, regardless of source licence."""
    for figure in figures:
        validate_figure(figure)
    return {
        "seed": seed,
        "figures": [
            {
                "figure_id": f.figure_id,
                "source_id": f.source_id,
                "url": f.url,
                "filter": f.filter,
            }
            for f in figures
        ],
    }
