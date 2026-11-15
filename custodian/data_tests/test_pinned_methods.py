"""MTH-03 replays, explicitly invoked by the lead on pinned public-cache receipts."""

from decimal import Decimal as D

import pytest
from custodian.data_tests.cache import pinned

from eii_core.calc.facts import Measure, NoData
from eii_core.calc.public_methods import (
    AnnualEnergy,
    TradeRow,
    licence_churn,
    supplier_metrics,
    zone_momentum,
)
from eii_core.calc.public_series import decomposition, ratio, rounded
from eii_core.calc.sector_economics import Component, sector_norms, share_range
from eii_custodian.publicdata.series.parse import customs_code, source_period


def reading(value, unit, period, chain, geography="national"):
    return Measure(
        D(str(value)),
        unit,
        str(period),
        geography,
        "national" if geography == "national" else "public",
        "public",
        (chain,),
    )


@pytest.mark.parametrize(
    "source,last,expected",
    [
        (
            "wage_occ",
            "2025",
            {
                "mean_before": "10084",
                "mean_after": "11855",
                "change": "1771",
                "within": "38",
                "mix": "1733",
                "mix_share_percent": "97.8",
                "change_percent": "17.6",
                "fixed_composition_percent": "1.0",
            },
        ),
        ("wage_act", "2023", {"change": "673", "mix": "572"}),
    ],
)
def test_pinned_c3(source, last, expected):
    rows, chain = pinned(source)
    dimension = "occupation" if source == "wage_occ" else "economic_activity"

    def groups(year):
        selected = [r for r in rows if str(r["year"]) == year]
        result = {}
        for row in selected:
            key = str((row["gender"], row[dimension]))
            assert key not in result, "duplicate wage group"
            result[key] = (
                reading(row["paid_employment_workers"], "count", year, chain),
                reading(row["monthly_average_wage_qr"], "qar_per_month", year, chain),
            )
        return result

    result = decomposition(groups("2020"), groups(last))
    for key, literal in expected.items():
        assert result[key].value == D(literal), key
        assert result[key].sources == (chain,)


def test_pinned_c4():
    sources = {
        source: pinned(source)
        for source in ("sec_hr_ind", "sec_hr_size", "sec_hr_goods", "sec_hr_serv")
    }
    results = {}
    for year in ("2018", "2019", "2020", "2021", "2022"):
        chosen = {
            source: [
                r
                for r in pair[0]
                if str(r["year"]) == year and str(r["activity_code"]) == "561"
            ]
            for source, pair in sources.items()
        }
        assert len(chosen["sec_hr_ind"]) == 1
        row = chosen["sec_hr_ind"][0]

        def m(value, unit, source="sec_hr_ind", year=year):
            return reading(value, unit, year, sources[source][1])

        employees = sum(
            (D(str(r["number_of_employees"])) for r in chosen["sec_hr_size"]), D(0)
        )
        components = []
        for source, group, label, field, wanted in (
            (
                "sec_hr_goods",
                "goods",
                "type_of_commodity",
                "estimates_of_intermediate_goods_value_value_in_1_000_qr",
                (("food", "Food Stuff"), ("beverages", "Beverages")),
            ),
            (
                "sec_hr_serv",
                "services",
                "type_of_service",
                "estimates_of_intermediate_services_value_value_in_1_000_qr",
                (("rent", "Rents of Buildings"),),
            ),
        ):
            total = sum((D(str(r[field])) for r in chosen[source]), D(0))
            for key, published_label in wanted:
                matching = [
                    r
                    for r in chosen[source]
                    if str(r[label]).casefold() == published_label.casefold()
                ]
                assert len(matching) == 1, "source component label:" + published_label
                components.append(
                    Component(
                        key,
                        group,
                        m(matching[0][field], "qar_thousand", source),
                        m(total, "qar_thousand", source),
                        group,
                    )
                )
        results[year] = sector_norms(
            employees=m(employees, "count", "sec_hr_size"),
            productivity=m(row["productivity_of_employee_qr"], "qar"),
            compensation_thousand=m(
                row["compensation_of_employees_value_in_1_000_qr"], "qar_thousand"
            ),
            surplus_thousand=m(
                row["operating_surplus_value_in_1_000_qr"], "qar_thousand"
            ),
            goods_percent=m(
                row["percentage_of_intermediate_goods_to_output"], "percent"
            ),
            services_percent=m(
                row["percentage_of_intermediate_services_to_output"], "percent"
            ),
            components=components,
        )
    for key, literal in {
        "food": "29.3",
        "beverages": "5.6",
        "rent": "11.6",
        "compensation_percent": "20.6",
        "surplus_percent": "19.7",
        "goods_percent": "40.6",
        "services_percent": "16.5",
    }.items():
        assert results["2022"][key].value == D(literal)
    for key, low, high in (
        ("food", "28.0", "29.3"),
        ("rent", "11.6", "15.1"),
        ("compensation_percent", "20.6", "25.2"),
        ("surplus_percent", "6.9", "19.7"),
    ):
        assert share_range([r[key].value for r in results.values()]) == (
            D(low),
            D(high),
        )


def test_pinned_c9():
    rows, chain = pinned("util_elec")
    selected = [r for r in rows if str(r["year"]) in ("2021", "2025")]
    energies = [
        AnnualEnergy(
            str(r["zone_number"]),
            int(r["year"]),
            D(str(r["value"])),
            True,
            reading(
                r["value"], "kwh", r["year"], chain, "zone:" + str(r["zone_number"])
            ),
        )
        for r in selected
    ]

    def national(year):
        total = sum((r.value for r in energies if r.year == year), D(0))
        return AnnualEnergy(
            "national", year, total, True, reading(total, "kwh", year, chain)
        )

    result = zone_momentum(energies, national(2021), national(2025))
    assert result["national_ratio"].value == D("1.34")
    assert result["zones"]["69"]["ratio"].value == D("3.34")
    assert result["order_unrounded"][:4] == ("2", "72", "29", "69")
    assert [
        result["zones"][key]["ranked_ratio"].value for key in ("2", "72", "29", "69")
    ] == [D("6.5"), D("5.4"), D("4.0"), D("3.3")]
    zero_zones = [r.zone for r in energies if r.year == 2021 and r.value == D(0)]
    assert zero_zones
    for zone in zero_zones:
        for slot in ("ratio", "ranked_ratio", "relative"):
            assert result["zones"][zone][slot] == NoData("no_denominator")
        assert result["zones"][zone]["ratio_unrounded"] is None
        assert result["zones"][zone]["ranked_unrounded"] is False
        assert zone not in result["order_unrounded"]


C2_CALENDAR = tuple(f"{2015 + i // 12}-{i % 12 + 1:02}" for i in range(125))

EXPECTED_C2_BULK_MONTHS = (
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

C2_MUNICIPAL_EXAMPLES = (
    ("بلدية الدوحة", "doha", 2109, 318, "15.1"),
    ("بلدية الظعاين", "al_daayen", 361, 49, "13.6"),
)


def c2_national_totals(rows, chain):
    counts: dict[str, D] = {}
    undated = D(0)
    for row in rows:
        period = source_period("lic_cancelled", row["sn_llg"], row["shhr_llg"])
        value = D(str(row["dd_lrkhs_lmlg"]))
        if period is None:
            undated += value
        else:
            counts[period] = counts.get(period, D(0)) + value
    dated = sum(counts.values(), D(0))
    months = {
        period: reading(value, "count", period, chain)
        for period, value in counts.items()
    }
    return counts, dated, undated, months


def c2_municipal_churn(
    active_rows,
    active_chain,
    cancelled_rows,
    cancelled_chain,
    municipality_ar: str,
    slug: str,
    activity_code: str = "5610101",
    year: str = "2024",
):
    if municipality_ar not in {row["lbldy"] for row in active_rows}:
        raise ValueError(f"municipality_missing:lic_active:{slug}:{municipality_ar}")
    if municipality_ar not in {row["lbldy"] for row in cancelled_rows}:
        raise ValueError(f"municipality_missing:lic_cancelled:{slug}:{municipality_ar}")
    stock_rows = [
        row
        for row in active_rows
        if row["lbldy"] == municipality_ar and row["rmz_lnsht_ltjry"] == activity_code
    ]
    if not stock_rows:
        raise ValueError(f"activity_missing:lic_active:{slug}:{activity_code}")
    stock = sum((D(str(row["dd_lrkhs_lnsht"])) for row in stock_rows), D(0))
    _, dated, undated, national_months = c2_national_totals(
        cancelled_rows, cancelled_chain
    )
    year_months = {f"{year}-{m:02}" for m in range(1, 13)}
    local_counts: dict[str, D] = {}
    for row in cancelled_rows:
        if row["lbldy"] == municipality_ar and row["rmz_lnsht_ltjry"] == activity_code:
            period = source_period("lic_cancelled", row["sn_llg"], row["shhr_llg"])
            if period in year_months:
                local_counts[period] = local_counts.get(period, D(0)) + D(
                    str(row["dd_lrkhs_lmlg"])
                )
    cancelled_total = sum(local_counts.values(), D(0))
    geography = f"municipality:{slug}"
    local_months = {
        period: reading(val, "count", period, cancelled_chain, geography)
        for period, val in local_counts.items()
    }
    result = licence_churn(
        reading(stock, "count", "2025-05", active_chain, geography),
        local_months,
        national_months,
        C2_CALENDAR,
        reading(dated + undated, "count", "2025-05", cancelled_chain),
        reading(dated, "count", "2025-05", cancelled_chain),
    )
    return stock, cancelled_total, result


def test_pinned_c2_national_cancellations():
    rows, chain = pinned("lic_cancelled")
    counts, dated, undated, months = c2_national_totals(rows, chain)
    active, active_chain = pinned("lic_active")
    stock = sum((D(str(row["dd_lrkhs_lnsht"])) for row in active), D(0))
    result = licence_churn(
        reading(stock, "count", "2025-05", active_chain),
        months,
        months,
        C2_CALENDAR,
        reading(dated + undated, "count", "2025-05", chain),
        reading(dated, "count", "2025-05", chain),
    )
    assert dated == D(153669)
    assert undated == D(7386)
    assert result["undated_count"].value == D(7386)
    for month, expected_count in (
        ("2020-07", 40791),
        ("2022-06", 14212),
        ("2024-09", 11232),
    ):
        assert month in result["bulk_months_unrounded"]
        assert counts[month] == D(expected_count)
    named_three = counts["2020-07"] + counts["2022-06"] + counts["2024-09"]
    named_share = D(rounded(ratio(named_three * 100, dated), 1))
    assert abs(named_share - D("43.1")) <= D("0.1")
    assert named_share == D("43.1")
    assert abs(result["bulk_share_percent"].value - D("89.7")) <= D("0.1")
    assert result["bulk_share_percent"].value == D("89.7")
    assert result["bulk_months_unrounded"] == EXPECTED_C2_BULK_MONTHS


@pytest.mark.parametrize(
    (
        "municipality_ar",
        "slug",
        "expected_active",
        "expected_cancelled",
        "expected_percent",
    ),
    C2_MUNICIPAL_EXAMPLES,
)
def test_pinned_c2_municipal_restaurants(
    municipality_ar: str,
    slug: str,
    expected_active: int,
    expected_cancelled: int,
    expected_percent: str,
):
    active_rows, active_chain = pinned("lic_active")
    cancelled_rows, cancelled_chain = pinned("lic_cancelled")
    stock, cancelled_2024, result = c2_municipal_churn(
        active_rows,
        active_chain,
        cancelled_rows,
        cancelled_chain,
        municipality_ar,
        slug,
    )
    assert cancelled_2024 == D(expected_cancelled)
    assert stock == D(expected_active)
    assert result["active_count"].value == D(expected_active)
    assert abs(result["including_percent"].value - D(expected_percent)) <= D("0.1")
    assert result["including_percent"].value == D(expected_percent)
    geography = f"municipality:{slug}"
    for fact in (
        result["active_count"],
        result["including_ratio"],
        result["including_percent"],
        result["excluding_percent"],
        *result["including_interval"],
        *result["excluding_interval"],
    ):
        assert (fact.geography, fact.geography_kind) == (geography, "public")
    for fact in (result["undated_count"], result["bulk_share_percent"]):
        assert (fact.geography, fact.geography_kind) == ("national", "national")


def test_pinned_c5_heading_checks_only():
    rows, chain = pinned("cus_imp_2025")
    selected = [r for r in rows if str(r["year"]) == "2025"]
    months = tuple(f"2025-{i:02}" for i in range(1, 13))
    trades = []
    for row in selected:
        code = customs_code("cus_imp_2025", row["harmonized_system_code"])
        month = source_period("cus_imp_2025", row["year"], row["month"])
        value, weight = (
            D(str(row["value_in_qatari_riyals"])),
            D(str(row["weight_in_kilograms"])),
        )
        trades.append(
            TradeRow(
                code or "not_stated",
                str(row["country_of_origin"]),
                month,
                value,
                weight,
                "kg",
                reading(value, "qar", month, chain),
                reading(weight, "kg", month, chain),
            )
        )
    total = supplier_metrics(
        trades, sorted({r.product for r in trades}), months, months, reviewed=True
    )
    assert rounded(total["total_value"].exact_unrounded / 10**9, 2) == "138.53"
    for heading, origin, expected in (
        ("1902", "Italy", "8.69"),
        ("1902", "Saudi Arabia", "11.45"),
        ("0406", "Italy", "40.61"),
        ("0406", "Denmark", "26.06"),
        ("1509", "Italy", "30.60"),
        ("1509", "Lebanon", "19.26"),
    ):
        chosen = [r for r in trades if r.product.startswith(heading)]
        result = supplier_metrics(
            chosen, sorted({r.product for r in chosen}), months, months, reviewed=True
        )
        assert result["origins"][origin]["unit_value"].value == D(expected)
