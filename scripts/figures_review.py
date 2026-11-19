"""Lead-only comparison entry: ``figures_review.py STORED REVIEWER OUTPUT``.

The callable accepts explicit paths: full stored draw and reviewer inputs stay
under data/ in live use. Tests call it only with invented temporary files. The
command line (S2-T08 part B, pass 3) prints and writes figure IDs, addresses
and match status only; its rule-44 clause is proposed to the lead.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Sequence
from dataclasses import fields
from pathlib import Path

from eii_custodian.publicdata.draw import Figure
from eii_custodian.publicdata.figures_review import compare, validate_record

USAGE = "usage: figures_review.py STORED REVIEWER OUTPUT"
# Closed refusals of ``run`` and the comparison; any other text is never shown.
REASONS = frozenset(
    {
        "figure_schema_invalid",
        "figure_review_count_invalid",
        "reviewer_schema_invalid",
        "reviewer_ids_mismatch",
        "figure_invalid",
        "committed_source_value",
        "review_result_invalid",
    }
)


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
    if len(stored) != 20:
        raise ValueError("figure_review_count_invalid")
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


def main(argv: Sequence[str]) -> int:
    """Three paths or a usage error (2) before any read; a refusal is 1."""
    if (
        len(argv) != 3
        or any(not arg or arg.startswith("-") for arg in argv)
        or Path(argv[2]).resolve() in {Path(argv[0]).resolve(), Path(argv[1]).resolve()}
    ):
        print(USAGE, file=sys.stderr)
        return 2
    stored, reviewer, output = (Path(arg) for arg in argv)
    try:
        code = run(stored, reviewer, output)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        print("figures_review: review_input_unreadable", file=sys.stderr)
        return 1
    except ValueError as exc:
        reason = str(exc) if str(exc) in REASONS else "review_input_invalid"
        print("figures_review: " + reason, file=sys.stderr)
        return 1
    verdict = json.loads(output.read_text(encoding="utf-8"))
    validate_record(verdict, "verdict")
    for row in verdict:
        print(row["figure_id"], row["url"], row["result"])
    return code


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
