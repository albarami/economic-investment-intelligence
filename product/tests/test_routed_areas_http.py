"""Pass-1 routing seam; production R2 mounting belongs to the next pass."""

import json
import socket
import subprocess
from decimal import Decimal as D
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi import Depends, FastAPI, Request
from product.tests.public_http_support import AreaStore, Client
from product.tests.test_public_context import context as fact_context

from eii_core.grid import cell_centre
from eii_product.api.area_context import AreaContextFactory, RoutingSource
from eii_product.api.session_store import SessionStore
from eii_product.areas_spike.engine import scaled_actor
from eii_product.tools.area_outline import read_outline
from eii_product.tools.make_area import MakeAreaContext, decode_area, make_area
from eii_product.tools.public_context import read_night_lights, read_population_age_sex


@pytest.mark.parametrize("native", [False, True])
def test_routed_context_make_decode_and_both_cards(native):
    store = AreaStore()
    centres = {r["cell"]: cell_centre(r["cell"]) for r in store.tables["grid_cell"]}
    latitude, longitude = next(iter(centres.values()))
    pin = (
        D(str(latitude)).quantize(D("0.000001")),
        D(str(longitude)).quantize(D("0.000001")),
    )
    calls = []

    def recorder(mode, minutes, lat, lon):
        calls.append((mode, minutes))
        return (
            (lat - D(".01"), lon - D(".01")),
            (lat - D(".01"), lon + D(".01")),
            (lat + D(".01"), lon + D(".01")),
            (lat + D(".01"), lon - D(".01")),
            (lat - D(".01"), lon - D(".01")),
        )

    if native:
        road = json.loads(
            (
                Path(__file__).parent / "fixtures/areas_spike/road_network.json"
            ).read_text()
        )
        old_pin = next(node for node in road["nodes"] if node["id"] == road["pin"])
        offset = float(pin[0]) - old_pin["lat"], float(pin[1]) - old_pin["lon"]
        for node in road["nodes"]:
            node["lat"] += offset[0]
            node["lon"] += offset[1]
        _actor, temporary = scaled_actor(json.dumps(road, sort_keys=True), 1.0)
        source = RoutingSource.from_tiles(Path(temporary.name))
    else:
        source = RoutingSource.from_call(recorder)
    factory = AreaContextFactory(store.release_id, source)
    app = FastAPI()
    app.state.sessions = SessionStore()
    # A test-only mounted consumer proves Depends without starting pass-2 routes.
    dependency = Depends(factory.dependency)

    @app.post("/invented/route")
    async def route(request: Request, area: MakeAreaContext = dependency):
        body = await request.json()
        with (
            patch.object(socket, "socket", side_effect=AssertionError("socket")),
            patch.object(
                socket, "create_connection", side_effect=AssertionError("connection")
            ),
            patch.object(subprocess, "Popen", side_effect=AssertionError("process")),
        ):
            result = make_area(
                store,
                {
                    "latitude": pin[0],
                    "longitude": pin[1],
                    "mode": body["mode"],
                    "cutoff": body["cutoff"],
                },
                area,
            )
            assert result.status == "OK"
            for reader in ("night", "population"):
                decoded = decode_area(store, result.payload["area_id"], area)
                assert decoded.status == "OK"
                outline = read_outline(decoded.payload["outline"])
                if reader == "night":
                    kwargs = fact_context("pub_night_lights")
                    kwargs["release_id"] = store.release_id
                    fact = read_night_lights(
                        store.tables["pub_night_lights"],
                        centres=centres,
                        area=outline,
                        area_id=result.payload["area_id"],
                        period="2026-03",
                        **kwargs,
                    )
                    assert fact.value == D(4)
                else:
                    kwargs = fact_context("pub_pop_agesex_grid")
                    kwargs["release_id"] = store.release_id
                    result_pop = read_population_age_sex(
                        store.tables["pub_pop_agesex_grid"],
                        area=outline,
                        area_id=result.payload["area_id"],
                        period="2025",
                        **kwargs,
                    )
                    assert result_pop.fact.value == D(40)
            return {"status": "OK"}

    for mode, cutoff in [("walk", 5), ("drive", 10)]:
        assert Client(app).post(
            "/invented/route", json={"mode": mode, "cutoff": cutoff}
        ).json() == {"status": "OK"}
    if not native:
        assert calls == [("walk", 5)] * 3 + [("drive", 10)] * 3


def test_native_routing_on_actual_tool_endpoints(tmp_path):
    from product.tests.test_tools_http import CardStore

    from eii_product.api.app import create_app
    from eii_product.ledger.local import LocalLedger

    store = CardStore()
    lat, lon = cell_centre(store.tables["grid_cell"][0]["cell"])
    road = json.loads(
        (Path(__file__).parent / "fixtures/areas_spike/road_network.json").read_text()
    )
    old = next(n for n in road["nodes"] if n["id"] == road["pin"])
    offset = (lat - old["lat"], lon - old["lon"])
    for node in road["nodes"]:
        node["lat"] += offset[0]
        node["lon"] += offset[1]
    _actor, temporary = scaled_actor(json.dumps(road, sort_keys=True), 1.0)
    ledger = LocalLedger(tmp_path / "ledger.sqlite")
    try:
        app = create_app(
            Path("product/tests/fixtures/tiles"),
            store=store,
            ledger=ledger,
            routing=RoutingSource.from_tiles(Path(temporary.name)),
            fc_setting_reader=lambda: None,
        )

        async def guarded(scope, receive, send):
            with (
                patch.object(socket, "socket", side_effect=AssertionError("socket")),
                patch.object(
                    socket,
                    "create_connection",
                    side_effect=AssertionError("connection"),
                ),
                patch.object(
                    subprocess, "Popen", side_effect=AssertionError("process")
                ),
            ):
                await app(scope, receive, send)

        client = Client(guarded)
        for mode, cutoff in [("walk", 5), ("drive", 10)]:
            result = client.post(
                "/api/tools/make_area",
                json={
                    "latitude": lat,
                    "longitude": lon,
                    "mode": mode,
                    "cutoff": cutoff,
                },
            )
            assert result.status_code == 200
            area = result.json()["payload"]["area_id"]
            night = client.post(
                "/api/tools/night_lights",
                json={"area_id": area, "month_key": "2026-03"},
            )
            assert night.status_code == 200 and night.json()["status"] == "OK"
            assert D(night.json()["facts"][0]["value"]) == 4
            pop = client.post(
                "/api/tools/population_age_sex", json={"area_id": area, "split": "none"}
            )
            assert pop.status_code == 200 and pop.json()["status"] == "OK"
            assert [D(f["value"]) for f in pop.json()["facts"]] == [D(20), D(20)]
            # The playbook must carry the very same native routing source and
            # chosen ID through its own selected-area request and stream.
            from types import SimpleNamespace

            with (
                patch(
                    "eii_product.assistant.playbooks.engine.resolve",
                    return_value=SimpleNamespace(status="NO_DATA", payload=None),
                ),
                patch(
                    "eii_product.assistant.playbooks.engine.sector_facts",
                    return_value={
                        "status": "NO_DATA",
                        "payload": {},
                        "facts": [],
                        "blocks": [],
                    },
                ),
            ):
                selected = client.post(
                    "/api/playbooks/site_check",
                    json={
                        "activity": "INVENTED-activity",
                        "pin": {"lat": lat, "lon": lon},
                        "mode": mode,
                        "cutoff": cutoff,
                    },
                )
            assert selected.status_code == 202
            stream = client.get(selected.json()["events_url"]).text
            assert "event: done" in stream and "event: error" not in stream
            assert json.dumps({"area_id": area}, separators=(",", ":")) in stream
    finally:
        ledger.close()
        temporary.cleanup()
