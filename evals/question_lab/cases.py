"""Versioned invented identities, language pairs and deterministic SHA ordering."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

LANGUAGES = ("en", "ar")
THEMES = ("dark", "light")


@dataclass(frozen=True)
class Case:
    identity: str
    family: str
    questions: dict[str, str]
    mode: str
    pin: float
    month: str
    expected_value: int | None
    expected_anchor_cell: str
    refusal: str | None
    angles: dict[str, str]


def load_cases(root: Path) -> tuple[Case, ...]:
    raw = json.loads((root / "evals/question_lab/cases.v1.json").read_text())
    if (
        set(raw) != {"version", "counting_unit", "cases"}
        or raw["version"] != "question-lab.v1"
    ):
        raise ValueError("question_manifest")
    cases = tuple(Case(**row) for row in raw["cases"])
    if any(
        set(case.questions) != set(LANGUAGES)
        or not case.identity.startswith("INVENTED-question-")
        for case in cases
    ):
        raise ValueError("question_manifest")
    return cases


def select_cases(cases: Sequence[Case], n: int, seed: int) -> tuple[Case, ...]:
    if len({c.identity for c in cases}) != len(cases):
        raise ValueError("question_identity")
    if n < 100 or n > len(cases) or seed < 0:
        raise ValueError("question_capacity")
    ordered = sorted(
        cases,
        key=lambda case: hashlib.sha256(
            f"question-lab.v1:{seed}:{case.identity}".encode()
        ).digest(),
    )
    selected = tuple(ordered[:n])
    if {case.family for case in selected} != {"flagship", "map", "chip", "refusal"}:
        raise ValueError("question_families")
    return selected


def coverage(cases: Sequence[Case]) -> dict[str, Any]:
    """Declare the finite domains before sampling, including unsupported cells."""
    domains = {
        "family": ("flagship", "map", "chip", "refusal"),
        "mode": ("polygon", "distance", "walk", "drive"),
        "activity": ("craft", "repair"),
        "place": ("garden", "square"),
        "intent": ("evidence", "map", "source", "decline"),
        "persona": ("founder", "analyst"),
        "phrasing": ("direct", "clarify"),
        "device": ("stage", "phone"),
        "hour": ("morning", "evening"),
        "day": ("weekday", "weekend"),
        "conversation": ("single", "clarification", "interrupt", "reset"),
    }
    rows: list[dict[str, Any]] = []
    for axis, domain in domains.items():
        counts = Counter(
            getattr(case, axis) if axis in {"family", "mode"} else case.angles[axis]
            for case in cases
        )
        rows.extend(
            {
                "axis": axis,
                "cell": cell,
                "count": counts[cell],
                "scope": "planned_inputs",
                "owner": "S3-T21",
            }
            for cell in domain
        )
    # Coverage of execution is joined by runner, never inferred from angle labels.
    missing = [
        ("free_text", "S8-T03", "no_free_text_route_at_head"),
        ("must_decline_pay_lookup_footfall", "S8-T03", "no_free_text_route_at_head"),
        ("must_suppress", "S5-T07", "public_only_path_component_fixture_only"),
        ("ranking_explanations", "S6-T11", "later_executor"),
        ("speech", "S8-T10", "later_executor"),
        ("native_stage", "S3-T21", "device_not_declared"),
        ("native_phone", "S3-T21", "device_not_declared"),
        ("held_out", "S3-T21", "separate_identity_not_provisioned"),
        ("dated_opening_chip", "S3-T10", "prerequisite_uncovered"),
        ("firms_chain", "S3-T10", "prerequisite_uncovered"),
    ]
    empty = [row for row in rows if row["count"] == 0]
    empty.extend(
        {
            "axis": "execution",
            "cell": cell,
            "count": 0,
            "owner": owner,
            "reason": reason,
        }
        for cell, owner, reason in missing
    )
    cross = [
        {
            "family": family,
            "mode": mode,
            "count": sum(c.family == family and c.mode == mode for c in cases),
        }
        for family in domains["family"]
        for mode in domains["mode"]
    ]
    empty.extend(
        {
            "axis": "family_mode",
            "cell": f"{row['family']}:{row['mode']}",
            "count": 0,
            "owner": "S3-T21",
        }
        for row in cross
        if row["count"] == 0
    )
    return {
        "planned_distinct_questions": len(cases),
        "planned_language_executions": len(cases) * 2,
        "language_executions": 0,
        "counting_unit": "distinct_question_identity_each_in_both_languages",
        "domains": domains,
        "cells": rows,
        "cross_cells": cross,
        "empty_cells": empty,
    }


def execution_coverage(
    cases: Sequence[Case],
    results: Sequence[Mapping[str, Any]],
    captures: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    from evals.question_lab.packet import SIZES

    grid = coverage(cases)
    identities = {case.identity for case in cases}
    pairs = {(row.get("question_id"), row.get("language")) for row in results}
    grid.update(
        language_executions=len(results),
        successful_language_executions=sum(not row.get("problems") for row in results),
        complete_bilingual_identities=sum(
            all((identity, lang) in pairs for lang in LANGUAGES)
            for identity in identities
        ),
        sealed_identities_executed=0,
    )
    grid["capture_cells"] = [
        {
            "axis": "capture",
            "cell": f"{w}x{h}:{lang}:{theme}",
            "size": f"{w}x{h}",
            "language": lang,
            "theme": theme,
            "count": sum(
                row.get("size") == f"{w}x{h}"
                and row.get("language") == lang
                and row.get("theme") == theme
                for row in captures
            ),
            "owner": "S3-T21",
            "reason": "browser_observations_required",
        }
        for w, h in SIZES
        for lang in LANGUAGES
        for theme in THEMES
    ]
    grid["judgement_cells"] = [
        {
            "axis": "full_judgement",
            "cell": key,
            "count": sum(
                row.get("judgements", {}).get(key) == "passed:complete"
                for row in results
            ),
            "owner": "S3-T21",
            "reason": "typed_API_or_fixture_evidence_is_partial",
        }
        for key in ("accuracy", "smoothness", "value", "visual", "map")
    ]
    grid["empty_cells"].extend(
        row
        for row in [*grid["capture_cells"], *grid["judgement_cells"]]
        if row["count"] == 0
    )
    grid["empty_cells"].extend(
        {
            "axis": "conversation_execution",
            "cell": cell,
            "count": 0,
            "owner": "S3-T21",
            "reason": "UI_episode_not_executed_by_typed_API_adapter",
        }
        for cell in ("clarification", "interrupt", "reset", "late_repaint")
    )
    return grid
