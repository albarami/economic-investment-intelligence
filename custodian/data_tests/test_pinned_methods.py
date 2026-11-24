"""MTH-03 replays, explicitly invoked by the lead on pinned public-cache receipts."""

import importlib.util
import json
import sys
import warnings
from decimal import Decimal as D
from fractions import Fraction
from pathlib import Path

import pytest

from eii_core.calc.facts import Measure, NoData
from eii_core.calc.public_methods import (
    AnnualEnergy,
    TradeRow,
    coverage_share,
    licence_churn,
    licence_density,
    location_quotient,
    supplier_metrics,
    zone_momentum,
)
from eii_core.calc.public_series import decomposition, ratio, rounded
from eii_core.calc.sector_economics import Component, sector_norms, share_range
from eii_custodian.publicdata.fetch.page_workbook import read_sheet
from eii_custodian.publicdata.fetch.snapshots import reviewed_selections
from eii_custodian.publicdata.frame.census import (
    C8_SOURCES,
    c8_national_counts,
)
from eii_custodian.publicdata.frame.census import (
    c8_block_rows as _c8_block_rows,
)
from eii_custodian.publicdata.frame.crosswalk import (
    municipality_key,
    municipality_keys,
    read_csv,
)
from eii_custodian.publicdata.frame.layers import COUNTS, layer_rows
from eii_custodian.publicdata.frame.population import population_rows
from eii_custodian.publicdata.review.activity import SpineError, committed_class_members
from eii_custodian.publicdata.series.parse import customs_code, source_period

_CACHE_NAME = "eii_data_tests_cache"
_cache = sys.modules.get(_CACHE_NAME)
if _cache is None:
    _cache_spec = importlib.util.spec_from_file_location(
        _CACHE_NAME, Path(__file__).resolve().parent / "cache.py"
    )
    assert _cache_spec is not None and _cache_spec.loader is not None
    _cache = importlib.util.module_from_spec(_cache_spec)
    sys.modules[_CACHE_NAME] = _cache
    _cache_spec.loader.exec_module(_cache)
pinned = _cache.pinned


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


def c1_replay(active, active_chain, population, population_chain, review, name):
    """Replay C1 on reviewed source municipalities, counting legacy activities too."""
    names = read_csv(review / "municipality_names.csv")
    target = municipality_key(name, names)
    active_keys = municipality_keys("lic_active", active, ("lbldy",), names, None)
    if target not in active_keys:
        raise ValueError("C1:municipality_missing")
    residents, reason = population_rows(population, review, names, None)
    if reason.startswith("unreviewed_indicator"):
        raise ValueError("C1:population_indicator_unreviewed")
    residents = [
        row
        for row in residents
        if row["period"] == "2025" and row["indicator"] == "residents"
    ]
    resident_keys = [row["municipality_code"] for row in residents]
    if len(set(resident_keys)) != len(resident_keys):
        raise ValueError("C1:population_duplicate")
    if set(resident_keys) != set(active_keys):
        raise ValueError("C1:population_missing")

    def licences(code=None, local=False):
        return sum(
            (
                D(str(row["dd_lrkhs_lnsht"]))
                for row, key in zip(active, active_keys, strict=True)
                if (not local or key == target)
                and (code is None or row["rmz_lnsht_ltjry"] == code)
            ),
            D(0),
        )

    counts = {
        "local_all": licences(local=True),
        "national_all": licences(),
        "local_restaurants": licences("5610101", local=True),
        "national_restaurants": licences("5610101"),
        "local_coffee": licences("5630112", local=True),
        "national_coffee": licences("5630112"),
        "local_population": sum(
            (
                D(str(row["value"]))
                for row in residents
                if row["municipality_code"] == target
            ),
            D(0),
        ),
        "national_population": sum((D(str(row["value"])) for row in residents), D(0)),
    }

    def m(key):
        local = key.startswith("local_")
        chain = population_chain if key.endswith("population") else active_chain
        return reading(
            counts[key],
            "count",
            "2025",
            chain,
            f"municipality:{target}" if local else "national",
        )

    return {
        **counts,
        "density": (
            licence_density(m("local_restaurants"), m("local_population")),
            licence_density(m("national_restaurants"), m("national_population")),
        ),
        "lq": tuple(
            location_quotient(
                m(f"local_{activity}"),
                m("local_all"),
                m(f"national_{activity}"),
                m("national_all"),
            )["value"]
            for activity in ("restaurants", "coffee")
        ),
    }


def test_pinned_c1():
    active, active_chain = pinned("lic_active")
    population, population_chain = pinned("pop_muni")
    result = c1_replay(
        active,
        active_chain,
        population,
        population_chain,
        _cache.ROOT / "custodian/publicdata/review",
        "Al Daayen",
    )
    for key, expected in {
        "local_all": 13600,
        "national_all": 249622,
        "local_restaurants": 361,
        "national_restaurants": 4782,
        "local_coffee": 173,
        "national_coffee": 1042,
        "local_population": 111282,
        "national_population": 3219982,
    }.items():
        assert result[key] == D(expected), key
    assert tuple(fact.value for fact in result["density"]) == (D(32), D(15))
    for fact, expected in zip(result["lq"], ("1.39", "3.05"), strict=True):
        assert abs(fact.value - D(expected)) <= D("0.01")


def _c8_share(private, total, chain, geography):
    return coverage_share(
        reading(private, "count", "2020", chain, geography),
        reading(total, "count", "2020", chain, geography),
    )


def c8_zone_share(row, chain):
    """A null in any sector makes this zone unavailable, never partially summed."""
    counts = [row[field] for field in COUNTS[C8_SOURCES["zone"]]]
    if any(value is None for value in counts):
        return coverage_share(None, None)
    if sum(counts[1:]) != counts[0]:
        raise ValueError("C8:sector_sum")
    if counts[0] <= 0 or any(value < 0 for value in counts):
        raise ValueError("C8:zone_denominator")
    return _c8_share(row["Private"], counts[0], chain, "zone:" + str(row["ZONE_NO"]))


def _c8_agrees(actual, expected, reason):
    # Safe failure: no source value, share or zone identifier reaches the log.
    if abs(Fraction(actual) - expected) > Fraction(1, 2):
        raise ValueError("C8:" + reason + "_mismatch")


def _c8_check_sex_totals(sheet, both_row):
    """Independent Fraction checks on cached cells; never use calc or formulas."""
    starts = _c8_block_rows(sheet)

    def counts(number, reason):
        try:
            values = tuple(
                Fraction(sheet.cells[f"{column}{number}"]) for column in "CDEFGHIJ"
            )
        except (KeyError, ValueError, ZeroDivisionError):
            raise ValueError("C8:" + reason) from None
        if any(value < 0 or value.denominator != 1 for value in values):
            raise ValueError("C8:" + reason)
        return values

    totals = {
        start: counts(start, "national_count" if start == both_row else "sex_count")
        for start in starts
    }
    for start in starts:
        end = min(
            (number for number in starts if number > start), default=max(sheet.rows) + 1
        )
        activities = [
            counts(number, "activity_count")
            for number in sheet.rows
            if start < number < end and sheet.cells.get(f"A{number}", "").strip()
        ]
        for index, value in enumerate(totals[start]):
            if value != sum((row[index] for row in activities), Fraction(0)):
                raise ValueError("C8:activity_sum_mismatch")
    both, male, female = (totals[start] for start in starts)
    if any(b != m + f for b, m, f in zip(both, male, female, strict=True)):
        raise ValueError("C8:sex_sum_mismatch")
    if both[-1] != sum(both[:-1], Fraction(0)):
        raise ValueError("C8:national_sector_sum")


def test_pinned_c8():
    """Lead-only: compare calc to plain raw-file division, never store its values."""
    national_body, national_chain = _cache.pinned_body(C8_SOURCES["national"])
    zone_body, zone_chain = _cache.pinned_body(C8_SOURCES["zone"])
    sheet = read_sheet(national_body, "76", cached_formulas=True)
    number, private, total = c8_national_counts(sheet)
    _c8_check_sex_totals(sheet, number)
    national = _c8_share(private, total, national_chain, "national")
    # Independent plain arithmetic on the original cells, without calc helpers.
    expected_national = (
        Fraction(sheet.cells[f"F{number}"]) * 100 / Fraction(sheet.cells[f"J{number}"])
    )
    _c8_agrees(national["percent"].value, expected_national, "national")
    if national["percent"].sources != (national_chain,):
        raise ValueError("C8:national_lineage")

    payload = json.loads(zone_body)
    rows = layer_rows(C8_SOURCES["zone"], payload)
    if not rows or len({row["ZONE_NO"] for row in rows}) != len(rows):
        raise ValueError("C8:zone_keys")
    actual_shares, expected_shares = [], []
    for row, feature in zip(rows, payload["features"], strict=True):
        raw = feature["attributes"]
        result = c8_zone_share(row, zone_chain)
        if any(raw[field] is None for field in COUNTS[C8_SOURCES["zone"]]):
            if result != NoData("no_denominator"):
                raise ValueError("C8:null_zone_mismatch")
            continue
        expected = Fraction(raw["Private"] * 100, raw["Total_Economic_active___15"])
        _c8_agrees(result["percent"].value, expected, "zone")
        if result["percent"].sources != (zone_chain,):
            raise ValueError("C8:zone_lineage")
        actual_shares.append(result["percent"].value)
        expected_shares.append(expected)
    if not actual_shares:
        raise ValueError("C8:no_complete_zones")
    low, high = share_range(actual_shares)
    _c8_agrees(low, min(expected_shares), "range_low")
    _c8_agrees(high, max(expected_shares), "range_high")


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
    "2015-12",
    "2017-06",
    "2020-07",
    "2020-11",
    "2021-02",
    "2021-04",
    "2021-06",
    "2022-06",
    "2024-09",
)

C2_MUNICIPAL_EXAMPLES = (
    ("بلدية الدوحة", "doha", 2109, 318, "15.1", 283, "13.4"),
    ("بلدية الظعاين", "al_daayen", 361, 49, "13.6", 48, "13.3"),
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
    assert abs(result["bulk_share_percent"].value - D("54.3")) <= D("0.1")
    assert result["bulk_share_percent"].value == D("54.3")
    assert result["bulk_months_unrounded"] == EXPECTED_C2_BULK_MONTHS


@pytest.mark.parametrize(
    (
        "municipality_ar",
        "slug",
        "expected_active",
        "expected_cancelled",
        "expected_percent",
        "expected_excluded",
        "expected_excluded_percent",
    ),
    C2_MUNICIPAL_EXAMPLES,
)
def test_pinned_c2_municipal_restaurants(
    municipality_ar: str,
    slug: str,
    expected_active: int,
    expected_cancelled: int,
    expected_percent: str,
    expected_excluded: int,
    expected_excluded_percent: str,
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
    # Assert the unrounded numerator as well as its displayed percentage.
    assert (
        result["excluding_percent"].exact_unrounded * expected_active
        == expected_excluded * 100
    )
    assert result["excluding_percent"].value == D(expected_excluded_percent)
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


WILSON_MUNICIPALITY = ("بلدية الشمال", "al_shamal")
WILSON_STOCK = D(28)
WILSON_CANCELLATIONS = D(6)
# Pre-registered before any run (L-1717; L5c section 1 option B): label -> year.
# Cancellations include flagged months. The 2025 cell is partial: the C2
# calendar ends at 2025-05 and licence_churn refuses any later month.
# custodian/tests/test_pinned_wilson.py pins this exact set; never widen it.
WILSON_PERIOD_GRID = (
    ("2015", "2015"),
    ("2016", "2016"),
    ("2017", "2017"),
    ("2018", "2018"),
    ("2019", "2019"),
    ("2020", "2020"),
    ("2021", "2021"),
    ("2022", "2022"),
    ("2023", "2023"),
    ("2024", "2024"),
    ("2025-partial", "2025"),
)


class WilsonPeriodIdentified(UserWarning):
    """Names the one matching grid label; never a count."""


def wilson_stock_check(active_rows, active_chain, cancelled_rows, cancelled_chain):
    """n is the May 2025 stock, so the year argument does not change it."""
    stock, _, _ = c2_municipal_churn(
        active_rows, active_chain, cancelled_rows, cancelled_chain, *WILSON_MUNICIPALITY
    )
    if stock != WILSON_STOCK:
        raise ValueError("wilson_stock_mismatch")


def wilson_period_label(active_rows, active_chain, cancelled_rows, cancelled_chain):
    rows = (active_rows, active_chain, cancelled_rows, cancelled_chain)
    wilson_stock_check(*rows)
    matches = [
        label
        for label, year in WILSON_PERIOD_GRID
        if c2_municipal_churn(*rows, *WILSON_MUNICIPALITY, year=year)[1]
        == WILSON_CANCELLATIONS
    ]
    if not matches:
        raise ValueError("wilson_period_no_match")
    if len(matches) > 1:
        raise ValueError("wilson_period_ambiguous")
    return matches[0]


# The only ValueError messages a pinned licence case admits, matched exactly.
LICENCE_REASONS = {
    "month outside calendar": "month_outside_calendar",
    **{
        f"{reason}:{source}": reason
        for reason in ("public_cache_missing", "receipt_hash_mismatch")
        for source in ("lic_active", "lic_cancelled")
    },
}
WILSON_REASONS = {
    "wilson_stock_mismatch": "wilson_stock_mismatch",
    "wilson_period_no_match": "wilson_period_no_match",
    "wilson_period_ambiguous": "wilson_period_ambiguous",
    **LICENCE_REASONS,
}
ISIC_REASONS = {
    "spine_pins_differ": "spine_pins_differ",
    "isic_stock_mismatch": "isic_stock_mismatch",
    "isic_ratio_mismatch": "isic_ratio_mismatch",
    "isic_lineage": "isic_lineage",
    **LICENCE_REASONS,
}


def closed_reason(error: Exception, reasons: dict[str, str]) -> str:
    """Map an error to a closed reason; never its own text."""
    if type(error) is SpineError:
        return "spine_refused"
    if type(error) is ValueError:
        return reasons.get(str(error), "source_invalid")
    return "source_invalid"


def wilson_reason(error: Exception) -> str:
    return closed_reason(error, WILSON_REASONS)


def _licence_case(case, check, reasons):
    """Safe failure: the case ID and a fixed reason, never a count."""
    try:
        active_rows, active_chain = pinned("lic_active")
        cancelled_rows, cancelled_chain = pinned("lic_cancelled")
        return check(active_rows, active_chain, cancelled_rows, cancelled_chain)
    except Exception as error:
        reason = closed_reason(error, reasons)
    pytest.fail(f"{case}:{reason}", pytrace=False)


def test_pinned_c2_wilson_stock():
    _licence_case("C2-WILSON-STOCK", wilson_stock_check, WILSON_REASONS)


def test_pinned_c2_wilson_period():
    label = _licence_case("C2-WILSON-PERIOD", wilson_period_label, WILSON_REASONS)
    warnings.warn(f"C2-WILSON-PERIOD:{label}", WilsonPeriodIdentified, stacklevel=1)


def c2_class_members(isic_class: str) -> tuple[str, ...]:
    """Build the spine from the committed review files and take one class.

    The spine is built exactly as the S2-T04 triage builds it, and the two
    licence feeds it reads must be the same snapshots the method pins name.
    """
    selected = reviewed_selections(_cache.CACHE)
    for key in ("lic_active", "lic_cancelled"):
        if selected.get(key) != _cache._pin(key):
            raise ValueError("spine_pins_differ")
    return committed_class_members(_cache.CACHE, isic_class, selections=selected)


def isic_5610_check(active_rows, active_chain, cancelled_rows, cancelled_chain):
    members = set(c2_class_members("5610"))
    class_cancelled = [
        row for row in cancelled_rows if row["rmz_lnsht_ltjry"] in members
    ]
    _, dated, undated, national_months = c2_national_totals(
        cancelled_rows, cancelled_chain
    )
    class_counts, _, _, _ = c2_national_totals(class_cancelled, cancelled_chain)
    window = set(
        f"{year}-{month:02}" for year in (2022, 2023, 2024) for month in range(1, 13)
    )
    class_months = {
        period: reading(value, "count", period, cancelled_chain)
        for period, value in class_counts.items()
        if period in window
    }
    stock = sum(
        (
            D(str(row["dd_lrkhs_lnsht"]))
            for row in active_rows
            if row["rmz_lnsht_ltjry"] in members
        ),
        D(0),
    )
    result = licence_churn(
        reading(stock, "count", "2025-05", active_chain),
        class_months,
        national_months,
        C2_CALENDAR,
        reading(dated + undated, "count", "2025-05", cancelled_chain),
        reading(dated, "count", "2025-05", cancelled_chain),
    )
    if result["active_count"].value != D(7878):
        raise ValueError("isic_stock_mismatch")
    ratio = result["including_ratio"]
    if ratio.exact_unrounded * 7878 != 2510 or ratio.value != D("0.32"):
        raise ValueError("isic_ratio_mismatch")
    if not {"lic_active", "lic_cancelled"} <= {
        chain.lineage_ref for chain in ratio.sources
    }:
        raise ValueError("isic_lineage")


def test_pinned_c2_isic_5610():
    _licence_case("C2-ISIC-5610", isic_5610_check, ISIC_REASONS)


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
