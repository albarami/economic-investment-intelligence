"""Area identifiers and the canonical area record.

Grammar, fixed here because section 11.1 of document 08 names the parts and not
the separators. Fields are separated by ``/``:

``ma1/<prefix>/<mode>/<cutoff>/<cell>/<lat>/<lon>``

``ma1/<prefix>/polygon/<shape_id>``

``prefix`` is the first 16 hexadecimal characters of the release id (BE-33,
"release prefix"). ``mode`` is ``distance``, ``walk`` or ``drive``. ``cutoff``
is the closed integer. ``cell`` is the decimal identifier of the base cell, or
the literal ``none`` when the pin has no base cell (decision 0030 item 10).
``lat`` and ``lon`` are the point reduced to six decimal places, a leading minus
when negative, and exactly six digits after the point. ``shape_id`` is 64
lowercase hexadecimal characters, the identifier of the registered polygon.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from decimal import Decimal

INVALID_ARGUMENT = "INVALID_ARGUMENT"
_PREFIX = 16
_MODES = frozenset({"distance", "walk", "drive"})
_HEX = re.compile(r"[0-9a-f]{16}\Z")
_SHAPE = re.compile(r"[0-9a-f]{64}\Z")
_INTEGER = re.compile(r"0|[1-9][0-9]*\Z")
_SIX = re.compile(r"-?(?:0|[1-9][0-9]*)[.][0-9]{6}\Z")


class AreaIdError(ValueError):
    """The identifier is refused. The message is INVALID_ARGUMENT."""


def build_area_id(
    *,
    release_id: str,
    mode: str | None = None,
    cutoff: int | None = None,
    cell: int | None = None,
    latitude: Decimal | None = None,
    longitude: Decimal | None = None,
    shape_id: str | None = None,
) -> str:
    """Build the identifier described in the module note."""
    prefix = release_id[:_PREFIX]
    if shape_id is not None:
        return f"ma1/{prefix}/polygon/{shape_id}"
    if mode is None or cutoff is None or latitude is None or longitude is None:
        raise AreaIdError(INVALID_ARGUMENT)
    cell_token = "none" if cell is None else str(cell)
    return (
        f"ma1/{prefix}/{mode}/{cutoff}/{cell_token}/"
        f"{format_six(latitude)}/{format_six(longitude)}"
    )


def parse_area_id(area_id: str, release_id: str) -> dict[str, object]:
    """Return a request dict. Another release and a malformed id are refused."""
    pieces = area_id.split("/")
    if len(pieces) < 3 or pieces[0] != "ma1":
        raise AreaIdError(INVALID_ARGUMENT)
    prefix = pieces[1]
    if _HEX.fullmatch(prefix) is None or prefix != release_id[:_PREFIX]:
        raise AreaIdError(INVALID_ARGUMENT)
    if pieces[2] == "polygon":
        if len(pieces) != 4 or _SHAPE.fullmatch(pieces[3]) is None:
            raise AreaIdError(INVALID_ARGUMENT)
        return {"shape_id": pieces[3]}
    if len(pieces) != 7 or pieces[2] not in _MODES:
        raise AreaIdError(INVALID_ARGUMENT)
    if _INTEGER.fullmatch(pieces[3]) is None:
        raise AreaIdError(INVALID_ARGUMENT)
    cell_text = pieces[4]
    if cell_text != "none" and _INTEGER.fullmatch(cell_text) is None:
        raise AreaIdError(INVALID_ARGUMENT)
    if _SIX.fullmatch(pieces[5]) is None or _SIX.fullmatch(pieces[6]) is None:
        raise AreaIdError(INVALID_ARGUMENT)
    return {
        "mode": pieces[2],
        "cutoff": int(pieces[3]),
        "cell": None if cell_text == "none" else int(cell_text),
        "latitude": Decimal(pieces[5]),
        "longitude": Decimal(pieces[6]),
    }


def valid_area_id(value: str) -> bool:
    """Check grammar without a release lookup; store tools bind the release."""
    pieces = value.split("/")
    if len(pieces) < 2:
        return False
    try:
        parse_area_id(value, pieces[1])
    except AreaIdError:
        return False
    return True


def format_six(value: Decimal) -> str:
    """Render a six-place decimal with a sign only when negative."""
    text = format(value.copy_abs(), "f")
    whole, _, fraction = text.partition(".")
    fraction = (fraction + "000000")[:6]
    sign = "-" if value < 0 else ""
    return f"{sign}{whole}.{fraction}"


def canonical_json(value: object) -> bytes:
    """Sorted keys, fixed separators, UTF-8. Decimals are written as numbers."""
    return _dump(value).encode("utf-8")


def _dump(value: object) -> str:
    if type(value) is Decimal:
        return format(value, "f")
    if type(value) is str:
        return json.dumps(value, ensure_ascii=False)
    if type(value) is int and not isinstance(value, bool):
        return str(value)
    if value is None:
        return "null"
    if type(value) is bool:
        return "true" if value else "false"
    if type(value) is list or type(value) is tuple:
        return "[" + ",".join(_dump(item) for item in value) + "]"
    if isinstance(value, Mapping):
        parts = [
            json.dumps(str(key), ensure_ascii=False) + ":" + _dump(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        ]
        return "{" + ",".join(parts) + "}"
    raise TypeError(INVALID_ARGUMENT)
