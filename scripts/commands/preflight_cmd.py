"""The preflight command: probe and print."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path

import preflight

from . import exits, table


def run(root: Path, environ: Mapping[str, str], args: Sequence[str]) -> int:
    """Print the probe report. Write nothing and start nothing of our own."""
    if args:
        table.write_usage()
        return 2
    report = preflight.run_preflight(root, environ)
    for line in report.text_lines():
        print(line)
    if report.status == 0:
        return exits.finish(0, "preflight", "")
    names = [line.check for line in report.lines if line.severity == "FAIL"]
    detail = "a check failed: " + ", ".join(names)
    return exits.finish(1, "preflight", detail)
