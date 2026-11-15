"""Kept deals of the two sales bulletins for card C41 (PUB-107).

A deal is one distinct transaction number: rows of one number whose measures
agree count once, and rows that disagree block the deal with a named reason so
it enters no aggregate. Transaction and parcel numbers stay inside the build
as join keys and never reach a release row (PUB-14, DR1). Property type and
use come from the Arabic label and the usage field through the reviewed use
map; the English label is never read. Kept deals are those card C14 keeps: a
crosswalk-matched district, a positive price, and a positive floor area for
every ``prop_sales`` deal and for the ``prop_resi_units`` deals of price basis
``per_m2``. A district outside the reviewed crosswalk is a blocked row with a
named coverage reason, the rule ``additions/property_venues.py`` already codes.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from decimal import Decimal

from eii_custodian.publicdata.additions.common import (
    AdditionError,
    Coverage,
    MeasureKind,
    parse_period_value,
    read_measure,
)
from eii_custodian.publicdata.additions.property_venues import (
    _ambiguous_districts,
    _district,
    _district_rows,
    _identifier_values,
    _known_districts,
    _municipality,
    _municipality_rows,
    _refuse_identifier_text,
    _text,
)
from eii_custodian.publicdata.property.use_map import (
    UseMapping,
    use_lookup,
)

SQ_M_PER_SQ_FT = Decimal("0.09290304")
BULLETIN_FIELDS = frozenset(
    {
        "registration_date",
        "encrypted_transaction_number",
        "encrypted_parcel_number",
        "sm_lbldy",
        "municipality_name",
        "sm_lmntq",
        "district_name",
        "nw_l_qr",
        "property_type",
        "property_usage",
        "area_square_meters",
        "area_square_feet",
        "price_per_square_meter",
        "property_value",
    }
)


@dataclass(frozen=True)
class Deal:
    """One kept deal. ``transaction`` is a join key, never a release field."""

    source_id: str
    district_key: str
    municipality_code: str
    period: str
    use_key: str
    unit_type: str | None
    land: bool
    basis: str
    price: Decimal | None
    value: Decimal | None
    area_m2: Decimal | None
    area_ft2: Decimal | None
    transaction: str


@dataclass(frozen=True)
class BulletinDeals:
    """The kept deals, the blocked coverage and the collected identifiers."""

    deals: tuple[Deal, ...]
    blocked: tuple[Coverage, ...]
    identifiers: frozenset[str]


def quarter_of(value: object) -> str:
    """Return the calendar quarter ``YYYY-Qn`` of a row date, or fail."""
    text = parse_period_value(value, "date")
    return f"{text[:4]}-Q{(int(text[5:7]) - 1) // 3 + 1}"


def refuse_release_identifiers(
    rows: Iterable[Mapping[str, object]], identifiers: frozenset[str]
) -> None:
    """Fail when a release row carries an identifier field or value (DR1(c))."""
    _refuse_identifier_text(repr(list(rows)), identifiers)


def parse_bulletin(
    rows: object,
    use_map: Iterable[UseMapping],
    crosswalk: Mapping[str, object],
) -> BulletinDeals:
    """Return the kept deals of one or both bulletins, or fail by name."""
    if not isinstance(rows, list):
        raise AdditionError("bulletin_rows")
    if any(not isinstance(row, dict) for row in rows):
        raise AdditionError("bulletin_row")
    mappings = list(use_map)
    names = _municipality_rows(crosswalk)
    districts = _district_rows(crosswalk)
    known = _known_districts(districts)
    identifiers = _identifier_values(rows)
    ambiguous = _ambiguous_districts(rows, names)
    prepared: list[Deal] = []
    counts: dict[str, int] = defaultdict(int)
    for row in rows:
        if set(row) - BULLETIN_FIELDS:
            raise AdditionError("unknown_source_field")
        municipality = _municipality(row, names)
        english = _text(row, "district_name")
        if english in ambiguous:
            counts["ambiguous_district"] += 1
            continue
        district = _district(english, _text(row, "sm_lmntq"), districts, known, counts)
        if district is None:
            continue
        mapping = use_lookup(mappings, _text(row, "nw_l_qr"), _usage(row))
        deal = _deal(row, district, municipality, mapping)
        reason = _unkept(deal)
        if reason is None:
            prepared.append(deal)
        else:
            counts[reason] += 1
    deals, disagreements = _dedupe(prepared)
    counts["repeated_deal_price_disagreement"] += disagreements
    blocked = tuple(
        Coverage(reason, count) for reason, count in sorted(counts.items()) if count
    )
    return BulletinDeals(tuple(deals), blocked, identifiers)


def _usage(row: Mapping[str, object]) -> str:
    value = row.get("property_usage")
    if value is None:
        return ""
    if not isinstance(value, str):
        raise AdditionError("measure_unparsed")
    return value


def _measure(row: Mapping[str, object], field: str) -> Decimal | None:
    read = read_measure(row.get(field), missing_forms=frozenset(), integral=True)
    return read.number if read.kind is MeasureKind.NUMBER else None


def _deal(
    row: Mapping[str, object],
    district: str,
    municipality: str,
    mapping: UseMapping,
) -> Deal:
    """Build one candidate deal for the row's mapped source."""
    value = _measure(row, "property_value")
    area_ft2 = _measure(row, "area_square_feet")
    area_m2 = _floor_area_m2(_measure(row, "area_square_meters"), area_ft2)
    if mapping.source_id == "prop_sales":
        basis = "per_m2"
        price = value / area_m2 if value is not None and area_m2 else None
    elif mapping.source_id == "prop_resi_units":
        if area_m2 is not None:
            basis = "per_m2"
            price = _measure(row, "price_per_square_meter")
        else:
            basis, price = "per_unit", value
    else:
        raise AdditionError("use_map_source")
    return Deal(
        source_id=mapping.source_id,
        district_key=district,
        municipality_code=municipality,
        period=quarter_of(row.get("registration_date")),
        use_key=mapping.use_key,
        unit_type=mapping.unit_type,
        land=mapping.land,
        basis=basis,
        price=price,
        value=value,
        area_m2=area_m2,
        area_ft2=area_ft2,
        transaction=_text(row, "encrypted_transaction_number"),
    )


def _floor_area_m2(area_m2: Decimal | None, area_ft2: Decimal | None) -> Decimal | None:
    if area_m2 is not None and area_m2 > 0:
        return area_m2
    if area_ft2 is not None and area_ft2 > 0:
        return area_ft2 * SQ_M_PER_SQ_FT
    return None


def _unkept(deal: Deal) -> str | None:
    """The keep rule of card C14, as a coverage reason or None."""
    if deal.value is None or deal.value <= 0:
        return "nonpositive_price"
    if deal.source_id == "prop_sales" and deal.area_m2 is None:
        return "nonpositive_area"
    if deal.basis == "per_m2" and (deal.price is None or deal.price <= 0):
        return "nonpositive_price"
    if deal.basis == "per_unit" and deal.price is None:
        return "nonpositive_price"
    return None


def _dedupe(rows: list[Deal]) -> tuple[list[Deal], int]:
    """One deal per transaction number inside a quarter cell (DR3)."""
    buckets: dict[
        tuple[object, ...], dict[str, tuple[Deal, set[tuple[object, ...]]]]
    ] = defaultdict(dict)
    for deal in rows:
        cell = (
            deal.district_key,
            deal.municipality_code,
            deal.period,
            deal.use_key,
            deal.unit_type,
        )
        entry = buckets[cell].setdefault(deal.transaction, (deal, set()))
        entry[1].add((deal.basis, deal.price, deal.value, deal.area_m2, deal.area_ft2))
    kept: list[Deal] = []
    blocked = 0
    for deals in buckets.values():
        for deal, measures in deals.values():
            if len(measures) != 1:
                blocked += 1
                continue
            kept.append(deal)
    return kept, blocked
