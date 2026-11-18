"""Exact decimal text shared by the trade sources. Nothing is rounded."""

from __future__ import annotations

import re
from decimal import Decimal

_UNSIGNED = re.compile(r"[0-9]+(?:\.[0-9]+)?")
_SIGNED = re.compile(r"-?[0-9]+(?:\.[0-9]+)?")
_ZERO = re.compile(r"-?0+(?:\.0+)?")
_ATTEMPT = re.compile(
    r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?|nan|inf|infinity",
    re.IGNORECASE,
)


class DecimalRefusal(Exception):
    """Fixed reason only. The rejected text is not kept on the exception."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


def is_zero_token(value: str) -> bool:
    """True when the token is a written zero, including a leading minus and zeros."""
    return _ZERO.fullmatch(value) is not None


def looks_numeric(value: str) -> bool:
    """True when the text is a numeric attempt, including nonfinite words."""
    return _ATTEMPT.fullmatch(value) is not None


def read_measure(
    value: str,
    *,
    total_digits: int,
    fractional_digits: int,
    signed: bool,
    missing: tuple[str, ...],
) -> tuple[str | None, str]:
    """Return the original decimal text, or null when a declared missing token appears."""
    if value in missing:
        return None, "source_missing"
    try:
        text = exact_decimal(
            value,
            total_digits=total_digits,
            fractional_digits=fractional_digits,
            signed=signed,
        )
    except DecimalRefusal as exc:
        if exc.reason == "decimal_format" and not looks_numeric(value):
            raise DecimalRefusal("missing_undeclared") from None
        raise
    return text, "present"


def exact_decimal(
    value: object,
    *,
    total_digits: int,
    fractional_digits: int,
    signed: bool,
) -> str:
    """Accept fixed-point ASCII and return the same characters.

    A float, an exponent, a sign the grammar does not allow, or a nonfinite
    value is refused. Digit limits count every written digit, including zeros.
    """
    if type(value) is not str:
        raise DecimalRefusal("decimal_format")
    pattern = _SIGNED if signed else _UNSIGNED
    if pattern.fullmatch(value) is None:
        raise DecimalRefusal("decimal_format")
    body = value[1:] if signed and value.startswith("-") else value
    whole, _, fraction = body.partition(".")
    if len(fraction) > fractional_digits:
        raise DecimalRefusal("decimal_fractional_digits")
    if len(whole) + len(fraction) > total_digits:
        raise DecimalRefusal("decimal_total_digits")
    if not Decimal(value).is_finite():
        raise DecimalRefusal("decimal_format")
    return value
