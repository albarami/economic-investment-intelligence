"""Minimal invented building table for run_build fixtures (S2-P21)."""

from __future__ import annotations

from pathlib import Path

from custodian.tests.fixtures.heights import invented

from eii_custodian.publicdata.heights.model import BUILDINGS_RELATIVE


def building_table_path(data_root: Path) -> Path:
    """The heights step building table under a cache parent (data root)."""
    return data_root / BUILDINGS_RELATIVE


def ensure_minimal_building_table(cache: Path) -> tuple[Path, bool]:
    """Write one valid invented building row beside the public cache.

    ``cache`` is the directory passed to ``run_build``. The table lives at
    ``cache.parent / assets/buildings/buildings.geojson``. The second return
    value is true only when this call created the file.
    """
    path = building_table_path(cache.parent)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file():
        return path, False
    path.write_bytes(
        invented.buildings_bytes(
            [
                invented.building_feature(
                    "SYN-B-0001",
                    invented.square(0.0, 0.0, 1.0),
                    None,
                    None,
                )
            ]
        )
    )
    return path, True
