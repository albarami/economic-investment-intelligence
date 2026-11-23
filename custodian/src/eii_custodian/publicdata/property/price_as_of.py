"""Snapshot-dated ``as_of`` on property price release rows."""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from eii_custodian.publicdata.additions.common import AdditionError
from eii_custodian.publicdata.fetch.snapshots import utc
from eii_custodian.publicdata.property.bulletin import Deal

PRICE_MEASURES = frozenset(
    {
        "median_price",
        "guide_price",
        "deal_value",
        "median_price_per_ft2",
        "median_price_per_m2",
        "land_median_price_per_ft2",
    }
)


def as_of_from_receipt(receipt: Mapping[str, object]) -> str:
    """Return the ISO date of one named snapshot's ``retrieved_utc``."""
    return utc(receipt["retrieved_utc"]).date().isoformat()


def row_has_price_figure(row: Mapping[str, object]) -> bool:
    """True when the row carries a non-null price measure."""
    return any(
        row.get(name) is not None and row.get(name) != "" for name in PRICE_MEASURES
    )


def require_price_as_of(row: Mapping[str, object], expected: str) -> None:
    """Refuse a price row whose ``as_of`` is absent or not the named snapshot."""
    value = row.get("as_of")
    if not isinstance(value, str) or not value or value != expected:
        raise AdditionError("price_as_of_missing")


def require_rows_price_as_of(rows: Iterable[Mapping[str, object]]) -> None:
    """Refuse any price row that lacks a non-empty ``as_of``."""
    for row in rows:
        if row_has_price_figure(row):
            value = row.get("as_of")
            if not isinstance(value, str) or not value:
                raise AdditionError("price_as_of_missing")


def require_rows_match_sources(
    rows: Iterable[Mapping[str, object]],
    as_of_by_source: Mapping[str, str],
) -> None:
    """Refuse a price row whose ``as_of`` is absent or not from its snapshots."""
    allowed = set(as_of_by_source.values())
    require_rows_price_as_of(rows)
    for row in rows:
        if row_has_price_figure(row):
            value = row.get("as_of")
            if not isinstance(value, str) or value not in allowed:
                raise AdditionError("price_as_of_missing")


def group_as_of(deals: Iterable[Deal], as_of_by_source: Mapping[str, str]) -> str:
    """One ``as_of`` for a deal group; refuse unlike snapshot dates."""
    stamps = {as_of_by_source[deal.source_id] for deal in deals}
    if len(stamps) != 1:
        raise AdditionError("price_as_of_mismatch")
    return next(iter(stamps))


def stamp_price_as_of(row: dict[str, object], as_of: str) -> dict[str, object]:
    """Copy a row and attach the snapshot date when it carries a price measure."""
    stamped = dict(row)
    if row_has_price_figure(row):
        stamped["as_of"] = as_of
    return stamped
