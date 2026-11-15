"""Literal method checks supporting the rational-context equivalence proofs."""

from decimal import Decimal, Inexact, Rounded, localcontext
from fractions import Fraction

from method_rows import energy, measure, trade

from eii_core.calc import public_methods as m
from eii_core.calc import public_series as s


def test_rational_methods_and_irrational_intervals_ignore_hostile_context():
    """10000/32=312.5, 100/16=6.25 and (10/10)/(8/25)=3.125 round half-up."""
    with localcontext(prec=1) as context:
        context.traps[Inexact] = True
        context.traps[Rounded] = True
        assert m.licence_density(measure(1), measure(32)).value == Decimal(313)
        coverage = m.coverage_share(measure(1), measure(16))
        assert coverage["percent"].value == Decimal("6.3")
        lq = m.location_quotient(
            measure(10),
            measure(10),
            measure(8, geography="national", kind="national"),
            measure(25, geography="national", kind="national"),
        )
        assert lq["value"].value == Decimal("3.13")
        # Wilson k=6,n=28: centre=9901/39802;
        # half=sqrt(695149)/5686; endpoints round to .102 and .395.
        interval = m.coverage_share(measure(6), measure(28))["interval"]
        assert tuple(fact.value for fact in interval) == (
            Decimal(".102"),
            Decimal(".395"),
        )


def test_supplier_fraction_sums_and_empty_prior_denominator():
    """Shares 1/4 and 3/4 give HHI 6250; an empty prior is no denominator."""
    months = tuple(f"2025-{i:02}" for i in range(1, 13))
    prior = tuple(f"2024-{i:02}" for i in range(1, 13))
    with localcontext(prec=1):
        result = m.supplier_metrics(
            [
                trade("invented", "a", months[0], 1, 8),
                trade("invented", "b", months[0], 3, 1),
            ],
            ["invented"],
            months,
            prior + months,
            reviewed=True,
            prior_rows=[],
            prior_months=prior,
        )
    assert result["total_value_unrounded"] == Fraction(4)
    assert type(result["total_value_unrounded"]) is Fraction
    assert result["hhi"].value == Decimal("6250.00")
    assert result["origins"]["a"]["share_percent"].value == Decimal("25.0")
    assert result["origins"]["a"]["unit_value"].value == Decimal("0.13")
    assert result["trend"] == m.NoData("no_denominator")
    assert m.supplier_metrics(
        [], ["invented"], months, months, reviewed=True
    ) == m.NoData("no_denominator")


def test_churn_and_momentum_remain_exact_under_one_digit_context():
    """Churn 1/16=6.25%; zone/national=(1)/(8/25)=3.125."""
    with localcontext(prec=1):
        churn = m.licence_churn(
            measure(16),
            {"2020-01": measure(1, period="2020-01")},
            {},
            s.C2_CALENDAR,
            measure(1, geography="national", kind="national"),
            measure(1, geography="national", kind="national"),
        )
        momentum = m.zone_momentum(
            [energy("invented", 2021, 1), energy("invented", 2025, 1)],
            energy("national", 2021, 25),
            energy("national", 2025, 8),
        )
    assert churn["including_percent"].value == Decimal("6.3")
    assert churn["excluding_percent"].value == Decimal("6.3")
    assert momentum["zones"]["invented"]["relative"].value == Decimal("3.13")
