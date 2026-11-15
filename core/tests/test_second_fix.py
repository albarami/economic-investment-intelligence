"""Second-pass regressions; invented arithmetic and fixture source chains."""

from dataclasses import replace
from decimal import Decimal as D
from fractions import Fraction

import pytest
from method_rows import chain, energy, measure
from test_public_series_calc import cell

from eii_core.calc.facts import (
    NoData,
    RegistrySource,
    compare_public_facts,
    emit,
    least_real,
)
from eii_core.calc.public_methods import licence_density, zone_momentum
from eii_core.calc.public_series import decomposition, rounded


def test_falling_mean_signed_share_and_periods():
    result = decomposition({"a": cell(1, 20, "2020")}, {"a": cell(1, 10, "2025")})
    assert result["change"].value == D(-10)
    assert result["within"].value == D(-10)
    assert result["mix"].value == D(0)
    assert result["mix_share_percent"].value == D("0.0")
    assert result["mean_before"].period == "2020"
    for key in (
        "change",
        "within",
        "mix",
        "mix_share_percent",
        "change_percent",
        "fixed_composition_change",
        "fixed_composition_percent",
    ):
        assert result[key].base_period == "2020"
        assert result[key].period == "2025"


def test_comparison_uses_exact_densities():
    before = licence_density(
        measure(149, period="2025-01"), measure(100000, period="2025-01")
    )
    after = licence_density(
        measure(151, period="2025-02"), measure(100000, period="2025-02")
    )
    assert before.value == after.value == D(15)
    result = compare_public_facts(before, after)
    assert result.direction.value == "higher"
    assert result.difference_unrounded == D("0.2")
    assert result.ratio.value == D("1.01")
    assert str(result.difference.value) == "0"
    assert before.exact_unrounded == Fraction(149, 10)


def test_emit_refuses_unrelated_metadata():
    kwargs = dict(
        unit="count",
        places=0,
        metric_key="m",
        release_id="r",
        geography="municipality:invented",
        geography_kind="public",
        period="2025-05",
        inputs=(measure(1),),
    )
    for changed in ({"period": "1999"}, {"geography": "zone:elsewhere"}):
        with pytest.raises(ValueError, match="mismatch"):
            emit(D(1), **(kwargs | changed))


def test_receipt_chain_is_required_and_date_is_canonical():
    pending = RegistrySource(
        "fixture", "fixture", "fixture", "fixture", "https://example.org"
    )
    with pytest.raises(ValueError, match="source"):
        replace(measure(1), sources=(pending,))
    with pytest.raises(ValueError, match="retrieval"):
        replace(chain(), retrieved="2026" + "1114")
    with pytest.raises(ValueError):
        replace(chain(), retrieved="2026-02-30")
    with pytest.raises(ValueError):
        replace(measure(1), geography_kind=" ")
    with pytest.raises(ValueError):
        replace(measure(1), sources=("bad",))
    with pytest.raises(ValueError):
        replace(measure(1), input_class="user_input")
    assert least_real(("public", "user_input")) == "public"


def test_negative_half_rounding_and_unknown_reason():
    assert rounded(D("-2.5"), 0) == "-3"
    assert rounded(D("-0.125"), 2) == "-0.13"
    with pytest.raises(ValueError, match="unknown"):
        NoData("unknown_key")


def test_card_floor_cannot_be_overridden():
    with pytest.raises(ValueError, match="baseline"):
        zone_momentum(
            [],
            energy("national", 2021, 1),
            energy("national", 2025, 2),
            minimum_baseline=D(5000000),
        )


def shown(number="120", period="2025-01", **changes):
    unit = changes.get("unit", "count")
    places = 1 if unit == "percent" else 0
    result = emit(
        D(number),
        unit="percent" if unit == "percent" else "count",
        places=places,
        metric_key="m",
        release_id="r",
        geography="municipality:invented_muni",
        geography_kind="public",
        period=period,
        inputs=(measure(number, period=period),),
    )
    return replace(result, **changes)


def held(period="2025-01", **changes):
    from eii_core.calc.facts import WithheldInput

    return WithheldInput(
        **(
            dict(
                metric_key="m",
                release_id="r",
                geography="municipality:invented_muni",
                geography_kind="public",
                period=period,
                unit="count",
                reason="earlier",
                sources=(chain("before"),),
            )
            | changes
        )
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"metric_key": "other"},
        {"release_id": "other"},
        {"unit": "qar"},
        {"period": "2025-04"},
        {"input_classes": ("synthetic",)},
        {"input_classes": ("public", "user_input"), "evidence_status": "inferred"},
    ],
)
def test_withheld_compatibility_precedes_suppression(changes):
    with pytest.raises(ValueError):
        compare_public_facts(held(), replace(shown("150", "2025-02"), **changes))


def test_withheld_and_missing_keep_all_metadata_and_chains():
    result = compare_public_facts(
        held(), held("2025-02", reason="later", sources=(chain("after"),))
    )
    assert result.direction.reasons == ("earlier", "later")
    assert result.sources == (chain("before"), chain("after"))
    assert (result.before_period, result.after_period) == ("2025-01", "2025-02")
    assert result.before_geography_kind == result.after_geography_kind == "public"
    missing = compare_public_facts(None, shown())
    assert missing.after_geography_kind == "public"
    assert missing.sources == (chain(),)
    with pytest.raises(ValueError):
        compare_public_facts(None, None)
    with pytest.raises(ValueError):
        held(sources=("bad",))


@pytest.mark.parametrize(
    "left,right,expected",
    [
        ("B01", "B02", "higher"),
        ("B12", "B09", "lower"),
        ("B01..B03", "B01..B03", "equal"),
        ("B01..B03", "B02", None),
    ],
)
def test_closed_band_direction_without_numeric_fields(left, right, expected):
    result = compare_public_facts(
        shown(unit="wage_band", value=left),
        shown(period="2025-02", unit="wage_band", value=right),
    )
    assert not hasattr(result, "difference")
    assert not hasattr(result, "ratio")
    if expected is None:
        assert result.direction == NoData("not_coverable")
    else:
        assert result.direction.value == expected


@pytest.mark.parametrize("value", ["b9", "anything", "B00", "B13", "B03..B01"])
def test_unknown_band_refused(value):
    with pytest.raises(ValueError):
        shown(unit="wage_band", value=value)


def test_card_metadata_plants_and_window():
    from method_rows import trade

    from eii_core.calc.public_methods import supplier_metrics

    before = {"a": cell(1, 10, "2020")}
    with pytest.raises(ValueError, match="period"):
        decomposition(before, before)
    months = tuple(f"2025-{i:02}" for i in range(1, 13))
    row = trade("p", "o1", months[0], 10, 2)
    with pytest.raises(ValueError, match="measure"):
        supplier_metrics(
            [replace(row, weight_row=replace(row.weight_row, value=D(3)))],
            ["p"],
            months,
            months,
            reviewed=True,
        )
    result = supplier_metrics(
        [row, trade("p", "o2", months[5], 20, 4)], ["p"], months, months, reviewed=True
    )
    for fact in (
        result["total_value"],
        result["hhi"],
        result["origins"]["o1"]["share_percent"],
    ):
        assert fact.period == "2025-01..2025-12"
        assert fact.geography == "national"
        assert fact.geography_kind == "national"
    with pytest.raises(ValueError, match="negative"):
        supplier_metrics(
            [trade("p", "o1", months[0], -5, 1), trade("p", "o2", months[0], 5, 1)],
            ["p"],
            months,
            months,
            reviewed=True,
        )
    rows = [energy("z", 2021, 1000000), energy("z", 2025, 2000000)]
    with pytest.raises(ValueError, match="period"):
        zone_momentum(
            [
                replace(rows[0], reading=replace(rows[0].reading, period="2020")),
                rows[1],
            ],
            energy("national", 2021, 1),
            energy("national", 2025, 2),
        )
    with pytest.raises(ValueError, match="2021"):
        zone_momentum(rows, energy("national", 2021, 1), energy("national", 2026, 2))
    momentum = zone_momentum(
        rows, energy("national", 2021, 1), energy("national", 2025, 2)
    )
    for fact in (
        momentum["national_ratio"],
        momentum["zones"]["z"]["ratio"],
        momentum["zones"]["z"]["relative"],
    ):
        assert fact.period == "2025"
        assert fact.base_period == "2021"


def test_comparison_all_three_fact_metadata_and_places():
    result = compare_public_facts(
        shown(evidence_status="inferred"),
        shown("150", "2025-02", sources=(chain("other"),)),
    )
    for fact in (result.difference, result.ratio, result.direction):
        assert fact.evidence_status == "inferred"
        assert fact.base_period == "2025-01"
        assert fact.period == "2025-02"
        assert fact.base_geography == fact.geography == "municipality:invented_muni"
        assert fact.base_geography_kind == fact.geography_kind == "public"
        assert fact.sources == (chain(), chain("other"))
    assert str(result.difference.value) == "30"
    percent = compare_public_facts(
        shown("12.3", unit="percent"), shown("15.6", "2025-02", unit="percent")
    )
    assert str(percent.difference.value) == "3.3"


def test_identity_guard_has_a_planted_broken_component(monkeypatch):
    from eii_core.calc import public_series

    # Only alter the later component; the guard must detect even a small residual.
    calls = iter([(D(1), D(10)), (D(1), D("20.001"))])
    monkeypatch.setattr(public_series, "weighted_mean", lambda groups: next(calls))
    with pytest.raises(ValueError, match=r"within \+ mix != change"):
        public_series._kitagawa({"a": (D(1), D(10))}, {"a": (D(1), D(20))})


def test_geography_schema_and_national_lq():
    from eii_core.calc.facts import require_aligned
    from eii_core.calc.public_methods import location_quotient

    for kind in ("", " ", "zone", "unknown"):
        with pytest.raises(ValueError, match="geography"):
            replace(measure(1), geography_kind=kind)
    with pytest.raises(ValueError, match="geography"):
        replace(measure(1), geography="national")
    with pytest.raises(ValueError, match="geography"):
        require_aligned((measure(1), measure(1, geography="national", kind="national")))
    with pytest.raises(ValueError, match="geography"):
        location_quotient(measure(10), measure(100), measure(10), measure(1000))


def test_churn_national_lineage_no_denominator_and_intervals():
    from test_public_methods import calendar

    from eii_core.calc.public_methods import licence_churn

    national = measure(
        10,
        period="2025-01",
        geography="national",
        kind="national",
        input_class="simulated",
        source=chain("national"),
    )
    result = licence_churn(
        measure(10),
        {"2025-01": measure(10, period="2025-01")},
        {"2025-01": national},
        calendar(),
        measure(10, geography="national", kind="national"),
        measure(10, geography="national", kind="national"),
    )
    assert result["bulk_share_percent"].provenance == "simulated"
    assert result["bulk_share_percent"].sources == (chain(), chain("national"))
    assert tuple(f.value for f in result["including_interval"]) == (
        D("0.722"),
        D("1.000"),
    )
    assert result["including_interval_unrounded"] is not None
    empty = licence_churn(
        measure(10),
        {},
        {},
        calendar(),
        measure(0, geography="national", kind="national"),
        measure(0, geography="national", kind="national"),
    )
    assert empty["bulk_share_percent"] == NoData("no_denominator")


def test_typed_results_only():
    from method_rows import trade
    from test_public_methods import calendar
    from test_sector_economics import inputs

    from eii_core.calc.facts import CalculationFact, Suppressed
    from eii_core.calc.public_methods import (
        coverage_share,
        licence_churn,
        location_quotient,
        supplier_metrics,
    )
    from eii_core.calc.sector_economics import sector_norms

    months = tuple(f"2025-{i:02}" for i in range(1, 13))
    results = [
        licence_density(measure(1), measure(100)),
        location_quotient(
            measure(10),
            measure(100),
            measure(10, geography="national", kind="national"),
            measure(1000, geography="national", kind="national"),
        ),
        licence_churn(
            measure(10),
            {},
            {},
            calendar(),
            measure(1, geography="national", kind="national"),
            measure(1, geography="national", kind="national"),
        ),
        decomposition({"a": cell(1, 10, "2020")}, {"a": cell(1, 20, "2025")}),
        sector_norms(**inputs()[0]),
        coverage_share(measure(3), measure(4)),
        supplier_metrics(
            [trade("p", "o", months[0], 10, 2)], ["p"], months, months, reviewed=True
        ),
        zone_momentum(
            [
                energy("z", 2021, 1000000),
                energy("z", 2025, 2000000),
                energy("z_zero", 2021, 0),
                energy("z_zero", 2025, 500),
            ],
            energy("national", 2021, 1),
            energy("national", 2025, 2),
        ),
    ]

    def walk(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if not key.endswith("_unrounded"):
                    walk(item)
        elif isinstance(value, (tuple, list)):
            for item in value:
                walk(item)
        else:
            assert isinstance(value, (CalculationFact, NoData, Suppressed)), value

    for result in results:
        walk(result)


def test_reason_keys_match_document():
    import re
    from pathlib import Path

    from eii_core.calc.facts import PACK_NO_DATA_REASONS

    document = (Path(__file__).parents[2] / "docs/03_DATA_CONTRACTS.md").read_text()
    row = next(line for line in document.splitlines() if line.startswith("| DAT-90 |"))
    clause = row.split("which may carry a reason key (")[1].split("). Non-suppressed")[
        0
    ]
    keys = set(re.findall(r"`([a-z_]+)`", clause))
    # These additional reasons are defined by the method cards, not DAT-90.
    assert PACK_NO_DATA_REASONS == keys | {
        "coverage_by_workplace_not_published",
        "cells_differ_between_years",
        "no_zoning_cover",
    }


def test_populated_groups_in_published_fixture():
    import json

    from test_public_series_calc import FIXTURE, _pay

    groups = json.loads(FIXTURE.read_text())["published"]["C3"]["groups"]
    result = decomposition(
        _pay(groups, "workers_before", "wage_before", "2020"),
        _pay(groups, "workers_after", "wage_after", "2025"),
    )
    assert result["populated_groups"].value == D(17)


def test_zero_prior_total_is_no_data():
    from method_rows import trade

    from eii_core.calc.public_methods import supplier_metrics

    months = tuple(f"2025-{i:02}" for i in range(1, 13))
    prior = tuple(f"2024-{i:02}" for i in range(1, 13))
    result = supplier_metrics(
        [trade("p", "o", months[0], 10, 2)],
        ["p"],
        months,
        (*prior, *months),
        reviewed=True,
        prior_rows=[trade("p", "o", prior[0], 0, 2)],
        prior_months=prior,
    )
    assert result["trend"] == NoData("no_denominator")


@pytest.mark.parametrize(
    "card",
    ["density", "lq", "churn", "pay", "sector", "supplier", "coverage", "energy"],
)
def test_every_card_mixed_inputs_and_joined_chains(card):
    from method_rows import trade
    from test_public_methods import calendar
    from test_sector_economics import inputs

    from eii_core.calc.facts import CalculationFact
    from eii_core.calc.public_methods import (
        coverage_share,
        licence_churn,
        location_quotient,
        supplier_metrics,
    )
    from eii_core.calc.sector_economics import sector_norms

    def weaker(row):
        return replace(row, input_class="simulated", sources=(chain("other"),))

    if card == "density":
        result = licence_density(measure(1), weaker(measure(100)))
    elif card == "lq":
        result = location_quotient(
            measure(10),
            measure(100),
            measure(10, geography="national", kind="national"),
            weaker(measure(1000, geography="national", kind="national")),
        )
    elif card == "churn":
        result = licence_churn(
            measure(10),
            {},
            {},
            calendar(),
            measure(1, geography="national", kind="national"),
            weaker(measure(1, geography="national", kind="national")),
        )
    elif card == "pay":
        result = decomposition(
            {"a": cell(1, 10, "2020")},
            {"a": (cell(1, 20, "2025")[0], weaker(cell(1, 20, "2025")[1]))},
        )
    elif card == "sector":
        values = inputs()[0]
        values["goods_percent"] = weaker(values["goods_percent"])
        result = sector_norms(**values)
    elif card == "supplier":
        months = tuple(f"2025-{i:02}" for i in range(1, 13))
        row = trade("p", "o", months[0], 10, 2)
        result = supplier_metrics(
            [replace(row, weight_row=weaker(row.weight_row))],
            ["p"],
            months,
            months,
            reviewed=True,
        )
    elif card == "coverage":
        result = coverage_share(measure(3), weaker(measure(4)))
    else:
        row = energy("z", 2025, 2000000)
        result = zone_momentum(
            [energy("z", 2021, 1000000), replace(row, reading=weaker(row.reading))],
            energy("national", 2021, 1),
            energy("national", 2025, 2),
        )
    found = []

    def walk(value):
        if isinstance(value, CalculationFact):
            found.append(value)
        elif isinstance(value, dict):
            for item in value.values():
                walk(item)
        elif isinstance(value, tuple):
            for item in value:
                walk(item)

    walk(result)
    assert found
    for fact in found:
        assert fact.provenance == "simulated", fact.metric_key
        assert set(fact.sources) == {chain(), chain("other")}, fact.metric_key


def test_constructor_fact_count_and_percent_places():
    from test_calculation_facts import fact

    assert (
        str(compare_public_facts(fact(), fact(150, "2025-02")).difference.value) == "30"
    )
    assert (
        str(
            compare_public_facts(
                replace(fact(), unit="percent", value=D("12.3")),
                replace(fact(150, "2025-02"), unit="percent", value=D("15.6")),
            ).difference.value
        )
        == "3.3"
    )


def test_size_bands_and_wilson_endpoints():
    from eii_core.calc.public_methods import wilson

    result = compare_public_facts(
        shown(unit="size_band", value="s01_09..s10_49"),
        shown(period="2025-02", unit="size_band", value="s50_plus"),
    )
    assert result.direction.value == "higher"
    with pytest.raises(ValueError, match="band"):
        shown(unit="size_band", value="s00_49")
    low, high = wilson(0, 10)
    assert low == Fraction(0) and rounded(low, 0) == "0"
    assert rounded(high, 3) == "0.278"
    low, high = wilson(10, 10)
    assert rounded(low, 3) == "0.722"
    assert high == D(1)


def test_band_changes_sort_after_numeric_changes():
    from eii_core.calc.facts import order_changes

    band = compare_public_facts(
        shown(unit="wage_band", value="B01"),
        shown(period="2025-02", unit="wage_band", value="B02"),
    )
    numeric = compare_public_facts(shown(), shown("150", "2025-02"))
    assert order_changes([band, numeric]) == (numeric, band)
