"""BE-20 to BE-24 normalisation and exact, ordered S1-T05 result comparison.

The decimal control is a parity probe, not a released primitive or display fact.
Released integer primitives never receive a tolerance.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from datetime import date, datetime
from decimal import ROUND_HALF_EVEN, Decimal, localcontext

type NormalValue = int | Decimal | str | date | None
QUANTUM = Decimal("0.000001")


class SpikeRefusal(ValueError):
    """A fixed diagnostic safe to print without driver details or caller values."""


class ParityMismatch(SpikeRefusal):
    """The complete ordered outputs differ."""


@dataclass(frozen=True)
class QueryResult:
    fixture_id: str
    columns: tuple[str, ...]
    rows: tuple[tuple[NormalValue, ...], ...]


def normalise(value: object) -> NormalValue:
    """Normalise supported driver scalars; refuse unsupported or non-finite values."""
    if value is None:
        return None
    if type(value) is int:
        return value
    if isinstance(value, (Decimal, float)):
        number = Decimal(repr(value)) if isinstance(value, float) else value
        if not number.is_finite():
            raise SpikeRefusal("non-finite number")
        if number == number.to_integral_value():
            return int(number)
        with localcontext() as context:
            context.prec = max(28, len(number.as_tuple().digits), number.adjusted() + 8)
            return number.quantize(QUANTUM, rounding=ROUND_HALF_EVEN)
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    raise SpikeRefusal("unsupported scalar")


def compare(left: QueryResult, right: QueryResult) -> None:
    """Compare identity, columns, dimensions, types, order and every field exactly."""
    if left.fixture_id != right.fixture_id:
        raise ParityMismatch("fixture identity mismatch")
    if left.columns != right.columns:
        raise ParityMismatch("column mismatch")
    if len(left.rows) != len(right.rows):
        raise ParityMismatch("row count mismatch")
    for row_index, (a, b) in enumerate(zip(left.rows, right.rows, strict=True)):
        if len(a) != len(left.columns) or len(b) != len(right.columns):
            raise ParityMismatch("row width mismatch")
        for column_index, (x, y) in enumerate(zip(a, b, strict=True)):
            if type(x) is not type(y) or x != y:
                # Positions only: even unexpected column names and values stay private.
                raise ParityMismatch(
                    f"field mismatch row={row_index} column={column_index}"
                )
