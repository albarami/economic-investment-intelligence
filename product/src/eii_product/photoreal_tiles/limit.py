"""OPS-74 budget journal. Missing state never means a fresh budget.

The journal is outside releases and stores. A pending record is synced before
sending; an interrupted exchange disables the mode rather than forgetting cost.
No API creates, truncates or restores this file.
"""

from __future__ import annotations

import fcntl
import json
import os
from collections.abc import Callable
from decimal import Decimal
from pathlib import Path
from threading import RLock
from typing import TextIO, TypedDict, TypeVar

from eii_core.reasons import closed_code, reason

T = TypeVar("T")
LOCK = RLock()
COUNT_PATH = Path(__file__).resolve().parents[4] / "data" / "photoreal-count.log"
SPEND_CEILING_USD = Decimal("20")
WARNING_FRACTION = Decimal("0.80")


class SpendMeter(TypedDict):
    billable_requests: int
    request_limit: int
    spend_usd: str
    warning: bool
    ceiling_usd: str
    price_per_thousand_usd: str
    method_version: str
    default_price_retrieved_on: str


class BudgetFailure(Exception):
    """Closed refusal; no provider details."""


class JournalStep:
    """Count of the append that is still inside the journal lock."""

    def __init__(self) -> None:
        self.count: int | None = None


def journal_order_token(count: int) -> str:
    """Canonical decimal of one journal step. Not a displayed spend figure."""
    if count < 0:
        raise BudgetFailure("count_unavailable")
    return str(count)


def meter_for_count(count: int, limit: int, price: Decimal) -> SpendMeter:
    """Exact server-only money and warning for one already-read count."""
    return {
        "billable_requests": count,
        "request_limit": limit,
        "spend_usd": format(Decimal(count) * price / 1000, "f"),
        "warning": Decimal(count) >= Decimal(limit) * WARNING_FRACTION,
        "ceiling_usd": format(SPEND_CEILING_USD, "f"),
        "price_per_thousand_usd": format(price, "f"),
        "method_version": "1",
        # Default price reading recorded in document 04, tiles3d_google.
        # This is not a retrieval claim about an operator override.
        "default_price_retrieved_on": "2026-11-13",
    }


class BillableFailure(Exception):
    """A known successful provider status whose response could not be consumed."""

    def __init__(self, diagnostic: str = "response_unavailable") -> None:
        super().__init__(closed_code(diagnostic, "response_unavailable"))


def encode_spend_meter(meter: SpendMeter) -> str:
    """One-line ASCII header value of a server meter. No second calculation."""
    return json.dumps(meter, ensure_ascii=True, separators=(",", ":"), sort_keys=True)


def billable_limit(price: Decimal) -> int:
    """Named absolute spend ceiling, ignoring the free allowance."""
    if not price.is_finite() or price <= 0:
        raise BudgetFailure("count_unavailable")
    return int(SPEND_CEILING_USD * 1000 / max(price, Decimal(6)))


class Budget:
    """Serialize check, provider exchange and append across threads/processes."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._seen = ""
        self._broken = False

    def _read(self, stream: TextIO) -> int:
        raw = stream.read()
        if self._broken or not raw.startswith(self._seen) or not raw.endswith("\n"):
            raise BudgetFailure("count_unavailable")
        lines = raw.splitlines()
        if not lines or lines[0] != "ready:0":
            raise BudgetFailure("count_unavailable")
        count = 0
        pending = False
        for line in lines[1:]:
            kind, sep, value = line.partition(":")
            if not sep or not value.isascii() or not value.isdecimal():
                raise BudgetFailure("count_unavailable")
            next_count = int(value)
            if not pending and kind == "pending" and next_count == count:
                pending = True
            elif pending and kind == "ready" and next_count in (count, count + 1):
                pending = False
                count = next_count
            else:
                raise BudgetFailure("count_unavailable")
        if pending:
            raise BudgetFailure("count_unavailable")
        self._seen = raw
        return count

    def _append(self, stream: TextIO, line: str) -> None:
        stream.write(line)
        stream.flush()
        os.fsync(stream.fileno())
        self._seen += line

    def count(self) -> int:
        """Read the durable count without changing or initializing the journal."""
        with LOCK:
            try:
                with self.path.open("r+", encoding="ascii") as stream:
                    fcntl.flock(stream, fcntl.LOCK_EX)
                    return self._read(stream)
            except (OSError, UnicodeError, ValueError) as error:
                raise BudgetFailure(reason(error, "count_unavailable")) from None

    def available(self, limit: int) -> None:
        if self.count() >= limit:
            raise BudgetFailure("cap_reached")

    def meter(self, limit: int, price: Decimal) -> SpendMeter:
        """Exact server-only money and warning; never a limit on view detail."""
        return meter_for_count(self.count(), limit, price)

    def request(
        self,
        limit: int,
        send: Callable[[], T],
        billable: Callable[[T], bool],
        step: JournalStep | None = None,
    ) -> T:
        with LOCK:
            try:
                with self.path.open("r+", encoding="ascii") as stream:
                    fcntl.flock(stream, fcntl.LOCK_EX)
                    count = self._read(stream)
                    if count >= limit:
                        raise BudgetFailure("cap_reached")
                    self._append(stream, f"pending:{count}\n")
                    try:
                        result = send()
                    except BillableFailure as error:
                        self._append(stream, f"ready:{count + 1}\n")
                        raise BudgetFailure(
                            reason(error, "response_unavailable")
                        ) from None
                    appended = count + int(billable(result))
                    self._append(stream, f"ready:{appended}\n")
                    if step is not None:
                        step.count = appended
                    return result
            except BudgetFailure:
                raise
            except Exception as error:
                self._broken = True
                raise BudgetFailure(reason(error, "count_unavailable")) from None
