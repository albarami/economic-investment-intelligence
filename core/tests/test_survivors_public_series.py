"""Exact-fraction mutation regressions; every input is invented."""

from decimal import Decimal, localcontext
from fractions import Fraction

import pytest

from eii_core.calc import public_series as s


def test_decimal_conversion_uses_fifty_digits():
    """One eighth is exactly .125 even under a one-digit caller context."""
    with localcontext(prec=1):
        assert s.decimal_value(Fraction(1, 8)) == Decimal("0.125")


@pytest.mark.parametrize("reverse", [False, True])
def test_mixed_subtraction_keeps_approximation_and_exact_difference(reverse):
    """1.125 - .25 = .875; reversing gives -.875, without caller rounding."""
    left, right = s.Approximate("1.125"), Fraction(1, 4)
    if reverse:
        left, right = right, left
    with localcontext(prec=1):
        result = s.subtract(left, right)
    assert type(result) is s.Approximate
    assert result == Decimal("-0.875" if reverse else "0.875")


def test_approximate_division_ignores_caller_precision():
    """1 / 8 = .125 even when the caller allows only one digit."""
    with localcontext(prec=1):
        result = s.divide(s.Approximate("1"), Fraction(8))
    assert type(result) is s.Approximate
    assert result == Decimal("0.125")


@pytest.mark.parametrize("reverse", [False, True])
def test_comparison_rejects_untyped_integer_operand(reverse):
    """A bare integer is outside Number; the closed refusal is literal."""
    left, right = 1, Decimal(2)
    if reverse:
        left, right = right, left
    with pytest.raises(ValueError, match=r"^finite Decimal required$"):
        s.compare(left, right)


@pytest.mark.parametrize("distance", ["0", "1e-41", "1e-40", "-1e-40"])
@pytest.mark.parametrize("both_approximate", [False, True])
def test_comparison_refuses_distance_at_or_inside_boundary(distance, both_approximate):
    """Distances up to and including 10^-40 are undecidable."""
    right = s.Approximate("0") if both_approximate else Fraction(0)
    with pytest.raises(ValueError, match=r"^undecidable comparison boundary$"):
        s.compare(s.Approximate(distance), right)


@pytest.mark.parametrize("distance,expected", [("1.01e-40", 1), ("-1.01e-40", -1)])
def test_comparison_decides_just_outside_boundary(distance, expected):
    """A distance of 1.01 times 10^-40 exceeds the refusal band."""
    assert s.compare(s.Approximate(distance), s.Approximate("0")) == expected


def test_exact_refuses_integer_with_closed_message():
    """Exact source admission refuses the integer 1, with the specified message."""
    with pytest.raises(ValueError, match=r"^finite Decimal required$"):
        s.exact(1)


@pytest.mark.parametrize("places,half", [(0, "0.5"), (1, "0.05"), (2, "-0.005")])
def test_rounding_refuses_boundary_distance_in_original_units(places, half):
    """Half plus 10^-40 is on the closed refusal edge at every scale."""
    value = Fraction(Decimal(half)) + Fraction(1, 10**40)
    # These fractions terminate; a large local context constructs the exact input.
    with localcontext(prec=80):
        approximate = s.Approximate(
            Decimal(value.numerator) / Decimal(value.denominator)
        )
    with pytest.raises(ValueError, match=r"^undecidable rounding boundary$"):
        s.rounded(approximate, places)


def test_rounding_accepts_just_outside_original_unit_boundary():
    """At one place, .05 + 1.05e-40 is outside the band and rounds to .1."""
    value = Fraction(1, 20) + Fraction(105, 10**42)
    with localcontext(prec=80):
        approximate = s.Approximate(
            Decimal(value.numerator) / Decimal(value.denominator)
        )
    assert s.rounded(approximate, 1) == "0.1"


@pytest.mark.parametrize(
    "value,places,expected",
    [("1.25", 1, "1.3"), ("-1.25", 1, "-1.3"), ("-0.004", 2, "0.00"), ("0", 2, "0.00")],
)
def test_half_up_rounding_and_unsigned_zero(value, places, expected):
    """Exact halves round away from zero; magnitudes below half become unsigned zero."""
    assert s.rounded(Decimal(value), places) == expected


@pytest.mark.parametrize(
    "value,places,expected", [("0", 7, "0.0000000"), ("125", -1, "130")]
)
def test_rounding_always_uses_fixed_not_scientific_notation(value, places, expected):
    """Zero at seven places stays fixed; 125 at tens rounds half-up to 130."""
    assert s.rounded(Decimal(value), places) == expected
