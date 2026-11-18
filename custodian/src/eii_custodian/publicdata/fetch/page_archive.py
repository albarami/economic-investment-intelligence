"""Stage all artefacts of one page/intake before exposing its source directory."""

from __future__ import annotations

import shutil
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from .snapshots import SnapshotError


@contextmanager
def staged_source(cache: Path, key: str) -> Iterator[Path]:
    """Validate/write in a private copy; restore the previous source on failure.

    Callers validate their cache/key confinement first. Every existing archive
    object is copied so the snapshot reader still checks conflicts and tamper.
    The two renames may briefly make the source unavailable; no partially built
    source tree becomes visible. This is a single-writer build seam.
    """
    destination = cache / key
    if destination.exists() and any(p.is_symlink() for p in destination.rglob("*")):
        raise SnapshotError("snapshot_path_invalid")
    cache.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".page-stage-", dir=cache) as folder:
        stage = Path(folder) / "cache"
        staged = stage / key
        staged.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            shutil.copytree(destination, staged)
        yield stage
        backup = Path(folder) / "previous"
        destination.parent.mkdir(parents=True, exist_ok=True)
        existed = destination.exists()
        if existed:
            destination.rename(backup)
        try:
            staged.rename(destination)
        except BaseException:
            if existed:
                backup.rename(destination)
            raise
