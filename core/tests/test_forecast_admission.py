"""Step-one plants: release handoff, source admission and unchanged lineage.

All records and hashes are invented fixtures. They prove no mounted history.
"""

from dataclasses import replace

import pytest
from test_forecast import chain, construction, released

from eii_core.calc import forecast as module
from eii_core.calc.forecast_list import definition


def test_source_pipeline_version_survives_forecast_derivation():
    series = construction()
    series = replace(series, sources=(replace(series.sources[0], version="source-v2"),))
    result = module.forecast_series(series)
    assert result.method == "c30_rolling_origin"
    assert result.version == "v1"
    assert all(fact.sources == series.sources for fact in result.facts)


def test_every_forecast_fact_has_derived_lineage_beside_original_sources():
    result = module.forecast_series(construction())
    for fact in result.facts:
        derivation = getattr(fact, "derivation", None)
        assert derivation is not None, "derived lineage missing from companion"
        assert (derivation.method, derivation.version) == (
            result.method,
            result.version,
        )
        assert (derivation.series_key, derivation.indicator) == (
            result.series_key,
            result.measure,
        )
        assert (derivation.model, derivation.horizon) == (result.model, result.horizon)
        assert derivation.admission == result.series.admission
        for changes in ({"method": "wrong"}, {"series_key": "wrong"}, {"horizon": 2}):
            with pytest.raises(ValueError):
                changed = replace(fact, derivation=replace(derivation, **changes))
                replace(result, value=changed)


@pytest.mark.parametrize(
    "key,reason",
    [
        ("consumer_prices", "publisher_or_licence_unconfirmed"),
        ("producer_prices", "no_source_table"),
        ("imports_by_product", "past_count_not_stated"),
        ("expected_households_and_workers", "no_conversion_parameter_source_table"),
        (
            "property_prices_quarterly",
            "awaiting_reviewed_use_map_and_district_crosswalk",
        ),
    ],
)
def test_open_source_reason_survives_without_fitting(monkeypatch, key, reason):
    def fitted(*args, **kwargs):
        pytest.fail("open source reached fitting")

    monkeypatch.setattr(module, "backtest", fitted)
    result = module.forecast_series(replace(construction(), key=key))
    assert result.state == "open"
    assert result.reason == reason
    assert result.facts == ()
    assert result.status == "NO_DATA"


def admission(series):
    contract = getattr(module, "ReleaseAdmission", None)
    assert contract is not None, "release admission contract missing"
    return contract(
        release_id=series.points[0].release_id,
        table=series.table,
        table_sha256="b" * 64,
        schema_sha256="c" * 64,
        grain=module.TABLE_GRAINS[series.table],
        source_hashes=tuple(
            (source.lineage_ref, source.sha256) for source in series.sources
        ),
    )


def test_release_evidence_required_before_fitting(monkeypatch):
    def fitted(*args, **kwargs):
        pytest.fail("unverified release reached fitting")

    series = construction()
    assert "admission" in series.__dataclass_fields__, "release admission missing"
    monkeypatch.setattr(module, "backtest", fitted)
    with pytest.raises(ValueError, match="release admission"):
        module.forecast_series(replace(series, admission=None))


@pytest.mark.parametrize(
    "changes",
    [
        {"release_id": "other"},
        {"table": "pub_licence_issued"},
        {"grain": ("invented",)},
        {"source_hashes": (("invented", "d" * 64),)},
        {"source_hashes": ()},
    ],
)
def test_foreign_release_table_grain_or_source_fails_before_fitting(
    monkeypatch, changes
):
    series = construction()
    evidence = admission(series)
    monkeypatch.setattr(module, "backtest", lambda *a, **k: pytest.fail("fitted"))
    with pytest.raises(ValueError, match="release admission"):
        module.forecast_series(replace(series, admission=replace(evidence, **changes)))


@pytest.mark.parametrize("field", ["table_sha256", "schema_sha256"])
@pytest.mark.parametrize("value", ["", "not-a-hash", "a" * 63])
def test_admission_digest_plants(field, value):
    with pytest.raises(ValueError, match="release admission"):
        replace(admission(construction()), **{field: value})


def test_conditional_establishment_history_is_public_and_not_backfilled():
    base = released("earner_count")
    assert definition("establishments_by_area") is not None
    series = replace(
        base,
        key="establishments_by_area",
        table="pub_register_snapshot",
        input_class="public",
        subject="area",
        history_route="snapshot",
        measure="establishment_count",
        sources=(chain("pub_register_snapshot"),),
        points=tuple(replace(p, measure="establishment_count") for p in base.points),
        families=(),
        partition="",
        protected_table="",
        admission=None,
    )
    series = replace(series, admission=admission(series))
    assert isinstance(module.forecast_series(series), module.ForecastResult)
    for changes in (
        {"input_class": "synthetic"},
        {"history_route": "current_stock_backfill"},
        {"history_route": "generated_openings"},
        {"table": "pub_register_company"},
    ):
        assert isinstance(
            module.forecast_series(replace(series, **changes)),
            module.ForecastNotOffered,
        )
    with pytest.raises(ValueError, match="release admission"):
        module.forecast_series(replace(series, admission=None))


@pytest.mark.parametrize("split", ["sex", "nationality"])
def test_public_split_never_becomes_ranking_criterion(split):
    series = replace(
        construction(),
        breakdown=((split, "fixture"),),
        source_breakdown=((split, "fixture"),),
    )
    assert not module.forecast_series(series).public_only_ranking


def test_released_generator_metadata_is_mandatory():
    series = released("pay_level")
    assert "generator_version" in series.__dataclass_fields__, (
        "generator metadata missing"
    )
    for changes in ({"generator": ""}, {"generator_version": ""}, {"window_key": ""}):
        with pytest.raises(ValueError, match="released window or generator"):
            module.forecast_series(replace(series, **changes))


def test_forecast_qualifiers_cannot_be_mutated_after_validation():
    result = module.forecast_series(construction())
    with pytest.raises(TypeError):
        result.qualifiers["model"] = "seasonal_naive"


def test_unpublished_input_never_reaches_fitting(monkeypatch):
    series = construction()
    assert "published" in series.points[0].__dataclass_fields__, (
        "publication status missing"
    )
    monkeypatch.setattr(module, "backtest", lambda *a, **k: pytest.fail("fitted"))
    with pytest.raises(ValueError, match="unpublished"):
        module.forecast_series(
            replace(
                series,
                points=(replace(series.points[0], published=False), *series.points[1:]),
            )
        )


@pytest.mark.parametrize("value", ["-1", "1.5"])
def test_invalid_count_history_is_not_forecast(value):
    from decimal import Decimal

    with pytest.raises(ValueError, match="count history"):
        replace(construction().points[0], value=Decimal(value))


def test_published_hotel_adr_and_capex_units_are_not_renamed():
    from test_forecast import evidence

    base = released("earner_count")
    hotel = replace(
        base,
        key="hotel_demand_and_room_rates",
        table="pub_hotel_monthly",
        input_class="public",
        subject="national",
        measure="adr",
        unit="qar",
        admission=evidence("pub_hotel_monthly"),
        sources=(chain("pub_hotel_monthly"),),
        families=(),
        partition="",
        protected_table="",
        points=tuple(replace(p, measure="adr", unit="qar") for p in base.points),
    )
    assert isinstance(module.forecast_series(hotel), module.ForecastResult)
    assert isinstance(
        module.forecast_series(
            replace(hotel, level="municipality", subject="municipality")
        ),
        module.ForecastNotOffered,
    )
    base = construction()
    investment = replace(
        base,
        key="announced_investment",
        table="fdi_projects",
        subject="sector",
        measure="announced_capex",
        unit="usd_million",
        admission=evidence("fdi_projects"),
        sources=(chain("fdi_projects"),),
        points=tuple(
            replace(p, measure="announced_capex", unit="usd_million")
            for p in base.points
        ),
    )
    result = module.forecast_series(investment)
    assert isinstance(result, module.ForecastResult)
    assert result.value.unit == "usd_million"


@pytest.mark.parametrize(
    "geography,kind",
    [
        ("national", "national"),
        ("district:invented", "public"),
        ("area_shape:invented", "area_shape"),
    ],
)
def test_municipal_series_cannot_be_relabelled_as_another_geography(geography, kind):
    series = replace(
        construction(),
        geography=geography,
        geography_kind=kind,
        source_geography=geography,
    )
    assert isinstance(module.forecast_series(series), module.ForecastNotOffered)


@pytest.mark.parametrize("key", ["stayer_index", "pay_level"])
def test_released_municipal_label_cannot_admit_district_geography(key):
    series = replace(
        released(key),
        level="municipality",
        geography="district:x",
        geography_kind="public",
    )
    assert isinstance(module.forecast_series(series), module.ForecastNotOffered)


@pytest.mark.parametrize(
    "key",
    ["pay_level", "earner_count", "wage_bill", "stayer_index", "employment_by_area"],
)
def test_released_series_cannot_use_user_scenario_geography(key):
    series = replace(
        released(key),
        geography="user_scenario:z",
        geography_kind="user_scenario",
    )
    assert isinstance(module.forecast_series(series), module.ForecastNotOffered)


@pytest.mark.parametrize(
    "key,level,geography,kind",
    [
        ("stayer_index", "municipality", "municipality:x", "public"),
        ("pay_level", "municipality", "municipality:x", "public"),
        ("pay_level", "area", "area_shape:x", "area_shape"),
        ("pay_level", "area", "release_units:x", "release_units"),
        ("earner_count", "area", "release_units:x", "release_units"),
        ("wage_bill", "area", "area_shape:x", "area_shape"),
        ("employment_by_area", "area", "release_units:x", "release_units"),
    ],
)
def test_released_geography_binding_keeps_valid_routes(key, level, geography, kind):
    series = replace(
        released(key),
        level=level,
        geography=geography,
        geography_kind=kind,
        # Source-geography and source-breakdown equality apply only to Public input.
        source_breakdown=(("fixture", "source_only"),),
    )
    assert isinstance(module.forecast_series(series), module.ForecastResult)


def test_source_less_request_needs_no_invented_series_chain_or_history():
    check = getattr(module, "forecast_source_refusal", None)
    assert check is not None, "source-only refusal boundary missing"
    result = check("producer_prices")
    assert result.reason == "no_source_table"
    assert result.facts == ()
    assert (
        check("construction_pipeline") is None
    )  # permits validation, not a mounted-data claim
    assert isinstance(check("licence_net"), module.ForecastNotOffered)
