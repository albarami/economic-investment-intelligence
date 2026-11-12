"""Placeholder body for commands whose work is not built."""

from __future__ import annotations

from . import exits, table


def run(command: str) -> int:
    """Exit 1 without reading the environment or starting a process."""
    return exits.finish(1, command, table.by_word(command).detail)
