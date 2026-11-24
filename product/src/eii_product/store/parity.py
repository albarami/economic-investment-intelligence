"""Parity cases, execution traces, coverage and the control report."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from eii_product.store.normalise import ToolResult, compare_tools
from eii_product.store.protocol import (
    NormalValue,
    Param,
    QueryResult,
    ReleaseStore,
    StoreHealth,
    StoreRefusal,
)
from eii_product.store.registry import Inventory, QueryName, sample_params


@dataclass(frozen=True)
class ParityCase:
    """One tool call. Inputs stay paired so the case cannot be reordered silently."""

    tool: str
    inputs: tuple[tuple[str, Param], ...]


@dataclass(frozen=True)
class ToolDescriptor:
    """A registered tool. Coverage reads traces, and the names are what it may run."""

    key: str
    run: Callable[[ReleaseStore, Mapping[str, Param]], ToolResult]
    queries: tuple[str, ...]


@dataclass(frozen=True)
class Coverage:
    """How many tools were judged. An empty list is zero tools and not a pass."""

    tools: int
    passed: bool


@dataclass(frozen=True)
class RunResult:
    """A finished run. The report is written only after this exists."""

    coverage: Coverage
    results: tuple[ToolResult, ...]
    traces: Mapping[str, tuple[str, ...]]
    pairs: tuple[tuple[ToolResult, ToolResult], ...]


class TracingStore:
    """Records every query name a tool fetches on one engine."""

    def __init__(self, inner: ReleaseStore, found: list[str]) -> None:
        """Wrap a store. The trace list is filled by fetch."""
        self._inner = inner
        self._found = found
        self.engine = inner.engine
        self.release_id = inner.release_id

    def fetch(self, query: QueryName, params: Mapping[str, Param]) -> QueryResult:
        """Delegate, and record the name only after the inner read returns."""
        result = self._inner.fetch(query, params)
        self._found.append(query.name)
        return result

    def ping(self, timeout_s: float) -> StoreHealth:
        """Delegate the health check."""
        return self._inner.ping(timeout_s)

    def close(self) -> None:
        """Delegate close."""
        self._inner.close()


def cover(
    *,
    tools: Sequence[ToolDescriptor],
    cases: Sequence[ParityCase],
    traces: Mapping[str, Sequence[str]],
    identities: Mapping[str, str],
    query_names: Sequence[str],
) -> Coverage:
    """Judge coverage from traces. A declaration is not an execution."""
    if len(tools) == 0:
        return Coverage(0, False)
    engines = tuple(traces)
    if len(engines) != 2 or engines[0] == engines[1]:
        raise StoreRefusal("distinct engines required")
    if identities[engines[0]] != identities[engines[1]]:
        raise StoreRefusal("release identity mismatch")
    covered = {case.tool for case in cases}
    for tool in tools:
        if tool.key not in covered:
            raise StoreRefusal("tool case missing")
    for name in query_names:
        for engine in engines:
            if name not in traces[engine]:
                raise StoreRefusal("query not executed")
    return Coverage(len(tools), True)


def run_parity(
    stores: Sequence[ReleaseStore],
    tools: Sequence[ToolDescriptor],
    cases: Sequence[ParityCase],
    inventory: Inventory,
    *,
    unit_precision: Mapping[str, int],
    round_fact: Callable[[NormalValue, int], NormalValue],
    destination: Path | None = None,
    scope: str = "control",
    fixture_id: str | None = None,
) -> RunResult:
    """Run every case on both stores. Write the report only after every check."""
    if (
        len(stores) != 2
        or stores[0] is stores[1]
        or stores[0].engine == stores[1].engine
    ):
        raise StoreRefusal("distinct engines required")
    if stores[0].release_id != stores[1].release_id:
        raise StoreRefusal("release identity mismatch")
    found: dict[str, list[str]] = {store.engine: [] for store in stores}
    results: list[ToolResult] = []
    pairs: list[tuple[ToolResult, ToolResult]] = []
    by_key = {tool.key: tool for tool in tools}
    for case in cases:
        tool = by_key.get(case.tool)
        if tool is None:
            raise StoreRefusal("tool case missing")
        pair: list[ToolResult] = []
        owned = set(tool.queries)
        for store in stores:
            wrapped = TracingStore(store, found[store.engine])
            before = len(found[store.engine])
            pair.append(tool.run(wrapped, dict(case.inputs)))
            for name in found[store.engine][before:]:
                if name not in owned:
                    raise StoreRefusal("query not owned")
        compare_tools(
            pair[0],
            pair[1],
            unit_precision=unit_precision,
            round_fact=round_fact,
        )
        results.append(pair[0])
        pairs.append((pair[0], pair[1]))
    traces = {engine: tuple(names) for engine, names in found.items()}
    query_names = tuple(query.name for query in inventory.queries)
    known = set(query_names)
    for tool in tools:
        for name in tool.queries:
            if name not in known:
                raise StoreRefusal("unknown query")
    coverage = cover(
        tools=tools,
        cases=cases,
        traces=traces,
        identities={store.engine: store.release_id for store in stores},
        query_names=query_names,
    )
    if destination is not None and coverage.passed:
        write_report(
            destination,
            results=tuple(results),
            traces=traces,
            scope=scope,
            release_id=stores[0].release_id,
            fixture_id=fixture_id,
            pairs=tuple(pairs),
        )
    return RunResult(coverage, tuple(results), traces, tuple(pairs))


def write_report(
    destination: Path,
    *,
    results: Sequence[ToolResult],
    traces: Mapping[str, Sequence[str]],
    scope: str,
    release_id: str | None,
    fixture_id: str | None,
    pairs: Sequence[tuple[ToolResult, ToolResult]],
) -> None:
    """Count the run across the two stores. A control report carries the fixture identity."""
    compared, identical = _fact_counts(pairs)
    payload: dict[str, object] = {
        "cases_run": len(results),
        "facts_compared": compared,
        "facts_identical": identical,
        "queries": {engine: list(names) for engine, names in sorted(traces.items())},
        "release_id": None if scope == "control" else release_id,
        "scope": scope,
    }
    if scope == "control":
        payload["fixture_id"] = fixture_id
    destination.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )


def _fact_counts(pairs: Sequence[tuple[ToolResult, ToolResult]]) -> tuple[int, int]:
    """Count facts examined across each pair of stores, never a result against itself."""
    compared = 0
    identical = 0
    for left, right in pairs:
        pair_compared, pair_identical = count_pair(left, right)
        compared += pair_compared
        identical += pair_identical
    return compared, identical


def count_pair(left: ToolResult, right: ToolResult) -> tuple[int, int]:
    """Count compared facts and the ones that match the other side."""
    compared = 0
    identical = 0
    for left_fact, right_fact in zip(left.facts, right.facts, strict=True):
        compared += 1
        if (
            left_fact.name == right_fact.name
            and left_fact.unit == right_fact.unit
            and type(left_fact.value) is type(right_fact.value)
            and left_fact.value == right_fact.value
        ):
            identical += 1
    return compared, identical


def prepare_all(store: ReleaseStore, inventory: Inventory) -> None:
    """Plan every query through the fetch binding path. Tools cannot call this."""
    plan = getattr(store, "plan", None)
    if not callable(plan):
        raise prepare_message(
            inventory.queries[0].name if inventory.queries else "none", store.engine
        )
    for spec in inventory.queries:
        plan(inventory.lookup(spec.name), sample_params(spec))


def prepare_message(query: str, engine: str) -> StoreRefusal:
    """The refusal prepare_all uses when the store cannot plan."""
    from eii_product.store.protocol import prepare_failed

    return prepare_failed(query, engine)
