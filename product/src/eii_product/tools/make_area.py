"""Public-only make_area. One validation table, then reads, then geometry.

The inventory arrives beside the store, on the call context. A release that is
not public-only returns the internal status RELEASE_MODE and reads nothing.
That status is not a public-only answer.
"""

from __future__ import annotations

import math
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Protocol, cast

from eii_core.grid import (
    base_cell,
    cell_centre,
    cells_in_circle,
    cells_in_polygon,
)
from eii_core.reasons import reason
from eii_core.shapes import (
    GEOMETRY_REFUSED,
    GeometryTextError,
    Point,
    Polygon,
    Ring,
    canonical_ring,
    decode_geometry,
    exact_point,
    point_in_land,
    point_in_ring,
    polygon_inside_land,
    reduce_six,
    representative_point,
    ring_is_simple,
    within_radius,
)
from eii_product.store.protocol import QueryResult
from eii_product.store.registry import Inventory
from eii_product.tools.areas import (
    INVALID_ARGUMENT,
    AreaIdError,
    build_area_id,
    canonical_json,
    parse_area_id,
    valid_area_id,
)
from eii_product.tools.routing import accepted_ring, outline

DISTANCE_M = frozenset({250, 500, 1000})
WALK_MINUTES = frozenset({5, 10, 15})
DRIVE_MINUTES = frozenset({5, 10, 15})
DRIVE_STAFFING_MINUTES = frozenset({20, 30})
DRIVE_LIMIT_MINUTES = 30
SITUATIONS = frozenset(
    {"weekday_lunch", "weekday_evening", "friday_evening", "ramadan_iftar"}
)
STAFFING_AND_PAY = "staffing_and_pay"
PUBLIC_ONLY = "public_only"
RELEASE_MODE = "RELEASE_MODE"
NOTE_SNAPPED = "SNAPPED_TO_WHOLE_UNITS"
GRID_QUERY = "make_area_grid_cells"
MUNICIPALITY_QUERY = "make_area_municipalities"
GAZETTEER_QUERY = "make_area_gazetteer_point"
QUERY_NAMES = (GRID_QUERY, MUNICIPALITY_QUERY, GAZETTEER_QUERY)

_SHAPE_ID = re.compile(r"[0-9a-f]{64}\Z")
_PLACE_KEY = re.compile(
    r"(?:[A-Za-z][A-Za-z0-9-]*|(?:district|zone|municipality):[A-Za-z0-9][A-Za-z0-9_-]*)\Z"
)
_FORBIDDEN_KEY_DIGITS = re.compile(r"(?<![0-9])(?:[0-9]{8}|[0-9]{11})(?![0-9])")
_PIN_KEYS = frozenset(
    {
        "latitude",
        "longitude",
        "place_key",
        "mode",
        "cutoff",
        "situation",
        "summer",
        "hour_key",
        "day_key",
    }
)
_SHAPE_KEYS = frozenset({"shape_id"})
_AREA_ID_KEYS = frozenset({"area_id"})
_GEOMETRY_KEYS = frozenset({"ring", "geometry", "coordinates", "features", "type"})
_MODES = frozenset({"distance", "walk", "drive"})
_LAT_MIN = Decimal(-90)
_LAT_MAX = Decimal(90)
_LON_MIN = Decimal(-180)
_LON_MAX = Decimal(180)

RoutingCall = Callable[[str, int, Decimal, Decimal], tuple[tuple[object, object], ...]]
PublicPoint = tuple[str, Decimal, Decimal]


class ArgumentError(ValueError):
    """The closed schema refused the request. The message is INVALID_ARGUMENT."""


@dataclass(frozen=True)
class DriveOptions:
    """Drive keys. All empty means free flow."""

    situation: str | None
    summer: bool | None
    hour_key: str | None
    day_key: str | None

    def keyed(self) -> bool:
        """True when a situation, an hour or a day key is present."""
        return (
            self.situation is not None
            or self.hour_key is not None
            or self.day_key is not None
        )


@dataclass(frozen=True)
class PinRequest:
    """A pin. Coordinates are absent until a gazetteer key is resolved."""

    mode: str
    cutoff: int
    latitude: Decimal | None
    longitude: Decimal | None
    place_key: str | None
    drive: DriveOptions | None


@dataclass(frozen=True)
class ShapeRequest:
    """A drawn shape, carried only by its identifier."""

    shape_id: str


@dataclass(frozen=True)
class AreaIdRequest:
    """A returned area, carried only by its identifier (decision 0087)."""

    area_id: str


@dataclass(frozen=True)
class RegisteredShape:
    """The polygon registered for this session and seat."""

    ring: tuple[tuple[object, object], ...]


@dataclass(frozen=True)
class ShapeMiss:
    """The lookup port's refusal. ``not_yours`` is another session or seat."""

    reason: str


class _Fetcher(Protocol):
    """The store method this tool calls. The parameter stays a looked-up name."""

    def fetch(self, query: object, params: Mapping[str, object]) -> QueryResult:
        """Run one inventory query."""


class ShapePort(Protocol):
    """The lookup port. This task does not build the route or the session store."""

    def find(self, shape_id: str) -> RegisteredShape | ShapeMiss:
        """Return the polygon, or unknown, or not yours."""


@dataclass(frozen=True)
class MakeAreaContext:
    """What the application supplies beside the store. The playbook is not a field."""

    release_id: str
    release_mode: str
    playbook_key: str | None
    inventory: Inventory
    shapes: ShapePort
    tile_folder: Path | None = None
    routing: RoutingCall | None = None
    hour_keys: frozenset[str] = frozenset()
    day_keys: frozenset[str] = frozenset()
    # Server-owned layer snapshot, keyed by layer, in latitude/longitude order.
    # None means unavailable. This is not a request or a release schema field.
    public_points: Mapping[str, tuple[PublicPoint, ...]] | None = None
    point_snapshot: Callable[[], Mapping[str, tuple[PublicPoint, ...]]] | None = None
    # Sources the serving policy keeps off for a hosted service (S3-T20 B5).
    hosting_off: frozenset[str] = frozenset()


@dataclass(frozen=True)
class MakeAreaResult:
    """The tool result. It holds no fact."""

    tool: str
    status: str
    reason: str | None
    release_id: str
    payload: Mapping[str, object] | None


def validate_request(
    request: Mapping[str, object],
    playbook_key: str | None,
    hour_keys: frozenset[str] = frozenset(),
    day_keys: frozenset[str] = frozenset(),
) -> PinRequest | ShapeRequest | AreaIdRequest:
    """Accept one closed request. Nothing is read or routed.

    ``hour_keys`` and ``day_keys`` are the closed lists the application supplies.
    """
    if any(key in _GEOMETRY_KEYS for key in request):
        raise ArgumentError(INVALID_ARGUMENT)
    if "area_id" in request:
        return _area_id(request)
    if "shape_id" in request:
        return _shape(request)
    return _pin(request, playbook_key, hour_keys, day_keys)


def validate_before_read(
    request: Mapping[str, object],
    playbook_key: str | None,
    store: object,
    route: object,
    hour_keys: frozenset[str] = frozenset(),
    day_keys: frozenset[str] = frozenset(),
) -> PinRequest | ShapeRequest | AreaIdRequest:
    """Validate before any read or route. The stand-ins are not called."""
    del store, route
    return validate_request(request, playbook_key, hour_keys, day_keys)


def make_area(
    store: object, request: Mapping[str, object], context: MakeAreaContext
) -> MakeAreaResult:
    """Build one public-only area, or a status from the check order."""
    if context.release_mode != PUBLIC_ONLY:
        return _result(context, RELEASE_MODE, "release_not_public_only", None)
    try:
        parsed = validate_request(
            request, context.playbook_key, context.hour_keys, context.day_keys
        )
    except (ArgumentError, AreaIdError):
        return _invalid(context)
    if isinstance(parsed, AreaIdRequest):
        return decode_area(store, parsed.area_id, context)
    try:
        return _checked(store, parsed, context)
    except GeometryTextError as error:
        raise ValueError(reason(error)) from None
    except (ArgumentError, AreaIdError):
        return _invalid(context)


def decode_area(
    store: object, area_id: str, context: MakeAreaContext
) -> MakeAreaResult:
    """Decode an identifier through the closed schema and the same path."""
    if context.release_mode != PUBLIC_ONLY:
        return _result(context, RELEASE_MODE, "release_not_public_only", None)
    try:
        request = parse_area_id(area_id, context.release_id)
    except AreaIdError:
        return _invalid(context)
    carries_cell = "cell" in request
    encoded_cell = request.pop("cell") if carries_cell else None
    result = make_area(store, request, context)
    if result.payload is None:
        return result
    if carries_cell and not _encoded_cell_matches(encoded_cell, result.payload):
        return _invalid(context)
    if result.payload["area_id"] != area_id:
        return _invalid(context)
    return result


def _encoded_cell_matches(encoded: object, payload: Mapping[str, object]) -> bool:
    """The cell spelled in the identifier equals the recomputed anchor."""
    record = payload["record"]
    if not isinstance(record, Mapping):
        return False
    anchor = record["anchor_cell"]
    if encoded is None:
        return anchor is None
    if type(anchor) is not str:
        return False
    return anchor == str(encoded)


def read_land(store: object, inventory: Inventory) -> tuple[Polygon, ...]:
    """Fetch the municipality query and decode its geometry text."""
    result = _fetch(store, inventory, MUNICIPALITY_QUERY, {})
    polygons: list[Polygon] = []
    for row in result.rows:
        text = row[1]
        if text is None:
            continue
        if type(text) is not str:
            raise GeometryTextError(GEOMETRY_REFUSED)
        polygons.extend(decode_geometry(text))
    return tuple(polygons)


def canonical_payload(result: MakeAreaResult) -> bytes:
    """Byte-stable JSON of the payload. A result without one is the status."""
    body = {
        "status": result.status,
        "reason": result.reason,
        "payload": result.payload,
    }
    return canonical_json(body)


def _checked(
    store: object, parsed: PinRequest | ShapeRequest, context: MakeAreaContext
) -> MakeAreaResult:
    if isinstance(parsed, ShapeRequest):
        return _shape_area(store, parsed, context)
    return _pin_area(store, parsed, context)


def _shape_area(
    store: object, parsed: ShapeRequest, context: MakeAreaContext
) -> MakeAreaResult:
    found = context.shapes.find(parsed.shape_id)
    if isinstance(found, ShapeMiss):
        return _invalid(context)
    ring = _registered_ring(found.ring)
    land = read_land(store, context.inventory)
    if not polygon_inside_land(ring, land):
        return _out(context)
    frame = _frame(store, context.inventory)
    anchor = base_cell(*_floats(representative_point(ring)), frame)
    selected = cells_in_polygon((ring,), frame)
    outline_body = _ring_outline(ring)
    return _ok(
        context,
        "polygon",
        None,
        None,
        parsed.shape_id,
        None,
        anchor,
        outline_body,
        selected,
        True,
    )


def _pin_area(
    store: object, parsed: PinRequest, context: MakeAreaContext
) -> MakeAreaResult:
    latitude, longitude = _resolve(store, parsed, context)
    land = read_land(store, context.inventory)
    point = exact_point(latitude, longitude)
    if not point_in_land(point, land):
        return _out(context)
    frame = _frame(store, context.inventory)
    anchor = base_cell(float(latitude), float(longitude), frame)
    keyed = parsed.drive is not None and parsed.drive.keyed()
    if keyed and anchor is None:
        return _result(context, "NO_DATA", "point_without_base_cell", None)
    if keyed and anchor is not None:
        return _invalid(context)
    if anchor is None:
        outline_body = _pin_outline(parsed, latitude, longitude, context)
        return _ok(
            context,
            parsed.mode,
            latitude,
            longitude,
            None,
            parsed.cutoff,
            None,
            outline_body,
            None,
            False,
        )
    selected, outline_body = _with_cell(
        parsed, latitude, longitude, anchor, frame, context
    )
    return _ok(
        context,
        parsed.mode,
        latitude,
        longitude,
        None,
        parsed.cutoff,
        anchor,
        outline_body,
        selected,
        True,
    )


def _with_cell(
    parsed: PinRequest,
    latitude: Decimal,
    longitude: Decimal,
    anchor: int,
    frame: tuple[tuple[int, int], ...],
    context: MakeAreaContext,
) -> tuple[tuple[int, ...], dict[str, object]]:
    if parsed.mode == "distance":
        centre = cell_centre(anchor)
        selected = cells_in_circle(centre[0], centre[1], float(parsed.cutoff), frame)
        return selected, _circle_outline(longitude, latitude, parsed.cutoff)
    ring = accepted_ring(
        _routing(context, parsed.mode, parsed.cutoff, latitude, longitude)
    )
    selected = cells_in_polygon((ring,), frame)
    if anchor not in selected:
        selected = tuple(sorted((*selected, anchor)))
    return selected, _ring_outline(ring)


def _pin_outline(
    parsed: PinRequest,
    latitude: Decimal,
    longitude: Decimal,
    context: MakeAreaContext,
) -> dict[str, object]:
    if parsed.mode == "distance":
        return _circle_outline(longitude, latitude, parsed.cutoff)
    ring = accepted_ring(
        _routing(context, parsed.mode, parsed.cutoff, latitude, longitude)
    )
    return _ring_outline(ring)


def _routing(
    context: MakeAreaContext,
    mode: str,
    minutes: int,
    latitude: Decimal,
    longitude: Decimal,
) -> tuple[tuple[object, object], ...]:
    if context.routing is not None:
        return context.routing(mode, minutes, latitude, longitude)
    if context.tile_folder is None:
        raise ValueError("routing_tiles")
    return outline(
        context.tile_folder, mode, minutes, float(latitude), float(longitude)
    )


def _resolve(
    store: object, parsed: PinRequest, context: MakeAreaContext
) -> tuple[Decimal, Decimal]:
    if parsed.place_key is not None:
        found = _place(store, context.inventory, parsed.place_key)
        if found is None:
            raise ArgumentError(INVALID_ARGUMENT)
        return reduce_six(found[0]), reduce_six(found[1])
    if parsed.latitude is None or parsed.longitude is None:
        raise ArgumentError(INVALID_ARGUMENT)
    return reduce_six(parsed.latitude), reduce_six(parsed.longitude)


def _place(
    store: object, inventory: Inventory, place_key: str
) -> tuple[Decimal, Decimal] | None:
    result = _fetch(store, inventory, GAZETTEER_QUERY, {"place_key": place_key})
    if len(result.rows) != 1:
        return None
    _key, lon, lat = result.rows[0]
    return _decimal(lat), _decimal(lon)


def _frame(store: object, inventory: Inventory) -> tuple[tuple[int, int], ...]:
    result = _fetch(store, inventory, GRID_QUERY, {})
    rows: list[tuple[int, int]] = []
    for cell, resolution in result.rows:
        if type(cell) is not int or type(resolution) is not int:
            raise ValueError("grid_row_invalid")
        rows.append((cell, resolution))
    return tuple(rows)


def _fetch(
    store: object, inventory: Inventory, name: str, params: Mapping[str, object]
) -> QueryResult:
    return cast(_Fetcher, store).fetch(inventory.lookup(name), params)


def _ok(
    context: MakeAreaContext,
    mode: str,
    latitude: Decimal | None,
    longitude: Decimal | None,
    shape_id: str | None,
    cutoff: int | None,
    anchor: int | None,
    outline_body: dict[str, object],
    selected: tuple[int, ...] | None,
    report: bool,
) -> MakeAreaResult:
    area_id = build_area_id(
        release_id=context.release_id,
        mode=None if shape_id is not None else mode,
        cutoff=None if shape_id is not None else cutoff,
        cell=anchor,
        latitude=latitude,
        longitude=longitude,
        shape_id=shape_id,
    )
    record = _record(
        context.release_id,
        area_id,
        mode,
        latitude,
        longitude,
        shape_id,
        cutoff,
        anchor,
        outline_body,
    )
    cells = None if selected is None else [str(cell) for cell in selected]
    snap = None
    if report and cells is not None:
        snap = {"cells": list(cells), "note": NOTE_SNAPPED}
    payload: dict[str, object] = {
        "area_id": area_id,
        "outline": outline_body,
        "record": record,
        "units": {} if cells is None else {"cells": cells},
        "snap_report": snap,
        "point_feature_ids": _point_feature_ids(
            context.point_snapshot()
            if context.point_snapshot is not None
            else context.public_points,
            outline_body,
        ),
    }
    return _result(context, "OK", None, payload)


def _point_feature_ids(
    layers: Mapping[str, tuple[PublicPoint, ...]] | None,
    shape: Mapping[str, object],
) -> dict[str, list[str]] | None:
    """Exact-shape membership of the server's Public layer snapshot only.

    Geometry comes from this tool's returned outline, never its snapped cells.
    A missing snapshot remains unavailable; non-point features are not inputs.
    """
    if layers is None:
        return None
    if shape["type"] == "Circle":
        lon, lat = cast(list[Decimal], shape["coordinates"])
        radius = cast(int, shape["radius_m"])

        def inside(latitude: Decimal, longitude: Decimal) -> bool:
            return within_radius(
                (float(lat), float(lon)),
                (float(latitude), float(longitude)),
                float(radius),
            )
    else:
        rings = cast(list[list[list[Decimal]]], shape["coordinates"])
        ring = tuple(exact_point(lat, lon) for lon, lat in rings[0])

        def inside(latitude: Decimal, longitude: Decimal) -> bool:
            return point_in_ring(exact_point(latitude, longitude), ring)

    return {
        key: sorted(
            {identifier for identifier, lat, lon in layers[key] if inside(lat, lon)}
        )
        for key in sorted(layers)
    }


def _record(
    release_id: str,
    area_id: str,
    mode: str,
    latitude: Decimal | None,
    longitude: Decimal | None,
    shape_id: str | None,
    cutoff: int | None,
    anchor: int | None,
    outline_body: dict[str, object],
) -> dict[str, object]:
    if shape_id is not None:
        shape = "polygon"
        request: dict[str, object] = {"shape_id": shape_id}
    elif mode == "distance":
        shape = "radius"
        request = {"point": _point(*_pair(latitude, longitude)), "radius_m": cutoff}
    else:
        shape = mode
        request = {"point": _point(*_pair(latitude, longitude)), "minutes": cutoff}
    return {
        "traffic": "free_flow",
        "shape": shape,
        "request": request,
        "release_id": release_id,
        "area_id": area_id,
        "anchor_cell": None if anchor is None else str(anchor),
        "requested_shape": outline_body,
    }


def _pair(
    latitude: Decimal | None, longitude: Decimal | None
) -> tuple[Decimal, Decimal]:
    if latitude is None or longitude is None:
        raise ArgumentError(INVALID_ARGUMENT)
    return latitude, longitude


def _point(latitude: Decimal, longitude: Decimal) -> dict[str, str]:
    from eii_product.tools.areas import format_six

    return {"latitude": format_six(latitude), "longitude": format_six(longitude)}


def _circle_outline(
    longitude: Decimal, latitude: Decimal, radius_m: int
) -> dict[str, object]:
    return {
        "type": "Circle",
        "coordinates": [longitude, latitude],
        "radius_m": radius_m,
    }


def _ring_outline(ring: tuple[Point, ...]) -> dict[str, object]:
    coordinates = [
        [_decimal_number(point[1]), _decimal_number(point[0])] for point in ring
    ]
    return {"type": "Polygon", "coordinates": [coordinates]}


def _decimal_number(value: object) -> Decimal:
    if type(value) is Decimal:
        return value
    from fractions import Fraction

    if type(value) is Fraction:
        return _exact_finite_decimal(value)
    raise ArgumentError(INVALID_ARGUMENT)


def _exact_finite_decimal(value: object) -> Decimal:
    """Exact decimal of a finite fraction, with no division in the decimal context."""
    from fractions import Fraction

    if type(value) is not Fraction:
        raise ArgumentError(INVALID_ARGUMENT)
    numerator = value.numerator
    denominator = value.denominator
    twos = 0
    while denominator % 2 == 0:
        denominator //= 2
        twos += 1
    fives = 0
    while denominator % 5 == 0:
        denominator //= 5
        fives += 1
    if denominator != 1:
        raise ArgumentError(INVALID_ARGUMENT)
    if twos > fives:
        numerator *= 5 ** (twos - fives)
        places = twos
    else:
        numerator *= 2 ** (fives - twos)
        places = fives
    sign = 1 if numerator < 0 else 0
    digits = tuple(int(character) for character in str(abs(numerator)))
    return Decimal((sign, digits, -places))


def _floats(point: Point) -> tuple[float, float]:
    return (float(point[0]), float(point[1]))


def _decimal(value: object) -> Decimal:
    if type(value) is int and not isinstance(value, bool):
        return Decimal(value)
    if type(value) is Decimal:
        return value
    raise ArgumentError(INVALID_ARGUMENT)


def _result(
    context: MakeAreaContext,
    status: str,
    reason: str | None,
    payload: dict[str, object] | None,
) -> MakeAreaResult:
    return MakeAreaResult("make_area", status, reason, context.release_id, payload)


def _invalid(context: MakeAreaContext) -> MakeAreaResult:
    return _result(context, INVALID_ARGUMENT, None, None)


def _out(context: MakeAreaContext) -> MakeAreaResult:
    return _result(context, "OUT_OF_SCOPE", None, None)


def _registered_ring(points: tuple[tuple[object, object], ...]) -> Ring:
    """Canonical simple ring, or INVALID_ARGUMENT. No geometry error escapes."""
    ring: Ring | None = None
    try:
        candidate = canonical_ring(points)
        if ring_is_simple(candidate):
            ring = candidate
    except (TypeError, ValueError):
        ring = None
    if ring is None:
        raise ArgumentError(INVALID_ARGUMENT)
    return ring


def _shape(request: Mapping[str, object]) -> ShapeRequest:
    if set(request) != _SHAPE_KEYS:
        raise ArgumentError(INVALID_ARGUMENT)
    shape_id = request["shape_id"]
    if type(shape_id) is not str or _SHAPE_ID.fullmatch(shape_id) is None:
        raise ArgumentError(INVALID_ARGUMENT)
    return ShapeRequest(shape_id)


def _area_id(request: Mapping[str, object]) -> AreaIdRequest:
    """The identifier alone, in the grammar of section 11.1; the release binds later."""
    if set(request) != _AREA_ID_KEYS:
        raise ArgumentError(INVALID_ARGUMENT)
    area_id = request["area_id"]
    if type(area_id) is not str or not valid_area_id(area_id):
        raise ArgumentError(INVALID_ARGUMENT)
    return AreaIdRequest(area_id)


def _pin(
    request: Mapping[str, object],
    playbook_key: str | None,
    hour_keys: frozenset[str],
    day_keys: frozenset[str],
) -> PinRequest:
    if (
        not set(request) <= _PIN_KEYS
        or "mode" not in request
        or "cutoff" not in request
    ):
        raise ArgumentError(INVALID_ARGUMENT)
    mode = request["mode"]
    if type(mode) is not str or mode not in _MODES:
        raise ArgumentError(INVALID_ARGUMENT)
    cutoff = _cutoff(mode, request["cutoff"], playbook_key)
    drive = _drive(request, mode, hour_keys, day_keys)
    latitude, longitude, place_key = _where(request)
    return PinRequest(mode, cutoff, latitude, longitude, place_key, drive)


def _cutoff(mode: str, value: object, playbook_key: str | None) -> int:
    if type(value) is not int or isinstance(value, bool):
        raise ArgumentError(INVALID_ARGUMENT)
    if mode == "drive" and value > DRIVE_LIMIT_MINUTES:
        raise ArgumentError(INVALID_ARGUMENT)
    if mode == "distance" and value in DISTANCE_M:
        return value
    if mode == "walk" and value in WALK_MINUTES:
        return value
    if mode == "drive" and value in DRIVE_MINUTES:
        return value
    if (
        mode == "drive"
        and value in DRIVE_STAFFING_MINUTES
        and playbook_key == STAFFING_AND_PAY
    ):
        return value
    raise ArgumentError(INVALID_ARGUMENT)


def _drive(
    request: Mapping[str, object],
    mode: str,
    hour_keys: frozenset[str],
    day_keys: frozenset[str],
) -> DriveOptions | None:
    named = ("situation", "summer", "hour_key", "day_key")
    present = {key for key in named if key in request}
    if mode != "drive":
        if present:
            raise ArgumentError(INVALID_ARGUMENT)
        return None
    if not present:
        return DriveOptions(None, None, None, None)
    situation_form = {"situation", "summer"}
    clock_form = {"hour_key", "day_key"}
    if present <= situation_form:
        if present != situation_form:
            raise ArgumentError(INVALID_ARGUMENT)
        situation = request["situation"]
        summer = request["summer"]
        if type(situation) is not str or situation not in SITUATIONS:
            raise ArgumentError(INVALID_ARGUMENT)
        if type(summer) is not bool:
            raise ArgumentError(INVALID_ARGUMENT)
        if situation == "ramadan_iftar" and summer is True:
            raise ArgumentError(INVALID_ARGUMENT)
        return DriveOptions(situation, summer, None, None)
    if present != clock_form:
        raise ArgumentError(INVALID_ARGUMENT)
    hour_key = request["hour_key"]
    day_key = request["day_key"]
    if type(hour_key) is not str or hour_key not in hour_keys:
        raise ArgumentError(INVALID_ARGUMENT)
    if type(day_key) is not str or day_key not in day_keys:
        raise ArgumentError(INVALID_ARGUMENT)
    return DriveOptions(None, None, hour_key, day_key)


def _where(
    request: Mapping[str, object],
) -> tuple[Decimal | None, Decimal | None, str | None]:
    has_point = "latitude" in request or "longitude" in request
    has_key = "place_key" in request
    if has_point == has_key:
        raise ArgumentError(INVALID_ARGUMENT)
    if has_key:
        place_key = request["place_key"]
        if (
            type(place_key) is not str
            or _PLACE_KEY.fullmatch(place_key) is None
            or _FORBIDDEN_KEY_DIGITS.search(place_key) is not None
        ):
            raise ArgumentError(INVALID_ARGUMENT)
        return None, None, place_key
    latitude = _coordinate(request.get("latitude"))
    longitude = _coordinate(request.get("longitude"))
    _range_check(latitude, longitude)
    return latitude, longitude, None


def _coordinate(value: object) -> Decimal:
    if type(value) is bool or value is None:
        raise ArgumentError(INVALID_ARGUMENT)
    if type(value) is float:
        if not math.isfinite(value):
            raise ArgumentError(INVALID_ARGUMENT)
        number = Decimal.from_float(value)
    elif type(value) is int:
        number = Decimal(value)
    elif type(value) is Decimal:
        if not value.is_finite():
            raise ArgumentError(INVALID_ARGUMENT)
        number = value
    else:
        raise ArgumentError(INVALID_ARGUMENT)
    return number


def _range_check(latitude: Decimal, longitude: Decimal) -> None:
    if not (_LAT_MIN <= latitude <= _LAT_MAX and _LON_MIN <= longitude <= _LON_MAX):
        raise ArgumentError(INVALID_ARGUMENT)
