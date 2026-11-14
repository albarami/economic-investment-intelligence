"""L-81 R6: pin the measured grid error and evidence of turn-dependent entry.

L-84 S4 fixes the absolute bound before this run. We
also pin the crossing's turn-minus-straight entry shifts against the engine's
route-time shifts, within 0.2 seconds (largest measured discrepancy 0.151661
seconds). Identical link sums predict no shift.
No product option, geometry, speed or fixture is changed to meet either bound.
"""

import json
import unittest
from fractions import Fraction

from assignment_area_measurement import measure_all

# the method card states that, on the spike's fixtures, a node enters the
# engine's outline up to 40 seconds from its route time (measured maximum
# 34.004 s on 2026-11-13, plus a stated margin)
ROUTE_BOUND_SECONDS = Fraction(40)
# At a turn, a node's entry into the outline moves by the difference of the two
# route times within 0.2 seconds, at every approach of the crossing and at both
# of its speeds (largest measured 0.151661 seconds).
TURN_SHIFT_BOUND_SECONDS = Fraction("0.2")


class AssignmentAreaTimeTests(unittest.TestCase):
    def test_outline_entry_measurements_and_turn_shifts(self) -> None:
        rows = measure_all()
        for row in rows:
            print(json.dumps(row, sort_keys=True))
        self.assertEqual(
            {
                name: sum(row["fixture"] == name for row in rows)
                for name in ("crossing", "hourly", "worked")
            },
            {"crossing": 5 * 5 * 2, "hourly": 3 * 3 * 17, "worked": 3 * 3 * 3},
        )
        for row in rows:
            if row["route_seconds"] is None:
                self.assertEqual(row["fixture"], "worked")
                self.assertEqual(row["route_error"], "No path could be found for input")
                self.assertIsNone(row["entry_high_seconds"])
                continue
            self.assertIsNotNone(row["entry_high_seconds"], row)
            low = Fraction(row["entry_low_seconds"])
            high = Fraction(row["entry_high_seconds"])
            self.assertGreater(high, low, row)
            # Method card: entry times are bracketed within 0.01 seconds.
            self.assertLessEqual(high - low, Fraction("0.01"), row)
            for endpoint in (low, high):
                self.assertLessEqual(
                    abs(endpoint - Fraction(row["route_seconds"])),
                    ROUTE_BOUND_SECONDS,
                    row,
                )
        self.assertEqual(sum(row["route_seconds"] is None for row in rows), 3 * 3)
        for hour in (None, 8):
            for origin, straight_id, turn_ids in (
                ("W", "E", ("N", "S")),
                ("E", "W", ("S", "N")),
                ("N", "S", ("E", "W")),
                ("S", "N", ("W", "E")),
            ):
                approach = {
                    row["destination"]: row
                    for row in rows
                    if row["fixture"] == "crossing"
                    and row["hour"] == hour
                    and row["origin"] == "SYN-N-" + origin
                }
                self.assertEqual(
                    Fraction(approach["SYN-N-C"]["route_seconds"]),
                    Fraction("66.78") if hour is None else Fraction("200.34"),
                )
                straight = approach["SYN-N-" + straight_id]
                for destination in turn_ids:
                    turn = approach["SYN-N-" + destination]
                    self.assertEqual(turn["link_seconds"], straight["link_seconds"])
                    entry_shift = Fraction(turn["entry_high_seconds"]) - Fraction(
                        straight["entry_high_seconds"]
                    )
                    route_shift = Fraction(turn["route_seconds"]) - Fraction(
                        straight["route_seconds"]
                    )
                    self.assertGreater(entry_shift, TURN_SHIFT_BOUND_SECONDS)
                    self.assertLessEqual(
                        abs(entry_shift - route_shift),
                        TURN_SHIFT_BOUND_SECONDS,
                        (hour, origin, destination, str(entry_shift - route_shift)),
                    )
