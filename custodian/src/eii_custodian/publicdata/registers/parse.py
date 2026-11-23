"""Closed CSV projection; no repairs, network, ambient settings or inferred facts."""

from __future__ import annotations

import csv
import io
import math
import re
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date

from eii_custodian.publicdata.frame.checks import FrameError
from eii_custodian.publicdata.frame.grid import point_cell

from .contracts import (
    CARD_COLUMNS,
    HEADER_ONLY,
    NUMERIC_COLUMNS,
    REGISTRATION,
    ROLES,
    SCHEMAS,
    SOURCE_ROW_KEY,
    company_key_ok,
    refuse,
    row_identity,
)
from .provenance import Frame


@dataclass(repr=False)
class InputAudit:
    """Ephemeral identifiers never leave intake; only closed absence counts do."""

    licences: set[str] = field(default_factory=set)
    notice_absences: int = 0  # {events}; never a date estimate
    non_registration_absences: int = 0  # {rows}; never a repaired number
    duplicate_absences: int = 0  # {rows}, not distinct numbers
    duplicate_registrations: set[str] = field(default_factory=set)


def parse_value(value: str, declaration: str) -> str | None:
    optional = declaration.endswith("?")
    kind = declaration.removesuffix("?")
    if value == "" and optional:
        return None
    if kind == "empty":
        if value:
            refuse("unconfirmed_branch_structure")
        return None
    if kind == "registration":
        if REGISTRATION.fullmatch(value) is None:
            refuse("registration_format")
    elif kind == "fc_number":
        if re.fullmatch(r"[0-9]{5}", value) is None:
            refuse("registration_format")
    elif kind == "row_key":
        if SOURCE_ROW_KEY.fullmatch(value) is None:
            refuse("row_key_format")
    elif kind == "date":
        if re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value) is None:
            refuse("malformed_date")
        try:
            date.fromisoformat(value)
        except ValueError:
            refuse("malformed_date")
    elif kind in {"integer", "year"}:
        if re.fullmatch(r"[0-9]{4}" if kind == "year" else r"[0-9]+", value) is None:
            refuse("integer_format")
    elif kind in {"longitude", "latitude"}:
        if re.fullmatch(r"-?[0-9]+(?:\.[0-9]+)?", value) is None:
            refuse("coordinate_format")
        number = float(value)
        bound = 180 if kind == "longitude" else 90
        if not math.isfinite(number) or not -bound <= number <= bound:
            refuse("coordinate_format")
    elif kind == "yes_no":
        if value not in {"yes", "no"}:
            refuse("tax_registered_format")
    elif kind == "text":
        if not value.strip():
            refuse("required_text")
    else:
        refuse("input_declaration")
    return value


def _numeric_value(name: str, value: object, declaration: str) -> None:
    """Validate a persisted numeric column without treating it as identifier text."""
    if value is None:
        parse_value("", declaration)
    elif name == "capital_qar":
        if type(value) is not int:
            refuse("release_type")
        if not 0 <= value <= 2**63 - 1:
            refuse("integer_format")
    else:
        if type(value) is not float:
            refuse("release_type")
        bound = 180 if name == "lon" else 90
        if not math.isfinite(value) or not -bound <= value <= bound:
            refuse("coordinate_format")


def _project_numbers(row: dict[str, object]) -> None:
    for name in NUMERIC_COLUMNS:
        value = row[name]
        if value is not None:
            # The CSV lexeme has already passed its numeric declaration.
            if not isinstance(value, str):
                refuse("release_type")
            try:
                row[name] = int(value) if name == "capital_qar" else float(value)
            except ValueError:
                refuse("integer_format")
            if name == "capital_qar":
                _numeric_value(name, row[name], "integer?")


def _rows(body: bytes, role: str, audit: InputAudit) -> list[dict[str, str | None]]:
    try:
        reader = csv.reader(io.StringIO(body.decode("utf-8"), newline=""), strict=True)
        header = next(reader, [])
        schema = SCHEMAS[role]
        expected = set(schema) | (
            set(HEADER_ONLY) if role == "establishments" else set()
        )
        if len(header) != len(expected) or set(header) != expected:
            refuse("input_schema")
        rows = []
        for record in reader:
            if len(record) != len(header):
                refuse("input_schema")
            row: dict[str, str | None] = {}
            for name, value in zip(header, record, strict=True):
                if name not in schema:
                    continue
                if (
                    role == "establishments"
                    and name == "registration_number"
                    and re.fullmatch(r"[A-Za-z]{1,10}", value)
                ):
                    audit.non_registration_absences += 1
                    row[name] = None
                elif (
                    role == "events"
                    and name == "notice_expiration_date"
                    and re.fullmatch(r"[0-9]{2}-[A-Z][a-z]{2}-[0-9]{3}", value)
                ):
                    audit.notice_absences += 1
                    row[name] = None
                else:
                    row[name] = parse_value(value, schema[name])
            if role == "establishments":
                licence = row["licence_number"]
                assert isinstance(licence, str)  # required integer declaration
                audit.licences.add(licence)
            rows.append(row)
        return rows
    except (UnicodeError, csv.Error, TypeError, AttributeError):
        refuse("input_csv")


def _withhold_duplicate_registrations(
    rows: list[dict[str, str | None]], audit: InputAudit
) -> None:
    """Preserve every establishment; withhold all occurrences of shared numbers."""
    counts = Counter(row["registration_number"] for row in rows)
    duplicates = {
        number for number, count in counts.items() if number is not None and count > 1
    }
    audit.duplicate_registrations.update(duplicates)
    for row in rows:
        if row["registration_number"] in duplicates:
            row["registration_number"] = None
            audit.duplicate_absences += 1


def _keyed(
    rows: list[dict[str, str | None]], key: str
) -> dict[str, dict[str, str | None]]:
    found: dict[str, dict[str, str | None]] = {}
    row_keys: set[str | None] = set()
    for row in rows:
        value = row[key]
        if value is None and key == "registration_number":
            value = row_identity(str(row["row_key"]))
        if value is None:
            refuse("missing_registration_key")
        if value in found:
            refuse("duplicate_registration_key")
        if "row_key" in row:
            if row["row_key"] in row_keys:
                refuse("duplicate_row_key")
            row_keys.add(row["row_key"])
        found[value] = row
    return found


def _cell(row: Mapping[str, str | None], frame: Frame) -> int | None:
    lon, lat = row["lon"], row["lat"]
    if (lon is None) != (lat is None):
        refuse("coordinate_pair")
    if lon is None or lat is None:
        return None
    try:
        return point_cell(float(lon), float(lat), frame.cells)
    except (FrameError, ValueError, OverflowError):
        refuse("frame_location")


def parse(
    source_id: str,
    files: Mapping[str, bytes],
    frame: Frame,
    *,
    audit: InputAudit | None = None,
) -> list[dict[str, object]]:
    if source_id not in ROLES or set(files) != ROLES[source_id]:
        refuse("input_schema")
    audit = InputAudit() if audit is None else audit
    parsed = {role: _rows(body, role, audit) for role, body in files.items()}
    if source_id == "biz_register":
        _withhold_duplicate_registrations(parsed["establishments"], audit)
        companies = _keyed(parsed["establishments"], "registration_number")
        result = []
        for key, source in sorted(companies.items()):
            row: dict[str, object] = {name: source.get(name) for name in CARD_COLUMNS}
            row.update(
                registration_number=key,
                source_id=source_id,
                registered_cell=_cell(source, frame),
            )
            _project_numbers(row)
            result.append(row)
        return result
    companies = _keyed(parsed["companies"], "qfc_number")
    geocodes = _keyed(parsed["geocoded"], "qfc_number")
    events = _keyed(parsed["events"], "qfc_number")
    if companies.keys() != geocodes.keys() or not events.keys() <= companies.keys():
        refuse("companion_keys")
    result = []
    for key, source in sorted(companies.items()):
        geocode = geocodes[key]
        if source["row_key"] != geocode["row_key"]:
            refuse("companion_row_key")
        row = dict.fromkeys(CARD_COLUMNS)
        row.update(
            {name: value for name, value in source.items() if name in CARD_COLUMNS}
        )
        row.update(
            {
                name: value
                for name, value in events.get(key, {}).items()
                if name in CARD_COLUMNS
            }
        )
        row.update(
            registration_number=key,
            source_id=source_id,
            registered_cell=_cell(geocode, frame),
            lon=geocode["lon"],
            lat=geocode["lat"],
        )
        _project_numbers(row)
        result.append(row)
    return result


def validate_card(row: Mapping[str, object], frame: Frame) -> None:
    """Revalidate persisted values and recompute location at the loader seam."""
    source = row["source_id"]
    role = "establishments" if source == "biz_register" else "companies"
    allowed = set(SCHEMAS[role]) | {
        "registered_cell",
        "source_id",
        "registration_number",
    }
    if source == "fc_register":
        allowed |= {"event", "notice_expiration_date", "lon", "lat"}
    if any(value is not None for name, value in row.items() if name not in allowed):
        refuse("release_source_field")
    for name, declaration in SCHEMAS[role].items():
        if name not in CARD_COLUMNS:
            continue
        value = row[name]
        if name == "registration_number":
            if not company_key_ok(value):
                refuse("registration_format")
            continue
        if name in NUMERIC_COLUMNS:
            _numeric_value(name, value, declaration)
            continue
        if value is not None and not isinstance(value, str):
            refuse("release_type")
        parse_value("" if value is None else value, declaration)
    if source == "fc_register":
        key = row["registration_number"]
        if not isinstance(key, str):
            refuse("release_type")
        parse_value(key, "fc_number")
        for name, declaration in (
            ("event", "text?"),
            ("notice_expiration_date", "date?"),
            ("lon", "longitude?"),
            ("lat", "latitude?"),
        ):
            value = row[name]
            if name in NUMERIC_COLUMNS:
                _numeric_value(name, value, declaration)
                continue
            if value is not None and not isinstance(value, str):
                refuse("release_type")
            parse_value("" if value is None else value, declaration)
    coordinates = {
        name: str(row[name]) if row[name] is not None else None
        for name in ("lon", "lat")
    }
    if row["registered_cell"] != _cell(coordinates, frame):
        refuse("release_cell_mismatch")
