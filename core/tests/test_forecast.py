"""C30 contract plants on invented histories and invented source chains."""

import json
import os
import subprocess
import sys
from copy import deepcopy
from dataclasses import replace
from decimal import ROUND_DOWN, Inexact, localcontext
from decimal import Decimal as D
from pathlib import Path

import pytest
from test_decimal_context_contract import representation

import eii_core.calc as calc
from eii_core.calc import forecast as module
from eii_core.calc import forecast_series
from eii_core.calc.facts import CalculationFact, NoData, SourceChain, Suppressed
from eii_core.calc.forecast import (
    ForecastNotOffered,
    ForecastPoint,
    ForecastSeries,
    HomeFamily,
    ReleaseAdmission,
    period_step,
)
from eii_core.calc.forecast_list import definition
from eii_core.calc.forecast_models import predict, smoothing


def chain(table="pub_property_sale"):
    return SourceChain(
        "invented",
        table,
        "invented_source_method",
        "v1",
        "Invented publisher",
        "Invented fixture",
        "https://example.test/fixture",
        "CC0",
        "2025-01-01",
        "a" * 64,
    )


def evidence(table):
    return ReleaseAdmission(
        release_id="invented",
        table=table,
        table_sha256="b" * 64,
        schema_sha256="c" * 64,
        grain=module.TABLE_GRAINS[table],
        source_hashes=(("invented", "a" * 64),),
        window_period="2020-01/2021-11"
        if table in ("worker_pay", "resident_pay", "month_change", "occupation_pay")
        else "",
        window_key="e" * 64
        if table in ("worker_pay", "resident_pay", "month_change", "occupation_pay")
        else "",
    )


def test_property_fact_unit_and_unknown_unit():
    fields = dict(
        value=D("15.25"),
        metric_key="forecast_value",
        release_id="invented",
        geography="district:invented",
        geography_kind="public",
        period="2026",
        input_classes=("public",),
        sources=(chain(),),
        evidence_status="inferred",
    )
    assert CalculationFact(unit="qar_per_m2", **fields).unit == "qar_per_m2"
    with pytest.raises(ValueError, match="unsupported numeric unit"):
        CalculationFact(unit="invented_unit", **fields)


def test_forecast_entry_is_available():

    assert callable(getattr(calc, "forecast_series", None))


def construction(values=(10, 11, 12, 13, 15)):

    return ForecastSeries(
        admission=evidence("pub_building_permits"),
        key="construction_pipeline",
        table="pub_building_permits",
        subject="municipality",
        geography="municipality:invented",
        geography_kind="public",
        level="municipality",
        frequency="year",
        measure="completion_certificates",
        unit="count",
        input_class="public",
        source_geography="municipality:invented",
        breakdown=(("type", "invented"),),
        source_breakdown=(("type", "invented"),),
        sources=(chain("pub_building_permits"),),
        points=tuple(
            ForecastPoint(
                str(2020 + i), D(v), "completion_certificates", "invented", "count"
            )
            for i, v in enumerate(values)
        ),
    )


def test_fractional_count_has_exact_value_and_target_companions():

    result = forecast_series(construction())
    # Drift errors 0, 0, 1; final 15 + (15 - 10) / 4 = 16.25.
    assert result.model == "drift"
    assert result.value.value == D(16)
    assert result.value.places == 0
    assert result.value.exact_unrounded == D("16.25")
    assert result.origin == "2024"
    assert result.target == "2025"
    assert result.qualifiers == {"model": "drift", "horizon": 1}
    assert result.caveats == ("forecast_backtest_range", "permit_not_start")
    for fact in result.facts:
        assert fact.period == result.target
        assert fact.evidence_status == "inferred"
        assert fact.sources[0].method == "invented_source_method"
    assert result.history_deal_counts == ()


def test_admission_and_pre_fit_refusals(monkeypatch):

    def fitted(*args, **kwargs):
        raise AssertionError("must refuse before fitting")

    monkeypatch.setattr(module, "backtest", fitted)
    series = construction()
    for changes in (
        {"key": "unknown"},
        {"key": "establishments_by_area"},
        {"key": "licence_net"},
        {"key": "generated_openings"},
        {"key": "generated_closures"},
        {"table": "pub_licence_issued"},
        {"input_class": "synthetic"},
        {"input_class": "simulated"},
        {"measure": "permits"},
        {"level": "district"},
        {"subject": "area"},
        {"subject": "place_public"},
        {"subject": "register_company"},
        {"subject": "fdi_project"},
        {"subject": "venture"},
        {"reconciliation_open": True},
        {"unit": "qar"},
        {"source_geography": "municipality:other_invented"},
        {"source_breakdown": ()},
        {"sources": (chain("wrong_table"),)},
    ):
        result = module.forecast_series(replace(series, **changes))
        assert type(result) is ForecastNotOffered
        assert result.reason == "forecast_not_offered"


def test_short_distinct_from_decline_and_carried_before_gap(monkeypatch):

    series = construction()
    assert module.forecast_series(replace(series, points=())) == NoData(
        "series_too_short"
    )
    assert module.forecast_series(replace(series, points=series.points[:3])) == NoData(
        "series_too_short"
    )
    earlier = replace(series.points[0], period="2010", carried_forward=True)

    def fitted(*args, **kwargs):
        raise AssertionError("carried window reached fitting")

    monkeypatch.setattr(module, "backtest", fitted)
    assert module.forecast_series(
        replace(series, points=(earlier, *series.points))
    ) == Suppressed("CARRIED_FORWARD")


def test_gap_suffix_keeps_window_identity_and_flags():

    series = construction()
    earlier = replace(series.points[0], period="2010")
    result = forecast_series(replace(series, points=(earlier, *series.points)))
    assert result.history == series.points
    assert result.series.points == (earlier, *series.points)
    assert result.value.release_id == "invented"
    assert forecast_series(
        replace(series, points=(earlier, *series.points[:4]))
    ) == NoData("series_too_short")
    with pytest.raises(ValueError, match="mixed release"):
        replace(series, points=(replace(earlier, release_id="another"), *series.points))


@pytest.mark.parametrize(
    "period,frequency,expected",
    [
        ("2025-12", "month", ("2025-12", "2026-01")),
        ("2025-Q4", "quarter", ("2025-Q4", "2026-Q1")),
        ("2025-Q2", "quarter", ("2025-Q2", "2025-Q3")),
        ("2025", "year", ("2025", "2026")),
        ("2025-12/2026-01", "month", ("2026-01", "2026-02")),
    ],
)
def test_periods(period, frequency, expected):
    assert period_step(period, frequency) == expected


@pytest.mark.parametrize(
    "period,frequency",
    [
        ("UNDATED", "month"),
        ("2025-1", "month"),
        ("2025-00", "month"),
        ("2025-13", "month"),
        ("2025-Q0", "quarter"),
        ("2025-Q5", "quarter"),
        ("0999", "year"),
        ("2025-01", "year"),
        ("2025-01/2025-03", "month"),
        ("2025-01/2025-02/2025-03", "month"),
        ("2025/2026", "year"),
        ("2025", "unknown"),
        ("9999", "year"),
    ],
)
def test_bad_periods(period, frequency):
    with pytest.raises(ValueError):
        period_step(period, frequency)


def test_constructor_order_and_release_ids():
    series = construction()
    for points in (tuple(reversed(series.points)), (series.points[0],) * 2):
        with pytest.raises(ValueError, match="ordered and unique"):
            replace(series, points=points)
    with pytest.raises(ValueError, match="text"):
        replace(series.points[0], release_id="")
    with pytest.raises(ValueError, match="invalid period"):
        replace(series, points=(replace(series.points[0], period="UNDATED"),))


@pytest.mark.parametrize(
    "slot", ["value", "low", "high", "error", "points", "inside", "tested"]
)
def test_each_missing_or_mismatched_companion(slot):
    result = forecast_series(construction())
    fact = getattr(result, slot)
    for changed in (
        None,
        replace(fact, release_id="other"),
        replace(fact, period="2024"),
        replace(fact, geography="municipality:other"),
        replace(fact, evidence_status="observed"),
        replace(fact, metric_key="other"),
        replace(fact, value=D(999)),
    ):
        with pytest.raises(ValueError, match="companion"):
            replace(result, **{slot: changed})


@pytest.mark.parametrize(
    "changes",
    [
        {"origin": "2023"},
        {"target": "2026"},
        {"method": ""},
        {"version": "other"},
        {"series_key": "other"},
        {"measure": "other"},
        {"table": "other"},
        {"sources": ()},
        {"breakdown": ()},
        {"history": ()},
        {"families": ("wrong",)},
        {"qualifiers": {"model": "drift", "horizon": 1, "extra": "bad"}},
        {"qualifiers": {"model": "drift", "horizon": True}},
        {"horizon": True},
        {"caveats": ("permit_not_start",)},
        {"caveats": ("forecast_backtest_range",)},
        {
            "caveats": (
                "forecast_backtest_range",
                "permit_not_start",
                "projection_not_forecast",
            )
        },
        {"low_clamped": True},
        {"high_clamped": True},
        {"public_only_ranking": False},
        {"reliability": "standard"},
    ],
)
def test_result_constructor_plants(changes):
    with pytest.raises(ValueError):
        replace(forecast_series(construction()), **changes)


@pytest.mark.parametrize(
    "low,high,marks",
    [
        ("-2", "-1", (True, True)),
        ("-1", "2", (True, False)),
        ("0", "2", (False, False)),
        ("1", "2", (False, False)),
    ],
)
def test_independent_clamps(monkeypatch, low, high, marks):
    baseline = module.forecast_series(construction())
    computation = replace(baseline.computation, low=(D(low),), high=(D(high),))
    monkeypatch.setattr(module, "backtest", lambda *a, **k: computation)
    result = module.forecast_series(construction())
    assert (result.low_clamped, result.high_clamped) == marks
    assert result.low.value == max(D(0), D(low))
    assert result.high.value == max(D(0), D(high))
    assert result.computation.low == (D(low),)
    assert result.computation.high == (D(high),)
    for flag in ("low_clamped", "high_clamped"):
        with pytest.raises(ValueError, match="clamp"):
            replace(result, **{flag: not getattr(result, flag)})
    for slot in ("low", "high"):
        with pytest.raises(ValueError, match="companion"):
            replace(result, **{slot: replace(getattr(result, slot), value=D(-1))})


def test_negative_point_before_rounding_and_exact_zero(monkeypatch):
    baseline = module.forecast_series(construction()).computation
    negative = replace(baseline, forecasts=(D("-0.4"),))
    monkeypatch.setattr(module, "backtest", lambda *a, **k: negative)
    assert module.forecast_series(construction()) == NoData("forecast_below_zero")
    zero = replace(baseline, forecasts=(D(0),), low=(D(0),), high=(D(0),))
    monkeypatch.setattr(module, "backtest", lambda *a, **k: zero)
    assert module.forecast_series(construction()).value.value == 0


def released(key):
    spec = definition(key)
    table = "month_change" if key == "stayer_index" else "worker_pay"
    partition = (
        "wp_all_count"
        if key in ("earner_count", "employment_by_area")
        else "wp_all_money"
    )
    columns = (
        (("wage_bill", "numerator"), ("earner_count", "denominator"))
        if key == "pay_level"
        else ((spec.measures[0], "single"),)
    )
    families = tuple(
        HomeFamily(
            "worker_pay",
            partition,
            "net",
            "cohort" if key == "stayer_index" else "ALL",
            c,
            role,
        )
        for c, role in columns
    )
    points = []
    period = "2020-01"
    for i in range(22 if key == "stayer_index" else 23):
        earlier, later = period_step(period, "month")
        points.append(
            ForecastPoint(
                earlier + "/" + later if key == "stayer_index" else earlier,
                D(100 + i),
                spec.measures[0],
                "invented",
                spec.unit,
            )
        )
        period = later
    return replace(
        construction(),
        admission=replace(evidence(table), feed_names=spec.confirmed_sources),
        window_key="e" * 64,
        window_period="2020-01/2021-11",
        generator="invented_generator",
        generator_version="fixture-v1",
        key=key,
        table=table,
        subject="area",
        geography="national",
        geography_kind="national",
        level="national",
        frequency="month",
        measure=spec.measures[0],
        unit=spec.unit,
        input_class="synthetic",
        source_geography="national",
        sources=(chain(table),),
        points=tuple(points),
        partition=partition,
        protected_table="worker_pay",
        families=families,
        breakdown=(),
        source_breakdown=(),
    )


@pytest.mark.parametrize(
    "key",
    ["pay_level", "earner_count", "wage_bill", "stayer_index", "employment_by_area"],
)
def test_every_released_key_and_wrong_bindings(key):
    series = released(key)
    result = forecast_series(series)
    assert result.value.provenance == "synthetic"
    assert result.origin == period_step(series.points[-1].period, "month")[0]
    assert not result.public_only_ranking
    assert result.caveats == (
        "forecast_backtest_range",
        "synthetic_not_evidence_about_qatar",
        "synthetic_change",
    )
    assert result.families == series.families
    for changes in (
        {"table": "outlet_register"},
        {"input_class": "public"},
        {"level": "district"},
        {"subject": "national"},
        {"families": ()},
        {"partition": "wrong"},
    ):
        assert isinstance(
            forecast_series(replace(series, **changes)), ForecastNotOffered
        )
    for caveat in result.caveats:
        with pytest.raises(ValueError, match="caveats"):
            replace(result, caveats=tuple(c for c in result.caveats if c != caveat))
    with pytest.raises(ValueError, match="ranking"):
        replace(result, public_only_ranking=True)
    with pytest.raises(ValueError, match="target"):
        replace(result, origin="2020-01")


def test_stayer_pair_chain_and_no_finer_level():
    series = released("stayer_index")
    assert isinstance(
        forecast_series(replace(series, level="area")), ForecastNotOffered
    )
    with pytest.raises(ValueError, match="broken stayer pair"):
        replace(series, points=(series.points[0], *series.points[2:]))
    with pytest.raises(ValueError, match="stayer pair required"):
        replace(series, points=(replace(series.points[0], period="2020-01"),))


def property_series():
    return replace(
        construction(),
        admission=evidence("pub_property_sale"),
        key="property_prices",
        table="pub_property_sale",
        subject="district",
        geography="district:invented",
        source_geography="district:invented",
        level="district",
        municipality="municipality:invented",
        measure="median_price_per_m2",
        unit="qar_per_m2",
        sources=(chain(),),
        points=tuple(
            replace(p, measure="median_price_per_m2", unit="qar_per_m2", deal_count=29)
            for p in construction().points
        ),
    )


def test_property_geography_counts_and_categories():
    series = property_series()
    result = forecast_series(series)
    assert result.value.unit == "qar_per_m2"
    assert result.value.places == 2
    assert result.value.geography == "district:invented"
    assert result.series.municipality == "municipality:invented"
    assert result.breakdown == series.source_breakdown
    assert tuple(f.period for f in result.history_deal_counts) == tuple(
        p.period for p in series.points
    )
    assert all(f.value == 29 for f in result.history_deal_counts)
    assert result.reliability == "low_count"
    for changes in (
        {"municipality": ""},
        {"geography": "district:other"},
        {"subject": "area"},
        {"points": tuple(replace(p, deal_count=None) for p in series.points)},
    ):
        assert isinstance(
            forecast_series(replace(series, **changes)), ForecastNotOffered
        )
    with pytest.raises(ValueError, match="deal counts"):
        replace(result, history_deal_counts=())


@pytest.mark.parametrize("split", ["sex", "nationality"])
def test_public_splits_never_move_or_relabel(split):
    original = ((split, "invented_category"),)
    series = replace(construction(), breakdown=original, source_breakdown=original)
    result = forecast_series(series)
    assert result.breakdown == original
    assert not result.public_only_ranking
    assert isinstance(
        forecast_series(replace(series, geography="municipality:other")),
        ForecastNotOffered,
    )
    assert isinstance(
        forecast_series(replace(series, breakdown=((split, "changed"),))),
        ForecastNotOffered,
    )
    with pytest.raises(ValueError, match="categories"):
        replace(result, breakdown=((split, "changed"),))


@pytest.mark.parametrize(
    "field",
    [
        "key",
        "table",
        "subject",
        "geography",
        "geography_kind",
        "level",
        "frequency",
        "measure",
        "unit",
        "input_class",
        "source_geography",
        "municipality",
        "partition",
        "protected_table",
    ],
)
def test_exact_series_text(field):
    series = construction()
    subclass = type("PlantedText", (str,), {})
    with pytest.raises(ValueError):
        replace(series, **{field: subclass(getattr(series, field))})


@pytest.mark.parametrize("field", ["period", "measure", "release_id", "unit"])
def test_exact_point_text(field):
    point = construction().points[0]
    subclass = type("PlantedText", (str,), {})
    with pytest.raises(ValueError):
        replace(point, **{field: subclass(getattr(point, field))})


@pytest.mark.parametrize(
    "value",
    [1, True, 1.5, D("NaN"), D("Infinity"), type("PlantedDecimal", (D,), {})(1)],
)
def test_point_numeric_type(value):
    with pytest.raises(ValueError):
        replace(construction().points[0], value=value)


def test_iterables_and_immutability():
    series = construction()
    original = deepcopy(series)
    expected = forecast_series(series)
    for convert in (list, iter):
        assert (
            forecast_series(
                replace(
                    series,
                    points=convert(series.points),
                    sources=convert(series.sources),
                    breakdown=convert(series.breakdown),
                    source_breakdown=convert(series.source_breakdown),
                )
            )
            == expected
        )
    assert series == original
    refused = replace(series, reconciliation_open=True)
    original_refused = deepcopy(refused)
    forecast_series(refused)
    assert refused == original_refused


def representation_battery():
    price = property_series()
    price = replace(
        price,
        points=tuple(
            replace(p, value=D(str(v)))
            for p, v in zip(
                price.points,
                ("10.005", "11.005", "12.005", "13.005", "15.005"),
                strict=True,
            )
        ),
    )
    return representation(
        (
            forecast_series(construction()),
            forecast_series(price),
            smoothing((D(10), D(12), D(11)), D("0.5")),
            predict((D(10), D(12), D(11)), "simple_exponential_smoothing", 1, 1),
        )
    )


def test_hostile_decimal_context_and_halfway():
    expected = representation_battery()
    with localcontext() as context:
        context.prec = 2
        context.rounding = ROUND_DOWN
        context.traps[Inexact] = True
        assert representation_battery() == expected
    assert expected[1]["value"]["value"][0] == "16.26"
    assert expected[1]["value"]["exact_unrounded"][0] == "16.255"


@pytest.mark.parametrize("when", ["before", "after"])
def test_process_decimal_defaults(when):
    script = """
import decimal, json, sys
def alter():
    c = decimal.DefaultContext
    c.prec = 2
    c.rounding = decimal.ROUND_FLOOR
    c.Emin, c.Emax = -5, 5
    c.clamp, c.capitals = 1, 0
    c.traps[decimal.Inexact] = True
    c.traps[decimal.Rounded] = True
if sys.argv[1] == "before":
    alter()
from test_forecast import representation_battery
if sys.argv[1] == "after":
    alter()
print(json.dumps(representation_battery(), sort_keys=True))
"""
    core = Path(__file__).resolve().parents[1]
    env = dict(
        os.environ, PYTHONPATH=os.pathsep.join((str(core / "src"), str(core / "tests")))
    )

    def run(mode):
        result = subprocess.run(
            [sys.executable, "-c", script, mode],
            env=env,
            capture_output=True,
            text=True,
            check=True,
        )
        return json.loads(result.stdout)

    assert run(when) == run("unchanged")


def test_investment_units_notes_and_running_year():
    for measure, unit in (
        ("project_count", "count"),
        ("announced_capex", "qar_million"),
    ):
        base = construction()
        series = replace(
            base,
            admission=evidence("fdi_projects"),
            key="announced_investment",
            table="fdi_projects",
            subject="sector",
            measure=measure,
            unit=unit,
            sources=(chain("fdi_projects"),),
            points=tuple(replace(p, measure=measure, unit=unit) for p in base.points),
        )
        result = forecast_series(series)
        assert "fdi_estimates" in result.caveats
        assert result.value.unit == unit
        assert result.value.places == (0 if measure == "project_count" else 2)
        for changes in (
            {"subject": "fdi_project"},
            {"unit": "unknown"},
            {"unit": ""},
            {"points": (*series.points[:-1], replace(series.points[-1], unit="qar"))},
            {
                "points": (
                    *series.points[:-1],
                    replace(series.points[-1], complete=False),
                )
            },
        ):
            assert isinstance(
                forecast_series(replace(series, **changes)), ForecastNotOffered
            )
        with pytest.raises(ValueError, match="caveats"):
            replace(result, caveats=("forecast_backtest_range",))


def test_hotels_and_licences_keep_separate_measures_and_bulk_flags():
    base = released("earner_count")
    results = []
    for key, table, measure, unit in (
        ("hotel_demand_and_room_rates", "pub_hotel_monthly", "demand", "count"),
        (
            "hotel_demand_and_room_rates",
            "pub_hotel_monthly",
            "adr",
            "qar",
        ),
        ("licence_issues", "pub_licence_issued", "issued_count", "count"),
        ("licence_cancellations", "pub_licence_cancelled", "cancelled_count", "count"),
    ):
        series = replace(
            base,
            admission=evidence(table),
            key=key,
            table=table,
            measure=measure,
            unit=unit,
            input_class="public",
            subject="municipality",
            geography="municipality:invented",
            geography_kind="public",
            source_geography="municipality:invented",
            level="municipality",
            sources=(chain(table),),
            points=tuple(
                replace(p, measure=measure, unit=unit, bulk_month=i == 0)
                for i, p in enumerate(base.points)
            ),
            families=(),
            partition="",
            protected_table="",
        )
        if key == "hotel_demand_and_room_rates":
            series = replace(
                series,
                geography="national",
                geography_kind="national",
                source_geography="national",
                level="national",
                subject="national",
            )
        result = forecast_series(series)
        results.append(result)
        assert result.history[0].bulk_month is True
        assert result.series_key == key and result.measure == measure
        assert result.value.unit == unit
        if key == "licence_issues":
            assert "openings_incomplete" in result.caveats
            with pytest.raises(ValueError):
                replace(result, caveats=("forecast_backtest_range",))
        if key == "licence_cancellations":
            with pytest.raises(ValueError, match="history"):
                replace(
                    result,
                    history=tuple(replace(p, bulk_month=False) for p in result.history),
                )
        assert isinstance(
            forecast_series(replace(series, table="invented_wrong")), ForecastNotOffered
        )
    assert results[0].measure != results[1].measure


def test_wrong_table_even_when_source_chain_matches(monkeypatch):
    series = construction()
    wrong = replace(
        series, table="pub_licence_issued", sources=(chain("pub_licence_issued"),)
    )

    def fitted(*args, **kwargs):
        raise AssertionError("wrong admitted table reached fitting")

    monkeypatch.setattr(module, "backtest", fitted)
    assert isinstance(forecast_series(wrong), ForecastNotOffered)


@pytest.mark.parametrize("field", ["breakdown", "caveats", "reliability", "qualifiers"])
def test_result_metadata_exact_text(field):
    result = forecast_series(construction())
    subclass = type("PlantedText", (str,), {})
    changes = {
        "breakdown": tuple((subclass(k), v) for k, v in result.breakdown),
        "caveats": tuple(subclass(c) for c in result.caveats),
        "reliability": subclass(result.reliability),
        "qualifiers": {subclass(k): v for k, v in result.qualifiers.items()},
    }
    with pytest.raises(ValueError, match="text"):
        replace(result, **{field: changes[field]})


@pytest.mark.parametrize(
    "changes",
    [
        {"sources": ()},
        {"sources": ("invalid",)},
        {"points": ("invalid",)},
        {"families": ("invalid",)},
        {"breakdown": (("one",),)},
        {"source_breakdown": (("", "category"),)},
        {"reconciliation_open": 1},
    ],
)
def test_malformed_series_construction(changes):
    with pytest.raises(ValueError):
        replace(construction(), **changes)


@pytest.mark.parametrize(
    "changes",
    [
        {"deal_count": -1},
        {"deal_count": True},
        {"deal_count": 1.5},
        {"bulk_month": 1},
        {"carried_forward": 1},
        {"complete": 1},
    ],
)
def test_malformed_point_construction(changes):
    with pytest.raises(ValueError):
        replace(construction().points[0], **changes)


@pytest.mark.parametrize(
    "changes",
    [
        {"table": "other"},
        {"partition": "rp_all_money"},
        {"measure": "unknown"},
        {"breakdown": "other"},
        {"column": "earner_count"},
        {"role": "denominator"},
    ],
)
def test_ratio_family_binding_plants(changes):
    series = released("pay_level")
    altered = replace(series.families[0], **changes)
    assert isinstance(
        forecast_series(replace(series, families=(altered, series.families[1]))),
        ForecastNotOffered,
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"inside": (4,)},
        {"low": (D(20),), "high": (D(19),)},
    ],
)
def test_result_interval_count_guards(monkeypatch, changes):
    baseline = forecast_series(construction()).computation
    monkeypatch.setattr(
        module, "backtest", lambda *a, **k: replace(baseline, **changes)
    )
    with pytest.raises(ValueError, match="interval counts or ends"):
        forecast_series(construction())


@pytest.mark.parametrize(
    "count_value,mark", [(29, "low_count"), (30, "standard"), (31, "standard")]
)
def test_property_reliability_boundary(count_value, mark):
    series = property_series()
    series = replace(
        series, points=tuple(replace(p, deal_count=count_value) for p in series.points)
    )
    assert forecast_series(series).reliability == mark


def test_direct_fact_fractional_count_is_rejected():
    result = forecast_series(construction())
    with pytest.raises(ValueError, match="fractional count"):
        replace(result.value, value=D("16.25"))
    assert result.error.places == 2


def test_municipal_stayer_and_resident_bindings():
    series = released("stayer_index")
    municipal = replace(
        series,
        geography="municipality:invented",
        geography_kind="public",
        level="municipality",
    )
    assert forecast_series(municipal).value.geography == municipal.geography
    for key in ("pay_level", "earner_count", "wage_bill", "stayer_index"):
        series = released(key)
        partition = series.partition.replace("wp_", "rp_")
        table = "month_change" if key == "stayer_index" else "resident_pay"
        series = replace(
            series,
            admission=replace(evidence(table), feed_names=series.admission.feed_names),
            table=table,
            partition=partition,
            protected_table="resident_pay",
            sources=(chain(table),),
            families=tuple(
                replace(f, table="resident_pay", partition=partition)
                for f in series.families
            ),
        )
        assert forecast_series(series).families == series.families
