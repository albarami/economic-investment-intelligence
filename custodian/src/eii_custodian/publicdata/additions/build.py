"""Dispatch family parsers and publish their Public tables as one set."""

from __future__ import annotations

import hashlib
import importlib
import json
import re
from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from decimal import Decimal
from pathlib import Path

import yaml  # type: ignore[import-untyped]

from eii_custodian.publicdata.additions.common import (
    ADDITION_FAMILIES,
    AdditionError,
    FamilyParse,
    refuse_duplicate_keys,
    require_lineage,
)
from eii_custodian.publicdata.additions.property_venues import (
    PARSERS as PROPERTY_PARSERS,
)
from eii_custodian.publicdata.additions.property_venues import (
    load_venue_crosswalk,
)
from eii_custodian.publicdata.additions.storage import publish
from eii_custodian.publicdata.fetch.receipts import sha256_hex
from eii_custodian.publicdata.fetch.registry import Entry

Parser = Callable[
    [
        Entry,
        list[dict[str, object]],
        Mapping[str, object],
        Mapping[str, object],
        Mapping[str, object],
    ],
    FamilyParse,
]
Selection = Mapping[str, str] | tuple[tuple[str, str], ...]
_PROPERTY_COLUMNS = (
    ("district_key", "VARCHAR"),
    ("municipality_code", "VARCHAR"),
    ("period", "VARCHAR"),
    ("unit_type", "VARCHAR"),
    ("deal_count", "INTEGER"),
    ("median_price", "DECIMAL(14,2)"),
    ("price_basis", "VARCHAR"),
    ("source_key", "VARCHAR"),
    ("publisher", "VARCHAR"),
    ("licence_id", "VARCHAR"),
    ("licence_basis", "VARCHAR"),
    ("retrieved_utc", "VARCHAR"),
    ("sha256", "VARCHAR"),
    ("method", "VARCHAR"),
)
_VENUE_COLUMNS = (
    ("venue_key", "VARCHAR"),
    ("venue_kind", "VARCHAR"),
    ("name_en", "VARCHAR"),
    ("name_ar", "VARCHAR"),
    ("region", "VARCHAR"),
    ("place_id", "VARCHAR"),
    ("period", "VARCHAR"),
    ("indicator", "VARCHAR"),
    ("value", "INTEGER"),
    ("unit", "VARCHAR"),
    ("source_key", "VARCHAR"),
    ("publisher", "VARCHAR"),
    ("licence_id", "VARCHAR"),
    ("licence_basis", "VARCHAR"),
    ("retrieved_utc", "VARCHAR"),
    ("sha256", "VARCHAR"),
    ("method", "VARCHAR"),
)
_VENUE_KEY = ("venue_key", "period", "indicator")
_PROPERTY_KEY = ("district_key", "period", "unit_type")
_LINEAGE_COLUMNS = (
    ("source_key", "VARCHAR"),
    ("publisher", "VARCHAR"),
    ("licence_id", "VARCHAR"),
    ("licence_basis", "VARCHAR"),
    ("retrieved_utc", "VARCHAR"),
    ("sha256", "VARCHAR"),
    ("method", "VARCHAR"),
)
_DECIMAL = re.compile(r"^DECIMAL\((\d+),(\d+)\)$")
_INT32_MIN = -2147483648
_INT32_MAX = 2147483647
_ADDED = (
    (
        "pub_establishment_size",
        ("table_code", "activity_key", "size_class", "period", "indicator"),
        (("value", "DECIMAL(18,2)"), ("unit", "VARCHAR")),
    ),
    (
        "pub_manufacturing",
        ("table_code", "period", "breakdown_key", "indicator"),
        (("value", "DECIMAL(18,4)"), ("unit", "VARCHAR")),
    ),
    (
        "pub_trade_wr",
        ("trade_type", "period", "indicator"),
        (("value", "DECIMAL(18,2)"), ("unit", "VARCHAR")),
    ),
    (
        "pub_trade_logistics",
        ("table_code", "period", "breakdown_key", "indicator"),
        (("value", "DECIMAL(18,2)"), ("unit", "VARCHAR")),
    ),
    (
        "pub_building_permits",
        (
            "municipality_code",
            "period",
            "document_type",
            "permit_type",
            "building_type",
        ),
        (("document_count", "INTEGER"),),
    ),
    (
        "pub_population_age",
        ("municipality_code", "period", "age_group", "indicator"),
        (("value", "DECIMAL(18,4)"), ("unit", "VARCHAR")),
    ),
    (
        "pub_hotels_municipality",
        ("municipality_code", "period", "facility_type"),
        (("facility_count", "INTEGER"),),
    ),
    (
        "pub_census_2015_municipality",
        ("municipality_code", "period", "indicator"),
        (("value", "DECIMAL(18,4)"), ("unit", "VARCHAR")),
    ),
    (
        "pub_labour_sex_municipality",
        ("municipality_code", "period", "sex", "indicator"),
        (("value", "DECIMAL(18,4)"), ("unit", "VARCHAR")),
    ),
    (
        "pub_population_age_sex",
        ("municipality_code", "period", "age_group", "sex", "indicator"),
        (("value", "DECIMAL(18,4)"), ("unit", "VARCHAR")),
    ),
    (
        "pub_active_sex_age",
        ("period", "sex", "age_group", "activity_key", "indicator"),
        (("value", "DECIMAL(18,4)"), ("unit", "VARCHAR")),
    ),
    (
        "pub_active_nationality_occupation",
        (
            "period",
            "nationality_group",
            "sex",
            "occupation_key",
            "activity_key",
            "indicator",
        ),
        (("value", "DECIMAL(18,4)"), ("unit", "VARCHAR")),
    ),
    (
        "pub_compensation_nationality",
        ("table_code", "period", "activity_key", "nationality_group", "indicator"),
        (("value", "DECIMAL(18,2)"), ("unit", "VARCHAR")),
    ),
    (
        "pub_students",
        (
            "municipality_code",
            "period",
            "education_level",
            "education_type",
            "sex",
            "nationality_group",
            "indicator",
        ),
        (("value", "INTEGER"), ("unit", "VARCHAR")),
    ),
    (
        "pub_visitor_markets",
        ("table_code", "period", "nationality_group", "breakdown_key", "indicator"),
        (("value", "DECIMAL(18,2)"), ("unit", "VARCHAR")),
    ),
)


def _catalogue() -> dict[str, tuple[tuple[tuple[str, str], ...], tuple[str, ...]]]:
    found: dict[str, tuple[tuple[tuple[str, str], ...], tuple[str, ...]]] = {
        "pub_property_resi": (_PROPERTY_COLUMNS, _PROPERTY_KEY),
        "pub_venue_visits": (_VENUE_COLUMNS, _VENUE_KEY),
    }
    for name, key, measures in _ADDED:
        columns = tuple((column, "VARCHAR") for column in key)
        found[name] = (columns + measures + _LINEAGE_COLUMNS, key)
    return found


_CATALOGUE = _catalogue()


def checked_selection(pairs: tuple[tuple[str, str], ...]) -> dict[str, str]:
    """One hash per registry key. A repeated key is refused."""
    found: dict[str, str] = {}
    for key, digest in pairs:
        if key in found:
            raise AdditionError("duplicate_slug_selection")
        if key == "" or digest == "":
            raise AdditionError("slug_absent")
        found[key] = digest
    return found


def parsers() -> dict[str, Parser]:
    """Parsers this pass owns, plus any later pass that has exported PARSERS."""
    found: dict[str, Parser] = dict(PROPERTY_PARSERS)
    for module in _later_modules():
        later = getattr(module, "PARSERS", None)
        if isinstance(later, dict):
            found.update(later)
    return found


def _later_modules() -> tuple[object, ...]:
    """Import the passes that are present. A missing pass is pending, not a failure."""
    found: list[object] = []
    for load in (_load_industry, _load_municipal, _load_splits):
        try:
            found.append(load())
        except ImportError:
            continue
    return tuple(found)


def _load_industry() -> object:
    return importlib.import_module("eii_custodian.publicdata.additions.industry")


def _load_municipal() -> object:
    return importlib.import_module("eii_custodian.publicdata.additions.municipal")


def _load_splits() -> object:
    return importlib.import_module("eii_custodian.publicdata.additions.splits")


def build_additions(
    cache: Path,
    entries: tuple[Entry, ...] | list[Entry],
    selected_hashes: Selection,
    review: Path,
    frame: Path,
    output: Path,
) -> Path:
    """Parse the selected cached exports and publish their tables, or publish nothing."""
    selection = (
        checked_selection(selected_hashes)
        if isinstance(selected_hashes, tuple)
        else dict(selected_hashes)
    )
    by_key = {entry.key: entry for entry in entries}
    if len(by_key) != len(tuple(entries)):
        raise AdditionError("duplicate_slug_selection")
    field_map = _field_map(review / "additions_property_venues.yaml")
    crosswalks: dict[str, object] = {
        "frame": frame,
        "review": review,
        "venues": load_venue_crosswalk(review / "venue_crosswalk.csv"),
    }
    parsed: list[FamilyParse] = []
    pending: list[str] = []
    available = parsers()
    for key, digest in sorted(selection.items()):
        entry = by_key.get(key)
        if entry is None or entry.source_id not in ADDITION_FAMILIES:
            raise AdditionError("slug_absent")
        raw, receipt = _cached_export(cache, entry, digest)
        parser = available.get(entry.source_id)
        if parser is None:
            pending.append(key)
            continue
        parsed.append(parser(entry, raw, receipt, field_map, crosswalks))
    tables = _tables(parsed)
    report = _report(parsed, pending)
    return publish(output, tables, {"pending_slugs": pending}, report)


def _tables(
    parsed: Sequence[FamilyParse],
) -> tuple[
    tuple[str, tuple[tuple[str, str], ...], tuple[tuple[object, ...], ...]], ...
]:
    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for item in parsed:
        grouped[item.table].extend(item.rows)
    built: list[
        tuple[str, tuple[tuple[str, str], ...], tuple[tuple[object, ...], ...]]
    ] = []
    for name in sorted(grouped):
        rows = tuple(grouped[name])
        spec = _CATALOGUE.get(name)
        if spec is None:
            raise AdditionError("unknown_table")
        columns, key = spec
        fields = tuple(column for column, _kind in columns)
        for row in rows:
            _refuse_row(row, columns, key)
        refuse_duplicate_keys(rows, key)
        built.append(_pair(name, columns, fields, rows))
    return tuple(built)


def _refuse_row(
    row: Mapping[str, object],
    columns: tuple[tuple[str, str], ...],
    key: tuple[str, ...],
) -> None:
    names = {name for name, _kind in columns}
    if set(row) != names:
        raise AdditionError("table_columns_mismatch")
    key_names = set(key)
    for name, _kind in columns:
        value = row[name]
        if isinstance(value, float):
            raise AdditionError("value_out_of_column")
        if name in key_names and (not isinstance(value, str) or value == ""):
            raise AdditionError("key_part_missing")
    require_lineage(row)
    for name, kind in columns:
        value = row[name]
        if value is None and _null_accepted(name, row):
            continue
        _refuse_value(value, kind)


def _null_accepted(name: str, row: Mapping[str, object]) -> bool:
    """A null stands only where document 03 section 7.3 states its condition."""
    if name == "median_price":
        return row.get("deal_count") == 0
    if name in {"name_ar", "place_id"}:
        return True
    if name == "region":
        return row.get("venue_kind") == "museum_or_exhibition"
    return False


def _refuse_value(value: object, kind: str) -> None:
    if kind == "VARCHAR":
        if not isinstance(value, str):
            raise AdditionError("value_out_of_column")
        return
    number = _decimal_value(value)
    if number is None or not number.is_finite():
        raise AdditionError("value_out_of_column")
    if kind == "INTEGER":
        if number != number.to_integral_value():
            raise AdditionError("value_out_of_column")
        if number < _INT32_MIN or number > _INT32_MAX:
            raise AdditionError("value_out_of_column")
        return
    match = _DECIMAL.fullmatch(kind)
    if match is None:
        raise AdditionError("value_out_of_column")
    precision = int(match.group(1))
    scale = int(match.group(2))
    _tuple = number.as_tuple()
    exponent = _tuple.exponent
    if not isinstance(exponent, int):
        raise AdditionError("value_out_of_column")
    places = -exponent if exponent < 0 else 0
    if places > scale:
        raise AdditionError("value_out_of_column")
    if exponent >= 0:
        integer_digits = len(_tuple.digits) + exponent
    else:
        integer_digits = max(0, len(_tuple.digits) + exponent)
    if integer_digits > precision - scale:
        raise AdditionError("value_out_of_column")


def _decimal_value(value: object) -> Decimal | None:
    if isinstance(value, bool) or value is None or isinstance(value, float):
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, int):
        return Decimal(value)
    return None


def _pair(
    name: str,
    columns: tuple[tuple[str, str], ...],
    fields: tuple[str, ...],
    rows: tuple[dict[str, object], ...],
) -> tuple[str, tuple[tuple[str, str], ...], tuple[tuple[object, ...], ...]]:
    return name, columns, tuple(tuple(row[field] for field in fields) for row in rows)


def _report(parsed: Sequence[FamilyParse], pending: list[str]) -> dict[str, object]:
    coverage: list[dict[str, object]] = []
    questions: list[dict[str, str]] = []
    for item in parsed:
        for count in item.coverage:
            coverage.append({"reason": count.reason, "count": count.count})
        for question in item.questions:
            questions.append(
                {
                    "contract": question.contract,
                    "inventory": question.inventory,
                    "change": question.change,
                }
            )
    return {"coverage": coverage, "questions": questions, "pending_slugs": pending}


def _cached_export(
    cache: Path, entry: Entry, digest: str
) -> tuple[list[dict[str, object]], dict[str, object]]:
    directory = cache / entry.key
    body_path = directory / f"{digest}.{entry.extension}"
    side_path = directory / f"{digest}.meta.json"
    if not body_path.is_file() or not side_path.is_file():
        raise AdditionError("hash_absent")
    body = body_path.read_bytes()
    if sha256_hex(body) != digest or hashlib.sha256(body).hexdigest() != digest:
        raise AdditionError("hash_mismatch")
    try:
        loaded = json.loads(body.decode("utf-8"))
        receipt = json.loads(side_path.read_text(encoding="utf-8"))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise AdditionError("export_unreadable") from error
    if isinstance(loaded, dict):
        results = loaded.get("results")
        loaded = results if isinstance(results, list) else None
    if not isinstance(loaded, list) or not all(isinstance(row, dict) for row in loaded):
        raise AdditionError("export_unreadable")
    if not isinstance(receipt, dict):
        raise AdditionError("export_unreadable")
    rows: list[dict[str, object]] = []
    for row in loaded:
        if isinstance(row, dict):
            rows.append(row)
    return rows, receipt


def _field_map(path: Path) -> dict[str, object]:
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as error:
        raise AdditionError("field_map_unreadable") from error
    if not isinstance(loaded, dict):
        raise AdditionError("field_map_unreadable")
    return loaded
