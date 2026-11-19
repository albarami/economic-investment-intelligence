"""Planted product reads, serving routes, derived facts and release inclusions."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import import_boundary_cases as cases
import import_boundary_guard as guard


class UnreadBackup(unittest.TestCase):
    def test_product_cache_read_serve_config_and_fact_refused(self) -> None:
        plants = (
            'open("data/public_cache/satellite_cdse_backup/tile.tif", "rb")',
            'mount("/imagery", directory="data/public_cache")',
            'config = {"imagery": "satellite_cdse_backup"}',
            "from eii_custodian.publicdata.cdse.cache import parents",
            'fact = {"source": "satellite_cdse_backup", "value": 7}',
        )
        for plant in plants:
            with self.subTest(plant=plant), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                cases.make_tree(root)
                cases.write_planted(root, "eii_product", plant + "\n")
                failures, _notes = guard.check_imports(root)
                self.assertTrue(failures, plant)

    def test_release_freeze_generator_inclusion_refused(self) -> None:
        for area in ("release", "freeze", "world", "assignment_spike"):
            with self.subTest(area=area), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                cases.make_tree(root)
                path = cases.package_dir(root, "eii_custodian") / area / "planted.py"
                path.parent.mkdir()
                path.write_text('asset = "satellite_cdse_backup"\n')
                failures, _notes = guard.check_imports(root)
                self.assertTrue(failures)

    def test_cache_file_bundled_in_product_refused(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            cases.make_tree(root)
            path = cases.package_dir(root, "eii_product") / "satellite_cdse_backup"
            path.mkdir()
            (path / "picture.bin").write_bytes(b"invented raster")
            failures, _notes = guard.check_imports(root)
            self.assertTrue(failures)

    def test_empty_product_stays_independent(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            cases.make_tree(root)
            self.assertEqual(guard.check_imports(root), ([], []))
