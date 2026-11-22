"""Annual per-square-metre sale aggregates of card C14 (MTH-50)."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable

from eii_custodian.publicdata.property.bulletin import Deal
from eii_custodian.publicdata.property.quarter import _median


def sale_aggregates(deals: Iterable[Deal]) -> tuple[dict[str, object], ...]:
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
        prices = [deal.price for deal in cells[cell] if deal.price is not None]
        rows.append(
            {
                "district_key": cell[0],
                "municipality_code": cell[1],
                "period": cell[2],
                "property_type": cell[3],
                "deal_count": len(prices),
                "median_price_per_m2": _median(prices) if prices else None,
            }
        )
    return tuple(rows)
