"""Project an inner refusal onto the closed diagnostic vocabulary."""

from __future__ import annotations

from eii_core.reason_codes import CODES


def closed_code(value: object, fallback: str) -> str:
    """Accept an entire known code only, never an excerpt or a formatted error."""
    if type(value) is str and value in CODES:
        return value
    if type(fallback) is str and (fallback in CODES or fallback == ""):
        return fallback
    return "operation_failed"


def reason(error: Exception, fallback: str = "operation_failed") -> str:
    """Retain closed reasons; classify unstructured faults without their text."""
    for candidate in (
        getattr(error, "reason", None),
        getattr(error, "variable", None),
        error.args[0] if len(error.args) == 1 else None,
    ):
        code = closed_code(candidate, "")
        if code:
            return code
    if isinstance(error, KeyError):
        return "input_key_missing"
    if isinstance(error, TypeError):
        return "input_type_invalid"
    if isinstance(error, AttributeError):
        return "input_attribute_missing"
    if isinstance(error, TimeoutError):
        return "operation_timeout"
    if isinstance(error, OSError):
        return "operation_os_error"
    return closed_code(fallback, "operation_failed")
