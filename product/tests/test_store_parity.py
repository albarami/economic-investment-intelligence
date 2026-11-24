"""Coverage guard. These tests use memory stores, so they do not prove two engines."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import pytest
from store_live_controls import FIXTURE_DIR, FIXTURE_ID

from eii_product.store.normalise import Fact, ToolResult
from eii_product.store.parity import (
    ParityCase,
    RunResult,
    ToolDescriptor,
    count_pair,
    cover,
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
from eii_product.store.registry import Inventory, QueryName, load_inventory

INVENTORY = load_inventory(FIXTURE_DIR)
OTHER = "b" * 64
PRECISION = {"SYN-count": 0}


def test_tool_without_a_case_is_refused() -> None:
    with pytest.raises(StoreRefusal) as caught:
        run_parity(
            (_Memory("postgres", FIXTURE_ID, 2), _Memory("embedded", FIXTURE_ID, 2)),
            (_tool(),),
            (),
            INVENTORY,
            unit_precision=PRECISION,
            round_fact=_round,
        )
    assert str(caught.value) == "tool case missing"


def test_case_for_an_unknown_tool_is_refused() -> None:
    with pytest.raises(StoreRefusal) as caught:
        run_parity(
            (_Memory("postgres", FIXTURE_ID, 2), _Memory("embedded", FIXTURE_ID, 2)),
            (),
            (_case(INVENTORY),),
            INVENTORY,
            unit_precision=PRECISION,
            round_fact=_round,
        )
    assert str(caught.value) == "tool case missing"


def test_tool_with_a_case_passes() -> None:
    outcome = _run(2, 2)
    assert outcome.coverage.passed is True
    assert outcome.coverage.tools == 1


def test_added_query_file_with_no_executed_case_is_refused(tmp_path: Path) -> None:
    folder = tmp_path / "added"
    folder.mkdir()
    (folder / "__init__.py").write_text('"""marker"""\n', encoding="utf-8")
    for name in ("control_rows", "syn_added"):
        source = FIXTURE_DIR / "control_rows.sql"
        text = source.read_text(encoding="utf-8").replace("control_rows", name, 1)
        (folder / f"{name}.sql").write_text(text, encoding="utf-8")
        (folder / f"{name}.toml").write_text(
            (FIXTURE_DIR / "control_rows.toml").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
    inventory = load_inventory(folder)
    with pytest.raises(StoreRefusal) as caught:
        run_parity(
            (_Memory("postgres", FIXTURE_ID, 2), _Memory("embedded", FIXTURE_ID, 2)),
            (_tool(inventory),),
            ((_case(inventory)),),
            inventory,
            unit_precision=PRECISION,
            round_fact=_round,
        )
    assert str(caught.value) == "query not executed"


def test_query_executed_on_one_engine_only_is_refused() -> None:
    def run(store: ReleaseStore, params: Mapping[str, Param]) -> ToolResult:
        del params
        if store.engine == "postgres":
            store.fetch(INVENTORY.lookup("control_rows"), {"units": ["SYN-a"]})
        return _result(store.engine, 2)

    with pytest.raises(StoreRefusal) as caught:
        run_parity(
            (_Memory("postgres", FIXTURE_ID, 2), _Memory("embedded", FIXTURE_ID, 2)),
            (ToolDescriptor("syn_control", run, ("control_rows",)),),
            (_case(INVENTORY),),
            INVENTORY,
            unit_precision=PRECISION,
            round_fact=_round,
        )
    assert str(caught.value) == "query not executed"


def test_an_inventory_query_no_tool_declares_is_still_required(tmp_path: Path) -> None:
    folder = tmp_path / "undeclared"
    folder.mkdir()
    (folder / "__init__.py").write_text('"""marker"""\n', encoding="utf-8")
    for name in ("control_rows", "syn_added"):
        source = FIXTURE_DIR / "control_rows.sql"
        text = source.read_text(encoding="utf-8").replace("control_rows", name, 1)
        (folder / f"{name}.sql").write_text(text, encoding="utf-8")
        (folder / f"{name}.toml").write_text(
            (FIXTURE_DIR / "control_rows.toml").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
    inventory = load_inventory(folder)
    member = inventory.lookup("control_rows")

    def run(store: ReleaseStore, params: Mapping[str, Param]) -> ToolResult:
        del params
        row = store.fetch(member, {"units": ["SYN-a"]}).rows[0]
        value = row[0]
        if type(value) is not int:
            raise StoreRefusal("result types invalid")
        return _result(store.engine, value)

    with pytest.raises(StoreRefusal) as caught:
        run_parity(
            (_Memory("postgres", FIXTURE_ID, 2), _Memory("embedded", FIXTURE_ID, 2)),
            (ToolDescriptor("syn_control", run, ("control_rows",)),),
            (_case(inventory),),
            inventory,
            unit_precision=PRECISION,
            round_fact=_round,
        )
    assert str(caught.value) == "query not executed"


def test_a_declared_name_is_unknown_on_an_empty_inventory(tmp_path: Path) -> None:
    folder = tmp_path / "empty"
    folder.mkdir()
    (folder / "__init__.py").write_text('"""marker"""\n', encoding="utf-8")
    inventory = load_inventory(folder)

    def run(store: ReleaseStore, params: Mapping[str, Param]) -> ToolResult:
        del store, params
        return _result("postgres", 2)

    with pytest.raises(StoreRefusal) as caught:
        run_parity(
            (_Memory("postgres", FIXTURE_ID, 2), _Memory("embedded", FIXTURE_ID, 2)),
            (ToolDescriptor("syn_control", run, ("control_rows",)),),
            (_case(inventory),),
            inventory,
            unit_precision=PRECISION,
            round_fact=_round,
        )
    assert str(caught.value) == "unknown query"


def test_declared_but_unexecuted_coverage_is_refused() -> None:
    def run(store: ReleaseStore, params: Mapping[str, Param]) -> ToolResult:
        del store, params
        return _result("postgres", 2)

    with pytest.raises(StoreRefusal) as caught:
        run_parity(
            (_Memory("postgres", FIXTURE_ID, 2), _Memory("embedded", FIXTURE_ID, 2)),
            (ToolDescriptor("syn_control", run, ("control_rows",)),),
            (_case(INVENTORY),),
            INVENTORY,
            unit_precision=PRECISION,
            round_fact=_round,
        )
    assert str(caught.value) == "query not executed"


def test_cover_of_one_engine_is_refused() -> None:
    with pytest.raises(StoreRefusal) as caught:
        cover(
            tools=(_tool(),),
            cases=(_case(INVENTORY),),
            traces={"postgres": ("control_rows",)},
            identities={"postgres": FIXTURE_ID},
            query_names=("control_rows",),
        )
    assert str(caught.value) == "distinct engines required"


def test_same_engine_twice_is_refused() -> None:
    with pytest.raises(StoreRefusal) as caught:
        run_parity(
            (_Memory("postgres", FIXTURE_ID, 2), _Memory("postgres", FIXTURE_ID, 2)),
            (_tool(),),
            (_case(INVENTORY),),
            INVENTORY,
            unit_precision=PRECISION,
            round_fact=_round,
        )
    assert str(caught.value) == "distinct engines required"


def test_unequal_identities_are_refused() -> None:
    with pytest.raises(StoreRefusal) as caught:
        run_parity(
            (_Memory("postgres", FIXTURE_ID, 2), _Memory("embedded", OTHER, 2)),
            (_tool(),),
            (_case(INVENTORY),),
            INVENTORY,
            unit_precision=PRECISION,
            round_fact=_round,
        )
    assert str(caught.value) == "release identity mismatch"


def test_empty_tool_list_reports_zero_and_no_pass() -> None:
    judged = cover(tools=(), cases=(), traces={}, identities={}, query_names=())
    assert judged.tools == 0
    assert judged.passed is False


def test_one_changed_integer_fails_the_case() -> None:
    with pytest.raises(StoreRefusal) as caught:
        _run(2, 3)
    assert str(caught.value).startswith("field mismatch")


def test_report_of_a_control_run(tmp_path: Path) -> None:
    destination = tmp_path / "report.json"
    _run(2, 2, destination)
    import json

    payload = json.loads(destination.read_text(encoding="utf-8"))
    assert payload["scope"] == "control"
    assert payload["release_id"] is None
    assert payload["fixture_id"] == FIXTURE_ID
    assert payload["cases_run"] == 1
    assert payload["facts_compared"] == 1
    assert payload["facts_identical"] == 1


def test_no_report_after_a_failed_case(tmp_path: Path) -> None:
    destination = tmp_path / "report.json"
    with pytest.raises(StoreRefusal):
        _run(2, 3, destination)
    assert not destination.exists()


def test_report_counts_across_the_two_stores(tmp_path: Path) -> None:
    """Identical is counted across the pair. One differing fact makes the counts differ by one."""
    import json

    left = _result("postgres", 2)
    right = _result("embedded", 3)
    destination = tmp_path / "report.json"
    write_report(
        destination,
        results=(left,),
        pairs=((left, right),),
        traces={"embedded": ("control_rows",), "postgres": ("control_rows",)},
        scope="control",
        release_id=FIXTURE_ID,
        fixture_id=FIXTURE_ID,
    )
    payload = json.loads(destination.read_text(encoding="utf-8"))
    assert payload["facts_compared"] - payload["facts_identical"] == 1


def test_facts_identical_are_counted_apart_from_facts_compared() -> None:
    """A mismatched pair is compared and not identical. One counter is not the other."""
    compared, identical = count_pair(_result("postgres", 2), _result("embedded", 3))
    assert compared == 1
    assert identical == 0


def test_tool_that_runs_a_query_it_does_not_own_is_refused() -> None:
    def run(store: ReleaseStore, params: Mapping[str, Param]) -> ToolResult:
        del params
        store.fetch(INVENTORY.lookup("control_rows"), {"units": ["SYN-a"]})
        return _result(store.engine, 2)

    with pytest.raises(StoreRefusal) as caught:
        run_parity(
            (_Memory("postgres", FIXTURE_ID, 2), _Memory("embedded", FIXTURE_ID, 2)),
            (ToolDescriptor("syn_control", run, ()),),
            (_case(INVENTORY),),
            INVENTORY,
            unit_precision=PRECISION,
            round_fact=_round,
        )
    assert str(caught.value) == "query not owned"


def test_caught_unknown_fetch_is_not_an_execution(tmp_path: Path) -> None:
    """A tool that swallows an unknown fetch has not executed the query."""
    _caught_refusal_is_not_an_execution(tmp_path, "unknown query")


def test_caught_parameter_refusal_is_not_an_execution(tmp_path: Path) -> None:
    """A tool that swallows a parameter refusal has not executed the query."""
    _caught_refusal_is_not_an_execution(tmp_path, "parameter types invalid")


def test_cover_refuses_unequal_release_identities() -> None:
    """Coverage compares the two identities itself, before it counts queries."""
    with pytest.raises(StoreRefusal) as caught:
        cover(
            tools=(_tool(),),
            cases=(_case(),),
            traces={
                "postgres": ("control_rows", "control_shape"),
                "embedded": ("control_rows", "control_shape"),
            },
            identities={"postgres": FIXTURE_ID, "embedded": OTHER},
            query_names=("control_rows", "control_shape"),
        )
    assert str(caught.value) == "release identity mismatch"


def test_store_without_plan_is_prepare_failed() -> None:
    """prepare_all refuses a store that cannot plan, naming the first query."""
    store = _Memory("embedded", FIXTURE_ID, 2)
    with pytest.raises(StoreRefusal) as caught:
        prepare_all(store, INVENTORY)
    assert str(caught.value) == "prepare failed query=control_rows engine=embedded"


def test_report_counts_are_counted_not_supplied(tmp_path: Path) -> None:
    destination = tmp_path / "report.json"
    same = _result("postgres", 2)
    write_report(
        destination,
        results=(same,),
        pairs=((same, same),),
        traces={"embedded": ("control_rows",), "postgres": ("control_rows",)},
        scope="control",
        release_id=FIXTURE_ID,
        fixture_id=FIXTURE_ID,
    )
    import json

    payload = json.loads(destination.read_text(encoding="utf-8"))
    assert payload["cases_run"] == 1
    assert payload["facts_compared"] == 1
    assert "facts_compared" not in write_report.__code__.co_varnames
    assert payload["queries"]["embedded"] == ["control_rows"]


class _Memory:
    def __init__(self, engine: EngineName, identity: str, total: int) -> None:
        self.engine: EngineName = engine
        self.release_id = identity
        self.total = total

    def fetch(self, query: QueryName, params: Mapping[str, Param]) -> QueryResult:
        del params
        if query.name == "control_shape":
            return QueryResult(("shape_id", "shape"), (("SYN-g0", "01"),))
        if query.name != "control_rows":
            raise StoreRefusal("unknown query")
        return QueryResult(("count_value",), ((self.total,),))

    def ping(self, timeout_s: float) -> StoreHealth:
        del timeout_s
        return StoreHealth(ok=True)

    def close(self) -> None:
        return None


def _tool(inventory: Inventory = INVENTORY) -> ToolDescriptor:
    member = inventory.lookup("control_rows")

    def run(store: ReleaseStore, params: Mapping[str, Param]) -> ToolResult:
        del params
        row = store.fetch(member, {"units": ["SYN-a"]}).rows[0]
        shape = inventory.get("control_shape")
        if shape is not None:
            store.fetch(inventory.lookup("control_shape"), {})
        value = row[0]
        if type(value) is not int:
            raise StoreRefusal("result types invalid")
        return _result(store.engine, value)

    return ToolDescriptor(
        "syn_control", run, tuple(query.name for query in inventory.queries)
    )


def _case(inventory: Inventory = INVENTORY) -> ParityCase:
    del inventory
    return ParityCase("syn_control", (("units", ["SYN-a"]),))


def _result(engine: str, total: int) -> ToolResult:
    return ToolResult(
        engine,
        "SYN-call",
        1,
        "syn_control",
        "ok",
        None,
        (Fact("total", "SYN-count", total),),
    )


def _run(left: int, right: int, destination: Path | None = None) -> RunResult:
    return run_parity(
        (_Memory("postgres", FIXTURE_ID, left), _Memory("embedded", FIXTURE_ID, right)),
        (_tool(),),
        (_case(INVENTORY),),
        INVENTORY,
        unit_precision=PRECISION,
        round_fact=_round,
        destination=destination,
        scope="control",
        fixture_id=FIXTURE_ID,
    )


def _round(value: NormalValue, places: int) -> NormalValue:
    del places
    return value


def _caught_refusal_is_not_an_execution(folder: Path, reason: str) -> None:
    inventory = _one_query(folder)
    member = inventory.lookup("control_rows")
    destination = folder / "report.json"

    def run(store: ReleaseStore, params: Mapping[str, Param]) -> ToolResult:
        del params
        try:
            store.fetch(member, {"units": ["SYN-a"]})
        except StoreRefusal as caught:
            assert str(caught) == reason
        return _result(store.engine, 2)

    with pytest.raises(StoreRefusal) as caught:
        run_parity(
            (
                _Refuse("postgres", reason),
                _Refuse("embedded", reason),
            ),
            (ToolDescriptor("syn_control", run, ("control_rows",)),),
            (_case(),),
            inventory,
            unit_precision=PRECISION,
            round_fact=_round,
            destination=destination,
            scope="control",
            fixture_id=FIXTURE_ID,
        )
    assert str(caught.value) == "query not executed"
    assert not destination.exists()


def _one_query(folder: Path) -> Inventory:
    root = folder / "one"
    root.mkdir()
    (root / "__init__.py").write_text('"""marker"""\n', encoding="utf-8")
    for suffix in (".sql", ".toml"):
        name = "control_rows" + suffix
        (root / name).write_text(
            (FIXTURE_DIR / name).read_text(encoding="utf-8"), encoding="utf-8"
        )
    return load_inventory(root)


class _Refuse:
    """Both engines refuse the one registered read and still look like stores."""

    def __init__(self, engine: EngineName, reason: str) -> None:
        self.engine: EngineName = engine
        self.release_id = FIXTURE_ID
        self.reason = reason

    def fetch(self, query: QueryName, params: Mapping[str, Param]) -> QueryResult:
        del query, params
        raise StoreRefusal(self.reason)

    def ping(self, timeout_s: float) -> StoreHealth:
        del timeout_s
        return StoreHealth(ok=True)

    def close(self) -> None:
        return None
