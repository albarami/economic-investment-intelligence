"""The pure aggregates of ``pub_property_quarter`` (card C41, PUB-107).

The deals of the two sales bulletins share one row keyed as section 7.3 of
document 03 states — the key holds no ``source_id`` (DR2). The formula is the
card's: a price per square foot is the deal's price in QAR over its floor
area in square feet, the area converted by the exact factor ``0.09290304`` or
taken as the source's own square feet where it gives them; the median of an
even count is the mean of the two central values. The per-square-foot median
takes every kept ``prop_sales`` deal and only the ``prop_resi_units`` deals of
price basis ``per_m2``; a ``per_unit`` deal carries no floor area and gives no
price per square foot. ``deal_count`` is the kept deals and ``deal_value``
their price sum (MTH-116, MTH-117). A row refuses mixed price bases.
"""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Iterable, Mapping
from decimal import ROUND_HALF_UP, Decimal

from eii_custodian.publicdata.additions.common import AdditionError
from eii_custodian.publicdata.property.bulletin import SQ_M_PER_SQ_FT, Deal
from eii_custodian.publicdata.property.price_as_of import group_as_of, stamp_price_as_of

_CENT = Decimal("0.01")
_QUARTER = re.compile(r"^(\d{4})-Q([1-4])$")
QUARTER_COLUMNS = (
    "district_key",
    "municipality_code",
    "period",
    "use_key",
    "unit_type",
    "deal_count",
    "deal_value",
    "median_price_per_ft2",
    "land_deal_count",
    "land_median_price_per_ft2",
    "median_price",
    "price_basis",
    "as_of",
)


def square_feet(area_m2: Decimal) -> Decimal:
    """Square metres to square feet by the card's exact factor."""
    return (area_m2 / SQ_M_PER_SQ_FT).quantize(_CENT, rounding=ROUND_HALF_UP)


def quarter_aggregates(
    deals: Iterable[Deal],
    *,
    as_of_by_source: Mapping[str, str] | None = None,
) -> tuple[dict[str, object], ...]:
    """Return the ``pub_property_quarter`` rows over the kept deals."""
    cells: dict[tuple[str, ...], list[Deal]] = defaultdict(list)
    units: dict[tuple[str, ...], list[Deal]] = defaultdict(list)
    for deal in deals:
        cell = (
            deal.district_key,
            deal.municipality_code,
            deal.period,
            deal.use_key,
        )
        cells[cell].append(deal)
        if deal.unit_type is not None:
            units[(*cell, deal.unit_type)].append(deal)
    rows: list[dict[str, object]] = []
    for all_cell, group in cells.items():
        prices = [p for p in map(_square_foot_price, group) if p is not None]
        land = [deal for deal in group if deal.land]
        land_prices = [p for p in map(_square_foot_price, land) if p is not None]
        built = _row(
            all_cell,
            "all",
            len(group),
            _sum(group),
            median_price_per_ft2=_median(prices) if prices else None,
            land_deal_count=len(land),
            land_median_price_per_ft2=(_median(land_prices) if land_prices else None),
        )
        if as_of_by_source is not None:
            built = stamp_price_as_of(built, group_as_of(group, as_of_by_source))
        rows.append(built)
    for unit_cell, group in units.items():
        bases = {deal.basis for deal in group}
        if len(bases) != 1:
            raise AdditionError("mixed_price_basis")
        prices = [deal.price for deal in group if deal.price is not None]
        built = _row(
            unit_cell[:-1],
            unit_cell[-1],
            len(group),
            _sum(group),
            median_price=(_median(prices) if len(prices) == len(group) else None),
            price_basis=next(iter(bases)),
        )
        if as_of_by_source is not None:
            built = stamp_price_as_of(built, group_as_of(group, as_of_by_source))
        rows.append(built)
    return tuple(
        sorted(
            rows,
            key=lambda row: (
                str(row["district_key"]),
                str(row["municipality_code"]),
                str(row["period"]),
                str(row["use_key"]),
                str(row["unit_type"]),
            ),
        )
    )


def forecast_window(quarters: Iterable[str]) -> tuple[str, str, int] | None:
    """The trailing contiguous run of quarters with a kept value (C30, DR11).

    A quarter with no kept deal has no value, so the quarters before it are
    not used: the window is the run of consecutive quarters that ends at the
    last quarter. Returns ``(first, last, past_count)`` or None when empty.
    """
    seen = {_quarter_index(quarter): quarter for quarter in quarters}
    if not seen:
        return None
    ordered = sorted(seen)
    run = [ordered[-1]]
    for index in reversed(ordered[:-1]):
        if index != run[0] - 1:
            break
        run.insert(0, index)
    return seen[run[0]], seen[run[-1]], len(run)


def held_series_window(
    period: str, past_count: int, quarters: Iterable[str]
) -> tuple[str, str, int]:
    """Refuse a held forecast entry whose window is not the kept-quarter window.

    A held ``property_prices_quarterly`` entry may state only the trailing
    contiguous run of quarters with a kept deal: its ``period`` bounds and
    ``past_count`` equal ``forecast_window`` of those quarters (J27).
    """
    window = forecast_window(quarters)
    first, _, last = period.partition("/")
    if window is None or window != (first, last, past_count):
        raise AdditionError("held_window_mismatch")
    return window


def _quarter_index(quarter: object) -> int:
    if not isinstance(quarter, str):
        raise AdditionError("quarter_period")
    match = _QUARTER.fullmatch(quarter)
    if match is None:
        raise AdditionError("quarter_period")
    return int(match.group(1)) * 4 + int(match.group(2))


def _row(
    cell: tuple[str, ...],
    unit_type: str,
    deal_count: int,
    deal_value: Decimal,
    **measures: object,
) -> dict[str, object]:
    row: dict[str, object] = {
        "district_key": cell[0],
        "municipality_code": cell[1],
        "period": cell[2],
        "use_key": cell[3],
        "unit_type": unit_type,
        "deal_count": deal_count,
        "deal_value": deal_value,
        "median_price_per_ft2": None,
        "land_deal_count": None,
        "land_median_price_per_ft2": None,
        "median_price": None,
        "price_basis": None,
    }
    row.update(measures)
    return row


def _sum(group: list[Deal]) -> Decimal:
    total = sum((deal.value for deal in group if deal.value is not None), Decimal(0))
    return total.quantize(_CENT, rounding=ROUND_HALF_UP)


def _median(values: list[Decimal]) -> Decimal:
    ordered = sorted(values)
    count = len(ordered)
    if count % 2 == 1:
        value = Decimal(ordered[count // 2])
    else:
        left = Decimal(ordered[count // 2 - 1])
        right = Decimal(ordered[count // 2])
        value = (left + right) / Decimal(2)
    return value.quantize(_CENT, rounding=ROUND_HALF_UP)


def _square_foot_price(deal: Deal) -> Decimal | None:
    """The deal's price per square foot, or None when it carries none."""
    if deal.value is None or deal.value <= 0:
        return None
    if deal.source_id != "prop_sales" and deal.basis != "per_m2":
        return None
    if deal.area_ft2 is not None and deal.area_ft2 > 0:
        return deal.value / deal.area_ft2
    if deal.area_m2 is not None and deal.area_m2 > 0:
        return deal.value * SQ_M_PER_SQ_FT / deal.area_m2
    return None
