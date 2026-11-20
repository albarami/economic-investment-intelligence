"""Card arithmetic and invented guard fixtures; not real-file regressions."""

import json
from decimal import Decimal as D
from fractions import Fraction
from pathlib import Path

import pytest
from method_rows import chain, energy, measure, trade
from result_types import fact_value

from eii_core.calc.facts import Measure, MeasureMismatch, NoData
from eii_core.calc.public_methods import (
    coverage_share,
    licence_churn,
    licence_density,
    location_quotient,
    reliability,
    supplier_metrics,
    wilson,
    zone_momentum,
)
from eii_core.calc.public_series import rounded

FIXTURE = Path(__file__).parent / "fixtures/methods/public_methods.json"


def test_methods_fixture_has_no_census_counts():
    fixture = json.loads(FIXTURE.read_text())
    assert "C8" not in fixture["published"], "census counts and shares stay local"
    for row in fixture["published"].values():
        assert "pub_census_national" not in row["sources"]


def test_methods_fixture_sources_have_attribution():
    fixture = json.loads(FIXTURE.read_text())
    for name, source in fixture["sources"].items():
        assert {"publisher", "dataset", "url", "licence"} <= source.keys(), name


def counted(value: int, **kwargs: str) -> Measure:
    return measure(value, **kwargs)


def test_c8_invented_national_coverage():
    # INVENTED: restricted census inputs and expected shares stay in the cache.
    row = json.loads(FIXTURE.read_text())["invented"]["C8"]
    source = chain()
    result = coverage_share(
        measure(
            row["private"],
            period="2020",
            geography="national",
            kind="national",
            source=source,
        ),
        measure(
            row["employed"],
            period="2020",
            geography="national",
            kind="national",
            source=source,
        ),
    )
    percent = result["percent"]
    assert percent.value == D(row["percent"]) == D("75.0")
    assert percent.exact_unrounded == Fraction(75)
    assert percent.sources == (source,)
    assert percent.geography == "national"


def test_c1_printed_densities_and_lq():
    assert licence_density(
        measure(361, metric="licences"), measure(111282, metric="residents")
    ).value == D(32)
    assert licence_density(
        measure(4782, metric="licences"), measure(3219982, metric="residents")
    ).value == D(15)
    restaurants = location_quotient(
        measure(361, geography="al_daayen"),
        measure(13600, geography="al_daayen"),
        measure(4782, geography="national", kind="national"),
        measure(249622, geography="national", kind="national"),
    )
    coffee = location_quotient(
        measure(173, geography="al_daayen"),
        measure(13600, geography="al_daayen"),
        measure(1042, geography="national", kind="national"),
        measure(249622, geography="national", kind="national"),
    )
    assert fact_value(restaurants["value"]) == D("1.39")
    assert fact_value(coffee["value"]) == D("3.05")
    withheld = location_quotient(
        measure(9),
        measure(100),
        measure(10, geography="national", kind="national"),
        measure(1000, geography="national", kind="national"),
    )
    assert withheld["status"] == NoData("too_few_licences")
    assert fact_value(withheld["count"]) == D(9)
    assert fact_value(
        location_quotient(
            measure(10),
            measure(100),
            measure(10, geography="national", kind="national"),
            measure(1000, geography="national", kind="national"),
        )["value"]
    ) == D(10)


def test_zero_national_share_and_activity_above_the_local_total():
    with pytest.raises(ValueError, match="non-positive"):
        location_quotient(
            measure(10),
            measure(100),
            measure(0, geography="national", kind="national"),
            measure(100, geography="national", kind="national"),
        )
    with pytest.raises(ValueError, match="exceeds"):
        location_quotient(
            measure(11),
            measure(10),
            measure(10, geography="national", kind="national"),
            measure(100, geography="national", kind="national"),
        )


def test_churn_interval_includes_the_equal_count():
    result = licence_churn(
        measure(10),
        {"2025-01": month_count("2025-01", 10)},
        {},
        calendar(),
        national_total(10),
        national_total(10),
    )
    assert tuple(f.value for f in result["including_interval"]) == (
        D("0.722"),
        D("1.000"),
    )
    assert tuple(f.value for f in result["excluding_interval"]) == (
        D("0.722"),
        D("1.000"),
    )
    assert result["including_interval_unrounded"] is not None


def test_c1_interval_is_the_card_scale_not_the_share_formula():
    """Independent of calling wilson() again: 10 of 100 against a national share of 0.01."""
    result = location_quotient(
        measure(10),
        measure(100),
        measure(10, geography="national", kind="national"),
        measure(1000, geography="national", kind="national"),
    )
    low, high = result["interval"]
    assert (low.value, high.value) == (D("5.52"), D("17.44"))


@pytest.mark.parametrize("args", [(0, 0), (1, -1), (1.5, 100)])
def test_c1_invalid_counts(args):
    with pytest.raises(ValueError):
        licence_density(measure(args[0]), measure(args[1]))


def test_c1_refuses_a_unit_period_or_geography_mismatch():
    with pytest.raises(MeasureMismatch, match="unit"):
        licence_density(measure(10, unit="qar"), measure(100))
    with pytest.raises(MeasureMismatch, match="period"):
        licence_density(measure(10, period="2025-05"), measure(100, period="2024-05"))
    with pytest.raises(MeasureMismatch, match="geography"):
        licence_density(measure(10, geography="a"), measure(100, geography="b"))


def calendar():
    return tuple(f"{2015 + i // 12}-{i % 12 + 1:02}" for i in range(125))


def month_count(month: str, value: int, geography: str = "invented_muni") -> Measure:
    kind = "national" if geography == "national" else "municipality"
    return measure(value, period=month, geography=geography, kind=kind)


def national_total(value: int) -> Measure:
    return measure(value, geography="national", kind="national")


def test_c2_printed_percentages_ratio_undated():
    national = {
        "2020-07": month_count("2020-07", 40791, "national"),
        "2022-06": month_count("2022-06", 14212, "national"),
        "2024-09": month_count("2024-09", 11232, "national"),
    }
    for active, cancelled, expected in [
        (2109, 318, "15.1"),
        (361, 49, "13.6"),
        (7878, 2510, "31.9"),
    ]:
        result = licence_churn(
            measure(active),
            {"2024-01": month_count("2024-01", cancelled)},
            national,
            calendar(),
            national_total(161055),
            national_total(153669),
        )
        assert fact_value(result["including_percent"]) == D(expected)
        assert result["undated_count"].value == 7386
        assert "undated_share" not in result
    assert fact_value(result["including_ratio"]) == D("0.32")
    assert fact_value(result["bulk_share_percent"]) == D("43.1")
    assert result["bulk_months_unrounded"] == ("2020-07", "2022-06", "2024-09")


def test_c2_exclusion_and_non_binomial_flow():
    result = licence_churn(
        measure(10),
        {"2020-07": month_count("2020-07", 20), "2020-01": month_count("2020-01", 1)},
        {"2020-07": month_count("2020-07", 20, "national")},
        calendar(),
        national_total(21),
        national_total(21),
    )
    assert fact_value(result["including_percent"]) == D(210)
    assert fact_value(result["excluding_percent"]) == D(10)
    assert result["including_interval"] == NoData("not_coverable")
    assert result["excluding_interval"] is not None
    with pytest.raises(ValueError):
        licence_churn(
            measure(10),
            {},
            {},
            calendar()[:-1],
            national_total(1),
            national_total(1),
        )
    with pytest.raises(ValueError):
        licence_churn(
            measure(10),
            {},
            {},
            (*calendar(), calendar()[0]),
            national_total(1),
            national_total(1),
        )


def test_c2_count_and_calendar_refusals():
    with pytest.raises(ValueError, match="bulk"):
        licence_churn(
            measure(10),
            {},
            {"2020-07": month_count("2020-07", 5, "national")},
            calendar(),
            national_total(4),
            national_total(4),
        )
    with pytest.raises(ValueError, match="dated"):
        licence_churn(
            measure(10),
            {},
            {},
            calendar(),
            national_total(1),
            national_total(2),
        )
    with pytest.raises(ValueError, match="outside"):
        licence_churn(
            measure(10),
            {"2014-12": month_count("2014-12", 1)},
            {},
            calendar(),
            national_total(1),
            national_total(1),
        )


def test_wilson_and_reliability():
    lo, hi = wilson(6, 28)
    assert (rounded(lo, 3), rounded(hi, 3)) == ("0.102", "0.395")
    assert reliability(29) == "low_count"
    assert reliability(30) == "standard"
    assert reliability(None) == "not_applicable"
    full_low, full_high = wilson(10, 10)
    assert rounded(full_high, 3) == "1.000"
    assert rounded(full_low, 3) == "0.722"
    for k, n in [(1, 0), (-1, 10), (11, 10)]:
        with pytest.raises(ValueError):
            wilson(k, n)


def test_invented_c8_fixture_row_is_read():
    row = json.loads(FIXTURE.read_text())["invented"]["C8"]
    result = coverage_share(measure(row["private"]), measure(row["employed"]))
    assert fact_value(result["percent"]) == D(75)


def test_c8_invented_coverage_and_workplace():
    result = coverage_share(measure(3), measure(4))
    assert fact_value(result["percent"]) == D(75)
    assert result["geography_unrounded"] == "municipality:invented_muni"
    assert coverage_share(None, None, workplace=True) == NoData(
        "coverage_by_workplace_not_published"
    )
    with pytest.raises(MeasureMismatch, match="geography"):
        coverage_share(
            measure(3, geography="invented_zone"),
            measure(4, geography="different_zone"),
        )


def test_c8_reliability_and_interval_literals():
    wide = coverage_share(measure(10), measure(40))
    assert wide["reliability_unrounded"] == "standard"
    narrow = coverage_share(measure(3), measure(4))
    assert tuple(fact_value(f) for f in narrow["interval"]) == (D("0.301"), D("0.954"))


def test_c5_invented_all_origins_and_exclusions():
    months = tuple(f"2025-{i:02}" for i in range(1, 13))
    rows = [trade("invented_line", str(i), "2025-01", 10, 2) for i in range(6)]
    rows += [
        trade("invented_line", "0", "2025-01", 10, 0),
        trade("invented_line", "0", "2025-01", 10, 2, "litre"),
    ]
    result = supplier_metrics(rows, ("invented_line",), months, months, reviewed=True)
    assert fact_value(result["total_value"]) == D(80)
    assert fact_value(result["origin_count"]) == 6
    assert fact_value(result["origins"]["0"]["share_percent"]) == D("37.5")
    assert fact_value(result["origins"]["0"]["unit_value"]) == D("5.00")
    assert fact_value(result["origins"]["0"]["other_units"]) == 1
    assert fact_value(result["origins"]["0"]["nonpositive_kg"]) == 1
    assert fact_value(result["hhi"]) == D("2187.50")
    with pytest.raises(ValueError):
        supplier_metrics(rows, ("invented_line",), months, months, reviewed=False)
    with pytest.raises(ValueError):
        supplier_metrics(rows, ("invented_line",), months, months[:-1], reviewed=True)


def test_c5_window_refusals():
    months = tuple(f"2025-{i:02}" for i in range(1, 13))
    with pytest.raises(ValueError, match="outside"):
        supplier_metrics(
            [trade("x", "o", "2024-12", 1, 1)], ("x",), months, months, reviewed=True
        )
    with pytest.raises(ValueError, match="consecutive"):
        broken = (*months[:-1], "2026-01")
        supplier_metrics([], ("x",), broken, broken, reviewed=True)
    with pytest.raises(ValueError, match="invalid month"):
        bad = (*months[1:], "2025-13")
        supplier_metrics([], ("x",), bad, bad, reviewed=True)
    with pytest.raises(ValueError):
        supplier_metrics([], ("x", "x"), months, months, reviewed=True)
    prior = tuple(f"2024-{i:02}" for i in range(1, 13))
    with pytest.raises(ValueError, match="prior row"):
        supplier_metrics(
            [trade("x", "o", months[0], 1, 1)],
            ("x",),
            months,
            (*prior, *months),
            reviewed=True,
            prior_rows=[trade("x", "o", months[0], 1, 1)],
            prior_months=prior,
        )


def test_c9_invented_order_eligibility_precision_and_partial_year():
    rows = [
        energy(k, 2021, 1000000) for k in ("invented_a", "invented_b", "invented_c")
    ]
    rows += [
        energy("invented_a", 2025, 3344000),
        energy("invented_b", 2025, 3344900),
        energy("invented_c", 2025, 3344000),
    ]
    result = zone_momentum(
        rows, energy("national", 2021, "41.78"), energy("national", 2025, "55.83")
    )
    assert fact_value(result["national_ratio"]) == D("1.34")
    assert result["order_unrounded"] == ("invented_b", "invented_a", "invented_c")
    assert fact_value(result["zones"]["invented_a"]["ratio"]) == D("3.34")
    for altered in [
        [*rows, rows[0]],
        rows[:-1],
        [energy(r.zone, r.year, r.value, False) for r in rows],
    ]:
        with pytest.raises(ValueError):
            zone_momentum(
                altered, energy("national", 2021, 1), energy("national", 2025, 2)
            )


def test_c9_tie_reversed_input_and_numeric_zone_keys():
    rows = [
        energy(k, 2021, 1000000) for k in ("invented_a", "invented_b", "invented_c")
    ]
    rows += [
        energy("invented_a", 2025, 3344000),
        energy("invented_b", 2025, 3344900),
        energy("invented_c", 2025, 3344000),
    ]
    result = zone_momentum(
        list(reversed(rows)),
        energy("national", 2021, "41.78"),
        energy("national", 2025, "55.83"),
    )
    assert result["order_unrounded"] == ("invented_b", "invented_a", "invented_c")
    tied = [
        energy("10", 2021, 1000000),
        energy("2", 2021, 1000000),
        energy("10", 2025, 2000000),
        energy("2", 2025, 2000000),
    ]
    ordered = zone_momentum(
        tied, energy("national", 2021, 1), energy("national", 2025, 2)
    )
    assert ordered["order_unrounded"] == ("2", "10")


def test_c9_refusals_and_fixed_baseline():
    rows = [energy("z", 2021, 1000000), energy("z", 2025, 2000000)]
    with pytest.raises(ValueError):
        zone_momentum(rows, energy("national", 2025, 2), energy("national", 2021, 1))
    with pytest.raises(ValueError, match="negative"):
        zone_momentum(
            [energy("z", 2021, 1000000), energy("z", 2025, -1)],
            energy("national", 2021, 1),
            energy("national", 2025, 2),
        )
    with pytest.raises(ValueError, match="baseline"):
        zone_momentum(
            [],
            energy("national", 2021, 1),
            energy("national", 2025, 2),
            minimum_baseline=D(0),
        )
    with pytest.raises(ValueError, match="2021"):
        zone_momentum(
            [energy("z", 2023, 1000000), energy("z", 2024, 2000000)],
            energy("national", 2023, 1),
            energy("national", 2024, 2),
        )
    small = zone_momentum(
        [energy("z", 2021, 5), energy("z", 2025, 50)],
        energy("national", 2021, 1),
        energy("national", 2025, 2),
    )
    assert small["order_unrounded"] == ()
    assert small["zones"]["z"]["ranked_unrounded"] is False


def test_published_zone_order_and_zone_69():
    """Card C9 order and zone 69's 3.34, from the published zone levels."""
    published = json.loads(FIXTURE.read_text())["published"]["C9"]
    rows = []
    for zone in published["zones"]:
        rows.append(energy(zone["zone"], 2021, zone["kwh_2021"].replace(",", "")))
        rows.append(energy(zone["zone"], 2025, zone["kwh_2025"].replace(",", "")))
    result = zone_momentum(
        rows,
        energy("national", 2021, published["national_before"]),
        energy("national", 2025, published["national_after"]),
    )
    assert result["order_unrounded"][:4] == ("2", "72", "29", "69")
    assert fact_value(result["zones"]["69"]["ratio"]) == D("3.34")
    assert fact_value(result["national_ratio"]) == D("1.34")
    assert result["zones"]["69"]["relative"].value == D("2.50")
    assert [
        result["zones"][z]["ranked_ratio"].value for z in ("2", "72", "29", "69")
    ] == [D("6.5"), D("5.4"), D("4.0"), D("3.3")]
    assert [
        result["zones"][zone]["ratio"].value for zone in ("2", "72", "29", "69")
    ] == [
        D("6.47"),
        D("5.39"),
        D("4.03"),
        D("3.34"),
    ]


def test_committed_method_fixture_arithmetic():
    fixtures = json.loads(FIXTURE.read_text())
    published = fixtures["published"]
    c1 = published["C1"]
    assert licence_density(
        measure(c1["local_restaurants"], metric="licences"),
        measure(c1["local_population"], metric="residents"),
    ).value == D(c1["density"][0])
    assert fact_value(
        location_quotient(
            measure(c1["local_coffee"], geography="al_daayen"),
            measure(c1["local_all"], geography="al_daayen"),
            measure(c1["national_coffee"], geography="national", kind="national"),
            measure(c1["national_all"], geography="national", kind="national"),
        )["value"]
    ) == D(c1["lq"][1])
    c2 = published["C2"]
    churn = licence_churn(
        measure(7878),
        {"2024-01": month_count("2024-01", 2510)},
        {
            month: month_count(month, value, "national")
            for month, value in c2["bulk"].items()
        },
        calendar(),
        national_total(c2["all"]),
        national_total(c2["dated"]),
    )
    assert churn["undated_count"].value == D(7386)
    assert churn["bulk_share_percent"].value == D("43.1")
    c5 = published["C5"]
    months = tuple(f"2025-{i:02}" for i in range(1, 13))
    supplied = supplier_metrics(
        [trade("heading", "invented", "2025-01", D(c5["value"]), D(c5["weight"]))],
        ("heading",),
        months,
        months,
        reviewed=True,
    )
    assert fact_value(supplied["origins"]["invented"]["unit_value"]) == D(
        c5["unit_value"]
    )
    assert c1["sources"] == ["lic_active", "pop_muni"]
    assert (
        fixtures["sources"]["pop_muni"]["dataset"]
        == "population-and-labour-force-by-municipality"
    )


def test_supplier_prior_window_is_adjacent_and_like_for_like():
    months = tuple(f"2025-{i:02}" for i in range(1, 13))
    prior = tuple(f"2024-{i:02}" for i in range(1, 13))
    result = supplier_metrics(
        [trade("invented", "invented", months[0], 30, 1)],
        ("invented",),
        months,
        (*prior, *months),
        reviewed=True,
        prior_rows=[trade("invented", "invented", prior[0], 20, 1)],
        prior_months=prior,
    )
    assert fact_value(result["trend"]) == D("0.5")
    old = tuple(f"2023-{i:02}" for i in range(1, 13))
    with pytest.raises(ValueError, match="adjacent"):
        supplier_metrics(
            [trade("invented", "invented", months[0], 30, 1)],
            ("invented",),
            months,
            (*old, *months),
            reviewed=True,
            prior_rows=[],
            prior_months=old,
        )


def test_rounding_boundaries_and_missing_results():
    assert coverage_share(None, measure(6)) == NoData("no_denominator")
    assert fact_value(coverage_share(measure(1), measure(6))["percent"]) == D("16.7")
    churn = licence_churn(
        measure(6),
        {"2025-01": month_count("2025-01", 1)},
        {"2020-07": month_count("2020-07", 1, "national")},
        calendar(),
        national_total(6),
        national_total(6),
    )
    assert fact_value(churn["excluding_percent"]) == D("16.7")
    assert fact_value(churn["bulk_share_percent"]) == D("16.7")
    months = tuple(f"2025-{i:02}" for i in range(1, 13))
    assert supplier_metrics([], ("invented",), months, months, reviewed=True) == NoData(
        "no_denominator"
    )
    result = supplier_metrics(
        [
            trade("invented", "invented_a", months[0], 1, 3),
            trade("invented", "invented_b", months[0], 2, 3),
        ],
        ("invented",),
        months,
        months,
        reviewed=True,
    )
    assert fact_value(result["hhi"]) == D("5555.56")
    assert fact_value(result["origins"]["invented_a"]["share_percent"]) == D("33.3")
    assert fact_value(result["origins"]["invented_a"]["unit_value"]) == D("0.33")
    momentum = zone_momentum(
        [energy("invented", 2021, 1000000), energy("invented", 2025, 1000000)],
        energy("national", 2021, 3),
        energy("national", 2025, 7),
    )
    assert fact_value(momentum["zones"]["invented"]["relative"]) == D("0.43")
