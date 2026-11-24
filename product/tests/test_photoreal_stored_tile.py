"""A photoreal tile is not stored. A planted file on that route is seen."""

import json
import uuid

import pytest
from product.tests.test_map_modes import Response

from eii_product.api.app import create_app


@pytest.fixture
def provider(tmp_path, monkeypatch):
    monkeypatch.setenv("MAPTILE_API_KEY", "SYN-" + uuid.uuid4().hex)
    monkeypatch.setenv("ESRI_API_KEY", "SYN-" + uuid.uuid4().hex)
    monkeypatch.setenv("EII_PHOTOREAL_TILE_BASE", "https://photoreal.invalid/")
    monkeypatch.setenv("EII_IMAGERY_TILE_BASE", "https://imagery.invalid/")
    count = tmp_path / "count"
    count.write_text("ready:0\n")
    calls = []
    response = Response()
    served: dict[str, bytes] = {}

    def opener(request, timeout):
        calls.append(request)
        if "/v1/3dtiles/root.json?" in request.full_url:
            raw = json.dumps(
                {
                    "asset": {"version": "1.1"},
                    "geometricError": 0,
                    "root": {
                        "geometricError": 0,
                        "boundingVolume": {"sphere": [0, 0, 0, 1]},
                        "content": {"uri": "child.glb?session=SYN-session"},
                    },
                }
            ).encode()
            served["root"] = raw
            return Response(
                status=response.status,
                raw=raw,
                headers={"Content-Type": "application/json"},
            )
        if "/v1/3dtiles/child.glb?" in request.full_url:
            raw = b"SYN-tile"
            served["child"] = raw
            return Response(
                status=response.status,
                raw=raw,
                headers={"Content-Type": "model/gltf-binary"},
            )
        return response

    return count, calls, response, opener, served


def test_photoreal_route_stores_no_tile(tmp_path, provider):
    from product.tests.test_map_modes import invoke

    count, _calls, _response, opener, served = provider
    app = create_app(tmp_path, opener=opener, count_path=count)
    status, raw, _headers = invoke(app, "/api/photoreal/views", "POST")
    assert status == 200
    view = json.loads(raw)["view_id"]
    query = "view=" + view
    status, body, headers = invoke(app, "/api/photoreal/3dtiles/root.json", query=query)
    assert status == 200
    assert headers[b"cache-control"] == b"no-store"
    child = json.loads(body)["root"]["content"]["uri"]
    status, tile, headers = invoke(app, child, query=query)
    assert status == 200
    assert tile == b"SYN-tile"
    assert headers[b"cache-control"] == b"no-store"
    root = served["root"]
    rewritten = body
    assert root != rewritten
    assert b"session=SYN-session" in root
    assert b"session=SYN-session" not in rewritten
    assert b"/api/photoreal/" in rewritten

    def stored(needle: bytes) -> bool:
        return any(
            needle in path.read_bytes()
            for path in tmp_path.rglob("*")
            if path.is_file()
        )

    for needle in (root, tile, rewritten, b"session=SYN-session", b"/api/photoreal/"):
        assert stored(needle) is False
    plant = tmp_path / "stored-tile"
    plant.write_bytes(tile)
    assert stored(tile) is True
    plant.unlink()
    root_plant = tmp_path / "stored-root"
    root_plant.write_bytes(root)
    assert stored(root) is True
    root_plant.unlink()
    assert stored(tile) is False
    assert stored(root) is False
