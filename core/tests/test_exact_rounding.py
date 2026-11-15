"""Lead verification: invented exact halves, rounded only at the boundary."""

from decimal import Decimal as D

import pytest

from eii_core.calc.public_series import decomposition, rounded


@pytest.mark.parametrize(
    "before,after,key,places,expected",
    [
        ([(5, "1"), (1, "0")], [(2, "1"), (1, "2")], "change", 0, "1"),
        ([(2, "5"), (2, "5")], [(5, "15"), (1, "10.5")], "within", 0, "9"),
        ([(6, "9.5"), (5, "7")], [(9, "20"), (3, "16")], "mix_share", 1, "6.3"),
    ],
)
def test_verification_exact_halves(before, after, key, places, expected):
    # Exact hand results: 4/3 - 5/6 = 1/2; within = 17/2; mix/change*100 = 25/4.
    result = decomposition(
        {str(i): (D(n), D(w)) for i, (n, w) in enumerate(before)},
        {str(i): (D(n), D(w)) for i, (n, w) in enumerate(after)},
    )
    value = (
        result["mix"] / result["change"] * 100 if key == "mix_share" else result[key]
    )
    assert rounded(value, places) == expected
    assert result["within"] + result["mix"] == result["change"]


@pytest.mark.parametrize(
    "value,places,expected",
    [("-0.4", 0, "0"), ("-0.004", 2, "0.00"), ("-0.5", 0, "-1")],
)
def test_verification_negative_zero(value, places, expected):
    assert rounded(D(value), places) == expected


def test_wilson_rational_square_endpoint():
    from fractions import Fraction

    from eii_core.calc.public_methods import wilson

    # k=0,n=1: upper = z²/(1+z²) = 2401/3026; lower=0.
    assert wilson(0, 1) == (Fraction(0), Fraction(2401, 3026))


def test_wilson_irrational_endpoint():
    from eii_core.calc.public_methods import wilson

    # k=6,n=28 gives endpoints 0.102123... and 0.395389... .
    assert tuple(rounded(x, 3) for x in wilson(6, 28)) == ("0.102", "0.395")


def test_irrational_rounding_boundary_refuses():
    from eii_core.calc.public_series import Approximate

    with pytest.raises(ValueError, match="undecidable rounding boundary"):
        rounded(Approximate("0.50000000000000000000000000000000000000001"), 0)


def test_three_groups_nonterminating_and_zero_count():
    from fractions import Fraction as F

    # Means 1000/6 and 1870/7; within=-1577/21, mix=1229/7, change=2110/21.
    before = {"a": (D(2), D(100)), "b": (D(4), D(200)), "c": (D(0), D(999))}
    after = {"a": (D(1), D(110)), "b": (D(4), D(190)), "c": (D(2), D(500))}
    result = decomposition(before, after)
    assert result["within"] == F(-1577, 21)
    assert result["mix"] == F(1229, 7)
    assert result["change"] == F(2110, 21)
    assert result["within"] + result["mix"] == result["change"]


def test_method_exact_halves():
    from method_rows import energy, measure, trade

    from eii_core.calc import public_methods as p

    # 10000/32=312.5; 100/16=6.25; (1)/(8/25)=3.125.
    assert p.licence_density(measure(1), measure(32)).value == D(313)
    assert p.coverage_share(measure(1), measure(16))["percent"].value == D("6.3")
    result = p.location_quotient(
        measure(10),
        measure(10),
        measure(8, geography="national", kind="national"),
        measure(25, geography="national", kind="national"),
    )
    assert result["value"].value == D("3.13")
    moved = p.zone_momentum(
        [energy("invented", 2021, 1), energy("invented", 2025, 1)],
        energy("national", 2021, 25),
        energy("national", 2025, 8),
    )
    assert moved["zones"]["invented"]["relative"].value == D("3.13")
    months = tuple(f"2025-{m:02}" for m in range(1, 13))
    # Shares 1/16 and 15/16; HHI=10000*226/256=8828.125 -> 8828.13.
    supplied = p.supplier_metrics(
        [
            trade("invented", "a", months[0], 1, 8),
            trade("invented", "b", months[0], 15, 1),
        ],
        ["invented"],
        months,
        months,
        reviewed=True,
    )
    assert supplied["hhi"].value == D("8828.13")
    assert supplied["origins"]["a"]["share_percent"].value == D("6.3")
    assert supplied["origins"]["a"]["unit_value"].value == D("0.13")


def test_sector_exact_half():
    from method_rows import measure

    from eii_core.calc.sector_economics import Component, sector_norms

    # .00375*1000/3/100*100=1.25; (1/3)*37.65=12.55.
    result = sector_norms(
        employees=measure(3),
        productivity=measure(100, "qar"),
        compensation_thousand=measure(".00375", "qar_thousand"),
        surplus_thousand=measure(".00375", "qar_thousand"),
        goods_percent=measure("37.65", "percent"),
        services_percent=measure(0, "percent"),
        components=[
            Component(
                "food",
                "goods",
                measure(1, "qar_thousand"),
                measure(3, "qar_thousand"),
                "goods",
            )
        ],
    )
    assert result["compensation_percent"].value == D("1.3")
    assert result["surplus_percent"].value == D("1.3")
    assert result["food"].value == D("12.6")


def test_comparison_exact_half_and_uncertainty():
    from fractions import Fraction as F

    from method_rows import measure

    from eii_core.calc.facts import compare_public_facts, emit
    from eii_core.calc.public_series import Approximate, compare

    def fact(value, period):
        row = measure(1, period=period)
        return emit(
            value,
            unit="qar",
            places=0,
            metric_key="invented",
            release_id="invented",
            geography=row.geography,
            geography_kind=row.geography_kind,
            period=period,
            inputs=(row,),
        )

    # 7/6-2/3=1/2, so the difference is 1 at zero places.
    assert compare_public_facts(
        fact(F(2, 3), "2020"), fact(F(7, 6), "2021")
    ).difference.value == D(1)
    with pytest.raises(ValueError, match="undecidable comparison boundary"):
        compare(Approximate("1.00000000000000000000000000000000000000001"), F(1))


def test_share_range_irrational_comparison_contract():
    from eii_core.calc.public_series import Approximate
    from eii_core.calc.sector_economics import share_range

    low, high = Approximate("1.01"), Approximate("2.01")
    assert share_range([high, low]) == (low, high)
    with pytest.raises(ValueError, match="undecidable comparison boundary"):
        share_range([low, Approximate("1.01000000000000000000000000000000000000001")])
