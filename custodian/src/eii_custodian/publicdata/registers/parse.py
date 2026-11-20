"""Closed CSV projection; no repairs, network, ambient settings or inferred facts."""

from __future__ import annotations

import csv
import io
import math
import re
from collections.abc import Mapping
from datetime import date

from eii_custodian.publicdata.frame.checks import FrameError
from eii_custodian.publicdata.frame.grid import point_cell

from .contracts import CARD_COLUMNS, REGISTRATION, ROLES, SCHEMAS, refuse
from .provenance import Frame


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
        if REGISTRATION.fullmatch(value) is None or len(value) > 10:
            refuse("registration_format")
    elif kind == "fc_number":
        if re.fullmatch(r"[0-9]{5}", value) is None:
            refuse("registration_format")
    elif kind == "row_key":
        if re.fullmatch(r"[a-f0-9]{20}", value) is None:
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
        if value not in {"Yes", "No"}:
            refuse("tax_registered_format")
    elif kind == "text":
        if not value.strip():
            refuse("required_text")
    else:
        refuse("input_declaration")
    return value


def _rows(body: bytes, role: str) -> list[dict[str, str | None]]:
    try:
        reader = csv.reader(io.StringIO(body.decode("utf-8"), newline=""), strict=True)
        header = next(reader, [])
        schema = SCHEMAS[role]
        if len(header) != len(schema) or set(header) != set(schema):
            refuse("input_schema")
        rows = []
        for record in reader:
            if len(record) != len(header):
                refuse("input_schema")
            rows.append(
                {
                    name: parse_value(value, schema[name])
                    for name, value in zip(header, record, strict=True)
                }
            )
        return rows
    except (UnicodeError, csv.Error, TypeError, AttributeError):
        refuse("input_csv")


def _keyed(
    rows: list[dict[str, str | None]], key: str
) -> dict[str, dict[str, str | None]]:
    found: dict[str, dict[str, str | None]] = {}
    row_keys: set[str | None] = set()
    for row in rows:
        value = row[key]
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
    source_id: str, files: Mapping[str, bytes], frame: Frame
) -> list[dict[str, object]]:
    if source_id not in ROLES or set(files) != ROLES[source_id]:
        refuse("input_schema")
    parsed = {role: _rows(body, role) for role, body in files.items()}
    if source_id == "biz_register":
        companies = _keyed(parsed["establishments"], "registration_number")
        result = []
        for key, source in sorted(companies.items()):
            row: dict[str, object] = {name: source.get(name) for name in CARD_COLUMNS}
            row.update(
                registration_number=key,
                source_id=source_id,
                registered_cell=_cell(source, frame),
            )
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
        result.append(row)
    return result


def validate_card(row: Mapping[str, object], frame: Frame) -> None:
    """Revalidate persisted lexemes and recompute location at the loader seam."""
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
            if value is not None and not isinstance(value, str):
                refuse("release_type")
            parse_value("" if value is None else value, declaration)
    coordinates = {
        name: str(row[name]) if row[name] is not None else None
        for name in ("lon", "lat")
    }
    if row["registered_cell"] != _cell(coordinates, frame):
        refuse("release_cell_mismatch")
