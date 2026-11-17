"""Pure request and matching rules of decision 0031 items 5 and 6.

The future transport caller reserves credits immediately before each send.
Reservation is deliberately not refundable: a failed request is never retried.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping

LIMIT_VARIABLE = "EII_BESTTIME_RUN_CREDIT_LIMIT"


def run_limit(environ: Mapping[str, str]) -> int:
    """Read the positive whole-number limit; never echo its value."""
    value = environ.get(LIMIT_VARIABLE, "")
    if re.fullmatch(r"[0-9]+", value) is None:
        raise ValueError(f"{LIMIT_VARIABLE}: expected positive whole number")
    limit = int(value)
    if limit <= 0:
        raise ValueError(f"{LIMIT_VARIABLE}: expected positive whole number")
    return limit


class CreditBudget:
    """A run's one-shot reservations; an over-limit request closes the run."""

    def __init__(self, limit: int) -> None:
        if type(limit) is not int or limit <= 0:
            raise ValueError("credit limit: expected positive integer")
        self.limit = limit
        self.used = 0
        self.stopped = False
        self.sent: set[tuple[str, str]] = set()

    def reserve(self, place_id: str, kind: str, cost: int) -> bool:
        """Reserve once before sending, or stop permanently before overspending."""
        if type(cost) is not int or cost <= 0:
            raise ValueError("request cost: expected positive integer")
        if kind not in {"forecast", "query"}:
            raise ValueError("unknown request kind")
        if (place_id, kind) in self.sent:
            raise ValueError("duplicate request")
        if kind == "query" and (place_id, "forecast") not in self.sent:
            raise ValueError("query before forecast")
        if self.stopped:
            return False
        if self.used + cost > self.limit:
            self.stopped = True
            return False
        self.used += cost
        self.sent.add((place_id, kind))
        return True


def names_match(asked: str, matched: str) -> bool:
    """G4: exact equality after NFC and case folding, with no other changes."""
    return (
        unicodedata.normalize("NFC", asked).casefold()
        == unicodedata.normalize("NFC", matched).casefold()
    )


def reaches_minimum(matched_with_figure: int) -> bool:
    """SYN-86 threshold only; no pooled shape or figure is computed here."""
    return matched_with_figure >= 3
