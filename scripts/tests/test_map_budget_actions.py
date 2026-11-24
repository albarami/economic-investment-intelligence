"""Offline product actions on an invented release and temporary budget journal."""

from __future__ import annotations

import shutil
import tempfile
import unittest
from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path

import commands_support as support
import public_release_fixture as fixture

from eii_product.photoreal_tiles.limit import COUNT_PATH, Budget, BudgetFailure
from eii_product.store.loader import run_load
from preflight_store import PgOutcome, select_store


class ExistingSchema:
    """Database fixture: reload refuses an already installed release."""

    stand_in = True

    def execute(self, sql: str, params: object = None) -> list[tuple[object, ...]]:
        if "rolsuper" in sql:
            return [("eii_owner", False)]
        if "extnamespace" in sql:
            return [("SYN_extensions",)]
        if "extname" in sql:
            return [("plpgsql",), ("postgis",)]
        if "pg_namespace" in sql:
            return [("SYN_installed",)]
        return []

    def close(self) -> None:
        pass


class BudgetActions(unittest.TestCase):
    def test_store_selection_new_release_restore_and_reload_preserve_count(
        self,
    ) -> None:
        self.assertEqual(COUNT_PATH, support.ROOT / "data" / "photoreal-count.log")
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            journal = root / "count.log"
            journal.write_text("ready:0\n", encoding="ascii")
            Budget(journal).request(1, lambda: True, bool)
            before = journal.read_bytes()

            def unchanged() -> None:
                self.assertEqual(journal.read_bytes(), before)
                with self.assertRaisesRegex(BudgetFailure, "cap_reached"):
                    Budget(journal).available(1)

            for probe, expected in (
                (PgOutcome("ok", "SYN-ready"), "postgres"),
                (None, "embedded"),
            ):
                self.assertEqual(select_store(probe, None).store, expected)
                unchanged()
            release = root / "release"
            release.mkdir()
            fixture.build_fixture(release)
            unchanged()
            restored = root / "restored"
            shutil.copytree(release, restored)
            unchanged()
            for target in (release, restored, release):
                error = StringIO()
                with redirect_stderr(error):
                    code = run_load(
                        target,
                        host="fixture.invalid",
                        port=1,
                        database="SYN_database",
                        connect=lambda **kwargs: ExistingSchema(),
                    )
                self.assertEqual(code, 1, error.getvalue())
                self.assertIn("schema_exists", error.getvalue())
                unchanged()
