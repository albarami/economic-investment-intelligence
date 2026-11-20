"""``run_build`` wrapper that prepares the minimal building table."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from custodian.tests.support.buildings import ensure_minimal_building_table


def _shared_session_assets(cache: Path) -> Path | None:
    """Return the session-shared assets folder flat-cache runs may pollute."""
    if cache.name == "public_cache":
        return None
    parent = cache.parent
    if not parent.name.startswith("pytest-"):
        return None
    return parent / "assets"


def run_build(*args: Any, **kwargs: Any) -> Any:
    """Call production ``run_build`` after ensuring the building table exists."""
    from eii_custodian.publicdata.fetch.build import run_build as _run_build

    cache: Path | None = None
    if len(args) >= 3:
        cache = args[2]
    if cache is None:
        cache = kwargs.get("cache")
    cleanup: Path | None = None
    if cache is not None:
        ensure_minimal_building_table(cache)
        cleanup = _shared_session_assets(cache)
    try:
        return _run_build(*args, **kwargs)
    finally:
        if cleanup is not None and cleanup.is_dir():
            shutil.rmtree(cleanup)
