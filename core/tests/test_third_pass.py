"""Third-pass regressions on invented fixtures."""

from decimal import Decimal as D

import pytest
from method_rows import energy, measure

from eii_core.calc.facts import MeasureMismatch, NoData
from eii_core.calc.public_methods import licence_churn, zone_momentum
from eii_core.calc.public_series import ratio, rounded


@pytest.mark.parametrize("later_kwh", [0, 500000])
def test_c9_zero_base_zones_emit_no_denominator_and_preserve_order(later_kwh: int):
    baseline_rows = [
        energy("invented_high", 2021, 1000000),
        energy("invented_high", 2025, 4000000),
        energy("invented_mid", 2021, 1000000),
        energy("invented_mid", 2025, 2500000),
        energy("invented_below_floor", 2021, 500),
        energy("invented_below_floor", 2025, 1500),
    ]
    result = zone_momentum(
        [
            *baseline_rows,
            energy("invented_zero", 2021, 0),
            energy("invented_zero", 2025, later_kwh),
        ],
        energy("national", 2021, 10),
        energy("national", 2025, 20),
    )
    zero_entry = result["zones"]["invented_zero"]
    for slot in ("ratio", "ranked_ratio", "relative"):
        assert zero_entry[slot] == NoData("no_denominator")
    assert zero_entry["ratio_unrounded"] is None
    assert zero_entry["ranked_unrounded"] is False
    assert "invented_zero" not in result["order_unrounded"]
    assert result["order_unrounded"] == ("invented_high", "invented_mid")
    assert result["national_ratio"].value == D("2.00")
    for other, multiple, relative in (
        ("invented_high", "4.00", "2.00"),
        ("invented_mid", "2.50", "1.25"),
        ("invented_below_floor", "3.00", "1.50"),
    ):
        assert result["zones"][other]["ratio"].value == D(multiple)
        assert result["zones"][other]["relative"].value == D(relative)
    assert result["zones"]["invented_below_floor"]["ratio"].value == D("3.00")
    assert result["zones"]["invented_below_floor"]["relative"].value == D("1.50")
    assert result["zones"]["invented_below_floor"]["ranked_unrounded"] is False
    assert "invented_below_floor" not in result["order_unrounded"]


def _calendar() -> tuple[str, ...]:
    return tuple(f"{2015 + i // 12}-{i % 12 + 1:02}" for i in range(125))


def _national(value: int, period: str = "2025-05"):
    return measure(value, period=period, geography="national", kind="national")


def test_c2_municipal_call_emits_national_and_local_geographies():
    result = licence_churn(
        measure(2109, geography="invented_muni", kind="municipality"),
        {
            "2024-01": measure(
                300, period="2024-01", geography="invented_muni", kind="municipality"
            ),
            "2024-09": measure(
                18, period="2024-09", geography="invented_muni", kind="municipality"
            ),
        },
        {
            "2020-07": _national(40791, "2020-07"),
            "2022-06": _national(14212, "2022-06"),
            "2024-09": _national(11232, "2024-09"),
        },
        _calendar(),
        _national(161055),
        _national(153669),
    )
    assert result["active_count"].value == D(2109)
    assert result["including_percent"].value == D("15.1")
    for fact in (
        result["active_count"],
        result["including_ratio"],
        result["including_percent"],
        result["excluding_percent"],
        *result["including_interval"],
        *result["excluding_interval"],
    ):
        assert (fact.geography, fact.geography_kind) == (
            "municipality:invented_muni",
            "public",
        )
    for fact in (result["undated_count"], result["bulk_share_percent"]):
        assert (fact.geography, fact.geography_kind) == ("national", "national")


@pytest.mark.parametrize("active_geo", ["muni", "national"])
@pytest.mark.parametrize("which", ["all", "dated", "month"])
def test_c2_refuses_national_totals_under_municipal_geography(
    active_geo: str, which: str
):
    active = (
        measure(20, geography="invented_muni", kind="municipality")
        if active_geo == "muni"
        else _national(20)
    )
    bad = measure(10, geography="invented_muni", kind="municipality")
    bad_month = measure(
        10, period="2024-09", geography="invented_muni", kind="municipality"
    )
    with pytest.raises(MeasureMismatch, match="geography"):
        licence_churn(
            active,
            {},
            {"2024-09": bad_month if which == "month" else _national(10, "2024-09")},
            _calendar(),
            bad if which == "all" else _national(10),
            bad if which == "dated" else _national(10),
        )


INVENTED_42_BULK_MONTHS = (
    "2017-06",
    "2020-07",
    "2020-11",
    "2021-02",
    "2021-04",
    "2021-05",
    "2021-06",
    "2021-12",
    "2022-01",
    "2022-02",
    "2022-03",
    "2022-04",
    "2022-06",
    "2022-12",
    "2023-01",
    "2023-02",
    "2023-03",
    "2023-04",
    "2023-05",
    "2023-06",
    "2023-07",
    "2023-08",
    "2023-09",
    "2023-10",
    "2023-11",
    "2023-12",
    "2024-01",
    "2024-02",
    "2024-03",
    "2024-04",
    "2024-05",
    "2024-06",
    "2024-07",
    "2024-08",
    "2024-09",
    "2024-10",
    "2024-11",
    "2024-12",
    "2025-01",
    "2025-02",
    "2025-03",
    "2025-04",
)


def test_c2_invented_125_month_series_mirrors_national_data_test():
    named_peaks = {"2020-07": 2000, "2022-06": 1200, "2024-09": 1070}
    flagged_set = set(INVENTED_42_BULK_MONTHS)
    counts: dict[str, int] = {}
    for month in _calendar():
        if month in named_peaks:
            counts[month] = named_peaks[month]
        elif month in flagged_set:
            counts[month] = 100
        else:
            counts[month] = 10
    dated = D(sum(counts.values()))
    undated = D(500)
    months = {period: _national(val, period) for period, val in counts.items()}
    result = licence_churn(
        _national(50000),
        months,
        months,
        _calendar(),
        _national(int(dated + undated)),
        _national(int(dated)),
    )
    assert dated == D(9000)
    assert result["undated_count"].value == D(500)
    for month, expected_count in (
        ("2020-07", 2000),
        ("2022-06", 1200),
        ("2024-09", 1070),
    ):
        assert month in result["bulk_months_unrounded"]
        assert D(counts[month]) == D(expected_count)
    three_total = D(counts["2020-07"] + counts["2022-06"] + counts["2024-09"])
    three_share = D(rounded(ratio(three_total * 100, dated), 1))
    assert three_share == D("47.4")
    assert result["bulk_share_percent"].value == D("90.8")
    assert len(INVENTED_42_BULK_MONTHS) == 42
    assert result["bulk_months_unrounded"] == INVENTED_42_BULK_MONTHS


def test_c2_refuses_consistently_mislabelled_national_totals():
    with pytest.raises(MeasureMismatch, match="geography"):
        licence_churn(
            measure(20),
            {},
            {"2024-09": measure(10, period="2024-09")},
            _calendar(),
            measure(10),
            measure(10),
        )


def test_comparison_refuses_distinct_valid_geography_kinds():
    from dataclasses import replace

    from test_calculation_facts import fact

    from eii_core.calc.facts import compare_public_facts

    first = replace(
        fact(), geography="area_shape:invented", geography_kind="area_shape"
    )
    second = replace(
        fact(), geography="release_units:invented", geography_kind="release_units"
    )
    with pytest.raises(ValueError, match="incompatible period/geography"):
        compare_public_facts(first, second)


def test_comparison_refuses_invalid_month_adjacency():
    from test_calculation_facts import fact

    from eii_core.calc.facts import compare_public_facts

    with pytest.raises(ValueError, match="incompatible period/geography"):
        compare_public_facts(fact(period="2025-13"), fact(period="2026-02"))


def test_national_series_zone_identity_guard():
    from dataclasses import replace

    with pytest.raises(ValueError, match="incompatible national series"):
        zone_momentum(
            [],
            energy("national", 2021, 10),
            replace(energy("national", 2025, 20), zone="invented_other"),
        )


def test_coverage_refuses_excess_by_name():
    from eii_core.calc.public_methods import coverage_share

    with pytest.raises(ValueError, match="private employed exceeds employed"):
        coverage_share(measure(11), measure(10))


def test_invented_numeric_unit_is_refused():
    from dataclasses import replace

    from test_calculation_facts import fact

    with pytest.raises(ValueError, match="unsupported numeric unit"):
        replace(fact(), unit="invented_unit")


def test_c4_rejects_unknown_keyword_in_closed_signature():
    from test_sector_economics import inputs

    from eii_core.calc.sector_economics import sector_norms

    with pytest.raises(TypeError, match="invented_production"):
        sector_norms(**inputs()[0], invented_production=D(1))


def test_churn_unrounded_excluded_interval_at_equal_stock():
    result = licence_churn(
        measure(10),
        {"2024-01": measure(10, period="2024-01")},
        {},
        _calendar(),
        _national(10),
        _national(10),
    )
    assert tuple(rounded(x, 3) for x in result["excluding_interval_unrounded"]) == (
        "0.722",
        "1.000",
    )


def test_pay_levels_have_no_base_period():
    from test_second_fix import cell

    from eii_core.calc.public_series import decomposition

    result = decomposition({"a": cell(1, 10, "2020")}, {"a": cell(1, 20, "2025")})
    assert result["mean_before"].base_period == ""
    assert result["mean_after"].base_period == ""
    assert result["change"].base_period == "2020"


def test_no_payroll_size_band_direction():
    from dataclasses import replace

    from test_calculation_facts import fact

    from eii_core.calc.facts import compare_public_facts

    before = replace(fact(), value="no_payroll", unit="size_band")
    after = replace(fact(period="2025-02"), value="s01_09", unit="size_band")
    assert compare_public_facts(before, after).direction.value == "higher"


def test_user_scenario_geography_is_a_valid_closed_kind():
    row = measure(1, geography="user_scenario:invented", kind="user_scenario")
    assert row.geography == "user_scenario:invented"
    assert row.geography_kind == "user_scenario"
