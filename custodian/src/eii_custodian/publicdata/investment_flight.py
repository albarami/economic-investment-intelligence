"""Read the dashboard's framed push stream into project rows.

The page holds no table. Records sit in push scripts, then in text rows,
then in one JSON document. A byte is cut before it is decoded. Numbers keep
the digits the page wrote.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal

from eii_custodian.publicdata.investment_contracts import (
    CAPEX_LABEL_WORDS,
    CAPEX_PRECISION,
    CAPEX_SCALE,
    CAPEX_UNIT_USD,
    CAVEAT_KEY,
    CAVEAT_PHRASES,
    COLUMN_FROM_PAGE,
    FIELD_SPECS,
    FURTHER_FIELDS,
    PROVENANCE_PUBLIC,
    PUBLISHED_FIELDS,
    SHAPE_ID,
    STRING_EMPTY,
    STRING_NULL,
    STRING_TEXT,
    TOP_LEVEL_KEYS,
    DashboardShape,
    InvestmentFailure,
    SourceEnvelope,
    ValueKind,
    bare_digit_run,
    fail,
    parse_decimal,
    project_key,
)
from eii_custodian.publicdata.investment_crosswalk import mapped_columns

_SCRIPT = re.compile(r"<script\b[^>]*>(.*?)</script>", re.IGNORECASE | re.DOTALL)
_PAYLOAD_PREFIX = "self.__next_f.push("
_HEX = b"0123456789abcdef"
_INT = re.compile(r"^-?(?:0|[1-9][0-9]*)$")
_DAY = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
_WORD = {word: re.compile(r"\b" + word + r"\b") for word in CAPEX_LABEL_WORDS}
_CHUNK_KEY = b'"serializedDatasetChunks"'
_REF = re.compile(r"^\$[0-9a-f]*$")
_LAT_SCALE = 12
_LAT_PRECISION = 15


def read_dashboard(
    body: bytes, shape: DashboardShape, envelope: SourceEnvelope
) -> tuple[tuple[dict[str, object], ...], int] | InvestmentFailure:
    """Return project rows and the count of empty coordinates, or one failure."""
    if shape.shape_id != SHAPE_ID:
        return fail(envelope, "shape_mismatch", SHAPE_ID, shape.shape_id or "missing")
    if shape.country_iso3 or shape.municipality_code or shape.place_key:
        return fail(
            envelope, "name_derived_key", "source-issued identifier", "legacy map"
        )
    try:
        page = body.decode("utf-8")
    except UnicodeError:
        return fail(envelope, "unreadable", "utf-8", "not utf-8")
    phrases = _visible_phrases(page, envelope)
    if isinstance(phrases, InvestmentFailure):
        return phrases
    payload = _payload(page, envelope)
    if isinstance(payload, InvestmentFailure):
        return payload
    rows = _rows(payload, envelope)
    if isinstance(rows, InvestmentFailure):
        return rows
    found = _document(rows, envelope)
    if isinstance(found, InvestmentFailure):
        return found
    document, counts = found
    return _projects(document, counts, shape, envelope)


def _visible_phrases(page: str, envelope: SourceEnvelope) -> InvestmentFailure | None:
    visible = _SCRIPT.sub(" ", page)
    visible = re.sub(r"<[^>]+>", " ", visible)
    for _key, phrase in CAVEAT_PHRASES:
        if phrase not in visible:
            return fail(envelope, "missing_caveat", phrase, "absent")
    for word, pattern in _WORD.items():
        if pattern.search(visible) is None:
            return fail(envelope, "capex_label", word, "absent")
    return None


def _payload(page: str, envelope: SourceEnvelope) -> bytes | InvestmentFailure:
    """Join payload scripts. Any other script, bootstrap included, is ignored."""
    parts: list[str] = []
    for script in _SCRIPT.findall(page):
        body = script.strip()
        if not (body.startswith(_PAYLOAD_PREFIX) and body.endswith(")")):
            continue
        inner = body[len(_PAYLOAD_PREFIX) : -1]
        try:
            value, end = json.JSONDecoder().raw_decode(inner)
        except json.JSONDecodeError:
            return fail(envelope, "push_argument", "two-element array", "unreadable")
        if inner[end:].strip():
            return fail(envelope, "push_argument", "two-element array", "unreadable")
        if (
            not isinstance(value, list)
            or len(value) != 2
            or value[0] != 1
            or not isinstance(value[1], str)
        ):
            return fail(envelope, "push_argument", "two-element array", "refused")
        parts.append(value[1])
    if not parts:
        return fail(envelope, "no_push_payload", "push payload", "absent")
    # surrogateescape keeps a text row that splits a multibyte character.
    # A page that does not split one encodes as ordinary UTF-8.
    return "".join(parts).encode("utf-8", "surrogateescape")


def _rows(
    payload: bytes, envelope: SourceEnvelope
) -> list[tuple[str, str, bytes]] | InvestmentFailure:
    rows: list[tuple[str, str, bytes]] = []
    index = 0
    size = len(payload)
    while index < size:
        start = index
        while index < size and payload[index : index + 1] in _HEX:
            index += 1
        if index >= size or payload[index : index + 1] != b":":
            return fail(envelope, "row_framing", "id and colon", "absent")
        row_id = payload[start:index].decode("ascii")
        index += 1
        if index < size and payload[index : index + 1] == b"T":
            index += 1
            length_at = index
            while index < size and payload[index : index + 1] in _HEX:
                index += 1
            if (
                index >= size
                or payload[index : index + 1] != b","
                or length_at == index
            ):
                return fail(envelope, "row_framing", "id and colon", "absent")
            length = int(payload[length_at:index].decode("ascii"), 16)
            index += 1
            if index + length > size:
                return fail(envelope, "text_row_length", "bytes that remain", "longer")
            rows.append(("text", row_id, payload[index : index + length]))
            index += length
            continue
        end = payload.find(b"\n", index)
        if end < 0:
            rows.append(("other", row_id, payload[index:]))
            break
        rows.append(("other", row_id, payload[index:end]))
        index = end + 1
    return rows


def _document(
    rows: list[tuple[str, str, bytes]], envelope: SourceEnvelope
) -> tuple[dict[str, object], tuple[int, int]] | InvestmentFailure:
    texts = _text_rows(rows, envelope)
    if isinstance(texts, InvestmentFailure):
        return texts
    found = _chunk_objects(rows, envelope)
    if isinstance(found, InvestmentFailure):
        return found
    if len(found) != 1:
        observed = "none" if not found else str(len(found))
        return fail(envelope, "chunk_list", "one", observed)
    chunk = found[0]
    refs = chunk.get("serializedDatasetChunks")
    if not isinstance(refs, list) or not refs:
        return fail(envelope, "chunk_reference", "text row", "missing")
    pieces: list[bytes] = []
    for ref in refs:
        if not isinstance(ref, str) or _REF.fullmatch(ref) is None:
            observed = ref if isinstance(ref, str) else "not a reference"
            return fail(envelope, "chunk_reference", "text row", observed)
        row_id = ref[1:]
        if row_id not in texts:
            return fail(envelope, "chunk_reference", "text row", ref)
        pieces.append(texts[row_id])
    blob = b"".join(pieces)
    try:
        text = blob.decode("utf-8")
    except UnicodeError:
        return fail(envelope, "chunk_encoding", "utf-8", "not utf-8")
    try:
        document = json.loads(text, parse_int=_number, parse_float=_number)
    except json.JSONDecodeError:
        return fail(envelope, "chunk_json", "one json document", "refused")
    if not isinstance(document, dict):
        return fail(envelope, "chunk_json", "one json document", "not an object")
    counts = _metric_counts(chunk)
    if counts is None:
        return fail(envelope, "record_count", "record count", "not an integer")
    return document, counts


def _metric_counts(found: Mapping[str, object]) -> tuple[int, int] | None:
    """Read the two integer counts from diagnostics.metrics of the chunk object."""
    diagnostics = found.get("diagnostics")
    if not isinstance(diagnostics, dict):
        return None
    metrics = diagnostics.get("metrics")
    if not isinstance(metrics, dict):
        return None
    raw = _integer(metrics.get("rawRecordCount"))
    recorded = _integer(metrics.get("recordCount"))
    if raw is None or recorded is None:
        return None
    return raw, recorded


def _text_rows(
    rows: list[tuple[str, str, bytes]], envelope: SourceEnvelope
) -> dict[str, bytes] | InvestmentFailure:
    """Keep one body per text-row id. Another row may repeat an id or leave it empty."""
    texts: dict[str, bytes] = {}
    others: set[str] = set()
    for kind, row_id, body in rows:
        if kind == "text":
            if row_id in texts or row_id in others:
                return fail(
                    envelope, "row_framing", "unique text row", row_id or "empty"
                )
            texts[row_id] = body
            continue
        if row_id in texts:
            return fail(envelope, "row_framing", "unique text row", row_id or "empty")
        others.add(row_id)
    return texts


def _chunk_objects(
    rows: list[tuple[str, str, bytes]], envelope: SourceEnvelope
) -> list[dict[str, object]] | InvestmentFailure:
    """Collect every object that holds the chunk-list key, anywhere in the payload."""
    found: list[dict[str, object]] = []
    for kind, _row_id, body in rows:
        if kind != "other" or _CHUNK_KEY not in body:
            continue
        try:
            parsed = json.loads(
                body.decode("utf-8"), parse_int=_number, parse_float=_number
            )
        except (UnicodeError, json.JSONDecodeError):
            return fail(envelope, "chunk_list", "one", "unreadable")
        before = len(found)
        _collect_chunks(parsed, found)
        if len(found) == before:
            return fail(envelope, "chunk_list", "one", "unreadable")
    return found


def _collect_chunks(value: object, found: list[dict[str, object]]) -> None:
    if isinstance(value, dict):
        if "serializedDatasetChunks" in value:
            found.append(value)
        for item in value.values():
            _collect_chunks(item, found)
        return
    if isinstance(value, list):
        for item in value:
            _collect_chunks(item, found)


def _projects(
    document: Mapping[str, object],
    counts: tuple[int, int],
    shape: DashboardShape,
    envelope: SourceEnvelope,
) -> tuple[tuple[dict[str, object], ...], int] | InvestmentFailure:
    if set(document) != TOP_LEVEL_KEYS:
        return fail(
            envelope,
            "top_level_keys",
            "clientProjects,indexBaseMetrics,currencyText,latestDate",
            ",".join(sorted(str(key) for key in document)),
        )
    if document.get("currencyText") != "USD":
        observed = document.get("currencyText")
        shown = observed if isinstance(observed, str) else "refused"
        return fail(envelope, "currency_text", "USD", shown)
    projects = document.get("clientProjects")
    if not isinstance(projects, list) or any(
        not isinstance(item, dict) for item in projects
    ):
        return fail(envelope, "client_projects", "list of objects", "refused")
    raw, recorded = counts
    if raw != len(projects) or recorded != len(projects):
        observed = str(raw) if raw != len(projects) else str(recorded)
        return fail(envelope, "record_count", str(len(projects)), observed)
    built: list[dict[str, object]] = []
    seen: set[str] = set()
    empty_coordinates = 0
    for record in projects:
        row = _record(record, shape, envelope)
        if isinstance(row, InvestmentFailure):
            return row
        project, emptied = row
        key = str(project["project_key"])
        if key in seen:
            return fail(envelope, "duplicate_project", "unique published fields", key)
        seen.add(key)
        empty_coordinates += emptied
        built.append(project)
    if not built:
        return fail(envelope, "schema_missing", "project", "missing")
    return tuple(built), empty_coordinates


def _record(
    record: Mapping[str, object], shape: DashboardShape, envelope: SourceEnvelope
) -> tuple[dict[str, object], int] | InvestmentFailure:
    unknown = sorted(set(record) - set(PUBLISHED_FIELDS))
    if unknown:
        return fail(envelope, "unknown_field", "declared field", unknown[0])
    missing = sorted(set(PUBLISHED_FIELDS) - set(record))
    if missing:
        return fail(envelope, "missing_field", missing[0], "missing")
    loaded: dict[str, object] = {}
    tokens: dict[str, str] = {}
    for name in PUBLISHED_FIELDS:
        kind, strings = FIELD_SPECS[name]
        value = _load(name, record[name], kind, strings, envelope)
        if isinstance(value, InvestmentFailure):
            return value
        stored, token = value
        loaded[name] = stored
        tokens[name] = token
        if (
            kind is ValueKind.TEXT
            and isinstance(stored, str)
            and bare_digit_run(stored)
        ):
            return fail(envelope, "identifier_shape", "no bare digit run", name)
    dated = _announced(loaded, envelope)
    if isinstance(dated, InvestmentFailure):
        return dated
    money = _capex(loaded, envelope)
    if isinstance(money, InvestmentFailure):
        return money
    capex_value, capex_unit = money
    coordinates = _coordinates(loaded, envelope)
    if isinstance(coordinates, InvestmentFailure):
        return coordinates
    lat, lng, emptied = coordinates
    key = project_key(tokens)
    row: dict[str, object] = {
        "project_key": key,
        "caveat_keys": [CAVEAT_KEY],
        "provenance": PROVENANCE_PUBLIC,
        "join_key": "",
        "capex_value": capex_value,
        "capex_unit": capex_unit,
        "announced": dated,
        "lat": lat,
        "lng": lng,
    }
    for column, page_field in COLUMN_FROM_PAGE.items():
        if column in {"capex_value", "jobs", "announced"}:
            continue
        row[column] = loaded[page_field]
    row["jobs"] = loaded["jobs"]
    for name in FURTHER_FIELDS:
        if name in {"jobs", "lat", "lng"}:
            continue
        row[name] = loaded[name]
    mapped = mapped_columns(shape.crosswalk, loaded["project_id"], key, envelope)
    if isinstance(mapped, InvestmentFailure):
        return mapped
    row.update(mapped)
    if shape.column_from != COLUMN_FROM_PAGE:
        return fail(envelope, "confirmation_fields", "mapped fields", "incomplete")
    return row, emptied


def _load(
    name: str,
    value: object,
    kind: ValueKind,
    strings: frozenset[str],
    envelope: SourceEnvelope,
) -> tuple[object, str] | InvestmentFailure:
    token = _published_token(value)
    if kind is ValueKind.TAGS:
        if not isinstance(value, list) or any(
            not isinstance(item, str) for item in value
        ):
            return fail(envelope, "field_type", f"{name}:list of text", _seen(value))
        stored: object = (
            None
            if not value
            else json.dumps(value, separators=(",", ":"), ensure_ascii=True)
        )
        return stored, token
    if isinstance(value, str):
        if value == "" and STRING_EMPTY in strings:
            return None, token
        if value != "" and STRING_TEXT in strings:
            return value, token
        return fail(envelope, "field_type", f"{name}:{kind.value}", "string")
    if value is None:
        if STRING_NULL in strings:
            return None, token
        return fail(envelope, "field_type", f"{name}:{kind.value}", "null")
    if kind is ValueKind.TEXT:
        return fail(envelope, "field_type", f"{name}:{kind.value}", _seen(value))
    number = _number_token(value)
    if number is None:
        return fail(envelope, "field_type", f"{name}:{kind.value}", _seen(value))
    if kind is ValueKind.INTEGER:
        parsed = _integer(value)
        if parsed is None:
            return fail(envelope, "unrepresentable", "integer", "refused")
        return parsed, token
    if kind is ValueKind.DECIMAL_18_2:
        fitted = parse_decimal(
            number, precision=CAPEX_PRECISION, scale=CAPEX_SCALE, signed=True
        )
    else:
        fitted = parse_decimal(
            number, precision=_LAT_PRECISION, scale=_LAT_SCALE, signed=True
        )
    if fitted is None:
        return fail(envelope, "unrepresentable", kind.value, "refused")
    return fitted, token


def _announced(
    loaded: Mapping[str, object], envelope: SourceEnvelope
) -> str | InvestmentFailure | None:
    date = loaded["project_date"]
    year = loaded["project_year"]
    month = loaded["project_month"]
    if date is None:
        if year is not None or month is not None:
            return fail(envelope, "announced", "empty year and month", "dated parts")
        return None
    if not isinstance(date, str) or _DAY.fullmatch(date) is None:
        return fail(envelope, "announced", "calendar date", "refused")
    try:
        parsed = datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        return fail(envelope, "announced", "calendar date", "refused")
    if year != parsed.year or month != parsed.month - 1:
        return fail(envelope, "announced", "year and zero-based month", "mismatch")
    return date


def _capex(
    loaded: Mapping[str, object], envelope: SourceEnvelope
) -> tuple[str | None, str | None] | InvestmentFailure:
    currency = loaded["capex_currency"]
    value = loaded["capex"]
    if not isinstance(value, str):
        return fail(envelope, "unrepresentable", "decimal(18,2)", "refused")
    if currency is None:
        if Decimal(value) != 0:
            return fail(
                envelope, "capex_currency", "USD or empty with zero", "empty currency"
            )
        return None, None
    if currency != "USD":
        seen = currency if isinstance(currency, str) else "refused"
        return fail(envelope, "capex_currency", "USD", seen)
    return value, CAPEX_UNIT_USD


def _coordinates(
    loaded: Mapping[str, object], envelope: SourceEnvelope
) -> tuple[str | None, str | None, int] | InvestmentFailure:
    lat = loaded["lat"]
    lng = loaded["lng"]
    if not isinstance(lat, str) or not isinstance(lng, str):
        return fail(envelope, "unrepresentable", "decimal(15,12)", "refused")
    lat_zero = Decimal(lat) == 0
    lng_zero = Decimal(lng) == 0
    if lat_zero and lng_zero:
        return None, None, 1
    if lat_zero or lng_zero:
        return fail(envelope, "coordinate", "both empty or neither", "one zero")
    if Decimal(lat) < Decimal("-90") or Decimal(lat) > Decimal("90"):
        return fail(envelope, "coordinate", "latitude -90 to 90", "outside")
    if Decimal(lng) < Decimal("-180") or Decimal(lng) > Decimal("180"):
        return fail(envelope, "coordinate", "longitude -180 to 180", "outside")
    return lat, lng, 0


def _number(text: str) -> tuple[str, str]:
    return ("n", text)


def _number_token(value: object) -> str | None:
    if (
        isinstance(value, tuple)
        and len(value) == 2
        and value[0] == "n"
        and isinstance(value[1], str)
    ):
        return value[1]
    return None


def _integer(value: object) -> int | None:
    token = _number_token(value)
    if token is None or _INT.fullmatch(token) is None:
        return None
    return int(token)


def _published_token(value: object) -> str:
    number = _number_token(value)
    if number is not None:
        return number
    if value is None:
        return "null"
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=True)
    if isinstance(value, list):
        return "[" + ",".join(_published_token(item) for item in value) + "]"
    if isinstance(value, bool):
        return "true" if value else "false"
    return "null"


def _seen(value: object) -> str:
    if isinstance(value, str):
        return "string"
    if value is None:
        return "null"
    if isinstance(value, list):
        return "list"
    if isinstance(value, dict):
        return "object"
    if _number_token(value) is not None:
        return "number"
    return "other"
