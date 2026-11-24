"""The Public outcome boundary: governed answers, atomic ledger, closed errors."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, cast
from uuid import uuid4

from fastapi.encoders import jsonable_encoder
from starlette.responses import JSONResponse

from eii_core.facts import Fact
from eii_core.reasons import closed_code, reason
from eii_product.api.playbooks import refusal
from eii_product.ledger.local import LocalLedger, tool_entry
from eii_product.store.protocol import EngineName, StoreRefusal
from eii_product.tools.areas import AreaIdError
from eii_product.tools.make_area import ArgumentError, MakeAreaResult

GOVERNED = frozenset({"OK", "SUPPRESSED", "NO_DATA", "OUT_OF_SCOPE"})


@dataclass(frozen=True)
class PublicResult:
    tool: str
    status: str
    release_id: str
    payload: Mapping[str, object] | None = None
    facts: tuple[Fact, ...] = ()
    blocks: tuple[Mapping[str, object], ...] = ()
    caveat_keys: tuple[str, ...] = ()
    reason: str | None = field(default=None)


def wire_fact(fact: Fact) -> dict[str, Any]:
    """Fixed Fact projection: keep numeric values as JSON numbers for Fact chips."""
    projected = cast(dict[str, Any], jsonable_encoder(fact.model_dump(mode="python")))
    if type(fact.value) in (Decimal, int, float) and Decimal(
        str(float(cast(Decimal | int | float, fact.value)))
    ) != Decimal(str(fact.value)):
        raise ValueError("numeric_wire_invalid")
    return projected


def error_response(
    error: Exception, *, answer_id: str | None = None, release_id: str | None = None
) -> JSONResponse:
    """Never interpolate an exception, query, coordinate or path."""
    diagnostic = reason(error)
    context = {"answer_id": answer_id, "release_id": release_id}
    if isinstance(error, (ArgumentError, AreaIdError)):
        return refusal(
            422,
            "INVALID_ARGUMENT",
            message_key=None if diagnostic == "INVALID_ARGUMENT" else diagnostic,
            **context,
        )
    if isinstance(error, StoreRefusal) and diagnostic == "STORE_UNAVAILABLE":
        return refusal(503, "STORE_UNAVAILABLE", message_key=None, **context)
    if isinstance(error, TimeoutError):
        return refusal(504, "QUERY_TIMEOUT", message_key=diagnostic, **context)
    return refusal(500, "INTERNAL", message_key=diagnostic, **context)


def respond(
    run: Callable[[], PublicResult | MakeAreaResult],
    *,
    ledger: LocalLedger,
    engine: EngineName,
    arguments: dict[str, Any],
    prepare: Callable[[PublicResult], Callable[[], None]] | None = None,
) -> JSONResponse:
    """Do not release an envelope until exactly one ledger entry is verified."""
    try:
        result = run()
        if result.status == "INVALID_ARGUMENT":
            return refusal(
                422,
                "INVALID_ARGUMENT",
                message_key=closed_code(result.reason, "INVALID_ARGUMENT")
                if result.reason is not None
                else None,
            )
        if result.status not in GOVERNED:
            return refusal(500, "INTERNAL")
        admit = (
            prepare(result)
            if prepare is not None and isinstance(result, PublicResult)
            else None
        )
        facts = result.facts if isinstance(result, PublicResult) else ()
        blocks = result.blocks if isinstance(result, PublicResult) else ()
        caveats = list(result.caveat_keys) if isinstance(result, PublicResult) else []
        if result.reason is not None:
            caveats.append(result.reason)
        call_id = str(uuid4())
        body = {
            "tool": result.tool,
            "call_id": call_id,
            "release_id": result.release_id,
            "engine": engine,
            "status": result.status,
            "blocks": list(blocks),
            "facts": [wire_fact(fact) for fact in facts],
            "payload": result.payload,
            "caveat_keys": caveats,
        }
        # Serialize before committing, so even a malformed payload leaves no row.
        response = JSONResponse(content=jsonable_encoder(body))
        entry = tool_entry(
            answer_id=call_id,
            tool=result.tool,
            arguments=arguments,
            release_id=result.release_id,
            engine=engine,
            status=result.status,
            fact_ids=[fact.fact_id for fact in facts],
        )
        with ledger.transaction():
            ledger.write(entry)
            ledger.require_entry(entry)
        if admit is not None:
            admit()
        return response
    except Exception as error:
        return error_response(error)
