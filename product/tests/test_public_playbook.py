"""Offline S3-T08 controls; all releases use the custodian fixture builder."""

from copy import deepcopy

import pytest

from eii_product.assistant.catalogue.load import catalogue_directory, load_catalogue
from eii_product.assistant.catalogue.schema import Catalogue


def catalogue():
    result = load_catalogue(catalogue_directory())
    assert isinstance(result, Catalogue)
    return result


@pytest.mark.parametrize("plant", ["unknown", "property"])
def test_stage_rejects_planted_directive(plant):
    from eii_product.tools.stage import stage

    directive = {
        "directive": "fly",
        "target": {"place_key": "INVENTED-pin"},
        "zoom": "street",
    }
    assert stage(directive, catalogue())["payload"]["directive"] == directive
    if plant == "unknown":
        directive["directive"] = "invented"
    else:
        directive["extra"] = True
    with pytest.raises(ValueError, match="INVALID_ARGUMENT"):
        stage(directive, catalogue())


@pytest.mark.parametrize("plant", ["order", "content"])
def test_bundle_comparison_rejects_changes(plant):
    from eii_product.assistant.playbooks.engine import require_identical

    left = {
        "steps": ["near", "wide"],
        "engine": "embedded",
        "call_id": "a",
        "facts": ["INVENTED-a"],
    }
    right = deepcopy(left)
    right.update(engine="postgres", call_id="b")
    require_identical(left, right)
    if plant == "order":
        right["steps"].reverse()
    else:
        right["facts"] = ["INVENTED-b"]
    with pytest.raises(ValueError, match="bundle_mismatch"):
        require_identical(left, right)


@pytest.mark.parametrize("plant", ["zero", "duplicate", "origin"])
def test_ledger_one_row_per_call(tmp_path, plant):
    from eii_product.ledger.local import LocalLedger, tool_entry

    ledger = LocalLedger(tmp_path / "ledger.sqlite")
    entry = tool_entry(
        answer_id="INVENTED-answer",
        tool="stage",
        arguments={"latitude": 25, "target": {"lat": 25, "lon": 51}},
        release_id="ab" * 32,
        engine="embedded",
        status="OK",
        fact_ids=[],
    )
    assert ledger.rows() == []
    ledger.write(entry)
    ledger.write(entry)
    ledger.require_entry(entry)
    assert len(ledger.rows()) == 1
    assert ledger.rows()[0]["arguments"] == {"target": {}}
    assert ledger.rows()[0]["seat_key"] == ""
    assert ledger.rows()[0]["organisation_id"] is None
    assert entry["entry_id"].split("-")[2].startswith("7")
    if plant == "zero":
        ledger.connection.execute("DELETE FROM ledger_entry")
    elif plant == "duplicate":
        duplicate = dict(entry, entry_id="INVENTED-other")
        ledger.write(duplicate)
    else:
        entry["origin"] = "seeded"
        with pytest.raises(ValueError):
            ledger.write(entry)
        return
    with pytest.raises(ValueError, match="ledger_cardinality"):
        ledger.require_entries([entry])


def test_playbook_registry_refuses_unknowns():
    from eii_product.assistant.playbooks.registry import (
        load_playbook,
        validate_definition,
    )

    definition = load_playbook("site_check", catalogue())
    assert [call.tool for call in definition.calls] == [
        "resolve",
        "make_area",
        "make_area",
        "stage",
        "stage",
        "sector_facts",
        "night_lights",
        "population_age_sex",
    ]
    with pytest.raises(ValueError, match="NOT_FOUND"):
        load_playbook("invented", catalogue())
    raw = definition.model_dump()
    raw["questions"][0] = "invented"
    with pytest.raises(ValueError):
        validate_definition(raw, catalogue())


@pytest.mark.parametrize(
    "plant", ["Sources", "Assumptions", "Nothing invented", "Scope", "Limits stated"]
)
def test_each_accounting_predicate(plant):
    from eii_product.assistant.accounting import account
    from eii_product.assistant.playbooks.models import Bundle
    from eii_product.assistant.playbooks.registry import load_playbook
    from eii_product.assistant.templates.writer import compose

    bundle = Bundle(release_id="ab" * 32, inputs={"activity": "INVENTED-activity"})
    definition = load_playbook("site_check", catalogue())
    draft = compose(bundle, definition, catalogue())
    assert all(account(draft, bundle, definition, catalogue()).values())
    if plant == "Sources":
        draft.brief["layout"] = [
            {"component": "invented", "props": {"fact_id": "f_" + "ab" * 16}}
        ]
    elif plant == "Assumptions":
        draft.assumptions = []
    elif plant == "Nothing invented":
        draft.brief["layout"] = [{"component": "invented", "props": {}}]
    elif plant == "Scope":
        draft.playbook = "invented"
    else:
        draft.still_to_test = []
    assert account(draft, bundle, definition, catalogue())[plant] is False


def test_make_area_identifier_is_accepted_by_stage():
    from decimal import Decimal

    from eii_product.tools.areas import build_area_id
    from eii_product.tools.stage import stage

    area_id = build_area_id(
        release_id="ab" * 32,
        mode="walk",
        cutoff=5,
        latitude=Decimal("25"),
        longitude=Decimal("51"),
    )
    directive = {"directive": "rings", "area_ids": [area_id]}
    assert stage(directive, catalogue())["payload"]["directive"] == directive


def test_the_brief_is_buffered_until_the_gate_passes():
    import asyncio

    from eii_product.api.answers import Answer
    from eii_product.assistant.accounting import account
    from eii_product.assistant.playbooks.models import Bundle
    from eii_product.assistant.playbooks.registry import load_playbook

    async def exercise():
        entered, release = asyncio.Event(), asyncio.Event()
        bundle = Bundle(release_id="ab" * 32, inputs={})
        bundle.cards = [
            {
                "card_id": "INVENTED-card",
                "kind": "unit_economics",
                "status": "NO_DATA",
                "fact_ids": [],
                "caveat_keys": [],
                "template_key": "no_data",
            }
        ]
        definition = load_playbook("site_check", catalogue())

        async def gate(draft, bundle, definition, catalogue):
            entered.set()
            await release.wait()
            return account(draft, bundle, definition, catalogue)

        answer = Answer("INVENTED-answer", bundle, definition, catalogue(), gate=gate)
        stream = answer.events()
        first = await anext(stream)
        assert first.kind == "evidence"
        await asyncio.wait_for(entered.wait(), 1)
        assert not any(event.kind in {"narrative", "done"} for event in answer.history)
        release.set()
        rest = [event async for event in stream]
        kinds = [event.kind for event in rest]
        assert kinds.index("receipt") < kinds.index("narrative") < kinds.index("done")
        from eii_product.assistant.accounting import CHECKS

        receipt = next(event for event in rest if event.kind == "receipt")
        assert all(receipt.data["Checked before display"][key] for key in CHECKS)
        replay = [event async for event in answer.events(first.id)]
        assert replay == rest
        assert len({event.id for event in replay}) == len(replay)

    asyncio.run(exercise())


@pytest.mark.parametrize("plant", ["component", "props", "fallback"])
@pytest.mark.parametrize("inspect_first", ["narrative", "done"])
def test_invalid_components_are_not_rendered(plant, inspect_first):
    import asyncio

    from eii_product.api.answers import Answer
    from eii_product.assistant.playbooks.models import Bundle
    from eii_product.assistant.playbooks.registry import load_playbook
    from eii_product.assistant.templates.writer import compose

    async def exercise():
        bundle = Bundle(release_id="ab" * 32, inputs={})
        definition = load_playbook("site_check", catalogue())
        draft = compose(bundle, definition, catalogue())
        draft.brief["layout"] = (
            [{"component": "invented", "props": {}}]
            if plant != "props"
            else [{"component": "foundation_note", "props": {"invented": True}}]
        )
        if plant == "fallback":
            definition.layout = draft.brief["layout"]
        answer = Answer(
            "INVENTED-answer", bundle, definition, catalogue(), candidate=draft
        )
        events = [event async for event in answer.events()]
        from eii_product.assistant.catalogue.brief import check_brief

        expected = compose(
            bundle, load_playbook("site_check", catalogue()), catalogue()
        )
        narrative = [event.data for event in events if event.kind == "narrative"]
        if plant != "fallback":
            if inspect_first == "done":
                assert check_brief(catalogue(), events[-1].data["brief"], {}) is None
            assert narrative == [
                item
                for value in expected.brief.values()
                for item in (value if isinstance(value, list) else [value])
            ]
            assert check_brief(catalogue(), events[-1].data["brief"], {}) is None
            receipt = next(event.data for event in events if event.kind == "receipt")
            for key in ("assumptions", "caveat_keys", "coverage_keys"):
                assert receipt["Checked before display"][key] == getattr(expected, key)
        if plant == "fallback":
            assert events[-1].kind == "error"
            assert not any(event.kind in {"narrative", "done"} for event in events)
        else:
            assert events[-1].kind == "done"
            assert events[-1].data["brief"]["layout"] == [
                {"component": "foundation_note", "props": {}}
            ]
        assert len(answer.failures) == 1
        assert set(answer.failures[0]) == {
            "ts",
            "level",
            "event",
            "answer_id",
            "seat_key",
            "tool",
            "engine",
            "release_id",
            "status",
            "duration_ms",
            "error_code",
            "error_id",
        }

    asyncio.run(exercise())


@pytest.mark.parametrize("form", ["polygon", "walk", "drive", "distance"])
def test_stage_area_grammar_accepts_built_forms(form):
    from decimal import Decimal

    from eii_product.tools.areas import build_area_id, parse_area_id
    from eii_product.tools.stage import stage

    release_id = "ab" * 32
    kwargs = (
        {"shape_id": "cd" * 32}
        if form == "polygon"
        else dict(
            mode=form, cutoff=5, cell=9, latitude=Decimal("25"), longitude=Decimal("51")
        )
    )
    area = build_area_id(release_id=release_id, **kwargs)
    assert parse_area_id(area, release_id)
    for directive in (
        {"directive": "rings", "area_ids": [area]},
        {"directive": "split", "area_ids": [area, area]},
    ):
        assert stage(directive, catalogue())["payload"]["directive"] == directive


@pytest.mark.parametrize(
    "plant", ["version", "missing", "empty", "parent", "precision", "mode"]
)
def test_stage_area_grammar_refuses_malformed(plant):
    from eii_product.tools.areas import AreaIdError, parse_area_id
    from eii_product.tools.stage import stage

    pieces = ["ma1", "ab" * 8, "walk", "5", "none", "25.000000", "51.000000"]
    if plant == "version":
        pieces[0] = "ma2"
    elif plant == "missing":
        pieces.pop()
    elif plant == "empty":
        pieces[4] = ""
    elif plant == "parent":
        pieces[4] = ".."
    elif plant == "precision":
        pieces[5] += "0"
    else:
        pieces[2] = "invented"
    area = "/".join(pieces)
    with pytest.raises(AreaIdError):
        parse_area_id(area, "ab" * 32)
    with pytest.raises(ValueError, match="INVALID_ARGUMENT"):
        stage({"directive": "rings", "area_ids": [area]}, catalogue())


@pytest.mark.parametrize(
    "directive",
    [
        {"directive": "hour", "hour_key": "INVENTED/a"},
        {"directive": "highlight", "place_keys": ["INVENTED/a"]},
        {"directive": "fly", "target": {"area_id": "INVENTED/a"}, "zoom": "street"},
    ],
)
def test_stage_other_identifiers_still_refuse_slashes(directive):
    from eii_product.tools.stage import stage

    with pytest.raises(ValueError, match="INVALID_ARGUMENT"):
        stage(directive, catalogue())


@pytest.fixture(scope="module")
def loaded_playbook(tmp_path_factory):
    tmp_path = tmp_path_factory.mktemp("playbook")
    from public_release_fixture import build_fixture
    from test_live_public_release_load import _RecordingPostgres

    from eii_product.ledger.local import LocalLedger
    from eii_product.store.embedded import EmbeddedStore
    from eii_product.store.loader import run_load
    from eii_product.store.registry import PACKAGED
    from eii_product.store.release_check import check_release, manifest_rows

    folder = tmp_path / "release"
    identity = build_fixture(folder, cards=True)
    checked = check_release(folder)
    from eii_product.store.loader import _parquet_rows

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
    store = EmbeddedStore(folder / "release.duckdb", identity, PACKAGED)
    ledger = LocalLedger(tmp_path / "ledger.sqlite")
    from eii_product.assistant.playbooks.registry import load_playbook

    definition = load_playbook("site_check", catalogue())
    try:
        yield store, ledger, definition
    finally:
        store.close()
        ledger.close()


def test_loaded_fixture_bundle_and_brief_repeat(loaded_playbook):
    from eii_product.assistant.playbooks.engine import execute
    from eii_product.assistant.templates.writer import compose

    store, ledger, definition = loaded_playbook
    identity = store.release_id
    inputs = {
        "activity": "INVENTED-activity",
        "pin": {"lat": 25, "lon": 51},
        "lang": "en",
    }
    bundles = [
        execute(store, definition, inputs, catalogue(), ledger, "INVENTED-" + suffix)
        for suffix in ("a", "b")
    ]
    from eii_product.assistant.playbooks.engine import require_identical

    require_identical(bundles[0].wire(), bundles[1].wire())
    require_identical(
        compose(bundles[0], definition, catalogue()).wire(),
        compose(bundles[1], definition, catalogue()).wire(),
    )
    assert len(ledger.rows()) == 2 * len(definition.calls)
    assert bundles[0].cards
    assert bundles[0].facts
    assert all(item.valid(identity) for item in bundles[0].facts.values())


def test_area_coordinates_never_enter_ledger(tmp_path):
    from eii_product.ledger.local import without_coordinates

    area = "ma1/" + "ab" * 8 + "/walk/5/none/25.000000/51.000000"
    assert without_coordinates({"area_ids": [area]}) == {"area_ids": ["area_redacted"]}


def test_stage_registered_with_parity_case():
    from product.tests.make_area_support import RecordingStore, StandInStore

    from eii_product.store.parity import run_parity
    from eii_product.store.registry import PACKAGED, Inventory
    from eii_product.tools.registry import (
        stage_descriptor,
        stage_parity_cases,
        tool_keys,
    )

    assert "stage" in tool_keys()
    inventory = Inventory((), PACKAGED.token, ())
    result = run_parity(
        (StandInStore(inventory, {}), RecordingStore(inventory, {})),
        (stage_descriptor(catalogue()),),
        stage_parity_cases(),
        inventory,
        unit_precision={},
        round_fact=lambda value, places: value,
    )
    assert result.coverage.passed


@pytest.mark.parametrize(
    "plant",
    ["control", "zero", "duplicate", "unknown", "extra", "shape", "missing", "body"],
)
def test_loaded_http_route_and_ledger(loaded_playbook, monkeypatch, plant, capsys):
    import asyncio
    import json
    from pathlib import Path
    from uuid import uuid4

    from eii_product.api.app import create_app

    store, ledger, definition = loaded_playbook
    before = len(ledger.rows())
    write = ledger.write
    if plant == "zero":
        monkeypatch.setattr(ledger, "write", lambda entry: None)
    elif plant == "duplicate":

        def duplicate(entry):
            write(entry)
            write(dict(entry, entry_id=str(uuid4())))

        monkeypatch.setattr(ledger, "write", duplicate)
    app = create_app(Path("."), store=store, ledger=ledger)
    body = {"activity": "INVENTED-activity", "pin": {"lat": 25, "lon": 51}}
    if plant == "extra":
        body["invented"] = True
    if plant == "shape":
        body["shape_id"] = "ab" * 32
    if plant == "missing":
        body.pop("pin")
    if plant == "body":
        body = []
    name = "invented" if plant == "unknown" else "site_check"

    async def request(method, path, value=None):
        messages = []
        consumed = False

        async def send(message):
            messages.append(message)

        async def receive():
            nonlocal consumed
            if not consumed:
                consumed = True
                return {
                    "type": "http.request",
                    "body": json.dumps(value).encode(),
                    "more_body": False,
                }
            await asyncio.Event().wait()

        await app(
            dict(
                type="http",
                asgi={"version": "3.0"},
                http_version="1.1",
                method=method,
                scheme="http",
                path=path,
                query_string=b"",
                headers=[(b"content-type", b"application/json")],
                root_path="",
            ),
            receive,
            send,
        )
        if messages[0]["status"] != 202 and method == "POST":
            from product.tests.test_playbook_http import assert_http_error

            assert_http_error(messages, messages[0]["status"], capsys)
        return messages[0]["status"], b"".join(m.get("body", b"") for m in messages)

    async def run():
        status, response = await request("POST", "/api/playbooks/" + name, body)
        assert (
            status
            == {
                "control": 202,
                "zero": 500,
                "duplicate": 500,
                "unknown": 404,
                "extra": 422,
                "shape": 422,
                "missing": 422,
                "body": 422,
            }[plant]
        )
        if plant == "control":
            assert len(ledger.rows()) - before == len(definition.calls)
            status, stream = await request("GET", json.loads(response)["events_url"])
            assert status == 200
            assert b"event: done" in stream
            assert stream.index(b"event: evidence") < stream.index(b"event: narrative")
            assert b'"writer":"template"' in stream
            assert b'"source_chain"' in stream
            ledger_after_stream = len(ledger.rows())
            replay_status, replay_stream = await request(
                "GET", json.loads(response)["events_url"]
            )
            assert replay_status == 200 and replay_stream == stream
            assert len(ledger.rows()) == ledger_after_stream
            for frame in stream.decode().split("\r\n\r\n"):
                if not frame:
                    continue
                fields = dict(line.split(": ", 1) for line in frame.splitlines())
                data = json.loads(fields["data"])
                if fields["event"] == "plan_step":
                    assert set(data) == {
                        "step_id",
                        "tool",
                        "label_en",
                        "label_ar",
                        "state",
                    }
                if fields["event"] == "evidence":
                    area_fields = (
                        {"area_id", "area_role"}
                        if data["kind"] in {"night_lights", "population_age_sex"}
                        else set()
                    )
                    assert set(data) == area_fields | {
                        "card_id",
                        "kind",
                        "status",
                        "fact_ids",
                        "facts",
                        "caveat_keys",
                        "template_key",
                    }
        elif plant in {"unknown", "extra", "shape", "missing", "body"}:
            assert len(ledger.rows()) == before

    asyncio.run(run())


def test_loaded_fixture_through_postgres_adapter(loaded_playbook, monkeypatch):
    """Recorded driver rows exercise the adapter; live parity remains separate."""
    from eii_product.assistant.playbooks.engine import execute, require_identical
    from eii_product.assistant.templates.writer import compose
    from eii_product.store.postgres import PostgresStore
    from eii_product.store.registry import PACKAGED, bind, require_query
    from eii_product.tools.areas import canonical_json

    store, ledger, definition = loaded_playbook
    captured = {}
    original = store.fetch

    def fetch(query, params):
        result = original(query, params)
        spec = require_query(PACKAGED, query)
        sql, bound = bind(spec, params, "postgres", postgis_schema='"public"')
        captured[(sql, canonical_json(bound))] = result
        return result

    monkeypatch.setattr(store, "fetch", fetch)
    inputs = {
        "activity": "INVENTED-activity",
        "pin": {"lat": 25, "lon": 51},
        "lang": "en",
    }
    left = execute(
        store, definition, inputs, catalogue(), ledger, "INVENTED-driver-embedded"
    )

    class Cursor:
        def __init__(self):
            self.description = None
            self.rows = []

        def execute(self, sql, params=None):
            if "pg_extension" in sql:
                self.rows = [("public",)]
            elif "set_config" in sql:
                self.rows = [(params[0],)]
            elif sql in {"BEGIN READ ONLY", "COMMIT", "ROLLBACK"}:
                self.rows = []
            else:
                result = captured[(sql, canonical_json(params))]
                self.description = [(name,) for name in result.columns]
                self.rows = list(result.rows)

        def fetchone(self):
            return self.rows[0] if self.rows else None

        def fetchall(self):
            return self.rows

        def close(self):
            pass

    class Connection:
        autocommit = True

        def cursor(self):
            return Cursor()

        def close(self):
            pass

    postgres = PostgresStore(Connection(), store.release_id, PACKAGED)
    right = execute(
        postgres, definition, inputs, catalogue(), ledger, "INVENTED-driver-postgres"
    )
    require_identical(left.wire(), right.wire())
    require_identical(
        compose(left, definition, catalogue()).wire(),
        compose(right, definition, catalogue()).wire(),
    )


def test_uuid7_unavailable_refuses_without_fallback(monkeypatch):
    import uuid

    from eii_product.ledger.local import tool_entry

    monkeypatch.delattr(uuid, "uuid7")
    with pytest.raises(RuntimeError, match="python_version_refused"):
        tool_entry(
            answer_id="INVENTED-answer",
            tool="stage",
            arguments={},
            release_id="ab" * 32,
            engine="embedded",
            status="OK",
            fact_ids=[],
        )


def test_activity_code_uses_the_sector_tool_grammar():
    from eii_product.api.playbooks import Inputs

    assert (
        Inputs.model_validate(
            {"activity": "561", "pin": {"lat": 25, "lon": 51}}
        ).activity
        == "561"
    )


@pytest.mark.parametrize("length", [8, 11])
def test_activity_refuses_identifier_shaped_digit_runs(length):
    from eii_product.api.playbooks import Inputs

    with pytest.raises(ValueError):
        Inputs.model_validate({"activity": "1" * length, "pin": {"lat": 25, "lon": 51}})


def test_executor_failure_leaves_no_answer_or_partial_ledger(
    loaded_playbook, monkeypatch, capsys
):
    import asyncio
    from pathlib import Path

    from product.tests.test_playbook_http import assert_http_error, http_request

    from eii_product.api.app import create_app

    store, ledger, _definition = loaded_playbook
    before = ledger.rows()
    created = []
    monkeypatch.setattr(
        "eii_product.api.playbooks.Answer", lambda *a, **kw: created.append(a)
    )

    def fail(*args):
        assert len(ledger.rows()) > len(before)
        raise RuntimeError("invented_executor_failure")

    monkeypatch.setattr("eii_product.assistant.playbooks.engine.make_area", fail)
    app = create_app(Path("."), store=store, ledger=ledger)

    async def run():
        tasks = asyncio.all_tasks()
        messages = await http_request(
            app,
            "POST",
            "/api/playbooks/site_check",
            {"activity": "INVENTED-activity", "pin": {"lat": 25, "lon": 51}},
        )
        assert messages[0]["status"] == 500
        assert_http_error(messages, 500, capsys)
        assert not created
        assert asyncio.all_tasks() == tasks
        assert ledger.rows() == before

    asyncio.run(run())


def test_disconnect_finishes_and_replay_reruns_no_tools(loaded_playbook, monkeypatch):
    import asyncio
    import json
    from pathlib import Path

    from product.tests.test_playbook_http import http_request

    from eii_product.api.answers import Answer
    from eii_product.api.app import create_app
    from eii_product.assistant.accounting import account
    from eii_product.assistant.playbooks import engine

    store, ledger, _definition = loaded_playbook
    calls, answers = [], []

    def counted(name, original):
        def call(*args, **kwargs):
            calls.append(name)
            return original(*args, **kwargs)

        return call

    for name in ("resolve", "make_area", "stage", "sector_facts"):
        monkeypatch.setattr(engine, name, counted(name, getattr(engine, name)))

    def capture(*args, **kwargs):
        answer = Answer(*args, **kwargs)
        answers.append(answer)
        return answer

    monkeypatch.setattr("eii_product.api.playbooks.Answer", capture)

    async def run():
        entered, release, disconnect = asyncio.Event(), asyncio.Event(), asyncio.Event()

        async def gate(*args):
            entered.set()
            await release.wait()
            return account(*args)

        app = create_app(Path("."), store=store, ledger=ledger, gate=gate)
        messages = await http_request(
            app,
            "POST",
            "/api/playbooks/site_check",
            {"activity": "INVENTED-activity", "pin": {"lat": 25, "lon": 51}},
        )
        body = json.loads(b"".join(m.get("body", b"") for m in messages))
        path = body["events_url"]
        seen = []

        def on_send(message):
            if b"event: evidence" in message.get("body", b""):
                seen.append(message["body"])
                disconnect.set()

        request = asyncio.create_task(
            http_request(app, "GET", path, send_hook=on_send, disconnect=disconnect)
        )
        try:
            await asyncio.wait_for(entered.wait(), 2)
            await asyncio.wait_for(request, 2)
            assert seen
            answer = answers[0]
            assert answer.task is not None and not answer.task.done()
        finally:
            release.set()
        await asyncio.wait_for(answer.task, 2)
        assert answer.closed and answer.history[-1].kind == "done"
        assert calls == ["resolve", "make_area", "make_area", "sector_facts"]
        before = list(calls)
        cursor = seen[-1].split(b"\r\n", 1)[0].removeprefix(b"id: ")
        replay = await http_request(
            app, "GET", path, headers=[(b"last-event-id", cursor)]
        )
        frames = b"".join(m.get("body", b"") for m in replay)
        ids = [
            int(line[4:]) for line in frames.splitlines() if line.startswith(b"id: ")
        ]
        assert ids == [event.id for event in answer.history if event.id > int(cursor)]
        assert calls == before
        terminal = await http_request(
            app,
            "GET",
            path,
            headers=[(b"last-event-id", str(len(answer.history)).encode())],
        )
        assert terminal[0]["status"] == 200
        assert b"".join(m.get("body", b"") for m in terminal) == b""
        assert calls == before

    asyncio.run(run())


@pytest.mark.parametrize(
    "plant,reason",
    [
        ("duplicate", "duplicate_call"),
        ("fragment", "unknown_fragment"),
        ("claim", "unknown_claim"),
        ("extra", "extra_forbidden"),
    ],
)
def test_definition_direct_refusals(plant, reason):
    from eii_product.assistant.playbooks.registry import (
        load_playbook,
        validate_definition,
    )

    raw = load_playbook("site_check", catalogue()).model_dump()
    assert validate_definition(raw, catalogue())
    if plant == "duplicate":
        raw["calls"][1]["key"] = raw["calls"][0]["key"]
    elif plant == "fragment":
        raw["headline_key"] = "invented"
    elif plant == "claim":
        raw["claims"] = [{"claim_key": "invented", "slots": {}}]
    else:
        raw["invented"] = True
    with pytest.raises(ValueError, match=reason):
        validate_definition(raw, catalogue())


def test_execute_directly_requires_ledger(loaded_playbook):
    from eii_product.assistant.playbooks.engine import execute

    store, ledger, definition = loaded_playbook
    inputs = {
        "activity": "INVENTED-activity",
        "pin": {"lat": 25, "lon": 51},
        "lang": "en",
    }
    execute(store, definition, inputs, catalogue(), ledger, "INVENTED-control")
    with pytest.raises(ValueError, match=r"^ledger_required$"):
        execute(
            store,
            definition,
            {
                "activity": "INVENTED-activity",
                "pin": {"lat": 25, "lon": 51},
                "lang": "en",
            },
            catalogue(),
            None,
            "INVENTED-answer",
        )


@pytest.mark.parametrize("plant", ["unmatched", "collision"])
def test_metric_binding_direct_refusal(monkeypatch, plant):
    from product.tests.test_playbook_accounting import invented_bundle

    from eii_core.facts import fact_id
    from eii_product.assistant.playbooks.engine import unit_economics_metric

    fact = next(iter(invented_bundle().facts.values())).fact
    identity = fact_id(
        release_id=fact.release_id,
        metric_key="food",
        geography=fact.geography,
        period=fact.period,
        qualifiers={"activity": "INVENTED-activity"},
    )
    fact = fact.model_copy(update={"fact_id": identity})
    assert unit_economics_metric(fact, "INVENTED-activity") == "food"
    if plant == "unmatched":
        fact = fact.model_copy(update={"fact_id": "f_" + "cd" * 16})
    else:
        monkeypatch.setattr(
            "eii_product.assistant.playbooks.engine.fact_id", lambda **kw: identity
        )
    with pytest.raises(ValueError, match=r"^fact_binding_invalid$"):
        unit_economics_metric(fact, "INVENTED-activity")


@pytest.mark.parametrize(
    "plant,reason",
    [
        ("coordinate", "ledger_entry_invalid"),
        ("area", "ledger_entry_invalid"),
        ("kind", "ledger_entry_invalid"),
        ("columns", "ledger_entry_invalid"),
        ("conflict", "ledger_replay_conflict"),
    ],
)
def test_ledger_direct_refusals(tmp_path, plant, reason):
    from eii_product.ledger.local import LocalLedger, tool_entry

    ledger = LocalLedger(tmp_path / "ledger.sqlite")
    try:
        entry = tool_entry(
            answer_id="INVENTED-answer",
            tool="stage",
            arguments={},
            release_id="ab" * 32,
            engine="embedded",
            status="OK",
            fact_ids=[],
        )
        ledger.write(entry)
        before = ledger.rows()
        entry = dict(entry)
        if plant == "coordinate":
            entry["arguments"] = {"latitude": 25}
        elif plant == "area":
            entry["arguments"] = {
                "area_id": "ma1/" + "ab" * 8 + "/walk/5/none/25.000000/51.000000"
            }
        elif plant == "kind":
            entry["kind"] = "invented"
        elif plant == "columns":
            entry["invented"] = True
        else:
            entry["status"] = "NO_DATA"
        with pytest.raises(ValueError, match=r"^" + reason + "$"):
            ledger.write(entry)
        assert ledger.rows() == before
    finally:
        ledger.close()


@pytest.mark.parametrize(
    "field,bound,direction",
    [("lat", -90, -1), ("lat", 90, 1), ("lon", -180, -1), ("lon", 180, 1)],
)
def test_coordinate_boundaries(field, bound, direction):
    import math

    from eii_product.api.playbooks import Inputs

    raw = {"activity": "INVENTED-activity", "pin": {"lat": 25, "lon": 51}}
    raw["pin"][field] = bound
    assert getattr(Inputs.model_validate(raw).pin, field) == bound
    raw["pin"][field] = math.nextafter(bound, math.inf * direction)
    with pytest.raises(ValueError, match=r"less_than_equal|greater_than_equal"):
        Inputs.model_validate(raw)


def test_activity_length_boundary():
    from eii_product.api.playbooks import Inputs

    raw = {"activity": "a" * 200, "pin": {"lat": 25, "lon": 51}}
    assert Inputs.model_validate(raw).activity == raw["activity"]
    raw["activity"] += "a"
    with pytest.raises(ValueError, match="string_too_long"):
        Inputs.model_validate(raw)


def test_inputs_directly_require_area():
    from eii_product.api.playbooks import Inputs

    raw = {"activity": "INVENTED-activity", "pin": {"lat": 25, "lon": 51}}
    assert Inputs.model_validate(raw)
    del raw["pin"]
    with pytest.raises(ValueError, match="INVALID_ARGUMENT"):
        Inputs.model_validate(raw)
