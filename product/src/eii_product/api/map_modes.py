"""Closed map availability and ephemeral same-origin provider routes."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import TypedDict

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response

from eii_core.reasons import closed_code
from eii_core.reasons import reason as closed_reason
from eii_product.api.playbooks import refusal
from eii_product.config import map_setting, read_maptile_api_key
from eii_product.photoreal_tiles.limit import (
    LOCK,
    Budget,
    BudgetFailure,
    JournalStep,
    billable_limit,
    encode_spend_meter,
    journal_order_token,
    meter_for_count,
)
from eii_product.photoreal_tiles.native import NativeFailure, NativeViews
from eii_product.photoreal_tiles.proxy import (
    closed_path,
    fetch_tile,
    safe_response,
    satellite_credit,
    valid_base,
)

NO_STORE = {"Cache-Control": "no-store"}


def build_router(
    key_reader: Callable[[], str | None],
    offline_reader: Callable[[], bool],
    opener: Callable[..., object],
    count_path: Path,
) -> APIRouter:
    router = APIRouter()
    budget = Budget(count_path)
    native = NativeViews()

    def pricing() -> tuple[Decimal, int]:
        try:
            price = Decimal(map_setting("EII_PHOTOREAL_PRICE_PER_THOUSAND") or "6")
            maximum = billable_limit(price)
            configured = map_setting("EII_PHOTOREAL_LIMIT")
            limit = min(maximum, max(0, int(configured))) if configured else maximum
            return price, limit
        except (ValueError, InvalidOperation) as error:
            raise BudgetFailure(closed_reason(error, "count_unavailable")) from None

    def limit() -> int:
        return pricing()[1]

    def reason(satellite: bool) -> str | None:
        key = key_reader() if satellite else read_maptile_api_key()
        if not key:
            return "no_key"
        if offline_reader() is not False:
            return "offline"
        base = map_setting(
            "EII_IMAGERY_TILE_BASE" if satellite else "EII_PHOTOREAL_TILE_BASE"
        )
        if not valid_base(base):
            return "no_address"
        if not satellite:
            try:
                budget.available(limit())
            except BudgetFailure as error:
                return closed_reason(error, "count_unavailable")
        return None

    @router.get("/api/map-modes")
    def map_modes() -> JSONResponse:
        modes: dict[str, object] = {"open": {"available": True, "reason": None}}
        for mode, satellite in (("satellite", True), ("photoreal", False)):
            why = reason(satellite)
            if satellite:
                modes[mode] = {"available": why is None, "reason": why}
                continue
            meter = None
            try:
                price, maximum = pricing()
                meter = budget.meter(maximum, price)
                if why in {None, "cap_reached"}:
                    why = (
                        "cap_reached" if meter["billable_requests"] >= maximum else None
                    )
            except BudgetFailure as error:
                if why is None or why == "cap_reached":
                    why = closed_reason(error, "count_unavailable")
            modes[mode] = {"available": why is None, "reason": why, "meter": meter}
        return JSONResponse(modes, headers=NO_STORE)

    @router.get("/api/imagery/tiles/{z}/{x}/{y}")
    def imagery(z: str, x: str, y: str) -> Response:
        why = reason(True)
        if why is not None:
            return refuse(why)
        if not all(
            value.isascii() and value.isdecimal() and len(value) <= 2 for value in (z,)
        ):
            return refuse()
        zoom = int(z)
        if zoom > 30 or not all(
            value.isascii() and value.isdecimal() and len(value) <= 10
            for value in (x, y)
        ):
            return refuse()
        if int(x) >= 2**zoom or int(y) >= 2**zoom:
            return refuse()
        key = key_reader()
        if not key:
            return refuse()
        try:
            credit = satellite_credit(opener, map_setting("EII_IMAGERY_TILE_BASE"), key)
        except Exception as error:
            return refuse(closed_reason(error))
        if not credit:
            return refuse()
        try:
            result = fetch_tile(
                opener,
                map_setting("EII_IMAGERY_TILE_BASE"),
                f"tile/{z}/{y}/{x}",
                key,
                satellite=True,
            )
        except Exception as error:
            return refuse(closed_reason(error))
        status, raw, headers = result
        if not safe_response(raw, headers, key):
            return refuse()
        headers["x-attribution"] = credit
        return deliver((status, raw, headers), key, require_credit=True)

    @router.post("/api/photoreal/views")
    def new_view() -> Response:
        why = reason(False)
        if why is not None:
            return refuse(why)
        with LOCK:
            native.purge()
            identifier = uuid.uuid4().hex
            native.create(identifier)
        return JSONResponse({"view_id": identifier}, headers=NO_STORE)

    @router.delete("/api/photoreal/views/{identifier}")
    def dispose_view(identifier: str) -> Response:
        with LOCK:
            native.dispose(identifier)
        return Response(status_code=204, headers=NO_STORE)

    @router.get("/api/photoreal/{path:path}")
    def photoreal(path: str, request: Request) -> Response:
        if (
            not closed_path(path)
            or set(request.query_params) != {"view"}
            or len(request.query_params.multi_items()) != 1
        ):
            return refuse()
        view = request.query_params["view"]
        with LOCK:
            if not native.contains(view):
                return refuse()
            why = reason(False)
            if why is not None:
                return refuse(why)
            key = read_maptile_api_key()
            if not key:
                return refuse()
            try:
                target = native.target(
                    view, path, map_setting("EII_PHOTOREAL_TILE_BASE")
                )
            except NativeFailure as error:
                return refuse(closed_reason(error))
            step = JournalStep()
            try:
                result = budget.request(
                    limit(),
                    lambda: fetch_tile(
                        opener,
                        map_setting("EII_PHOTOREAL_TILE_BASE"),
                        path,
                        key,
                        satellite=False,
                        native=target,
                    ),
                    lambda response: 200 <= response[0] < 300,
                    step,
                )
            except BudgetFailure as error:
                return refuse(closed_reason(error))
            issued = meter_header(pricing, step.count)
            status, raw, headers = result
            if not 200 <= status < 300 or not safe_response(raw, headers, key):
                native.dispose(view)
                return refuse(
                    closed_code(headers.get("x-eii-error-code"), "response_unavailable")
                )
            try:
                if target.path.endswith(".json"):
                    raw = native.rewrite(
                        view, target, raw, map_setting("EII_PHOTOREAL_TILE_BASE")
                    )
                    headers["content-type"] = "application/json"
                native.refuse_session_echo(view, raw)
            except NativeFailure as error:
                native.dispose(view)
                return refuse(closed_reason(error))
            return deliver(
                (status, raw, headers),
                key,
                require_credit=False,
                meter=None if issued is None else issued["meter"],
                order=None if issued is None else issued["order"],
            )

    return router


def refuse(reason: str = "no_key") -> JSONResponse:
    capped = reason == "cap_reached"
    response = refusal(
        429 if capped else 404,
        "PROVIDER_CAP_REACHED" if capped else "NOT_FOUND",
        message_key=closed_code(reason, "operation_failed"),
    )
    response.headers.update(NO_STORE)
    return response


class IssuedSpend(TypedDict):
    meter: str
    order: str


def meter_header(
    pricing: Callable[[], tuple[Decimal, int]],
    step: int | None,
) -> IssuedSpend | None:
    """Meter and order token for the journal step just appended.

    A failed read sends neither. The token is that step, not a later count.
    """
    if step is None:
        return None
    try:
        price, maximum = pricing()
        return {
            "meter": encode_spend_meter(meter_for_count(step, maximum, price)),
            "order": journal_order_token(step),
        }
    except BudgetFailure:
        return None


def deliver(
    result: tuple[int, bytes, dict[str, str]],
    key: str,
    *,
    require_credit: bool,
    meter: str | None = None,
    order: str | None = None,
) -> Response:
    status, raw, headers = result
    if not 200 <= status < 300 or not safe_response(raw, headers, key):
        return refuse(
            closed_code(headers.get("x-eii-error-code"), "response_unavailable")
        )
    outgoing = dict(NO_STORE)
    credit = headers.get("x-attribution", "")
    if (require_credit and not credit) or (
        credit and (not credit.isascii() or any(ord(c) < 32 for c in credit))
    ):
        return refuse()
    if credit:
        outgoing["X-Attribution"] = credit
    if meter is not None:
        outgoing["X-Spend-Meter"] = meter
        if order is not None:
            outgoing["X-Spend-Order"] = order
    content_type = headers.get("content-type", "application/octet-stream")
    if content_type not in {
        "image/png",
        "image/jpeg",
        "application/json",
        "application/octet-stream",
        "model/gltf-binary",
    }:
        return refuse()
    return Response(raw, status_code=status, headers=outgoing, media_type=content_type)
