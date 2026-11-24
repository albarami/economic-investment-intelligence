"""OPS-74 budget journal. Missing state never means a fresh budget.

The journal is outside releases and stores. A pending record is synced before
sending; an interrupted exchange disables the mode rather than forgetting cost.
No API creates, truncates or restores this file.
"""

from __future__ import annotations

import fcntl
import os
from collections.abc import Callable
from decimal import Decimal
from pathlib import Path
from threading import RLock
from typing import TextIO, TypedDict, TypeVar

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


class BillableFailure(Exception):
    """A known successful provider status whose response could not be consumed."""

    def __init__(self) -> None:
        super().__init__("response_unavailable")


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
            except (OSError, UnicodeError, ValueError):
                raise BudgetFailure("count_unavailable") from None

    def available(self, limit: int) -> None:
        if self.count() >= limit:
            raise BudgetFailure("cap_reached")

    def meter(self, limit: int, price: Decimal) -> SpendMeter:
        """Exact server-only money and warning; never a limit on view detail."""
        count = self.count()
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

    def request(
        self, limit: int, send: Callable[[], T], billable: Callable[[T], bool]
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
                    except BillableFailure:
                        self._append(stream, f"ready:{count + 1}\n")
                        raise BudgetFailure("response_unavailable") from None
                    self._append(stream, f"ready:{count + int(billable(result))}\n")
                    return result
            except BudgetFailure:
                raise
            except Exception:
                self._broken = True
                raise BudgetFailure("count_unavailable") from None
