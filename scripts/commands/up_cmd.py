"""The up command: probe, then refuse until serving exists."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path

import preflight

from . import exits, table


def run(root: Path, environ: Mapping[str, str], args: Sequence[str]) -> int:
    """Select a store and stop. Serving is not built."""
    if tuple(args) == ("--embedded",):
        embedded = True
    elif len(args) == 0:
        embedded = False
    else:
        table.write_usage()
        return 2
    report = preflight.run_preflight(
        root,
        environ,
        embedded=embedded,
        docker=False,
    )
    for line in report.text_lines():
        print(line)
    code, detail = preflight.up_decision(environ, report)
    if code != 0:
        return exits.finish(code, "up", detail)
    return exits.finish(1, "up", table.by_word("up").detail)
