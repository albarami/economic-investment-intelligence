"""Lead-only comparison entry. CLI grammar awaits the lead's rule-44 clause.

The callable accepts explicit paths: full stored draw and reviewer inputs stay
under data/ in live use. Tests call it only with invented temporary files.
"""

from __future__ import annotations

import json
from dataclasses import fields
from pathlib import Path

from eii_custodian.publicdata.draw import Figure
from eii_custodian.publicdata.figures_review import compare, validate_record


def run(stored_path: Path, reviewer_path: Path, output_path: Path) -> int:
    """Write only the value-free verdict, returning failure for any no-match."""
    stored = json.loads(stored_path.read_text(encoding="utf-8"))
    reviewer = json.loads(reviewer_path.read_text(encoding="utf-8"))
    names = {field.name for field in fields(Figure)}
    if not isinstance(stored, list) or not all(
        isinstance(row, dict)
        and set(row) == names
        and all(isinstance(value, str) for value in row.values())
        for row in stored
    ):
        raise ValueError("figure_schema_invalid")
    if not isinstance(reviewer, dict) or not all(
        isinstance(k, str) and isinstance(v, str) for k, v in reviewer.items()
    ):
        raise ValueError("reviewer_schema_invalid")
    verdict = compare([Figure(**row) for row in stored], reviewer)
    validate_record(verdict, "verdict")
    output_path.write_text(
        json.dumps(verdict, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return 0 if verdict and all(row["result"] == "match" for row in verdict) else 1
