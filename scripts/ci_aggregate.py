"""Judge the hosted `tests` check from the results of the jobs it needs.

Standard library only: the final job runs it with the runner's own Python and
no environment sync. Usage: ``ci_aggregate.py NEEDS_JSON`` where NEEDS_JSON is
the workflow expression ``toJSON(needs)``. A matrix job's result is
``success`` only when every leg succeeded; a failed, cancelled or skipped job,
a missing job or an extra job fails the check.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Sequence
from typing import TextIO

NEEDED = ("suite", "web-spikes")
USAGE = "usage: ci_aggregate.py NEEDS_JSON"


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
    """Print the verdict and return 0 when every needed job succeeded, else 1."""
    if len(argv) != 1:
        print(USAGE, file=out)
        return 2
    found = problems(argv[0])
    for line in found:
        print(line, file=out)
    print("RESULT: " + ("FAILED" if found else "PASSED"), file=out)
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
