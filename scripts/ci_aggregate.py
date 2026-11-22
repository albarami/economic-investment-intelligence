"""Judge the hosted `tests` check from the results of the jobs it needs.

Usage: ``ci_aggregate.py WORKFLOW NEEDS_JSON`` where WORKFLOW is the checked-out
``ci.yml`` and NEEDS_JSON is the workflow expression ``toJSON(needs)``. Before
it reads a result, the matrix list of job ``suite`` in WORKFLOW must equal the
SUITES table, so a suite dropped from the matrix fails here and not only in the
guard tests that suite runs. A matrix job's result is ``success`` only when
every leg succeeded; a failed, cancelled or skipped job, a missing job or an
extra job fails the check.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import TextIO

import yaml

import run_tests

NEEDED = ("suite", "web-spikes")
USAGE = "usage: ci_aggregate.py WORKFLOW NEEDS_JSON"
NOT_A_LIST = "FAIL matrix-unreadable: the suite matrix is not a list of names"


def matrix_problems(matrix: object) -> list[str]:
    """Return one FAIL line per difference between the matrix list and SUITES."""
    if not isinstance(matrix, list) or not all(isinstance(n, str) for n in matrix):
        return [NOT_A_LIST]
    if not matrix:
        return ["FAIL matrix-empty: the suite matrix lists no suite"]
    names = [suite.name for suite in run_tests.SUITES]
    found = [f"FAIL matrix-missing: {name}" for name in names if name not in matrix]
    found += [f"FAIL matrix-unexpected: {n}" for n in sorted(set(matrix) - set(names))]
    twice = sorted({name for name in matrix if matrix.count(name) > 1})
    found += [f"FAIL matrix-duplicate: {name}" for name in twice]
    if not found and matrix != names:
        found.append("FAIL matrix-order: the suite matrix is not in SUITES order")
    return found


def workflow_problems(path: Path) -> list[str]:
    """Read job ``suite``'s matrix list from WORKFLOW and compare it with SUITES."""
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as error:
        return [f"FAIL workflow-unreadable: {type(error).__name__}"]
    matrix: object = document
    for key in ("jobs", "suite", "strategy", "matrix", "suite"):
        if not isinstance(matrix, dict):
            return [NOT_A_LIST]
        matrix = matrix.get(key)
    return matrix_problems(matrix)


def problems(text: str) -> list[str]:
    """Return one FAIL line per fault; an empty list means every job succeeded."""
    try:
        needs = json.loads(text)
    except json.JSONDecodeError as error:
        return [f"FAIL needs-unreadable: {error.msg}"]
    if not isinstance(needs, dict):
        return ["FAIL needs-unreadable: not a mapping of job results"]
    found: list[str] = []
    for job in sorted(set(NEEDED) - set(needs)):
        found.append(f"FAIL shard-missing: {job}")
    for job in sorted(set(needs) - set(NEEDED)):
        found.append(f"FAIL shard-unexpected: {job}")
    for job in NEEDED:
        entry = needs.get(job)
        if job not in needs:
            continue
        result = entry.get("result") if isinstance(entry, dict) else None
        if result != "success":
            found.append(f"FAIL shard-result: {job}: {result}")
    return found


def main(argv: Sequence[str], out: TextIO = sys.stdout) -> int:
    """Print the verdict: 0 when the matrix is whole and every job succeeded."""
    if len(argv) != 2:
        print(USAGE, file=out)
        return 2
    found = [*workflow_problems(Path(argv[0])), *problems(argv[1])]
    for line in found:
        print(line, file=out)
    print("RESULT: " + ("FAILED" if found else "PASSED"), file=out)
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
