"""Invented method fixtures with literal values and closed metadata."""

from dataclasses import replace
from decimal import Decimal as D
from fractions import Fraction

import pytest
from method_rows import energy, measure, trade
from test_public_methods import calendar

from eii_core.calc import public_methods as p
from eii_core.calc.facts import NoData


def national(value, period="2025-05"):
    return measure(value, period=period, geography="national", kind="national")


def churn(**changes):
    args = dict(
        active_row=measure(10),
        cancellations={"2025-01": measure(10, period="2025-01")},
        national_totals={},
        calendar=calendar(),
        all_cancellations_row=national(12),
        dated_cancellations_row=national(10),
    )
    args.update(changes)
    return p.licence_churn(**args)


@pytest.mark.parametrize(
    "changes,reason",
    [
        ({"calendar": ()}, "complete declared calendar required"),
        (
            {
                "all_cancellations_row": measure(12),
                "dated_cancellations_row": measure(10),
            },
            "geography mismatch",
        ),
        ({"all_cancellations_row": national(9)}, "dated count exceeds total"),
        (
            {"cancellations": {"2025-01": measure(1, period="2025-02")}},
            "period mismatch",
        ),
        ({"national_totals": {"2025-01": national(1, "2025-02")}}, "period mismatch"),
        (
            {"cancellations": {"2014-12": measure(1, period="2014-12")}},
            "month outside calendar",
        ),
        (
            {"national_totals": {"2025-01": national(11, "2025-01")}},
            "bulk count exceeds dated count",
        ),
    ],
)
def test_churn_exact_refusals(changes, reason):
    with pytest.raises(ValueError) as error:
        churn(**changes)
    assert str(error.value) == reason


def test_churn_output_metadata_and_flow_above_stock():
    result = churn()
    for key, value, metric in (
        ("active_count", "10", "active_count"),
        ("including_ratio", "1.00", "including_ratio"),
        ("including_percent", "100.0", "including_percent"),
        ("excluding_percent", "100.0", "excluding_percent"),
        ("undated_count", "2", "undated_count"),
        ("bulk_share_percent", "0.0", "bulk_share"),
    ):
        assert str(result[key].value) == value
        assert result[key].metric_key == metric
    for key in ("including_interval", "excluding_interval"):
        assert tuple(str(x.value) for x in result[key]) == ("0.722", "1.000")
        assert tuple(x.metric_key for x in result[key]) == ("churn_low", "churn_high")
    above = churn(cancellations={"2025-01": measure(11, period="2025-01")})
    assert above["excluding_interval"] == NoData("not_coverable")
    assert above["excluding_interval_unrounded"] is None


def test_coverage_equal_counts_and_metadata():
    result = p.coverage_share(measure(10), measure(10))
    assert str(result["percent"].value) == "100.0"
    assert result["percent"].metric_key == "coverage_percent"
    assert tuple(x.metric_key for x in result["interval"]) == (
        "coverage_low",
        "coverage_high",
    )
    with pytest.raises(ValueError) as error:
        p.coverage_share(measure(11), measure(10))
    assert str(error.value) == "private employed exceeds employed"


MONTHS = tuple(f"2025-{i:02}" for i in range(1, 13))
PRIOR = tuple(f"2024-{i:02}" for i in range(1, 13))


@pytest.mark.parametrize(
    "months,reason",
    [
        (MONTHS[:-1], "twelve complete months required"),
        ((*MONTHS[:-1], MONTHS[0]), "twelve complete months required"),
        (("2025-1", *MONTHS[1:]), "invalid month"),
        (("025-01", *MONTHS[1:]), "invalid month"),
        (("2025-01-x", *MONTHS[1:]), "invalid month"),
        (("2025-xx", *MONTHS[1:]), "invalid month"),
        (("2025-13", *MONTHS[1:]), "invalid month"),
        ((*MONTHS[:-1], "2026-01"), "consecutive months required"),
    ],
)
def test_month_refusals(months, reason):
    with pytest.raises(ValueError) as error:
        p._months(months)
    assert str(error.value) == reason


def test_months_can_cross_year_boundary():
    p._months((*PRIOR[6:], *MONTHS[:6]))


@pytest.mark.parametrize(
    "field,changes,reason",
    [
        ("value_row", {"period": "2025-02"}, "period mismatch"),
        ("weight_row", {"period": "2025-02"}, "period mismatch"),
        ("value_row", {"unit": "count"}, "unit mismatch"),
        ("weight_row", {"unit": "count"}, "unit mismatch"),
        ("value_row", {"value": D(2)}, "row value does not match its measure"),
        (
            "weight_row",
            {"geography": "zone:invented", "geography_kind": "public"},
            "geography mismatch",
        ),
    ],
)
def test_trade_row_exact_refusals(field, changes, reason):
    row = trade("invented", "invented", MONTHS[0], 1, 1)
    row = replace(row, **{field: replace(getattr(row, field), **changes)})
    with pytest.raises(ValueError) as error:
        p._trade(row)
    assert str(error.value) == reason


def supplied(**changes):
    args = dict(
        rows=[trade("invented", "invented", MONTHS[-1], 2, 1)],
        products=("invented",),
        months=MONTHS,
        complete_months=(*PRIOR, *MONTHS),
        reviewed=True,
    )
    args.update(changes)
    return p.supplier_metrics(**args)


@pytest.mark.parametrize(
    "changes,reason",
    [
        ({"reviewed": False}, "reviewed basket required"),
        ({"complete_months": MONTHS[:-1]}, "incomplete window"),
        (
            {"rows": [trade("invented_other", "invented", MONTHS[0], 1, 1)]},
            "row outside selected basket/window",
        ),
        (
            {"rows": [trade("invented", "invented", MONTHS[0], -1, 1)]},
            "negative import value",
        ),
        (
            {"prior_rows": [], "prior_months": PRIOR, "complete_months": MONTHS},
            "incomplete or overlapping prior window",
        ),
        (
            {"prior_rows": [], "prior_months": (*PRIOR[1:], MONTHS[0])},
            "incomplete or overlapping prior window",
        ),
        (
            {
                "prior_rows": [],
                "prior_months": tuple(f"2023-{i:02}" for i in range(1, 13)),
                "complete_months": (
                    *tuple(f"2023-{i:02}" for i in range(1, 13)),
                    *MONTHS,
                ),
            },
            "prior window must be adjacent",
        ),
        (
            {
                "prior_rows": [trade("invented_other", "invented", PRIOR[0], 1, 1)],
                "prior_months": PRIOR,
            },
            "prior row outside selected basket/window",
        ),
        (
            {
                "prior_rows": [trade("invented", "invented", PRIOR[0], -1, 1)],
                "prior_months": PRIOR,
            },
            "negative import value",
        ),
    ],
)
def test_supplier_exact_refusals(changes, reason):
    with pytest.raises(ValueError) as error:
        supplied(**changes)
    assert str(error.value) == reason


def test_supplier_requires_one_geography_across_rows():
    row = trade("invented", "invented_other", MONTHS[0], 1, 1)
    other = replace(
        row,
        value_row=replace(
            row.value_row, geography="zone:invented", geography_kind="public"
        ),
        weight_row=replace(
            row.weight_row, geography="zone:invented", geography_kind="public"
        ),
    )
    with pytest.raises(ValueError) as error:
        supplied(rows=[trade("invented", "invented", MONTHS[0], 1, 1), other])
    assert str(error.value) == "geography mismatch"


def test_supplier_metadata_zero_values_and_missing_weight():
    result = supplied(
        rows=[
            trade("invented", "invented", MONTHS[-1], 2, 1),
            trade("invented", "invented_empty", MONTHS[0], 0, 0),
        ]
    )
    for key, value in (
        ("total_value", "2.00"),
        ("origin_count", "2"),
        ("hhi", "10000.00"),
    ):
        assert str(result[key].value) == value
        assert result[key].metric_key == key
    assert result["trend_unrounded"] is None
    origin = result["origins"]["invented"]
    for key, value, metric in (
        ("share_percent", "100.0", "share"),
        ("unit_value", "2.00", "unit_value"),
        ("other_units", "0", "other_units"),
        ("nonpositive_kg", "0", "nonpositive_kg"),
    ):
        assert str(origin[key].value) == value
        assert origin[key].metric_key == metric
    assert result["origins"]["invented_empty"]["unit_value"] == NoData("no_denominator")
    trend = supplied(
        prior_rows=[trade("invented", "invented", PRIOR[0], 1, 1)], prior_months=PRIOR
    )["trend"]
    assert str(trend.value) == "1.0000"
    assert trend.metric_key == "trend"
    assert trend.period == "2025-01..2025-12"
    assert trend.base_period == "2024-01..2024-12"


def momentum(**changes):
    args = dict(
        rows=[energy("invented", 2021, 1), energy("invented", 2025, 2)],
        national_before=energy("national", 2021, 1),
        national_after=energy("national", 2025, 1),
    )
    args.update(changes)
    return p.zone_momentum(**args)


@pytest.mark.parametrize(
    "changes,reason",
    [
        ({"minimum_baseline": D(1)}, "card baseline is 1,000,000 kWh"),
        (
            {"national_after": energy("national", 2021, 1)},
            "incompatible national series",
        ),
        (
            {"national_before": energy("national", 2020, 1)},
            "card years are 2021 and 2025",
        ),
        (
            {"rows": [replace(energy("invented", 2021, 1), value=D(2))]},
            "period mismatch",
        ),
        (
            {
                "rows": [
                    replace(
                        energy("invented", 2021, 1),
                        reading=measure(1, unit="count", period="2021"),
                    )
                ]
            },
            "unit mismatch",
        ),
        (
            {"rows": [energy("invented", 2021, 1, False)]},
            "partial year or negative energy",
        ),
        (
            {"rows": [energy("invented", 2021, 1), energy("invented", 2021, 1)]},
            "duplicate or wrong year",
        ),
        ({"rows": [energy("invented", 2021, 1)]}, "incomplete annual pair"),
        (
            {"national_after": energy("national", 2025, 0)},
            "non-positive national ratio",
        ),
    ],
)
def test_momentum_exact_refusals(changes, reason):
    with pytest.raises(ValueError) as error:
        momentum(**changes)
    assert str(error.value) == reason


def test_momentum_one_unit_base_and_metadata():
    result = momentum()
    assert str(result["national_ratio"].value) == "1.00"
    assert result["national_ratio"].metric_key == "national_ratio"
    for key, metric, expected in (
        ("ratio", "zone_ratio", "2.00"),
        ("ranked_ratio", "ranked_ratio", "2.0"),
        ("relative", "relative", "2.00"),
    ):
        fact = result["zones"]["invented"][key]
        assert str(fact.value) == expected
        assert fact.metric_key == metric
        assert fact.period == "2025"
        assert fact.base_period == "2021"
    assert p._zone_tie("2") == (0, 2)
    assert p._zone_tie("invented") == (1, "invented")


def test_wilson_upper_bound_with_all_twelve_successes():
    assert p.wilson(12, 12)[1] == D(1)


def test_method_fraction_precision_ignores_caller_and_default_context(monkeypatch):
    from decimal import ROUND_UP, DefaultContext, localcontext

    monkeypatch.setattr(DefaultContext, "rounding", ROUND_UP)
    with localcontext() as context:
        context.prec = 6
        covered = p.coverage_share(measure(1), measure(3))
        changed = churn(
            active_row=measure(3),
            cancellations={"2025-01": measure(1, period="2025-01")},
            national_totals={"2025-01": national(1, "2025-01")},
            all_cancellations_row=national(3),
            dated_cancellations_row=national(3),
        )
        supplied_result = supplied(
            rows=[
                trade("invented", "invented_a", MONTHS[0], 1, 1),
                trade("invented", "invented_b", MONTHS[-1], 2, 1),
            ]
        )
        moved = momentum(national_after=energy("national", 2025, 3))
    assert str(covered["percent"].exact_unrounded) == str(Fraction(100, 3))
    assert str(changed["bulk_share_percent"].exact_unrounded) == str(Fraction(100, 3))
    assert str(
        supplied_result["origins"]["invented_a"]["share_percent"].exact_unrounded
    ) == str(Fraction(100, 3))
    assert str(moved["zones"]["invented"]["relative"].exact_unrounded) == str(
        Fraction(2, 3)
    )


def test_location_interval_unrounded_is_scaled_by_national_share():
    from eii_core.calc.public_series import rounded

    result = p.location_quotient(
        measure(10), measure(100), national(10), national(1000)
    )
    assert tuple(rounded(x, 2) for x in result["interval_unrounded"]) == (
        "5.52",
        "17.44",
    )


def test_show_accepts_single_input_anchor():
    fact = p._show(
        D(1), places=0, unit="count", metric_key="invented", inputs=(national(1),)
    )
    assert fact.value == D(1)
    assert fact.geography == "national"
    assert fact.period == "2025-05"


@pytest.mark.parametrize(
    "call",
    [
        lambda: p.licence_density(measure(1, unit="qar"), measure(1, period="2024")),
        lambda: p.location_quotient(
            measure(10, unit="qar"),
            measure(20, period="2024"),
            national(10),
            national(20),
        ),
        lambda: p.location_quotient(
            measure(10),
            measure(20),
            national(10),
            replace(national(20), unit="qar", period="2024"),
        ),
        lambda: churn(active_row=replace(national(10), unit="qar")),
        lambda: churn(all_cancellations_row=measure(12, unit="qar")),
        lambda: p.coverage_share(measure(1, unit="qar"), measure(2, period="2024")),
    ],
    ids=("density", "local", "national", "churn_local", "churn_national", "coverage"),
)
def test_count_unit_refusal_precedes_other_alignment_errors(call):
    with pytest.raises(ValueError) as error:
        call()
    assert str(error.value) == "unit mismatch"


def test_wilson_one_trial_closed_form_endpoints(monkeypatch):
    from decimal import ROUND_UP, DefaultContext

    monkeypatch.setattr(DefaultContext, "rounding", ROUND_UP)
    # At one trial, the nontrivial endpoints reduce to 625/3026 and 2401/3026.
    # These rational-square cases retain the exact endpoints.
    assert p.wilson(1, 1)[0] == Fraction(625, 3026)
    assert p.wilson(0, 1)[1] == Fraction(2401, 3026)


def test_density_large_count_intermediate_rounding():
    from decimal import localcontext

    with localcontext() as context:
        context.prec = 6
        assert p.licence_density(measure(1234567), measure(1)).value == D("1234567E4")
        # (3e50 + 5)*10000/(2e50) = 15000 + 1/(4e45), exactly.
        result = p.licence_density(measure("3" + "0" * 49 + "5"), measure("2E50"))
    assert str(result.exact_unrounded) == str(Fraction(15000) + Fraction(1, 4 * 10**45))


def test_location_and_relative_fraction_working_precision(monkeypatch):
    from decimal import ROUND_UP, DefaultContext, localcontext

    monkeypatch.setattr(DefaultContext, "rounding", ROUND_UP)
    with localcontext() as context:
        context.prec = 6
        quotient = p.location_quotient(
            measure(10), measure(10), national(3), national(10)
        )
        moved = momentum(
            rows=[energy("invented", 2021, 1), energy("invented", 2025, 1)],
            national_after=energy("national", 2025, 3),
        )
    assert str(quotient["value"].exact_unrounded) == str(Fraction(10, 3))
    assert str(moved["zones"]["invented"]["relative"].exact_unrounded) == str(
        Fraction(1, 3)
    )
