"""Public layer HTTP contracts and class-boundary/source-chain plants."""

import json
from decimal import Decimal
from pathlib import Path

import pytest
from product.tests.public_layer_render_fixture import seed_contract_rows
from product.tests.test_tools_http import service as service

from eii_core.facts import Fact, validate_chain

PUBLIC_KEYS = (
    "public_places",
    "land_prices",
    "rail_plan",
    "health_centres",
    "zoning",
    "commercial_points",
    "address_points",
    "parcels",
    "landmarks",
    "fdi_projects",
    "property_prices",
    "night_lights",
    "zone_electricity_growth",
)


@pytest.mark.parametrize("key", PUBLIC_KEYS)
def test_all_public_layers_and_lineage(service, key):
    client, ledger, store, _calls = service
    response = client.get(
        "/api/layers/" + key + ("?month_key=2026-03" if key == "night_lights" else "")
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok" and body["payload"]["layers"][0]["features"]
    for item in body["facts"]:
        fact = Fact.model_validate_json(json.dumps(item))
        assert (
            validate_chain(
                fact.lineage_ref,
                store.tables["fact_lineage"],
                store.tables["source_registry"],
            )
            is None
        )
    assert ledger.rows() == []


@pytest.mark.parametrize(
    "query",
    [
        "month_key=bad",
        "month_key=2026-13",
        "month_key=2026-03&month_key=2026-03",
        "other=x",
    ],
)
def test_layer_closed_queries(service, query):
    client, *_ = service
    assert client.get("/api/layers/night_lights?" + query).status_code == 422
    assert client.get("/api/layers/land_prices?" + query).status_code == 422


def test_unknown_unserved_and_month_no_data(service):
    client, *_ = service
    assert client.get("/api/layers/unknown").status_code == 404
    assert client.get("/api/layers/presence").status_code == 501
    assert (
        client.get("/api/layers/night_lights?month_key=2030-01").json()["status"]
        == "NO_DATA"
    )


def test_hero_and_land_integration_fixtures(service):
    client, *_ = service
    for key, fixture in [
        ("zone_electricity_growth", "hero-layer"),
        ("land_prices", "land-price-layer"),
    ]:
        body = client.get("/api/layers/" + key).json()
        expected = json.loads(
            Path("web/tests/fixtures/" + fixture + ".json").read_text()
        )
        assert body == expected
    hero = client.get("/api/layers/zone_electricity_growth").json()["payload"][
        "layers"
    ][0]
    assert len(hero["features"]) == 5
    assert {r["reason_key"] for r in hero["not_ranked"]} == {
        "below_ranking_floor",
        "no_denominator",
        "missing_input",
    }
    assert all(
        set(r) == {"feature_id", "ring", "reason_key", "name_segments"}
        for r in hero["not_ranked"]
    )
    land = client.get("/api/layers/land_prices").json()["payload"]["layers"][0]
    assert [g["group_key"] for g in land["class_breaks"]] == [
        "invented_commercial",
        "invented_residential",
    ]
    by = {f["feature_id"]: f for f in land["features"]}
    commercial = [f for f in by.values() if f["class_group"] == "invented_commercial"]
    assert [
        next(f for f in commercial if f["fact_id"] == b["fact_id"])[
            "feature_id"
        ].rsplit(":", 1)[-1]
        for b in land["class_breaks"][0]["breaks"]
    ] == list("dhj")
    assert [b["class_id"] for b in land["class_breaks"][0]["breaks"]] == [
        "band_low",
        "band_mid_low",
        "band_mid",
    ]
    for g in land["class_breaks"]:
        assert all(set(b) == {"class_id", "fact_id"} for b in g["breaks"])


def test_broken_chain_never_emits_feature(service):
    client, _ledger, store, _calls = service
    store.tables["fact_lineage"] = []
    assert client.get("/api/layers/land_prices").json()["facts"] == []


def test_classless_feature_refused_before_emission(service):
    from unittest.mock import patch

    client, *_ = service
    with patch(
        "eii_product.api.public_layers.class_group",
        return_value={"group_key": None, "breaks": []},
    ):
        response = client.get("/api/layers/land_prices")
    assert response.status_code == 500
    assert set(response.json()) == {"error"}


@pytest.mark.parametrize(
    "key,table",
    [
        ("land_prices", "pub_land_price"),
        ("public_places", "pub_place"),
        ("night_lights", "pub_night_lights"),
        ("fdi_projects", "fdi_projects"),
    ],
)
def test_row_source_must_belong_to_its_chain(service, key, table):
    client, _ledger, store, _calls = service
    store.tables[table] = [
        {**row, "source_id": "INVENTED-unregistered-source"}
        for row in store.tables[table]
    ]
    body = client.get(
        "/api/layers/" + key + ("?month_key=2026-03" if key == "night_lights" else "")
    ).json()
    assert not any(f["lineage_ref"] == "lin_" + table for f in body["facts"])


def test_hero_without_rankable_values_is_no_data(service):
    client, _ledger, store, _calls = service
    store.tables["pub_zone_utility"] = [
        {**r, "value": Decimal(100)} for r in store.tables["pub_zone_utility"]
    ]
    body = client.get("/api/layers/zone_electricity_growth").json()
    assert body["status"] == "NO_DATA" and body["facts"] == []


@pytest.mark.parametrize(
    "announced,kind",
    [
        ("2025", "calendar_year"),
        ("2025-03", "calendar_month"),
        ("2025-03-04", "calendar_date"),
    ],
)
def test_fdi_preserves_published_date_precision(service, announced, kind):
    client, _ledger, store, _calls = service
    store.tables["fdi_projects"] = [
        {**r, "announced": announced} for r in store.tables["fdi_projects"]
    ]
    body = client.get("/api/layers/fdi_projects").json()
    feature = body["payload"]["layers"][0]["features"][0]
    assert feature["announced"]["referenceKind"] == kind
    assert feature["announced"]["value"] == announced


def test_fdi_gatherer_copies_registered_credit_not_publisher(service):
    client, *_ = service
    body = client.get("/api/layers/fdi_projects").json()
    assert (
        body["payload"]["credits"]["gatherer"]
        == body["payload"]["sources"][0]["attribution"]
    )


def test_fdi_published_fields_fact_slots_filters_and_placement(service):
    client, _ledger, store, _calls = service
    seed_contract_rows(store)
    body = client.get("/api/layers/fdi_projects").json()
    features = body["payload"]["layers"][0]["features"]
    assert len(features) == 4
    feature = features[0]
    assert feature["place_key"] == "INVENTED-landmark-a"
    assert body["payload"]["gazetteer_points"] == ["INVENTED-landmark-a"]
    assert set(body["payload"]["filter_options"]) == {
        "sector",
        "source_country",
        "period",
        "stated_location",
    }
    facts = {fact["fact_id"]: fact for fact in body["facts"]}
    slots = [
        feature[key]
        for key in ("capex_fact_id", "jobs_fact_id", "lon_fact_id", "lat_fact_id")
    ]
    assert len(set(slots)) == 4
    assert [(facts[key]["value"], facts[key]["unit"]) for key in slots] == [
        (12.5, "usd_million"),
        (12.5, "announced_jobs"),
        (1.5, "decimal_degree"),
        (1.25, "decimal_degree"),
    ]
    for name, value in store.tables["fdi_projects"][0].items():
        if name in {"source_id", "capex_value", "jobs", "lng", "lat", "announced"}:
            continue
        segments = feature["field_segments"][name]
        assert "".join(s.get("text", s.get("value", "")) for s in segments) == str(
            value
        )
        for segment in segments:
            if segment["kind"] == "reference":
                assert facts[segment["recordId"]]["value"] == str(value)
    assert "position" not in features[1]
    assert features[2]["position"] == [1, 1]


def test_mixed_places_preserve_record_source_and_release(service):
    client, _ledger, store, _calls = service
    seed_contract_rows(store)
    body = client.get("/api/layers/public_places").json()
    features = body["payload"]["layers"][0]["features"]
    assert {feature["source_id"] for feature in features} == {
        store.tables["pub_place"][0]["source_id"],
        "INVENTED-fsq-source",
    }
    sources = {source["sourceId"]: source for source in body["payload"]["sources"]}
    assert sources["INVENTED-fsq-source"]["sourceRelease"]["value"] == "2025-01-10"
    assert (
        sources["INVENTED-fsq-source"]["sourceRelease"]["referenceKind"]
        == "calendar_date"
    )


@pytest.mark.parametrize("release", [None, "2025-02-29", "2025-01"])
def test_fsq_release_reference_refuses_missing_or_invalid_date(service, release):
    client, _ledger, store, _calls = service
    seed_contract_rows(store)
    store.tables["pub_place_fsq"] = [
        {**row, "source_release": release} for row in store.tables["pub_place_fsq"]
    ]
    response = client.get("/api/layers/public_places")
    assert response.status_code == 500 and set(response.json()) == {"error"}


def test_fsq_source_cannot_claim_two_release_dates(service):
    client, _ledger, store, _calls = service
    seed_contract_rows(store)
    first = store.tables["pub_place_fsq"][0]
    store.tables["pub_place_fsq"] = [
        first,
        {
            **first,
            "fsq_place_id": "INVENTED-fsq-second",
            "source_release": "2025-02-06",
        },
    ]
    response = client.get("/api/layers/public_places")
    assert response.status_code == 500 and set(response.json()) == {"error"}


def test_fdi_capex_unit_is_never_assumed(service):
    client, _ledger, store, _calls = service
    seed_contract_rows(store)
    store.tables["fdi_projects"] = [
        {**store.tables["fdi_projects"][0], "capex_unit": "INVENTED-unsupported"}
    ]
    assert client.get("/api/layers/fdi_projects").status_code == 500


def test_fdi_null_fields_and_published_zero_are_not_filled_or_dropped(service):
    client, _ledger, store, _calls = service
    seed_contract_rows(store)
    first = store.tables["fdi_projects"][0]
    store.tables["fdi_projects"] = [
        {
            **first,
            "capex_value": Decimal(0),
            "jobs": Decimal(0),
            "sub_sector": None,
            "place_key": None,
            "lat": None,
            "lng": None,
        }
    ]
    body = client.get("/api/layers/fdi_projects").json()
    feature = body["payload"]["layers"][0]["features"][0]
    facts = {fact["fact_id"]: fact for fact in body["facts"]}
    assert facts[feature["capex_fact_id"]]["value"] == 0
    assert facts[feature["jobs_fact_id"]]["value"] == 0
    assert "sub_sector" not in feature["field_segments"]
    assert "position" not in feature
    assert body["payload"]["gazetteer_points"] == []


def test_fdi_field_verification_failure_refuses_the_complete_route(service):
    """Plant a failed field-chain verification after the primary binding passed."""
    from unittest.mock import patch

    from eii_product.api.public_layers import LayerRead

    client, _ledger, store, _calls = service
    seed_contract_rows(store)
    original = LayerRead.fact

    def fail_field(ctx, table, metric, *args, **kwargs):
        return (
            None
            if metric == "fdi_field"
            else original(ctx, table, metric, *args, **kwargs)
        )

    with patch.object(LayerRead, "fact", fail_field):
        response = client.get("/api/layers/fdi_projects")
    assert response.status_code == 500 and set(response.json()) == {"error"}
