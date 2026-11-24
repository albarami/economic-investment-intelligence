"""frame_grid builds the build's own grid and writes nothing (ruling L-1748 item 2).

Every cache, review file and name here is invented (the seventh-pass world).
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from custodian.tests.test_frame_live_survivors import _world

from eii_custodian.publicdata.fetch.snapshots import reviewed_selections
from eii_custodian.publicdata.frame.build import build_frame, inspect_cache
from eii_custodian.publicdata.frame.live import frame_grid


def _tree(root: Path) -> dict[str, str]:
    """Every path under root with the sha256 of each file; a folder is listed."""
    return {
        str(path.relative_to(root)): (
            hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else "/"
        )
        for path in sorted(root.rglob("*"))
    }


def test_frame_grid_writes_nothing_and_equals_the_builds_grid(tmp_path: Path) -> None:
    prepared = _world(tmp_path)
    cache_before, review_before = _tree(prepared.cache), _tree(prepared.review)
    selections = reviewed_selections(prepared.cache)
    inspected = inspect_cache(
        prepared.cache, prepared.entries, prepared.review, selections
    )
    staged = frame_grid(
        prepared.cache, prepared.entries, prepared.review, selections, inspected
    )
    assert _tree(prepared.cache) == cache_before
    assert _tree(prepared.review) == review_before
    assert staged.grid
    built = build_frame(prepared.cache, prepared.entries, prepared.review)
    assert staged.grid == built.tables["grid_cell"]
