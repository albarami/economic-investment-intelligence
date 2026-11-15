"""Hand-computable invented fixtures for public-series arithmetic."""

from decimal import Decimal as D

import pytest

from eii_core.calc.public_series import (
    bulk_months,
    decomposition,
    growth,
    ratio,
    rounded,
    unit_value,
    weighted_mean,
)


def test_ratio_rounds_only_at_end() -> None:
    assert rounded(ratio(D(10), D(3)), 2) == "3.33"
    assert rounded(D("1.005"), 2) == "1.01"


def test_weighted_mean_and_kitagawa() -> None:
    before = {"invented_a": (D(3), D(10)), "invented_b": (D(1), D(30))}
    after = {"invented_a": (D(1), D(14)), "invented_b": (D(3), D(34))}
    assert weighted_mean(before) == (D(4), D(15))
    assert decomposition(before, after) == {
        "mean_before": D(15),
        "mean_after": D(29),
        "change": D(14),
        "within": D(4),
        "mix": D(10),
        "groups": D(2),
    }


def test_customs_positive_kg_only_and_other_units_counted() -> None:
    assert unit_value(
        [(D(30), D(2), "kg"), (D(999), D(0), "kg"), (D(900), D(10), "litre")]
    ) == (D(15), 1, 1)
    assert unit_value([(D(30), D(0), "kg")]) == (None, 0, 1)


def test_bulk_calendar_includes_missing_months_and_strict_threshold() -> None:
    assert bulk_months({"2015-01": D(2)}) == ("2015-01",)
    months = {f"{2015 + i // 12}-{i % 12 + 1:02}": D(2) for i in range(125)}
    months["2020-07"] = D(6)
    months["2022-06"] = D(7)
    assert bulk_months(months) == ("2022-06",)


def test_growth_and_partial_year_refusal() -> None:
    assert growth(D(4), D(5)) == D(25)
    with pytest.raises(ValueError, match="partial"):
        growth(D(4), D(5), partial_year=True)


def test_invalid_denominator_and_group_set_refused() -> None:
    with pytest.raises(ValueError, match="denominator"):
        ratio(D(1), D(0))
    with pytest.raises(ValueError, match="groups"):
        decomposition({"a": (D(1), D(1))}, {"b": (D(1), D(1))})
