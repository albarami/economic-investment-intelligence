"""Shape bounds, canonical identity, cookie binding and disclosure plants."""

import json
import math
from decimal import Decimal
from http.cookies import SimpleCookie
from pathlib import Path
from unittest.mock import patch

import pytest
from product.tests.public_http_support import AreaStore, Client

from eii_core.shapes import ring_sha256
from eii_product.api.app import create_app
from eii_product.ledger.local import LocalLedger


def polygon(x=1.0):
    return {
        "geometry": {
            "type": "Polygon",
            "coordinates": [[[x, 1], [x + 0.1, 1], [x + 0.1, 1.1], [x, 1.1], [x, 1]]],
        }
    }


@pytest.fixture
def app(tmp_path):
    ledger = LocalLedger(tmp_path / "ledger.sqlite")
    app = create_app(
        Path("product/tests/fixtures/tiles"),
        store=AreaStore(),
        ledger=ledger,
        session_cap=3,
        fc_setting_reader=lambda: None,
    )
    yield app
    ledger.close()


def refused(response, status=422, code="INVALID_ARGUMENT"):
    assert response.status_code == status
    body = response.json()
    assert set(body) == {"error"}
    assert set(body["error"]) == {"code", "message_key", "error_id"}
    assert body["error"]["code"] == code
    assert "set-cookie" not in response.headers


def test_shape_identity_cookie_isolation_restart(app, capsys):
    http = Client(app)
    with (
        patch.object(Path, "write_bytes", side_effect=AssertionError("write")),
        patch.object(Path, "write_text", side_effect=AssertionError("write")),
    ):
        response = http.post("/api/areas/shapes", json=polygon())
    assert response.status_code == 201
    expected = ring_sha256(
        [
            (Decimal(str(lat)), Decimal(str(lon)))
            for lon, lat in polygon()["geometry"]["coordinates"][0]
        ]
    )
    assert response.json() == {"shape_id": expected}
    cookie = response.headers["set-cookie"]
    flags = SimpleCookie(cookie)["eii_session"]
    assert flags["httponly"] and flags["samesite"] == "strict" and flags["path"] == "/"
    assert all(
        word not in cookie for word in ("Secure", "Domain", "Expires", "Max-Age")
    )
    assert http.post("/api/areas/shapes", json=polygon()).json() == {
        "shape_id": expected
    }
    assert app.state.sessions.count == 1
    key = http.cookies["eii_session"]
    assert app.state.sessions.shapes(key).find(expected).ring
    assert (
        not app.state.sessions.shapes("INVENTED-other")
        .find(expected)
        .__class__.__name__
        == "RegisteredShape"
    )
    assert key not in capsys.readouterr().out


@pytest.mark.parametrize(
    "body",
    [
        {"geometry": polygon()["geometry"], "extra": True},
        {},
        {"geometry": {"type": "MultiPolygon", "coordinates": []}},
        {
            "geometry": {
                "type": "Polygon",
                "coordinates": polygon()["geometry"]["coordinates"] * 2,
            }
        },
        {
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[1, 1], [2, 1], [2, 2], [1, 2]]],
            }
        },
        {
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[1, 1], [2, 2], [2, 1], [1, 2], [1, 1]]],
            }
        },
        polygon(4),
        {
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[True, 1], [2, 1], [2, 2], [True, 1]]],
            }
        },
        {
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[float("nan"), 1], [2, 1], [2, 2], [float("nan"), 1]]],
            }
        },
        {
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[181, 1], [2, 1], [2, 2], [181, 1]]],
            }
        },
        {
            "geometry": {
                "type": "Polygon",
                "coordinates": [[["1", 1], [2, 1], [2, 2], ["1", 1]]],
            }
        },
    ],
)
def test_invalid_geometry_plants_keep_nothing(app, body, capsys):
    refused(Client(app).post("/api/areas/shapes", json=body))
    assert app.state.sessions.count == 0
    log = capsys.readouterr().out
    assert "coordinates" not in log and "geometry" not in log


def test_size_type_vertex_and_shape_limits(app):
    http = Client(app)
    refused(
        http.post(
            "/api/areas/shapes",
            content=b"not-json",
            headers={"Content-Type": "text/plain"},
        )
    )
    oversized_body = json.dumps(polygon()).encode().ljust(65537, b" ")
    refused(http.post("/api/areas/shapes", content=oversized_body))
    refused(http.post("/api/areas/shapes", content=b"{"))
    oversized = polygon()
    points = [
        [
            1.5 + 0.1 * math.cos(i * 2 * math.pi / 500),
            1.5 + 0.1 * math.sin(i * 2 * math.pi / 500),
        ]
        for i in range(500)
    ]
    oversized["geometry"]["coordinates"][0] = [*points, points[0]]
    refused(http.post("/api/areas/shapes", json=oversized))
    assert app.state.sessions.count == 0
    for i in range(50):
        assert (
            http.post("/api/areas/shapes", json=polygon(1 + i / 1000)).status_code
            == 201
        )
    assert http.post("/api/areas/shapes", json=polygon()).status_code == 201
    refused(http.post("/api/areas/shapes", json=polygon(1.2)))
    assert len(app.state.sessions.shapes(http.cookies["eii_session"])) == 50


def test_cap_refusal_unknown_cookie_no_allocation(app):
    clients = [Client(app) for _ in range(3)]
    for http in clients:
        assert http.post("/api/areas/shapes", json=polygon()).status_code == 201
    fourth = Client(app)
    refused(fourth.post("/api/areas/shapes", json=polygon()), 429, "RATE_LIMITED")
    fourth.cookies["eii_session"] = "INVENTED-unknown"
    refused(fourth.post("/api/areas/shapes", json=polygon()), 429, "RATE_LIMITED")
    assert app.state.sessions.count == 3
    for http in clients:
        assert http.post("/api/areas/shapes", json=polygon(1.3)).status_code == 201


@pytest.mark.parametrize(
    "error,status,code", [(TimeoutError("INVENTED-hidden"), 504, "QUERY_TIMEOUT")]
)
def test_land_read_failure_uses_result_boundary(app, monkeypatch, error, status, code):
    def broken(*args):
        raise error

    monkeypatch.setattr("eii_product.api.shapes.read_land", broken)
    refused(Client(app).post("/api/areas/shapes", json=polygon()), status, code)
    assert app.state.sessions.count == 0
