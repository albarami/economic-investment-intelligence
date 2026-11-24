"""The sole entry for drawn polygons: bounded JSON and core validation."""

import json
from decimal import Decimal

from fastapi import APIRouter, Request
from starlette.responses import JSONResponse, Response

from eii_core.shapes import Ring, canonical_ring, polygon_inside_land, ring_is_simple
from eii_product.api.playbooks import refusal
from eii_product.api.results import error_response
from eii_product.api.session_store import CapReached, SessionStore, ShapeLimit
from eii_product.store.protocol import ReleaseStore
from eii_product.store.registry import PACKAGED
from eii_product.tools.make_area import read_land

BODY_LIMIT = 64 * 1024
VERTEX_LIMIT = 500


def _pairs(items: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in items:
        if key in result:
            raise ValueError("INVALID_ARGUMENT")
        result[key] = value
    return result


def _number(value: object, limit: int) -> Decimal:
    if isinstance(value, Decimal):
        number = value
    elif type(value) is int:
        number = Decimal(value)
    else:
        raise ValueError("INVALID_ARGUMENT")
    if not number.is_finite() or not -limit <= number <= limit:
        raise ValueError("INVALID_ARGUMENT")
    return number


def _ring(raw: object) -> Ring:
    if type(raw) is not dict or set(raw) != {"geometry"}:
        raise ValueError("INVALID_ARGUMENT")
    geometry = raw["geometry"]
    if (
        type(geometry) is not dict
        or set(geometry) != {"type", "coordinates"}
        or geometry["type"] != "Polygon"
    ):
        raise ValueError("INVALID_ARGUMENT")
    coordinates = geometry["coordinates"]
    if type(coordinates) is not list or len(coordinates) != 1:
        raise ValueError("INVALID_ARGUMENT")
    points = coordinates[0]
    if type(points) is not list or not 4 <= len(points) <= VERTEX_LIMIT:
        raise ValueError("INVALID_ARGUMENT")
    prepared = []
    for point in points:
        if type(point) is not list or len(point) != 2:
            raise ValueError("INVALID_ARGUMENT")
        lon, lat = point
        prepared.append((_number(lat, 90), _number(lon, 180)))
    if prepared[0] != prepared[-1]:
        raise ValueError("INVALID_ARGUMENT")
    ring = canonical_ring(prepared)
    if not ring_is_simple(ring):
        raise ValueError("INVALID_ARGUMENT")
    return ring


def build_router(store: ReleaseStore | None, sessions: SessionStore) -> APIRouter:
    router = APIRouter()

    @router.post("/api/areas/shapes", response_model=None)
    async def register(request: Request) -> Response:
        if (
            request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
            != "application/json"
        ):
            return refusal(422, "INVALID_ARGUMENT")
        body = bytearray()
        async for part in request.stream():
            if len(body) + len(part) > BODY_LIMIT:
                return refusal(422, "INVALID_ARGUMENT")
            body.extend(part)
        try:
            ring = _ring(
                json.loads(body, parse_float=Decimal, object_pairs_hook=_pairs)
            )
        except (TypeError, ValueError, ArithmeticError):
            return refusal(422, "INVALID_ARGUMENT")
        try:
            if store is None:
                return refusal(500, "INTERNAL")
            land = read_land(store, PACKAGED)
            inside = polygon_inside_land(ring, land)
        except Exception as error:
            return error_response(error)
        if not inside:
            return refusal(422, "INVALID_ARGUMENT")
        admitted = sessions.admit(request.cookies.get("eii_session"))
        if isinstance(admitted, CapReached):
            return refusal(429, "RATE_LIMITED")
        try:
            shape_id = admitted.shapes.add(ring)
        except ShapeLimit:
            return refusal(422, "INVALID_ARGUMENT")
        response = JSONResponse(status_code=201, content={"shape_id": shape_id})
        admitted.keep(response)
        return response

    return router
