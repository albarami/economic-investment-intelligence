"""HTTP ASGI stream controls with an explicitly held accounting gate."""

import asyncio

import pytest
from fastapi import FastAPI
from product.tests.test_public_playbook import catalogue

from eii_product.api.answers import Answer
from eii_product.assistant.accounting import account
from eii_product.assistant.playbooks.models import Bundle
from eii_product.assistant.playbooks.registry import load_playbook


def test_route_requires_ledger(tmp_path):
    from eii_product.api.playbooks import build_router

    with pytest.raises(ValueError, match="ledger_required"):
        build_router(object(), None, catalogue())


def test_http_stream_holds_narrative_and_replays():
    from eii_product.api.playbooks import answer_router

    async def run():
        entered, release = asyncio.Event(), asyncio.Event()
        bundle = Bundle("ab" * 32, {})
        bundle.cards = [{"kind": "unit_economics", "status": "NO_DATA", "fact_ids": []}]
        definition = load_playbook("site_check", catalogue())

        async def gate(draft, bundle, definition, cat):
            entered.set()
            await release.wait()
            return account(draft, bundle, definition, cat)

        answer = Answer("INVENTED-answer", bundle, definition, catalogue(), gate=gate)
        app = FastAPI()
        app.include_router(answer_router({answer.answer_id: answer}))
        sent = []
        evidence = asyncio.Event()

        async def send(message):
            sent.append(message)
            if b"event: evidence" in message.get("body", b""):
                evidence.set()

        async def receive():
            await asyncio.Event().wait()

        scope = dict(
            type="http",
            asgi={"version": "3.0"},
            http_version="1.1",
            method="GET",
            scheme="http",
            path="/api/answers/INVENTED-answer/events",
            raw_path=b"/api/answers/INVENTED-answer/events",
            query_string=b"",
            headers=[],
            root_path="",
        )
        task = asyncio.create_task(app(scope, receive, send))
        try:
            await asyncio.wait_for(entered.wait(), 2)
            await asyncio.wait_for(evidence.wait(), 2)
            held = b"".join(m.get("body", b"") for m in sent)
            assert b"event: narrative" not in held
            assert b"event: done" not in held
        finally:
            release.set()
            await asyncio.wait_for(task, 2)
        body = b"".join(m.get("body", b"") for m in sent)
        assert (
            body.index(b"event: evidence")
            < body.index(b"event: receipt")
            < body.index(b"event: narrative")
            < body.index(b"event: done")
        )
        ids = [line for line in body.splitlines() if line.startswith(b"id: ")]
        assert len(ids) == len(set(ids))
        assert ids == [
            b"id: " + str(number).encode() for number in range(1, len(ids) + 1)
        ]
        sent.clear()
        scope["headers"] = [(b"last-event-id", b"1")]
        await app(scope, receive, send)
        replay = b"".join(m.get("body", b"") for m in sent)
        assert replay == body.split(b"\r\n\r\n", 1)[1]

    asyncio.run(run())


@pytest.mark.parametrize(
    "path,cursor,status",
    [
        ("/api/answers/missing/events", "0", 404),
        *(
            ("/api/answers/INVENTED-answer/events", cursor, 422)
            for cursor in ("invented", "-1", "100")
        ),
    ],
)
def test_http_unknown_answer_and_bad_cursor(capsys, path, cursor, status):
    from eii_product.api.playbooks import answer_router

    bundle = Bundle("ab" * 32, {})
    answer = Answer(
        "INVENTED-answer", bundle, load_playbook("site_check", catalogue()), catalogue()
    )
    app = FastAPI()
    app.include_router(answer_router({answer.answer_id: answer}))

    async def run():
        messages = []

        async def send(message, messages=messages):
            messages.append(message)

        async def receive():
            await asyncio.Event().wait()

        await app(
            dict(
                type="http",
                asgi={"version": "3.0"},
                http_version="1.1",
                method="GET",
                scheme="http",
                path=path,
                query_string=b"",
                headers=[(b"last-event-id", cursor.encode())],
                root_path="",
            ),
            receive,
            send,
        )
        assert messages[0]["status"] == status
        assert_http_error(messages, status, capsys)

    asyncio.run(run())


def assert_http_error(messages, status, capsys):
    import json
    from uuid import UUID

    body = json.loads(b"".join(m.get("body", b"") for m in messages))
    code = {404: "NOT_FOUND", 422: "INVALID_ARGUMENT", 500: "PLAYBOOK_FAILED"}[status]
    error_id = body["error"]["error_id"]
    assert str(UUID(error_id)) == error_id
    assert body == {
        "error": {"code": code, "message_key": code.lower(), "error_id": error_id}
    }
    logs = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    row = next(row for row in logs if row.get("error_id") == error_id)
    assert row["error_code"] == code
    assert set(row) == {
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


async def http_request(
    app, method, path, value=None, headers=(), send_hook=None, disconnect=None
):
    import json

    messages = []
    consumed = False

    async def receive():
        nonlocal consumed
        if not consumed:
            consumed = True
            return {
                "type": "http.request",
                "body": json.dumps(value).encode(),
                "more_body": False,
            }
        if disconnect is not None:
            await disconnect.wait()
            return {"type": "http.disconnect"}
        await asyncio.Event().wait()

    async def send(message):
        messages.append(message)
        if send_hook is not None:
            send_hook(message)

    await app(
        dict(
            type="http",
            asgi={"version": "3.0"},
            http_version="1.1",
            method=method,
            scheme="http",
            path=path,
            query_string=b"",
            headers=[(b"content-type", b"application/json"), *headers],
            root_path="",
        ),
        receive,
        send,
    )
    return messages


@pytest.mark.parametrize("plant", ["type", "missing"])
def test_accounting_result_direct_refusal(plant):
    from eii_product.assistant.templates.writer import compose

    async def run():
        cat = catalogue()
        bundle = Bundle("ab" * 32, {})
        definition = load_playbook("site_check", cat)
        draft = compose(bundle, definition, cat)
        result = account(draft, bundle, definition, cat)
        assert all(result.values())
        if plant == "type":
            result["Sources"] = "yes"
        else:
            del result["Sources"]

        async def gate(*args):
            return result

        answer = Answer("INVENTED-answer", bundle, definition, cat, gate=gate)
        with pytest.raises(ValueError, match=r"^accounting_result_invalid$"):
            await answer.checked(draft)
        events = [event async for event in answer.events()]
        assert [event.kind for event in events] == ["error"]
        assert events[0].data["code"] == "ANSWER_FAILED"

    asyncio.run(run())


@pytest.mark.parametrize("cursor", [-1, 1])
def test_answer_direct_cursor_refusal(cursor):
    async def run():
        answer = Answer(
            "INVENTED-answer",
            Bundle("ab" * 32, {}),
            load_playbook("site_check", catalogue()),
            catalogue(),
        )
        with pytest.raises(ValueError, match=r"^INVALID_ARGUMENT$"):
            await anext(answer.events(cursor))
        assert answer.task is None

    asyncio.run(run())


def test_app_direct_catalogue_refusal(monkeypatch, tmp_path):
    from eii_product.api.app import create_app
    from eii_product.assistant.catalogue.schema import Refusal
    from eii_product.ledger.local import LocalLedger

    ledger = LocalLedger(tmp_path / "ledger.sqlite")
    assert create_app(tmp_path, store=object(), ledger=ledger)
    monkeypatch.setattr(
        "eii_product.api.app.load_catalogue",
        lambda *args: Refusal("INVENTED", "catalogue"),
    )
    with pytest.raises(ValueError, match=r"^catalogue_invalid$"):
        create_app(tmp_path, store=object(), ledger=ledger)
    ledger.close()
