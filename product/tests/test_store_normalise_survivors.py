"""Kills surviving mutants of value normalisation and the two comparators."""

from __future__ import annotations

from collections.abc import Iterator
from decimal import ROUND_DOWN, Decimal, DefaultContext
from typing import Any

import pytest

from eii_product.store.normalise import (
    Fact,
    ToolResult,
    compare_queries,
    compare_tools,
    normalise,
)
from eii_product.store.protocol import NormalValue, QueryResult, StoreRefusal

_PRECISION = {"SYN-unit": 0, "SYN-other": 0}
_WIDE = Decimal("1234567890123456789012345.4")


def full_text(caught: pytest.ExceptionInfo[BaseException], literal: str) -> None:
    """Compare the whole message with one hand-written literal."""
    assert str(caught.value) == literal


def unchecked(value: object) -> Any:
    """Pass one value the annotation rejects through a single typed boundary."""
    return value


def test_owned_context_ignores_the_process_default() -> None:
    """Precision, rounding and the upper exponent stay on the owned context."""
    saved = (DefaultContext.prec, DefaultContext.rounding, DefaultContext.Emax)
    DefaultContext.prec = 6
    DefaultContext.rounding = ROUND_DOWN
    DefaultContext.Emax = 2
    try:
        assert normalise(Decimal("0.0000015")) == Decimal("0.000002")
        assert normalise(Decimal("123456789.1234567")) == Decimal("123456789.123457")
        assert normalise(Decimal("1000.5")) == Decimal("1000.500000")
    finally:
        DefaultContext.prec, DefaultContext.rounding, DefaultContext.Emax = saved


def test_unrepresentable_quantize_is_nan_not_a_trap() -> None:
    """Empty traps return NaN. The process default would raise instead."""
    result = normalise(_WIDE)
    assert type(result) is Decimal
    assert result.is_nan()


def test_equal_cells_match_and_a_short_row_iteration_is_refused() -> None:
    """Same values pass. A row sequence that lies about its length does not."""
    compare_queries("aa", _rows(((2,),)), "aa", _rows(((2,),)))
    left = QueryResult(("label",), unchecked(_Short(((2,), (3,)), 1)))
    right = QueryResult(("label",), unchecked(_Short(((2,),), 1)))
    with pytest.raises(ValueError) as caught:
        compare_queries("aa", left, "aa", right)
    full_text(caught, "zip() argument 2 is shorter than argument 1")


def test_one_wide_row_is_a_width_mismatch() -> None:
    """A wide left row is refused even when the right row matches the header."""
    left = QueryResult(("label",), (("SYN-a", "SYN-b"),))
    right = QueryResult(("label",), (("SYN-a",),))
    with pytest.raises(StoreRefusal) as caught:
        compare_queries("aa", left, "aa", right)
    full_text(caught, "row width mismatch")


def test_a_short_cell_iteration_is_refused() -> None:
    """Both rows claim the header width. The shorter iteration is still refused."""
    left = QueryResult(("label", "qty"), (_Short((2, 3), 2),))
    right = QueryResult(("label", "qty"), (_Short((2,), 2),))
    with pytest.raises(ValueError) as caught:
        compare_queries("aa", left, "aa", right)
    full_text(caught, "zip() argument 2 is shorter than argument 1")


def test_each_tool_field_names_its_own_position() -> None:
    """Tool, status, release, fact name and fact unit each name one position."""
    base = _tool((Fact("total", "SYN-unit", 2),))
    cases = (
        (_tool((Fact("total", "SYN-unit", 2),), tool="syn_other"), "row=0 column=0"),
        (_tool((Fact("total", "SYN-unit", 2),), status="no"), "row=0 column=1"),
        (_tool((Fact("total", "SYN-unit", 2),), release_id="abab"), "row=0 column=2"),
        (_tool((Fact("other", "SYN-unit", 2),)), "row=0 column=0"),
        (_tool((Fact("total", "SYN-other", 2),)), "row=0 column=1"),
    )
    for variant, position in cases:
        with pytest.raises(StoreRefusal) as caught:
            compare_tools(base, variant, unit_precision=_PRECISION, round_fact=_round)
        full_text(caught, f"field mismatch {position}")


def test_a_short_fact_iteration_is_refused() -> None:
    """Equal fact counts still refuse a sequence that yields fewer facts."""
    fact = Fact("total", "SYN-unit", 2)
    left = _tool(unchecked(_Short((fact, fact), 1)))
    right = _tool(unchecked(_Short((fact,), 1)))
    with pytest.raises(ValueError) as caught:
        compare_tools(left, right, unit_precision=_PRECISION, round_fact=_round)
    full_text(caught, "zip() argument 2 is shorter than argument 1")


def test_rounding_is_applied_to_ints_and_decimals_only() -> None:
    """An int is rounded. Text is compared as itself and is not handed over."""
    left = _tool((Fact("total", "SYN-unit", 2),))
    right = _tool((Fact("total", "SYN-unit", Decimal("2.4")),))
    compare_tools(left, right, unit_precision=_PRECISION, round_fact=_as_decimal)
    words = _tool((Fact("total", "SYN-unit", "SYN-kept"),))
    compare_tools(words, words, unit_precision=_PRECISION, round_fact=_refuse_text)


class _Short:
    """A sequence whose length and whose iteration disagree."""

    def __init__(self, items: tuple[object, ...], claimed: int) -> None:
        self._items = items
        self._claimed = claimed

    def __len__(self) -> int:
        return self._claimed

    def __iter__(self) -> Iterator[object]:
        return iter(self._items)


def _rows(rows: tuple[tuple[object, ...], ...]) -> QueryResult:
    return QueryResult(("label",), rows)


def _tool(
    facts: object,
    *,
    tool: str = "syn_tool",
    status: str = "ok",
    release_id: str | None = None,
) -> ToolResult:
    return ToolResult(
        "postgres",
        "SYN-call",
        1,
        tool,
        status,
        release_id,
        unchecked(facts),
    )


def _round(value: NormalValue, places: int) -> NormalValue:
    del value, places
    return 0


def _as_decimal(value: NormalValue, places: int) -> NormalValue:
    del places
    return Decimal(value) if type(value) is int else Decimal("2")


def _refuse_text(value: NormalValue, places: int) -> NormalValue:
    del value, places
    raise StoreRefusal("unsupported scalar")
