"""``run_build`` wrapper that prepares the minimal building table."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from custodian.tests.support.buildings import ensure_minimal_building_table


def run_build(*args: Any, **kwargs: Any) -> Any:
    """Call production ``run_build`` after ensuring the building table exists."""
    from eii_custodian.publicdata.fetch.build import run_build as _run_build

    cache: Path | None = None
    if len(args) >= 3:
        cache = args[2]
    if cache is None:
        cache = kwargs.get("cache")
    created_table: Path | None = None
    if cache is not None:
        table_path, created = ensure_minimal_building_table(cache)
        if created:
            created_table = table_path
    try:
        return _run_build(*args, **kwargs)
    finally:
        if created_table is not None and created_table.is_file():
            created_table.unlink()
