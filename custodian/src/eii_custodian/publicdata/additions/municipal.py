"""Municipal permits, population by age, hotel facilities and the 2015 census.

A row is written with its lineage, left out under a named reason, or the build
stops by a named error. Municipality spellings resolve only through the frame
lookup. Monthly and annual permit figures are never added together, a hotel
number is a facility count, and census geometry is not kept.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Context, Decimal, localcontext
from pathlib import Path
from typing import Any

import yaml

from eii_custodian.publicdata.additions.common import (
    METHOD_VERSION,
    AdditionError,
    ContractQuestion,
    Coverage,
    FamilyParse,
    MeasureKind,
    attach_lineage,
    observe_period_bounds,
    parse_period_rule,
    read_measure,
    receipt_text,
    refuse_duplicate_keys,
    require_closed,
)
from eii_custodian.publicdata.fetch.registry import Entry
from eii_custodian.publicdata.frame.crosswalk import (
    load_municipality_names,
    municipality_keys,
    read_csv,
)

_SCALE = Decimal("0.0001")
_PERMIT_KEY = (
    "municipality_code",
    "period",
    "document_type",
    "permit_type",
    "building_type",
)
_POPULATION_KEY = ("municipality_code", "period", "age_group", "indicator")
_HOTEL_KEY = ("municipality_code", "period", "facility_type")
_CENSUS_KEY = ("municipality_code", "period", "indicator")
_PERMITS = "eii_custodian.publicdata.additions.municipal.parse_permits"
_POPULATION = "eii_custodian.publicdata.additions.municipal.parse_population"
_HOTELS = "eii_custodian.publicdata.additions.municipal.parse_hotels"
_CENSUS = "eii_custodian.publicdata.additions.municipal.parse_census"
_CLASSIFICATION = ContractQuestion(
    contract=(
        "permit_type is a published key or all, and building_type is a "
        "published key or all"
    ),
    inventory=(
        "the monthly type_of_permit has 3 classes and the annual permit_type "
        "has 11; they are different classifications in one column"
    ),
    change="add a classification field so the two vocabularies are not one column",
)
_MONTHLY = ContractQuestion(
    contract=(
        "pub_building_permits is keyed by municipality_code, period, "
        "document_type, permit_type and building_type"
    ),
    inventory=(
        "monthly slugs carry no municipality field; the municipality is known "
        "only from the slug; municipality_names.csv is a name list, not a slug list"
    ),
    change=(
        "record both published spellings of that one municipality for the "
        "existing lookup to resolve"
    ),
)
_SHARES = ContractQuestion(
    contract=(
        "pub_census_2015_municipality indicator is establishments or employees; "
        "value is the count; unit is establishments or persons"
    ),
    inventory=(
        "two percent-share fields beside the counts; each share is in percent "
        "and the eight rows of a share sum to 100"
    ),
    change=(
        "add share indicators with unit percent on the municipality grain, "
        "and add no national row"
    ),
)


@dataclass(frozen=True)
class _PermitKind:
    """Which document the slug's own type field states."""

    document: str
    measure: str
    type_field: str
    arabic_field: str
    monthly: bool


def parse_permits(
    entry: Entry,
    raw: list[dict[str, object]],
    receipt: Mapping[str, object],
    field_map: Mapping[str, object],
    crosswalks: Mapping[str, object],
) -> FamilyParse:
    """Parse one permit or certificate slug. Monthly rows need declared spellings."""
    kind = _permit_kind(entry)
    _refuse_unknown(entry, raw)
    rules = _rules(field_map, crosswalks)
    codes = _codes(entry, raw, _geography(rules, entry.key), _names(crosswalks))
    built: list[dict[str, object]] = []
    missing = 0
    absent = 0
    for row, code in zip(raw, codes, strict=True):
        period = _period(entry, row)
        permit_type, building_type = _permit_labels(row, kind, rules)
        count = _whole(row.get(kind.measure))
        if count is None:
            missing += 1
        if code is None:
            absent += 1
        if count is None or code is None:
            continue
        built.append(
            _lineage(
                entry,
                receipt,
                {
                    "municipality_code": code,
                    "document_type": kind.document,
                    "permit_type": permit_type,
                    "building_type": building_type,
                    "document_count": count,
                },
                period,
                _PERMITS,
            )
        )
    refuse_duplicate_keys(tuple(built), _PERMIT_KEY)
    questions = [_CLASSIFICATION]
    if absent:
        questions.append(_MONTHLY)
    return _done(
        "pub_building_permits",
        _sort(built, _PERMIT_KEY),
        {"missing_measure": missing, "municipality_absent": absent},
        _bounds(entry, raw),
        tuple(questions),
    )


def parse_population(
    entry: Entry,
    raw: list[dict[str, object]],
    receipt: Mapping[str, object],
    field_map: Mapping[str, object],
    crosswalks: Mapping[str, object],
) -> FamilyParse:
    """Parse population by municipality and age. Cells are not summed."""
    _refuse_unknown(entry, raw)
    rules = _rules(field_map, crosswalks)
    ages = _strings(rules, "age_groups")
    codes = _codes(entry, raw, _geography(rules, entry.key), _names(crosswalks))
    built: list[dict[str, object]] = []
    missing = 0
    for row, code in zip(raw, codes, strict=True):
        period = _period(entry, row)
        value = _scaled(row.get("count"))
        if code is None or value is None:
            missing += 1
            continue
        built.append(
            _lineage(
                entry,
                receipt,
                {
                    "municipality_code": code,
                    "age_group": require_closed(
                        _text(row, "age_groups"), ages, "age_group"
                    ),
                    "indicator": "residents",
                    "value": value,
                    "unit": "persons",
                },
                period,
                _POPULATION,
            )
        )
    refuse_duplicate_keys(tuple(built), _POPULATION_KEY)
    return _done(
        "pub_population_age",
        _sort(built, _POPULATION_KEY),
        {"missing_measure": missing},
        _bounds(entry, raw),
        (),
    )


def parse_hotels(
    entry: Entry,
    raw: list[dict[str, object]],
    receipt: Mapping[str, object],
    field_map: Mapping[str, object],
    crosswalks: Mapping[str, object],
) -> FamilyParse:
    """Parse hotel and hotel-apartment counts. The number is facilities."""
    _refuse_unknown(entry, raw)
    rules = _rules(field_map, crosswalks)
    pairs = _pairs(rules, "facility_pairs")
    codes = _codes(entry, raw, _geography(rules, entry.key), _names(crosswalks))
    built: list[dict[str, object]] = []
    missing = 0
    for row, code in zip(raw, codes, strict=True):
        period = _period(entry, row)
        facility = _paired(
            _text(row, "facility_type"),
            _text(row, "nw_lmnsh"),
            pairs,
            "category_disagreement",
            "facility_type",
        )
        count = _whole(row.get("number"))
        if code is None or count is None:
            missing += 1
            continue
        built.append(
            _lineage(
                entry,
                receipt,
                {
                    "municipality_code": code,
                    "facility_type": facility,
                    "facility_count": count,
                },
                period,
                _HOTELS,
            )
        )
    refuse_duplicate_keys(tuple(built), _HOTEL_KEY)
    return _done(
        "pub_hotels_municipality",
        _sort(built, _HOTEL_KEY),
        {"missing_measure": missing},
        _bounds(entry, raw),
        (),
    )


def parse_census(
    entry: Entry,
    raw: list[dict[str, object]],
    receipt: Mapping[str, object],
    field_map: Mapping[str, object],
    crosswalks: Mapping[str, object],
) -> FamilyParse:
    """Keep the file's census year and its two counts. Drop shares and geometry."""
    _refuse_unknown(entry, raw)
    rules = _rules(field_map, crosswalks)
    codes = _codes(entry, raw, _geography(rules, entry.key), _names(crosswalks))
    counts = _census_counts(rules)
    percent_fields = _string_list(rules, "census_percent_fields")
    geometry_fields = _string_list(rules, "census_geometry_fields")
    built: list[dict[str, object]] = []
    missing = 0
    shares = 0
    geometry = 0
    for row, code in zip(raw, codes, strict=True):
        period = _period(entry, row)
        shares += _shares(row, percent_fields)
        geometry += _geometry(row, geometry_fields)
        if code is None:
            missing += len(counts)
            continue
        for indicator, field, unit in counts:
            value = _scaled(row.get(field))
            if value is None:
                missing += 1
                continue
            built.append(
                _lineage(
                    entry,
                    receipt,
                    {
                        "municipality_code": code,
                        "indicator": indicator,
                        "value": value,
                        "unit": unit,
                    },
                    period,
                    _CENSUS,
                )
            )
    refuse_duplicate_keys(tuple(built), _CENSUS_KEY)
    return _done(
        "pub_census_2015_municipality",
        _sort(built, _CENSUS_KEY),
        {
            "missing_measure": missing,
            "percent_share_unheld": shares,
            "geometry_discarded": geometry,
        },
        _bounds(entry, raw),
        (_SHARES,),
    )


PARSERS = {
    "permits_muni": parse_permits,
    "pop_muni_age": parse_population,
    "hotels_muni": parse_hotels,
    "est_census_2015_muni": parse_census,
}


def _permit_kind(entry: Entry) -> _PermitKind:
    columns = {name for name, _kind in entry.columns}
    if "certificate_type" in columns:
        return _PermitKind(
            "completion_certificate", "count", "certificate_type", "nw_lshhd", False
        )
    if "permit_type" in columns:
        return _PermitKind("building_permit", "count", "permit_type", "nw_lrkhs", False)
    if "type_of_permit" in columns:
        return _PermitKind(
            "building_permit", "number", "type_of_permit", "nw_lrkhs", True
        )
    raise AdditionError("document_type")


def _permit_labels(
    row: Mapping[str, object], kind: _PermitKind, rules: Mapping[str, object]
) -> tuple[str, str]:
    english = _text(row, kind.type_field)
    arabic = _text(row, kind.arabic_field)
    if kind.monthly:
        _text(row, "lshhr")
        return (
            _paired(
                english,
                arabic,
                _pairs(rules, "monthly_permit_pairs"),
                "category_disagreement",
                "category_unlisted",
            ),
            "all",
        )
    building = _building(row, rules, kind.document)
    if kind.document == "building_permit":
        require_closed(
            english, _strings(rules, "annual_permit_type"), "category_unlisted"
        )
        require_closed(
            arabic, _strings(rules, "annual_permit_type_ar"), "category_unlisted"
        )
    else:
        require_closed(
            english, _strings(rules, "certificate_type"), "category_unlisted"
        )
    return english, building


def _building(
    row: Mapping[str, object], rules: Mapping[str, object], document: str
) -> str:
    english = _text(row, "building_type")
    arabic = _text(row, "nw_lmbn")
    if document == "building_permit":
        return _paired(
            english,
            arabic,
            _pairs(rules, "annual_building_pairs"),
            "category_disagreement",
            "category_unlisted",
        )
    if english not in _strings(rules, "certificate_building_type"):
        raise AdditionError("category_unlisted")
    matched = [
        pair
        for pair in _pairs(rules, "certificate_building_pairs")
        if pair[0] == english
    ]
    if matched and (english, arabic) not in matched:
        raise AdditionError("category_disagreement")
    return english


def _rules(
    field_map: Mapping[str, object], crosswalks: Mapping[str, object]
) -> dict[str, object]:
    if "geography" in field_map:
        if not isinstance(field_map.get("geography"), dict):
            raise AdditionError("field_map_unreadable")
        return {str(key): value for key, value in field_map.items()}
    review = crosswalks.get("review")
    if not isinstance(review, Path):
        raise AdditionError("field_map_unreadable")
    path = review / "additions_municipal.yaml"
    if not path.is_file():
        raise AdditionError("field_map_unreadable")
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as error:
        raise AdditionError("field_map_unreadable") from error
    if not isinstance(loaded, dict) or not isinstance(loaded.get("geography"), dict):
        raise AdditionError("field_map_unreadable")
    return _string_keys(loaded)


def _geography(rules: Mapping[str, object], key: str) -> dict[str, object]:
    block = rules.get("geography")
    if not isinstance(block, dict):
        raise AdditionError("field_map_unreadable")
    item = block.get(key)
    if not isinstance(item, dict) or item.get("grain") != "municipality":
        raise AdditionError("geography_undeclared")
    if "municipality_code" in item:
        raise AdditionError("second_mapping")
    return _string_keys(item)


def _codes(
    entry: Entry,
    raw: list[dict[str, object]],
    geo: Mapping[str, object],
    names: list[dict[str, str]],
) -> list[str | None]:
    fields = _string_list(geo, "name_fields")
    if fields:
        records = [{field: _text(row, field) for field in fields} for row in raw]
        return list(
            municipality_keys(entry.source_id, records, tuple(fields), names, None)
        )
    published = geo.get("published_names", [])
    if not isinstance(published, list) or not all(
        isinstance(name, str) for name in published
    ):
        raise AdditionError("field_map_unreadable")
    if len(published) == 0:
        return [None] * len(raw)
    if len(published) != 2:
        raise AdditionError("municipality_spellings")
    found = municipality_keys(
        entry.source_id,
        [{"municipality": published[0], "lbldy": published[1]}],
        ("municipality", "lbldy"),
        names,
        None,
    )
    return [found[0]] * len(raw)


def _names(crosswalks: Mapping[str, object]) -> list[dict[str, str]]:
    frame = crosswalks.get("frame")
    if not isinstance(frame, Path) or not (frame / "municipality_names.csv").is_file():
        raise AdditionError("crosswalk_missing")
    rows = read_csv(frame / "municipality_names.csv")
    known = {row["municipality_code"] for row in rows}
    return load_municipality_names(frame, known)


def _whole(value: object) -> int | None:
    number = _number(value, integral=True)
    if number is None:
        return None
    if number < 0:
        raise AdditionError("measure_negative")
    return int(number)


def _scaled(value: object) -> Decimal | None:
    number = _number(value, integral=True)
    if number is None:
        return None
    if number < 0:
        raise AdditionError("measure_negative")
    precision = _working_precision(number, places=4, carry=0)
    with localcontext(Context(prec=precision, rounding=ROUND_HALF_UP)):
        return number.quantize(_SCALE, rounding=ROUND_HALF_UP)


def _working_precision(number: Decimal, *, places: int, carry: int) -> int:
    """Precision that holds this integral number at the contract scale."""
    pair = number.as_tuple()
    digits = len(pair.digits)
    exponent = pair.exponent
    if isinstance(exponent, int) and exponent >= 0:
        integer_digits = digits + exponent
    elif isinstance(exponent, int):
        integer_digits = max(0, digits + exponent)
    else:
        integer_digits = digits
    return max(digits, integer_digits + places + carry, 1)


def _number(value: object, *, integral: bool) -> Decimal | None:
    read = read_measure(value, missing_forms=frozenset(), integral=integral)
    if read.kind is MeasureKind.MISSING:
        return None
    if read.number is None:
        raise AdditionError("measure_unparsed")
    return read.number


def _shares(row: Mapping[str, object], fields: tuple[str, ...]) -> int:
    kept = 0
    for field in fields:
        value = row.get(field)
        if value is None or value == "":
            continue
        _number(value, integral=False)
        kept += 1
    return kept


def _geometry(row: Mapping[str, object], fields: tuple[str, ...]) -> int:
    return sum(1 for field in fields if row.get(field) is not None)


def _census_counts(rules: Mapping[str, object]) -> tuple[tuple[str, str, str], ...]:
    value = rules.get("census_counts")
    if not isinstance(value, list) or not value:
        raise AdditionError("field_map_unreadable")
    found: list[tuple[str, str, str]] = []
    for item in value:
        if not isinstance(item, dict):
            raise AdditionError("field_map_unreadable")
        indicator = item.get("indicator")
        field = item.get("field")
        unit = item.get("unit")
        if (
            not isinstance(indicator, str)
            or not isinstance(field, str)
            or not isinstance(unit, str)
        ):
            raise AdditionError("field_map_unreadable")
        found.append((indicator, field, unit))
    return tuple(found)


def _pairs(rules: Mapping[str, object], name: str) -> tuple[tuple[str, str], ...]:
    value = rules.get(name)
    if not isinstance(value, list):
        raise AdditionError("field_map_unreadable")
    found: list[tuple[str, str]] = []
    for item in value:
        if (
            not isinstance(item, list)
            or len(item) != 2
            or not isinstance(item[0], str)
            or not isinstance(item[1], str)
        ):
            raise AdditionError("field_map_unreadable")
        found.append((item[0], item[1]))
    return tuple(found)


def _paired(
    english: str,
    arabic: str,
    pairs: tuple[tuple[str, str], ...],
    disagreement: str,
    unlisted: str,
) -> str:
    if (english, arabic) in pairs:
        return english
    if any(pair[0] == english for pair in pairs):
        raise AdditionError(disagreement)
    raise AdditionError(unlisted)


def _strings(rules: Mapping[str, object], name: str) -> frozenset[str]:
    return frozenset(_string_list(rules, name))


def _string_list(rules: Mapping[str, object], name: str) -> tuple[str, ...]:
    value = rules.get(name)
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise AdditionError("field_map_unreadable")
    return tuple(value)


def _string_keys(value: dict[Any, Any]) -> dict[str, object]:
    found: dict[str, object] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            raise AdditionError("field_map_unreadable")
        found[key] = item
    return found


def _text(row: Mapping[str, object], field: str) -> str:
    value = row.get(field)
    if not isinstance(value, str) or value.strip() == "":
        raise AdditionError("category_unparsed")
    return value


def _period(entry: Entry, row: dict[str, object]) -> str:
    first, last = _bounds(entry, [row])
    if first != last:
        raise AdditionError("period_form")
    return first


def _bounds(entry: Entry, raw: list[dict[str, object]]) -> tuple[str, str]:
    return observe_period_bounds(list(raw), parse_period_rule(entry.period_field))


def _lineage(
    entry: Entry,
    receipt: Mapping[str, object],
    row: dict[str, object],
    period: str,
    method: str,
) -> dict[str, object]:
    return attach_lineage(
        row,
        source_key=entry.key,
        publisher=entry.publisher,
        licence_id=entry.licence_id,
        licence_basis=entry.licence_basis,
        retrieved_utc=receipt_text(receipt, "retrieved_utc"),
        sha256=receipt_text(receipt, "sha256"),
        period=period,
        method=f"{method}@{METHOD_VERSION}",
    )


def _refuse_unknown(entry: Entry, raw: list[dict[str, object]]) -> None:
    declared = {name for name, _kind in entry.columns}
    for row in raw:
        if set(row) - declared:
            raise AdditionError("unknown_source_field")


def _sort(
    rows: list[dict[str, object]], keys: tuple[str, ...]
) -> tuple[dict[str, object], ...]:
    return tuple(sorted(rows, key=lambda row: tuple(str(row[key]) for key in keys)))


def _done(
    table: str,
    rows: tuple[dict[str, object], ...],
    counts: dict[str, int],
    bounds: tuple[str, str],
    questions: tuple[ContractQuestion, ...],
) -> FamilyParse:
    coverage = tuple(
        Coverage(reason, count) for reason, count in sorted(counts.items()) if count
    )
    return FamilyParse(table, rows, coverage, bounds[0], bounds[1], questions)
