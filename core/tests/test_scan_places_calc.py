"""Behavioural boundaries of Public place selection; invented records only."""

from datetime import date
from decimal import Decimal

import pytest

from eii_core.calc import scan_places as calc


def test_threshold_boundary():
    assert not calc.confidence_passes(Decimal("0.699"))
    assert calc.confidence_passes(Decimal("0.7"))
    assert calc.confidence_passes(Decimal("0.701"))
    for value in (True, "0.8", float("nan"), float("inf"), -1, 2):
        with pytest.raises(ValueError):
            calc.confidence_passes(value)


def test_latest_check_date_governs():
    older = {"check_date": date(2024, 1, 1), "status": "verified_open"}
    newer = {"check_date": date(2025, 1, 1), "status": "not_found"}
    for rows in ([older, newer], [newer, older]):
        assert calc.latest_verification(rows) == newer
    assert calc.latest_verification([]) is None
    with pytest.raises(ValueError):
        calc.latest_verification([newer, dict(newer, status="verified_open")])
    with pytest.raises(ValueError):
        calc.latest_verification([dict(newer, check_date="2025-01-01")])


def test_distance_order_tie_and_limit():
    rows = [
        dict(place_id="SYN-b", distance=2),
        dict(place_id="SYN-a", distance=2),
        dict(place_id="SYN-c", distance=1),
    ]
    for supplied in (rows, list(reversed(rows))):
        assert [r["place_id"] for r in calc.order_places(supplied, 50)] == [
            "SYN-c",
            "SYN-a",
            "SYN-b",
        ]
        assert calc.order_places(supplied, 1) == [rows[2]]
    for limit in (0, 51, True, "1", 1.5):
        with pytest.raises(ValueError):
            calc.order_places(rows, limit)
    for distance in (True, "2", -1, float("nan"), float("inf")):
        with pytest.raises(ValueError):
            calc.order_places([dict(place_id="SYN-a", distance=distance)], 1)


def test_route_conversion():
    assert calc.route_metres(Decimal("1.2345"), "kilometers") == Decimal("1234.5")
    assert calc.route_metres(None, "kilometers") is None
    for value, unit in [
        (True, "kilometers"),
        (-1, "kilometers"),
        (1, "miles"),
        (float("nan"), "kilometers"),
    ]:
        with pytest.raises(ValueError):
            calc.route_metres(value, unit)


@pytest.mark.parametrize("identifier", [None, True, 7, ""])
def test_identifier_is_required(identifier):
    with pytest.raises(ValueError, match="identifier_invalid"):
        calc.order_places([dict(place_id=identifier, distance=1)], 1)


@pytest.mark.parametrize(
    "value,expected", [("0.000", "0"), ("12.3400", "12.34"), ("1200", "1.2E+3")]
)
def test_canonical_number_is_exact(value, expected):
    assert str(calc.canonical_number(Decimal(value))) == expected


@pytest.mark.parametrize("value", ["1", True, Decimal("NaN"), Decimal("Infinity"), -1])
def test_number_guard_plants(value):
    with pytest.raises(ValueError, match="number_invalid"):
        calc.number(value)


@pytest.mark.parametrize("limit", [0, 51, True, "1", 1.5])
def test_limit_guard_plants(limit):
    with pytest.raises(ValueError, match="limit_invalid"):
        calc.validate_limit(limit)


def test_upper_confidence_guard_plant():
    with pytest.raises(ValueError, match="confidence_invalid"):
        calc.confidence_passes(Decimal("1.01"))


def test_latest_empty_plant():
    try:
        result = calc.latest_verification([])
    except IndexError:
        pytest.fail("empty verification must return no governing row")
    assert result is None


def test_latest_type_plant():
    with pytest.raises(ValueError, match="check_date_invalid"):
        calc.latest_verification([{"check_date": "2025-01-01"}])


def test_latest_ambiguity_plant():
    with pytest.raises(ValueError, match="verification_ambiguous"):
        calc.latest_verification([{"check_date": date(2025, 1, 1)}] * 2)


def test_distance_precedes_name_plant():
    rows = [dict(place_id="SYN-a", distance=2), dict(place_id="SYN-z", distance=1)]
    assert calc.order_places(rows, 1) == [rows[1]]


def test_route_null_plant():
    try:
        result = calc.route_metres(None, "kilometers")
    except ValueError:
        pytest.fail("unreachable route must return no distance")
    assert result is None


def test_route_unit_plant():
    with pytest.raises(ValueError, match="route_unit_invalid"):
        calc.route_metres(1, "miles")
