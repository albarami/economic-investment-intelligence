"""INVENTED child-run proofs for the remaining pinned method cases."""

import re
from decimal import Decimal as D
from fractions import Fraction
from types import SimpleNamespace

import pytest
from custodian.data_tests import test_pinned_methods as methods
from custodian.tests.test_pinned_wilson import (
    CHILD,
    ONE_MATCH,
    SENTINEL,
    SHAMAL,
    active_rows,
    cancelled_rows,
    summary,
)
from custodian.tests.test_restricted_expectation_guards import child_run
from hypothesis import given
from hypothesis import strategies as st

from eii_core.calc.facts import NoData, SourceChain
from eii_custodian.publicdata.review.activity import SpineError

CHAIN = SourceChain(
    "invented_source",
    "invented_table",
    "invented_method",
    "invented-v1",
    "INVENTED publisher",
    "INVENTED dataset",
    "https://example.invalid",
    "CC0-1.0",
    "2026-01-01",
    "a" * 64,
)
C3_OCC_EXPECTED = {
    "mean_before": "10084",
    "mean_after": "11855",
    "change": "1771",
    "within": "38",
    "mix": "1733",
    "mix_share_percent": "97.8",
    "change_percent": "17.6",
    "fixed_composition_percent": "1.0",
}
C3_ACT_EXPECTED = {"change": "673", "mix": "572"}
C5_HEADINGS = (
    ("1902", "Italy", "8.69"),
    ("1902", "Saudi Arabia", "11.45"),
    ("0406", "Italy", "40.61"),
    ("0406", "Denmark", "26.06"),
    ("1509", "Italy", "30.60"),
    ("1509", "Lebanon", "19.26"),
)
CASE_SOURCES = {
    "C1": "lic_active",
    "C3": "wage_occ",
    "C4": "sec_hr_ind",
    "C5": "cus_imp_2025",
    "C9": "util_elec",
    "C2-NATIONAL": "lic_cancelled",
    "C2-MUNICIPAL": "lic_active",
}
CASE_TESTS = {
    "C1": "test_pinned_c1",
    "C3": "test_pinned_c3",
    "C4": "test_pinned_c4",
    "C5": "test_pinned_c5_heading_checks_only",
    "C9": "test_pinned_c9",
    "C2-NATIONAL": "test_pinned_c2_national_cancellations",
    "C2-MUNICIPAL": "test_pinned_c2_municipal_restaurants",
}
CASE_REASONS = {
    "C1": (
        "municipality_missing",
        "population_indicator_unreviewed",
        "population_duplicate",
        "population_missing",
        "count_mismatch",
        "density_mismatch",
        "lq_mismatch",
    ),
    "C3": ("duplicate_wage_group", "decomposition_mismatch", "lineage"),
    "C4": ("industry_row", "component_label", "norms_mismatch", "range_mismatch"),
    "C5": ("total_mismatch", "unit_value_mismatch"),
    "C9": (
        "momentum_mismatch",
        "order_mismatch",
        "zero_zone_missing",
        "zero_zone_mismatch",
    ),
    "C2-NATIONAL": (
        "totals_mismatch",
        "bulk_month_mismatch",
        "bulk_share_mismatch",
        "bulk_order_mismatch",
    ),
    "C2-MUNICIPAL": (
        "cancelled_mismatch",
        "stock_mismatch",
        "including_mismatch",
        "excluding_mismatch",
        "geography_mismatch",
    ),
}
SPLIT_PLANTS = {
    ("C9", "momentum_mismatch"): (
        "momentum_national",
        "momentum_zone69",
        "momentum_ranked",
    ),
    ("C9", "zero_zone_mismatch"): (
        "zero_zone_ratio",
        "zero_zone_ranked_ratio",
        "zero_zone_relative",
        "zero_zone_ratio_unrounded",
        "zero_zone_ranked_unrounded",
        "zero_zone_order",
    ),
    ("C2-NATIONAL", "totals_mismatch"): (
        "totals_dated",
        "totals_undated",
        "totals_result_undated",
    ),
    ("C2-NATIONAL", "bulk_month_mismatch"): tuple(
        f"bulk_month_{part}_{month.replace('-', '_')}"
        for month in ("2020-07", "2022-06", "2024-09")
        for part in ("missing", "count")
    ),
    ("C2-NATIONAL", "bulk_share_mismatch"): (
        "bulk_share_named",
        "bulk_share_result",
    ),
    ("C2-MUNICIPAL", "stock_mismatch"): (
        "stock_return",
        "stock_active_count",
    ),
    ("C2-MUNICIPAL", "excluding_mismatch"): (
        "excluding_exact",
        "excluding_value",
    ),
    ("C2-MUNICIPAL", "geography_mismatch"): (
        "geography_local",
        "geography_national",
    ),
}
NEGATIVE_CASES = [
    (case, kind, reason)
    for case, kinds in CASE_REASONS.items()
    for kind in kinds
    for reason in (kind,)
    if (case, kind) not in SPLIT_PLANTS
    and (case, kind) != ("C5", "unit_value_mismatch")
]
NEGATIVE_CASES += [
    (case, plant, reason)
    for (case, reason), plants in SPLIT_PLANTS.items()
    for plant in plants
]
NEGATIVE_CASES += [
    ("C5", f"unit_value_mismatch:{heading}:{origin}", "unit_value_mismatch")
    for heading, origin, _ in C5_HEADINGS
]
NEGATIVE_CASES += [
    (case, kind, kind)
    for case in CASE_TESTS
    for kind in ("public_cache_missing", "receipt_hash_mismatch")
]
NEGATIVE_CASES += [(case, "source_invalid", "source_invalid") for case in CASE_TESTS]
NEGATIVE_CASES += [(case, "spine_refused", "spine_refused") for case in CASE_TESTS]
NEGATIVE_CASES += [
    ("C2-NATIONAL", "month_outside_calendar", "month_outside_calendar"),
    ("C2-MUNICIPAL", "month_outside_calendar", "month_outside_calendar"),
]
NEGATIVE_CASES += [
    ("C2-MUNICIPAL", kind, "source_invalid")
    for kind in (
        "missing_active_municipality",
        "missing_cancelled_municipality",
        "missing_activity",
    )
]


def raiser(error):
    def raise_it(*_args, **_kwargs):
        raise error

    return raise_it


def fact(value, geography="national", kind="national", exact=None):
    return SimpleNamespace(
        value=D(str(value)),
        geography=geography,
        geography_kind=kind,
        exact_unrounded=exact,
    )


def child_text(case, kind, variant="occ"):
    arguments = ""
    if case == "C3":
        expected = C3_OCC_EXPECTED if variant == "occ" else C3_ACT_EXPECTED
        source, last = (
            ("wage_occ", "2025") if variant == "occ" else ("wage_act", "2023")
        )
        arguments = f"{source!r}, {last!r}, {expected!r}"
    elif case == "C2-MUNICIPAL":
        arguments = repr(methods.C2_MUNICIPAL_EXAMPLES[0])[1:-1]
    replacement = (
        "from custodian.tests import test_pinned_closed_methods as closed\n"
        f"closed.plant(methods, {case!r}, {kind!r})\n"
        f"case = methods.{CASE_TESTS[case]}\n"
        f"def test_invented():\n    case({arguments})\n"
    )
    return CHILD.replace(
        "methods.pinned = invented.child_pinned({shamal!r}, {parts!r})\n",
        replacement,
    ).replace(
        "from custodian.data_tests.test_pinned_methods import (\n"
        "    test_pinned_c2_wilson_period,\n"
        "    test_pinned_c2_wilson_stock,\n"
        ")\n",
        "",
    )


def run_closed(tmp_path, case, kind, variant="occ"):
    result = child_run(tmp_path, child_text(case, kind, variant))
    return result, result.stdout + result.stderr


def plant_c1(methods_module, kind):
    methods_module.pinned = lambda _source: ([], CHAIN)
    if kind in CASE_REASONS["C1"][:4]:
        methods_module.c1_replay = raiser(ValueError(f"C1:{kind}"))
        return
    counts = {
        "local_all": 13600,
        "national_all": 249622,
        "local_restaurants": 361,
        "national_restaurants": 4782,
        "local_coffee": 173,
        "national_coffee": 1042,
        "local_population": 111282,
        "national_population": 3219982,
    }
    if kind == "count_mismatch":
        counts["local_all"] = SENTINEL
    density = (D(32), D(15))
    if kind == "density_mismatch":
        density = (D(SENTINEL), D(15))
    lq = (D("1.39"), D("3.05"))
    if kind == "lq_mismatch":
        lq = (D(SENTINEL), D("3.05"))
    result = {
        **counts,
        "density": tuple(fact(value) for value in density),
        "lq": tuple(fact(value) for value in lq),
    }
    methods_module.c1_replay = lambda *_args: result


def c3_results(kind, source):
    literals = C3_ACT_EXPECTED if source == "wage_act" else C3_OCC_EXPECTED
    return {
        key: SimpleNamespace(
            value=D(SENTINEL)
            if kind == "decomposition_mismatch" and key == "change"
            else D(literal),
            sources=() if kind == "lineage" else (CHAIN,),
        )
        for key, literal in literals.items()
    }


def plant_c3(methods_module, kind):
    rows = []
    if kind == "duplicate_wage_group":
        rows = [
            {
                "year": 2020,
                "gender": "INVENTED",
                "occupation": "INVENTED",
                "paid_employment_workers": 1,
                "monthly_average_wage_qr": 1,
            }
        ] * 2
    selected = {"source": "wage_occ"}

    def pinned(source):
        selected["source"] = source
        return rows, CHAIN

    methods_module.pinned = pinned
    methods_module.decomposition = lambda *_args: c3_results(kind, selected["source"])


def c4_rows(kind):
    sources = {
        key: [] for key in ("sec_hr_ind", "sec_hr_size", "sec_hr_goods", "sec_hr_serv")
    }
    for year in range(2018, 2023):
        if not (kind == "industry_row" and year == 2020):
            sources["sec_hr_ind"].append(
                {
                    "year": year,
                    "activity_code": "561",
                    "productivity_of_employee_qr": 0,
                    "compensation_of_employees_value_in_1_000_qr": 0,
                    "operating_surplus_value_in_1_000_qr": 0,
                    "percentage_of_intermediate_goods_to_output": 0,
                    "percentage_of_intermediate_services_to_output": 0,
                }
            )
        for label in ("Food Stuff", "Beverages"):
            sources["sec_hr_goods"].append(
                {
                    "year": year,
                    "activity_code": "561",
                    "type_of_commodity": "INVENTED"
                    if kind == "component_label"
                    and year == 2020
                    and label == "Food Stuff"
                    else label,
                    "estimates_of_intermediate_goods_value_value_in_1_000_qr": 0,
                }
            )
        sources["sec_hr_serv"].append(
            {
                "year": year,
                "activity_code": "561",
                "type_of_service": "Rents of Buildings",
                "estimates_of_intermediate_services_value_value_in_1_000_qr": 0,
            }
        )
    return sources


def c4_norms(year, kind):
    later = year != 2022
    values = {
        "food": "29.3" if not later else "28.0",
        "beverages": "5.6",
        "rent": "11.6" if not later else "15.1",
        "compensation_percent": "20.6" if not later else "25.2",
        "surplus_percent": "19.7" if not later else "6.9",
        "goods_percent": "40.6",
        "services_percent": "16.5",
    }
    if kind == "norms_mismatch" and year == 2022:
        values["food"] = str(SENTINEL)
    if kind == "range_mismatch" and year == 2021:
        values["food"] = str(SENTINEL)
    return {key: fact(value) for key, value in values.items()}


def plant_c4(methods_module, kind):
    sources = c4_rows(kind)
    methods_module.pinned = lambda source: (sources[source], CHAIN)
    methods_module.sector_norms = lambda **kwargs: c4_norms(
        int(kwargs["employees"].period), kind
    )


def plant_c5(methods_module, kind):
    methods_module.pinned = lambda _source: ([], CHAIN)
    calls = iter(("total", *C5_HEADINGS))
    planted = (
        tuple(kind.split(":", 2)[1:]) if kind.startswith("unit_value_mismatch:") else ()
    )

    def metrics(*_args, **_kwargs):
        selected = next(calls)
        if selected == "total":
            exact = D(SENTINEL) if kind == "total_mismatch" else D("138530000000")
            return {"total_value": SimpleNamespace(exact_unrounded=exact)}
        heading, origin, expected = selected
        value = SENTINEL if planted == (heading, origin) else expected
        return {"origins": {origin: {"unit_value": fact(value)}}}

    methods_module.supplier_metrics = metrics


def c9_result(kind):
    zones = {
        key: {"ratio": fact(value), "ranked_ratio": fact(ranked)}
        for key, value, ranked in (
            ("2", "0", "6.5"),
            ("72", "0", "5.4"),
            ("29", "0", "4.0"),
            ("69", "3.34", "3.3"),
        )
    }
    zones["0"] = {
        "ratio": NoData("no_denominator"),
        "ranked_ratio": NoData("no_denominator"),
        "relative": NoData("no_denominator"),
        "ratio_unrounded": None,
        "ranked_unrounded": False,
    }
    if kind == "momentum_zone69":
        zones["69"]["ratio"] = fact(SENTINEL)
    if kind == "momentum_ranked":
        zones["72"]["ranked_ratio"] = fact(SENTINEL)
    zero_slot = {
        "zero_zone_ratio": "ratio",
        "zero_zone_ranked_ratio": "ranked_ratio",
        "zero_zone_relative": "relative",
    }.get(kind)
    if zero_slot is not None:
        zones["0"][zero_slot] = fact(SENTINEL)
    if kind == "zero_zone_ratio_unrounded":
        zones["0"]["ratio_unrounded"] = D(SENTINEL)
    if kind == "zero_zone_ranked_unrounded":
        zones["0"]["ranked_unrounded"] = True
    order = ("2", "72", "29", "69")
    if kind == "order_mismatch":
        order = (str(SENTINEL), "72", "29", "69")
    if kind == "zero_zone_order":
        order = (*order, "0")
    return {
        "national_ratio": fact(SENTINEL if kind == "momentum_national" else "1.34"),
        "zones": zones,
        "order_unrounded": order,
    }


def plant_c9(methods_module, kind):
    rows = (
        []
        if kind == "zero_zone_missing"
        else [
            {"year": 2021, "zone_number": 0, "value": 0},
            {"year": 2025, "zone_number": 0, "value": 0},
        ]
    )
    methods_module.pinned = lambda _source: (rows, CHAIN)
    methods_module.zone_momentum = lambda *_args: c9_result(kind)


def plant_c2_national(methods_module, kind):
    methods_module.pinned = lambda _source: ([], CHAIN)
    counts = {"2020-07": D(40791), "2022-06": D(14212), "2024-09": D(11232)}
    dated = D(SENTINEL) if kind == "totals_dated" else D(153669)
    undated = D(SENTINEL) if kind == "totals_undated" else D(7386)
    methods_module.c2_national_totals = lambda *_args: (counts, dated, undated, {})
    if kind == "month_outside_calendar":
        methods_module.licence_churn = raiser(ValueError("month outside calendar"))
        return
    bulk = list(methods.EXPECTED_C2_BULK_MONTHS)
    if kind.startswith("bulk_month_"):
        part, year, month = kind.removeprefix("bulk_month_").rsplit("_", 2)
        period = f"{year}-{month}"
        if part == "missing":
            bulk.remove(period)
        else:
            counts[period] = D(SENTINEL)
    if kind == "bulk_order_mismatch":
        bulk.reverse()
    if kind == "bulk_share_named":
        methods_module.rounded = lambda *_args: str(SENTINEL)
    result_undated = SENTINEL if kind == "totals_result_undated" else 7386
    methods_module.licence_churn = lambda *_args: {
        "undated_count": fact(result_undated),
        "bulk_share_percent": fact(SENTINEL if kind == "bulk_share_result" else "54.3"),
        "bulk_months_unrounded": tuple(bulk),
    }


def c2_municipal_result(kind):
    _, slug, active, _, including, excluded, excluding = methods.C2_MUNICIPAL_EXAMPLES[
        0
    ]
    geography = f"municipality:{slug}"

    def local(value, exact=None):
        return fact(
            value,
            "national" if kind == "geography_local" else geography,
            "national" if kind == "geography_local" else "public",
            exact,
        )

    national_geography = geography if kind == "geography_national" else "national"
    national_kind = "public" if kind == "geography_national" else "national"
    excluding_exact = (
        Fraction(SENTINEL)
        if kind == "excluding_exact"
        else Fraction(excluded * 100, active)
    )
    return {
        "active_count": local(SENTINEL if kind == "stock_active_count" else active),
        "including_ratio": local("0"),
        "including_percent": local(
            SENTINEL if kind == "including_mismatch" else including
        ),
        "excluding_percent": local(
            SENTINEL if kind == "excluding_value" else excluding,
            excluding_exact,
        ),
        "including_interval": (),
        "excluding_interval": (),
        "undated_count": fact(0, national_geography, national_kind),
        "bulk_share_percent": fact(0, national_geography, national_kind),
    }


def plant_c2_municipal(methods_module, kind):
    methods_module.pinned = lambda _source: ([], CHAIN)
    if kind.startswith("missing_"):
        active = active_rows()
        cancelled = cancelled_rows(ONE_MATCH)
        target = methods.C2_MUNICIPAL_EXAMPLES[0][0]
        for row in (*active, *cancelled):
            if row["lbldy"] == SHAMAL:
                row["lbldy"] = target
        if kind == "missing_active_municipality":
            active = [row for row in active if row["lbldy"] != target]
        elif kind == "missing_cancelled_municipality":
            cancelled = [row for row in cancelled if row["lbldy"] != target]
        else:
            for row in active:
                if row["lbldy"] == target:
                    row["rmz_lnsht_ltjry"] = "5630112"
        by_source = {
            "lic_active": (active, CHAIN),
            "lic_cancelled": (cancelled, CHAIN),
        }
        methods_module.pinned = by_source.__getitem__
        return
    if kind == "month_outside_calendar":
        methods_module.c2_municipal_churn = raiser(ValueError("month outside calendar"))
        return
    _, _, active, cancelled, _, _, _ = methods.C2_MUNICIPAL_EXAMPLES[0]
    stock = SENTINEL if kind == "stock_return" else active
    total = SENTINEL if kind == "cancelled_mismatch" else cancelled
    methods_module.c2_municipal_churn = lambda *_args: (
        D(stock),
        D(total),
        c2_municipal_result(kind),
    )


def plant(methods_module, case, kind):
    """Install one invented passing setup or one isolated closed-reason fault."""
    if kind == "source_invalid":
        methods_module.pinned = raiser(KeyError(str(SENTINEL)))
        return
    if kind == "spine_refused":
        methods_module.pinned = raiser(SpineError(f"INVENTED {SENTINEL}"))
        return
    if kind in ("public_cache_missing", "receipt_hash_mismatch"):
        methods_module.pinned = raiser(ValueError(f"{kind}:{CASE_SOURCES[case]}"))
        return
    {
        "C1": plant_c1,
        "C3": plant_c3,
        "C4": plant_c4,
        "C5": plant_c5,
        "C9": plant_c9,
        "C2-NATIONAL": plant_c2_national,
        "C2-MUNICIPAL": plant_c2_municipal,
    }[case](methods_module, kind)


@pytest.mark.parametrize("case", sorted(CASE_TESTS))
def test_pinned_case_passes_on_invented_setup(tmp_path, case):
    passing, output = run_closed(tmp_path, case, "pass")
    assert passing.returncode == 0, output


def test_pinned_c3_activity_case_passes_on_invented_setup(tmp_path):
    passing, output = run_closed(tmp_path, "C3", "pass", variant="act")
    assert passing.returncode == 0, output


@pytest.mark.parametrize(("case", "kind", "reason"), NEGATIVE_CASES)
def test_pinned_case_prints_only_case_and_closed_reason(tmp_path, case, kind, reason):
    failing, output = run_closed(tmp_path, case, kind)
    assert failing.returncode == 1, "child_not_failed"
    assert str(SENTINEL) not in output, "sentinel_leaked"
    assert summary(failing) == {f"{case}:{reason}"}


@pytest.mark.parametrize(
    "map_name",
    (
        "C1_REASONS",
        "C3_REASONS",
        "C4_REASONS",
        "C5_REASONS",
        "C9_REASONS",
        "C2_NATIONAL_REASONS",
        "C2_MUNICIPAL_REASONS",
    ),
)
@given(
    st.data(),
    st.sampled_from([ValueError, KeyError, TypeError, SpineError, AssertionError]),
)
def test_each_new_reason_map_is_closed(map_name, data, kind):
    reasons = getattr(methods, map_name)
    message = data.draw(st.one_of(st.sampled_from(sorted(reasons)), st.text()))
    reason = methods.closed_reason(kind(message), reasons)
    admitted = reasons.get(message)
    if kind is SpineError:
        expected = "spine_refused"
    elif kind is ValueError and admitted:
        expected = admitted
    else:
        expected = "source_invalid"
    assert reason == expected
    assert re.fullmatch(r"[a-z_]+", reason)
