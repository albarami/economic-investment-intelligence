"""Kills surviving mutants of the query registry outside the scanners."""

from __future__ import annotations

import hashlib
import locale
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
import sqlglot

from eii_product.store.protocol import StoreRefusal
from eii_product.store.registry import (
    ContractColumn,
    ContractTable,
    QueryName,
    QuerySpec,
    ReturnSpec,
    _bare_projected,
    _bind_value,
    _contract,
    _contract_column_type,
    _contract_table,
    _fits,
    _geometry_sql,
    _keyword_at,
    _outer_select_list,
    _sample,
    _wrap_geometry,
    checked_result,
    load_inventory,
    packaged_sql_dir,
)

_TEXT = (
    '[[tables]]\nname = "control_rows"\nanchor = "invented control table"\n'
    'key = ["unit_id"]\n\n[[tables.columns]]\nname = "unit_id"\n'
    'type = "string"\nnullable = false\n'
)
_GEOM = (
    '[[tables]]\nname = "control_geom"\nanchor = "invented control table"\n'
    'key = ["shape"]\n\n[[tables.columns]]\nname = "shape"\n'
    'type = "geometry"\nnullable = true\n'
)


def refusal(caught: pytest.ExceptionInfo[StoreRefusal], text: str) -> None:
    """Compare the whole refusal text with one hand-written literal."""
    assert str(caught.value) == text


def as_any(value: object) -> Any:
    """Hand a value the parameter's annotation would reject."""
    return value


def _write(folder: Path, name: str, sql: str, toml: str) -> None:
    folder.mkdir()
    (folder / "__init__.py").write_text('"""marker"""\n', encoding="utf-8")
    (folder / f"{name}.sql").write_text(sql, encoding="utf-8")
    (folder / f"{name}.toml").write_text(toml, encoding="utf-8")


def _sql(name: str, params: str, returns: str, order: str, body: str) -> str:
    return (
        f"-- name: {name}\n-- params: {params}\n-- returns: {returns}\n"
        f"-- order: {order}\n{body}\n"
    )


def _expect_header(folder: Path, sql: str) -> None:
    _write(folder, "syn_rows", sql, _TEXT)
    with pytest.raises(StoreRefusal) as caught:
        load_inventory(folder)
    refusal(caught, "query header invalid")


def _column_table() -> dict[str, object]:
    return {
        "name": "control_rows",
        "anchor": "invented control table",
        "key": ["unit_id"],
        "columns": [{"name": "unit_id", "type": "string", "nullable": False}],
    }


def test_packaged_sql_dir_is_the_package_folder() -> None:
    """The packaged folder is the sql package, marker and all."""
    folder = packaged_sql_dir()
    assert folder.name == "sql"
    assert folder.parent.name == "store"
    assert (folder / "__init__.py").is_file()


def test_loader_closes_the_guard(tmp_path: Path) -> None:
    """A name minted after the loader returns is still refused."""
    _write(
        tmp_path / "syn_rows",
        "syn_rows",
        _sql("syn_rows", "", "unit_id text", "unit_id", "SELECT 1 AS unit_id"),
        _TEXT,
    )
    load_inventory(tmp_path / "syn_rows")
    with pytest.raises(StoreRefusal) as caught:
        QueryName("syn_rows", object())
    refusal(caught, "unknown query")


def test_utf8_read_ignores_the_process_locale(tmp_path: Path) -> None:
    """A non-ascii byte in the query and the contract is read as UTF-8."""
    sql = _sql(
        "syn_rows",
        "",
        "unit_id text",
        "unit_id",
        "SELECT p.unit_id AS unit_id FROM control_rows AS p -- caff\u00e8",
    )
    toml = _TEXT.replace("invented control table", "invented caff\u00e8 table")
    folder = tmp_path / "syn_rows"
    _write(folder, "syn_rows", sql, toml)
    previous = locale.setlocale(locale.LC_ALL)
    locale.setlocale(locale.LC_ALL, "C")
    try:
        inventory = load_inventory(folder)
    finally:
        locale.setlocale(locale.LC_ALL, previous)
    loaded = inventory.get("syn_rows")
    assert loaded is not None
    assert loaded.tables[0].anchor == "invented caff\u00e8 table"


def test_loaded_query_keeps_the_file_digest(tmp_path: Path) -> None:
    """The digest is the SHA-256 of the query file bytes."""
    sql = _sql("syn_rows", "", "unit_id text", "unit_id", "SELECT 1 AS unit_id")
    folder = tmp_path / "syn_rows"
    _write(folder, "syn_rows", sql, _TEXT)
    inventory = load_inventory(folder)
    loaded = inventory.get("syn_rows")
    assert loaded is not None
    digest = hashlib.sha256((folder / "syn_rows.sql").read_bytes()).hexdigest()
    assert loaded.sha256 == digest


def test_header_line_without_a_colon_is_refused(tmp_path: Path) -> None:
    _expect_header(
        tmp_path / "syn_rows",
        "-- name syn_rows\n-- params:\n-- returns: unit_id text\n"
        "-- order: unit_id\nSELECT 1 AS unit_id\n",
    )


def test_header_line_without_the_mark_is_refused(tmp_path: Path) -> None:
    _expect_header(
        tmp_path / "syn_rows",
        "name: syn_rows\n-- params:\n-- returns: unit_id text\n"
        "-- order: unit_id\nSELECT 1 AS unit_id\n",
    )


def test_empty_body_is_refused(tmp_path: Path) -> None:
    _expect_header(
        tmp_path / "syn_rows",
        "-- name: syn_rows\n-- params:\n-- returns: unit_id text\n"
        "-- order: unit_id\n\n",
    )


def test_two_colons_do_not_unpack(tmp_path: Path) -> None:
    """A second colon stays inside the value; it is not a third field."""
    _expect_header(
        tmp_path / "syn_rows",
        "-- name: syn_rows:extra\n-- params:\n-- returns: unit_id text\n"
        "-- order: unit_id\nSELECT 1 AS unit_id\n",
    )


@pytest.mark.parametrize(
    "params",
    ["only", "n float", "n bigint, n bigint", "1bad bigint"],
)
def test_parameter_shape_is_refused(tmp_path: Path, params: str) -> None:
    _expect_header(
        tmp_path / "syn_rows",
        _sql("syn_rows", params, "unit_id text", "unit_id", "SELECT 1 AS unit_id"),
    )


@pytest.mark.parametrize(
    "returns",
    [
        "",
        "only",
        "unit_id string",
        "1bad text",
        "unit_id text, unit_id text",
        "flag bool",
    ],
)
def test_return_shape_is_refused(tmp_path: Path, returns: str) -> None:
    order = "" if returns == "" else "unit_id"
    _expect_header(
        tmp_path / "syn_rows",
        _sql("syn_rows", "", returns, order, "SELECT 1 AS unit_id"),
    )


@pytest.mark.parametrize("order", ["other", "unit_id, unit_id", "1bad"])
def test_order_names_must_be_known_return_columns(tmp_path: Path, order: str) -> None:
    _expect_header(
        tmp_path / "syn_rows",
        _sql("syn_rows", "", "unit_id text", order, "SELECT 1 AS unit_id"),
    )


def test_samples_are_the_fixed_values() -> None:
    """Each header type has one fixed sample, and each list is a new object."""
    assert _sample("bigint") == 0
    assert _sample("text") == "SYN-sample"
    assert _sample("bool") is True
    assert _sample("date") == date(2000, 1, 1)
    first = _sample("list[bigint]")
    second = _sample("list[bigint]")
    assert first == [0]
    assert second == [0]
    assert first is not second
    words = _sample("list[text]")
    assert words == ["SYN-sample"]
    assert words is not _sample("list[text]")
    with pytest.raises(StoreRefusal) as caught:
        _sample("bytea")
    refusal(caught, "parameter types invalid")


def test_bind_value_requires_the_exact_type() -> None:
    """A value is copied only when its Python type is the header type."""
    assert _bind_value("bigint", 4) == 4
    assert _bind_value("text", "SYN-a") == "SYN-a"
    assert _bind_value("bool", False) is False
    assert _bind_value("date", date(2000, 1, 2)) == date(2000, 1, 2)
    source = [4]
    copied = _bind_value("list[bigint]", source)
    assert copied == [4]
    assert copied is not source
    words = ["SYN-a"]
    copied_words = _bind_value("list[text]", words)
    assert copied_words == ["SYN-a"]
    assert copied_words is not words
    refused = (
        ("bigint", "4"),
        ("bigint", True),
        ("text", 4),
        ("bool", 1),
        ("bool", "True"),
        ("date", "2000-01-02"),
        ("list[bigint]", 4),
        ("list[bigint]", ["4"]),
        ("list[text]", [4]),
        ("text", [4]),
        ("bytea", 4),
    )
    for type_name, value in refused:
        with pytest.raises(StoreRefusal) as caught:
            _bind_value(type_name, value)
        refusal(caught, "parameter types invalid")


def test_numeric_fit_and_unknown_type() -> None:
    assert _fits(2, "numeric") is True
    assert _fits(Decimal("2.5"), "numeric") is True
    assert _fits("SYN", "numeric") is False
    assert _fits(None, "numeric") is True
    assert _fits("SYN", "other") is False


def test_geometry_result_uses_the_holder() -> None:
    """A geometry cell is held, and a non-geometry text is unsupported."""
    spec = QuerySpec(
        "syn_geom",
        (),
        (ReturnSpec("shape", "geometry"),),
        ("shape",),
        "SELECT g.shape AS shape FROM control_geom AS g",
        "ab",
        (),
    )
    held = checked_result(spec, ("shape",), (("01AB",), (None,)))
    assert held.columns == ("shape",)
    assert held.rows == (("01AB",), (None,))
    with pytest.raises(StoreRefusal) as caught:
        checked_result(spec, ("shape",), (("zz",),))
    refusal(caught, "unsupported scalar")


def test_contract_rejects_a_semicolon_inside_a_string(tmp_path: Path) -> None:
    toml = _TEXT.replace("invented control table", "invented; control table")
    folder = tmp_path / "syn_rows"
    _write(
        folder,
        "syn_rows",
        _sql("syn_rows", "", "unit_id text", "unit_id", "SELECT 1 AS unit_id"),
        toml,
    )
    with pytest.raises(StoreRefusal) as caught:
        load_inventory(folder)
    refusal(caught, "query header invalid")


def test_missing_key_defaults_to_empty() -> None:
    raw = _column_table()
    del raw["key"]
    loaded = _contract_table(raw)
    assert loaded.key == ()
    assert loaded.anchor == "invented control table"
    assert loaded.columns[0].nullable is False


def test_invalid_column_name_is_refused() -> None:
    """A bad column name is refused even when the key does not miss it."""
    raw = _column_table()
    raw["key"] = []
    raw["columns"] = [{"name": "Unit", "type": "string", "nullable": False}]
    with pytest.raises(StoreRefusal) as caught:
        _contract_table(raw)
    refusal(caught, "query header invalid")


def test_contract_read_rejects_semicolon_before_toml(tmp_path: Path) -> None:
    """The semicolon guard runs on the file text the loader reads."""
    path = tmp_path / "syn_rows.toml"
    path.write_text(
        _TEXT.replace("invented control table", "invented; control table"),
        encoding="utf-8",
    )
    with pytest.raises(StoreRefusal) as caught:
        _contract(path)
    refusal(caught, "query header invalid")


def test_contract_column_type_refuses_each_miss() -> None:
    """Each miss raises the caller's reason, not a stand-in."""
    table = ContractTable(
        "control_rows",
        "invented control table",
        ("unit_id",),
        (ContractColumn("unit_id", "string", False),),
    )
    twin = ContractTable(
        "control_rows",
        "invented control table",
        (),
        (ContractColumn("unit_id", "string", False),),
    )
    query = QuerySpec(
        "syn_rows", (), (ReturnSpec("unit_id", "text"),), (), "SELECT 1", "ab", (table,)
    )
    duplicated = QuerySpec(
        "syn_rows",
        (),
        (ReturnSpec("unit_id", "text"),),
        (),
        "SELECT 1",
        "ab",
        (table, twin),
    )
    blank = ContractTable(
        "control_rows",
        "invented control table",
        (),
        (ContractColumn("", "string", False),),
    )
    blank_query = QuerySpec(
        "syn_rows", (), (ReturnSpec("unit_id", "text"),), (), "SELECT 1", "ab", (blank,)
    )
    cases: tuple[tuple[QuerySpec, object, str], ...] = (
        (query, None, "unit_id"),
        (query, "control_rows", ""),
        (query, "other_rows", "unit_id"),
        (duplicated, "control_rows", "unit_id"),
        (query, "control_rows", "other"),
        (blank_query, "control_rows", ""),
    )
    for spec, table_name, column_name in cases:
        with pytest.raises(StoreRefusal) as caught:
            _contract_column_type(
                spec, as_any(table_name), column_name, "query header invalid"
            )
        refusal(caught, "query header invalid")


def test_keyword_needs_both_bounds() -> None:
    """A keyword is a whole token, including at either end of the text."""
    assert _keyword_at("SELECT", 0, "SELECT") is True
    assert _keyword_at("SELECTX", 0, "SELECT") is False
    assert _keyword_at("XSELECT", 1, "SELECT") is False
    assert _keyword_at("_SELECT", 1, "SELECT") is False
    assert _keyword_at("SELECT_", 0, "SELECT") is False
    assert _keyword_at(" SELECT", 1, "SELECT") is True
    assert _keyword_at("XSELECT ", 1, "SELECT") is False


def test_from_must_follow_select() -> None:
    assert _outer_select_list("SELECT a FROM t") == (6, 9)
    with pytest.raises(StoreRefusal) as caught:
        _outer_select_list("FROM t SELECT a")
    refusal(caught, "forbidden construct")


def test_bare_projection_keeps_a_real_alias() -> None:
    renamed = sqlglot.parse_one(
        "SELECT g.shape AS area FROM control_geom AS g", read="postgres"
    )
    output, node = _bare_projected(renamed.expressions[0])
    assert output == "area"
    assert type(node).__name__ == "Column"
    plain = sqlglot.parse_one("SELECT g.shape FROM control_geom AS g", read="postgres")
    plain_output, plain_node = _bare_projected(plain.expressions[0])
    assert plain_output == "shape"
    assert type(plain_node).__name__ == "Column"


def test_empty_alias_uses_the_column_name() -> None:
    tree = sqlglot.parse_one(
        'SELECT g.shape AS "" FROM control_geom AS g', read="postgres"
    )
    output, node = _bare_projected(tree.expressions[0])
    assert output == "shape"
    assert type(node).__name__ == "Column"


def test_empty_column_name_is_not_a_projection_name() -> None:
    tree = sqlglot.parse_one('SELECT g."" FROM control_geom AS g', read="postgres")
    output, _node = _bare_projected(tree.expressions[0])
    assert output is None


def test_geometry_tie_parses_postgres_only(tmp_path: Path) -> None:
    """FROM ONLY is postgres. A default parse must not accept the tie."""
    sql = _sql(
        "syn_geom",
        "",
        "shape geometry",
        "shape",
        "SELECT g.shape AS shape FROM ONLY control_geom AS g",
    )
    folder = tmp_path / "syn_geom"
    _write(folder, "syn_geom", sql, _GEOM)
    inventory = load_inventory(folder)
    loaded = inventory.get("syn_geom")
    assert loaded is not None
    assert loaded.returns[0].type_name == "geometry"


def test_contract_cte_parses_postgres_only(tmp_path: Path) -> None:
    """A contract-table CTE is refused, and only a postgres parse can see it."""
    sql = _sql(
        "syn_rows",
        "",
        "unit_id text",
        "unit_id",
        "WITH control_rows AS ("
        "SELECT p.unit_id AS unit_id FROM ONLY control_rows AS p"
        ") SELECT control_rows.unit_id AS unit_id FROM control_rows",
    )
    _expect_header(tmp_path / "syn_rows", sql)


def test_unparsed_geometry_query_is_refused(tmp_path: Path) -> None:
    """A geometry query the postgres parser rejects names that refusal."""
    sql = _sql(
        "syn_geom",
        "",
        "shape geometry",
        "shape",
        "SELECT g.shape AS shape FROM control_geom AS g WHERE (",
    )
    _write(tmp_path / "syn_geom", "syn_geom", sql, _GEOM)
    with pytest.raises(StoreRefusal) as caught:
        load_inventory(tmp_path / "syn_geom")
    refusal(caught, "query header invalid")


def test_union_is_not_a_select_tie(tmp_path: Path) -> None:
    sql = _sql(
        "syn_geom",
        "",
        "shape geometry",
        "shape",
        "SELECT g.shape AS shape FROM control_geom AS g "
        "UNION SELECT g.shape AS shape FROM control_geom AS g",
    )
    _write(tmp_path / "syn_geom", "syn_geom", sql, _GEOM)
    with pytest.raises(StoreRefusal) as caught:
        load_inventory(tmp_path / "syn_geom")
    refusal(caught, "query header invalid")


def test_empty_name_does_not_hide_a_later_geometry_column(tmp_path: Path) -> None:
    """An empty name is skipped; the geometry column after it is still tied."""
    sql = _sql(
        "syn_geom",
        "",
        "shape geometry",
        "shape",
        'SELECT g."", g.shape AS shape FROM control_geom AS g',
    )
    folder = tmp_path / "syn_geom"
    _write(folder, "syn_geom", sql, _GEOM)
    inventory = load_inventory(folder)
    loaded = inventory.get("syn_geom")
    assert loaded is not None
    assert loaded.returns[0].name == "shape"


def test_leading_expression_does_not_stop_the_tie(tmp_path: Path) -> None:
    """A non-bare item does not abandon a later geometry column."""
    sql = _sql(
        "syn_geom",
        "",
        "n bigint, shape geometry",
        "shape",
        "SELECT 1 AS n, g.shape AS shape FROM control_geom AS g",
    )
    folder = tmp_path / "syn_geom"
    _write(folder, "syn_geom", sql, _GEOM)
    inventory = load_inventory(folder)
    loaded = inventory.get("syn_geom")
    assert loaded is not None
    assert tuple(item.name for item in loaded.returns) == ("n", "shape")


def test_wrap_refuses_a_bare_column_of_another_name() -> None:
    spec = QuerySpec(
        "syn_geom",
        (),
        (ReturnSpec("shape", "geometry"),),
        ("shape",),
        "SELECT g.other FROM control_geom AS g",
        "ab",
        (),
    )
    with pytest.raises(StoreRefusal) as caught:
        _wrap_geometry("SELECT g.other FROM control_geom AS g", spec, "embedded", None)
    refusal(caught, "forbidden construct")


def test_unknown_engine_refusal_is_exact() -> None:
    """bind refuses an unknown engine before this function can see it."""
    with pytest.raises(StoreRefusal) as caught:
        _geometry_sql(as_any("other"), "g.shape", "shape", None)
    refusal(caught, "unknown engine")
