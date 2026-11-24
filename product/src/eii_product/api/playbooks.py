"""Closed Public playbook requests and resumable template SSE answers."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Callable, Coroutine
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, Request, Response
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from fastapi.sse import EventSourceResponse, ServerSentEvent

from eii_core.reasons import closed_code, reason

if TYPE_CHECKING:
    from eii_product.api.area_context import AreaContextFactory
    from eii_product.api.release import MountedRelease

from eii_product.api.answers import Answer, Gate, default_gate
from eii_product.api.session_store import CapReached, SessionKey, SessionStore
from eii_product.assistant.catalogue.schema import Catalogue
from eii_product.assistant.playbooks.engine import execute
from eii_product.assistant.playbooks.inputs import Inputs
from eii_product.assistant.playbooks.inputs import Pin as Pin
from eii_product.assistant.playbooks.registry import load_playbook
from eii_product.ledger.local import LocalLedger
from eii_product.store.protocol import ReleaseStore
from eii_product.tools.make_area import ArgumentError, MakeAreaContext


def refusal(
    status: int,
    code: str,
    *,
    message_key: str | None = None,
    answer_id: str | None = None,
    release_id: str | None = None,
) -> JSONResponse:
    diagnostic = (
        closed_code(message_key, code.lower())
        if message_key is not None
        else code.lower()
    )
    error_id = str(uuid4())
    print(
        json.dumps(
            dict(
                ts=datetime.now(UTC).isoformat(),
                level="error",
                event="playbook_refused",
                answer_id=answer_id,
                seat_key="",
                tool=None,
                engine=None,
                release_id=release_id,
                status=status,
                duration_ms=None,
                error_code=code if message_key is None else diagnostic,
                error_id=error_id,
            ),
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    return JSONResponse(
        status_code=status,
        content={
            "error": {
                "code": code,
                "message_key": diagnostic,
                "error_id": error_id,
            }
        },
    )


class SessionsFull(Exception):
    """No new session fits; the answer rolls back before admission."""


class PlaybookRoute(APIRoute):
    """Keep request-validation errors on this router in the BE-91 envelope."""

    def get_route_handler(self) -> Callable[[Request], Coroutine[Any, Any, Response]]:
        handler = super().get_route_handler()

        async def handle(request: Request) -> Response:
            try:
                return await handler(request)
            except RequestValidationError:
                return refusal(422, "INVALID_ARGUMENT")

        return handle


def build_router(
    store: ReleaseStore,
    ledger: LocalLedger | None,
    catalogue: Catalogue,
    *,
    gate: Gate = default_gate,
    area_contexts: AreaContextFactory | None = None,
    mount: MountedRelease | None = None,
) -> APIRouter:
    """A store cannot serve playbooks without the BE-69 writer."""
    if ledger is None:
        raise ValueError("ledger_required")
    answers: dict[str, Answer] = {}
    router = APIRouter(route_class=PlaybookRoute)

    def admitted(request: Request) -> SessionKey:
        # An answer's lineage is held for the session that receives it.
        sessions: SessionStore = request.app.state.sessions
        found = sessions.admit(request.cookies.get("eii_session"))
        if isinstance(found, CapReached):
            raise SessionsFull("RATE_LIMITED")
        return found

    async def context_dependency(request: Request) -> MakeAreaContext | None:
        return None if area_contexts is None else area_contexts.dependency(request)

    dependency = Depends(
        context_dependency if area_contexts is None else area_contexts.dependency
    )

    @router.post("/api/playbooks/{playbook}", status_code=202, response_model=None)
    async def start(
        playbook: str,
        raw: dict[str, object],
        request: Request,
        response: Response,
        context: MakeAreaContext | None = dependency,
    ) -> dict[str, str] | Response:
        try:
            definition = load_playbook(playbook, catalogue)
        except ValueError as error:
            return refusal(404, "NOT_FOUND", message_key=reason(error))
        except OSError as error:
            from eii_product.api.results import error_response

            return error_response(error)
        try:
            inputs = Inputs.model_validate(raw)
        except ValueError:
            return refusal(422, "INVALID_ARGUMENT")
        answer_id = str(uuid4())
        session: SessionKey | None = None
        try:
            try:
                with ledger.transaction():
                    bundle = execute(
                        store,
                        definition,
                        inputs.model_dump(exclude_none=True),
                        catalogue,
                        ledger,
                        answer_id,
                        area_context=context,
                    )
                    # Chains validate before the commit; admission waits for it.
                    admit = None if mount is None else mount.prepare_answer(bundle)
                    session = None if admit is None else admitted(request)
            except BaseException:
                # A failed commit frees this request's own new session slot.
                if session is not None:
                    request.app.state.sessions.release(session)
                raise
        except ArgumentError as error:
            return refusal(422, "INVALID_ARGUMENT", message_key=reason(error))
        except SessionsFull:
            return refusal(429, "RATE_LIMITED")
        except Exception as error:
            from eii_product.api.results import error_response

            return error_response(
                error, answer_id=answer_id, release_id=store.release_id
            )
        if admit is not None and session is not None:
            admit(session.key)
            session.keep(response)
        answers[answer_id] = Answer(answer_id, bundle, definition, catalogue, gate=gate)
        return {
            "answer_id": answer_id,
            "events_url": f"/api/answers/{answer_id}/events",
        }

    router.include_router(answer_router(answers))
    return router


def answer_router(answers: dict[str, Answer]) -> APIRouter:
    router = APIRouter(route_class=PlaybookRoute)

    @router.get("/api/answers/{answer_id}/events")
    async def events(
        answer_id: str, last_event_id: Annotated[str | None, Header()] = None
    ) -> Response:
        answer = answers.get(answer_id)
        if answer is None:
            return refusal(404, "NOT_FOUND", answer_id=answer_id)
        try:
            after = 0 if last_event_id is None else int(last_event_id)
            if after < 0 or after > len(answer.history):
                raise ValueError("cursor")
        except ValueError:
            return refusal(422, "INVALID_ARGUMENT")

        async def stream() -> AsyncIterator[str]:
            async for event in answer.events(after):
                frame = ServerSentEvent(
                    data=event.data, event=event.kind, id=str(event.id)
                )
                data = json.dumps(
                    jsonable_encoder(frame.data),
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
                yield f"id: {frame.id}\r\nevent: {frame.event}\r\ndata: {data}\r\n\r\n"

        return EventSourceResponse(stream())

    return router
