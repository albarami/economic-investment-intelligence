"""Closed command adapter; evaluation dependencies are loaded only on demand."""

from __future__ import annotations

import sys
from collections.abc import Mapping, Sequence
from pathlib import Path

from commands import table
from eii_core.reasons import reason


def parse(args: Sequence[str]) -> tuple[int, int] | None:
    if len(args) != 5 or args[0] != "run":
        return None
    fields = dict(zip(args[1::2], args[2::2], strict=True))
    if set(fields) != {"--n", "--seed"}:
        return None
    if any(
        not text.isascii() or not text.isdecimal() or len(text) > 6
        for text in fields.values()
    ):
        return None
    n, seed = int(fields["--n"]), int(fields["--seed"])
    return (n, seed) if n >= 100 else None


def run(root: Path, environ: Mapping[str, str], args: Sequence[str]) -> int:
    parsed = parse(args)
    if parsed is None:
        table.write_usage()
        return 2
    sys.path.insert(0, str(root))
    from evals.question_lab.runner import run_lab

    try:
        return run_lab(root, environ, *parsed)
    except Exception as error:
        # No arbitrary exception, path, environment value or child output.
        print("FAIL question-lab: " + reason(error), file=sys.stderr)
        return 1
