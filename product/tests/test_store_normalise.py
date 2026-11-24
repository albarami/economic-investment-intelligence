"""Normalisation and both comparison levels."""

from __future__ import annotations

from datetime import date, datetime, time
from decimal import ROUND_HALF_EVEN, Decimal

import pytest

from eii_product.store.normalise import (
    Fact,
    ToolResult,
    compare_queries,
    compare_tools,
    normalise,
)
from eii_product.store.protocol import NormalValue, QueryResult, StoreRefusal

PRECISION = {"SYN-unit": 2}


def test_rows_in_another_order_fail() -> None:
    left = _rows((("SYN-a",), ("SYN-b",)))
    right = _rows((("SYN-b",), ("SYN-a",)))
    with pytest.raises(StoreRefusal) as caught:
        compare_queries("aa", left, "aa", right)
    assert str(caught.value) == "field mismatch row=0 column=0"


def test_half_even_rounds_ties_to_even() -> None:
    """0.0000005 and 0.0000015 are the half-even ties at six places."""
    assert normalise(Decimal("0.0000005")) == Decimal("0.000000")
    assert normalise(Decimal("0.0000015")) == Decimal("0.000002")
    assert normalise(Decimal("-0.0000005")) == Decimal("0.000000")
    assert normalise(Decimal("-0.0000015")) == Decimal("-0.000002")


def test_accent_normalises_to_nfc() -> None:
    composed = "SYN-\u00e9"
    decomposed = "SYN-e\u0301"
    assert composed != decomposed
    assert normalise(decomposed) == normalise(composed) == composed


def test_integral_decimal_becomes_int_and_unequal_decimal_fails() -> None:
    assert normalise(Decimal("2.000000")) == 2
    assert type(normalise(Decimal("2.000000"))) is int
    left = _rows(((2,),))
    right = _rows(((Decimal("2.000001"),),))
    with pytest.raises(StoreRefusal) as caught:
        compare_queries("aa", left, "aa", right)
    assert str(caught.value).startswith("field mismatch")


def test_release_identity_mismatch_is_refused() -> None:
    """Identity is compared before any row. Removing that line lets the rows pass."""
    left = _rows((("SYN-a",),))
    with pytest.raises(StoreRefusal) as caught:
        compare_queries("aa", left, "bb", left)
    assert str(caught.value) == "release identity mismatch"


def test_column_mismatch_is_refused() -> None:
    """Column names are compared before values. Removing that line lets the rows pass."""
    left = QueryResult(("unit_id",), (("SYN-a",),))
    right = QueryResult(("label",), (("SYN-a",),))
    with pytest.raises(StoreRefusal) as caught:
        compare_queries("aa", left, "aa", right)
    assert str(caught.value) == "column mismatch"


def test_row_width_mismatch_is_refused() -> None:
    """A row wider than its header is refused even when both sides match."""
    wide = QueryResult(("unit_id",), (("SYN-a", "SYN-extra"),))
    with pytest.raises(StoreRefusal) as caught:
        compare_queries("aa", wide, "aa", wide)
    assert str(caught.value) == "row width mismatch"


def test_fewer_rows_are_row_count_mismatch() -> None:
    with pytest.raises(StoreRefusal) as caught:
        compare_queries("aa", _rows(((1,), (2,))), "aa", _rows(((1,),)))
    assert str(caught.value) == "row count mismatch"


def test_non_finite_number_is_refused() -> None:
    """A non-finite float is refused before any other scalar rule."""
    for value in (float("nan"), float("inf"), float("-inf")):
        with pytest.raises(StoreRefusal) as caught:
            normalise(value)
        assert str(caught.value) == "non-finite number"


def test_boolean_and_other_scalars_are_unsupported() -> None:
    """Bool, bytes and a clock time are not store scalars."""
    for value in (True, b"SYN", time(0, 0)):
        with pytest.raises(StoreRefusal) as caught:
            normalise(value)
        assert str(caught.value) == "unsupported scalar"


def test_quantise_ignores_the_caller_context() -> None:
    """Precision, traps and exponent limits of the caller do not change the result."""
    import decimal

    value = Decimal("0.0000015")
    expected = Decimal("0.000002")
    hostile = (
        decimal.Context(prec=5, rounding=ROUND_HALF_EVEN),
        decimal.Context(
            prec=28,
            rounding=ROUND_HALF_EVEN,
            traps=[decimal.Inexact, decimal.Rounded],
        ),
        decimal.Context(prec=28, rounding=ROUND_HALF_EVEN, Emin=-1, Emax=1),
    )
    for context in hostile:
        with decimal.localcontext(context):
            assert normalise(value) == expected


def test_right_fact_without_precision_is_refused() -> None:
    """The right-hand unit is checked even when the left-hand unit is known."""
    left = _tool("postgres", "SYN-a", 1, Decimal("1.00"))
    right = ToolResult(
        "embedded",
        "SYN-a",
        1,
        "syn_tool",
        "ok",
        None,
        (Fact("total", "SYN-other", Decimal("1.00")),),
    )
    with pytest.raises(StoreRefusal) as caught:
        compare_tools(left, right, unit_precision=PRECISION, round_fact=_round)
    assert str(caught.value) == "fact precision missing"


def test_unequal_fact_counts_are_row_count_mismatch() -> None:
    """Two tool results with different fact counts are a row-count refusal."""
    left = _tool("postgres", "SYN-a", 1, Decimal("1"))
    extra = (*left.facts, Fact("other", "SYN-unit", Decimal("1")))
    right = ToolResult("embedded", "SYN-a", 1, "syn_tool", "ok", None, extra)
    with pytest.raises(StoreRefusal) as caught:
        compare_tools(left, right, unit_precision=PRECISION, round_fact=_round)
    assert str(caught.value) == "row count mismatch"


def test_geometry_text_is_held_and_other_values_are_refused() -> None:
    """Upper-case even hex beginning 01 is kept. Anything else is refused."""
    from eii_product.store.normalise import hold_geometry

    held = "0101000000000000000000C03F000000000000D03F"
    assert hold_geometry(held) == held
    assert hold_geometry(None) is None
    for value in ("01ab", b"01AB", memoryview(b"01AB"), 1, True):
        with pytest.raises(StoreRefusal) as caught:
            hold_geometry(value)
        assert str(caught.value) == "unsupported scalar"


def test_dates_null_and_text_follow_the_rule() -> None:
    assert normalise(None) is None
    assert normalise(datetime(2000, 1, 2, 3, 4)) == date(2000, 1, 2)
    assert normalise(date(2000, 1, 2)) == date(2000, 1, 2)
    assert normalise(2.0) == 2


def test_engine_timing_and_call_id_are_ignored() -> None:
    left = _tool("postgres", "SYN-a", 1, Decimal("1.014"))
    right = _tool("embedded", "SYN-b", 9, Decimal("1.011"))
    compare_tools(left, right, unit_precision=PRECISION, round_fact=_round)


def test_each_other_tool_field_is_compared() -> None:
    base = _tool("postgres", "SYN-a", 1, Decimal("1.01"))
    fact = base.facts[0]
    variants = (
        ToolResult("postgres", "SYN-a", 1, "syn_other", "ok", None, (fact,)),
        ToolResult("postgres", "SYN-a", 1, "syn_tool", "no", None, (fact,)),
        ToolResult("postgres", "SYN-a", 1, "syn_tool", "ok", "bbbb", (fact,)),
        ToolResult(
            "postgres",
            "SYN-a",
            1,
            "syn_tool",
            "ok",
            None,
            (Fact("other", "SYN-unit", fact.value),),
        ),
        ToolResult(
            "postgres",
            "SYN-a",
            1,
            "syn_tool",
            "ok",
            None,
            (Fact("total", "SYN-other", fact.value),),
        ),
    )
    for variant in variants:
        with pytest.raises(StoreRefusal):
            compare_tools(base, variant, unit_precision=PRECISION, round_fact=_round)


def test_missing_unit_precision_is_refused() -> None:
    with pytest.raises(StoreRefusal) as caught:
        compare_tools(
            _tool("postgres", "SYN-a", 1, Decimal("1")),
            _tool("embedded", "SYN-a", 1, Decimal("1")),
            unit_precision={},
            round_fact=_round,
        )
    assert str(caught.value) == "fact precision missing"


def test_fact_values_use_the_declared_precision() -> None:
    close_left = _tool("postgres", "SYN-a", 1, Decimal("1.004"))
    close_right = _tool("embedded", "SYN-a", 1, Decimal("1.001"))
    compare_tools(close_left, close_right, unit_precision=PRECISION, round_fact=_round)
    apart = _tool("embedded", "SYN-a", 1, Decimal("1.02"))
    with pytest.raises(StoreRefusal) as caught:
        compare_tools(close_left, apart, unit_precision=PRECISION, round_fact=_round)
    assert str(caught.value) == "field mismatch row=0 column=2"


def _rows(rows: tuple[tuple[object, ...], ...]) -> QueryResult:
    return QueryResult(
        ("label",), tuple(tuple(normalise(value) for value in row) for row in rows)
    )


def _tool(engine: str, call_id: str, duration: int, value: Decimal) -> ToolResult:
    return ToolResult(
        engine,
        call_id,
        duration,
        "syn_tool",
        "ok",
        None,
        (Fact("total", "SYN-unit", value),),
    )


def _round(value: NormalValue, places: int) -> NormalValue:
    if isinstance(value, bool) or not isinstance(value, (int, Decimal)):
        return value
    quantum = Decimal(1).scaleb(-places)
    return Decimal(value).quantize(quantum, rounding=ROUND_HALF_EVEN)
