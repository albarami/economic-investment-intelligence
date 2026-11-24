"""S3-T26 selected-area contract, transport, accounting and boundary plants."""

import json
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from product.tests.public_http_support import Client
from product.tests.test_public_playbook import catalogue
from product.tests.test_public_playbook import loaded_playbook as loaded_playbook
from product.tests.test_shapes_http import polygon, refused
from product.tests.test_tools_http import service as service

from eii_product.api.playbooks import Inputs
from eii_product.assistant.playbooks.engine import execute, require_identical
from eii_product.assistant.playbooks.registry import load_playbook
from eii_product.assistant.templates.writer import compose

BASE = {"activity": "INVENTED-activity", "lang": "en"}
PIN = {"lat": 1, "lon": 1}
SELECTIONS = ("polygon", "distance", "walk", "drive", "default")


def request_for(client, selection):
    if selection == "polygon":
        registered = client.post("/api/areas/shapes", json=polygon())
        assert registered.status_code == 201
        return {"shape_id": registered.json()["shape_id"]}
    return {
        "pin": PIN,
        **(
            {}
            if selection == "default"
            else {"mode": selection, "cutoff": 500 if selection == "distance" else 15}
        ),
    }


def tool_request(selected):
    if "shape_id" in selected:
        return selected
    return {
        "latitude": selected["pin"]["lat"],
        "longitude": selected["pin"]["lon"],
        "mode": selected.get("mode", "walk"),
        "cutoff": selected.get("cutoff", 5),
    }


@pytest.mark.parametrize("selection", SELECTIONS)
def test_closed_projection_accepts_existing_area_alternatives(service, selection):
    client, *_ = service
    selected = request_for(client, selection)
    parsed = Inputs.model_validate({**BASE, **selected})
    assert parsed.area_request() == tool_request(selected)


@pytest.mark.parametrize(
    "extra",
    [
        {"unknown": True},
        {"pin": PIN},
        {"mode": "walk"},
        {"cutoff": 5},
        {"mode": "walk", "cutoff": 5},
    ],
)
def test_shape_conflicts_refused_before_execution(service, extra):
    client, ledger, *_ = service
    selected = request_for(client, "polygon")
    with patch("eii_product.api.playbooks.execute") as run:
        refused(
            client.post("/api/playbooks/site_check", json={**BASE, **selected, **extra})
        )
    run.assert_not_called()
    assert ledger.rows() == []


@pytest.mark.parametrize(
    "extra",
    [
        {"mode": "walk"},
        {"cutoff": 5},
        {"mode": "walk", "cutoff": 6},
        {"mode": "drive", "cutoff": 30},
        {"mode": "distance", "cutoff": 5},
        {"mode": "walk", "cutoff": True},
        {"mode": "walk", "cutoff": 5.0},
        {"mode": None},
        {"cutoff": None},
        {"shape_id": None},
        {"mode": "drive", "cutoff": 10, "situation": "weekday_lunch"},
        {"seat": "INVENTED-foreign"},
        {"area_id": "INVENTED-foreign"},
    ],
)
def test_pin_conflicts_refused_before_execution(service, extra):
    client, ledger, *_ = service
    with patch("eii_product.api.playbooks.execute") as run:
        refused(
            client.post("/api/playbooks/site_check", json={**BASE, "pin": PIN, **extra})
        )
    run.assert_not_called()
    assert ledger.rows() == []


@pytest.fixture
def capture(service):
    client, ledger, store, routing = service
    bundles = []
    client.card_calls = []
    from eii_product.tools.public_context_tools import run_card

    def recorded_card(store, tool, arguments, context):
        client.card_calls.append((tool, dict(arguments)))
        return run_card(store, tool, arguments, context)

    def recorded(*args, **kwargs):
        bundle = execute(*args, **kwargs)
        bundles.append(bundle)
        return bundle

    with (
        patch("eii_product.api.playbooks.execute", side_effect=recorded),
        patch(
            "eii_product.tools.public_context_tools.run_card", side_effect=recorded_card
        ),
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
        yield client, ledger, store, routing, bundles


def assert_selected(bundle, expected, selection):
    role = "wider" if selection == "drive" else "near"
    steps = {step["key"]: step for step in bundle.steps}
    assert steps[role]["payload"]["area_id"] == expected["area_id"]
    assert steps[role]["payload"]["outline"] == expected["outline"]
    assert bundle.area_roles["headline"] == expected["area_id"]
    assert bundle.area_roles[role] == expected["area_id"]
    assert {
        "directive": "fly",
        "target": {"area_id": expected["area_id"]},
        "zoom": "street",
    } in bundle.stage
    rings = next(d for d in bundle.stage if d["directive"] == "rings")
    assert expected["area_id"] in rings["area_ids"]
    assert len(set(rings["area_ids"])) <= 2
    if selection == "polygon":
        assert bundle.area_roles["wider"] is None
        assert steps["wider"]["status"] == "NO_DATA"
    for card in bundle.cards:
        if card["kind"] in {"night_lights", "population_age_sex"}:
            assert card["area_id"] == expected["area_id"]
            assert card["area_role"] == role
    assert {"night_lights", "population_age_sex"} <= {
        card["kind"] for card in bundle.cards
    }


@pytest.mark.parametrize("lang", ["en", "ar"])
@pytest.mark.parametrize("selection", SELECTIONS)
def test_selected_outline_cards_stage_and_repeat(capture, selection, lang):
    client, ledger, store, _routing, bundles = capture
    selected = request_for(client, selection)
    expected = json.loads(
        client.post("/api/tools/make_area", json=tool_request(selected)).content,
        parse_float=Decimal,
    )["payload"]
    # The API tool and playbook use the identical session/routing snapshot.
    before = len(ledger.rows())
    for _ in range(2):
        response = client.post(
            "/api/playbooks/site_check", json={**BASE, **selected, "lang": lang}
        )
        assert response.status_code == 202
        events = client.get(response.json()["events_url"]).text
        assert "event: done" in events and "event: error" not in events
        assert "event: receipt" in events
        assert_selected(bundles[-1], expected, selection)
        assert {name for name, _ in client.card_calls} == {
            "night_lights",
            "population_age_sex",
        }
        assert all(
            args["area_id"] == expected["area_id"] for _, args in client.card_calls
        )
        assert all(
            e.fact.provenance == "public" and e.valid(store.release_id)
            for e in bundles[-1].facts.values()
        )
    require_identical(bundles[-2].wire(), bundles[-1].wire())
    require_identical(
        compose(
            bundles[-2], load_playbook("site_check", catalogue()), catalogue()
        ).wire(),
        compose(
            bundles[-1], load_playbook("site_check", catalogue()), catalogue()
        ).wire(),
    )
    assert len(ledger.rows()) - before == 2 * len(bundles[-1].steps)
    assert "latitude" not in json.dumps(ledger.rows())
    assert "coordinates" not in json.dumps(ledger.rows())
    assert expected["area_id"] not in json.dumps(ledger.rows())


@pytest.mark.parametrize("boundary", ["session", "seat", "release"])
def test_selected_shape_boundary_refuses_atomically(capture, boundary):
    client, ledger, _store, _, _bundles = capture
    selected = request_for(client, "polygon")
    assert (
        client.post("/api/playbooks/site_check", json={**BASE, **selected}).status_code
        == 202
    )
    before = ledger.rows()
    if boundary == "session":
        client = Client(client.app)
    elif boundary == "seat":
        from eii_product.api.area_context import trusted_seat

        client.app.dependency_overrides[trusted_seat] = lambda: "INVENTED-other-seat"
    else:
        client.app.state.area_contexts.release_id = "cd" * 32
    refused(client.post("/api/playbooks/site_check", json={**BASE, **selected}))
    assert ledger.rows() == before


def test_selected_routing_is_not_optional(capture):
    client, ledger, _, _, _ = capture
    selected = request_for(client, "walk")
    assert (
        client.post("/api/playbooks/site_check", json={**BASE, **selected}).status_code
        == 202
    )
    before = ledger.rows()
    client.app.state.area_contexts.routing = None
    response = client.post("/api/playbooks/site_check", json={**BASE, **selected})
    assert response.status_code == 500
    assert ledger.rows() == before


def test_fly_accepts_the_selected_area_identifier(service):
    from eii_product.tools.stage import stage

    client, *_ = service
    selected = request_for(client, "polygon")
    area = client.post("/api/tools/make_area", json=selected).json()["payload"][
        "area_id"
    ]
    directive = {"directive": "fly", "target": {"area_id": area}, "zoom": "street"}
    assert stage(directive, catalogue())["payload"]["directive"] == directive
    with pytest.raises(ValueError, match="INVALID_ARGUMENT"):
        stage({**directive, "target": {"area_id": area + "/invented"}}, catalogue())


def test_selected_accounting_holds_and_forbids_egress(capture, monkeypatch):
    import asyncio
    import socket
    import urllib.request

    from eii_product.api.answers import Answer
    from eii_product.assistant.accounting import account
    from eii_product.assistant.playbooks.registry import load_playbook

    client, ledger, _store, _routing, bundles = capture
    attempts = []

    def forbidden(*args, **kwargs):
        attempts.append("attempt")
        raise AssertionError("model_egress")

    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(urllib.request, "urlopen", forbidden)
    selected = request_for(client, "distance")
    response = client.post("/api/playbooks/site_check", json={**BASE, **selected})
    assert response.status_code == 202
    events = client.get(response.json()["events_url"]).text
    assert "event: done" in events
    assert attempts == []
    assert "/api/ask" not in events
    bundle = bundles[-1]
    definition = load_playbook("site_check", catalogue())
    assert len(ledger.rows()) == len(bundle.steps)

    async def held():
        entered, release = asyncio.Event(), asyncio.Event()

        async def gate(*args):
            entered.set()
            await release.wait()
            return account(*args)

        answer = Answer("INVENTED-held", bundle, definition, catalogue(), gate=gate)
        stream = answer.events()
        first = await anext(stream)
        await asyncio.wait_for(entered.wait(), 2)
        try:
            assert not any(e.kind in {"narrative", "done"} for e in answer.history)
        finally:
            release.set()
            rest = [e async for e in stream]
        kinds = [e.kind for e in [first, *rest]]
        assert kinds.index("receipt") < kinds.index("narrative") < kinds.index("done")
        assert rest[-1].kind == "done"

    asyncio.run(held())
    assert attempts == []


@pytest.mark.parametrize("selection", SELECTIONS)
def test_selected_coordinates_never_persist_or_log(capture, selection, capsys):
    client, ledger, _store, _routing, _bundles = capture
    selected = request_for(client, selection)
    response = client.post("/api/playbooks/site_check", json={**BASE, **selected})
    assert response.status_code == 202
    client.get(response.json()["events_url"])
    rows = ledger.rows()
    from eii_product.ledger.local import without_coordinates

    assert all(
        row["arguments"] == without_coordinates(row["arguments"]) for row in rows
    )
    assert not any("ma1/" in json.dumps(row) for row in rows)
    logs = capsys.readouterr()
    assert logs.out == logs.err == ""


def test_selected_failure_rolls_back_every_tool(capture, monkeypatch):
    client, ledger, _store, _routing, _bundles = capture
    selected = request_for(client, "polygon")
    before = ledger.rows()

    def fail(*args, **kwargs):
        raise RuntimeError("INVENTED-failed-card")

    monkeypatch.setattr("eii_product.tools.public_context_tools.run_card", fail)
    refused(
        client.post("/api/playbooks/site_check", json={**BASE, **selected}),
        500,
        "PLAYBOOK_FAILED",
    )
    assert ledger.rows() == before


def test_selected_live_cases_execute_on_loaded_embedded_release(loaded_playbook):
    import live_public_playbook as live

    from eii_product.store.parity import TracingStore

    store, ledger, definition = loaded_playbook
    trace = []
    runs = live.selected_runs(
        TracingStore(store, trace), definition, catalogue(), ledger
    )
    assert set(runs) == {
        (case, lang, repeat)
        for case in SELECTIONS
        for lang in ("en", "ar")
        for repeat in ("a", "b")
    }
    for (case, lang, _repeat), (bundle, brief) in runs.items():
        previous, previous_brief = runs[(case, lang, "a")]
        require_identical(previous, bundle)
        require_identical(previous_brief, brief)
        assert all(f["provenance"] == "public" for f in bundle["facts"])
        assert any(
            card["kind"] == "population_age_sex" and card["fact_ids"]
            for card in bundle["cards"]
        )
    assert {
        "night_lights_cells",
        "population_age_sex_rows",
        "make_area_municipalities",
        "make_area_grid_cells",
    } <= set(trace)


@pytest.fixture(scope="module")
def embedded_resolver_release(tmp_path_factory):
    """The resolver fixture on the embedded engine; no database or network."""
    from public_release_fixture import build_fixture
    from test_live_public_release_load import embedded_fixture_store

    from eii_product.ledger.local import LocalLedger

    tmp_path = tmp_path_factory.mktemp("inventory-guard")
    folder = tmp_path / "release"
    identity = build_fixture(folder, resolver=True)
    store = embedded_fixture_store(folder, identity)
    ledger = LocalLedger(tmp_path / "ledger.sqlite")
    try:
        yield store, ledger
    finally:
        ledger.close()
        store.close()


def test_declared_live_inventories_are_named_queries_and_execute(
    embedded_resolver_release,
):
    """Every declared name is a PACKAGED query its route really executes."""
    import live_public_playbook as live

    from eii_product.store.parity import TracingStore
    from eii_product.store.registry import PACKAGED

    store, ledger = embedded_resolver_release
    _, resolve_trace = live.resolve_route_cases(store, ledger)
    selected_trace = []
    live.selected_runs(
        TracingStore(store, selected_trace),
        load_playbook("site_check", catalogue()),
        catalogue(),
        ledger,
    )
    for names, trace in (
        (live.RESOLVE_ROUTE_QUERIES, set(resolve_trace)),
        (set(live.SELECTED_QUERIES), set(selected_trace)),
    ):
        for name in names:
            assert PACKAGED.get(name) is not None, name
            assert name in trace, name


def test_public_card_metric_binding_keeps_existing_calculator_keys(capture):
    client, _ledger, _store, _routing, bundles = capture
    selected = request_for(client, "distance")
    assert (
        client.post("/api/playbooks/site_check", json={**BASE, **selected}).status_code
        == 202
    )
    metrics = {item.returned().metric_key for item in bundles[-1].facts.values()}
    assert metrics == {"night_lights_radiance", "population_grid_people"}


def test_polygon_uses_registered_session_even_without_routing(capture):
    client, _ledger, _store, _routing, bundles = capture
    selected = request_for(client, "polygon")
    client.app.state.area_contexts.routing = None
    response = client.post("/api/playbooks/site_check", json={**BASE, **selected})
    assert response.status_code == 202
    assert bundles[-1].area_roles["headline"] is not None
    assert bundles[-1].area_roles["wider"] is None


def test_selected_refusal_logs_never_echo_coordinates(capture, monkeypatch, capsys):
    client, ledger, _store, _routing, _bundles = capture
    selected = request_for(client, "distance")
    before = ledger.rows()

    def fail(*args, **kwargs):
        raise RuntimeError("INVENTED-coordinate-sentinel latitude=1 longitude=1")

    monkeypatch.setattr("eii_product.tools.public_context_tools.run_card", fail)
    response = client.post("/api/playbooks/site_check", json={**BASE, **selected})
    refused(response, 500, "PLAYBOOK_FAILED")
    logs = capsys.readouterr()
    assert "INVENTED-coordinate-sentinel" not in logs.out + logs.err + response.text
    assert "latitude" not in logs.out + logs.err + response.text
    assert "longitude" not in logs.out + logs.err + response.text
    assert ledger.rows() == before


def test_missing_trusted_seat_cannot_read_an_existing_session(capture):
    from eii_product.api.area_context import trusted_seat

    client, ledger, _store, _routing, _bundles = capture
    selected = request_for(client, "polygon")
    assert (
        client.post("/api/playbooks/site_check", json={**BASE, **selected}).status_code
        == 202
    )
    before = ledger.rows()
    client.app.dependency_overrides[trusted_seat] = lambda: None
    refused(client.post("/api/playbooks/site_check", json={**BASE, **selected}))
    assert ledger.rows() == before


@pytest.mark.parametrize("tool", ["make_area", "night_lights", "population_age_sex"])
def test_absent_trusted_seat_blocks_sibling_decoders(service, tool):
    from eii_product.api.area_context import trusted_seat

    client, ledger, _store, _routing = service
    selected = request_for(client, "polygon")
    area = client.post("/api/tools/make_area", json=selected).json()["payload"][
        "area_id"
    ]
    arguments = (
        selected
        if tool == "make_area"
        else {
            "area_id": area,
            **(
                {"month_key": "2026-03"}
                if tool == "night_lights"
                else {"split": "none"}
            ),
        }
    )
    assert client.post("/api/tools/" + tool, json=arguments).status_code == 200
    before, count = ledger.rows(), client.app.state.sessions.count
    client.app.dependency_overrides[trusted_seat] = lambda: None
    response = client.post("/api/tools/" + tool, json=arguments)
    print("PPV_REACHED", flush=True)
    refused(response)
    assert ledger.rows() == before
    assert client.app.state.sessions.count == count


@pytest.mark.parametrize(
    "tool,extra",
    [
        ("population_age_sex", {"split": "invented"}),
        ("population_age_sex", {"invented": True}),
        ("night_lights", {"invented": True}),
    ],
)
def test_playbook_card_dispatch_reuses_closed_tool_models(
    capture, monkeypatch, tool, extra
):
    client, ledger, _store, _routing, _bundles = capture
    selected = request_for(client, "distance")
    definition = load_playbook("site_check", catalogue())
    assert (
        client.post("/api/playbooks/site_check", json={**BASE, **selected}).status_code
        == 202
    )
    before = ledger.rows()
    calls = [
        call.model_copy(update={"arguments": {**call.arguments, **extra}})
        if call.tool == tool
        else call
        for call in definition.calls
    ]
    changed = definition.model_copy(update={"calls": calls})
    monkeypatch.setattr(
        "eii_product.api.playbooks.load_playbook", lambda *args: changed
    )
    refused(
        client.post("/api/playbooks/site_check", json={**BASE, **selected}),
        500,
        "PLAYBOOK_FAILED",
    )
    assert ledger.rows() == before
