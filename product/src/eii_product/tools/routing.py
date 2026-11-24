"""In-process walk and free-flow drive outlines. No server, socket or subprocess."""

from __future__ import annotations

import math
from decimal import Decimal
from fractions import Fraction
from pathlib import Path
from typing import Any, cast

from eii_core.shapes import Ring, canonical_ring, ring_is_simple

ROUTING_TILES_UNAVAILABLE = "routing tiles unavailable"


class RoutingTilesUnavailable(RuntimeError):
    """The tile folder cannot be read. The message names no path."""


def outline(
    tile_folder: Path,
    mode: str,
    minutes: int,
    latitude: float,
    longitude: float,
) -> tuple[tuple[float, float], ...]:
    """Return the engine ring as latitude, longitude. The library loads here only."""
    if not _ready(tile_folder):
        raise RoutingTilesUnavailable(ROUTING_TILES_UNAVAILABLE)
    ring = accepted_ring(_isochrone(tile_folder, mode, minutes, latitude, longitude))
    return tuple((float(lat), float(lon)) for lat, lon in ring)


def accepted_ring(value: object) -> Ring:
    """Canonical ring of an engine answer or a latitude, longitude ring.

    Every unusable answer is the closed routing refusal. The refusal is raised
    after the handler, so the message, the cause and the context carry no path
    and no engine text. A boolean is not a number.
    """
    ring: Ring | None = None
    try:
        candidate = canonical_ring(_coordinate_pairs(value))
        if ring_is_simple(candidate):
            ring = candidate
    except (AttributeError, IndexError, KeyError, TypeError, ValueError):
        ring = None
    if ring is None:
        raise RoutingTilesUnavailable(ROUTING_TILES_UNAVAILABLE)
    return ring


def _isochrone(
    tile_folder: Path, mode: str, minutes: int, latitude: float, longitude: float
) -> Any:
    """Open the tiles. An unreadable config or tile folder becomes the closed refusal.

    The refusal is raised after the handler finishes, so the message, the cause
    and the context carry no path.
    """
    import valhalla

    costing = "auto" if mode == "drive" else "pedestrian"
    request = {
        "locations": [{"lat": latitude, "lon": longitude}],
        "costing": costing,
        "contours": [{"time": minutes}],
        "polygons": True,
        "costing_options": {costing: {"speed_types": []}},
    }
    answer = None
    try:
        actor = valhalla.Actor(str(tile_folder / "config.json"))
        answer = actor.isochrone(request)
    except (OSError, RuntimeError, ValueError, TypeError, KeyError):
        answer = None
    if answer is None:
        raise RoutingTilesUnavailable(ROUTING_TILES_UNAVAILABLE)
    return answer


def network_distance(
    tile_folder: Path,
    mode: str,
    origin: tuple[float, float],
    destination: tuple[float, float],
) -> tuple[object, str]:
    """Raw matrix distance on the same tile configuration as the area outline.

    Valhalla matrix API, tag 3.9.1: null is an unreachable connection.
    Unit conversion belongs to eii_core.calc.scan_places, never this adapter.
    """
    import valhalla

    if not _ready(tile_folder) or mode not in {"walk", "drive"}:
        raise RoutingTilesUnavailable(ROUTING_TILES_UNAVAILABLE)
    costing = "auto" if mode == "drive" else "pedestrian"
    request = {
        "sources": [{"lat": origin[0], "lon": origin[1]}],
        "targets": [{"lat": destination[0], "lon": destination[1]}],
        "costing": costing,
        "costing_options": {costing: {"speed_types": []}},
        "units": "kilometers",
        "verbose": True,
    }
    result = None
    try:
        actor = valhalla.Actor(str(tile_folder / "config.json"))
        answer = actor.matrix(request)
        if type(answer) is dict and answer.get("units") == "kilometers":
            value = answer["sources_to_targets"][0][0]["distance"]
            if value is not None:
                _engine_number(value)
            result = (value, "kilometers")
    except (OSError, RuntimeError, ValueError, TypeError, KeyError, IndexError):
        result = None
    if result is None:
        raise RoutingTilesUnavailable(ROUTING_TILES_UNAVAILABLE)
    return result


def _coordinate_pairs(value: object) -> list[tuple[object, object]]:
    if type(value) is dict:
        return _pairs_from_engine(cast(dict[str, object], value))
    if type(value) is not list and type(value) is not tuple:
        raise TypeError(ROUTING_TILES_UNAVAILABLE)
    return [
        _stored_pair(position)
        for position in cast(list[object] | tuple[object, ...], value)
    ]


def _pairs_from_engine(answer: dict[str, object]) -> list[tuple[object, object]]:
    if "features" not in answer:
        raise KeyError(ROUTING_TILES_UNAVAILABLE)
    features = _as_list(answer["features"])
    if len(features) == 0:
        raise ValueError(ROUTING_TILES_UNAVAILABLE)
    feature = _as_dict(features[0])
    if "geometry" not in feature:
        raise KeyError(ROUTING_TILES_UNAVAILABLE)
    geometry = _as_dict(feature["geometry"])
    if geometry.get("type") != "Polygon":
        raise ValueError(ROUTING_TILES_UNAVAILABLE)
    if "coordinates" not in geometry:
        raise KeyError(ROUTING_TILES_UNAVAILABLE)
    coordinates = _as_list(geometry["coordinates"])
    if len(coordinates) != 1:
        raise ValueError(ROUTING_TILES_UNAVAILABLE)
    ring = _as_list(coordinates[0])
    pairs: list[tuple[object, object]] = []
    for position in ring:
        if type(position) is not list:
            raise TypeError(ROUTING_TILES_UNAVAILABLE)
        row = cast(list[object], position)
        if len(row) != 2:
            raise ValueError(ROUTING_TILES_UNAVAILABLE)
        longitude, latitude = row[0], row[1]
        _engine_number(longitude)
        _engine_number(latitude)
        pairs.append((latitude, longitude))
    return pairs


def _stored_pair(position: object) -> tuple[object, object]:
    if type(position) is not list and type(position) is not tuple:
        raise TypeError(ROUTING_TILES_UNAVAILABLE)
    row = cast(list[object] | tuple[object, ...], position)
    if len(row) != 2:
        raise ValueError(ROUTING_TILES_UNAVAILABLE)
    latitude, longitude = row[0], row[1]
    _stored_number(latitude)
    _stored_number(longitude)
    return (latitude, longitude)


def _engine_number(value: object) -> None:
    if type(value) is bool or (type(value) is not int and type(value) is not float):
        raise TypeError(ROUTING_TILES_UNAVAILABLE)
    if type(value) is float and not math.isfinite(value):
        raise ValueError(ROUTING_TILES_UNAVAILABLE)


def _stored_number(value: object) -> None:
    if type(value) is bool:
        raise TypeError(ROUTING_TILES_UNAVAILABLE)
    if type(value) is int:
        return
    if type(value) is float:
        if not math.isfinite(value):
            raise ValueError(ROUTING_TILES_UNAVAILABLE)
        return
    if type(value) is Decimal:
        if not value.is_finite():
            raise ValueError(ROUTING_TILES_UNAVAILABLE)
        return
    if type(value) is Fraction:
        return
    raise TypeError(ROUTING_TILES_UNAVAILABLE)


def _as_list(value: object) -> list[object]:
    if type(value) is not list:
        raise TypeError(ROUTING_TILES_UNAVAILABLE)
    return cast(list[object], value)


def _as_dict(value: object) -> dict[str, object]:
    if type(value) is not dict:
        raise TypeError(ROUTING_TILES_UNAVAILABLE)
    return cast(dict[str, object], value)


def _ready(tile_folder: Path) -> bool:
    try:
        return tile_folder.is_dir() and (tile_folder / "config.json").is_file()
    except OSError:
        return False
