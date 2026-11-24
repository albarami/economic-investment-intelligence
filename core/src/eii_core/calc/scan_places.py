"""Deterministic Public place comparisons and units (BE-104; brief B2)."""

from collections.abc import Mapping, Sequence
from datetime import date
from decimal import Decimal
from typing import cast


def number(value: object) -> Decimal:
    """Strict finite numeric source cell, never a coercible text or boolean."""
    if type(value) not in (int, float, Decimal):
        raise ValueError("number_invalid")
    result = Decimal(str(value))
    if not result.is_finite() or result < 0:
        raise ValueError("number_invalid")
    return result


def confidence_passes(value: object) -> bool:
    """PUB-48: include the threshold itself."""
    confidence = number(value)
    if confidence > 1:
        raise ValueError("confidence_invalid")
    return confidence >= Decimal("0.7")


def canonical_number(value: object) -> Decimal:
    """Remove representational trailing zeros without decimal-context rounding."""
    parts = number(value).as_tuple()
    digits = list(parts.digits)
    exponent = cast(int, parts.exponent)
    while digits and digits[-1] == 0:
        digits.pop()
        exponent += 1
    if not digits:
        return Decimal(0)
    return Decimal((parts.sign, tuple(digits), exponent))


def latest_verification[Row: Mapping[str, object]](rows: Sequence[Row]) -> Row | None:
    """Latest check governs; duplicate governing dates are release defects."""
    if not rows:
        return None
    if any(type(row.get("check_date")) is not date for row in rows):
        raise ValueError("check_date_invalid")
    ordered = sorted(rows, key=lambda row: cast(date, row["check_date"]), reverse=True)
    if len(ordered) > 1 and ordered[0]["check_date"] == ordered[1]["check_date"]:
        raise ValueError("verification_ambiguous")
    return ordered[0]


def validate_limit(limit: object) -> int:
    """Accept the closed request range without coercion."""
    if type(limit) is not int or not 1 <= limit <= 50:
        raise ValueError("limit_invalid")
    return limit


def _identifier(row: Mapping[str, object], key: str) -> str:
    value = row[key]
    if type(value) is not str or not value:
        raise ValueError("identifier_invalid")
    return value


def order_places[Row: Mapping[str, object]](
    rows: Sequence[Row], limit: object
) -> list[Row]:
    """Ascending unrounded distance, total identifier tie break, then limit."""
    accepted = validate_limit(limit)
    return sorted(
        rows, key=lambda row: (number(row["distance"]), _identifier(row, "place_id"))
    )[:accepted]


def route_metres(value: object, unit: str) -> Decimal | None:
    """Exact kilometre conversion; null explicitly means unreachable."""
    if unit != "kilometers":
        raise ValueError("route_unit_invalid")
    if value is None:
        return None
    parts = number(value).as_tuple()
    return Decimal((parts.sign, parts.digits, cast(int, parts.exponent) + 3))
