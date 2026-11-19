"""Retained ordinary C30 regressions; no mutation campaign is run here."""

from copy import deepcopy
from dataclasses import replace
from decimal import Decimal as D
from decimal import Inexact, localcontext
from types import MappingProxyType

import pytest
from test_forecast import construction, evidence, property_series, released

from eii_core.calc import forecast as f
from eii_core.calc.forecast_backtest import backtest
from eii_core.calc.forecast_list import definition
from eii_core.calc.forecast_models import predict, smoothing


class Text(str):
    """Planted non-exact text."""


@pytest.mark.parametrize(
    "call,message",
    [
        (lambda: definition(Text("pay_level")), "exact text required"),
        (lambda: predict((), "drift", 1, 1), "empty history"),
        (lambda: smoothing((D(1),), D(0)), "invalid alpha"),
        (lambda: predict((D(1),), "bad", 1, 1), "unknown candidate"),
        (
            lambda: predict((D(1),), "drift", 0, 1),
            "positive season and horizon required",
        ),
        (lambda: predict((D(1),), "seasonal_naive", 2, 1), "season exceeds history"),
        (lambda: predict((D(1),), "drift", 1, 1), "drift requires two values"),
        (lambda: f.period_step("2025/2026", "year"), "invalid period pair"),
        (lambda: f.period_step("2025-01/2025-03", "month"), "nonadjacent period pair"),
        (lambda: f.period_step("bad", "year"), "invalid period"),
        (lambda: f.period_step("9999", "year"), "period outside supported years"),
        (lambda: f.period_step(Text("2025"), "year"), "exact nonempty text required"),
        (lambda: f.period_step("2025", Text("year")), "exact nonempty text required"),
        (
            lambda: f.ForecastNotOffered(Text("forecast_not_offered")),
            "invalid forecast decline",
        ),
    ],
    ids=[
        "definition",
        "empty",
        "alpha",
        "candidate",
        "dimensions",
        "season",
        "drift",
        "pair",
        "adjacency",
        "period",
        "overflow",
        "period-type",
        "frequency-type",
        "decline",
    ],
)
def test_exact_diagnostic(call, message):
    with pytest.raises(ValueError) as caught:
        call()
    assert str(caught.value) == message


@pytest.mark.parametrize(
    "changes", [{"season": 0}, {"season": True}, {"horizon": 0}, {"horizon": True}]
)
def test_backtest_dimensions_even_with_short_history(changes):
    args = dict(season=1, horizon=1, candidates=("drift",)) | changes
    with pytest.raises(ValueError, match=r"^positive season and horizon required$"):
        backtest((), **args)


@pytest.mark.parametrize("candidates", [(), ("bad",), (Text("drift"),)])
def test_backtest_candidates_before_short_history(candidates):
    with pytest.raises(ValueError, match=r"^unknown candidate$"):
        backtest((), season=1, horizon=1, candidates=candidates)


def test_predict_boundary_last_level_and_own_decimal_context():
    assert predict((D(7), D(9)), "seasonal_naive", 2, 3) == (D(7), D(9), D(7))
    assert (
        predict((D(1), D(2)), "simple_exponential_smoothing", 1, 2) == (D("1.1"),) * 2
    )
    assert predict((D(1), D(2), D(3)), "simple_exponential_smoothing", 1, 1) == (
        D("2.89"),
    )
    expected = predict(tuple(map(D, (1, 2, 3, 5))), "drift", 1, 2)
    with localcontext() as ctx:
        ctx.prec = 2
        ctx.traps[Inexact] = True
        assert predict(tuple(map(D, (1, 2, 3, 5))), "drift", 1, 2) == expected


@pytest.mark.parametrize(
    "changes,message",
    [
        ({"unit": Text("count")}, "exact text required"),
        ({"bulk_month": 1}, "boolean required"),
    ],
)
def test_point_diagnostics(changes, message):
    with pytest.raises(ValueError) as caught:
        replace(construction().points[0], **changes)
    assert str(caught.value) == message


@pytest.mark.parametrize(
    "field", ["table", "partition", "measure", "breakdown", "column", "role"]
)
def test_family_exact_text(field):
    family = released("pay_level").families[0]
    with pytest.raises(ValueError, match=r"^exact nonempty text required$"):
        replace(family, **{field: Text(getattr(family, field))})


@pytest.mark.parametrize(
    "changes,message",
    [
        ({"unit": Text("count")}, "exact text required"),
        ({"breakdown": (("one",),)}, "invalid breakdown"),
        ({"sources": ()}, "missing source chain"),
        ({"sources": ("bad",)}, "invalid source chain"),
        ({"families": ("bad",)}, "invalid home family"),
        ({"points": ("bad",)}, "invalid point"),
        ({"reconciliation_open": 1}, "boolean required"),
    ],
)
def test_series_diagnostics(changes, message):
    with pytest.raises(ValueError) as caught:
        replace(construction(), **changes)
    assert str(caught.value) == message


def test_series_order_pair_and_release_diagnostics():
    series = construction()
    cases = [
        (
            series,
            {"points": tuple(reversed(series.points))},
            "periods must be ordered and unique",
        ),
        (
            series,
            {
                "points": (
                    series.points[0],
                    replace(series.points[1], release_id="other"),
                )
            },
            "mixed release ids",
        ),
    ]
    stayer = released("stayer_index")
    cases += [
        (
            stayer,
            {"points": (replace(stayer.points[0], period="2020-01"),)},
            "stayer pair required",
        ),
        (
            stayer,
            {"points": (stayer.points[0], *stayer.points[2:])},
            "broken stayer pair chain",
        ),
        (
            released("earner_count"),
            {
                "points": (
                    replace(
                        released("earner_count").points[0], period="2020-01/2020-02"
                    ),
                )
            },
            "unexpected period pair",
        ),
    ]
    for original, changes, message in cases:
        with pytest.raises(ValueError) as caught:
            replace(original, **changes)
        assert str(caught.value) == message


def test_empty_series_still_validates_frequency_and_family_snapshot():
    with pytest.raises(ValueError, match=r"^exact nonempty text required$"):
        replace(construction(), points=(), frequency=Text("year"))
    series = released("pay_level")
    families = list(series.families)
    copy = replace(series, families=families)
    families.clear()
    assert copy.families == series.families
    assert type(copy.families) is tuple


def test_binding_variants_and_project_count_unit():
    series = released("stayer_index")
    assert isinstance(
        f.forecast_series(replace(series, protected_table="bad")), f.ForecastNotOffered
    )
    for key in ("stayer_index", "pay_level"):
        series = released(key)
        partition = "wp_all_quartile" if key == "stayer_index" else series.partition
        series = replace(
            series,
            partition=partition,
            families=tuple(
                replace(x, partition=partition, measure="basic")
                for x in series.families
            ),
        )
        assert isinstance(f.forecast_series(series), f.ForecastResult)
    series = released("earner_count")
    assert isinstance(
        f.forecast_series(replace(series, protected_table="resident_pay")),
        f.ForecastResult,
    )
    base = construction()
    series = replace(
        base,
        admission=evidence("fdi_projects"),
        key="announced_investment",
        table="fdi_projects",
        subject="sector",
        measure="project_count",
        unit="qar",
        sources=tuple(replace(x, table="fdi_projects") for x in base.sources),
        points=tuple(
            replace(x, measure="project_count", unit="qar") for x in base.points
        ),
    )
    assert isinstance(f.forecast_series(series), f.ForecastNotOffered)


@pytest.mark.parametrize(
    "field",
    [
        "model",
        "origin",
        "target",
        "method",
        "version",
        "series_key",
        "measure",
        "table",
    ],
)
def test_result_exact_identity_text(field):
    result = f.forecast_series(construction())
    with pytest.raises(ValueError, match=r"^exact nonempty text required$"):
        replace(result, **{field: Text(getattr(result, field))})


@pytest.mark.parametrize(
    "changes,message",
    [
        ({"horizon": True}, "invalid horizon"),
        ({"qualifiers": {}}, "invalid qualifiers"),
        ({"version": "other"}, "inconsistent lineage or categories"),
        ({"origin": "2023"}, "inconsistent history or target"),
        ({"low_clamped": 0}, "invalid clamp marks"),
        ({"high_clamped": 0}, "invalid clamp marks"),
        ({"caveats": ()}, "invalid forecast caveats"),
        ({"public_only_ranking": False}, "invalid Public-only ranking"),
        ({"reliability": "standard"}, "invalid reliability"),
    ],
)
def test_result_exact_diagnostics(changes, message):
    with pytest.raises(ValueError) as caught:
        replace(f.forecast_series(construction()), **changes)
    assert str(caught.value) == message


def test_result_independent_companion_fields_and_qualifier_snapshot():
    result = f.forecast_series(construction())
    changes = [deepcopy(result.value), deepcopy(result.value)]
    object.__setattr__(changes[0], "release_id", "other")
    object.__setattr__(changes[1], "exact_unrounded", D("16.26"))
    for value in changes:
        with pytest.raises(ValueError, match=r"^inconsistent companion fact$"):
            replace(result, value=value)
    with pytest.raises(ValueError, match=r"^invalid qualifiers$"):
        replace(
            result,
            model="seasonal_naive",
            qualifiers={"model": "seasonal_naive", "horizon": 1},
        )
    mapping = dict(result.qualifiers)
    copy = replace(result, qualifiers=MappingProxyType(mapping))
    mapping.clear()
    assert copy.qualifiers == result.qualifiers
    assert type(copy.qualifiers) is f.ForecastQualifiers


def test_result_refusals_before_companion_comparison():
    result = f.forecast_series(construction())
    for series in (
        replace(result.series, key="bad"),
        replace(result.series, subject="area"),
        replace(result.series, points=()),
    ):
        with pytest.raises(ValueError, match=r"^inadmissible result$"):
            replace(result, series=series)
    for series in (
        replace(result.series, reconciliation_open=True),
        replace(
            result.series,
            points=tuple(
                replace(p, carried_forward=True) for p in result.series.points
            ),
        ),
    ):
        with pytest.raises(ValueError, match=r"^withheld window$"):
            replace(result, series=series, history=series.points)
    with pytest.raises(ValueError, match=r"^negative forecast$"):
        replace(result, computation=replace(result.computation, forecasts=(D(-1),)))


def test_result_interval_and_property_diagnostics(monkeypatch):
    result = f.forecast_series(construction())
    monkeypatch.setattr(
        f, "backtest", lambda *a, **k: replace(result.computation, inside=(4,))
    )
    with pytest.raises(ValueError, match=r"^invalid interval counts or ends$"):
        f.forecast_series(construction())
    monkeypatch.undo()
    result = f.forecast_series(property_series())
    with pytest.raises(ValueError, match=r"^missing property deal counts$"):
        replace(result, history_deal_counts=())


def test_fact_names_scales_versions_zero_error_unit_and_counts():
    series = construction()
    series = replace(
        series, sources=tuple(replace(s, version="source-v2") for s in series.sources)
    )
    result = f.forecast_series(series)
    assert tuple(x.metric_key for x in result.facts) == (
        "forecast_value",
        "forecast_low",
        "forecast_high",
        "forecast_backtest_error",
        "forecast_backtest_points",
        "forecast_inside",
        "forecast_tested",
    )
    assert tuple(x.places for x in result.facts) == (0, 0, 0, 2, 0, 0, 0)
    assert all(s.version == "source-v2" for x in result.facts for s in x.sources)
    assert f.forecast_series(construction((10,) * 5)).error.unit == "count"
    prices = f.forecast_series(property_series())
    assert all(
        x.metric_key == "deal_count" and x.places == 0
        for x in prices.history_deal_counts
    )
    series = replace(
        series, points=tuple(replace(p, deal_count=99) for p in series.points)
    )
    assert f.forecast_series(series).history_deal_counts == ()
    assert f.forecast_series(construction((50,) * 5)).reliability == "standard"
    series = construction((50,) * 5)
    series = replace(
        series, points=tuple(replace(p, deal_count=5) for p in series.points)
    )
    assert f.forecast_series(series).reliability == "low_count"


@pytest.mark.parametrize(
    "values,errors,inside",
    [
        ((10, 10, 8, 6, 4, 3), (-2, -2, -2, -1), 3),
        ((10, 10, 11, 9, 11, 13), (1, -2, 2, 2), 3),
        ((10, 10, 8, 7, 6, 4), (-2, -1, -1, -2), 4),
    ],
)
def test_leave_one_out_keeps_every_other_origin(values, errors, inside):
    result = backtest(
        map(D, values), season=1, horizon=1, candidates=("seasonal_naive",)
    )
    assert result.candidates[0].errors == tuple((D(e),) for e in errors)
    assert result.inside == (inside,)


@pytest.mark.parametrize("field", ["geography", "geography_kind"])
def test_series_geography_text_diagnostic(field):
    series = construction()
    with pytest.raises(ValueError, match=r"^exact nonempty text required$"):
        replace(series, **{field: Text(getattr(series, field))})
