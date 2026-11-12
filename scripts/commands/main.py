"""Dispatch one ./eii command."""

from __future__ import annotations

import os
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import commands.database as database
import commands.placeholder as placeholder
import commands.preflight_cmd as preflight_cmd
import commands.table as table
import commands.up_cmd as up_cmd


def main(argv: Sequence[str], environ: Mapping[str, str], root: Path) -> int:
    """Dispatch one command and return an exit code from 0 to 7."""
    if len(argv) == 0 or argv[0] not in table.WORDS or argv[0] == "test":
        table.write_usage()
        return 2
    word = argv[0]
    rest = argv[1:]
    if word == "preflight":
        return preflight_cmd.run(root, environ, rest)
    if word in {"db-up", "db-down"}:
        return database.run(word, environ, root, rest)
    if word == "up":
        return up_cmd.run(root, environ, rest)
    if word in table.PLACEHOLDERS:
        if rest:
            table.write_usage()
            return 2
        return placeholder.run(word)
    table.write_usage()
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:], os.environ, Path(__file__).resolve().parents[2]))
