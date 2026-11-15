"""Hand-computable invented fixtures for public-series arithmetic."""

import json
from decimal import Decimal as D
from pathlib import Path

import pytest
from method_rows import measure
from result_types import fact_value

from eii_core.calc.public_series import (
    bulk_months,
    decomposition,
    growth,
    ratio,
    rounded,
    unit_value,
    weighted_mean,
)

FIXTURE = Path(__file__).parent / "fixtures/methods/public_methods.json"


def test_ratio_rounds_only_at_end() -> None:
    assert rounded(ratio(D(10), D(3)), 2) == "3.33"
    assert rounded(D("1.005"), 2) == "1.01"


def cell(workers: object, wage: object, period: str):
    return (
        measure(
            workers, period=period, geography="national", kind="national", unit="count"
        ),
        measure(
            wage,
            period=period,
            geography="national",
            kind="national",
            unit="qar_per_month",
        ),
    )


def test_weighted_mean_and_kitagawa() -> None:
    before = {"invented_a": (D(3), D(10)), "invented_b": (D(1), D(30))}
    assert weighted_mean(before) == (D(4), D(15))
    result = decomposition(
        {"invented_a": cell(3, 10, "2020"), "invented_b": cell(1, 30, "2020")},
        {"invented_a": cell(1, 14, "2025"), "invented_b": cell(3, 34, "2025")},
    )
    assert fact_value(result["mean_before"]) == D(15)
    assert fact_value(result["mean_after"]) == D(29)
    assert result["change_unrounded"] == D(14)
    assert result["within_unrounded"] == D(4)
    assert result["mix_unrounded"] == D(10)
    assert result["populated_groups"].value == D(2)
    assert result["fixed_composition_change_unrounded"] == D(4)


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
        decomposition({"a": cell(1, 1, "2020")}, {"b": cell(1, 1, "2025")})


def _pay(group_rows: list[dict[str, str]], workers: str, wage: str, period: str):
    return {
        row["group"]: (
            measure(
                row[workers].replace(",", ""),
                period=period,
                geography="national",
                kind="national",
                unit="count",
            ),
            measure(
                row[wage].replace(",", ""),
                period=period,
                geography="national",
                kind="national",
                unit="qar_per_month",
            ),
        )
        for row in group_rows
    }


def test_published_occupation_decomposition_matches_the_card():
    """Card C3 printed figures, through decomposition(), from the eighteen published cells."""
    groups = json.loads(FIXTURE.read_text())["published"]["C3"]["groups"]
    result = decomposition(
        _pay(groups, "workers_before", "wage_before", "2020"),
        _pay(groups, "workers_after", "wage_after", "2025"),
    )
    assert fact_value(result["mean_before"]) == D(10084)
    assert fact_value(result["mean_after"]) == D(11855)
    assert fact_value(result["within"]) == D(38)
    assert fact_value(result["mix"]) == D(1733)
    assert fact_value(result["mix_share_percent"]) == D("97.8")
    assert fact_value(result["change_percent"]) == D("17.6")
    assert rounded(result["fixed_composition_mean_unrounded"], 0) == "10181"
    assert fact_value(result["fixed_composition_percent"]) == D("1.0")


def test_within_weight_is_the_average_share_when_wage_changes_differ():
    """s1 alone would give within 8; the average share gives 7."""
    before = {
        "invented_a": (
            measure(
                1, period="2020", geography="national", kind="national", unit="count"
            ),
            measure(
                10,
                period="2020",
                geography="national",
                kind="national",
                unit="qar_per_month",
            ),
        ),
        "invented_b": (
            measure(
                1, period="2020", geography="national", kind="national", unit="count"
            ),
            measure(
                20,
                period="2020",
                geography="national",
                kind="national",
                unit="qar_per_month",
            ),
        ),
    }
    after = {
        "invented_a": (
            measure(
                1, period="2025", geography="national", kind="national", unit="count"
            ),
            measure(
                12,
                period="2025",
                geography="national",
                kind="national",
                unit="qar_per_month",
            ),
        ),
        "invented_b": (
            measure(
                3, period="2025", geography="national", kind="national", unit="count"
            ),
            measure(
                30,
                period="2025",
                geography="national",
                kind="national",
                unit="qar_per_month",
            ),
        ),
    }
    result = decomposition(before, after)
    assert result["within_unrounded"] == D(7)
    assert result["mix_unrounded"] == D("3.5")
    assert result["change_unrounded"] == D("10.5")
    awkward_before = {
        "a": (D(7), D(10)),
        "b": (D(11), D(20)),
        "c": (D(13), D(30)),
    }
    awkward_after = {
        "a": (D(17), D(11)),
        "b": (D(3), D(40)),
        "c": (D(19), D(15)),
    }
    from eii_core.calc.public_series import _kitagawa

    split = _kitagawa(awkward_before, awkward_after)
    # Independent rational calculation of the published formula on these invented cells:
    # within = -200/93; mix = -5568/1209.
    assert rounded(split["within_unrounded"], 6) == "-2.150538"
    assert rounded(split["mix_unrounded"], 6) == "-4.605459"


def test_invented_fixture_cells_are_read():
    invented = json.loads(FIXTURE.read_text())["invented"]
    before = {
        key: cell(workers, wage, "2020")
        for key, (workers, wage) in invented["C3"]["before"].items()
    }
    after = {
        key: cell(workers, wage, "2025")
        for key, (workers, wage) in invented["C3"]["after"].items()
    }
    result = decomposition(before, after)
    assert fact_value(result["change"]) == D(14)
    assert fact_value(result["within"]) == D(4)
    assert fact_value(result["mix"]) == D(10)


def test_fractional_bulk_month_is_refused():
    with pytest.raises(ValueError):
        bulk_months({"2015-01": D("1.5")})


def test_fixed_composition_uses_baseline_counts_and_mean_wages():
    result = decomposition(
        {"invented_a": cell(3, 10, "2020"), "invented_b": cell(1, 30, "2020")},
        {"invented_a": cell(1, 14, "2025"), "invented_b": cell(3, 34, "2025")},
    )
    assert result["fixed_composition_change_unrounded"] == D(4)
    assert result["within_unrounded"] == D(4)
    assert result["mix_unrounded"] == D(10)
    assert result["change_unrounded"] == D(14)


@pytest.mark.parametrize(
    "cell", [(D("NaN"), D(1)), (D("1.5"), D(1)), (D(1), D(-1)), (D(0), D(0))]
)
def test_invalid_decomposition_cells(cell):
    with pytest.raises(ValueError):
        decomposition({"invented": cell}, {"invented": cell})
