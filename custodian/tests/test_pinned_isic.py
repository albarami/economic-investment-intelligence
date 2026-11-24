"""INVENTED inputs only: the ISIC 5610 data-test case fails with closed words.

Each child run plants one fault carrying a sentinel count and checks that the
whole child output holds `C2-ISIC-5610:<reason>` and never the sentinel.
"""

import re
from decimal import Decimal as D
from fractions import Fraction
from types import SimpleNamespace

import pytest
from custodian.data_tests import test_pinned_methods as methods
from custodian.tests.test_pinned_wilson import (
    CHILD,
    ONE_MATCH,
    SENTINEL,
    child_pinned,
    summary,
)
from custodian.tests.test_restricted_expectation_guards import child_run
from hypothesis import given
from hypothesis import strategies as st

from eii_custodian.publicdata.review.activity import SpineError

ISIC_CHILD = CHILD.replace(
    "methods.pinned = invented.child_pinned({shamal!r}, {parts!r})\n",
    "from custodian.tests import test_pinned_isic as isic\n"
    "isic.plant_isic(methods, {kind!r})\n",
).replace(
    "    test_pinned_c2_wilson_period,\n    test_pinned_c2_wilson_stock,\n",
    "    test_pinned_c2_isic_5610,\n",
)
PINS = {"lic_active": "invented-pin-a", "lic_cancelled": "invented-pin-c"}


def churn_result(kind):
    """A stand-in for `licence_churn`'s three read slots; `kind` breaks one."""
    exact = Fraction(SENTINEL) if kind == "ratio_exact" else Fraction(2510, 7878)
    value = D(SENTINEL) if kind == "ratio_value" else D("0.32")
    refs = ("lic_active", f"lic_{SENTINEL}" if kind == "lineage" else "lic_cancelled")
    sources = tuple(SimpleNamespace(lineage_ref=ref) for ref in refs)
    return {
        "active_count": SimpleNamespace(value=D(7878)),
        "including_ratio": SimpleNamespace(
            exact_unrounded=exact, value=value, sources=sources
        ),
    }


def plant_isic(methods_module, kind):
    """Serve invented rows and pins, then plant the one fault named by `kind`."""

    def raiser(error):
        def raise_it(*_args, **_kwargs):
            raise error

        return raise_it

    parts = (SENTINEL - 500, 0) if kind == "stock" else (20, 8)
    methods_module.pinned = child_pinned(ONE_MATCH, parts)
    selected = {**PINS, "lic_cancelled": str(SENTINEL)} if kind == "pins" else PINS
    methods_module.reviewed_selections = lambda _cache: dict(selected)
    methods_module._cache._pin = PINS.__getitem__
    methods_module.committed_class_members = (
        raiser(SpineError(f"conflicting activity name for {SENTINEL}"))
        if kind == "spine"
        else lambda *_args, **_kwargs: ("5610101",)
    )
    if kind == "pinned":
        methods_module.pinned = raiser(KeyError(str(SENTINEL)))
    if kind in ("pass", "ratio_exact", "ratio_value", "lineage"):
        methods_module.licence_churn = lambda *_args, **_kwargs: churn_result(kind)


def test_isic_case_passes_on_matching_invented_result(tmp_path):
    passing = child_run(tmp_path, ISIC_CHILD.format(kind="pass"))
    assert passing.returncode == 0, "child_not_passed"


@pytest.mark.parametrize(
    ("kind", "reason"),
    [
        ("spine", "spine_refused"),
        ("pins", "spine_pins_differ"),
        ("pinned", "source_invalid"),
        ("stock", "isic_stock_mismatch"),
        ("ratio_exact", "isic_ratio_mismatch"),
        ("ratio_value", "isic_ratio_mismatch"),
        ("lineage", "isic_lineage"),
    ],
)
def test_isic_case_prints_only_case_and_closed_reason(tmp_path, kind, reason):
    failing = child_run(tmp_path, ISIC_CHILD.format(kind=kind))
    output = failing.stdout + failing.stderr
    assert failing.returncode == 1, "child_not_failed"
    assert str(SENTINEL) not in output, "sentinel_leaked"
    assert summary(failing) == {f"C2-ISIC-5610:{reason}"}


@pytest.mark.parametrize(
    ("message", "reason"),
    [
        ("spine_pins_differ", "spine_pins_differ"),
        ("isic_stock_mismatch", "isic_stock_mismatch"),
        ("isic_ratio_mismatch", "isic_ratio_mismatch"),
        ("isic_lineage", "isic_lineage"),
        ("month outside calendar", "month_outside_calendar"),
        ("public_cache_missing:lic_active", "public_cache_missing"),
        ("receipt_hash_mismatch:lic_cancelled", "receipt_hash_mismatch"),
        ("wilson_stock_mismatch", "source_invalid"),
        ("isic_stock_mismatch:7878", "source_invalid"),
        ("9876543", "source_invalid"),
        ("", "source_invalid"),
    ],
)
def test_isic_reason_admits_only_its_closed_set(message, reason):
    assert methods.closed_reason(ValueError(message), methods.ISIC_REASONS) == reason


@pytest.mark.parametrize("detail", ["", "9876543", "conflicting activity name for 1"])
def test_any_spine_error_is_spine_refused(detail):
    assert methods.closed_reason(SpineError(detail), methods.ISIC_REASONS) == (
        "spine_refused"
    )


@given(
    st.text(),
    st.sampled_from([ValueError, KeyError, TypeError, SpineError, AssertionError]),
)
def test_isic_reason_is_always_closed(message, kind):
    reason = methods.closed_reason(kind(message), methods.ISIC_REASONS)
    admitted = methods.ISIC_REASONS.get(message)
    if kind is SpineError:
        expected = "spine_refused"
    elif kind is ValueError and admitted:
        expected = admitted
    else:
        expected = "source_invalid"
    assert reason == expected
    assert re.fullmatch(r"[a-z_]+", reason)
