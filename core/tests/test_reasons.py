"""Closed diagnostics resist arbitrary text in every supported carrier."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from hypothesis import example, given
from hypothesis import strategies as st

from eii_core.reason_codes import CODES
from eii_core.reasons import closed_code, reason


@pytest.mark.parametrize("code", sorted(CODES))
def test_every_closed_code_survives_all_carriers(code: str) -> None:
    assert closed_code(code, "operation_failed") == code
    for attribute in ("reason", "variable"):
        error = Exception("INVENTED-sensitive-text")
        setattr(error, attribute, code)
        assert reason(error) == code
    assert reason(ValueError(code)) == code


@given(st.text())
@example("")
@example("digest_mismatch /INVENTED/private SELECT secret")
@example("digest_mismatch\n")
@example("digest_mismatchdigest_mismatch")
@example(" DIGEST_MISMATCH ")
def test_unknown_text_never_travels_in_diagnostics(text: str) -> None:
    if text in CODES:
        return
    assert closed_code(text, "operation_failed") == "operation_failed"
    error = ValueError(text)
    error.reason = text
    error.variable = text
    assert reason(error) == "operation_failed"


@pytest.mark.parametrize("value", [None, False, 0, [], {}, SimpleNamespace()])
def test_nonstring_carriers_cannot_bypass_membership(value: object) -> None:
    error = Exception(value)
    error.reason = value
    error.variable = value
    assert reason(error) == "operation_failed"


@pytest.mark.parametrize(
    "error,expected",
    [
        (KeyError("INVENTED-private"), "input_key_missing"),
        (TypeError("INVENTED-private"), "input_type_invalid"),
        (AttributeError("INVENTED-private"), "input_attribute_missing"),
        (TimeoutError("INVENTED-private"), "operation_timeout"),
        (OSError("INVENTED-private"), "operation_os_error"),
        (Exception("INVENTED-private"), "operation_failed"),
    ],
)
def test_unstructured_fault_has_a_safe_specific_category(
    error: Exception, expected: str
) -> None:
    assert reason(error) == expected


def test_multiple_args_and_precedence_do_not_format_exception_text() -> None:
    error = Exception("digest_mismatch", "INVENTED-private")
    assert reason(error) == "operation_failed"
    error.reason = "source_link_missing"
    error.variable = "routing_tiles"
    assert reason(error) == "source_link_missing"


@given(st.text())
@example("INVENTED/private SELECT secret")
def test_fallback_itself_cannot_publish_unknown_text(text: str) -> None:
    assert closed_code(None, text) in CODES | {""}
    assert reason(Exception("INVENTED-unstructured"), text) in CODES
