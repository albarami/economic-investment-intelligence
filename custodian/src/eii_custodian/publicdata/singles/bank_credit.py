"""Banks' credit by economic activity. National rows; the modified date is not a period."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal

from eii_custodian.publicdata.singles.tenders import pattern_class

_COLUMNS = ("year", "economic_activity", "lnsht_lqtsdy", "value")
_VALUE = re.compile(r"\A[0-9]+(?:\.[0-9]{1,2})?\Z")
_CENTS = Decimal("0.01")


class CreditError(Exception):
    """The credit table is not the published shape. Nothing is returned."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


@dataclass(frozen=True)
class CreditRow:
    """One pub_bank_credit row. No area figure."""

    activity_key: str
    period: str
    value: Decimal
    unit: str | None


def parse_bank_credit(rows: Sequence[Mapping[str, object]]) -> tuple[CreditRow, ...]:
    """Return typed national credit rows, or raise with nothing loaded."""
    parsed: list[CreditRow] = []
    for row in rows:
        if set(row) != set(_COLUMNS):
            raise CreditError("unexpected_column")
        activity = row["economic_activity"]
        year = row["year"]
        if not isinstance(activity, str) or activity.strip() == "":
            raise CreditError("activity")
        if not isinstance(year, str) or year.strip() == "":
            raise CreditError("year")
        if not isinstance(row["lnsht_lqtsdy"], str):
            raise CreditError("activity")
        parsed.append(
            CreditRow(activity.strip(), year.strip(), _value(row["value"]), None)
        )
    return tuple(parsed)


def credit_period_bounds(
    rows: Sequence[Mapping[str, object]], *, modified: str | None = None
) -> tuple[str | None, str | None]:
    """First and last year. A modified date is provenance and does not extend them."""
    if modified is not None and modified.strip() == "" and not rows:
        return None, None
    periods = sorted(
        str(row["year"]) for row in rows if isinstance(row.get("year"), str)
    )
    if not periods:
        return None, None
    return periods[0], periods[-1]


def _value(raw: object) -> Decimal:
    if isinstance(raw, bool):
        raise CreditError("value")
    if isinstance(raw, int):
        return Decimal(raw).quantize(_CENTS)
    if isinstance(raw, str) and _VALUE.fullmatch(raw.strip()):
        return Decimal(raw.strip()).quantize(_CENTS)
    shown = raw if isinstance(raw, str) else ""
    if shown.strip() == "":
        raise CreditError("value")
    raise CreditError(f"value {pattern_class(shown.strip())}")
