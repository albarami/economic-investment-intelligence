"""Establishment size, manufacturing, trade and logistics parsers.

Each bulletin keeps its own field names and labels. A missing size class is
not filled. A country enters only by an exact crosswalk label. A missing
measure is left out and is never stored as zero.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from decimal import ROUND_HALF_UP, Context, Decimal, localcontext
from pathlib import Path
from typing import cast

import yaml

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

_EST_KEY = ("table_code", "activity_key", "size_class", "period", "indicator")
_MFG_KEY = ("table_code", "period", "breakdown_key", "indicator")
_TRADE_KEY = ("trade_type", "period", "indicator")
_SCALE_ESTABLISHMENT = 2
_SCALE_MANUFACTURING = 6
_SCALE_LOGISTICS = 2
_TWO_DIGITS = re.compile(r"^\d{2}$")
_FOUR_DIGITS = re.compile(r"^\d{4}$")
_SECTION = re.compile(r"^[A-Z]$")
_ISO3 = re.compile(r"^[A-Z]{3}$")
_SIZE_QUESTION = ContractQuestion(
    contract=(
        "pub_establishment_size is keyed by table_code, activity_key, "
        "size_class, period and indicator"
    ),
    inventory="the business-services slug has no size class; it has a field group",
    change="keep those rows out; do not fill size_class with ALL",
)
_TRADE_QUESTION = ContractQuestion(
    contract=(
        "pub_trade_wr is keyed by trade_type, period and indicator, "
        "and indicator is purchases, sales or stocks"
    ),
    inventory=(
        "each trade type and year holds six measure-breakdown pairs "
        "and the key has no breakdown column"
    ),
    change="add breakdown to the primary key and keep indicator as the measure",
)
_REGION_QUESTION = ContractQuestion(
    contract=(
        "pub_trade_logistics breakdown_key holds each country as an "
        "ISO 3166-1 alpha-3 code through a committed crosswalk"
    ),
    inventory=(
        "country of previous port is ten regions, not countries, "
        "and a region has no ISO code"
    ),
    change=(
        "allow a reviewed region key that is not an ISO code, "
        "or keep the region rows out"
    ),
)
_TRADE_INDICATORS = frozenset({"purchases", "sales", "stocks"})


def parse_establishment_size(
    entry: Entry,
    raw: list[dict[str, object]],
    receipt: Mapping[str, object],
    field_map: Mapping[str, object],
    crosswalks: Mapping[str, object],
) -> FamilyParse:
    """Parse one establishment-size bulletin onto pub_establishment_size."""
    spec = _spec(_review(field_map, crosswalks), entry)
    if spec.get("layout") != "establishment":
        raise AdditionError("slug_unmapped")
    return _establishment(entry, raw, receipt, spec)


def parse_manufacturing(
    entry: Entry,
    raw: list[dict[str, object]],
    receipt: Mapping[str, object],
    field_map: Mapping[str, object],
    crosswalks: Mapping[str, object],
) -> FamilyParse:
    """Parse one manufacturing bulletin onto pub_manufacturing."""
    spec = _spec(_review(field_map, crosswalks), entry)
    layout = spec.get("layout")
    if layout == "licence":
        return _licence(entry, raw, receipt, spec)
    if layout == "products":
        return _products(entry, raw, receipt, spec)
    raise AdditionError("slug_unmapped")


def parse_trade(
    entry: Entry,
    raw: list[dict[str, object]],
    receipt: Mapping[str, object],
    field_map: Mapping[str, object],
    crosswalks: Mapping[str, object],
) -> FamilyParse:
    """Read wholesale and retail trade. The contract key cannot hold the breakdown."""
    spec = _spec(_review(field_map, crosswalks), entry)
    if spec.get("layout") != "trade":
        raise AdditionError("slug_unmapped")
    return _trade(entry, raw, receipt, spec)


def parse_logistics(
    entry: Entry,
    raw: list[dict[str, object]],
    receipt: Mapping[str, object],
    field_map: Mapping[str, object],
    crosswalks: Mapping[str, object],
) -> FamilyParse:
    """Parse certificates or vessels. Country labels match the crosswalk exactly."""
    review = _review(field_map, crosswalks)
    spec = _spec(review, entry)
    walk = _crosswalk(review)
    layout = spec.get("layout")
    if layout == "certificates":
        return _certificates(entry, raw, receipt, spec, review, walk)
    if layout == "vessels":
        return _vessels(entry, raw, receipt, spec, review, walk)
    if layout == "wide":
        return _wide(entry, raw, receipt, spec, review, walk)
    raise AdditionError("slug_unmapped")


PARSERS = {
    "est_size_act": parse_establishment_size,
    "mfg_industry": parse_manufacturing,
    "trade_wr": parse_trade,
    "trade_logistics": parse_logistics,
}


def _establishment(
    entry: Entry,
    raw: list[dict[str, object]],
    receipt: Mapping[str, object],
    spec: Mapping[str, object],
) -> FamilyParse:
    allowed = _string_set(spec.get("fields"))
    counts: dict[str, int] = {}
    rows: list[dict[str, object]] = []
    for source in raw:
        _own_fields(source, allowed)
        period = parse_period_value(source.get("year"), "year_text")
        activity = _activity(spec, source.get("activity_code"))
        indicators = spec.get("indicators")
        if indicators == FIELD_UNCONFIRMED:
            raise AdditionError("indicator_labels_unconfirmed")
        indicator = require_closed(
            _mapped(
                _text(source, _name(spec, "indicator_field")),
                indicators,
                "unknown_indicator",
            ),
            frozenset({"establishments", "employees", "compensation"}),
            "unknown_indicator",
        )
        _text(source, _name(spec, "indicator_ar"), "arabic_twin_missing")
        number = _number(
            source.get("value"), integral=True, places=_SCALE_ESTABLISHMENT
        )
        if number is None:
            _add(counts, "measure_missing")
            continue
        size_field = spec.get("size_field")
        if not isinstance(size_field, str):
            _add(counts, "missing_size_class")
            continue
        size = require_closed(
            _text(source, size_field),
            _string_set(spec.get("size_classes")),
            "unknown_size_class",
        )
        _size_arabic(source, spec, size)
        rows.append(
            _attach(
                entry,
                receipt,
                {
                    "table_code": entry.slug,
                    "activity_key": activity,
                    "size_class": size,
                    "indicator": indicator,
                    "value": number,
                    "unit": _unit(spec),
                },
                period,
                "parse_establishment_size",
            )
        )
    questions = (_SIZE_QUESTION,) if counts.get("missing_size_class") else ()
    return _finish(
        entry, raw, "pub_establishment_size", rows, counts, questions, _EST_KEY
    )


def _licence(
    entry: Entry,
    raw: list[dict[str, object]],
    receipt: Mapping[str, object],
    spec: Mapping[str, object],
) -> FamilyParse:
    allowed = _string_set(spec.get("fields"))
    licences = _string_set(spec.get("licence_types"))
    counts: dict[str, int] = {}
    rows: list[dict[str, object]] = []
    for source in raw:
        _own_fields(source, allowed)
        period = parse_period_value(source.get("year"), "year_text")
        licence = require_closed(
            _text(source, _name(spec, "licence_field")),
            licences,
            "unknown_licence_type",
        )
        arabic = spec.get("licence_ar")
        if isinstance(arabic, str):
            _text(source, arabic, "arabic_twin_missing")
        breakdown = _breakdown((("licence_type", licence),))
        for measure in _measures(spec):
            number = _number(
                source.get(_name_of(measure, "field")),
                integral=_integral(spec, measure),
                places=_SCALE_MANUFACTURING,
            )
            if number is None:
                _add(counts, "measure_missing")
                continue
            rows.append(
                _attach(
                    entry,
                    receipt,
                    {
                        "table_code": entry.slug,
                        "breakdown_key": breakdown,
                        "indicator": _name_of(measure, "indicator"),
                        "value": number,
                        "unit": _name_of(measure, "unit"),
                    },
                    period,
                    "parse_manufacturing",
                )
            )
    return _finish(entry, raw, "pub_manufacturing", rows, counts, (), _MFG_KEY)


def _products(
    entry: Entry,
    raw: list[dict[str, object]],
    receipt: Mapping[str, object],
    spec: Mapping[str, object],
) -> FamilyParse:
    allowed = _string_set(spec.get("fields"))
    counts: dict[str, int] = {}
    rows: list[dict[str, object]] = []
    for source in raw:
        _own_fields(source, allowed)
        period = parse_period_value(source.get("year"), "year_text")
        category = require_closed(
            _text(source, "category"),
            _string_set(spec.get("categories")),
            "unknown_category",
        )
        product = require_closed(
            _text(source, "product"),
            _string_set(spec.get("products")),
            "unknown_product",
        )
        unit = require_closed(
            _text(source, "unit"), _string_set(spec.get("units")), "unknown_unit"
        )
        for field in ("lfy", "lmntj", "lwhd"):
            _text(source, field, "arabic_twin_missing")
        number = _number(
            source.get("production"), integral=True, places=_SCALE_MANUFACTURING
        )
        if number is None:
            _add(counts, "measure_missing")
            continue
        rows.append(
            _attach(
                entry,
                receipt,
                {
                    "table_code": entry.slug,
                    "breakdown_key": _breakdown(
                        (("category", category), ("product", product))
                    ),
                    "indicator": "production",
                    "value": number,
                    "unit": unit,
                },
                period,
                "parse_manufacturing",
            )
        )
    return _finish(entry, raw, "pub_manufacturing", rows, counts, (), _MFG_KEY)


def _trade(
    entry: Entry,
    raw: list[dict[str, object]],
    receipt: Mapping[str, object],
    spec: Mapping[str, object],
) -> FamilyParse:
    allowed = _string_set(spec.get("fields"))
    counts: dict[str, int] = {}
    for source in raw:
        _own_fields(source, allowed)
        parse_period_value(source.get("year"), "year_text")
        _text(source, "type_of_trade", "trade_type_absent")
        for field in ("nw_ltjr", "lmw_shr", "ltfsyl"):
            _text(source, field, "arabic_twin_missing")
        require_closed(
            _mapped(
                _text(source, "measure"), spec.get("indicators"), "unknown_indicator"
            ),
            _TRADE_INDICATORS,
            "unknown_indicator",
        )
        require_closed(
            _text(source, "breakdown"),
            _string_set(spec.get("breakdowns")),
            "unknown_breakdown",
        )
        number = _number(
            source.get("value"), integral=True, places=_SCALE_ESTABLISHMENT
        )
        if number is None:
            _add(counts, "measure_missing")
            continue
        _add(counts, "breakdown_not_in_key")
    questions = (_TRADE_QUESTION,) if counts.get("breakdown_not_in_key") else ()
    return _finish(entry, raw, "pub_trade_wr", [], counts, questions, _TRADE_KEY)


def _certificates(
    entry: Entry,
    raw: list[dict[str, object]],
    receipt: Mapping[str, object],
    spec: Mapping[str, object],
    review: Mapping[str, object],
    walk: Mapping[str, str],
) -> FamilyParse:
    allowed = _string_set(spec.get("fields"))
    unpublished = _string_set(review.get("certificate_types_unpublished"))
    kinds = _string_set(review.get("certificate_types"))
    withheld = _string_set(review.get("country_labels_withheld"))
    regions = _string_set(review.get("regions_not_countries"))
    counts: dict[str, int] = {}
    rows: list[dict[str, object]] = []
    for source in raw:
        _own_fields(source, allowed)
        period = parse_period_value(source.get("year"), "year_text")
        _text(source, "nw_lshhd", "arabic_twin_missing")
        _text(source, "ldwl_lmstwrd", "arabic_twin_missing")
        kind = _text(source, "type_of_certificate")
        number = _number(
            source.get("number_of_issued_certificates"),
            integral=True,
            places=_SCALE_LOGISTICS,
        )
        if number is None:
            _add(counts, "measure_missing")
            continue
        if kind in unpublished:
            _add(counts, "certificate_type_unpublished")
            continue
        if kind not in kinds:
            kind = _mapped(
                kind, review.get("certificate_type_aliases"), "unknown_certificate_type"
            )
        kind = require_closed(kind, kinds, "unknown_certificate_type")
        label = _text(source, _name(spec, "country_field"))
        if label in regions:
            _add(counts, "region_not_country")
            continue
        if _country_withheld(label, withheld, counts):
            continue
        country = _country(label, walk)
        rows.append(
            _attach(
                entry,
                receipt,
                {
                    "table_code": entry.slug,
                    "breakdown_key": _breakdown(
                        (("certificate_type", kind), ("importing_country", country))
                    ),
                    "indicator": _name(spec, "indicator"),
                    "value": number,
                    "unit": _unit(spec),
                },
                period,
                "parse_logistics",
            )
        )
    rows = _combine_certificates(rows, counts)
    return _finish(entry, raw, "pub_trade_logistics", rows, counts, (), _MFG_KEY)


def _combine_certificates(
    rows: list[dict[str, object]], counts: dict[str, int]
) -> list[dict[str, object]]:
    """Sum integral certificate counts only within the full contract key."""
    combined: dict[tuple[object, ...], dict[str, object]] = {}
    totals: dict[tuple[object, ...], int] = {}
    for row in rows:
        key = tuple(row[field] for field in _MFG_KEY)
        if key in combined:
            _add(counts, "country_labels_merged")
        else:
            combined[key] = row
        # {certificates}: Python integers keep the sum independent of Decimal context.
        totals[key] = totals.get(key, 0) + int(cast(Decimal, row["value"]))
    for key, row in combined.items():
        row["value"] = Decimal(totals[key])
    return list(combined.values())


def _country_withheld(
    label: str, withheld: frozenset[str], counts: dict[str, int]
) -> bool:
    if label in withheld:
        _add(counts, "country_label_withheld")
        return True
    return False


def _vessels(
    entry: Entry,
    raw: list[dict[str, object]],
    receipt: Mapping[str, object],
    spec: Mapping[str, object],
    review: Mapping[str, object],
    walk: Mapping[str, str],
) -> FamilyParse:
    allowed = _string_set(spec.get("fields"))
    regions = _string_set(review.get("regions_not_countries"))
    withheld = _string_set(review.get("country_labels_withheld"))
    vessels = _string_set(review.get("vessel_types"))
    counts: dict[str, int] = {}
    rows: list[dict[str, object]] = []
    for source in raw:
        _own_fields(source, allowed)
        period = parse_period_value(source.get("year"), "year_text")
        label = _text(source, _name(spec, "country_field"))
        vessel = require_closed(
            _text(source, "vessel_type"), vessels, "unknown_vessel_type"
        )
        indicator = _mapped(
            _text(source, "indicator"), spec.get("indicators"), "unknown_indicator"
        )
        for field in ("bld_lmyn_lsbq", "nw_lsfyn", "lbyn"):
            _text(source, field, "arabic_twin_missing")
        number = _number(source.get("number"), integral=False, places=_SCALE_LOGISTICS)
        if number is None:
            _add(counts, "measure_missing")
            continue
        if label in regions:
            _add(counts, "region_not_country")
            continue
        if _country_withheld(label, withheld, counts):
            continue
        country = _country(label, walk)
        rows.append(
            _attach(
                entry,
                receipt,
                {
                    "table_code": entry.slug,
                    "breakdown_key": _breakdown(
                        (
                            ("country_of_previous_port", country),
                            ("vessel_type", vessel),
                        )
                    ),
                    "indicator": indicator,
                    "value": number,
                    "unit": _unit(spec),
                },
                period,
                "parse_logistics",
            )
        )
    questions = (_REGION_QUESTION,) if counts.get("region_not_country") else ()
    return _finish(entry, raw, "pub_trade_logistics", rows, counts, questions, _MFG_KEY)


def _wide(
    entry: Entry,
    raw: list[dict[str, object]],
    receipt: Mapping[str, object],
    spec: Mapping[str, object],
    review: Mapping[str, object],
    walk: Mapping[str, str],
) -> FamilyParse:
    allowed = _string_set(spec.get("fields"))
    columns = tuple(sorted(_string_set(spec.get("columns"))))
    regions = _string_set(review.get("regions_not_countries"))
    withheld = _string_set(review.get("country_labels_withheld"))
    counts: dict[str, int] = {}
    rows: list[dict[str, object]] = []
    for source in raw:
        _own_fields(source, allowed)
        period = parse_period_value(source.get("year"), "year_text")
        label = _text(source, _name(spec, "country_field"))
        if label in regions:
            _add(counts, "region_not_country")
            continue
        if _country_withheld(label, withheld, counts):
            continue
        country = _country(label, walk)
        indicator = _mapped(
            _text(source, "number_tonnage"), spec.get("indicators"), "unknown_indicator"
        )
        for field in ("bld_ltsjyl", "l_dd_wlhmwl"):
            _text(source, field, "arabic_twin_missing")
        for column in columns:
            number = _number(source.get(column), integral=True, places=_SCALE_LOGISTICS)
            if number is None:
                _add(counts, "measure_missing")
                continue
            rows.append(
                _attach(
                    entry,
                    receipt,
                    {
                        "table_code": entry.slug,
                        "breakdown_key": _breakdown(
                            (
                                ("country_of_registration", country),
                                ("vessel_type", column),
                            )
                        ),
                        "indicator": indicator,
                        "value": number,
                        "unit": _unit(spec),
                    },
                    period,
                    "parse_logistics",
                )
            )
    return _finish(entry, raw, "pub_trade_logistics", rows, counts, (), _MFG_KEY)


def _finish(
    entry: Entry,
    raw: list[dict[str, object]],
    table: str,
    rows: list[dict[str, object]],
    counts: dict[str, int],
    questions: tuple[ContractQuestion, ...],
    key_fields: tuple[str, ...],
) -> FamilyParse:
    fit = fit_to_contract(tuple(rows), key_fields=key_fields)
    for item in fit.blocked:
        _add(counts, item.reason, item.count)
    refuse_duplicate_keys(fit.kept, key_fields)
    ordered = tuple(
        sorted(fit.kept, key=lambda row: tuple(str(row[field]) for field in key_fields))
    )
    first, last = _bounds(entry, raw)
    coverage = tuple(
        Coverage(reason, counts[reason]) for reason in sorted(counts) if counts[reason]
    )
    return FamilyParse(table, ordered, coverage, first, last, questions)


def _bounds(entry: Entry, raw: list[dict[str, object]]) -> tuple[str, str]:
    rule = parse_period_rule(entry.period_field)
    if rule.field == FIELD_UNCONFIRMED:
        raise AdditionError("period_field_unconfirmed")
    return observe_period_bounds(list(raw), rule)


def _attach(
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
        method=(
            f"eii_custodian.publicdata.additions.industry.{method}@{METHOD_VERSION}"
        ),
    )


def _review(
    field_map: Mapping[str, object], crosswalks: Mapping[str, object]
) -> Mapping[str, object]:
    if "slugs" in field_map and "country_crosswalk" in field_map:
        if field_map.get("version") != 1:
            raise AdditionError("field_map_unreadable")
        return field_map
    review = crosswalks.get("review")
    if not isinstance(review, Path):
        raise AdditionError("field_map_unreadable")
    path = review / "additions_industry.yaml"
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as error:
        raise AdditionError("field_map_unreadable") from error
    if not isinstance(loaded, dict) or loaded.get("version") != 1:
        raise AdditionError("field_map_unreadable")
    return loaded


def _spec(review: Mapping[str, object], entry: Entry) -> dict[str, object]:
    slugs = _as_dict(review.get("slugs"))
    raw = slugs.get(entry.slug)
    if not isinstance(raw, dict):
        raise AdditionError("slug_unmapped")
    schema_name = raw.get("schema")
    merged: dict[str, object]
    if isinstance(schema_name, str):
        schema = _as_dict(review.get("schemas")).get(schema_name)
        if not isinstance(schema, dict):
            raise AdditionError("field_map_unreadable")
        merged = dict(schema)
        merged.update(raw)
    else:
        merged = dict(raw)
    if merged.get("family") != entry.source_id:
        raise AdditionError("slug_unmapped")
    return merged


def _crosswalk(review: Mapping[str, object]) -> dict[str, str]:
    rows = review.get("country_crosswalk")
    if not isinstance(rows, list):
        raise AdditionError("country_crosswalk")
    found: dict[str, str] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise AdditionError("country_crosswalk")
        label = row.get("published_label")
        iso = row.get("iso3")
        if not isinstance(label, str) or label == "" or not isinstance(iso, str):
            raise AdditionError("country_crosswalk")
        if _ISO3.fullmatch(iso) is None or label in found:
            raise AdditionError("country_crosswalk")
        found[label] = iso
    return found


def _country(label: str, walk: Mapping[str, str]) -> str:
    if label not in walk:
        raise AdditionError("country_unreviewed")
    return walk[label]


def _activity(spec: Mapping[str, object], value: object) -> str:
    if not isinstance(value, str):
        raise AdditionError("activity_code_form")
    form = spec.get("activity_form")
    if form == "closed":
        return require_closed(
            value, _string_set(spec.get("activity_codes")), "activity_code_unlisted"
        )
    if form == "two_digit" and _TWO_DIGITS.fullmatch(value):
        return value
    if form == "four_digit" and _FOUR_DIGITS.fullmatch(value):
        return value
    if form == "mixed" and (
        _SECTION.fullmatch(value)
        or _TWO_DIGITS.fullmatch(value)
        or _FOUR_DIGITS.fullmatch(value)
    ):
        return value
    raise AdditionError("activity_code_form")


def _size_arabic(
    source: Mapping[str, object], spec: Mapping[str, object], size: str
) -> None:
    arabic = _text(source, _name(spec, "size_ar"), "arabic_twin_missing")
    pairs = spec.get("size_pairs")
    if not isinstance(pairs, dict) or size not in pairs:
        return
    expected = pairs[size]
    if arabic != expected:
        raise AdditionError("arabic_twin_mismatch")


def _number(value: object, *, integral: bool, places: int) -> Decimal | None:
    read = read_measure(value, missing_forms=frozenset(), integral=integral)
    if read.kind is MeasureKind.MISSING:
        return None
    if read.number is None:
        raise AdditionError("measure_unparsed")
    quantum = Decimal(1).scaleb(-places)
    precision = _working_precision(read.number, places=places, carry=1)
    with localcontext(Context(prec=precision, rounding=ROUND_HALF_UP)):
        quantized = read.number.quantize(quantum, rounding=ROUND_HALF_UP)
    if quantized != read.number:
        raise AdditionError("measure_precision")
    return quantized


def _working_precision(number: Decimal, *, places: int, carry: int) -> int:
    """Precision that holds one half-up quantize of this number."""
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


def _breakdown(pairs: tuple[tuple[str, str], ...]) -> str:
    parts: list[str] = []
    for name, value in sorted(pairs):
        if "=" in name or "=" in value or "|" in name or "|" in value:
            raise AdditionError("breakdown_unencodable")
        parts.append(f"{name}={value}")
    return "|".join(parts)


def _measures(spec: Mapping[str, object]) -> tuple[Mapping[str, object], ...]:
    value = spec.get("measures")
    if not isinstance(value, list):
        raise AdditionError("field_map_unreadable")
    found: list[Mapping[str, object]] = []
    for item in value:
        if not isinstance(item, dict):
            raise AdditionError("field_map_unreadable")
        found.append(item)
    return tuple(found)


def _integral(spec: Mapping[str, object], measure: Mapping[str, object]) -> bool:
    if measure.get("indicator") == "labour" and "labour_integral" in spec:
        return bool(spec.get("labour_integral"))
    return bool(measure.get("integral"))


def _mapped(value: str, mapping: object, name: str) -> str:
    if not isinstance(mapping, dict):
        raise AdditionError("field_map_unreadable")
    found = mapping.get(value)
    if not isinstance(found, str) or found == "":
        raise AdditionError(name)
    return found


def _own_fields(row: Mapping[str, object], allowed: frozenset[str]) -> None:
    keys = set(row)
    if keys - allowed:
        raise AdditionError("unknown_source_field")
    if allowed - keys:
        raise AdditionError("source_field_absent")


def _text(row: Mapping[str, object], field: str, name: str = "measure_unparsed") -> str:
    value = row.get(field)
    if not isinstance(value, str) or value == "":
        raise AdditionError(name)
    return value


def _name(spec: Mapping[str, object], key: str) -> str:
    value = spec.get(key)
    if not isinstance(value, str) or value == "":
        raise AdditionError("field_map_unreadable")
    return value


def _name_of(measure: Mapping[str, object], key: str) -> str:
    value = measure.get(key)
    if not isinstance(value, str) or value == "":
        raise AdditionError("field_map_unreadable")
    return value


def _unit(spec: Mapping[str, object]) -> str:
    value = spec.get("unit")
    if not isinstance(value, str) or value == "":
        raise AdditionError("field_map_unreadable")
    return value


def _string_set(value: object) -> frozenset[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise AdditionError("field_map_unreadable")
    return frozenset(item for item in value if isinstance(item, str))


def _as_dict(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise AdditionError("field_map_unreadable")
    return value


def _add(counts: dict[str, int], reason: str, count: int = 1) -> None:
    counts[reason] = counts.get(reason, 0) + count
