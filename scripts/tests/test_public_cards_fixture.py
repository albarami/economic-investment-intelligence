"""The cards variant is invented and leaves earlier variants unchanged."""

import tempfile
import unittest
from pathlib import Path

from public_release_fixture import (
    _cards_tables,
    _playbook_tables,
    build_fixture,
    fixture_tables,
    unknown_source,
    unmarked_name,
)

from eii_core.grid import cell_centre
from eii_product.store.release_check import check_release


class CardsFixtureTests(unittest.TestCase):
    def test_rows_and_preserved_variants(self) -> None:
        before = (fixture_tables(), _playbook_tables())
        tables = _cards_tables()
        by_name = {table.name: table for table in tables}
        self.assertIsNone(unmarked_name(tables))
        self.assertIsNone(unknown_source(tables))
        grid = by_name["grid_cell"].rows
        self.assertEqual(len(grid), 4)
        self.assertTrue(all(row["resolution"] == 9 for row in grid))
        self.assertTrue(
            all(
                isinstance(row["cell"], int) and 0 < cell_centre(row["cell"])[0] < 3
                for row in grid
            )
        )
        self.assertEqual(len(by_name["pub_venue_busyness"].rows), 167)
        self.assertEqual(len(by_name["pub_pop_agesex_grid"].rows), 16)
        self.assertEqual(len(by_name["pub_land_price"].rows), 12)
        self.assertEqual(len(by_name["zone"].rows), 8)
        self.assertEqual(
            by_name["pub_rail_plan"].rows[0]["feature_kind"], "planned_station"
        )
        self.assertEqual(by_name["pub_health_centre"].rows[0]["feature_kind"], "centre")
        self.assertEqual(
            by_name["pub_property_quarter"].rows[0]["district_key"],
            "INVENTED-district-a",
        )
        self.assertEqual(before, (fixture_tables(), _playbook_tables()))

    def test_build_checked_cards_release(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            folder = Path(raw) / "release"
            identity = build_fixture(folder, cards=True)
            self.assertEqual(check_release(folder).document["release_id"], identity)
