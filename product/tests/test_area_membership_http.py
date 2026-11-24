"""The route's trusted release snapshot, not a client-supplied feature list."""

from pathlib import Path

import pytest
from product.tests.test_tools_http import service as service


def membership_exchange(client):
    layer = client.get("/api/layers/public_places").json()
    first = layer["payload"]["layers"][0]["features"][0]
    lon, lat = first["position"]
    response = client.post(
        "/api/tools/make_area",
        json={"latitude": lat, "longitude": lon, "mode": "distance", "cutoff": 250},
    )
    assert response.status_code == 200
    envelope = response.json()
    assert envelope["status"] == "OK"
    assert (
        first["feature_id"] in envelope["payload"]["point_feature_ids"]["public_places"]
    )
    return {"layer": layer["payload"], "envelope": envelope}


def test_route_membership_uses_the_serving_layer_ids(service):
    client, _ledger, _store, _calls = service
    membership_exchange(client)


def test_absent_snapshot_and_request_injection(service):
    client, _ledger, _store, _calls = service
    contexts = client.app.state.area_contexts
    contexts.point_snapshot = None
    layer = client.get("/api/layers/public_places").json()
    lon, lat = layer["payload"]["layers"][0]["features"][0]["position"]
    args = {"latitude": lat, "longitude": lon, "mode": "distance", "cutoff": 250}
    response = client.post("/api/tools/make_area", json=args)
    assert response.status_code == 200
    assert response.json()["payload"]["point_feature_ids"] is None
    response = client.post(
        "/api/tools/make_area",
        json={**args, "point_feature_ids": {"public_places": ["SYN-injected"]}},
    )
    assert response.status_code == 422


def test_invalid_request_never_reads_the_point_snapshot(service):
    client, _ledger, _store, _calls = service

    def plant():
        pytest.fail("invalid request opened the Public snapshot")

    client.app.state.area_contexts.point_snapshot = plant
    assert (
        client.post("/api/tools/make_area", json={"mode": "unregistered"}).status_code
        == 422
    )


if __name__ == "__main__":
    # Shared API-to-browser integration specimen, using only invented fixture data.
    import json
    from tempfile import TemporaryDirectory

    with TemporaryDirectory(dir=".overnight/tmp") as folder:
        fixture = service.__wrapped__(Path(folder))
        try:
            client, *_ = next(fixture)
            print(json.dumps(membership_exchange(client)))
        finally:
            fixture.close()


def test_snapshot_does_not_invent_a_position_for_an_unlocated_feature(monkeypatch):
    from decimal import Decimal

    from eii_product.api import public_layers

    calls = []

    def read_layer(store, key):
        calls.append(key)
        return {
            "payload": {
                "layers": [
                    {
                        "features": [
                            {
                                "geometry_kind": "point",
                                "feature_id": "SYN-located",
                                "position": [0.5, 0.25],
                            },
                            {"geometry_kind": "point", "feature_id": "SYN-unlocated"},
                            {"geometry_kind": "line", "feature_id": "SYN-line"},
                        ]
                    }
                ]
            }
        }

    monkeypatch.setattr(public_layers, "read_layer", read_layer)
    snapshot = public_layers.public_point_snapshot(object())
    assert tuple(calls) == public_layers.PUBLIC_POINT_LAYER_KEYS
    assert all(
        points == (("SYN-located", Decimal("0.25"), Decimal("0.5")),)
        for points in snapshot.values()
    )
