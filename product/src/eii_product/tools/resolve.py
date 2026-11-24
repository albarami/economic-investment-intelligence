"""Resolve places and activities. Six named queries, then matching in Python.

The index is loaded once for a store and kept on the context. Matching uses
``eii_core.text``. No score is computed. A company, owner or person is never
a candidate.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol, cast

from eii_core.shapes import (
    GEOMETRY_REFUSED,
    GeometryTextError,
    Polygon,
    decode_geometry,
    exact_point,
    point_in_land,
)
from eii_core.text import normalise
from eii_product.store.protocol import NormalValue, QueryResult
from eii_product.store.registry import Inventory

GAZETTEER_QUERY = "resolve_gazetteer"
DISTRICT_QUERY = "resolve_district"
ZONE_QUERY = "resolve_zone"
MUNICIPALITY_QUERY = "resolve_municipality"
GRAPH_NODE_QUERY = "resolve_graph_node"
GRAPH_EDGE_QUERY = "resolve_graph_edge"
QUERY_NAMES = (
    GAZETTEER_QUERY,
    DISTRICT_QUERY,
    ZONE_QUERY,
    MUNICIPALITY_QUERY,
    GRAPH_NODE_QUERY,
    GRAPH_EDGE_QUERY,
)
TOOL_KEY = "resolve"
INVALID_ARGUMENT = "INVALID_ARGUMENT"
UNMAPPABLE = "UNMAPPABLE"
_TEXT_LIMIT = 200
_CANDIDATE_CAP = 5
_REQUEST_KEYS = frozenset({"text", "lang", "kind"})
_LANGS = frozenset({"en", "ar"})
_KINDS = frozenset({"place", "activity", "both"})
_CANDIDATE_KINDS = frozenset({"place", "activity"})
_SOURCES = frozenset({"gazetteer", "activity_spine"})
_MATCHES = frozenset({"exact", "normalised"})
_PLACE_FIELDS = frozenset({"kind", "key", "label_en", "label_ar", "source", "match"})
_ACTIVITY_FIELDS = _PLACE_FIELDS | frozenset(
    {"commerce_code", "isic_class", "place_category", "not_mappable"}
)
_REGISTER_PREFIX = "register:"
_BARE_DIGITS = re.compile(r"[0-9]{8}\Z|[0-9]{11}\Z")
# Rule 23 and the identifier exception (lead ruling, S3-T03 box 3): a numeral
# may sit only inside an identifier string, that is a key, a register or
# classification code, or a place's proper name. No other returned value
# holds one; the resolver returns no fact.
_NUMERAL_CATEGORIES = frozenset({"Nd", "Nl", "No"})
_IDENTIFIER_FIELDS = {
    "place": frozenset({"key", "label_en", "label_ar"}),
    "activity": frozenset({"key", "commerce_code", "isic_class", "place_category"}),
}


class ArgumentError(ValueError):
    """The closed request was refused. The message is INVALID_ARGUMENT."""


class PayloadError(ValueError):
    """The payload is outside the closed model."""


class _Fetcher(Protocol):
    """The store method this tool calls."""

    release_id: str

    def fetch(self, query: object, params: Mapping[str, object]) -> QueryResult:
        """Run one inventory query."""


@dataclass(frozen=True)
class _Place:
    key: str
    name_en: str
    name_ar: str
    aliases: tuple[str, ...]
    longitude: Decimal | int | None
    latitude: Decimal | int | None
    cell: int | None


@dataclass(frozen=True)
class _Activity:
    key: str
    code: str
    label_en: str
    label_ar: str
    isic_class: str
    place_category: str
    not_mappable: bool


@dataclass(frozen=True)
class ResolveIndex:
    """Rows read once. Districts and zones are held because the contract reads them."""

    places: tuple[_Place, ...]
    activities: tuple[_Activity, ...]
    districts: tuple[tuple[str, str, str], ...]
    zones: tuple[tuple[str, str, str], ...]
    land: tuple[Polygon, ...]


@dataclass(frozen=True)
class _Parsed:
    text: str
    lang: str
    kind: str


@dataclass(frozen=True)
class ResolveResult:
    """The tool result. It follows the base's tool result and holds no fact."""

    tool: str
    status: str
    reason: str | None
    release_id: str
    payload: Mapping[str, object] | None


class ResolveContext:
    """The inventory, and one index per store object."""

    def __init__(self, inventory: Inventory) -> None:
        """Keep the inventory. Indexes are filled on the first read of a store."""
        self.inventory = inventory
        self._indexes: dict[int, ResolveIndex] = {}

    def index_for(self, store: object) -> ResolveIndex:
        """Return the index already read for this store, or read it once."""
        key = id(store)
        found = self._indexes.get(key)
        if found is None:
            found = load_index(store, self.inventory)
            self._indexes[key] = found
        return found


def load_index(store: object, inventory: Inventory) -> ResolveIndex:
    """Read the six tables through named queries. Matching does not read again."""
    places = _places(_fetch(store, inventory, GAZETTEER_QUERY))
    districts = _names(_fetch(store, inventory, DISTRICT_QUERY))
    zones = _names(_fetch(store, inventory, ZONE_QUERY))
    land = _land(_fetch(store, inventory, MUNICIPALITY_QUERY))
    nodes = _records(_fetch(store, inventory, GRAPH_NODE_QUERY))
    edges = _records(_fetch(store, inventory, GRAPH_EDGE_QUERY))
    return ResolveIndex(places, _activities(nodes, edges), districts, zones, land)


def resolve(
    store: object, request: Mapping[str, object], context: ResolveContext
) -> ResolveResult:
    """Match one closed request. A bad request reads nothing."""
    release_id = cast(_Fetcher, store).release_id
    try:
        parsed = parse_request(request)
    except ArgumentError:
        return _status(release_id, INVALID_ARGUMENT, None)
    index = context.index_for(store)
    try:
        return _matched(release_id, parsed, index)
    except PayloadError:
        return _status(release_id, INVALID_ARGUMENT, None)


def parse_request(request: Mapping[str, object]) -> _Parsed:
    """Accept exactly text, lang and kind. Nothing else is read."""
    if set(request) != _REQUEST_KEYS:
        raise ArgumentError(INVALID_ARGUMENT)
    text = request["text"]
    lang = request["lang"]
    kind = request["kind"]
    if type(text) is not str or not 1 <= len(text) <= _TEXT_LIMIT:
        raise ArgumentError(INVALID_ARGUMENT)
    if type(lang) is not str or lang not in _LANGS:
        raise ArgumentError(INVALID_ARGUMENT)
    if type(kind) is not str or kind not in _KINDS:
        raise ArgumentError(INVALID_ARGUMENT)
    return _Parsed(text, lang, kind)


def require_candidate(candidate: Mapping[str, object]) -> None:
    """Refuse a numeral outside an identifier, an unknown or non-string field,
    a foreign source or a register key."""
    kind = candidate.get("kind")
    if kind == "place":
        allowed = _PLACE_FIELDS
    elif kind == "activity":
        allowed = _ACTIVITY_FIELDS
    else:
        raise PayloadError(INVALID_ARGUMENT)
    if set(candidate) != allowed:
        raise PayloadError(INVALID_ARGUMENT)
    _string(candidate, "kind", _CANDIDATE_KINDS)
    _string(candidate, "source", _SOURCES)
    _string(candidate, "match", _MATCHES)
    key = _string(candidate, "key", None)
    if key.startswith(_REGISTER_PREFIX) or _BARE_DIGITS.fullmatch(key) is not None:
        raise PayloadError(INVALID_ARGUMENT)
    _string(candidate, "label_en", None)
    _string(candidate, "label_ar", None)
    if kind == "activity":
        _string(candidate, "commerce_code", None)
        _string(candidate, "isic_class", None)
        _string(candidate, "place_category", None)
        if type(candidate["not_mappable"]) is not bool:
            raise PayloadError(INVALID_ARGUMENT)
    identifiers = _IDENTIFIER_FIELDS[kind]
    for name, value in candidate.items():
        if name not in identifiers and type(value) is str and _has_numeral(value):
            raise PayloadError(INVALID_ARGUMENT)


def _has_numeral(value: str) -> bool:
    return any(unicodedata.category(char) in _NUMERAL_CATEGORIES for char in value)


def require_payload(payload: Mapping[str, object]) -> None:
    """The payload is candidates only. Facts are not a field of this result."""
    if set(payload) != {"candidates"}:
        raise PayloadError(INVALID_ARGUMENT)
    candidates = payload["candidates"]
    if type(candidates) is not list:
        raise PayloadError(INVALID_ARGUMENT)
    if len(candidates) > _CANDIDATE_CAP:
        raise PayloadError(INVALID_ARGUMENT)
    for candidate in candidates:
        if not isinstance(candidate, Mapping):
            raise PayloadError(INVALID_ARGUMENT)
        require_candidate(candidate)


def _matched(release_id: str, parsed: _Parsed, index: ResolveIndex) -> ResolveResult:
    found = _collect(parsed, index)
    if not found:
        return _status(release_id, "NO_DATA", None)
    inside: list[dict[str, object]] = []
    outside = False
    for candidate, located in found:
        if located is False:
            outside = True
            continue
        if located is None:
            continue
        inside.append(candidate)
    if not inside:
        status = "OUT_OF_SCOPE" if outside else "NO_DATA"
        return _status(release_id, status, None)
    ordered = sorted(inside, key=_rank)
    payload: dict[str, object] = {"candidates": ordered[:_CANDIDATE_CAP]}
    require_payload(payload)
    return _status(release_id, "OK", payload)


def _collect(
    parsed: _Parsed, index: ResolveIndex
) -> list[tuple[dict[str, object], bool | None]]:
    found: list[tuple[dict[str, object], bool | None]] = []
    if parsed.kind in {"place", "both"}:
        for place in index.places:
            match = _best(parsed.text, (place.name_en, place.name_ar, *place.aliases))
            if match is None:
                continue
            found.append((_place_candidate(place, match), _located(place, index.land)))
    if parsed.kind in {"activity", "both"}:
        for activity in index.activities:
            match = _best(parsed.text, (activity.label_en, activity.label_ar))
            if match is None:
                continue
            found.append((_activity_candidate(activity, match), True))
    return found


def _place_candidate(place: _Place, match: str) -> dict[str, object]:
    return {
        "kind": "place",
        "key": place.key,
        "label_en": place.name_en,
        "label_ar": place.name_ar,
        "source": "gazetteer",
        "match": match,
    }


def _activity_candidate(activity: _Activity, match: str) -> dict[str, object]:
    return {
        "kind": "activity",
        "key": activity.key,
        "label_en": activity.label_en,
        "label_ar": activity.label_ar,
        "source": "activity_spine",
        "match": match,
        "commerce_code": activity.code,
        "isic_class": activity.isic_class,
        "place_category": activity.place_category,
        "not_mappable": activity.not_mappable,
    }


def _best(text: str, labels: tuple[str, ...]) -> str | None:
    found: str | None = None
    exact = unicodedata.normalize("NFC", text)
    folded = normalise(text)
    for label in labels:
        if label == "":
            continue
        if unicodedata.normalize("NFC", label) == exact:
            return "exact"
        if found is None and normalise(label) == folded:
            found = "normalised"
    return found


def _rank(candidate: Mapping[str, object]) -> tuple[int, int, str]:
    match = 0 if candidate["match"] == "exact" else 1
    kind = 0 if candidate["kind"] == "place" else 1
    key = candidate["key"]
    if type(key) is not str:
        raise PayloadError(INVALID_ARGUMENT)
    return (match, kind, key)


def _located(place: _Place, land: tuple[Polygon, ...]) -> bool | None:
    if place.latitude is None or place.longitude is None:
        return None
    try:
        point = exact_point(place.latitude, place.longitude)
    except (TypeError, ValueError):
        return None
    return point_in_land(point, land)


def _places(result: QueryResult) -> tuple[_Place, ...]:
    rows: list[_Place] = []
    for record in _records(result):
        key = _cell_text(record.get("place_key"))
        if key is None:
            continue
        longitude = _coordinate(record.get("lon"))
        latitude = _coordinate(record.get("lat"))
        cell = record.get("cell")
        rows.append(
            _Place(
                key,
                _cell_text(record.get("name_en")) or "",
                _cell_text(record.get("name_ar")) or "",
                _aliases(record.get("aliases")),
                longitude,
                latitude,
                cell if type(cell) is int else None,
            )
        )
    return tuple(rows)


def _activities(
    nodes: tuple[dict[str, NormalValue], ...],
    edges: tuple[dict[str, NormalValue], ...],
) -> tuple[_Activity, ...]:
    by_id = {
        text: node
        for node in nodes
        if (text := _cell_text(node.get("node_id"))) is not None
    }
    classified: dict[str, str] = {}
    listed: dict[str, list[str]] = {}
    for edge in edges:
        edge_type = _cell_text(edge.get("edge_type"))
        origin = _cell_text(edge.get("from_node_id"))
        target = _cell_text(edge.get("to_node_id"))
        if origin is None or target is None or edge_type is None:
            continue
        if edge_type == "classified_as":
            classified[origin] = target
        elif edge_type == "listed_as":
            listed.setdefault(origin, []).append(target)
    found: list[_Activity] = []
    for node in nodes:
        if _cell_text(node.get("node_type")) != "activity":
            continue
        key = _cell_text(node.get("node_id"))
        code = _cell_text(node.get("code"))
        if key is None or code is None:
            continue
        class_node = by_id.get(classified.get(key, ""))
        class_code = (
            "" if class_node is None else (_cell_text(class_node.get("code")) or "")
        )
        not_mappable = class_code == UNMAPPABLE or class_node is None
        category = ""
        if not not_mappable:
            category = _category(listed.get(classified.get(key, ""), ()), by_id)
        found.append(
            _Activity(
                key,
                code,
                _cell_text(node.get("label_en")) or "",
                _cell_text(node.get("label_ar")) or "",
                "" if not_mappable else class_code,
                category,
                not_mappable,
            )
        )
    return tuple(found)


def _category(
    targets: tuple[str, ...] | list[str], by_id: Mapping[str, Mapping[str, NormalValue]]
) -> str:
    codes: list[str] = []
    for target in targets:
        node = by_id.get(target)
        if node is None or _cell_text(node.get("node_type")) != "place_category":
            continue
        code = _cell_text(node.get("code"))
        if code is not None:
            codes.append(code)
    if not codes:
        return ""
    return sorted(codes)[0]


def _land(result: QueryResult) -> tuple[Polygon, ...]:
    polygons: list[Polygon] = []
    for record in _records(result):
        text = record.get("geometry")
        if type(text) is not str:
            continue
        try:
            polygons.extend(decode_geometry(text))
        except GeometryTextError as error:
            if str(error) != GEOMETRY_REFUSED:
                raise
            continue
    return tuple(polygons)


def _names(result: QueryResult) -> tuple[tuple[str, str, str], ...]:
    rows: list[tuple[str, str, str]] = []
    for record in _records(result):
        values = tuple(record.values())
        if len(values) < 3:
            continue
        texts = tuple(_cell_text(value) or "" for value in values[:3])
        rows.append((texts[0], texts[1], texts[2]))
    return tuple(rows)


def _aliases(value: NormalValue) -> tuple[str, ...]:
    if type(value) is not str or value == "":
        return ()
    return tuple(part.strip() for part in value.split(";") if part.strip() != "")


def _coordinate(value: NormalValue) -> Decimal | int | None:
    if type(value) is int or type(value) is Decimal:
        return value
    return None


def _cell_text(value: object) -> str | None:
    if type(value) is str:
        return value
    return None


def _string(
    candidate: Mapping[str, object], name: str, allowed: frozenset[str] | None
) -> str:
    value = candidate[name]
    if type(value) is not str:
        raise PayloadError(INVALID_ARGUMENT)
    if allowed is not None and value not in allowed:
        raise PayloadError(INVALID_ARGUMENT)
    return value


def _records(result: QueryResult) -> tuple[dict[str, NormalValue], ...]:
    return tuple(dict(zip(result.columns, row, strict=True)) for row in result.rows)


def _fetch(store: object, inventory: Inventory, name: str) -> QueryResult:
    return cast(_Fetcher, store).fetch(inventory.lookup(name), {})


def _status(
    release_id: str, status: str, payload: Mapping[str, object] | None
) -> ResolveResult:
    return ResolveResult(TOOL_KEY, status, None, release_id, payload)
