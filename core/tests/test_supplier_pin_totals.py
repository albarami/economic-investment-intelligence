"""C5 pin inputs remain exact QAR amounts and dimensionless ratios."""

from dataclasses import replace
from decimal import Decimal
from fractions import Fraction

import pytest
from core.tests.method_rows import trade
from hypothesis import given
from hypothesis import strategies as st

from eii_core.calc.facts import MeasureMismatch, NoData, emit
from eii_core.calc.public_methods import supplier_metrics

PRIOR = tuple(f"2024-{month:02}" for month in range(1, 13))
LATEST = tuple(f"2025-{month:02}" for month in range(1, 13))


def metrics(prior, latest):
    return supplier_metrics(
        [trade("SYN input", "SYN origin", LATEST[0], latest, 2311000)],
        ("SYN input",),
        LATEST,
        (*PRIOR, *LATEST),
        reviewed=True,
        prior_rows=[trade("SYN input", "SYN origin", PRIOR[0], prior, 1)],
        prior_months=PRIOR,
    )


def test_c5_worked_example_and_exact_totals():
    result = metrics(10_040_000, 20_080_000)
    assert result["prior_total_value_unrounded"] == Fraction(10_040_000)
    assert result["total_value_unrounded"] == Fraction(20_080_000)
    assert result["trend_unrounded"] == Fraction(1)
    assert result["origins"]["SYN origin"]["unit_value"].value == Decimal("8.69")


@given(prior=st.integers(min_value=1), latest=st.integers(min_value=0))
def test_trend_sign_follows_latest_minus_prior(prior, latest):
    result = metrics(prior, latest)
    trend = result["trend_unrounded"]
    assert (trend > 0) == (latest > prior)
    assert (trend < 0) == (latest < prior)
    assert (trend == 0) == (latest == prior)
    assert result["prior_total_value_unrounded"] == prior
    assert result["total_value_unrounded"] == latest


def test_zero_prior_is_returned_with_no_trend_denominator():
    result = metrics(0, 1)
    assert result["prior_total_value_unrounded"] == 0
    assert result["trend"] == NoData("no_denominator")


def test_zero_latest_still_returns_totals_and_negative_trend():
    result = metrics(7, 0)
    assert result["prior_total_value_unrounded"] == 7
    assert result["total_value_unrounded"] == 0
    assert result["trend_unrounded"] == -1
    assert result["hhi"] == NoData("no_denominator")


def test_trend_declares_both_receipt_backed_windows():
    result = metrics(7, 14)
    assert result["trend"].period == "2025-01..2025-12"
    assert result["trend"].base_period == "2024-01..2024-12"


@pytest.mark.parametrize("side", ["latest", "prior"])
def test_trend_refuses_a_receipt_measure_period_mismatch(side):
    latest = trade("SYN input", "SYN origin", LATEST[0], 14, 1)
    prior = trade("SYN input", "SYN origin", PRIOR[0], 7, 1)
    if side == "latest":
        latest = replace(latest, value_row=replace(latest.value_row, period="2023-01"))
    else:
        prior = replace(prior, value_row=replace(prior.value_row, period="2023-01"))
    with pytest.raises(MeasureMismatch, match=r"^period mismatch$"):
        supplier_metrics(
            [latest],
            ("SYN input",),
            LATEST,
            (*PRIOR, *LATEST),
            reviewed=True,
            prior_rows=[prior],
            prior_months=PRIOR,
        )


@pytest.mark.parametrize(
    "change", [None, "latest", "prior", "reverse_latest", "reverse_prior", "outside"]
)
def test_window_comparison_emission_requires_both_input_windows(change):
    latest = trade("SYN input", "SYN origin", LATEST[0], 14, 1).value_row
    prior = trade("SYN input", "SYN origin", PRIOR[0], 7, 1).value_row
    arguments = dict(
        unit="ratio",
        places=4,
        metric_key="trend",
        release_id="SYN-release",
        geography="national",
        geography_kind="national",
        period="2025-01..2025-12",
        base_period="2024-01..2024-12",
        inputs=(prior, latest),
    )
    if change == "latest":
        arguments["period"] = "2026-01..2026-12"
    elif change == "prior":
        arguments["base_period"] = "2023-01..2023-12"
    elif change == "reverse_latest":
        arguments["period"] = "2025-12..2025-01"
    elif change == "reverse_prior":
        arguments["base_period"] = "2024-12..2024-01"
    elif change == "outside":
        arguments["inputs"] = (prior, latest, replace(latest, period="2026-01"))
    if change is not None:
        with pytest.raises(MeasureMismatch, match=r"^period mismatch$"):
            emit(Fraction(1), **arguments)
    else:
        result = emit(Fraction(1), **arguments)
        assert result.period == arguments["period"]
        assert result.base_period == arguments["base_period"]


def test_emit_refuses_a_scalar_base_period_absent_from_its_inputs():
    row = trade("SYN input", "SYN origin", LATEST[0], 14, 1).value_row
    with pytest.raises(MeasureMismatch, match=r"^period mismatch$"):
        emit(
            Fraction(1),
            unit="ratio",
            places=4,
            metric_key="trend",
            release_id="SYN-release",
            geography="national",
            geography_kind="national",
            period="2025-01..2025-12",
            base_period="2024-01",
            inputs=(row,),
        )
