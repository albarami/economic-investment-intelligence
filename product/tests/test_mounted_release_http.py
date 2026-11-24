"""Mounted invented release: HTTP contracts, loaded provenance and refusal plants."""

import json
from pathlib import Path

import pytest
from product.tests.public_http_support import Client
from public_release_fixture import build_fixture
from test_live_public_release_load import _RecordingPostgres

from eii_product.api.app import create_app
from eii_product.api.public_layers import PUBLIC_LAYER_KEYS
from eii_product.api.startup import developer_policy
from eii_product.config import ConfigError
from eii_product.ledger.local import LocalLedger
from eii_product.store.embedded import EmbeddedStore
from eii_product.store.loader import _parquet_rows, run_load
from eii_product.store.protocol import QueryResult
from eii_product.store.receipt import ReceiptRefusal
from eii_product.store.registry import PACKAGED
from eii_product.store.release_check import check_release, manifest_rows


@pytest.fixture(scope="module")
def loaded(tmp_path_factory):
    folder = tmp_path_factory.mktemp("mounted-public")
    identity = build_fixture(folder, cards=True)
    checked = check_release(folder)
    rows = {
        entry["name"]: _parquet_rows(
            folder / entry["file"], checked.schemas[entry["name"]]
        )
        for entry in checked.document["tables"]
    }
    rows["release_manifest"] = manifest_rows(checked.document)
    connection = _RecordingPostgres(rows, names=tuple(rows), columns=checked.schemas)
    assert (
        run_load(
            folder,
            host="invented.invalid",
            port=1,
            database="INVENTED",
            connect=lambda **kw: connection,
        )
        == 0
    )
    yield folder, identity, rows


@pytest.fixture(scope="module")
def mounted(loaded, tmp_path_factory):
    tmp_path = tmp_path_factory.mktemp("mounted-ledger")
    folder, identity, rows = loaded
    store = EmbeddedStore(folder / "release.duckdb", identity, PACKAGED)
    ledger = LocalLedger(tmp_path / "ledger.sqlite")
    app = create_app(
        Path("product/tests/fixtures/tiles"),
        store=store,
        ledger=ledger,
        fc_setting_reader=lambda: None,
        release_dir=folder,
        startup_policy=developer_policy(folder),
    )
    yield Client(app), store, rows
    ledger.close()
    store.close()


def test_mounted_release_closed_projection(mounted):
    client, store, rows = mounted
    response = client.get(
        "/api/release", headers={"Origin": "https://invented.invalid"}
    )
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {
        "release_id",
        "release_kind",
        "rules_version_id",
        "tables",
        "hour_keys",
        "day_keys",
        "month_keys",
        "basemap_url",
    }
    assert body["release_id"] == store.release_id
    assert body["release_kind"] == "public_only"
    assert body["rules_version_id"] == rows["release_manifest"][0]["rules_version_id"]
    assert body["tables"] == [
        {"releaseId": store.release_id, "tableName": r["table_name"]}
        for r in sorted(rows["release_manifest"], key=lambda r: r["table_name"])
    ]
    assert response.headers["content-type"] == "application/json"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert "access-control-allow-origin" not in response.headers


@pytest.mark.parametrize("key", PUBLIC_LAYER_KEYS)
def test_emitted_fact_chain_comes_from_loaded_rows(mounted, key):
    client, store, rows = mounted
    body = client.get("/api/layers/" + key).json()
    assert body["facts"]
    for fact in body["facts"]:
        response = client.get("/api/facts/" + fact["fact_id"] + "/lineage")
        assert response.status_code == 200
        chain = response.json()
        assert set(chain) == {"fact_id", "release_id", "lineage", "sources", "binding"}
        assert chain["fact_id"] == fact["fact_id"]
        assert chain["release_id"] == store.release_id
        line = chain["lineage"]
        held = [
            r for r in rows["fact_lineage"] if r["lineage_id"] == fact["lineage_ref"]
        ]
        assert line["tableName"] == held[0]["table_name"]
        assert line["method"] + "@" + line["methodVersion"] == held[0]["transform"]
        assert line["sourceIds"] == sorted({r["source_id"] for r in held})
        for source in chain["sources"]:
            original = next(
                r
                for r in rows["source_registry"]
                if r["source_id"] == source["sourceId"]
            )
            assert source == dict(
                sourceId=original["source_id"],
                kind=original["kind"],
                inputClass="public",
                publisher=original["publisher"],
                datasetOrPage=original["title"],
                licenceOrTerms=original["licence"],
                retrievalDate=str(original["retrieved_on"]),
                sha256=original["sha256"],
            )
        assert chain["binding"]["metricKey"]
        assert "value" not in chain["binding"]


@pytest.mark.parametrize(
    "name",
    ("bad", "f_" + "a" * 31, "f_" + "A" * 32, "f_" + "a" * 1000, "%2e%2e%2fsecret"),
)
def test_malformed_fact_ids_refused(mounted, name):
    client, *_ = mounted
    response = client.get("/api/facts/" + name + "/lineage")
    assert response.status_code == (404 if "%2f" in name else 422)
    assert "value" not in response.json()


def test_foreign_fact_never_decodes_identifier(mounted):
    client, *_ = mounted
    assert client.get("/api/facts/f_" + "e" * 32 + "/lineage").status_code == 404


@pytest.mark.parametrize(
    "path", ("/api/release", "/api/facts/f_" + "a" * 32 + "/lineage")
)
def test_gets_refuse_query_and_body(mounted, path):
    client, *_ = mounted
    assert client.get(path + "?extra=INVENTED").status_code == 422
    assert client.request("GET", path, b"{}").status_code == 422


@pytest.mark.parametrize(
    "column,changed",
    (
        ("sha256", "cd" * 32),
        ("transform", "invented.fabricated@v9"),
        ("table_name", "pub_land_price"),
        ("input_class", "synthetic"),
        ("publisher", ""),
        ("licence", ""),
        ("title", ""),
        ("retrieved_on", None),
        ("kind", "synthetic_feed"),
        ("release_id", "ef" * 32),
    ),
)
def test_corrupt_loaded_chain_refuses_value_and_geometry(
    mounted, monkeypatch, column, changed
):
    client, store, _rows = mounted
    fetch = store.fetch

    def altered(query, params):
        result = fetch(query, params)
        if column == "sha256" and query.name != "sector_facts_sources":
            return result
        if column == "table_name" and query.name == "public_release_manifest":
            return result
        if column not in result.columns:
            return result
        index = result.columns.index(column)
        return QueryResult(
            result.columns,
            tuple(
                tuple(changed if i == index else v for i, v in enumerate(row))
                for row in result.rows
            ),
        )

    monkeypatch.setattr(store, "fetch", altered)
    response = client.get("/api/layers/parcels")
    assert response.status_code != 200 or (
        response.json()["facts"] == []
        and response.json()["payload"]["layers"][0]["features"] == []
    )


def test_unverified_mount_and_pending_receipt_refuse(loaded, mounted, tmp_path):
    folder, _identity, _ = loaded
    store = mounted[1]
    ledger = LocalLedger(tmp_path / "ledger.sqlite")
    try:
        app = create_app(
            Path("product/tests/fixtures/tiles"),
            store=store,
            ledger=ledger,
            fc_setting_reader=lambda: None,
        )
        assert Client(app).get("/api/release").status_code == 503
        receipt_path = folder / "load_receipt.json"
        original = receipt_path.read_text()
        pending = json.loads(original)
        pending["state"] = "pending"
        try:
            receipt_path.write_text(json.dumps(pending))
            with pytest.raises(ReceiptRefusal, match="receipt_not_complete"):
                create_app(
                    Path("product/tests/fixtures/tiles"),
                    store=store,
                    ledger=ledger,
                    release_dir=folder,
                    startup_policy=developer_policy(folder),
                    fc_setting_reader=lambda: None,
                )
        finally:
            receipt_path.write_text(original)
    finally:
        ledger.close()


@pytest.mark.parametrize("target", ("summary", "project"))
def test_unknown_response_property_and_sanitized_failures(mounted, monkeypatch, target):
    client, *_ = mounted
    body = client.get("/api/layers/parcels").json()
    fact = body["facts"][0]
    mount = client.app.state.release_mount
    original = getattr(mount, target)

    def unknown(*args):
        return {**original(*args), "INVENTED-extra": "INVENTED-secret-path-query"}

    monkeypatch.setattr(mount, target, unknown)
    path = (
        "/api/release"
        if target == "summary"
        else "/api/facts/" + fact["fact_id"] + "/lineage"
    )
    response = client.get(path)
    assert response.status_code == 500
    assert set(response.json()) == {"error"}
    assert "INVENTED-secret-path-query" not in response.text


def test_opaque_lineage_is_not_a_table_name(mounted):
    client, *_ = mounted
    response = client.get("/api/layers/parcels")
    assert response.status_code == 200
    body = response.json()
    fact = body["facts"][0]
    chain = client.get("/api/facts/" + fact["fact_id"] + "/lineage").json()
    assert fact["lineage_ref"] == "lin_pub_parcel_invented_suffix"
    assert chain["lineage"]["tableName"] == "pub_parcel"


def test_foreign_release_and_unbound_metric_cannot_register(mounted):
    from eii_core.facts import Fact
    from eii_product.api.release import Binding

    client, *_ = mounted
    body = client.get("/api/layers/parcels").json()
    fact = Fact.model_validate(body["facts"][0])
    mount = client.app.state.release_mount
    with pytest.raises(ValueError, match="chain_refused"):
        mount.register(
            [
                (
                    fact.model_copy(update={"release_id": "ef" * 32}),
                    Binding(metricKey="parcel_area", qualifiers={}),
                )
            ]
        )
    with pytest.raises(ValueError, match="metric_unbound"):
        mount.register([(fact, Binding(metricKey="", qualifiers={}))])


@pytest.mark.parametrize(
    "name",
    (
        "public_release_manifest",
        "public_lineage_for_table",
        "sector_facts_lineage",
        "sector_facts_sources",
    ),
)
def test_each_absent_named_chain_link_refuses_geometry(mounted, monkeypatch, name):
    client, store, _ = mounted
    original = store.fetch

    def missing(query, params):
        result = original(query, params)
        return QueryResult(result.columns, ()) if query.name == name else result

    monkeypatch.setattr(store, "fetch", missing)
    response = client.get("/api/layers/parcels")
    assert response.status_code != 200 or response.json()["facts"] == []


@pytest.mark.parametrize(
    "tool,args",
    (
        ("night_lights", {"month_key": "2026-03"}),
        ("population_age_sex", {"split": "sex"}),
        ("venue_busyness", {"place_keys": ["INVENTED-venue-a"], "weekday": "monday"}),
    ),
)
def test_card_facts_keep_envelope_and_transport_binding(mounted, tool, args):
    from product.tests.test_tools_http import KEYS

    client, *_ = mounted
    if tool != "venue_busyness":
        shape = client.post(
            "/api/areas/shapes",
            json={
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [
                        [[0.5, 0.5], [2.5, 0.5], [2.5, 2.5], [0.5, 2.5], [0.5, 0.5]]
                    ],
                }
            },
        ).json()["shape_id"]
        area = client.post("/api/tools/make_area", json={"shape_id": shape}).json()[
            "payload"
        ]["area_id"]
        args = {**args, "area_id": area}
    response = client.post("/api/tools/" + tool, json=args)
    assert response.status_code == 200
    body = response.json()
    assert set(body) == KEYS and body["facts"]
    for fact in body["facts"]:
        chain = client.get("/api/facts/" + fact["fact_id"] + "/lineage").json()
        assert chain["fact_id"] == fact["fact_id"]
        binding = chain["binding"]
        assert binding["metricKey"] in {
            "night_lights_radiance",
            "population_grid_people",
            "venue_busyness_index",
        }
        assert set(binding) == {"metricKey", "presentation", "qualifiers"}
        assert set(fact) == {
            "fact_id",
            "value",
            "unit",
            "period",
            "geography",
            "provenance",
            "input_classes",
            "evidence_status",
            "reliability",
            "coverage_keys",
            "caveat_keys",
            "label_en",
            "label_ar",
            "lineage_ref",
            "release_id",
        }
        assert "value" not in body["payload"]


def test_transport_projection_record(mounted):
    """Component runner consumes real response JSON from the loaded fixture."""
    client, *_ = mounted
    body = client.get("/api/layers/zone_electricity_growth").json()
    summary = client.get("/api/release")
    assert summary.status_code == 200 and body["facts"]
    shape = client.post(
        "/api/areas/shapes",
        json={
            "geometry": {
                "type": "Polygon",
                "coordinates": [
                    [[0.5, 0.5], [2.5, 0.5], [2.5, 2.5], [0.5, 2.5], [0.5, 0.5]]
                ],
            }
        },
    ).json()["shape_id"]
    area = client.post("/api/tools/make_area", json={"shape_id": shape}).json()[
        "payload"
    ]["area_id"]
    cards = {
        tool: client.post("/api/tools/" + tool, json=args).json()
        for tool, args in (
            ("night_lights", {"area_id": area, "month_key": "2026-03"}),
            ("population_age_sex", {"area_id": area, "split": "sex"}),
            (
                "venue_busyness",
                {"place_keys": ["INVENTED-venue-a"], "weekday": "monday"},
            ),
        )
    }
    chains = {}
    for result in (body, *cards.values()):
        assert result["facts"]
        for fact in result["facts"]:
            response = client.get("/api/facts/" + fact["fact_id"] + "/lineage")
            assert response.status_code == 200
            chains[fact["fact_id"]] = response.json()
    print(
        "MOUNTED_PROJECTION="
        + json.dumps(
            dict(release=summary.json(), body=body, cards=cards, chains=chains)
        )
    )


def test_loaded_errors_never_expose_exception_text(mounted, monkeypatch, capsys):
    client, store, _ = mounted

    def failed(*args):
        raise RuntimeError("INVENTED-secret-path-query")

    monkeypatch.setattr(store, "fetch", failed)
    response = client.get("/api/release")
    assert response.status_code == 500
    assert set(response.json()["error"]) == {"code", "message_key", "error_id"}
    assert "INVENTED-secret-path-query" not in response.text + capsys.readouterr().out


@pytest.mark.parametrize(
    "field,value", (("engines", ["embedded"]), ("row_counts", {}), ("digests", {}))
)
def test_incomplete_complete_receipt_is_not_a_verified_mount(
    loaded, mounted, field, value
):
    from eii_product.api.release import MountedRelease

    folder, _, _ = loaded
    path = folder / "load_receipt.json"
    original = path.read_text()
    record = json.loads(original)
    record[field] = value
    try:
        path.write_text(json.dumps(record))
        with pytest.raises(ValueError, match="mount_unverified"):
            MountedRelease(mounted[1], folder)
    finally:
        path.write_text(original)


def test_live_projection_executes_the_inventory_on_embedded(loaded, mounted):
    import live_public_playbook as live

    _output, trace, _context = live.public_projection(mounted[1], loaded[0])
    assert set(trace) == set(live.public_query_names())


def test_venue_lineage_preserves_stored_row_citation(mounted):
    client, *_ = mounted
    result = client.post(
        "/api/tools/venue_busyness",
        json={"place_keys": ["INVENTED-venue-a"], "weekday": "monday"},
    ).json()
    entry = next(e for e in result["payload"]["entries"] if e.get("fact_id"))
    response = client.get("/api/facts/" + entry["fact_id"] + "/lineage")
    assert response.status_code == 200
    lineage = response.json()["lineage"]
    assert lineage["rowRetrievalDate"] == entry["retrieved_on"]
    assert lineage["providerUpdatedOn"] == entry["provider_updated_on"]


def test_ledger_failure_does_not_admit_an_unemitted_fact(
    loaded, mounted, tmp_path, monkeypatch
):
    from eii_product.tools.public_context_tools import venue

    folder, _, _ = loaded
    store = mounted[1]
    args = {"place_keys": ["INVENTED-venue-a"], "weekday": "wednesday"}
    expected = venue(store, args).facts[0].fact_id
    ledger = LocalLedger(tmp_path / "refusing-ledger.sqlite")
    try:
        client = Client(
            create_app(
                Path("product/tests/fixtures/tiles"),
                store=store,
                ledger=ledger,
                release_dir=folder,
                startup_policy=developer_policy(folder),
                fc_setting_reader=lambda: None,
            )
        )

        def failed(*args):
            raise RuntimeError("INVENTED-ledger-failure")

        monkeypatch.setattr(LocalLedger, "write", failed)
        assert client.post("/api/tools/venue_busyness", json=args).status_code == 500
        assert client.get("/api/facts/" + expected + "/lineage").status_code == 404
    finally:
        ledger.close()


def test_unconfigured_mount_names_no_basemap(mounted):
    summary = mounted[0].get("/api/release").json()
    assert "basemap_url" in summary
    assert summary["basemap_url"] is None


def test_configured_mount_names_the_same_origin_basemap(mounted, loaded, tmp_path):
    folder, _, _ = loaded
    store = mounted[1]
    ledger = LocalLedger(tmp_path / "map-ledger.sqlite")
    try:
        app = create_app(
            tmp_path / "tiles",
            store=store,
            ledger=ledger,
            release_dir=folder,
            startup_policy=developer_policy(folder),
            basemap_name="basemap.pmtiles",
            fc_setting_reader=lambda: None,
        )
        assert Client(app).get("/api/release").json()["basemap_url"] == (
            "/tiles/basemap.pmtiles"
        )
    finally:
        ledger.close()


@pytest.mark.parametrize(
    "name", ("../basemap.pmtiles", "other.pmtiles", "https://invented.invalid/map")
)
def test_basemap_configuration_refuses_unknown_names(name, tmp_path, mounted, loaded):
    from eii_product.api.release import MountedRelease

    with pytest.raises(ConfigError, match="basemap_name"):
        create_app(tmp_path, basemap_name=name, fc_setting_reader=lambda: None)
    with pytest.raises(ValueError, match="mount_unverified"):
        MountedRelease(mounted[1], loaded[0], basemap_name=name)
