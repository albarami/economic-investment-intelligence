"""Invented, hand-worked regressions for the S2-T03 surviving mutations."""

from decimal import Decimal as D

import pytest

from eii_core.calc.public_series import (
    bulk_months,
    decomposition,
    growth,
    ratio,
    unit_value,
)


def test_ratio_preserves_exact_denominator_refusal() -> None:
    """A zero divisor raises the literal non-positive-denominator diagnostic."""
    with pytest.raises(ValueError, match=r"^non-positive denominator$"):
        ratio(D(1), D(0))


def test_growth_preserves_exact_partial_year_refusal() -> None:
    """A partial year raises the literal comparison-refusal diagnostic."""
    with pytest.raises(ValueError, match=r"^partial year cannot be compared$"):
        growth(D(4), D(5), partial_year=True)


def test_decomposition_preserves_exact_group_refusal() -> None:
    """Unequal group keys raise the literal different-groups diagnostic."""
    with pytest.raises(ValueError, match=r"^different groups$"):
        decomposition({"invented_a": (D(1), D(2))}, {"invented_b": (D(1), D(2))})


def test_unit_value_counts_every_other_unit_row() -> None:
    """Two non-kg rows give other=2, missing=0 and no usable unit value."""
    assert unit_value([(D(8), D(2), "litre"), (D(9), D(3), "piece")]) == (
        None,
        2,
        0,
    )


def test_unit_value_counts_every_nonpositive_kg_row() -> None:
    """Zero and negative kg give missing=2, other=0 and no usable unit value."""
    assert unit_value([(D(8), D(0), "kg"), (D(9), D(-1), "kg")]) == (None, 0, 2)


def test_unit_value_sums_values_across_usable_rows() -> None:
    """Both values contribute: (10 + 20) / (2 + 3) = 6 QAR/kg."""
    assert unit_value([(D(10), D(2), "kg"), (D(20), D(3), "kg")]) == (D(6), 0, 0)


def test_unit_value_sums_weights_across_usable_rows() -> None:
    """Both weights contribute: (12 + 28) / (1 + 7) = 5 QAR/kg."""
    assert unit_value([(D(12), D(1), "kg"), (D(28), D(7), "kg")]) == (D(5), 0, 0)


def test_bulk_months_includes_december_and_final_may() -> None:
    """With 123 zero months the median is 0; December and final May exceed it."""
    assert bulk_months({"2015-12": D(1), "2025-05": D(1)}) == (
        "2015-12",
        "2025-05",
    )


def test_bulk_months_excludes_june_after_calendar_end() -> None:
    """June 2025 lies outside C2's January 2015 through May 2025 calendar."""
    with pytest.raises(ValueError, match=r"^invalid cancellation month/count$"):
        bulk_months({"2025-06": D(1)})
