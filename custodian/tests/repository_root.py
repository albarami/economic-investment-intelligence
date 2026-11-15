"""Find the repository root from a test file's own location, at any depth.

A package test sits at `<root>/custodian/tests/` in a checkout and at
`<root>/custodian/mutants/tests/` in the mutation runner's copy. A test never
relies on the working folder: it anchors every path on the root found here.
"""

from __future__ import annotations

from pathlib import Path

MARKERS = ("AGENTS.md", "custodian/publicdata/sources.yaml")
LEVELS = 4


class RepositoryRootNotFoundError(LookupError):
    """No folder within the allowed levels above the start holds both markers."""


def repository_root(start: Path) -> Path:
    """Return the first folder above `start` that holds both marker files."""
    resolved = start.resolve()
    for folder in list(resolved.parents)[:LEVELS]:
        if all((folder / marker).is_file() for marker in MARKERS):
            return folder
    raise RepositoryRootNotFoundError(
        f"no folder within {LEVELS} levels above {resolved.name} holds "
        + " and ".join(MARKERS)
    )
