"""Public tool dispatch, behind one exact outcome/ledger boundary."""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from eii_product.api.release import MountedRelease

from fastapi import APIRouter, Depends, Request
from pydantic import ValidationError
from starlette.responses import JSONResponse

from eii_product.api.area_context import AreaContextFactory
from eii_product.api.playbooks import PlaybookRoute, refusal
from eii_product.api.results import PublicResult, error_response, respond
from eii_product.api.session_store import SessionStore
from eii_product.ledger.local import LocalLedger
from eii_product.store.protocol import ReleaseStore
from eii_product.store.registry import PACKAGED
from eii_product.tools.make_area import (
    MakeAreaContext,
    MakeAreaResult,
    make_area,
    validate_request,
)
from eii_product.tools.public_context_tools import CARD_MODELS, PLACE_KEY, run_card
from eii_product.tools.resolve import (
    ResolveContext,
    parse_request,
    require_payload,
    resolve,
)


def _resolved(
    store: ReleaseStore, args: dict[str, Any], context: ResolveContext
) -> PublicResult:
    """Project only validated candidates; never turn resolver metadata into facts."""
    result = resolve(store, args, context)
    if result.tool != "resolve" or result.release_id != store.release_id:
        raise ValueError("resolve_result_invalid")
    if result.status == "OK":
        if result.payload is None:
            raise ValueError("resolve_result_invalid")
        require_payload(result.payload)
        if not result.payload["candidates"]:
            raise ValueError("resolve_result_invalid")
    elif result.status not in {"NO_DATA", "OUT_OF_SCOPE"} or result.payload is not None:
        raise ValueError("resolve_result_invalid")
    return PublicResult(result.tool, result.status, result.release_id, result.payload)


def build_tools_router(
    store: ReleaseStore,
    ledger: LocalLedger,
    sessions: SessionStore,
    contexts: AreaContextFactory,
    *,
    mount: MountedRelease | None = None,
) -> APIRouter:
    del sessions  # The dependency reads the app's session store, without admission.
    router = APIRouter(route_class=PlaybookRoute)
    dependency = Depends(contexts.dependency)
    resolve_context = ResolveContext(PACKAGED)

    @router.post("/api/tools/{tool}")
    async def call(
        tool: str, request: Request, context: MakeAreaContext = dependency
    ) -> JSONResponse:
        if tool not in ("resolve", "make_area", *CARD_MODELS):
            return refusal(404, "NOT_FOUND")
        if (
            request.query_params
            or request.headers.get("content-type", "").split(";")[0]
            != "application/json"
        ):
            return refusal(422, "INVALID_ARGUMENT")
        try:
            raw = await request.json()
            if not isinstance(raw, dict):
                return refusal(422, "INVALID_ARGUMENT")
            args: dict[str, Any] = raw
            if tool == "resolve":
                parse_request(args)
            elif tool == "make_area":
                validate_request(
                    args, context.playbook_key, context.hour_keys, context.day_keys
                )
            else:
                args = (
                    CARD_MODELS[tool].model_validate(raw).model_dump(exclude_none=True)
                )
                if tool == "venue_busyness" and any(
                    PLACE_KEY.fullmatch(k) is None for k in args["place_keys"]
                ):
                    return refusal(422, "INVALID_ARGUMENT")
        except (ValidationError, ValueError):
            return refusal(422, "INVALID_ARGUMENT")
        except Exception as error:
            return error_response(error)

        def run() -> PublicResult | MakeAreaResult:
            result = (
                _resolved(store, args, resolve_context)
                if tool == "resolve"
                else make_area(store, args, context)
                if tool == "make_area"
                else run_card(store, tool, args, context)
            )
            return result

        return respond(
            run,
            ledger=ledger,
            engine=store.engine,
            arguments={k: v for k, v in args.items() if k != "text"}
            if tool == "resolve"
            else args,
            prepare=mount.prepare_card if mount is not None else None,
        )

    return router
