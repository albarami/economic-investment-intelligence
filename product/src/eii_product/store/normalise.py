"""Normalise driver scalars and compare results with no tolerance."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date, datetime
from decimal import ROUND_HALF_EVEN, Context, Decimal

from eii_product.store.protocol import (
    NormalValue,
    QueryResult,
    StoreRefusal,
    field_mismatch,
)

QUANTUM = Decimal("0.000001")
# decimal(18,2) needs 22 digits to keep 16 digits before the point and six after.
# 28 is that bound with the margin the previous quantiser used as its floor.
_QUANTISE_PRECISION = 28
_QUANTISE_EXPONENT = 999_999
_GEOMETRY_TEXT = re.compile(r"01(?:[0-9A-F]{2})*\Z")


def _quantise_context() -> Context:
    """A context this function owns. Nothing is copied from the caller."""
    return Context(
        prec=_QUANTISE_PRECISION,
        rounding=ROUND_HALF_EVEN,
        Emin=-_QUANTISE_EXPONENT,
        Emax=_QUANTISE_EXPONENT,
        capitals=1,
        clamp=0,
        flags=[],
        traps=[],
    )


def is_geometry_text(value: object) -> bool:
    """Upper-case hexadecimal ISO WKB: an even run of 0-9A-F beginning with 01."""
    return type(value) is str and _GEOMETRY_TEXT.fullmatch(value) is not None


def hold_geometry(value: object) -> str | None:
    """Keep the pinned geometry text. Convert nothing. Refuse every other value."""
    if value is None:
        return None
    if type(value) is str and is_geometry_text(value):
        return value
    raise StoreRefusal("unsupported scalar")


def normalise(value: object) -> NormalValue:
    """Apply the store rounding rule. Null stays null. Bool and bytes are refused."""
    if value is None:
        return None
    if type(value) is int:
        return value
    if isinstance(value, (Decimal, float)):
        number = Decimal(repr(value)) if isinstance(value, float) else value
        if not number.is_finite():
            raise StoreRefusal("non-finite number")
        context = _quantise_context()
        if context.compare(number, number.to_integral_value(context=context)) == 0:
            return int(number)
        return context.quantize(number, QUANTUM)
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    raise StoreRefusal("unsupported scalar")


def compare_queries(
    left_identity: str,
    left: QueryResult,
    right_identity: str,
    right: QueryResult,
) -> None:
    """Compare identity, columns, shape, order and every field exactly."""
    if left_identity != right_identity:
        raise StoreRefusal("release identity mismatch")
    if left.columns != right.columns:
        raise StoreRefusal("column mismatch")
    if len(left.rows) != len(right.rows):
        raise StoreRefusal("row count mismatch")
    for row_index, (left_row, right_row) in enumerate(
        zip(left.rows, right.rows, strict=True)
    ):
        if len(left_row) != len(left.columns) or len(right_row) != len(right.columns):
            raise StoreRefusal("row width mismatch")
        for column_index, (left_value, right_value) in enumerate(
            zip(left_row, right_row, strict=True)
        ):
            if type(left_value) is not type(right_value) or left_value != right_value:
                raise field_mismatch(row_index, column_index)


@dataclass(frozen=True)
class Fact:
    """One fact value inside a tool result. Display precision is not stored here."""

    name: str
    unit: str
    value: NormalValue


@dataclass(frozen=True)
class ToolResult:
    """A complete tool result. Engine, timing and call id are not compared."""

    engine: str
    call_id: str
    duration_ms: int
    tool: str
    status: str
    release_id: str | None
    facts: tuple[Fact, ...]


def compare_tools(
    left: ToolResult,
    right: ToolResult,
    *,
    unit_precision: Mapping[str, int],
    round_fact: Callable[[NormalValue, int], NormalValue],
) -> None:
    """Compare two tool results. Fact values are rounded by the supplied function."""
    if left.tool != right.tool:
        raise field_mismatch(0, 0)
    if left.status != right.status:
        raise field_mismatch(0, 1)
    if left.release_id != right.release_id:
        raise field_mismatch(0, 2)
    if len(left.facts) != len(right.facts):
        raise StoreRefusal("row count mismatch")
    for index, (left_fact, right_fact) in enumerate(
        zip(left.facts, right.facts, strict=True)
    ):
        if left_fact.unit not in unit_precision:
            raise StoreRefusal("fact precision missing")
        if right_fact.unit not in unit_precision:
            raise StoreRefusal("fact precision missing")
        if left_fact.name != right_fact.name:
            raise field_mismatch(index, 0)
        if left_fact.unit != right_fact.unit:
            raise field_mismatch(index, 1)
        places = unit_precision[left_fact.unit]
        left_value = _rounded(left_fact.value, places, round_fact)
        right_value = _rounded(right_fact.value, places, round_fact)
        if type(left_value) is not type(right_value) or left_value != right_value:
            raise field_mismatch(index, 2)


def _rounded(
    value: NormalValue,
    places: int,
    round_fact: Callable[[NormalValue, int], NormalValue],
) -> NormalValue:
    if type(value) is int or type(value) is Decimal:
        return round_fact(value, places)
    return value
