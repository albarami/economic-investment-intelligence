"""``run_build`` wrapper that prepares the minimal building table."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import patch

from custodian.tests.building_fixture import COLLECTION, PARTS, bind_height_table
from custodian.tests.support.buildings import ensure_minimal_building_table


def run_build(*args: Any, **kwargs: Any) -> Any:
    """Supply isolated inventory at the real height adapter's input boundary.

    National-frame fixtures supply their own producer inputs. Other acquisition
    fixtures use the shared invented C47 table after frame invalidation. Neither
    the height producer nor its manifest verifier is replaced.
    """
    from eii_custodian.publicdata.fetch.build import _heights
    from eii_custodian.publicdata.fetch.build import run_build as _run_build

    created_paths: list[Path] = []
    fixture_before: dict[Path, bytes] = {}
    fixture_after: set[Path] = set()
    created_directories: set[Path] = set()

    def heights(
        cache: Path, entries: Any, *height_args: Any, **height_kwargs: Any
    ) -> Any:
        # Frame production invalidates old inventory first. Supply the isolated
        # fixture only at the height boundary, after that invalidation, and run
        # the real adapter and manifest verifier over the invented dependencies.
        # A fixture exercising a national frame owns its own inventory inputs.
        if not any(row.source_id == "bnd_hdx" for row in entries):

            def fixture_directories() -> set[Path]:
                return {
                    directory
                    for root in (cache / "bldg_ovt", cache / "bnd_hdx")
                    for directory in (root, *root.rglob("*"))
                    if directory.is_dir()
                }

            def fixture_files() -> set[Path]:
                return {
                    file
                    for key in (*PARTS, COLLECTION, "bnd_hdx")
                    for file in (cache / key).rglob("*")
                    if file.is_file()
                } | {cache / "snapshot_pins.json"}

            fixture_before.update(
                (file, file.read_bytes()) for file in fixture_files() if file.is_file()
            )
            directories_before = fixture_directories()
            path, created = ensure_minimal_building_table(cache)
            if created:
                created_paths.extend((path, path.with_name("manifest.buildings.json")))
            # Acquisition tests may include inventory rows (even skipped ones).
            # This isolated height fixture uses its own invented inventory chain;
            # the caller's fetched rows and build log are left intact.
            entries = bind_height_table(
                cache,
                tuple(row for row in entries if row.source_id != "bldg_ovt"),
                path,
                write_manifest=False,
            )
            fixture_after.update(fixture_files())
            created_directories.update(fixture_directories() - directories_before)
            from eii_custodian.publicdata.fetch.snapshots import reviewed_selections

            height_kwargs["selections"] = reviewed_selections(cache)
        return _heights(cache, entries, *height_args, **height_kwargs)

    try:
        with patch("eii_custodian.publicdata.fetch.build._heights", heights):
            return _run_build(*args, **kwargs)
    finally:
        for path in created_paths:
            path.unlink(missing_ok=True)
        for file in fixture_after - fixture_before.keys():
            file.unlink(missing_ok=True)
        for file, body in fixture_before.items():
            file.write_bytes(body)
        for directory in sorted(
            created_directories, key=lambda path: len(path.parts), reverse=True
        ):
            if directory.is_dir() and not any(directory.iterdir()):
                directory.rmdir()
