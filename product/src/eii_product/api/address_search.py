"""Application-owned offline structured address lookup; no transport or writer.

The keyed provider's existing BE-136 route is separate. This national-centre
reader accepts exactly the published zone, street and building strings.
"""

from __future__ import annotations

import json
import logging
import re
import time
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Literal, Protocol

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from eii_product.imagery_provider.address import MAX_LOCATIONS, AddressHit
from eii_product.store.structured_address_sql import _EMBEDDED, _POSTGRES
from eii_product.store.structured_address_sql import INDEX_DDL as INDEX_DDL

_NUMBER = re.compile(r"[0-9]{1,7}")
_HASH = re.compile(r"[a-f0-9]{64}")
METHOD = "structured-address-v1"
SOURCE_URL = (
    "https://services.gisqatar.org.qa/server/rest/services/Vector/QARS/MapServer"
)


class AddressRefusal(ValueError):
    """Fixed reason; never echo a typed address or a result."""


@dataclass(frozen=True)
class AddressQuery:
    zone: str
    street: str
    building: str

    def __post_init__(self) -> None:
        for value in (self.zone, self.street, self.building):
            if not isinstance(value, str) or _NUMBER.fullmatch(value) is None:
                raise AddressRefusal("field_value_refused")

    @classmethod
    def parse(cls, body: object) -> AddressQuery:
        if not isinstance(body, dict):
            raise AddressRefusal("fields_refused")
        if "text" in body:
            raise AddressRefusal("free_text_refused")
        if set(body) != {"zone", "street", "building"}:
            raise AddressRefusal("fields_refused")
        return cls(body["zone"], body["street"], body["building"])


@dataclass(frozen=True)
class AddressRow:
    feature_key: str
    zone_number: str
    street_number: str
    building_number: str
    building_subtype: str | None
    lon: Decimal
    lat: Decimal
    source_id: str
    source_sha256: str
    retrieved_on: str
    licence_basis: str
    decision_record: str
    publisher: str
    terms_words: str
    source_url: str = SOURCE_URL
    licence_id: str = ""
    terms_read_on: str = "pending"

    def __post_init__(self) -> None:
        AddressQuery(self.zone_number, self.street_number, self.building_number)
        try:
            date.fromisoformat(self.retrieved_on)
            if self.terms_read_on != "pending":
                date.fromisoformat(self.terms_read_on)
        except (ValueError, TypeError):
            raise AddressRefusal("release_lineage_refused") from None
        if self.source_url != SOURCE_URL:
            raise AddressRefusal("release_lineage_refused")
        if (
            self.building_subtype is not None
            and _NUMBER.fullmatch(self.building_subtype) is None
        ):
            raise AddressRefusal("release_row_refused")
        if (
            not self.feature_key.startswith("fea-")
            or self.source_id != "gis_address"
            or _HASH.fullmatch(self.source_sha256) is None
            or self.licence_basis != "owner_decision"
            or self.decision_record != "0026"
            or not self.publisher
            or not self.terms_words
        ):
            raise AddressRefusal("release_lineage_refused")
        if (
            not isinstance(self.lon, Decimal)
            or not isinstance(self.lat, Decimal)
            or not self.lon.is_finite()
            or not self.lat.is_finite()
            or not -180 <= self.lon <= 180
            or not -90 <= self.lat <= 90
        ):
            raise AddressRefusal("release_point_refused")


@dataclass(frozen=True)
class AddressResult:
    status: Literal["found", "ambiguous", "not-found", "missing-source"]
    candidates: tuple[AddressRow, ...] = ()
    truncated: bool = False
    method_version: str = METHOD
    release_table: str = "pub_address_point"


class Search(Protocol):
    def search(self, query: AddressQuery) -> AddressResult: ...


def _result(rows: Sequence[AddressRow]) -> AddressResult:
    ordered = sorted(rows, key=lambda row: row.feature_key)
    if len({row.feature_key for row in ordered}) != len(ordered):
        raise AddressRefusal("duplicate_feature_key")
    status: Literal["found", "ambiguous", "not-found"] = (
        "not-found" if not ordered else "found" if len(ordered) == 1 else "ambiguous"
    )
    return AddressResult(status, tuple(ordered[:5]), len(ordered) > 5)


class AddressIndex:
    """Index only released Public rows; queries/results are never retained."""

    def __init__(self, rows: Sequence[AddressRow] | None) -> None:
        self.missing = rows is None
        groups: dict[tuple[str, str, str], list[AddressRow]] = {}
        seen: set[str] = set()
        for row in rows or ():
            if row.feature_key in seen:
                raise AddressRefusal("duplicate_feature_key")
            seen.add(row.feature_key)
            groups.setdefault(
                (row.zone_number, row.street_number, row.building_number), []
            ).append(row)
        self._rows = {
            key: tuple(sorted(group, key=lambda row: row.feature_key))
            for key, group in groups.items()
        }

    def search(self, query: AddressQuery) -> AddressResult:
        if self.missing:
            return AddressResult("missing-source")
        return _result(self._rows.get((query.zone, query.street, query.building), ()))


def prepare_read(engine: str, query: AddressQuery) -> tuple[str, tuple[str, str, str]]:
    if engine not in {"postgres", "embedded"}:
        raise AddressRefusal("engine_refused")
    return (_POSTGRES if engine == "postgres" else _EMBEDDED), (
        query.zone,
        query.street,
        query.building,
    )


class Reader(Protocol):
    def __call__(
        self, sql: str, values: tuple[str, str, str]
    ) -> Sequence[Sequence[object]]: ...


@dataclass(frozen=True)
class StoredAddressSearch:
    """Same fixed bounded read in both stores, with selected release lineage."""

    engine: str
    read: Reader
    lineage: Mapping[str, str] | None

    def search(self, query: AddressQuery) -> AddressResult:
        if self.lineage is None:
            return AddressResult("missing-source")
        sql, bound = prepare_read(self.engine, query)
        values = self.read(sql, bound)
        if len(values) > 6:
            raise AddressRefusal("store_bound_refused")
        rows = []
        expected = {
            "source_id",
            "source_sha256",
            "retrieved_on",
            "licence_basis",
            "decision_record",
            "publisher",
            "terms_words",
        }
        if set(self.lineage) != expected:
            raise AddressRefusal("release_lineage_refused")
        for value in values:
            if (
                len(value) != 7
                or any(not isinstance(v, str) for v in value[:4])
                or (value[4] is not None and not isinstance(value[4], str))
            ):
                raise AddressRefusal("release_row_refused")
            # Closed positional conversion; no source attributes outside the release schema.
            row = AddressRow(
                str(value[0]),
                str(value[1]),
                str(value[2]),
                str(value[3]),
                str(value[4]) if value[4] is not None else None,
                Decimal(str(value[5])),
                Decimal(str(value[6])),
                **self.lineage,
            )
            if (row.zone_number, row.street_number, row.building_number) != bound:
                raise AddressRefusal("store_result_refused")
            rows.append(row)
        return _result(rows)


def address_router(search: Search) -> APIRouter:
    router = APIRouter()

    @router.post("/api/address-search/structured")
    def structured(body: dict[str, object]) -> dict[str, object]:
        try:
            result = search.search(AddressQuery.parse(body))
        except AddressRefusal as error:
            raise HTTPException(status_code=422, detail=str(error)) from None
        return asdict(result)

    return router


LOGGER = logging.getLogger("eii.address_search")
_TEXT_LIMIT = 200
_LANGS = frozenset({"en", "ar"})
_LOG_FIELDS = (
    "answer_id",
    "duration_ms",
    "engine",
    "error_code",
    "error_id",
    "event",
    "level",
    "release_id",
    "seat_key",
    "status",
    "tool",
    "ts",
)
Transport = Callable[[str, str, str], tuple[AddressHit, ...]]
Opener = Callable[..., object]
TransportFactory = Callable[[Opener], Transport]


def offline_unset() -> bool:
    """The presenter's offline control is unset until a reader is injected."""
    return False


def build_router(
    key_reader: Callable[[], str | None],
    offline_reader: Callable[[], bool],
    transport_factory: TransportFactory,
    opener: Opener,
) -> APIRouter:
    """Routes for the address search. Nothing is stored."""
    router = APIRouter()

    @router.post("/api/address-search")
    async def address_search(request: Request) -> JSONResponse:
        started = time.monotonic()
        parsed = _parse_body(await request.body())
        if parsed is None:
            return _invalid(started)
        text, lang = parsed
        key = key_reader()
        offline = offline_reader()
        if type(key) is not str or key == "" or offline is not False:
            return _not_found(started)
        transport = transport_factory(opener)
        try:
            hits = transport(text, lang, key)
        except Exception:
            return _not_found(started)
        kept = hits[:MAX_LOCATIONS]
        if not kept:
            return _not_found(started)
        return _ok(started, kept)

    return router


def _parse_body(raw: bytes) -> tuple[str, str] | None:
    try:
        body = json.loads(raw)
    except ValueError:
        return None
    if type(body) is not dict or set(body) != {"text", "lang"}:
        return None
    text = body["text"]
    lang = body["lang"]
    if type(text) is not str or not 1 <= len(text) <= _TEXT_LIMIT:
        return None
    if type(lang) is not str or lang not in _LANGS:
        return None
    return text, lang


def _invalid(started: float) -> JSONResponse:
    error_id = _log("INVALID_ARGUMENT", "INVALID_ARGUMENT", started)
    return JSONResponse(
        status_code=422,
        content=_error("INVALID_ARGUMENT", "invalid_argument", error_id),
    )


def _not_found(started: float) -> JSONResponse:
    error_id = _log("NOT_FOUND", "NOT_FOUND", started)
    return JSONResponse(
        status_code=404,
        content=_error("NOT_FOUND", "address_search_not_found", error_id),
    )


def _ok(started: float, hits: tuple[AddressHit, ...]) -> JSONResponse:
    _log("OK", None, started)
    results = [
        {
            "label": hit.label,
            "point": {"longitude": hit.longitude, "latitude": hit.latitude},
        }
        for hit in hits
    ]
    return JSONResponse(status_code=200, content={"results": results})


def _error(code: str, message_key: str, error_id: str) -> dict[str, dict[str, str]]:
    return {"error": {"code": code, "message_key": message_key, "error_id": error_id}}


def _log(status: str, error_code: str | None, started: float) -> str:
    error_id = uuid.uuid4().hex
    duration_ms = int((time.monotonic() - started) * 1000)
    record = {
        "ts": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "level": "info",
        "event": "address_search",
        "answer_id": None,
        "seat_key": None,
        "tool": None,
        "engine": None,
        "release_id": None,
        "status": status,
        "duration_ms": duration_ms,
        "error_code": error_code,
        "error_id": error_id,
    }
    if tuple(sorted(record)) != _LOG_FIELDS:
        raise RuntimeError("log fields drifted")
    LOGGER.info("%s", json.dumps(record, sort_keys=True))
    return error_id
