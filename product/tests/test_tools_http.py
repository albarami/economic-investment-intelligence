"""Mounted closed Public tools, exact envelopes and identifier-only ledger."""

import json
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

import pytest
from product.tests.public_http_support import AreaStore, Client
from product.tests.test_shapes_http import polygon, refused

from eii_product.api.app import create_app
from eii_product.api.area_context import RoutingSource
from eii_product.ledger.local import LocalLedger
from eii_product.store.protocol import QueryResult, StoreRefusal

KEYS = {
    "tool",
    "call_id",
    "release_id",
    "engine",
    "status",
    "blocks",
    "facts",
    "payload",
    "caveat_keys",
}


class CardStore(AreaStore):
    def fetch(self, query, params):
        if query.name.startswith("make_area_"):
            return super().fetch(query, params)
        import re

        from eii_product.store.registry import PACKAGED, require_query

        query = require_query(PACKAGED, query)
        table = re.search(r"FROM (\w+) AS p", query.text)[1]
        rows = self.tables[table]
        for key, value in params.items():
            column = {
                "lineage": "lineage_id",
                "sources": "source_id",
                "month_key": "period",
                "place_keys": "place_id",
                "periods": "period",
            }.get(key, key)
            rows = [
                r
                for r in rows
                if (
                    r[column] in value
                    if isinstance(value, list)
                    else r[column] == value
                )
            ]
        names = tuple(r.name for r in query.returns)
        projected = [
            tuple(
                (
                    __import__(
                        "eii_product.store.normalise", fromlist=["hold_geometry"]
                    ).hold_geometry(r[k].hex().upper())
                    if isinstance(r.get(k), bytes)
                    else ("complete" if not r["partial_year"] else "partial")
                    if k == "completeness"
                    else r[k]
                )
                for k in names
            )
            for r in rows
        ]
        if "GROUP BY" in query.text:
            projected = list(dict.fromkeys(projected))
        return QueryResult(names, tuple(sorted(projected, key=repr)))


@pytest.fixture
def service(tmp_path):
    store = CardStore()
    ledger = LocalLedger(tmp_path / "ledger.sqlite")
    calls = []

    def route(mode, minutes, lat, lon):
        calls.append((mode, minutes))
        d = Decimal(".01")
        return (
            (lat - d, lon - d),
            (lat - d, lon + d),
            (lat + d, lon + d),
            (lat + d, lon - d),
            (lat - d, lon - d),
        )

    app = create_app(
        Path("product/tests/fixtures/tiles"),
        store=store,
        ledger=ledger,
        routing=RoutingSource.from_call(route),
        fc_setting_reader=lambda: None,
    )
    yield Client(app), ledger, store, calls
    ledger.close()


def shape_area(client):
    shape = client.post("/api/areas/shapes", json=polygon()).json()["shape_id"]
    response = client.post("/api/tools/make_area", json={"shape_id": shape})
    assert response.status_code == 200
    body = response.json()
    assert set(body) == KEYS
    assert "cells" not in body["payload"] and "cells" in body["payload"]["units"]
    return body["payload"]["area_id"]


def test_exact_envelope_ledger_and_shape_session(service):
    client, ledger, _store, _calls = service
    area = shape_area(client)
    for _ in range(2):
        body = client.post(
            "/api/tools/night_lights", json={"area_id": area, "month_key": "2026-03"}
        ).json()
        assert set(body) == KEYS
    rows = ledger.rows()
    assert len(rows) == 3 and len({r["answer_id"] for r in rows}) == 3
    assert rows[-1]["answer_id"] == body["call_id"]
    assert all(r["seat_key"] == "" and r["playbook"] == "site_check" for r in rows)
    assert area not in json.dumps(rows)
    assert client.app.state.sessions.count == 1
    other = Client(client.app)
    refused(other.post("/api/tools/make_area", json={"shape_id": area.split("/")[-1]}))


@pytest.mark.parametrize(
    "tool,body",
    [
        ("make_area", {"geometry": {}}),
        ("venue_busyness", {"place_keys": ["INVENTED-venue-a"], "extra": "INVENTED"}),
        (
            "make_area",
            {"latitude": True, "longitude": 1, "mode": "distance", "cutoff": 500},
        ),
        (
            "make_area",
            {"latitude": "1", "longitude": 1, "mode": "distance", "cutoff": 500},
        ),
        ("night_lights", {"area_id": "bad", "month_key": "2026-03", "extra": 1}),
        ("night_lights", {"area_id": "bad", "month_key": "2026-13"}),
        ("venue_busyness", {"place_keys": []}),
        ("venue_busyness", {"place_keys": ["1" * 8]}),
        ("venue_busyness", {"place_keys": ["1" * 11]}),
        ("venue_busyness", {"place_keys": ["INVENTED-a"] * 11}),
        ("venue_busyness", {"place_keys": ["INVENTED-venue-a"], "weekday": "Mon day"}),
        ("population_age_sex", {"area_id": "bad", "split": "age"}),
        *[
            (
                "make_area",
                {
                    "latitude": 1,
                    "longitude": 1,
                    "mode": "walk",
                    "cutoff": 5,
                    k: "INVENTED",
                },
            )
            for k in ("routing", "tile_folder", "routing_tiles")
        ],
    ],
)
def test_closed_body_refusals(service, tool, body):
    client, ledger, _store, calls = service
    refused(client.post("/api/tools/" + tool, json=body))
    assert ledger.rows() == [] and calls == [] and client.app.state.sessions.count == 0


def test_venue_full_week_missing_hour_and_unlisted(service):
    client, _ledger, _store, _calls = service
    body = client.post(
        "/api/tools/venue_busyness", json={"place_keys": ["INVENTED-venue-a"]}
    ).json()
    assert (
        body["status"] == "OK"
        and len(body["facts"]) == 167
        and len(body["payload"]["entries"]) == 168
    )
    assert all(
        "relative_busyness_not_people" in f["caveat_keys"] for f in body["facts"]
    )
    assert len([r for r in body["payload"]["entries"] if r["status"] == "NO_DATA"]) == 1
    assert (
        len(
            client.post(
                "/api/tools/venue_busyness",
                json={"place_keys": ["INVENTED-venue-a"], "weekday": "monday"},
            ).json()["facts"]
        )
        == 24
    )
    assert (
        client.post(
            "/api/tools/venue_busyness", json={"place_keys": ["INVENTED-venue-b"]}
        ).json()["status"]
        == "NO_DATA"
    )
    assert (
        client.post(
            "/api/tools/venue_busyness", json={"place_keys": ["INVENTED-unknown"]}
        ).json()["status"]
        == "OUT_OF_SCOPE"
    )
    refused(client.post("/api/tools/unknown", json={}), 404, "NOT_FOUND")


@pytest.mark.parametrize(
    "error,status,code",
    [
        (TimeoutError(), 504, "QUERY_TIMEOUT"),
        (StoreRefusal("STORE_UNAVAILABLE"), 503, "STORE_UNAVAILABLE"),
        (RuntimeError("SELECT INVENTED-sentinel"), 500, "INTERNAL"),
    ],
)
def test_sanitized_execution_errors(service, error, status, code, capsys):
    client, ledger, store, _calls = service
    with patch.object(store, "fetch", side_effect=error):
        response = client.post(
            "/api/tools/make_area",
            json={"latitude": 1, "longitude": 1, "mode": "distance", "cutoff": 500},
        )
    refused(response, status, code)
    assert ledger.rows() == []
    assert "SELECT" not in response.text + capsys.readouterr().out


def test_card_radius_polygon_and_month(service):
    from eii_core.grid import cell_centre

    client, _ledger, store, _calls = service
    # B is the fixture's isolated 7-radiance cell.
    cell = store.tables["grid_cell"][1]["cell"]
    lat, lon = cell_centre(cell)
    area = client.post(
        "/api/tools/make_area",
        json={"latitude": lat, "longitude": lon, "mode": "distance", "cutoff": 500},
    ).json()["payload"]["area_id"]
    response = client.post(
        "/api/tools/night_lights", json={"area_id": area, "month_key": "2026-03"}
    ).json()
    assert Decimal(response["facts"][0]["value"]) == 7
    assert {"calculated", "night_lights_not_activity"} <= set(
        response["facts"][0]["caveat_keys"]
    )
    assert (
        client.post(
            "/api/tools/night_lights", json={"area_id": area, "month_key": "2030-01"}
        ).json()["status"]
        == "NO_DATA"
    )
    pop = client.post(
        "/api/tools/population_age_sex", json={"area_id": area, "split": "sex"}
    ).json()
    assert len(pop["facts"]) == 4 and all(
        Decimal(f["value"]) == 10 for f in pop["facts"]
    )


def test_routed_mounted_make_and_both_cards(service):
    from eii_core.grid import cell_centre

    client, _ledger, store, calls = service
    lat, lon = cell_centre(store.tables["grid_cell"][0]["cell"])
    areas = []
    for mode, cutoff in [("walk", 5), ("drive", 10)]:
        response = client.post(
            "/api/tools/make_area",
            json={"latitude": lat, "longitude": lon, "mode": mode, "cutoff": cutoff},
        )
        assert response.status_code == 200
        areas.append(response.json()["payload"]["area_id"])
    for tool, extra in [
        ("night_lights", {"month_key": "2026-03"}),
        ("population_age_sex", {"split": "none"}),
    ]:
        for area in areas:
            response = client.post(
                "/api/tools/" + tool, json={"area_id": area, **extra}
            )
            assert response.status_code == 200 and response.json()["status"] == "OK"
            facts = response.json()["facts"]
            if tool == "night_lights":
                assert [Decimal(f["value"]) for f in facts] == [Decimal(4)]
            else:
                assert [Decimal(f["value"]) for f in facts] == [
                    Decimal(20),
                    Decimal(20),
                ]
    assert calls == [("walk", 5), ("drive", 10)] * 3


def test_missing_routing_ledger_failure_and_other_release(service):
    client, ledger, store, _calls = service
    client.app.state.area_contexts.routing = None
    refused(
        client.post(
            "/api/tools/make_area",
            json={"latitude": 1, "longitude": 1, "mode": "walk", "cutoff": 5},
        ),
        500,
        "INTERNAL",
    )
    assert ledger.rows() == []
    response = client.post(
        "/api/tools/make_area",
        json={"latitude": 1, "longitude": 1, "mode": "distance", "cutoff": 500},
    )
    assert response.status_code == 200
    area = response.json()["payload"]["area_id"].replace(
        "ma1/" + store.release_id[:16], "ma1/" + "cd" * 8
    )
    for tool, extra in [
        ("night_lights", {"month_key": "2026-03"}),
        ("population_age_sex", {"split": "none"}),
    ]:
        refused(client.post("/api/tools/" + tool, json={"area_id": area, **extra}))
    before = ledger.rows()
    with patch.object(ledger, "write", side_effect=ValueError("INVENTED-failed-write")):
        refused(
            client.post(
                "/api/tools/make_area",
                json={"latitude": 1, "longitude": 1, "mode": "distance", "cutoff": 500},
            ),
            500,
            "INTERNAL",
        )
    assert ledger.rows() == before


def test_unequal_polygon_mean_and_empty_outline(service):
    client, _ledger, _store, _calls = service
    for ring, expected in [
        ([[0.5, 0.5], [2.5, 0.5], [2.5, 2.5], [0.5, 2.5], [0.5, 0.5]], Decimal(7)),
        ([[0.1, 0.1], [0.2, 0.1], [0.2, 0.2], [0.1, 0.2], [0.1, 0.1]], None),
    ]:
        shape = client.post(
            "/api/areas/shapes",
            json={"geometry": {"type": "Polygon", "coordinates": [ring]}},
        ).json()["shape_id"]
        made = client.post("/api/tools/make_area", json={"shape_id": shape}).json()
        area = made["payload"]["area_id"]
        night = client.post(
            "/api/tools/night_lights", json={"area_id": area, "month_key": "2026-03"}
        ).json()
        if expected is None:
            assert night["status"] == "NO_DATA" and night["facts"] == []
            pop = client.post(
                "/api/tools/population_age_sex", json={"area_id": area, "split": "sex"}
            ).json()
            assert pop["status"] == "NO_DATA" and pop["facts"] == []
        else:
            assert Decimal(night["facts"][0]["value"]) == expected


def test_listed_public_key_can_start_with_digit(service):
    client, _ledger, store, _calls = service
    key = "7-INVENTED-venue"
    store.tables["pub_place"] = [
        {**row, "place_id": key} for row in store.tables["pub_place"][:1]
    ]
    store.tables["pub_venue_busyness"] = [
        {**row, "place_id": key} for row in store.tables["pub_venue_busyness"]
    ]
    body = client.post(
        "/api/tools/venue_busyness", json={"place_keys": [key], "weekday": "monday"}
    ).json()
    assert body["status"] == "OK" and len(body["facts"]) == 24


def test_make_area_by_returned_area_id_decision_0087(service):
    """The area_id input dispatches the BE-86 decode; the ledger keeps no shape."""
    client, ledger, store, _calls = service
    made = []
    for body in (
        {"latitude": 1, "longitude": 1, "mode": "walk", "cutoff": 5},
        {"latitude": 1, "longitude": 1, "mode": "drive", "cutoff": 10},
        {
            "shape_id": client.post("/api/areas/shapes", json=polygon()).json()[
                "shape_id"
            ]
        },
    ):
        first = client.post("/api/tools/make_area", json=body).json()
        again = client.post(
            "/api/tools/make_area", json={"area_id": first["payload"]["area_id"]}
        ).json()
        assert set(again) == KEYS and again["status"] == "OK"
        assert again["payload"] == first["payload"]
        made.append(first["payload"]["area_id"])
    rows = ledger.rows()
    by_id = [r for r in rows if r["arguments"] == {"area_id": "area_redacted"}]
    assert len(by_id) == 3
    assert not any(area in json.dumps(rows) for area in made)
    before = len(ledger.rows())
    walk = made[0]
    for body in (
        {"area_id": walk, "mode": "walk"},
        {"area_id": 7},
        {"area_id": "ma1/not-an-area"},
        {"area_id": walk.replace("ma1/" + store.release_id[:16], "ma1/" + "cd" * 8)},
    ):
        refused(client.post("/api/tools/make_area", json=body))
    refused(Client(client.app).post("/api/tools/make_area", json={"area_id": made[2]}))
    assert len(ledger.rows()) == before
