"""S3-T25: offline resolve on the existing typed route and exact key handoff."""

from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import pytest
from product.tests.public_http_support import Client
from product.tests.test_shapes_http import refused
from product.tests.test_tools_http import KEYS, CardStore
from public_release_fixture import _resolve_tables

from eii_product.api.app import create_app
from eii_product.ledger.local import LocalLedger
from eii_product.store.normalise import hold_geometry
from eii_product.store.protocol import QueryResult
from eii_product.store.registry import PACKAGED, require_query
from eii_product.tools.make_area import make_area
from eii_product.tools.resolve import QUERY_NAMES


class ResolveStore(CardStore):
    """Invented named-query projection; never real-store parity evidence."""

    def __init__(self):
        self.tables = {table.name: table.rows for table in _resolve_tables()}
        self.calls = []

    def fetch(self, query, params):
        query = require_query(PACKAGED, query)
        self.calls.append(query.name)
        if query.name in QUERY_NAMES or query.name == "make_area_gazetteer_point":
            table = {
                "resolve_gazetteer": "gazetteer",
                "resolve_district": "district",
                "resolve_zone": "zone",
                "resolve_municipality": "municipality",
                "resolve_graph_node": "graph_node",
                "resolve_graph_edge": "graph_edge",
                "make_area_gazetteer_point": "gazetteer",
            }[query.name]
            rows = self.tables[table]
            if params:
                rows = [r for r in rows if r["place_key"] == params["place_key"]]
            names = tuple(r.name for r in query.returns)
            return QueryResult(
                names,
                tuple(
                    tuple(
                        hold_geometry(r[k].hex()) if isinstance(r[k], bytes) else r[k]
                        for k in names
                    )
                    for r in sorted(rows, key=lambda r: str(r[names[0]]))
                ),
            )
        return super().fetch(PACKAGED.lookup(query.name), params)


@pytest.fixture
def service(tmp_path):
    store = ResolveStore()
    attempts = []

    def forbidden(*args, **kwargs):
        attempts.append("transport")
        raise RuntimeError("INVENTED-transport")

    ledger = LocalLedger(tmp_path / "ledger.sqlite")
    app = create_app(
        Path("product/tests/fixtures/tiles"),
        store=store,
        ledger=ledger,
        key_reader=lambda: None,
        offline_reader=lambda: True,
        transport_factory=forbidden,
        opener=forbidden,
        fc_setting_reader=lambda: None,
    )
    yield Client(app), store, ledger, attempts
    ledger.close()


def request(text="INVENTED-Garden", lang="en", kind="place"):
    return {"text": text, "lang": lang, "kind": kind}


@pytest.mark.parametrize(
    "lang,label", [("en", "INVENTED-Garden"), ("ar", "حديقة مخترعة")]
)
def test_resolve_mounted_envelope_and_read_once(service, lang, label):
    client, store, ledger, attempts = service
    for _ in range(2):
        response = client.post("/api/tools/resolve", json=request(label, lang))
        assert response.status_code == 200
        body = response.json()
        assert set(body) == KEYS
        assert body["tool"] == "resolve" and body["status"] == "OK"
        assert body["release_id"] == store.release_id
        assert body["facts"] == body["blocks"] == body["caveat_keys"] == []
        assert body["payload"] == {
            "candidates": [
                {
                    "kind": "place",
                    "key": "INVENTED-landmark-a",
                    "label_en": "INVENTED-Garden",
                    "label_ar": "حديقة مخترعة",
                    "source": "gazetteer",
                    "match": "exact",
                }
            ]
        }
    assert store.calls == list(QUERY_NAMES)
    assert len(ledger.rows()) == 2
    assert label not in str(ledger.rows())
    assert client.app.state.sessions.count == 0
    assert attempts == []


@pytest.mark.parametrize(
    "body",
    [
        {**request(), "extra": "INVENTED"},
        {"lang": "en", "kind": "place"},
        request(""),
        request("a" * 201),
        request(lang="fr"),
        request(kind="company"),
        request(text=True),
    ],
)
def test_resolve_closed_input_before_reads(service, body):
    client, store, ledger, attempts = service
    refused(client.post("/api/tools/resolve", json=body))
    assert store.calls == [] and ledger.rows() == [] and attempts == []


def test_resolve_unknown_tool_and_http_refusals(service):
    client, store, ledger, _ = service
    refused(
        client.post("/api/tools/INVENTED-unknown", json=request()), 404, "NOT_FOUND"
    )
    refused(client.post("/api/tools/resolve?text=INVENTED", json=request()))
    refused(client.post("/api/tools/resolve", content=b"{"))
    refused(client.post("/api/tools/resolve", json=[]))
    refused(
        client.post(
            "/api/tools/resolve", json=request(), headers={"content-type": "text/plain"}
        )
    )
    assert store.calls == [] and ledger.rows() == []


@pytest.mark.parametrize("lang", ["en", "ar"])
def test_selected_key_is_exact_area_and_null_cell_stays_null(service, lang):
    client, store, _, attempts = service
    for key, en, ar, null in [
        ("INVENTED-landmark-a", "INVENTED-Garden", "حديقة مخترعة", False),
        ("district:INVENTED-null", "INVENTED-Court", "ساحة مخترعة", True),
    ]:
        response = client.post(
            "/api/tools/resolve", json=request(en if lang == "en" else ar, lang)
        )
        assert response.status_code == 200
        candidate = response.json()["payload"]["candidates"][0]
        assert candidate["key"] == key
        args = {"place_key": candidate["key"], "mode": "distance", "cutoff": 250}
        expected = make_area(
            store,
            {**args, "place_key": key},
            client.app.state.area_contexts.for_playbook("site_check"),
        )
        area = client.post("/api/tools/make_area", json=args)
        assert area.status_code == 200 and area.json()["status"] == "OK"
        payload = area.json()["payload"]
        from fastapi.encoders import jsonable_encoder

        assert payload == jsonable_encoder(expected.payload)
        point = next(
            row for row in store.tables["gazetteer"] if row["place_key"] == key
        )
        assert payload["outline"] == {
            "type": "Circle",
            "coordinates": [float(point["lon"]), float(point["lat"])],
            "radius_m": args["cutoff"],
        }
        assert (payload["record"]["anchor_cell"] is None) is null
        if null:
            assert payload["units"] == {} and payload["snap_report"] is None
        assert payload["point_feature_ids"] is not None
        assert payload["record"]["shape"] == "radius"
    assert attempts == []


@pytest.mark.parametrize("lang", ["en", "ar"])
def test_outside_land_and_no_match(service, lang):
    client, _, ledger, _ = service
    for label, status in [
        ("INVENTED-Outside" if lang == "en" else "خارج مخترع", "OUT_OF_SCOPE"),
        ("INVENTED-missing" if lang == "en" else "غير موجود مخترع", "NO_DATA"),
    ]:
        response = client.post("/api/tools/resolve", json=request(label, lang))
        assert response.status_code == 200
        body = response.json()
        assert set(body) == KEYS and body["status"] == status
        assert body["payload"] is None and body["facts"] == []
    assert len(ledger.rows()) == 2


@pytest.mark.parametrize(
    "lang,label", [("en", "INVENTED-Craft"), ("ar", "حرفة مخترعة")]
)
def test_activity_candidate_and_both_kinds(service, lang, label):
    client, _, _, _ = service
    for kind in ("activity", "both"):
        response = client.post("/api/tools/resolve", json=request(label, lang, kind))
        assert response.status_code == 200
        candidates = response.json()["payload"]["candidates"]
        assert candidates == [
            {
                "kind": "activity",
                "key": "activity:INVENTED-craft",
                "label_en": "INVENTED-Craft",
                "label_ar": "حرفة مخترعة",
                "source": "activity_spine",
                "match": "exact",
                "commerce_code": "INVENTED-code",
                "isic_class": "INVENTED-class",
                "place_category": "INVENTED-category",
                "not_mappable": False,
            }
        ]


def test_malformed_candidate_from_resolver_never_crosses_projection(service):
    from eii_product.tools.resolve import ResolveContext, resolve

    client, store, ledger, _ = service
    valid = resolve(store, request(), ResolveContext(PACKAGED))
    assert valid.status == "OK"
    poisoned = replace(
        valid,
        payload={
            "candidates": [{**valid.payload["candidates"][0], "extra": "INVENTED"}]
        },
    )
    with patch("eii_product.api.tools.resolve", return_value=poisoned):
        refused(client.post("/api/tools/resolve", json=request()), 500, "INTERNAL")
    assert ledger.rows() == []


@pytest.mark.parametrize(
    "change",
    [
        {"tool": "INVENTED-tool"},
        {"release_id": "cd" * 32},
        {"status": "INVENTED-status"},
        {"status": "SUPPRESSED", "payload": None},
        {"status": "NO_DATA"},
        {"status": "OUT_OF_SCOPE"},
        {"payload": None},
        {"payload": {"candidates": []}},
    ],
)
def test_resolve_output_status_identity_and_shape_are_closed(service, change):
    from eii_product.tools.resolve import ResolveContext, resolve

    client, store, ledger, _ = service
    valid = resolve(store, request(), ResolveContext(PACKAGED))
    with patch("eii_product.api.tools.resolve", return_value=replace(valid, **change)):
        refused(client.post("/api/tools/resolve", json=request()), 500, "INTERNAL")
    assert ledger.rows() == []


def test_resolve_cap_normalisation_and_max_text(service):
    client, store, _, _ = service
    base = store.tables["gazetteer"][0]
    store.tables["gazetteer"] = [
        {**base, "place_key": "INVENTED-choice-" + suffix}
        for suffix in reversed("abcdefgh")
    ]
    response = client.post("/api/tools/resolve", json=request("invented-garden"))
    assert response.status_code == 200
    candidates = response.json()["payload"]["candidates"]
    assert [c["key"] for c in candidates] == [
        "INVENTED-choice-" + suffix for suffix in "abcde"
    ]
    assert all(c["match"] == "normalised" for c in candidates)
    response = client.post("/api/tools/resolve", json=request("a" * 200))
    assert response.status_code == 200 and response.json()["status"] == "NO_DATA"


@pytest.mark.parametrize(
    "key", ["district:INVENTED-null", "zone:INVENTED_zone", "municipality:7"]
)
@pytest.mark.parametrize("lang", ["en", "ar"])
def test_administrative_key_from_frame_reaches_exact_null_cell_area(service, key, lang):
    client, store, _, _ = service
    store.tables["gazetteer"] = [
        {**row, "place_key": key, "kind": key.split(":")[0]}
        if row["place_key"] == "district:INVENTED-null"
        else row
        for row in store.tables["gazetteer"]
    ]
    found = client.post(
        "/api/tools/resolve",
        json=request("INVENTED-Court" if lang == "en" else "ساحة مخترعة", lang),
    )
    assert found.status_code == 200
    candidate = found.json()["payload"]["candidates"][0]
    assert candidate["key"] == key
    made = client.post(
        "/api/tools/make_area",
        json={"place_key": candidate["key"], "mode": "distance", "cutoff": 250},
    )
    assert made.status_code == 200 and made.json()["status"] == "OK"
    assert made.json()["payload"]["record"]["anchor_cell"] is None
    assert made.json()["payload"]["outline"] == {
        "type": "Circle",
        "coordinates": [2.5, 2.5],
        "radius_m": 250,
    }


@pytest.mark.parametrize(
    "key",
    [
        "district:",
        "district:../INVENTED",
        "activity:INVENTED",
        "register:INVENTED",
        "district:" + "7" * 8,
        "zone:INVENTED-" + "7" * 11,
    ],
)
def test_administrative_key_guard_refuses_foreign_or_unsafe_keys_before_reads(
    service, key
):
    client, store, ledger, _ = service
    refused(
        client.post(
            "/api/tools/make_area",
            json={"place_key": key, "mode": "distance", "cutoff": 250},
        )
    )
    assert store.calls == [] and ledger.rows() == []


@pytest.mark.parametrize(
    "key,offline", [(None, False), (None, True), ("INVENTED-key", True)]
)
@pytest.mark.parametrize("lang", ["en", "ar"])
def test_address_off_counts_even_caught_transport_attempts(service, key, offline, lang):
    _, store, ledger, attempts = service

    def forbidden(*args, **kwargs):
        attempts.append("transport")
        raise RuntimeError("INVENTED-transport")

    client = Client(
        create_app(
            Path("product/tests/fixtures/tiles"),
            store=store,
            ledger=ledger,
            key_reader=lambda: key,
            offline_reader=lambda: offline,
            transport_factory=forbidden,
            opener=forbidden,
            fc_setting_reader=lambda: None,
        )
    )
    assert client.post("/api/tools/resolve", json=request(lang=lang)).status_code == 200
    refused(
        client.post(
            "/api/address-search", json={"text": "INVENTED-address", "lang": lang}
        ),
        404,
        "NOT_FOUND",
    )
    assert attempts == []


def test_mounted_route_executes_on_embedded_release(tmp_path):
    """Real embedded execution; PostgreSQL remains the lead's live proof."""
    from live_public_playbook import RESOLVE_ROUTE_QUERIES, resolve_route_cases
    from public_release_fixture import build_fixture
    from test_live_public_release_load import embedded_fixture_store

    folder = tmp_path / "release"
    identity = build_fixture(folder, resolver=True)
    store = embedded_fixture_store(folder, identity)
    ledger = LocalLedger(tmp_path / "ledger.sqlite")
    try:
        results, trace = resolve_route_cases(store, ledger)
        assert RESOLVE_ROUTE_QUERIES <= set(trace)
        assert len(results) == 14
    finally:
        ledger.close()
        store.close()
