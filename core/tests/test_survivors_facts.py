"""Comparison mutation regressions on invented facts and ratios."""

from dataclasses import replace
from decimal import localcontext
from fractions import Fraction

import pytest
from method_rows import measure

from eii_core.calc import facts as f
from eii_core.calc.public_series import Approximate


def numeric_fact(value, period="2020"):
    row = measure(1, period=period)
    return f.emit(
        value,
        unit="ratio",
        places=2,
        metric_key="invented",
        release_id="invented",
        geography=row.geography,
        geography_kind=row.geography_kind,
        period=period,
        inputs=(row,),
    )


def change(value, name="invented"):
    fact = numeric_fact(Fraction(1))
    return f.Comparison(
        metric_key=name,
        difference=fact,
        ratio=fact,
        direction=fact,
        ratio_unrounded=value,
    )


@pytest.mark.parametrize("side", ["before", "after"])
def test_comparison_refuses_one_nonnumeric_internal_value(side):
    """One malformed cached value must raise the numeric-comparison refusal."""
    before = numeric_fact(Fraction(1), "2020")
    after = numeric_fact(Fraction(2), "2021")
    # Plant corruption in the internal cache; valid displayed metadata stays intact.
    object.__setattr__(before if side == "before" else after, "exact_unrounded", "bad")
    with pytest.raises(ValueError, match=r"^numeric comparison required$"):
        f.compare_public_facts(before, after)


class FractionSubtype(Fraction):
    """A subtype must not pass the closed ratio admission."""


def test_ordering_refuses_fraction_subtype_with_closed_message():
    """Even a subtype equal to 1 must receive 'numeric ratio required'."""
    with pytest.raises(ValueError, match=r"^numeric ratio required$"):
        f.order_changes([change(FractionSubtype(1))])


def test_ordering_approximate_scores_uses_full_precision():
    """Distances .124 and .123 order b before a even with one caller digit."""
    a = change(Approximate("1.123"), "a")
    b = change(Approximate("1.124"), "b")
    with localcontext(prec=1):
        result = f.order_changes([a, b])
    assert result == (b, a)


def test_ordering_preserves_approximate_boundary_refusal():
    """Equal approximate distances are undecidable, never exact ties."""
    with pytest.raises(ValueError, match=r"^undecidable comparison boundary$"):
        f.order_changes(
            [change(Approximate("1.125"), "a"), change(Approximate(".875"), "b")]
        )


def test_ordering_puts_missing_after_numeric_in_both_input_orders():
    """A missing ratio follows a measured ratio, independent of input order."""
    numeric = change(Fraction(3, 2), "z")
    missing = replace(change(None, "a"), ratio=f.NoData("no_denominator"))
    assert f.order_changes([numeric, missing]) == (numeric, missing)
    assert f.order_changes([missing, numeric]) == (numeric, missing)


def test_ordering_equal_name_and_score_preserves_input_identity():
    """Identical name and distance keep the original order of distinct records."""
    first = change(Fraction(3, 2))
    second = replace(first, before_period="2021")
    assert f.order_changes([first, second]) == (first, second)
    assert f.order_changes([second, first]) == (second, first)


class StrictOrderName(str):
    """Comparison admits string subtypes that supply only strict ordering."""

    def __ge__(self, other):
        raise TypeError("non-strict ordering unavailable")


def test_ordering_metric_names_requires_only_strict_comparisons():
    """Equal scores order a before b using the admitted names' strict ordering."""
    a = change(Fraction(3, 2), StrictOrderName("a"))
    b = change(Fraction(3, 2), StrictOrderName("b"))
    assert f.order_changes([b, a]) == (a, b)
