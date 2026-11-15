"""Parsers for the Public split families of decision 0017.

A category the contract does not name is left out. A category the file does
not list is not invented. Sex or nationality that the file holds only in the
slug comes from the reviewed slug map.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

import yaml  # type: ignore[import-untyped]

from eii_custodian.publicdata.additions.common import (
    FIELD_UNCONFIRMED,
    METHOD_VERSION,
    AdditionError,
    ContractQuestion,
    Coverage,
    FamilyParse,
    MeasureKind,
    attach_lineage,
    fit_to_contract,
    observe_period_bounds,
    parse_period_rule,
    parse_period_value,
    read_measure,
    receipt_text,
    refuse_duplicate_keys,
    require_closed,
)
from eii_custodian.publicdata.fetch.registry import Entry
from eii_custodian.publicdata.frame.checks import FrameError
from eii_custodian.publicdata.frame.crosswalk import (
    load_municipality_names,
    municipality_key,
    read_csv,
)

_METHOD = f"eii_custodian.publicdata.additions.splits.parse@{METHOD_VERSION}"
_PERSONS = "persons"
_UNCONFIRMED = "to_be_confirmed"
_LABOUR_QUESTION = ContractQuestion(
    contract="indicator is population, labour_force, employed or unemployed",
    inventory=(
        "Economically Active, Economically Inactive and two population indicators "
        "do not match those four names; the population slugs' Employed repeats "
        "the employed slug"
    ),
    change=(
        "add a distinct indicator for each published population label and for "
        "economically inactive, and confirm whether Economically Active is "
        "labour_force, without storing the repeated Employed rows"
    ),
)
_TABLES = {
    "labour_population": "pub_labour_sex_municipality",
    "labour_gender": "pub_labour_sex_municipality",
    "population_age": "pub_population_age_sex",
    "active_sex": "pub_active_sex_age",
    "active_nat": "pub_active_nationality_occupation",
    "compensation": "pub_compensation_nationality",
    "students": "pub_students",
    "hotel": "pub_visitor_markets",
    "arrivals_mode": "pub_visitor_markets",
    "arrivals_region": "pub_visitor_markets",
    "arrivals_trends": "pub_visitor_markets",
}
_KEYS = {
    "labour_population": ("municipality_code", "period", "sex", "indicator"),
    "labour_gender": ("municipality_code", "period", "sex", "indicator"),
    "population_age": ("municipality_code", "period", "age_group", "sex", "indicator"),
    "active_sex": ("period", "sex", "age_group", "activity_key", "indicator"),
    "active_nat": (
        "period",
        "nationality_group",
        "sex",
        "occupation_key",
        "activity_key",
        "indicator",
    ),
    "compensation": (
        "table_code",
        "period",
        "activity_key",
        "nationality_group",
        "indicator",
    ),
    "students": (
        "municipality_code",
        "period",
        "education_level",
        "education_type",
        "sex",
        "nationality_group",
        "indicator",
    ),
    "hotel": (
        "table_code",
        "period",
        "nationality_group",
        "breakdown_key",
        "indicator",
    ),
    "arrivals_mode": (
        "table_code",
        "period",
        "nationality_group",
        "breakdown_key",
        "indicator",
    ),
    "arrivals_region": (
        "table_code",
        "period",
        "nationality_group",
        "breakdown_key",
        "indicator",
    ),
    "arrivals_trends": (
        "table_code",
        "period",
        "nationality_group",
        "breakdown_key",
        "indicator",
    ),
}
_MUNICIPAL = frozenset(
    {"labour_population", "labour_gender", "population_age", "students"}
)
_WIDE = frozenset({"arrivals_mode", "arrivals_region"})
_MONTHS = parse_period_rule("sit=columns;form=month_name_year")


@dataclass(frozen=True)
class _Role:
    kind: str
    sex: str | None
    nationality: str | None
    indicator: str | None
    measure: str
    integral: bool
    as_int: bool
    table_code: str | None
    code_field: str | None
    indicator_field: str | None


def parse_splits(
    entry: Entry,
    raw: list[dict[str, object]],
    receipt: Mapping[str, object],
    field_map: Mapping[str, object],
    crosswalks: Mapping[str, object],
) -> FamilyParse:
    """Parse one slug of a split family into the contract rows it can hold."""
    spec = _spec(field_map, crosswalks)
    role = _role(spec, entry.key)
    _refuse_unknown_fields(entry, raw)
    rule = parse_period_rule(entry.period_field)
    if rule.field == FIELD_UNCONFIRMED:
        raise AdditionError("period_field_unconfirmed")
    vocab = _vocab(spec)
    names = _names(crosswalks) if role.kind in _MUNICIPAL else None
    counts: dict[str, int] = {}
    built: list[dict[str, object]] = []
    for source in raw:
        built.extend(_cells(entry, source, role, vocab, names, counts, receipt))
    keys = _KEYS[role.kind]
    fit = fit_to_contract(tuple(built), key_fields=keys)
    refuse_duplicate_keys(fit.kept, keys)
    first, last = observe_period_bounds(list(raw), rule)
    questions = _questions(counts)
    return FamilyParse(
        _TABLES[role.kind],
        fit.kept,
        _coverage(counts, fit.blocked),
        first,
        last,
        questions,
    )


PARSERS = {
    "lf_muni_sex": parse_splits,
    "pop_muni_age_sex": parse_splits,
    "active_sex_age_act": parse_splits,
    "active_nat_occ_act": parse_splits,
    "comp_nat_act": parse_splits,
    "students_muni": parse_splits,
    "visitors_markets": parse_splits,
}


def _cells(
    entry: Entry,
    source: Mapping[str, object],
    role: _Role,
    vocab: Mapping[str, object],
    names: list[dict[str, str]] | None,
    counts: dict[str, int],
    receipt: Mapping[str, object],
) -> list[dict[str, object]]:
    if role.kind in _WIDE:
        return _wide(entry, source, role, vocab, counts, receipt)
    body = _long(source, role, vocab, names, counts)
    if body is None:
        return []
    period = _cell_period(entry, source)
    return [_carry(entry, receipt, body, period)]


def _long(
    source: Mapping[str, object],
    role: _Role,
    vocab: Mapping[str, object],
    names: list[dict[str, str]] | None,
    counts: dict[str, int],
) -> dict[str, object] | None:
    place = _place(source, names, counts) if names is not None else None
    if names is not None and place is None:
        return None
    kind = role.kind
    if kind == "labour_population":
        return _labour_population(source, role, vocab, counts, place or "")
    if kind == "labour_gender":
        return _labour_gender(source, role, vocab, counts, place or "")
    if kind == "population_age":
        return _population(source, role, vocab, counts, place or "")
    if kind == "active_sex":
        return _active_sex(source, role, vocab, counts)
    if kind == "active_nat":
        return _active_nat(source, role, vocab, counts)
    if kind == "compensation":
        return _compensation(source, role, vocab, counts)
    if kind == "students":
        return _students(source, role, vocab, counts, place or "")
    if kind == "hotel":
        return _hotel(source, role, vocab, counts)
    if kind == "arrivals_trends":
        return _trends(source, role, vocab, counts)
    raise AdditionError("field_map_unreadable")


def _labour_population(
    source: Mapping[str, object],
    role: _Role,
    vocab: Mapping[str, object],
    counts: dict[str, int],
    place: str,
) -> dict[str, object] | None:
    label = source.get("indicator")
    omitted = _string_map(vocab, "labour_omit")
    if isinstance(label, str) and label in omitted:
        _add(counts, omitted[label])
        return None
    raise AdditionError("category_unlisted")


def _labour_gender(
    source: Mapping[str, object],
    role: _Role,
    vocab: Mapping[str, object],
    counts: dict[str, int],
    place: str,
) -> dict[str, object] | None:
    number = _measure(source.get(role.measure), role, counts)
    if number is None:
        return None
    sex = _mapped(source.get("gender"), _string_map(vocab, "sex"))
    indicator = require_closed(
        role.indicator or "",
        frozenset({"employed", "unemployed"}),
        "category_unlisted",
    )
    return _people(place, sex, indicator, number, _PERSONS)


def _population(
    source: Mapping[str, object],
    role: _Role,
    vocab: Mapping[str, object],
    counts: dict[str, int],
    place: str,
) -> dict[str, object] | None:
    number = _measure(source.get(role.measure), role, counts)
    if number is None:
        return None
    age = _kept(
        source.get("age_groups_in_years"), _string_set(vocab, "ages_population")
    )
    twin = source.get("fy_t_l_mr_blsnwt")
    if isinstance(twin, str) and twin != "" and twin != age:
        raise AdditionError("category_unlisted")
    sex = require_closed(
        role.sex or "", frozenset({"female", "male"}), "category_unlisted"
    )
    return {
        "municipality_code": place,
        "age_group": age,
        "sex": sex,
        "indicator": "residents",
        "value": number,
        "unit": _PERSONS,
    }


def _active_sex(
    source: Mapping[str, object],
    role: _Role,
    vocab: Mapping[str, object],
    counts: dict[str, int],
) -> dict[str, object] | None:
    number = _measure(source.get(role.measure), role, counts)
    if number is None:
        return None
    return {
        "sex": require_closed(
            role.sex or "", frozenset({"female", "male"}), "category_unlisted"
        ),
        "age_group": _kept(source.get("age_group"), _string_set(vocab, "ages_active")),
        "activity_key": _kept(
            source.get("economic_activity"), _string_set(vocab, "activities")
        ),
        "indicator": "economically_active",
        "value": number,
        "unit": _PERSONS,
    }


def _active_nat(
    source: Mapping[str, object],
    role: _Role,
    vocab: Mapping[str, object],
    counts: dict[str, int],
) -> dict[str, object] | None:
    number = _measure(source.get(role.measure), role, counts)
    if number is None:
        return None
    return {
        "nationality_group": require_closed(
            role.nationality or "",
            frozenset({"qatari", "non_qatari"}),
            "category_unlisted",
        ),
        "sex": require_closed(
            role.sex or "", frozenset({"female", "male", "all"}), "category_unlisted"
        ),
        "occupation_key": _kept(
            source.get("occupation"), _string_set(vocab, "occupations")
        ),
        "activity_key": _kept(
            source.get("economic_activity"), _string_set(vocab, "activities")
        ),
        "indicator": "economically_active",
        "value": number,
        "unit": _PERSONS,
    }


def _compensation(
    source: Mapping[str, object],
    role: _Role,
    vocab: Mapping[str, object],
    counts: dict[str, int],
) -> dict[str, object] | None:
    indicator = _mapped(
        source.get(role.indicator_field or ""),
        _string_map(vocab, "compensation_indicator"),
    )
    number = _measure(source.get(role.measure), role, counts)
    if number is None:
        return None
    unit = "annual" if indicator == "compensation" else _UNCONFIRMED
    return {
        "table_code": role.table_code or "",
        "activity_key": _code(source.get(role.code_field or "")),
        "nationality_group": _mapped(
            source.get("nationality"), _string_map(vocab, "nationality")
        ),
        "indicator": indicator,
        "value": number,
        "unit": unit,
    }


def _students(
    source: Mapping[str, object],
    role: _Role,
    vocab: Mapping[str, object],
    counts: dict[str, int],
    place: str,
) -> dict[str, object] | None:
    number = _measure(source.get(role.measure), role, counts)
    if number is None:
        return None
    return {
        "municipality_code": place,
        "education_level": _kept(
            source.get("level_of_education"), _string_set(vocab, "education_level")
        ),
        "education_type": _kept(
            source.get("type_of_education"), _string_set(vocab, "education_type")
        ),
        "sex": _mapped(source.get("gender"), _string_map(vocab, "sex")),
        "nationality_group": _mapped(
            source.get("nationality"), _string_map(vocab, "nationality")
        ),
        "indicator": "students",
        "value": number,
        "unit": _PERSONS,
    }


def _hotel(
    source: Mapping[str, object],
    role: _Role,
    vocab: Mapping[str, object],
    counts: dict[str, int],
) -> dict[str, object] | None:
    group = _kept(source.get("nationality"), _string_set(vocab, "hotel_nationality"))
    rating = _kept(source.get("hotel_rating"), _string_set(vocab, "hotel_rating"))
    indicator = _mapped(source.get("metric"), _string_map(vocab, "metrics"))
    number = _measure(source.get(role.measure), role, counts)
    if number is None:
        return None
    return {
        "table_code": role.table_code or "",
        "nationality_group": group,
        "breakdown_key": f"hotel_rating={rating}",
        "indicator": indicator,
        "value": number,
        "unit": _UNCONFIRMED,
    }


def _trends(
    source: Mapping[str, object],
    role: _Role,
    vocab: Mapping[str, object],
    counts: dict[str, int],
) -> dict[str, object] | None:
    mode = _kept(source.get("mode_of_transportation"), _string_set(vocab, "modes"))
    number = _measure(source.get(role.measure), role, counts)
    if number is None:
        return None
    return {
        "table_code": role.table_code or "",
        "nationality_group": "all",
        "breakdown_key": f"mode_of_transportation={mode}",
        "indicator": "arrivals",
        "value": number,
        "unit": _UNCONFIRMED,
    }


def _wide(
    entry: Entry,
    source: Mapping[str, object],
    role: _Role,
    vocab: Mapping[str, object],
    counts: dict[str, int],
    receipt: Mapping[str, object],
) -> list[dict[str, object]]:
    shared = _wide_shared(source, role, vocab)
    built: list[dict[str, object]] = []
    for key, value in source.items():
        if not isinstance(key, str):
            raise AdditionError("period_form")
        period = _month_of(key)
        if period is None:
            continue
        number = _measure(value, role, counts)
        if number is None:
            continue
        built.append(_carry(entry, receipt, {**shared, "value": number}, period))
    return built


def _wide_shared(
    source: Mapping[str, object], role: _Role, vocab: Mapping[str, object]
) -> dict[str, object]:
    if role.kind == "arrivals_mode":
        mode = _kept(source.get("mode_of_entry"), _string_set(vocab, "modes"))
        return {
            "table_code": role.table_code or "",
            "nationality_group": "all",
            "breakdown_key": f"mode_of_entry={mode}",
            "indicator": "arrivals",
            "unit": _UNCONFIRMED,
        }
    region = _kept(source.get("region"), _string_set(vocab, "regions"))
    return {
        "table_code": role.table_code or "",
        "nationality_group": region,
        "breakdown_key": "ALL",
        "indicator": "arrivals",
        "unit": _UNCONFIRMED,
    }


def _people(
    place: str, sex: str, indicator: str, number: Decimal | int, unit: str
) -> dict[str, object]:
    return {
        "municipality_code": place,
        "sex": sex,
        "indicator": indicator,
        "value": number,
        "unit": unit,
    }


def _measure(
    value: object, role: _Role, counts: dict[str, int]
) -> Decimal | int | None:
    read = read_measure(value, missing_forms=frozenset(), integral=role.integral)
    if read.kind is MeasureKind.MISSING:
        _add(counts, "missing_measure")
        return None
    if read.number is None:
        raise AdditionError("measure_unparsed")
    if role.as_int:
        return int(read.number)
    return read.number


def _place(
    source: Mapping[str, object],
    names: list[dict[str, str]] | None,
    counts: dict[str, int],
) -> str | None:
    if names is None:
        return None
    english = source.get("municipality")
    arabic = source.get("lbldy")
    if not isinstance(english, str) or english.strip() == "":
        _add(counts, "contract_key_unheld")
        return None
    if not isinstance(arabic, str) or arabic.strip() == "":
        _add(counts, "contract_key_unheld")
        return None
    try:
        english_key = municipality_key(english, names)
        arabic_key = municipality_key(arabic, names)
    except FrameError as error:
        raise AdditionError("unmapped_municipality") from error
    if english_key != arabic_key:
        raise AdditionError("bilingual_municipality")
    return english_key


def _carry(
    entry: Entry,
    receipt: Mapping[str, object],
    row: Mapping[str, object],
    period: str,
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
        method=_METHOD,
    )


def _cell_period(entry: Entry, source: Mapping[str, object]) -> str:
    rule = parse_period_rule(entry.period_field)
    if rule.sit != "row":
        raise AdditionError("period_sit")
    return parse_period_value(source.get(rule.field), rule.form)


def _month_of(key: str) -> str | None:
    try:
        first, last = observe_period_bounds([{key: 0}], _MONTHS)
    except AdditionError as error:
        if error.name == "period_absent":
            return None
        raise
    if first != last:
        raise AdditionError("period_form")
    return first


def _code(value: object) -> str:
    if isinstance(value, bool) or value is None:
        raise AdditionError("category_unlisted")
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if not value.is_integer():
            raise AdditionError("category_unlisted")
        return str(int(value))
    if isinstance(value, str) and value.strip() != "":
        return value
    raise AdditionError("category_unlisted")


def _kept(value: object, allowed: frozenset[str]) -> str:
    if not isinstance(value, str) or value not in allowed:
        raise AdditionError("category_unlisted")
    return value


def _mapped(value: object, table: Mapping[str, str]) -> str:
    if not isinstance(value, str) or value not in table:
        raise AdditionError("category_unlisted")
    return table[value]


def _questions(counts: Mapping[str, int]) -> tuple[ContractQuestion, ...]:
    if counts.get("indicator_unheld") or counts.get("published_twice"):
        return (_LABOUR_QUESTION,)
    return ()


def _coverage(
    counts: Mapping[str, int], extra: tuple[Coverage, ...]
) -> tuple[Coverage, ...]:
    found = [
        Coverage(reason, count) for reason, count in sorted(counts.items()) if count > 0
    ]
    return tuple([*found, *extra])


def _add(counts: dict[str, int], reason: str) -> None:
    counts[reason] = counts.get(reason, 0) + 1


def _refuse_unknown_fields(entry: Entry, raw: list[dict[str, object]]) -> None:
    declared = {name for name, _kind in entry.columns}
    for row in raw:
        if set(row) - declared:
            raise AdditionError("unknown_source_field")


def _names(crosswalks: Mapping[str, object]) -> list[dict[str, str]]:
    review = crosswalks.get("frame")
    if not isinstance(review, Path):
        raise AdditionError("crosswalk_missing")
    rows = read_csv(review / "municipality_names.csv")
    known = {row["municipality_code"] for row in rows}
    return load_municipality_names(review, known)


def _spec(
    field_map: Mapping[str, object], crosswalks: Mapping[str, object]
) -> dict[str, object]:
    if "roles" in field_map and "vocab" in field_map:
        return dict(field_map)
    review = crosswalks.get("review")
    if not isinstance(review, Path):
        raise AdditionError("field_map_unreadable")
    path = review / "additions_splits.yaml"
    if not path.is_file():
        raise AdditionError("field_map_unreadable")
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as error:
        raise AdditionError("field_map_unreadable") from error
    if not isinstance(loaded, dict) or "roles" not in loaded or "vocab" not in loaded:
        raise AdditionError("field_map_unreadable")
    return loaded


def _vocab(spec: Mapping[str, object]) -> Mapping[str, object]:
    vocab = spec.get("vocab")
    if not isinstance(vocab, dict):
        raise AdditionError("field_map_unreadable")
    return vocab


def _role(spec: Mapping[str, object], key: str) -> _Role:
    roles = spec.get("roles")
    if not isinstance(roles, dict) or key not in roles:
        raise AdditionError("field_map_unreadable")
    raw = roles[key]
    if not isinstance(raw, dict):
        raise AdditionError("field_map_unreadable")
    kind = raw.get("kind")
    if not isinstance(kind, str) or kind not in _TABLES:
        raise AdditionError("field_map_unreadable")
    return _Role(
        kind,
        _optional(raw, "sex"),
        _optional(raw, "nationality"),
        _optional(raw, "indicator"),
        _required(raw, "measure") if "measure" in raw else "value",
        _flag(raw, "integral", True),
        _flag(raw, "as_int", False),
        _optional(raw, "table_code"),
        _optional(raw, "code_field"),
        _optional(raw, "indicator_field"),
    )


def _optional(raw: Mapping[str, object], name: str) -> str | None:
    if name not in raw or raw[name] is None:
        return None
    value = raw[name]
    if not isinstance(value, str):
        raise AdditionError("field_map_unreadable")
    return value


def _required(raw: Mapping[str, object], name: str) -> str:
    value = _optional(raw, name)
    if value is None:
        raise AdditionError("field_map_unreadable")
    return value


def _flag(raw: Mapping[str, object], name: str, default: bool) -> bool:
    if name not in raw:
        return default
    value = raw[name]
    if not isinstance(value, bool):
        raise AdditionError("field_map_unreadable")
    return value


def _string_map(vocab: Mapping[str, object], name: str) -> dict[str, str]:
    raw = vocab.get(name)
    if not isinstance(raw, dict):
        raise AdditionError("field_map_unreadable")
    mapped: dict[str, str] = {}
    for key, value in raw.items():
        if not isinstance(key, str) or not isinstance(value, str):
            raise AdditionError("field_map_unreadable")
        mapped[key] = value
    return mapped


def _string_set(vocab: Mapping[str, object], name: str) -> frozenset[str]:
    raw = vocab.get(name)
    if not isinstance(raw, list) or not all(isinstance(item, str) for item in raw):
        raise AdditionError("field_map_unreadable")
    return frozenset(item for item in raw if isinstance(item, str))
