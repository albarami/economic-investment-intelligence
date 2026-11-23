"""Annual per-square-metre sale aggregates of card C14 (MTH-50)."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping

from eii_custodian.publicdata.property.bulletin import Deal
from eii_custodian.publicdata.property.price_as_of import group_as_of, stamp_price_as_of
from eii_custodian.publicdata.property.quarter import _median


def sale_aggregates(
    deals: Iterable[Deal], *, as_of_by_source: Mapping[str, str] | None = None
) -> tuple[dict[str, object], ...]:
    """Aggregate kept prop_sales deals by district, year and reviewed use."""
    cells: dict[tuple[str, str, str, str], list[Deal]] = defaultdict(list)
    for deal in deals:
        if deal.source_id != "prop_sales":
            continue
        cell = (
            deal.district_key,
            deal.municipality_code,
            deal.period[:4],
            deal.use_key,
        )
        cells[cell].append(deal)
    rows = []
    for cell in sorted(cells):
        group = cells[cell]
        prices = [deal.price for deal in group if deal.price is not None]
        row = {
            "district_key": cell[0],
            "municipality_code": cell[1],
            "period": cell[2],
            "property_type": cell[3],
            "deal_count": len(prices),
            "median_price_per_m2": _median(prices) if prices else None,
        }
        if as_of_by_source is not None:
            row = stamp_price_as_of(row, group_as_of(group, as_of_by_source))
        rows.append(row)
    return tuple(rows)
