"""The public fixture is the catalogue's public tables, seeded and invented."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import public_release_fixture as fixture

from eii_core.manifest import CATALOGUE
from eii_custodian.release.public_only import TableWrite


class PublicFixture(unittest.TestCase):
    def test_fixture_holds_every_public_table(self) -> None:
        """The declarations are the catalogue's public tables, not a private list."""
        names = fixture.included_names()
        self.assertIsNone(fixture.missing_public(names))
        self.assertIn("pub_venue_busyness", names)
        self.assertIn("pub_night_lights", names)
        self.assertIn("pub_pop_agesex_grid", names)
        self.assertIn("pub_place_fsq", names)
        self.assertIn("fdi_projects", names)
        self.assertIn("access_score_grid", names)
        self.assertIn("grid_cell", names)
        self.assertIn("district", names)
        planted = [name for name in names if name != "pub_place"]
        self.assertEqual(fixture.missing_public(planted), "pub_place")
        tables = {table.name: table for table in fixture.fixture_tables()}
        keys = [row["district_key"] for row in tables["grid_cell"].rows]
        self.assertIn(None, keys)

    def test_every_name_like_value_carries_the_marker(self) -> None:
        """Every name-like value starts with INVENTED-."""
        tables = fixture.fixture_tables()
        self.assertIsNone(fixture.unmarked_name(tables))
        planted = list(tables)
        place = next(table for table in planted if table.name == "pub_place")
        row = dict(place.rows[0])
        row["name"] = "plain-name"
        replaced = TableWrite(place.name, place.columns, (row,))
        planted = [
            replaced if table.name == "pub_place" else table for table in planted
        ]
        self.assertEqual(fixture.unmarked_name(planted), "plain-name")

    def test_every_source_id_is_registered(self) -> None:
        """Every source_id is a row of the fixture's source_registry."""
        tables = fixture.fixture_tables()
        self.assertIsNone(fixture.unknown_source(tables))
        planted = list(tables)
        place = next(table for table in planted if table.name == "pub_place")
        row = dict(place.rows[0])
        row["source_id"] = "src-missing"
        replaced = TableWrite(place.name, place.columns, (row,))
        planted = [
            replaced if table.name == "pub_place" else table for table in planted
        ]
        self.assertEqual(fixture.unknown_source(planted), "src-missing")

    def test_fixture_holds_no_protected_simulated_or_privacy_written_table(
        self,
    ) -> None:
        """Protected, simulated and privacy-written tables stay out."""
        names = fixture.included_names()
        self.assertIsNone(fixture.forbidden_name(names))
        self.assertNotIn("release_unit", names)
        self.assertNotIn("graph_node", names)
        self.assertEqual(
            fixture.forbidden_name([*names, "resident_pay"]), "resident_pay"
        )
        privacy = [
            row.name
            for row in CATALOGUE
            if row.writer == "privacy"
            or row.manifest_class in {"protected", "simulated"}
        ]
        self.assertTrue(privacy)
        for name in privacy:
            self.assertNotIn(name, names)

    def test_fixture_is_seeded(self) -> None:
        """Two builds from the fixed seed share one release id."""
        with (
            tempfile.TemporaryDirectory() as first,
            tempfile.TemporaryDirectory() as second,
        ):
            left = fixture.build_fixture(Path(first))
            right = fixture.build_fixture(Path(second))
        self.assertEqual(left, right)
        self.assertEqual(len(left), 64)
