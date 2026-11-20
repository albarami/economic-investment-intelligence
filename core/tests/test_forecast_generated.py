"""S6-T25 calculation-only plants. Every history and hash is invented.

These fixtures do not establish source-to-release swap parity or a go-live gate.
"""

from dataclasses import replace
from decimal import ROUND_DOWN, Inexact, localcontext
from decimal import Decimal as D

import pytest
from test_forecast import chain, construction, evidence, released

from eii_core.calc import forecast as f
from eii_core.calc import forecast_backtest as bt
from eii_core.calc.facts import NoData, Suppressed
from eii_core.calc.forecast_list import DEFINITION_VERSION, DEFINITIONS, definition
from eii_core.calc.forecast_models import CANDIDATES

OCCUPATIONS = (
    ("employment_by_occupation_residence", "residence", "op_res_quartile"),
    ("employment_by_occupation_workplace", "workplace", "op_work_quartile"),
)
GENERATED_KEYS = (
    "pay_level",
    "earner_count",
    "wage_bill",
    "stayer_index",
    "employment_by_area",
    *(key for key, _, _ in OCCUPATIONS),
)


def occupation(key):
    _, basis, partition = next(row for row in OCCUPATIONS if row[0] == key)
    base = released("earner_count")
    return replace(
        base,
        key=key,
        table="occupation_pay",
        admission=replace(
            evidence("occupation_pay"), feed_names=definition(key).confirmed_sources
        ),
        sources=(chain("occupation_pay"),),
        partition=partition,
        protected_table="occupation_pay",
        breakdown=(("basis", basis), ("occupation_group", "2")),
        source_breakdown=(),
        families=(
            f.HomeFamily(
                "occupation_pay",
                partition,
                "net",
                f"basis={basis};occupation_group=2;band=ALL",
                "earner_count",
                "single",
            ),
        ),
    )


def generated(key):
    return (
        occupation(key)
        if key.startswith("employment_by_occupation_")
        else released(key)
    )


def test_closed_occupation_definitions_name_inputs_and_history():
    assert DEFINITION_VERSION == "c30-series-v3"
    for key, basis, _ in OCCUPATIONS:
        spec = definition(key)
        assert spec is not None
        assert (spec.state, spec.tables, spec.input_class) == (
            "released",
            ("occupation_pay",),
            "synthetic",
        )
        assert (spec.frequency, spec.unit, spec.subjects) == (
            "month",
            "count",
            ("area",),
        )
        assert spec.levels == ("area", "national")
        assert spec.measures == ("earner_count",)
        expected = ("business_register.v1", "employment.v1", "wages.v1")
        if basis == "residence":
            expected = (*expected[:2], "residence.v1", expected[-1])
        assert spec.confirmed_sources == expected


@pytest.mark.parametrize("key", ["joiner_count", "leaver_count", "hiring", "leaving"])
def test_retired_flows_remain_off_the_list_before_fitting(monkeypatch, key):
    monkeypatch.setattr(
        f, "backtest", lambda *a, **k: pytest.fail("retired flow fitted")
    )
    assert definition(key) is None
    assert isinstance(
        f.forecast_series(replace(released("earner_count"), key=key)),
        f.ForecastNotOffered,
    )


@pytest.mark.parametrize("key", GENERATED_KEYS)
def test_generated_inputs_use_one_contract_and_own_backtest(key):
    series = generated(key)
    result = f.forecast_series(series)
    assert isinstance(result, f.ForecastResult)
    expected = bt.backtest(
        (p.value for p in result.history), season=12, horizon=1, candidates=CANDIDATES
    )
    assert result.computation == expected
    assert result.origin == f.period_step(series.points[-1].period, "month")[0]
    assert result.origin == series.admission.window_period.split("/")[-1]
    assert result.target > result.origin  # target may be outside the protected window
    assert not result.public_only_ranking
    for fact in result.facts:
        assert fact.input_classes == ("synthetic",)
        assert fact.evidence_status == "inferred"
        assert fact.sources == series.sources
        assert fact.derivation.admission == series.admission
        assert fact.derivation.window_key == series.window_key
        assert fact.derivation.generator == series.generator
        assert fact.derivation.generator_version == series.generator_version
    assert result.low.exact_unrounded == max(D(0), expected.low[0])
    assert result.high.exact_unrounded == max(D(0), expected.high[0])
    assert result.error.exact_unrounded == expected.error
    assert result.inside.value == expected.inside[0]
    assert result.tested.value == result.points.value == expected.tested


@pytest.mark.parametrize("key,basis,partition", OCCUPATIONS)
@pytest.mark.parametrize(
    "geography,kind,level",
    [
        ("national", "national", "national"),
        ("release_units:invented", "release_units", "area"),
        ("area_shape:invented", "area_shape", "area"),
    ],
)
def test_occupation_geographies_and_both_pay_measures(
    key, basis, partition, geography, kind, level
):
    series = replace(
        occupation(key), geography=geography, geography_kind=kind, level=level
    )
    for measure in ("net", "basic"):
        result = f.forecast_series(
            replace(series, families=(replace(series.families[0], measure=measure),))
        )
        assert isinstance(result, f.ForecastResult)
        assert result.families[0].partition == partition


@pytest.mark.parametrize("key,basis,partition", OCCUPATIONS)
@pytest.mark.parametrize(
    "change",
    [
        "table",
        "partition",
        "protected_table",
        "family_table",
        "family_partition",
        "family_measure",
        "family_column",
        "family_role",
        "family_breakdown",
        "missing_band",
        "band_row",
        "basis",
        "group",
        "extra_split",
        "missing_split",
        "public",
        "named_subject",
        "municipality",
    ],
)
def test_occupation_binding_plants_refuse_before_fitting(
    monkeypatch, key, basis, partition, change
):
    series = occupation(key)
    changes = {
        "table": {"table": "worker_pay"},
        "partition": {
            "partition": "op_work_quartile"
            if basis == "residence"
            else "op_res_quartile"
        },
        "protected_table": {"protected_table": "worker_pay"},
        "basis": {"breakdown": (("basis", "wrong"), ("occupation_group", "2"))},
        "group": {"breakdown": (("basis", basis), ("occupation_group", "invented"))},
        "extra_split": {"breakdown": (*series.breakdown, ("gender", "invented"))},
        "missing_split": {"breakdown": ()},
        "missing_band": {
            "families": (
                replace(
                    series.families[0],
                    breakdown=f"basis={basis};occupation_group=2",
                ),
            )
        },
        "band_row": {
            "families": (
                replace(
                    series.families[0],
                    breakdown=f"basis={basis};occupation_group=2;band=B03",
                ),
            )
        },
        "public": {"input_class": "public"},
        "named_subject": {"subject": "register_company"},
        "municipality": {
            "level": "municipality",
            "geography": "municipality:invented",
            "geography_kind": "public",
        },
    }
    if change.startswith("family_"):
        field = change.removeprefix("family_")
        changes[change] = {
            "families": (replace(series.families[0], **{field: "wrong"}),)
        }
    monkeypatch.setattr(
        f, "backtest", lambda *a, **k: pytest.fail("invalid binding fitted")
    )
    assert isinstance(
        f.forecast_series(replace(series, **changes[change])), f.ForecastNotOffered
    )


@pytest.mark.parametrize("key", GENERATED_KEYS)
@pytest.mark.parametrize("plant", ["missing", "absent"])
def test_missing_confirmed_feeds_refuse_before_fitting(monkeypatch, key, plant):
    series = generated(key)
    feeds = definition(key).confirmed_sources
    admission = replace(
        series.admission, feed_names=feeds[:-1] if plant == "missing" else ()
    )
    monkeypatch.setattr(
        f, "backtest", lambda *a, **k: pytest.fail("unconfirmed feeds fitted")
    )
    assert f.forecast_series(replace(series, admission=admission)) == (
        f.ForecastNotOffered("forecast_not_offered")
    )


@pytest.mark.parametrize("key", GENERATED_KEYS)
def test_released_series_without_admission_is_an_error(monkeypatch, key):
    # Confirmation A N2: a released series with no admission stays an error, as on the Public route.
    monkeypatch.setattr(
        f, "backtest", lambda *a, **k: pytest.fail("unadmitted series fitted")
    )
    with pytest.raises(ValueError, match="release admission required"):
        f.forecast_series(replace(generated(key), admission=None))


def test_public_admission_with_feed_names_refuses_before_fitting(monkeypatch):
    # Confirmation A N3: no feed name reaches a Public fact's lineage.
    series = construction()
    planted = replace(
        series, admission=replace(series.admission, feed_names=("wages.v1",))
    )
    monkeypatch.setattr(
        f, "backtest", lambda *a, **k: pytest.fail("feed-named Public series fitted")
    )
    assert f.forecast_series(planted) == f.ForecastNotOffered("forecast_not_offered")


@pytest.mark.parametrize(
    "key", ["employment_by_area", "employment_by_occupation_workplace"]
)
@pytest.mark.parametrize("plant", ["wrong", "extra"])
def test_wrong_or_extra_confirmed_feeds_refuse_before_fitting(monkeypatch, key, plant):
    series = generated(key)
    feeds = definition(key).confirmed_sources
    # All names already exist in the window's feed universe (rule 12).
    planted = (
        (feeds[0], "residence.v1", feeds[-1])
        if plant == "wrong"
        else (*feeds, "residence.v1")
    )
    admission = replace(series.admission, feed_names=planted)
    assert admission.source_hashes == tuple(
        (source.lineage_ref, source.sha256) for source in series.sources
    )  # A self-consistent source chain cannot legitimise the wrong feed set.
    monkeypatch.setattr(
        f, "backtest", lambda *a, **k: pytest.fail("unconfirmed feeds fitted")
    )
    assert f.forecast_series(replace(series, admission=admission)) == (
        f.ForecastNotOffered("forecast_not_offered")
    )


@pytest.mark.parametrize("key", [key for key, _, _ in OCCUPATIONS])
@pytest.mark.parametrize("plant", ["wrong", "extra"])
def test_invented_confirmed_feed_refuses_before_fitting(monkeypatch, key, plant):
    series = occupation(key)
    feeds = definition(key).confirmed_sources
    # The planted name is no feed of this window's universe (rule 12).
    assert "invented.v1" not in {
        name for spec in DEFINITIONS for name in spec.confirmed_sources
    }
    planted = (
        (*feeds[:-1], "invented.v1") if plant == "wrong" else (*feeds, "invented.v1")
    )
    admission = replace(series.admission, feed_names=planted)
    assert admission.source_hashes == tuple(
        (source.lineage_ref, source.sha256) for source in series.sources
    )  # A self-consistent source chain cannot legitimise an invented feed.
    monkeypatch.setattr(
        f, "backtest", lambda *a, **k: pytest.fail("unconfirmed feeds fitted")
    )
    assert f.forecast_series(replace(series, admission=admission)) == (
        f.ForecastNotOffered("forecast_not_offered")
    )


@pytest.mark.parametrize("key", GENERATED_KEYS)
def test_exact_confirmed_feed_set_reaches_facts_regardless_of_order(key):
    series = generated(key)
    feeds = definition(key).confirmed_sources
    result = f.forecast_series(
        replace(series, admission=replace(series.admission, feed_names=feeds[::-1]))
    )
    assert isinstance(result, f.ForecastResult)
    for fact in result.facts:
        assert fact.derivation.admission.feed_names == feeds[::-1]
        assert fact.sources == series.sources


@pytest.mark.parametrize(
    "feeds",
    [None, "employment.v1", ["employment.v1"], (1,), ("",), ("employment.v1",) * 2],
)
def test_admission_feed_names_are_typed_and_unique(feeds):
    with pytest.raises(ValueError, match="release admission feeds"):
        replace(evidence("worker_pay"), feed_names=feeds)


@pytest.mark.parametrize("key", [r.key for r in DEFINITIONS if r.state == "open"])
def test_unavailable_is_no_data_with_source_reason_and_no_fitting(monkeypatch, key):
    monkeypatch.setattr(
        f, "backtest", lambda *a, **k: pytest.fail("absent source fitted")
    )
    result = f.forecast_source_refusal(key)
    assert result == f.forecast_series(replace(construction(), key=key))
    assert result.status == "NO_DATA"
    assert result.reason == definition(key).open_reason
    assert result.reason != "series_too_short"
    assert result.facts == ()
    for changes in (
        {"status": "OUT_OF_SCOPE"},
        {"reason": "series_too_short"},
        {"facts": (object(),)},
    ):
        with pytest.raises(ValueError, match="open forecast"):
            replace(result, **changes)


@pytest.mark.parametrize("key", GENERATED_KEYS)
def test_generated_short_and_gapped_history_has_no_numeric_output(key):
    series = generated(key)
    short = replace(series, points=series.points[-15:])
    assert f.forecast_series(short) == NoData("series_too_short")
    assert isinstance(
        f.forecast_series(replace(series, points=series.points[-16:])), f.ForecastResult
    )
    if key != "stayer_index":
        gap = replace(series, points=(*series.points[:2], *series.points[-15:]))
        assert f.forecast_series(gap) == NoData("series_too_short")


@pytest.mark.parametrize("key", GENERATED_KEYS)
def test_carry_and_unpublished_points_never_reach_fitting(monkeypatch, key):
    series = generated(key)
    monkeypatch.setattr(
        f, "backtest", lambda *a, **k: pytest.fail("withheld history fitted")
    )
    carried = replace(series.points[0], carried_forward=True)
    assert f.forecast_series(
        replace(series, points=(carried, *series.points[1:]))
    ) == Suppressed("CARRIED_FORWARD")
    unpublished = replace(series.points[0], published=False)
    with pytest.raises(ValueError, match="unpublished"):
        f.forecast_series(replace(series, points=(unpublished, *series.points[1:])))


def window_evidence(series, **changes):
    assert "window_period" in f.ReleaseAdmission.__dataclass_fields__, (
        "manifest window span missing"
    )
    assert "window_key" in f.ReleaseAdmission.__dataclass_fields__, (
        "manifest window identity missing"
    )
    return replace(series.admission, **changes)


@pytest.mark.parametrize("key", ["earner_count", "stayer_index"])
@pytest.mark.parametrize(
    "plant",
    [
        "foreign_key",
        "foreign_span",
        "broader_span",
        "before",
        "after",
        "missing_origin",
        "missing_span",
        "missing_key",
    ],
)
def test_protected_window_binding_precedes_fitting(monkeypatch, key, plant):
    series = released(key)
    window_evidence(series)
    if plant == "foreign_key":
        series = replace(series, admission=window_evidence(series, window_key="f" * 64))
    elif plant == "foreign_span":
        series = replace(
            series, admission=window_evidence(series, window_period="2020-02/2021-10")
        )
    elif plant == "broader_span":
        series = replace(
            series, admission=window_evidence(series, window_period="2019-12/2021-11")
        )
    elif plant in ("missing_span", "missing_key"):
        field = "window_period" if plant == "missing_span" else "window_key"
        series = replace(series, admission=window_evidence(series, **{field: ""}))
    elif plant == "missing_origin":
        series = replace(series, points=series.points[:-1])
    else:
        # Shift the complete contiguous series, preserving all release labels.
        start = "2019-12" if plant == "before" else "2020-02"
        shifted = []
        for point in series.points:
            _, later = f.period_step(start, "month")
            shifted.append(
                replace(
                    point, period=f"{start}/{later}" if key == "stayer_index" else start
                )
            )
            start = later
        series = replace(series, points=tuple(shifted))
    monkeypatch.setattr(
        f, "backtest", lambda *a, **k: pytest.fail("out-of-window history fitted")
    )
    with pytest.raises(ValueError, match="window"):
        f.forecast_series(series)


@pytest.mark.parametrize(
    "span",
    [
        "wrong",
        "2020-00/2021-11",
        "2021-11/2020-01",
        "2020-01/2021-11/2022-01",
        "2020-Q1/2021-11",
    ],
)
def test_malformed_manifest_span_is_rejected(span):
    series = released("earner_count")
    with pytest.raises(ValueError, match="window"):
        window_evidence(series, window_period=span)


def rebuilt_result(result, series, computation):
    """Build all companions/metadata consistently; only history provenance is stale."""
    facts = f._facts(series, definition(series.key), computation, result.target)
    slots = dict(
        zip(
            ("value", "low", "high", "error", "points", "inside", "tested"),
            facts,
            strict=True,
        )
    )
    return replace(
        result,
        series=series,
        computation=computation,
        model=computation.model,
        qualifiers={"model": computation.model, "horizon": result.horizon},
        history=series.points,
        sources=series.sources,
        families=series.families,
        low_clamped=computation.low[0] < 0,
        high_clamped=computation.high[0] < 0,
        **slots,
    )


def test_stale_computation_with_updated_companions_and_release_metadata_is_rejected():
    baseline = f.forecast_series(released("earner_count"))
    replacement = replace(
        baseline.series,
        window_key="f" * 64,
        sources=(replace(baseline.series.sources[0], sha256="f" * 64),),
        points=tuple(
            replace(p, value=p.value + D(i % 3), release_id="invented_replacement")
            for i, p in enumerate(baseline.series.points)
        ),
        admission=replace(
            baseline.series.admission,
            release_id="invented_replacement",
            table_sha256="d" * 64,
            window_key="f" * 64,
            source_hashes=(("invented", "f" * 64),),
        ),
        generator_version="fixture-v2",
    )
    fresh = f.forecast_series(replacement)
    assert fresh.computation != baseline.computation
    assert fresh.model == baseline.model  # matching labels do not prove freshness
    with pytest.raises(ValueError, match=r"backtest.*history"):
        rebuilt_result(baseline, replacement, baseline.computation)


@pytest.mark.parametrize(
    "component",
    [
        "candidates",
        "model",
        "scale",
        "error",
        "forecasts",
        "low",
        "high",
        "inside",
        "tested",
    ],
)
def test_entire_computation_is_recomputed_even_with_consistent_facts(component):
    result = f.forecast_series(construction())
    baseline = result.computation
    candidates = (
        replace(
            baseline.candidates[0],
            errors=((D(999),), *baseline.candidates[0].errors[1:]),
        ),
        *baseline.candidates[1:],
    )
    changes = {
        "candidates": candidates,
        "model": next(c for c in CANDIDATES if c != baseline.model),
        "scale": baseline.scale + D(1),
        "error": baseline.error + D(1),
        "forecasts": (baseline.forecasts[0] + D(1),),
        "low": (baseline.low[0] - D(1),),
        "high": (baseline.high[0] + D(1),),
        "inside": (0,),
        "tested": baseline.tested + 1,
    }
    with pytest.raises(ValueError, match=r"backtest.*history"):
        rebuilt_result(
            result, result.series, replace(baseline, **{component: changes[component]})
        )


@pytest.mark.parametrize("key", GENERATED_KEYS)
def test_replacement_history_reaches_backtesting_and_final_cpu_fit(monkeypatch, key):
    original = generated(key)
    replacement = replace(
        original,
        points=tuple(
            replace(p, value=p.value + D(7 + i % 4))
            for i, p in enumerate(original.points)
        ),
    )
    calls, fits = [], []
    real_backtest, real_predict = f.backtest, bt.predict

    def record_backtest(values, **kwargs):
        values = tuple(values)
        calls.append(values)
        return real_backtest(values, **kwargs)

    def record_predict(values, *args):
        fits.append(tuple(values))
        return real_predict(values, *args)

    monkeypatch.setattr(f, "backtest", record_backtest)
    monkeypatch.setattr(bt, "predict", record_predict)
    for series in (original, replacement):
        calls.clear()
        fits.clear()
        result = f.forecast_series(series)
        values = tuple(p.value for p in series.points)
        assert calls == [
            values,
            values,
        ]  # calculation and independent result verification
        assert values in fits  # winner refitted on the replacement's entire history
        first = max(2, 12 + 1)
        assert all(values[:origin] in fits for origin in range(first, len(values)))
        assert result.computation == real_backtest(
            values, season=12, horizon=1, candidates=CANDIDATES
        )


@pytest.mark.parametrize("key", GENERATED_KEYS)
def test_generated_forecasts_reproduce_on_cpu_under_hostile_decimal_context(key):
    series = generated(key)
    expected = f.forecast_series(series)
    assert f.forecast_series(series) == expected
    with localcontext() as context:
        context.prec = 2
        context.rounding = ROUND_DOWN
        context.traps[Inexact] = True
        assert f.forecast_series(series) == expected


@pytest.mark.parametrize("key", GENERATED_KEYS)
def test_generated_provenance_caveats_and_backend_markers_cannot_be_dropped(key):
    series = generated(key)
    result = f.forecast_series(series)
    for slot in ("value", "low", "high", "error", "points", "inside", "tested"):
        with pytest.raises(ValueError, match="companion"):
            replace(
                result,
                **{slot: replace(getattr(result, slot), input_classes=("public",))},
            )
    for caveat in ("synthetic_not_evidence_about_qatar", "synthetic_change"):
        with pytest.raises(ValueError, match="caveat"):
            replace(result, caveats=tuple(c for c in result.caveats if c != caveat))
    for field in ("window_key", "window_period", "generator", "generator_version"):
        with pytest.raises(ValueError, match="window or generator"):
            f.forecast_series(replace(series, **{field: ""}))
