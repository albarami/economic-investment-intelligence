"""Residential-unit aggregates and published venue visits.

A repeated transaction number is one deal. The median uses one per-square-metre
price for that deal when every kept row of the deal agrees, and the deal is
blocked when those prices differ. property_value is never summed. Transaction
and parcel identifiers never leave this module.
"""

from __future__ import annotations

import csv
from collections import defaultdict
from collections.abc import Mapping
from decimal import ROUND_HALF_UP, Context, Decimal, localcontext
from pathlib import Path

import yaml

from eii_custodian.publicdata.additions.common import (
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
    district_keys,
    load_municipality_names,
    municipality_key,
    read_csv,
)

REPEATED_TRANSACTION_RULE = (
    "deal_count counts distinct transaction numbers; "
    "one agreed per-square-metre price is kept once; "
    "disagreeing prices block that deal; property_value is never summed"
)
IDENTIFIER_FIELDS = frozenset(
    {"encrypted_transaction_number", "encrypted_parcel_number"}
)
VENUE_COLUMNS = (
    "source_key",
    "published_name",
    "venue_key",
    "place_id",
    "reviewer_role",
    "reviewed_on",
)
PROPERTY_KEY = ("district_key", "period", "unit_type")
VENUE_KEY = ("venue_key", "period", "indicator")
_PRICE_QUESTION = ContractQuestion(
    contract=(
        "pub_property_resi is keyed by district_key, period and unit_type, "
        "with one price_basis for all the sales of a row"
    ),
    inventory=(
        "every row carries both a per-square-metre price and a per-unit value, "
        "and one unit type only"
    ),
    change=(
        "add price_basis to the primary key before storing a per-unit aggregate "
        "beside the per-square-metre aggregate"
    ),
)
_QUARTER_QUESTION = ContractQuestion(
    contract="pub_property_quarter holds the quarterly sum and the per-square-foot median",
    inventory="repeated transaction numbers copy a deal value onto more than one row",
    change="leave pub_property_quarter to the task that owns PUB-107",
)


def parse_property(
    entry: Entry,
    raw: list[dict[str, object]],
    receipt: Mapping[str, object],
    field_map: Mapping[str, object],
    crosswalks: Mapping[str, object],
) -> FamilyParse:
    """Aggregate kept deals by district, month and unit type on the per-square-metre basis."""
    _refuse_unknown_fields(entry, raw)
    identifiers = _identifier_values(raw)
    names = _municipality_rows(crosswalks)
    districts = _district_rows(crosswalks)
    unit_types = _unit_types(field_map)
    prepared, blocked = _prepare_property_rows(
        raw, names, districts, _known_districts(districts), unit_types
    )
    grouped, disagreements = _deals(prepared)
    if disagreements:
        blocked.append(Coverage("repeated_deal_price_disagreement", disagreements))
    rows = _aggregate_property(entry, receipt, grouped)
    fit = fit_to_contract(rows, key_fields=PROPERTY_KEY, question=_PRICE_QUESTION)
    refuse_duplicate_keys(fit.kept, PROPERTY_KEY)
    _refuse_identifier_text(repr(fit.kept), identifiers)
    first, last = _bounds(entry, raw)
    coverage = _merge_coverage(blocked, fit.blocked)
    questions = (_PRICE_QUESTION, _QUARTER_QUESTION, *fit.questions)
    return FamilyParse("pub_property_resi", fit.kept, coverage, first, last, questions)


def parse_museum(
    entry: Entry,
    raw: list[dict[str, object]],
    receipt: Mapping[str, object],
    field_map: Mapping[str, object],
    crosswalks: Mapping[str, object],
) -> FamilyParse:
    """Count and omit reviewed missing cells; other non-numeric text stops the build."""
    return _parse_visits(entry, raw, receipt, field_map, crosswalks, museum=True)


def parse_health_centres(
    entry: Entry,
    raw: list[dict[str, object]],
    receipt: Mapping[str, object],
    field_map: Mapping[str, object],
    crosswalks: Mapping[str, object],
) -> FamilyParse:
    """Read health-centre year columns as annual periods. A null is not a zero and not a month."""
    return _parse_visits(entry, raw, receipt, field_map, crosswalks, museum=False)


def missing_forms_for(key: str) -> tuple[str, frozenset[str]] | None:
    """Return the reviewed missing-value field and forms for one registry key."""
    path = Path(__file__).resolve().parents[4] / "publicdata" / "review"
    file = path / "additions_property_venues.yaml"
    if not file.is_file():
        return None
    loaded = yaml.safe_load(file.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        return None
    block = loaded.get("missing_measures")
    if not isinstance(block, dict):
        return None
    item = block.get(key)
    if not isinstance(item, dict):
        return None
    field = item.get("field")
    forms = item.get("forms")
    if not isinstance(field, str) or not isinstance(forms, list):
        return None
    if not all(isinstance(form, str) for form in forms):
        return None
    return field, frozenset(form for form in forms if isinstance(form, str))


def load_venue_crosswalk(path: object) -> tuple[dict[str, str], ...]:
    """Load the reviewed crosswalk. The header-only file maps no name."""
    from pathlib import Path

    file = path if isinstance(path, Path) else Path(str(path))
    with file.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != VENUE_COLUMNS:
            raise AdditionError("venue_crosswalk")
        rows = [dict(row) for row in reader]
    seen: set[tuple[str, str]] = set()
    for row in rows:
        if any(row.get(column) is None for column in VENUE_COLUMNS):
            raise AdditionError("venue_crosswalk")
        if row["published_name"] == "" or row["venue_key"] == "":
            raise AdditionError("unreviewed_venue")
        if row["reviewer_role"] == "" or not _reviewed_on(row["reviewed_on"]):
            raise AdditionError("unreviewed_venue")
        identity = (row["source_key"], row["published_name"])
        if identity in seen:
            raise AdditionError("venue_crosswalk_conflict")
        seen.add(identity)
    return tuple(rows)


PARSERS = {
    "prop_resi_units": parse_property,
    "visits_museum": parse_museum,
    "visits_phcc": parse_health_centres,
}


def _parse_visits(
    entry: Entry,
    raw: list[dict[str, object]],
    receipt: Mapping[str, object],
    field_map: Mapping[str, object],
    crosswalks: Mapping[str, object],
    *,
    museum: bool,
) -> FamilyParse:
    _refuse_unknown_fields(entry, raw)
    links = crosswalks.get("venues")
    if not isinstance(links, tuple):
        raise AdditionError("venue_crosswalk")
    built: list[dict[str, object]] = []
    dropped = 0
    if museum:
        field, missing = _missing_measure(field_map, entry.key)
        built, dropped = _museum_rows(entry, raw, receipt, links, field, missing)
    else:
        built, dropped = _health_rows(entry, raw, receipt, links)
    refuse_duplicate_keys(tuple(built), VENUE_KEY)
    reason = "missing_measure" if museum else "missing_value"
    coverage = (Coverage(reason, dropped),) if dropped else ()
    first, last = _bounds(entry, raw)
    return FamilyParse("pub_venue_visits", tuple(built), coverage, first, last, ())


def _museum_rows(
    entry: Entry,
    raw: list[dict[str, object]],
    receipt: Mapping[str, object],
    links: tuple[dict[str, str], ...],
    field: str,
    missing: frozenset[str],
) -> tuple[list[dict[str, object]], int]:
    built: list[dict[str, object]] = []
    dropped = 0
    for row in raw:
        measure = read_measure(row.get(field), missing_forms=missing, integral=True)
        if measure.kind is MeasureKind.MISSING:
            dropped += 1
            continue
        period = _month_period(row)
        english = _venue(links, entry.key, _text(row, "museum"))
        arabic = _venue(links, entry.key, _text(row, "lmthf"))
        if english["venue_key"] != arabic["venue_key"]:
            raise AdditionError("venue_name_conflict")
        place = _one_place(english["place_id"], arabic["place_id"])
        value = measure.number
        if value is None:
            raise AdditionError("measure_unparsed")
        built.append(
            _visit_row(
                entry,
                receipt,
                venue_key=english["venue_key"],
                venue_kind="museum_or_exhibition",
                name_en=_text(row, "museum"),
                name_ar=_text(row, "lmthf"),
                region=None,
                place_id=place,
                period=period,
                indicator="visitors",
                value=int(value),
            )
        )
    return built, dropped


def _health_rows(
    entry: Entry,
    raw: list[dict[str, object]],
    receipt: Mapping[str, object],
    links: tuple[dict[str, str], ...],
) -> tuple[list[dict[str, object]], int]:
    built: list[dict[str, object]] = []
    dropped = 0
    rule = parse_period_rule(entry.period_field)
    for row in raw:
        link = _venue(links, entry.key, _text(row, "health_center_name"))
        for key, value in row.items():
            if rule.form != "year_header" or not isinstance(key, str):
                continue
            try:
                period = parse_period_value(key, "year_text")
            except AdditionError:
                continue
            measure = read_measure(value, missing_forms=frozenset(), integral=True)
            if measure.kind is MeasureKind.MISSING:
                dropped += 1
                continue
            number = measure.number
            if number is None:
                raise AdditionError("measure_unparsed")
            built.append(
                _visit_row(
                    entry,
                    receipt,
                    venue_key=link["venue_key"],
                    venue_kind="health_centre",
                    name_en=_text(row, "health_center_name"),
                    name_ar=None,
                    region=_text(row, "region"),
                    place_id=link["place_id"] or None,
                    period=period,
                    indicator="patient_visits",
                    value=int(number),
                )
            )
    return built, dropped


def _visit_row(
    entry: Entry,
    receipt: Mapping[str, object],
    *,
    venue_key: str,
    venue_kind: str,
    name_en: str,
    name_ar: str | None,
    region: str | None,
    place_id: str | None,
    period: str,
    indicator: str,
    value: int,
) -> dict[str, object]:
    require_closed(
        indicator, frozenset({"visitors", "patient_visits"}), "unknown_indicator"
    )
    require_closed(
        venue_kind,
        frozenset({"museum_or_exhibition", "health_centre"}),
        "unknown_indicator",
    )
    return attach_lineage(
        {
            "venue_key": venue_key,
            "venue_kind": venue_kind,
            "name_en": name_en,
            "name_ar": name_ar,
            "region": region,
            "place_id": place_id,
            "indicator": indicator,
            "value": value,
            "unit": "visits",
        },
        source_key=entry.key,
        publisher=entry.publisher,
        licence_id=entry.licence_id,
        licence_basis=entry.licence_basis,
        retrieved_utc=receipt_text(receipt, "retrieved_utc"),
        sha256=receipt_text(receipt, "sha256"),
        period=period,
        method=f"eii_custodian.publicdata.additions.property_venues.parse_visits@{METHOD_VERSION}",
    )


def _prepare_property_rows(
    raw: list[dict[str, object]],
    names: list[dict[str, str]],
    districts: list[dict[str, str]],
    known: set[str],
    unit_types: dict[str, str],
) -> tuple[list[dict[str, object]], list[Coverage]]:
    ambiguous = _ambiguous_districts(raw, names)
    prepared: list[dict[str, object]] = []
    counts: dict[str, int] = defaultdict(int)
    for row in raw:
        municipality = _municipality(row, names)
        english = _text(row, "district_name")
        if english in ambiguous:
            counts["ambiguous_district"] += 1
            continue
        district = _district(english, _text(row, "sm_lmntq"), districts, known, counts)
        if district is None:
            continue
        unit = unit_types.get(_text(row, "property_type"))
        if unit is None:
            raise AdditionError("unmapped_unit_type")
        price = row.get("price_per_square_meter")
        area = row.get("area_square_meters")
        if (
            not isinstance(price, int)
            or not isinstance(area, int)
            or isinstance(price, bool)
        ):
            raise AdditionError("measure_unparsed")
        if price <= 0 or area <= 0:
            counts["nonpositive_price"] += 1
            continue
        prepared.append(
            {
                "district_key": district,
                "municipality_code": municipality,
                "period": parse_period_value(row.get("registration_date"), "date")[:7],
                "unit_type": unit,
                "price_per_square_meter": price,
                "_deal": _text(row, "encrypted_transaction_number"),
            }
        )
    blocked = [Coverage(reason, count) for reason, count in sorted(counts.items())]
    return prepared, blocked


def _deals(
    rows: list[dict[str, object]],
) -> tuple[dict[tuple[str, str, str, str], list[int]], int]:
    """One price per transaction number inside a district, month and unit type."""
    buckets: dict[tuple[str, str, str, str], dict[str, set[int]]] = defaultdict(
        lambda: defaultdict(set)
    )
    for row in rows:
        deal = row["_deal"]
        if not isinstance(deal, str):
            raise AdditionError("measure_unparsed")
        key = (
            str(row["district_key"]),
            str(row["municipality_code"]),
            str(row["period"]),
            str(row["unit_type"]),
        )
        price = row["price_per_square_meter"]
        if not isinstance(price, int):
            raise AdditionError("measure_unparsed")
        buckets[key][deal].add(price)
    kept: dict[tuple[str, str, str, str], list[int]] = {}
    blocked = 0
    for key, deals in buckets.items():
        prices: list[int] = []
        for values in deals.values():
            if len(values) != 1:
                blocked += 1
                continue
            prices.append(next(iter(values)))
        kept[key] = prices
    return kept, blocked


def _aggregate_property(
    entry: Entry,
    receipt: Mapping[str, object],
    grouped: dict[tuple[str, str, str, str], list[int]],
) -> tuple[dict[str, object], ...]:
    rows: list[dict[str, object]] = []
    for key, prices in sorted(grouped.items()):
        if not prices:
            continue
        district, municipality, period, unit = key
        rows.append(
            attach_lineage(
                {
                    "district_key": district,
                    "municipality_code": municipality,
                    "unit_type": unit,
                    "deal_count": len(prices),
                    "median_price": _median(prices),
                    "price_basis": "per_m2",
                },
                source_key=entry.key,
                publisher=entry.publisher,
                licence_id=entry.licence_id,
                licence_basis=entry.licence_basis,
                retrieved_utc=receipt_text(receipt, "retrieved_utc"),
                sha256=receipt_text(receipt, "sha256"),
                period=period,
                method=(
                    "eii_custodian.publicdata.additions.property_venues.parse_property"
                    f"@{METHOD_VERSION}"
                ),
            )
        )
    return tuple(rows)


def _median(prices: list[int]) -> Decimal:
    ordered = sorted(prices)
    count = len(ordered)
    if count % 2 == 1:
        span = Decimal(ordered[count // 2])
    else:
        span = Decimal(ordered[count // 2 - 1] + ordered[count // 2])
    precision = _working_precision(span, places=2, carry=0)
    with localcontext(Context(prec=precision, rounding=ROUND_HALF_UP)):
        if count % 2 == 1:
            value = Decimal(ordered[count // 2])
        else:
            left = Decimal(ordered[count // 2 - 1])
            right = Decimal(ordered[count // 2])
            value = (left + right) / Decimal(2)
        return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _working_precision(number: Decimal, *, places: int, carry: int) -> int:
    """Precision that holds this number at the target scale without a second rounding."""
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


def _ambiguous_districts(
    raw: list[dict[str, object]], names: list[dict[str, str]]
) -> set[str]:
    seen: dict[str, set[str]] = defaultdict(set)
    for row in raw:
        seen[_text(row, "district_name")].add(_municipality(row, names))
    return {name for name, codes in seen.items() if len(codes) > 1}


def _municipality(row: Mapping[str, object], names: list[dict[str, str]]) -> str:
    try:
        english = municipality_key(_text(row, "municipality_name"), names)
        arabic = municipality_key(_text(row, "sm_lbldy"), names)
    except FrameError:
        raise AdditionError("unmapped_municipality") from None
    if english != arabic:
        raise AdditionError("municipality_disagreement")
    return english


def _district(
    english: str,
    arabic: str,
    districts: list[dict[str, str]],
    known: set[str],
    counts: dict[str, int],
) -> str | None:
    try:
        english_keys, english_error = district_keys(english, districts, known)
        arabic_keys, arabic_error = district_keys(arabic, districts, known)
    except FrameError:
        raise AdditionError("district_crosswalk") from None
    if english_error is not None or arabic_error is not None:
        counts["unmatched_district"] += 1
        return None
    if english_keys != arabic_keys:
        counts["district_disagreement"] += 1
        return None
    if len(english_keys) != 1:
        counts["district_key_not_singular"] += 1
        return None
    return english_keys[0]


def _venue(
    links: tuple[dict[str, str], ...], source_key: str, published_name: str
) -> dict[str, str]:
    matches = [
        row
        for row in links
        if row["source_key"] == source_key and row["published_name"] == published_name
    ]
    if not matches:
        raise AdditionError("unmapped_venue_name")
    if len(matches) != 1:
        raise AdditionError("venue_crosswalk_conflict")
    return matches[0]


def _one_place(english: str, arabic: str) -> str | None:
    filled = {value for value in (english, arabic) if value != ""}
    if len(filled) > 1:
        raise AdditionError("venue_place_conflict")
    if not filled:
        return None
    return next(iter(filled))


def _month_period(row: Mapping[str, object]) -> str:
    rule = parse_period_rule(
        "sit=row;form=year_text_and_month_name;field=year;month=month"
    )
    first, last = observe_period_bounds([dict(row)], rule)
    if first != last:
        raise AdditionError("period_form")
    return first


def _bounds(entry: Entry, raw: list[dict[str, object]]) -> tuple[str, str]:
    rule = parse_period_rule(entry.period_field)
    if rule.field == "to_be_confirmed":
        raise AdditionError("period_field_unconfirmed")
    return observe_period_bounds(list(raw), rule)


def _refuse_unknown_fields(entry: Entry, raw: list[dict[str, object]]) -> None:
    declared = {name for name, _kind in entry.columns}
    for row in raw:
        if set(row) - declared:
            raise AdditionError("unknown_source_field")


def _identifier_values(raw: list[dict[str, object]]) -> frozenset[str]:
    found: list[str] = []
    for row in raw:
        for field in IDENTIFIER_FIELDS:
            value = row.get(field)
            if isinstance(value, str) and value != "":
                found.append(value)
    return frozenset(found)


def _refuse_identifier_text(text: str, identifiers: frozenset[str]) -> None:
    for identifier in identifiers:
        if identifier in text:
            raise AdditionError("identifier_leak")
    for name in IDENTIFIER_FIELDS:
        if name in text:
            raise AdditionError("identifier_leak")


def _unit_types(field_map: Mapping[str, object]) -> dict[str, str]:
    value = field_map.get("unit_types")
    if not isinstance(value, dict) or not value:
        raise AdditionError("field_map_unreadable")
    mapped: dict[str, str] = {}
    for published, key in value.items():
        if not isinstance(published, str) or not isinstance(key, str):
            raise AdditionError("field_map_unreadable")
        mapped[published] = key
    return mapped


def _municipality_rows(crosswalks: Mapping[str, object]) -> list[dict[str, str]]:
    review = crosswalks.get("frame")
    from pathlib import Path

    if not isinstance(review, Path):
        raise AdditionError("crosswalk_missing")
    rows = read_csv(review / "municipality_names.csv")
    known = {row["municipality_code"] for row in rows}
    return load_municipality_names(review, known)


def _district_rows(crosswalks: Mapping[str, object]) -> list[dict[str, str]]:
    review = crosswalks.get("frame")
    from pathlib import Path

    if not isinstance(review, Path):
        raise AdditionError("crosswalk_missing")
    return read_csv(review / "district_crosswalk.csv")


def _known_districts(rows: list[dict[str, str]]) -> set[str]:
    known: set[str] = set()
    for row in rows:
        for key in row["district_keys"].split(";"):
            if key != "":
                known.add(key)
    return known


def _missing_measure(
    field_map: Mapping[str, object], key: str
) -> tuple[str, frozenset[str]]:
    block = field_map.get("missing_measures")
    if not isinstance(block, dict):
        raise AdditionError("field_map_unreadable")
    item = block.get(key)
    if not isinstance(item, dict):
        raise AdditionError("field_map_unreadable")
    field = item.get("field")
    forms = item.get("forms")
    if (
        not isinstance(field, str)
        or not field
        or not isinstance(forms, list)
        or not all(isinstance(form, str) for form in forms)
    ):
        raise AdditionError("field_map_unreadable")
    return field, frozenset(form for form in forms if isinstance(form, str))


def _text(row: Mapping[str, object], field: str) -> str:
    value = row.get(field)
    if not isinstance(value, str):
        raise AdditionError("measure_unparsed")
    return value


def _reviewed_on(value: str) -> bool:
    return parse_period_value(value, "date") == value


def _merge_coverage(
    blocked: list[Coverage], extra: tuple[Coverage, ...]
) -> tuple[Coverage, ...]:
    counts: dict[str, int] = {}
    for item in (*blocked, *extra):
        counts[item.reason] = counts.get(item.reason, 0) + item.count
    return tuple(Coverage(reason, count) for reason, count in sorted(counts.items()))
