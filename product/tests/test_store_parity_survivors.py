"""Kills surviving mutants of the parity run, the report and the fact counts."""

from __future__ import annotations

import locale
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any

import pytest
from store_live_controls import FIXTURE_DIR

from eii_product.store.normalise import Fact, ToolResult
from eii_product.store.parity import (
    ParityCase,
    ToolDescriptor,
    TracingStore,
    count_pair,
    prepare_all,
    run_parity,
    write_report,
)
from eii_product.store.protocol import (
    EngineName,
    NormalValue,
    Param,
    QueryResult,
    ReleaseStore,
    StoreHealth,
    StoreRefusal,
)
from eii_product.store.registry import Inventory, load_inventory

_RELEASE = "ab" * 32
_OTHER = "cd" * 32
_PRECISION = {"SYN-unit": 0}
_INVENTORY = load_inventory(FIXTURE_DIR)
_EMPTY = Inventory((), object(), ())
_CONTROL_REPORT = (
    '{"cases_run": 1, "facts_compared": 1, "facts_identical": 1, '
    '"fixture_id": "SYN-fix", "queries": {"embedded": [], "postgres": []}, '
    '"release_id": null, "scope": "control"}'
)
_CHECKED_REPORT = (
    '{"cases_run": 1, "facts_compared": 1, "facts_identical": 1, '
    '"queries": {"embedded": [], "postgres": []}, '
    f'"release_id": "{_RELEASE}", "scope": "checked"}}'
)
_COUNT_REPORT = (
    '{"cases_run": 2, "facts_compared": 4, "facts_identical": 3, '
    '"fixture_id": "SYN-fix", "queries": {"embedded": [], "postgres": []}, '
    '"release_id": null, "scope": "control"}'
)
_UTF8_REPORT = (
    '{"cases_run": 1, "facts_compared": 1, "facts_identical": 1, '
    '"fixture_id": "SYN-\u00e9", "queries": {"embedded": ["syn_rows"], '
    '"postgres": ["syn_rows"]}, "release_id": null, "scope": "control"}'
)


def full_text(caught: pytest.ExceptionInfo[BaseException], literal: str) -> None:
    """Compare the whole message with one hand-written literal."""
    assert str(caught.value) == literal


def unchecked(value: object) -> Any:
    """Pass one value the annotation rejects through a single typed boundary."""
    return value


def test_wrapper_forwards_engine_release_params_and_timeout() -> None:
    """The wrapper keeps the inner identity and the arguments it was given."""
    inner = _Probe("postgres", _RELEASE)
    wrapped = TracingStore(inner, [])
    assert wrapped.engine == "postgres"
    assert wrapped.release_id == _RELEASE
    wrapped.fetch(unchecked(_Query()), {"units": ["SYN-a"]})
    assert inner.params == {"units": ["SYN-a"]}
    wrapped.ping(1.5)
    assert inner.timeout == 1.5


def test_same_engine_on_two_objects_is_refused() -> None:
    """Two objects that name one engine are not a pair of engines."""
    with pytest.raises(StoreRefusal) as caught:
        _run(
            (_Probe("postgres", _RELEASE), _Probe("postgres", _RELEASE)),
            (),
            (),
        )
    full_text(caught, "distinct engines required")


def test_no_store_is_refused() -> None:
    """An empty store list is refused before any store is read."""
    with pytest.raises(StoreRefusal) as caught:
        _run((), (), ())
    full_text(caught, "distinct engines required")


def test_unequal_release_ids_are_refused_with_no_tools() -> None:
    """Release identity is checked even when there is no tool to run."""
    with pytest.raises(StoreRefusal) as caught:
        _run(
            (_Probe("postgres", _RELEASE), _Probe("embedded", _OTHER)),
            (),
            (),
        )
    full_text(caught, "release identity mismatch")


def test_each_tool_sees_only_its_own_new_queries() -> None:
    """A later tool is not charged with the queries the earlier tool ran."""
    rows = _INVENTORY.lookup("control_rows")
    shape = _INVENTORY.lookup("control_shape")

    def run_rows(store: ReleaseStore, params: Mapping[str, Param]) -> ToolResult:
        del params
        store.fetch(rows, {"units": ["SYN-a"]})
        return _result(store.engine)

    def run_shape(store: ReleaseStore, params: Mapping[str, Param]) -> ToolResult:
        del params
        store.fetch(shape, {})
        return _result(store.engine)

    outcome = run_parity(
        (_Probe("postgres", _RELEASE), _Probe("embedded", _RELEASE)),
        (
            ToolDescriptor("syn_rows", run_rows, ("control_rows",)),
            ToolDescriptor("syn_shape", run_shape, ("control_shape",)),
        ),
        (
            ParityCase("syn_rows", ()),
            ParityCase("syn_shape", ()),
        ),
        _INVENTORY,
        unit_precision=_PRECISION,
        round_fact=_round,
    )
    assert outcome.coverage.passed is True
    assert outcome.coverage.tools == 2
    assert outcome.traces["postgres"] == ("control_rows", "control_shape")
    assert outcome.traces["embedded"] == ("control_rows", "control_shape")


def test_omitted_scope_writes_a_control_report(tmp_path: Path) -> None:
    """The default scope is the control report, fixture and all."""
    destination = tmp_path / "report.json"
    outcome = _run(
        (_Probe("postgres", _RELEASE), _Probe("embedded", _RELEASE)),
        (_descriptor("syn_tool", {"marker": "SYN-mark"}),),
        (ParityCase("syn_tool", (("marker", "SYN-mark"),)),),
        destination=destination,
        fixture_id="SYN-fix",
    )
    assert outcome.results[0].engine == "postgres"
    assert outcome.pairs[0][0].engine == "postgres"
    assert outcome.pairs[0][1].engine == "embedded"
    assert destination.read_text(encoding="utf-8") == _CONTROL_REPORT


def test_checked_scope_writes_the_release_id(tmp_path: Path) -> None:
    """A scope other than control keeps the release identity in the report."""
    destination = tmp_path / "report.json"
    _run(
        (_Probe("postgres", _RELEASE), _Probe("embedded", _RELEASE)),
        (_descriptor("syn_tool", {"marker": "SYN-mark"}),),
        (ParityCase("syn_tool", (("marker", "SYN-mark"),)),),
        destination=destination,
        scope="checked",
        fixture_id="SYN-fix",
    )
    assert destination.read_text(encoding="utf-8") == _CHECKED_REPORT


def test_report_bytes_are_sorted_utf8(tmp_path: Path) -> None:
    """The report is sorted UTF-8 with the fixture character left unescaped."""
    destination = tmp_path / "report.json"
    saved = locale.setlocale(locale.LC_ALL)
    try:
        locale.setlocale(locale.LC_ALL, "C")
        write_report(
            destination,
            results=(_result("postgres"),),
            traces={"postgres": ("syn_rows",), "embedded": ("syn_rows",)},
            scope="control",
            release_id=_RELEASE,
            fixture_id="SYN-\u00e9",
            pairs=((_result("postgres"), _result("embedded")),),
        )
        assert destination.read_bytes() == _UTF8_REPORT.encode("utf-8")
    finally:
        locale.setlocale(locale.LC_ALL, saved)


def test_fact_counts_add_across_pairs_and_facts(tmp_path: Path) -> None:
    """Every fact of every pair is counted. The last pair is not the total."""
    matched = Fact("total", "SYN-unit", 2)
    other = Fact("other", "SYN-unit", 3)
    first = _result("postgres", (matched, other))
    second_left = _result("postgres", (matched, other))
    second_right = _result("embedded", (matched, Fact("other", "SYN-unit", 4)))
    destination = tmp_path / "report.json"
    write_report(
        destination,
        results=(first, second_left),
        traces={"embedded": (), "postgres": ()},
        scope="control",
        release_id=_RELEASE,
        fixture_id="SYN-fix",
        pairs=((first, first), (second_left, second_right)),
    )
    assert destination.read_text(encoding="utf-8") == _COUNT_REPORT


def test_count_pair_refuses_unequal_fact_iteration() -> None:
    """strict pairing refuses a right-hand side that yields fewer facts."""
    fact = Fact("total", "SYN-unit", 2)
    left = _result("postgres", unchecked(_Short((fact, fact), 2)))
    right = _result("embedded", unchecked(_Short((fact,), 1)))
    with pytest.raises(ValueError) as caught:
        count_pair(left, right)
    full_text(caught, "zip() argument 2 is shorter than argument 1")


def test_prepare_all_names_none_for_an_empty_inventory() -> None:
    """An inventory with no query is still named, as none."""
    with pytest.raises(StoreRefusal) as caught:
        prepare_all(_Probe("embedded", _RELEASE), _EMPTY)
    full_text(caught, "prepare failed query=none engine=embedded")


class _Query:
    """A query name the wrapper records after the inner read."""

    name = "syn_rows"


class _Probe:
    """A store that records the arguments the wrapper forwarded."""

    def __init__(self, engine: EngineName, release_id: str) -> None:
        self.engine: EngineName = engine
        self.release_id = release_id
        self.params: object = "unset"
        self.timeout: object = "unset"

    def fetch(self, query: object, params: Mapping[str, Param]) -> QueryResult:
        del query
        self.params = params
        return QueryResult(("label",), (("SYN-a",),))

    def ping(self, timeout_s: float) -> StoreHealth:
        self.timeout = timeout_s
        return StoreHealth(ok=True)

    def close(self) -> None:
        return None


class _Short:
    """A sequence whose length and whose iteration disagree."""

    def __init__(self, items: tuple[object, ...], claimed: int) -> None:
        self._items = items
        self._claimed = claimed

    def __len__(self) -> int:
        return self._claimed

    def __iter__(self) -> Iterator[object]:
        return iter(self._items)


def _result(engine: str, facts: object | None = None) -> ToolResult:
    if facts is None:
        facts = (Fact("total", "SYN-unit", 2),)
    return ToolResult(
        engine,
        "SYN-call",
        1,
        "syn_tool",
        "ok",
        None,
        unchecked(facts),
    )


def _descriptor(key: str, expected: Mapping[str, Param]) -> ToolDescriptor:
    def run(store: ReleaseStore, params: Mapping[str, Param]) -> ToolResult:
        if dict(params) != dict(expected):
            raise StoreRefusal("parameter types invalid")
        return _result(store.engine)

    return ToolDescriptor(key, run, ())


def _run(
    stores: tuple[_Probe, ...] | tuple[()],
    tools: tuple[ToolDescriptor, ...],
    cases: tuple[ParityCase, ...],
    *,
    destination: Path | None = None,
    scope: str | None = None,
    fixture_id: str | None = None,
) -> object:
    if scope is None:
        return run_parity(
            stores,
            tools,
            cases,
            _EMPTY,
            unit_precision=_PRECISION,
            round_fact=_round,
            destination=destination,
            fixture_id=fixture_id,
        )
    return run_parity(
        stores,
        tools,
        cases,
        _EMPTY,
        unit_precision=_PRECISION,
        round_fact=_round,
        destination=destination,
        scope=scope,
        fixture_id=fixture_id,
    )


def _round(value: NormalValue, places: int) -> NormalValue:
    del places
    return value
