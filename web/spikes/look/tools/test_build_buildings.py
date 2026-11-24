"""Heights for the building tiles. The tile round trip is in the Node test."""

from __future__ import annotations

import unittest

from build_buildings import (
    BASIS_FLOORS,
    BASIS_FOOTPRINT,
    BASIS_MEASURED,
    ESTIMATE_HIGH_METRES,
    ESTIMATE_LOW_METRES,
    STOREY_METRES,
    height_of,
)


class HeightTests(unittest.TestCase):
    def test_measured_height_is_kept(self) -> None:
        self.assertEqual(height_of(22.0, 4, 10.0), (22.0, BASIS_MEASURED))

    def test_floors_use_the_stated_storey(self) -> None:
        self.assertEqual(height_of(None, 4, 10.0), (4 * STOREY_METRES, BASIS_FLOORS))
        self.assertEqual(STOREY_METRES, 3.2)

    def test_footprint_estimate_varies_between_the_stated_ends(self) -> None:
        low, low_basis = height_of(None, None, 40.0)
        high, high_basis = height_of(None, None, 9000.0)
        mid, mid_basis = height_of(None, None, 2040.0)
        self.assertEqual(low, ESTIMATE_LOW_METRES)
        self.assertEqual(high, ESTIMATE_HIGH_METRES)
        self.assertEqual(low_basis, BASIS_FOOTPRINT)
        self.assertEqual(high_basis, BASIS_FOOTPRINT)
        self.assertEqual(mid_basis, BASIS_FOOTPRINT)
        self.assertGreater(mid, low)
        self.assertLess(mid, high)

    def test_a_missing_height_of_zero_is_not_measured(self) -> None:
        metres, basis = height_of(0, 2, 10.0)
        self.assertEqual(basis, BASIS_FLOORS)
        self.assertEqual(metres, 2 * STOREY_METRES)


if __name__ == "__main__":
    unittest.main()
