"""Exact C25 worked example; all inputs are invented."""

from fractions import Fraction
from pathlib import Path

from eii_custodian.assignment_spike.run import calculate

FIXTURES = Path(__file__).parent / "fixtures" / "assignment_spike"


def test_worked_example() -> None:
    result = calculate(
        FIXTURES / "worked_flows.json",
        FIXTURES / "worked_roads.json",
        FIXTURES / "worked_parameters.json",
    )
    direct = result.calculations[0]
    assert direct.volume == Fraction("500")
    assert direct.minutes == Fraction("12.5")
    assert direct.speed_kph == Fraction("48")
    assert direct.speed_ratio == "0.800"
    assert direct.volume_band == "vb2"
    assert len(result.calculations) == 2  # Zero-volume links have no row.
    assert result.shortest_minutes("SYN-N-0-0", "SYN-N-0-2", "weekday", 8, False) == (
        Fraction("12"),
        ("SYN-N-0-0", "SYN-N-1-1", "SYN-N-0-2"),
    )


def test_recorded_worked_floor_hour() -> None:
    result = calculate(
        FIXTURES / "worked_flows.json",
        FIXTURES / "worked_roads.json",
        FIXTURES / "worked_parameters.json",
    )
    direct = next(row for row in result.calculations if row.hour == 9)
    assert (direct.volume, direct.speed_kph, direct.minutes) == (
        Fraction(3000),
        Fraction(10),
        Fraction(60),
    )
    assert (direct.speed_ratio, direct.volume_band) == ("0.167", "vb3")
    assert result.shortest_minutes("SYN-N-0-0", "SYN-N-0-2", "weekday", 9, False) == (
        Fraction(12),
        ("SYN-N-0-0", "SYN-N-1-1", "SYN-N-0-2"),
    )
