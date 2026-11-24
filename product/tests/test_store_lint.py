"""Allow-list, order proof and recursive-depth proof."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from product.tests.frames import raised_in

from eii_product.store.lint import lint_inventory
from eii_product.store.protocol import StoreRefusal
from eii_product.store.registry import (
    PACKAGED,
    ContractTable,
    load_inventory,
    packaged_sql_dir,
)

HEADER = (
    "-- name: {name}\n-- params: {params}\n-- returns: {returns}\n-- order: {order}\n"
)
CONTRACT = """
[[tables]]
name = "control_rows"
anchor = "invented control table"
key = {key}

[[tables.columns]]
name = "unit_id"
type = "string"
nullable = false

[[tables.columns]]
name = "label"
type = "string"
nullable = true

[[tables.columns]]
name = "period"
type = "date"
nullable = false

[[tables.columns]]
name = "count_value"
type = "int"
nullable = false

[[tables.columns]]
name = "amount"
type = "decimal(18,6)"
nullable = true

[[tables.columns]]
name = "share"
type = "decimal(18,6)"
nullable = true
"""

ACCEPTED = {
    "syn_select": "SELECT p.unit_id AS unit_id FROM control_rows AS p ORDER BY p.unit_id ASC NULLS LAST",
    "syn_where": "SELECT p.unit_id AS unit_id FROM control_rows AS p WHERE p.label = :label ORDER BY p.unit_id ASC NULLS LAST",
    "syn_with": "WITH picked AS (SELECT p.unit_id AS unit_id FROM control_rows AS p) SELECT picked.unit_id AS unit_id FROM picked ORDER BY picked.unit_id ASC NULLS LAST",
    "syn_group": "SELECT p.unit_id AS unit_id, SUM(p.amount) AS amount FROM control_rows AS p GROUP BY p.unit_id HAVING SUM(p.amount) > 0 ORDER BY p.unit_id ASC NULLS LAST",
    "syn_limit_literal": "SELECT p.unit_id AS unit_id FROM control_rows AS p ORDER BY p.unit_id ASC NULLS LAST LIMIT 1",
    "syn_limit_param": "SELECT p.unit_id AS unit_id FROM control_rows AS p ORDER BY p.unit_id ASC NULLS LAST LIMIT :row_limit",
    "syn_predicates": "SELECT p.unit_id AS unit_id FROM control_rows AS p WHERE p.count_value = 1 AND p.count_value <> 2 AND p.count_value < 3 AND p.count_value <= 4 AND p.count_value > 5 AND p.count_value >= 6 AND p.label IS NULL AND p.label IS NOT NULL AND p.label IN ('SYN-a') AND p.unit_id = ANY(:units) AND p.label BETWEEN 'SYN-a' AND 'SYN-b' ORDER BY p.unit_id ASC NULLS LAST",
    "syn_expressions": "SELECT p.unit_id AS unit_id FROM control_rows AS p WHERE p.count_value + 1 - 1 * 1 = 1 AND NOT (p.label IS NULL) AND COALESCE(p.label, 'SYN-a') = 'SYN-a' AND CAST(p.count_value AS TEXT) = '1' AND p.period = CAST(:on_day AS DATE) ORDER BY p.unit_id ASC NULLS LAST",
    "syn_count": "SELECT p.unit_id AS unit_id, COUNT(p.label) AS count_value FROM control_rows AS p GROUP BY p.unit_id ORDER BY p.unit_id ASC NULLS LAST",
    "syn_count_distinct": "SELECT p.unit_id AS unit_id, COUNT(DISTINCT p.label) AS count_value FROM control_rows AS p GROUP BY p.unit_id ORDER BY p.unit_id ASC NULLS LAST",
    "syn_min_max": "SELECT p.unit_id AS unit_id, MIN(p.amount) AS min_amount, MAX(p.amount) AS max_amount FROM control_rows AS p GROUP BY p.unit_id ORDER BY p.unit_id ASC NULLS LAST",
    "syn_or": "SELECT p.unit_id AS unit_id FROM control_rows AS p WHERE p.label = 'SYN-a' OR p.label IS NULL ORDER BY p.unit_id ASC NULLS LAST",
    "syn_case": "SELECT CASE WHEN p.label IS NULL THEN p.unit_id ELSE p.unit_id END AS unit_id FROM control_rows AS p ORDER BY p.unit_id ASC NULLS LAST",
    "syn_nullif": "SELECT p.unit_id AS unit_id FROM control_rows AS p WHERE NULLIF(p.label, 'SYN-a') IS NULL ORDER BY p.unit_id ASC NULLS LAST",
    "syn_count_star": "SELECT p.unit_id AS unit_id, COUNT(*) AS count_value FROM control_rows AS p GROUP BY p.unit_id ORDER BY p.unit_id ASC NULLS LAST",
    "syn_cast_integer": "SELECT p.unit_id AS unit_id FROM control_rows AS p WHERE CAST(p.count_value AS INTEGER) = 1 ORDER BY p.unit_id ASC NULLS LAST",
    "syn_cast_bigint": "SELECT p.unit_id AS unit_id FROM control_rows AS p WHERE CAST(p.count_value AS BIGINT) = 1 ORDER BY p.unit_id ASC NULLS LAST",
}

GRAPH = """
WITH RECURSIVE g AS (
    SELECT p.unit_id AS unit_id, 0 AS depth
    FROM control_rows AS p
    WHERE p.unit_id = :start
    UNION ALL
    SELECT c.unit_id AS unit_id, g.depth + 1 AS depth
    FROM control_rows AS c
    INNER JOIN g ON c.label = g.unit_id
    WHERE g.depth < 4
)
SELECT g.unit_id AS unit_id, g.depth AS depth
FROM g
ORDER BY g.unit_id ASC NULLS LAST, g.depth ASC NULLS LAST
"""


ACCEPTED_PARAMS = {
    "syn_where": "label text",
    "syn_limit_param": "row_limit bigint",
    "syn_predicates": "units list[text]",
    "syn_expressions": "on_day date",
}
ACCEPTED_RETURNS = {
    "syn_group": "unit_id text, amount numeric",
    "syn_count": "unit_id text, count_value bigint",
    "syn_count_distinct": "unit_id text, count_value bigint",
    "syn_min_max": "unit_id text, min_amount numeric, max_amount numeric",
    "syn_count_star": "unit_id text, count_value bigint",
}


@pytest.mark.parametrize("name", sorted(ACCEPTED))
def test_allow_list_construct_is_accepted(tmp_path: Path, name: str) -> None:
    _lint_one(
        tmp_path,
        name,
        ACCEPTED[name],
        params=ACCEPTED_PARAMS.get(name, ""),
        returns=ACCEPTED_RETURNS.get(name, "unit_id text"),
    )


def test_graph_order_is_unproved(tmp_path: Path) -> None:
    """Key plus depth is not a total order, so every graph_ query is refused."""
    with pytest.raises(StoreRefusal) as caught:
        _lint_one(
            tmp_path,
            "graph_walk",
            GRAPH,
            params="start text",
            returns="unit_id text, depth bigint",
            order="unit_id, depth",
        )
    assert str(caught.value) == "order unproved"


@pytest.mark.parametrize(
    ("name", "sql"),
    [
        (
            "syn_divide",
            "SELECT p.count_value / 2 AS count_value FROM control_rows AS p",
        ),
        (
            "syn_like",
            "SELECT p.unit_id AS unit_id FROM control_rows AS p WHERE p.label LIKE 'SYN%'",
        ),
        (
            "syn_ilike",
            "SELECT p.unit_id AS unit_id FROM control_rows AS p WHERE p.label ILIKE 'syn%'",
        ),
        ("syn_avg", "SELECT AVG(p.amount) AS amount FROM control_rows AS p"),
        (
            "syn_right",
            "SELECT p.unit_id AS unit_id FROM control_rows AS p RIGHT JOIN control_rows AS q ON p.unit_id = q.unit_id",
        ),
        (
            "syn_full",
            "SELECT p.unit_id AS unit_id FROM control_rows AS p FULL JOIN control_rows AS q ON p.unit_id = q.unit_id",
        ),
        ("syn_schema", "SELECT p.unit_id AS unit_id FROM public.control_rows AS p"),
        ("syn_unknown_table", "SELECT p.unit_id AS unit_id FROM other_rows AS p"),
        (
            "syn_cast",
            "SELECT CAST(p.count_value AS DOUBLE) AS count_value FROM control_rows AS p",
        ),
        (
            "syn_in_subquery",
            "SELECT p.unit_id AS unit_id FROM control_rows AS p WHERE p.unit_id IN (SELECT q.unit_id FROM control_rows AS q)",
        ),
        (
            "syn_any_column",
            "SELECT p.unit_id AS unit_id FROM control_rows AS p WHERE p.unit_id = ANY(p.label)",
        ),
        (
            "syn_limit_expr",
            "SELECT p.unit_id AS unit_id FROM control_rows AS p ORDER BY p.unit_id ASC NULLS LAST LIMIT 1 + 1",
        ),
        ("syn_bare_column", "SELECT unit_id AS unit_id FROM control_rows AS p"),
        ("syn_distinct", "SELECT DISTINCT p.unit_id AS unit_id FROM control_rows AS p"),
        ("syn_star", "SELECT * FROM control_rows AS p"),
        (
            "syn_union_distinct",
            "SELECT p.unit_id AS unit_id FROM control_rows AS p UNION SELECT q.unit_id AS unit_id FROM control_rows AS q",
        ),
        ("syn_create", "CREATE TABLE syn_rows (unit_id TEXT)"),
        (
            "syn_cast_operator",
            "SELECT p.count_value::BIGINT AS count_value FROM control_rows AS p",
        ),
        (
            "syn_comma_join",
            "SELECT p.unit_id AS unit_id FROM control_rows AS p, control_rows AS q",
        ),
    ],
)
def test_forbidden_construct_is_refused(tmp_path: Path, name: str, sql: str) -> None:
    with pytest.raises(StoreRefusal) as caught:
        _lint_one(tmp_path, name, sql)
    assert str(caught.value) == "forbidden construct"


@pytest.mark.parametrize(
    ("name", "sql"),
    [
        (
            "syn_semicolon",
            "SELECT p.unit_id AS unit_id FROM control_rows AS p; SELECT p.unit_id FROM control_rows AS p",
        ),
        ("syn_hash", "SELECT #1 AS unit_id FROM control_rows AS p"),
    ],
)
def test_parse_invalid_is_refused(tmp_path: Path, name: str, sql: str) -> None:
    with pytest.raises(StoreRefusal) as caught:
        _lint_one(tmp_path, name, sql)
    assert str(caught.value) == "parse invalid"


@pytest.mark.parametrize(
    ("name", "sql", "key"),
    [
        (
            "syn_no_direction",
            "SELECT p.unit_id AS unit_id FROM control_rows AS p ORDER BY p.unit_id NULLS LAST",
            '["unit_id"]',
        ),
        (
            "syn_no_nulls",
            "SELECT p.unit_id AS unit_id FROM control_rows AS p ORDER BY p.unit_id ASC",
            '["unit_id"]',
        ),
        (
            "syn_order_differs",
            "SELECT p.unit_id AS unit_id, p.label AS label FROM control_rows AS p "
            "ORDER BY p.label ASC NULLS LAST",
            '["unit_id"]',
        ),
        (
            "syn_incomplete_key",
            "SELECT p.unit_id AS unit_id, p.label AS label FROM control_rows AS p ORDER BY p.unit_id ASC NULLS LAST",
            '["unit_id", "label"]',
        ),
        (
            "syn_join",
            "SELECT p.unit_id AS unit_id FROM control_rows AS p INNER JOIN control_rows AS q ON p.unit_id = q.unit_id ORDER BY p.unit_id ASC NULLS LAST",
            '["unit_id"]',
        ),
        (
            "syn_union_all",
            "SELECT p.unit_id AS unit_id FROM control_rows AS p UNION ALL SELECT q.unit_id AS unit_id FROM control_rows AS q ORDER BY 1 ASC NULLS LAST",
            '["unit_id"]',
        ),
        (
            "syn_no_key",
            "SELECT p.unit_id AS unit_id FROM control_rows AS p ORDER BY p.unit_id ASC NULLS LAST",
            "[]",
        ),
    ],
)
def test_unproved_order_is_refused(
    tmp_path: Path, name: str, sql: str, key: str
) -> None:
    wide = name in {"syn_incomplete_key", "syn_order_differs"}
    returns = "unit_id text, label text" if wide else "unit_id text"
    order = "unit_id, label" if name == "syn_order_differs" else "unit_id"
    with pytest.raises(StoreRefusal) as caught:
        _lint_one(tmp_path, name, sql, returns=returns, order=order, key=key)
    assert str(caught.value) == "order unproved"


NO_DEPTH = """
WITH RECURSIVE g AS (
    SELECT p.unit_id AS unit_id FROM control_rows AS p WHERE p.unit_id = :start
    UNION ALL
    SELECT c.unit_id AS unit_id FROM control_rows AS c
    INNER JOIN g ON c.label = g.unit_id
)
SELECT g.unit_id AS unit_id FROM g ORDER BY g.unit_id ASC NULLS LAST
"""


@pytest.mark.parametrize(
    "sql",
    [
        NO_DEPTH,
        GRAPH.replace("0 AS depth", "1 AS depth"),
        GRAPH.replace("g.depth + 1", "g.depth + 2"),
        GRAPH.replace("g.depth < 4", "g.depth < 5"),
        GRAPH.replace("WHERE g.depth < 4", "WHERE g.depth < 4 OR c.unit_id = :start"),
        GRAPH.replace("    WHERE g.depth < 4\n", ""),
    ],
)
def test_unproved_depth_is_refused(tmp_path: Path, sql: str) -> None:
    name = "graph_bad"
    has_depth = "AS depth" in sql
    returns = "unit_id text, depth bigint" if has_depth else "unit_id text"
    order = "unit_id, depth" if has_depth else "unit_id"
    with pytest.raises(StoreRefusal) as caught:
        _lint_one(
            tmp_path, name, sql, params="start text", returns=returns, order=order
        )
    assert str(caught.value) == "depth unproved"


def test_recursion_outside_graph_is_refused(tmp_path: Path) -> None:
    with pytest.raises(StoreRefusal) as caught:
        _lint_one(
            tmp_path,
            "syn_walk",
            GRAPH,
            params="start text",
            returns="unit_id text, depth bigint",
            order="unit_id, depth",
        )
    assert str(caught.value) == "depth unproved"


def test_placeholder_inside_a_literal_is_forbidden(tmp_path: Path) -> None:
    sql = "SELECT p.unit_id AS unit_id FROM control_rows AS p WHERE p.label = 'keep :label'"
    with pytest.raises(StoreRefusal) as caught:
        _lint_one(tmp_path, "syn_literal", sql, params="label text")
    assert str(caught.value) == "forbidden construct"


def test_renaming_cte_does_not_prove_order(tmp_path: Path) -> None:
    """An order column renamed in a CTE is not the key it is spelled as."""
    sql = (
        "WITH c AS (SELECT p.label AS unit_id FROM control_rows AS p) "
        "SELECT c.unit_id AS unit_id FROM c ORDER BY c.unit_id ASC NULLS LAST"
    )
    with pytest.raises(StoreRefusal) as caught:
        _lint_one(tmp_path, "syn_cte_rename", sql)
    assert str(caught.value) == "order unproved"


def test_unrenamed_cte_key_is_accepted(tmp_path: Path) -> None:
    """A CTE may prove order when the ordered columns are the key, unrenamed."""
    sql = (
        "WITH c AS (SELECT p.unit_id AS unit_id FROM control_rows AS p) "
        "SELECT c.unit_id AS unit_id FROM c ORDER BY c.unit_id ASC NULLS LAST"
    )
    _lint_one(tmp_path, "syn_cte_key", sql)


@pytest.mark.parametrize(
    ("name", "sql"),
    [
        (
            "syn_positional",
            "SELECT p.unit_id AS unit_id FROM control_rows AS p WHERE p.label = ? "
            "ORDER BY p.unit_id ASC NULLS LAST",
        ),
        (
            "syn_sum_distinct",
            "SELECT p.unit_id AS unit_id, SUM(DISTINCT p.amount) AS amount "
            "FROM control_rows AS p GROUP BY p.unit_id ORDER BY p.unit_id ASC NULLS LAST",
        ),
        (
            "syn_min_distinct",
            "SELECT p.unit_id AS unit_id, MIN(DISTINCT p.amount) AS amount "
            "FROM control_rows AS p GROUP BY p.unit_id ORDER BY p.unit_id ASC NULLS LAST",
        ),
        (
            "syn_percent_literal",
            "SELECT p.unit_id AS unit_id FROM control_rows AS p WHERE p.label = '50%' "
            "ORDER BY p.unit_id ASC NULLS LAST",
        ),
        (
            "syn_quoted_colon",
            'SELECT p.unit_id AS unit_id FROM control_rows AS p WHERE p.":label" IS NULL '
            "ORDER BY p.unit_id ASC NULLS LAST",
        ),
        (
            "syn_cast_int",
            "SELECT p.unit_id AS unit_id FROM control_rows AS p "
            "WHERE CAST(p.count_value AS INT) = 1 ORDER BY p.unit_id ASC NULLS LAST",
        ),
        (
            "syn_modulo",
            "SELECT MOD(p.count_value, 2) AS count_value FROM control_rows AS p",
        ),
        (
            "syn_distinct_on",
            "SELECT DISTINCT ON (p.unit_id) p.unit_id AS unit_id FROM control_rows AS p",
        ),
        (
            "syn_lateral",
            "SELECT p.unit_id AS unit_id FROM control_rows AS p "
            "INNER JOIN LATERAL (SELECT q.unit_id AS unit_id FROM control_rows AS q) AS q "
            "ON p.unit_id = q.unit_id",
        ),
        (
            "syn_window",
            "SELECT p.unit_id AS unit_id, "
            "SUM(p.count_value) OVER () AS count_value FROM control_rows AS p",
        ),
        (
            "syn_filter",
            "SELECT SUM(p.count_value) FILTER (WHERE p.label IS NOT NULL) "
            "AS count_value FROM control_rows AS p",
        ),
        (
            "syn_qualify",
            "SELECT p.unit_id AS unit_id FROM control_rows AS p "
            "QUALIFY p.unit_id IS NOT NULL",
        ),
        (
            "syn_pivot",
            "SELECT p.unit_id AS unit_id FROM control_rows AS p "
            "PIVOT (SUM(p.count_value) FOR p.label IN ('SYN-a')) AS pivoted",
        ),
        (
            "syn_asof",
            "SELECT p.unit_id AS unit_id FROM control_rows AS p "
            "ASOF JOIN control_rows AS q ON p.unit_id = q.unit_id",
        ),
        (
            "syn_spatial",
            "SELECT ST_AsText(p.label) AS unit_id FROM control_rows AS p",
        ),
        (
            "syn_grid",
            "SELECT h3_cell_to_parent(p.count_value, 1) AS count_value "
            "FROM control_rows AS p",
        ),
        (
            "syn_unknown_function",
            "SELECT syn_no_such(p.unit_id) AS unit_id FROM control_rows AS p",
        ),
        ("syn_now", "SELECT NOW() AS period FROM control_rows AS p"),
        (
            "syn_current_date",
            "SELECT CURRENT_DATE AS period FROM control_rows AS p",
        ),
        ("syn_random", "SELECT RANDOM() AS amount FROM control_rows AS p"),
        (
            "syn_insert",
            "INSERT INTO control_rows VALUES ('SYN-z', 'SYN-z', DATE '2000-01-01', 1, 1)",
        ),
        ("syn_update", "UPDATE control_rows SET label = 'SYN-z'"),
        ("syn_delete", "DELETE FROM control_rows"),
        ("syn_copy", "COPY control_rows TO 'syn.csv'"),
        ("syn_install", "INSTALL spatial"),
        ("syn_pragma", "PRAGMA database_size"),
        ("syn_set", "SET threads = 1"),
    ],
)
def test_named_construct_is_forbidden(tmp_path: Path, name: str, sql: str) -> None:
    with pytest.raises(StoreRefusal) as caught:
        _lint_one(tmp_path, name, sql)
    assert str(caught.value) == "forbidden construct"


@pytest.mark.parametrize(
    ("name", "sql"),
    [
        ("syn_attach", "ATTACH 'syn.db' AS syn"),
        ("syn_load", "LOAD spatial"),
    ],
)
def test_named_construct_is_parse_invalid(tmp_path: Path, name: str, sql: str) -> None:
    with pytest.raises(StoreRefusal) as caught:
        _lint_one(tmp_path, name, sql)
    assert str(caught.value) == "parse invalid"


def test_select_hash_parses_on_one_dialect_and_is_refused(tmp_path: Path) -> None:
    """DuckDB accepts the hash form; PostgreSQL's parser does not. The lint refuses it."""
    import sqlglot

    sql = "SELECT #1 AS unit_id FROM control_rows AS p"
    sqlglot.parse(sql, read="duckdb", error_level=sqlglot.ErrorLevel.RAISE)
    with pytest.raises(sqlglot.errors.SqlglotError):
        sqlglot.parse(sql, read="postgres", error_level=sqlglot.ErrorLevel.RAISE)
    with pytest.raises(StoreRefusal) as caught:
        _lint_one(tmp_path, "syn_hash_one", sql)
    assert str(caught.value) == "parse invalid"


@pytest.mark.parametrize("type_name", ["real", "double precision", "float8", "float"])
def test_contract_type_outside_the_vocabulary_is_refused(
    tmp_path: Path, type_name: str
) -> None:
    root = tmp_path / "typed"
    root.mkdir()
    (root / "__init__.py").write_text('"""marker"""\n', encoding="utf-8")
    (root / "syn_typed.sql").write_text(
        "-- name: syn_typed\n-- params:\n-- returns: unit_id text\n-- order: unit_id\n"
        "SELECT p.unit_id AS unit_id FROM control_rows AS p "
        "ORDER BY p.unit_id ASC NULLS LAST\n",
        encoding="utf-8",
    )
    (root / "syn_typed.toml").write_text(
        '[[tables]]\nname = "control_rows"\nanchor = "invented control table"\n'
        'key = ["unit_id"]\n\n[[tables.columns]]\nname = "unit_id"\n'
        f'type = "{type_name}"\nnullable = false\n',
        encoding="utf-8",
    )
    with pytest.raises(StoreRefusal) as caught:
        load_inventory(root)
    assert str(caught.value) == "query header invalid"


def test_sum_of_an_approximate_type_is_refused() -> None:
    """The lint refuses a sum of an approximate spelling even if a contract carried one."""
    from eii_product.store.registry import (
        ContractColumn,
        ContractTable,
        Inventory,
        QuerySpec,
        ReturnSpec,
    )

    spec = QuerySpec(
        "syn_sum_real",
        (),
        (ReturnSpec("share", "numeric"),),
        ("share",),
        "SELECT SUM(p.share) AS share FROM control_rows AS p "
        "ORDER BY p.share ASC NULLS LAST",
        "ab",
        (
            ContractTable(
                "control_rows",
                "invented control table",
                ("share",),
                (ContractColumn("share", "real", True),),
            ),
        ),
    )
    with pytest.raises(StoreRefusal) as caught:
        lint_inventory(Inventory((spec,), object(), ()))
    assert str(caught.value) == "forbidden construct"


@pytest.mark.parametrize(
    ("name", "sql"),
    [
        (
            "syn_cast_int4",
            "SELECT p.unit_id AS unit_id FROM control_rows AS p "
            "WHERE CAST(p.count_value AS INT4) = 1 ORDER BY p.unit_id ASC NULLS LAST",
        ),
        (
            "syn_cast_int8",
            "SELECT p.unit_id AS unit_id FROM control_rows AS p "
            "WHERE CAST(p.count_value AS INT8) = 1 ORDER BY p.unit_id ASC NULLS LAST",
        ),
        (
            "syn_cast_string",
            "SELECT p.unit_id AS unit_id FROM control_rows AS p "
            "WHERE CAST(p.count_value AS STRING) = '1' ORDER BY p.unit_id ASC NULLS LAST",
        ),
        (
            "syn_cast_comment",
            "SELECT p.unit_id AS unit_id FROM control_rows AS p "
            "WHERE CAST(p.count_value AS /* c */ INTEGER) = 1 "
            "ORDER BY p.unit_id ASC NULLS LAST",
        ),
    ],
)
def test_cast_type_word_is_one_of_the_four(tmp_path: Path, name: str, sql: str) -> None:
    """The type word is read from the query text. Aliases and a comment are refused."""
    with pytest.raises(StoreRefusal) as caught:
        _lint_one(tmp_path, name, sql, params="")
    assert str(caught.value) == "forbidden construct"


def test_count_distinct_of_two_arguments_is_refused(tmp_path: Path) -> None:
    sql = (
        "SELECT COUNT(DISTINCT p.unit_id, p.label) AS unit_id FROM control_rows AS p "
        "ORDER BY p.unit_id ASC NULLS LAST"
    )
    with pytest.raises(StoreRefusal) as caught:
        _lint_one(tmp_path, "syn_count_distinct_pair", sql, params="")
    assert str(caught.value) == "forbidden construct"


def test_undeclared_placeholder_is_refused(tmp_path: Path) -> None:
    sql = (
        "SELECT p.unit_id AS unit_id FROM control_rows AS p WHERE p.label = :label "
        "ORDER BY p.unit_id ASC NULLS LAST"
    )
    with pytest.raises(StoreRefusal) as caught:
        _lint_one(tmp_path, "syn_undeclared", sql, params="")
    assert str(caught.value) == "forbidden construct"


def test_unused_parameter_is_refused(tmp_path: Path) -> None:
    sql = (
        "SELECT p.unit_id AS unit_id FROM control_rows AS p "
        "ORDER BY p.unit_id ASC NULLS LAST"
    )
    with pytest.raises(StoreRefusal) as caught:
        _lint_one(tmp_path, "syn_unused", sql, params="label text")
    assert str(caught.value) == "forbidden construct"


@pytest.mark.parametrize(
    ("name", "sql", "returns"),
    [
        (
            "syn_project_name",
            "SELECT p.label AS label FROM control_rows AS p "
            "ORDER BY p.unit_id ASC NULLS LAST",
            "unit_id text",
        ),
        (
            "syn_project_order",
            "SELECT p.label AS label, p.unit_id AS unit_id FROM control_rows AS p "
            "ORDER BY p.unit_id ASC NULLS LAST",
            "unit_id text, label text",
        ),
        (
            "syn_project_count",
            "SELECT p.unit_id AS unit_id, p.label AS label FROM control_rows AS p "
            "ORDER BY p.unit_id ASC NULLS LAST",
            "unit_id text",
        ),
    ],
)
def test_projection_must_match_returns(
    tmp_path: Path, name: str, sql: str, returns: str
) -> None:
    """Names, order and count of the projection are held against the header."""
    with pytest.raises(StoreRefusal) as caught:
        _lint_one(tmp_path, name, sql, params="", returns=returns, order="unit_id")
    assert str(caught.value) == "forbidden construct"


def test_row_limit_parameter_must_be_an_integer(tmp_path: Path) -> None:
    sql = (
        "SELECT p.unit_id AS unit_id FROM control_rows AS p "
        "ORDER BY p.unit_id ASC NULLS LAST LIMIT :label"
    )
    with pytest.raises(StoreRefusal) as caught:
        _lint_one(tmp_path, "syn_limit_text", sql, params="label text")
    assert str(caught.value) == "forbidden construct"


def test_float_literal_is_refused(tmp_path: Path) -> None:
    sql = (
        "SELECT p.unit_id AS unit_id FROM control_rows AS p "
        "WHERE p.count_value = 1e0 ORDER BY p.unit_id ASC NULLS LAST"
    )
    with pytest.raises(StoreRefusal) as caught:
        _lint_one(tmp_path, "syn_float", sql, params="")
    assert str(caught.value) == "forbidden construct"


_ORDERED = "ORDER BY p.unit_id ASC NULLS LAST"
GEOMETRY = {
    "syn_geom_where": (
        "SELECT p.unit_id AS unit_id FROM control_rows AS p "
        f"WHERE p.shape IS NULL {_ORDERED}",
        "unit_id text",
    ),
    "syn_geom_join": (
        "SELECT p.unit_id AS unit_id FROM control_rows AS p "
        "INNER JOIN control_rows AS q ON p.unit_id = q.shape "
        f"{_ORDERED}",
        "unit_id text",
    ),
    "syn_geom_order": (
        "SELECT p.unit_id AS unit_id, p.shape FROM control_rows AS p ORDER BY p.shape ASC NULLS LAST",
        "unit_id text, shape geometry",
    ),
    "syn_geom_group": (
        "SELECT p.shape FROM control_rows AS p GROUP BY p.shape "
        "ORDER BY p.shape ASC NULLS LAST",
        "shape geometry",
    ),
    "syn_geom_agg": (
        "SELECT COUNT(p.shape) AS unit_id FROM control_rows AS p " + _ORDERED,
        "unit_id text",
    ),
    "syn_geom_cast": (
        "SELECT CAST(p.shape AS TEXT) AS unit_id FROM control_rows AS p " + _ORDERED,
        "unit_id text",
    ),
    "syn_geom_expr": (
        "SELECT COALESCE(p.shape, p.shape) AS unit_id FROM control_rows AS p "
        + _ORDERED,
        "unit_id text",
    ),
}


@pytest.mark.parametrize("name", sorted(GEOMETRY))
def test_geometry_column_is_refused_outside_its_one_place(
    tmp_path: Path, name: str
) -> None:
    sql, returns = GEOMETRY[name]
    order = "shape" if "shape" in returns and "unit_id" not in returns else "unit_id"
    if name == "syn_geom_order":
        order = "shape"
    if name == "syn_geom_group":
        order = "shape"
    with pytest.raises(StoreRefusal) as caught:
        _lint_one(
            tmp_path,
            name,
            sql,
            params="",
            returns=returns,
            order=order,
            shape=True,
        )
    assert str(caught.value) == "forbidden construct"


def test_geometry_column_under_another_return_type_is_refused() -> None:
    """The loader would refuse this header. The lint refuses it on a hand-built spec."""
    from eii_product.store.registry import (
        ContractColumn,
        ContractTable,
        Inventory,
        QuerySpec,
        ReturnSpec,
    )

    spec = QuerySpec(
        "syn_geom_text",
        (),
        (ReturnSpec("shape", "text"),),
        ("shape",),
        "SELECT p.shape FROM control_rows AS p ORDER BY p.shape ASC NULLS LAST",
        "ab",
        (
            ContractTable(
                "control_rows",
                "invented control table",
                ("shape",),
                (ContractColumn("shape", "geometry", True),),
            ),
        ),
    )
    with pytest.raises(StoreRefusal) as caught:
        lint_inventory(Inventory((spec,), object(), ()))
    assert str(caught.value) == "forbidden construct"


def test_bare_geometry_column_is_accepted(tmp_path: Path) -> None:
    sql = (
        "SELECT p.unit_id AS unit_id, p.shape FROM control_rows AS p "
        "ORDER BY p.unit_id ASC NULLS LAST"
    )
    _lint_one(
        tmp_path,
        "syn_geom_ok",
        sql,
        params="",
        returns="unit_id text, shape geometry",
        order="unit_id",
        shape=True,
    )


def test_every_packaged_query_passes_the_lint() -> None:
    """The count linted is the count of query files in the packaged folder."""
    sql_count = len(list(packaged_sql_dir().glob("*.sql")))
    validated = lint_inventory(PACKAGED)
    assert len(validated.queries) == sql_count


def test_planted_forbidden_file_in_packaged_copy_fails(tmp_path: Path) -> None:
    folder = tmp_path / "packaged"
    shutil.copytree(packaged_sql_dir(), folder)
    _write(
        folder,
        "syn_div",
        "SELECT p.count_value / 1 AS count_value FROM control_rows AS p",
    )
    with pytest.raises(StoreRefusal) as caught:
        lint_inventory(load_inventory(folder))
    assert str(caught.value) == "forbidden construct"
    twin = tmp_path / "twin"
    shutil.copytree(packaged_sql_dir(), twin)
    _write(
        twin,
        "syn_ok",
        "SELECT p.unit_id AS unit_id FROM control_rows AS p ORDER BY p.unit_id ASC NULLS LAST",
    )
    lint_inventory(load_inventory(twin))


@pytest.mark.parametrize(
    ("name", "sql", "params", "returns"),
    [
        (
            "syn_word_coalesce",
            "SELECT COALESCE(p.label, 'SYN-a') AS unit_id FROM control_rows AS p "
            "ORDER BY p.unit_id ASC NULLS LAST",
            "",
            "unit_id text",
        ),
        (
            "syn_word_nullif",
            "SELECT NULLIF(p.label, 'SYN-a') AS unit_id FROM control_rows AS p "
            "ORDER BY p.unit_id ASC NULLS LAST",
            "",
            "unit_id text",
        ),
        (
            "syn_word_cast",
            "SELECT p.unit_id AS unit_id FROM control_rows AS p "
            "WHERE CAST(p.count_value AS INTEGER) = 1 "
            "ORDER BY p.unit_id ASC NULLS LAST",
            "",
            "unit_id text",
        ),
        (
            "syn_word_sum",
            "SELECT p.unit_id AS unit_id, SUM(p.amount) AS amount "
            "FROM control_rows AS p GROUP BY p.unit_id "
            "ORDER BY p.unit_id ASC NULLS LAST",
            "",
            "unit_id text, amount numeric",
        ),
        (
            "syn_word_count",
            "SELECT p.unit_id AS unit_id, COUNT(p.label) AS count_value "
            "FROM control_rows AS p GROUP BY p.unit_id "
            "ORDER BY p.unit_id ASC NULLS LAST",
            "",
            "unit_id text, count_value bigint",
        ),
        (
            "syn_word_min",
            "SELECT p.unit_id AS unit_id, MIN(p.amount) AS amount "
            "FROM control_rows AS p GROUP BY p.unit_id "
            "ORDER BY p.unit_id ASC NULLS LAST",
            "",
            "unit_id text, amount numeric",
        ),
        (
            "syn_word_max",
            "SELECT p.unit_id AS unit_id, MAX(p.amount) AS amount "
            "FROM control_rows AS p GROUP BY p.unit_id "
            "ORDER BY p.unit_id ASC NULLS LAST",
            "",
            "unit_id text, amount numeric",
        ),
        (
            "syn_word_in",
            "SELECT p.unit_id AS unit_id FROM control_rows AS p "
            "WHERE p.label IN ('SYN-a') ORDER BY p.unit_id ASC NULLS LAST",
            "",
            "unit_id text",
        ),
        (
            "syn_word_any",
            "SELECT p.unit_id AS unit_id FROM control_rows AS p "
            "WHERE p.unit_id = ANY(:units) ORDER BY p.unit_id ASC NULLS LAST",
            "units list[text]",
            "unit_id text",
        ),
        (
            "syn_word_as",
            "WITH picked AS (SELECT p.unit_id AS unit_id FROM control_rows AS p) "
            "SELECT picked.unit_id AS unit_id FROM picked "
            "ORDER BY picked.unit_id ASC NULLS LAST",
            "",
            "unit_id text",
        ),
        (
            "syn_word_not",
            "SELECT p.unit_id AS unit_id FROM control_rows AS p "
            "WHERE NOT (p.label IS NULL) ORDER BY p.unit_id ASC NULLS LAST",
            "",
            "unit_id text",
        ),
    ],
)
def test_allowed_call_word_is_accepted(
    tmp_path: Path, name: str, sql: str, params: str, returns: str
) -> None:
    """Every admitted word followed by a parenthesis has a passing fixture."""
    order = "unit_id"
    _lint_one(tmp_path, name, sql, params=params, returns=returns, order=order)


@pytest.mark.parametrize(
    ("name", "sql"),
    [
        (
            "syn_ifnull",
            "SELECT IFNULL(p.label, 'SYN-a') AS unit_id FROM control_rows AS p "
            "ORDER BY p.unit_id ASC NULLS LAST",
        ),
        (
            "syn_nvl",
            "SELECT NVL(p.label, 'SYN-a') AS unit_id FROM control_rows AS p "
            "ORDER BY p.unit_id ASC NULLS LAST",
        ),
        (
            "syn_if",
            "SELECT IF(p.label IS NULL, p.unit_id, p.unit_id) AS unit_id "
            "FROM control_rows AS p ORDER BY p.unit_id ASC NULLS LAST",
        ),
        (
            "syn_qualified_call",
            "SELECT ext.COALESCE(p.label, 'SYN-a') AS unit_id FROM control_rows AS p "
            "ORDER BY p.unit_id ASC NULLS LAST",
        ),
        (
            "syn_unknown_call",
            "SELECT syn_no_such(p.unit_id) AS unit_id FROM control_rows AS p "
            "ORDER BY p.unit_id ASC NULLS LAST",
        ),
        (
            "syn_call_comment",
            "SELECT COALESCE /* c */ (p.label, 'SYN-a') AS unit_id "
            "FROM control_rows AS p ORDER BY p.unit_id ASC NULLS LAST",
        ),
    ],
)
def test_unlisted_function_word_is_forbidden(
    tmp_path: Path, name: str, sql: str
) -> None:
    """A word before a parenthesis that the allow-list does not name is refused."""
    with pytest.raises(StoreRefusal) as caught:
        _lint_one(tmp_path, name, sql, params="")
    assert str(caught.value) == "forbidden construct"


def test_select_without_order_is_unproved(tmp_path: Path) -> None:
    """A proved select with no ORDER BY is order unproved at that check."""
    sql = "SELECT p.unit_id AS unit_id FROM control_rows AS p"
    with pytest.raises(StoreRefusal) as caught:
        _lint_one(tmp_path, "syn_no_order", sql, params="")
    assert str(caught.value) == "order unproved"
    assert raised_in(caught, "_order")


def test_recursive_order_missing_the_key_is_unproved(tmp_path: Path) -> None:
    """A recursive read whose order omits the key is refused before the depth check."""
    sql = (
        "WITH RECURSIVE g AS ("
        "SELECT p.unit_id AS unit_id, 0 AS depth FROM control_rows AS p "
        "UNION ALL "
        "SELECT c.unit_id AS unit_id, g.depth + 1 AS depth "
        "FROM control_rows AS c INNER JOIN g ON c.label = g.unit_id "
        "WHERE g.depth < 4) "
        "SELECT g.depth AS depth FROM g ORDER BY g.depth ASC NULLS LAST"
    )
    with pytest.raises(StoreRefusal) as caught:
        _lint_one(
            tmp_path,
            "syn_recursive_key",
            sql,
            params="",
            returns="depth bigint",
            order="depth",
        )
    assert str(caught.value) == "order unproved"


def test_group_order_that_is_not_the_group_is_unproved(tmp_path: Path) -> None:
    """Ordering by the key while grouping by another column is order unproved."""
    sql = (
        "SELECT p.unit_id AS unit_id, p.label AS label FROM control_rows AS p "
        "GROUP BY p.label ORDER BY p.unit_id ASC NULLS LAST"
    )
    with pytest.raises(StoreRefusal) as caught:
        _lint_one(
            tmp_path,
            "syn_group_order",
            sql,
            params="",
            returns="unit_id text, label text",
            order="unit_id",
        )
    assert str(caught.value) == "order unproved"


def test_order_with_no_base_table_is_unproved(tmp_path: Path) -> None:
    """An order that names no contract table is order unproved."""
    sql = "SELECT 'SYN-a' AS unit_id ORDER BY p.unit_id ASC NULLS LAST"
    with pytest.raises(StoreRefusal) as caught:
        _lint_one(tmp_path, "syn_no_base", sql, params="")
    assert str(caught.value) == "order unproved"


def test_order_by_ordinal_is_unproved(tmp_path: Path) -> None:
    """An ordinal order item is not a column, so the order is unproved."""
    sql = "SELECT p.unit_id AS unit_id FROM control_rows AS p ORDER BY 1 ASC NULLS LAST"
    with pytest.raises(StoreRefusal) as caught:
        _lint_one(tmp_path, "syn_ordinal", sql, params="")
    assert str(caught.value) == "order unproved"
    assert raised_in(caught, "_column_name")


def test_text_column_is_not_geometry_because_another_table_says_so() -> None:
    """A text column keeps its own type when another table uses the same name."""
    from eii_product.store.registry import (
        ContractColumn,
        ContractTable,
        Inventory,
        QuerySpec,
        ReturnSpec,
    )

    tables = (
        ContractTable(
            "control_text",
            "invented control table",
            ("shape",),
            (ContractColumn("shape", "string", True),),
        ),
        ContractTable(
            "control_geom",
            "invented control table",
            ("shape",),
            (ContractColumn("shape", "geometry", True),),
        ),
    )
    accepted = QuerySpec(
        "syn_text",
        (),
        (ReturnSpec("shape", "text"),),
        ("shape",),
        "SELECT p.shape FROM control_text AS p ORDER BY p.shape ASC NULLS LAST",
        "ab",
        tables,
    )
    lint_inventory(Inventory((accepted,), object(), ()))
    refused = QuerySpec(
        "syn_wrap",
        (),
        (ReturnSpec("shape", "geometry"),),
        ("shape",),
        "SELECT p.shape FROM control_text AS p ORDER BY p.shape ASC NULLS LAST",
        "ab",
        tables,
    )
    with pytest.raises(StoreRefusal) as caught:
        lint_inventory(Inventory((refused,), object(), ()))
    assert str(caught.value) == "forbidden construct"


def test_sum_uses_the_table_the_alias_names() -> None:
    """SUM of a text column stays allowed when only another table's column is approximate."""
    from eii_product.store.registry import (
        ContractColumn,
        ContractTable,
        Inventory,
        QuerySpec,
        ReturnSpec,
    )

    text = ContractTable(
        "control_text",
        "invented control table",
        ("amount",),
        (ContractColumn("amount", "string", True),),
    )
    real = ContractTable(
        "control_real",
        "invented control table",
        ("amount",),
        (ContractColumn("amount", "real", True),),
    )
    text_sum = QuerySpec(
        "syn_sum_text",
        (),
        (ReturnSpec("amount", "numeric"),),
        ("amount",),
        "SELECT SUM(p.amount) AS amount FROM control_text AS p "
        "ORDER BY p.amount ASC NULLS LAST",
        "ab",
        (real, text),
    )
    lint_inventory(Inventory((text_sum,), object(), ()))
    real_sum = QuerySpec(
        "syn_sum_real",
        (),
        (ReturnSpec("amount", "numeric"),),
        ("amount",),
        "SELECT SUM(g.amount) AS amount FROM control_real AS g "
        "ORDER BY g.amount ASC NULLS LAST",
        "ab",
        (text, real),
    )
    with pytest.raises(StoreRefusal) as caught:
        lint_inventory(Inventory((real_sum,), object(), ()))
    assert str(caught.value) == "forbidden construct"


def test_own_scope_outer_approximate_sum_is_refused() -> None:
    """A CTE exact alias must not hide an approximate SUM in the outer select."""
    text, real, _geom, _rows = _scope_tables()
    sql = (
        "WITH cover AS (SELECT g.unit_id AS unit_id FROM control_text AS g) "
        "SELECT SUM(g.amount) AS amount FROM control_real AS g"
    )
    with pytest.raises(StoreRefusal) as caught:
        _lint_scope(sql, (("amount", "numeric"),), (), (text, real))
    assert str(caught.value) == "forbidden construct"


def test_own_scope_outer_exact_sum_reaches_the_order_proof() -> None:
    """A CTE approximate alias must not refuse an exact SUM in the outer select."""
    text, real, _geom, _rows = _scope_tables()
    sql = (
        "WITH cover AS (SELECT g.unit_id AS unit_id FROM control_real AS g) "
        "SELECT SUM(g.amount) AS amount FROM control_text AS g"
    )
    with pytest.raises(StoreRefusal) as caught:
        _lint_scope(sql, (("amount", "numeric"),), (), (text, real))
    assert str(caught.value) == "order unproved"
    assert raised_in(caught, "_order")


def test_own_scope_earlier_approximate_sum_is_refused() -> None:
    """A later exact alias must not hide an approximate SUM in an earlier scope."""
    text, real, _geom, _rows = _scope_tables()
    sql = (
        "WITH summed AS ("
        "SELECT g.unit_id AS unit_id, SUM(g.amount) AS amount "
        "FROM control_real AS g GROUP BY g.unit_id"
        "), exact AS ("
        "SELECT g.unit_id AS unit_id FROM control_text AS g"
        ") SELECT summed.unit_id AS unit_id FROM summed "
        "ORDER BY summed.unit_id ASC NULLS LAST"
    )
    with pytest.raises(StoreRefusal) as caught:
        _lint_scope(sql, (("unit_id", "text"),), ("unit_id",), (text, real))
    assert str(caught.value) == "forbidden construct"


def test_own_scope_outer_geometry_predicate_is_refused() -> None:
    """A CTE text alias must not hide a geometry column in the outer predicate."""
    text, _real, geom, _rows = _scope_tables()
    sql = (
        "WITH cover AS (SELECT g.unit_id AS unit_id FROM control_text AS g) "
        "SELECT g.unit_id AS unit_id FROM control_geom AS g "
        "WHERE g.shape IS NULL ORDER BY g.unit_id ASC NULLS LAST"
    )
    with pytest.raises(StoreRefusal) as caught:
        _lint_scope(sql, (("unit_id", "text"),), ("unit_id",), (text, geom))
    assert str(caught.value) == "forbidden construct"


def test_own_scope_earlier_geometry_predicate_is_refused() -> None:
    """A later text alias must not hide a geometry predicate in an earlier scope."""
    text, _real, geom, _rows = _scope_tables()
    sql = (
        "WITH hidden AS ("
        "SELECT g.unit_id AS unit_id FROM control_geom AS g WHERE g.shape IS NULL"
        "), cover AS ("
        "SELECT g.unit_id AS unit_id FROM control_text AS g"
        ") SELECT g.unit_id AS unit_id FROM hidden AS g "
        "ORDER BY g.unit_id ASC NULLS LAST"
    )
    with pytest.raises(StoreRefusal) as caught:
        _lint_scope(sql, (("unit_id", "text"),), ("unit_id",), (text, geom))
    assert str(caught.value) == "forbidden construct"


def test_own_scope_outer_text_predicate_reaches_the_order_proof() -> None:
    """A CTE geometry alias must not treat the outer text column as geometry."""
    text, _real, geom, _rows = _scope_tables()
    sql = (
        "WITH cover AS (SELECT g.unit_id AS unit_id FROM control_geom AS g) "
        "SELECT g.unit_id AS unit_id FROM control_text AS g "
        "WHERE g.shape IS NULL ORDER BY g.unit_id ASC NULLS LAST"
    )
    with pytest.raises(StoreRefusal) as caught:
        _lint_scope(sql, (("unit_id", "text"),), ("unit_id",), (text, geom))
    assert str(caught.value) == "order unproved"
    assert raised_in(caught, "_order")


def test_own_scope_duplicate_alias_text_table_first_is_refused() -> None:
    """One select that aliases two tables as g is refused, text table first."""
    text, _real, _geom, rows = _scope_tables()
    sql = (
        "SELECT SUM(g.amount) AS amount FROM control_text AS g "
        "INNER JOIN control_rows AS g ON g.unit_id = g.unit_id"
    )
    with pytest.raises(StoreRefusal) as caught:
        _lint_scope(sql, (("amount", "numeric"),), (), (text, rows))
    assert str(caught.value) == "forbidden construct"


def test_own_scope_duplicate_alias_text_table_last_is_refused() -> None:
    """One select that aliases two tables as g is refused, text table last."""
    text, _real, _geom, rows = _scope_tables()
    sql = (
        "SELECT SUM(g.amount) AS amount FROM control_rows AS g "
        "INNER JOIN control_text AS g ON g.unit_id = g.unit_id"
    )
    with pytest.raises(StoreRefusal) as caught:
        _lint_scope(sql, (("amount", "numeric"),), (), (text, rows))
    assert str(caught.value) == "forbidden construct"


def test_own_scope_same_table_alias_is_accepted() -> None:
    """The same alias may name one table inside a CTE and that CTE outside it."""
    text, _real, _geom, _rows = _scope_tables()
    sql = (
        "WITH inner_q AS ("
        "SELECT g.unit_id AS unit_id, g.amount AS amount FROM control_text AS g"
        ") SELECT g.unit_id AS unit_id, SUM(g.amount) AS total_amount "
        "FROM inner_q AS g GROUP BY g.unit_id "
        "ORDER BY g.unit_id ASC NULLS LAST"
    )
    _lint_scope(
        sql,
        (("unit_id", "text"), ("total_amount", "numeric")),
        ("unit_id",),
        (text,),
    )


def test_contract_cte_name_hides_an_approximate_sum() -> None:
    """A later CTE named as a contract table is refused before its body is typed."""
    text, real, _geom, _rows = _scope_tables()
    sql = (
        "WITH a AS ("
        "SELECT x.unit_id AS unit_id, SUM(x.amount) AS amount "
        "FROM control_real AS x GROUP BY x.unit_id"
        "), control_real AS ("
        "SELECT t.unit_id AS unit_id, t.amount AS amount FROM control_text AS t"
        ") SELECT a.unit_id AS unit_id FROM a ORDER BY a.unit_id ASC NULLS LAST"
    )
    with pytest.raises(StoreRefusal) as caught:
        _lint_scope(sql, (("unit_id", "text"),), ("unit_id",), (text, real))
    assert str(caught.value) == "forbidden construct"
    assert raised_in(caught, "_refuse_contract_cte")


def test_contract_cte_name_hides_a_geometry_predicate() -> None:
    """A later CTE named as a contract table is refused before geometry is typed."""
    text, _real, geom, _rows = _scope_tables()
    sql = (
        "WITH a AS ("
        "SELECT x.unit_id AS unit_id FROM control_geom AS x WHERE x.shape IS NULL"
        "), control_geom AS ("
        "SELECT t.unit_id AS unit_id, t.shape AS shape FROM control_text AS t"
        ") SELECT a.unit_id AS unit_id FROM a ORDER BY a.unit_id ASC NULLS LAST"
    )
    with pytest.raises(StoreRefusal) as caught:
        _lint_scope(sql, (("unit_id", "text"),), ("unit_id",), (text, geom))
    assert str(caught.value) == "forbidden construct"
    assert raised_in(caught, "_refuse_contract_cte")


def test_unquoted_contract_cte_case_is_refused() -> None:
    """An unquoted contract-table CTE in another case is refused before typing."""
    text, _real, _geom, _rows = _scope_tables()
    sql = (
        "WITH CONTROL_TEXT AS (SELECT t.unit_id AS unit_id FROM control_text AS t) "
        "SELECT c.unit_id AS unit_id FROM CONTROL_TEXT AS c "
        "ORDER BY c.unit_id ASC NULLS LAST"
    )
    with pytest.raises(StoreRefusal) as caught:
        _lint_scope(sql, (("unit_id", "text"),), ("unit_id",), (text,))
    assert str(caught.value) == "forbidden construct"
    assert raised_in(caught, "_refuse_non_lower_name")


def test_quoted_contract_cte_case_is_refused() -> None:
    """A quoted upper-case contract-table CTE is refused before typing."""
    text, _real, _geom, _rows = _scope_tables()
    sql = (
        'WITH "CONTROL_TEXT" AS (SELECT t.unit_id AS unit_id FROM control_text AS t) '
        'SELECT c.unit_id AS unit_id FROM "CONTROL_TEXT" AS c '
        "ORDER BY c.unit_id ASC NULLS LAST"
    )
    with pytest.raises(StoreRefusal) as caught:
        _lint_scope(sql, (("unit_id", "text"),), ("unit_id",), (text,))
    assert str(caught.value) == "forbidden construct"
    assert raised_in(caught, "_refuse_non_lower_name")


def test_mixed_case_cte_name_is_refused() -> None:
    """A mixed-case common-table name that is not a contract table is refused."""
    text, _real, _geom, _rows = _scope_tables()
    sql = (
        "WITH Base AS (SELECT t.unit_id AS unit_id FROM control_text AS t) "
        "SELECT Base.unit_id AS unit_id FROM Base "
        "ORDER BY Base.unit_id ASC NULLS LAST"
    )
    with pytest.raises(StoreRefusal) as caught:
        _lint_scope(sql, (("unit_id", "text"),), ("unit_id",), (text,))
    assert str(caught.value) == "forbidden construct"
    assert raised_in(caught, "_refuse_non_lower_name")


def test_upper_case_table_reference_is_refused() -> None:
    """An upper-case table reference with no CTE is refused before typing."""
    text, _real, _geom, _rows = _scope_tables()
    sql = (
        "SELECT t.unit_id AS unit_id FROM CONTROL_TEXT AS t "
        "ORDER BY t.unit_id ASC NULLS LAST"
    )
    with pytest.raises(StoreRefusal) as caught:
        _lint_scope(sql, (("unit_id", "text"),), ("unit_id",), (text,))
    assert str(caught.value) == "forbidden construct"
    assert raised_in(caught, "_refuse_non_lower_name")


def test_forward_cte_sum_is_an_unresolved_name() -> None:
    """An earlier body cannot see a later sibling, so its sum does not resolve."""
    text, _real, _geom, _rows = _scope_tables()
    sql = (
        "WITH earlier AS ("
        "SELECT x.unit_id AS unit_id, SUM(x.amount) AS amount "
        "FROM later_name AS x GROUP BY x.unit_id"
        "), later_name AS ("
        "SELECT t.unit_id AS unit_id, t.amount AS amount FROM control_text AS t"
        ") SELECT earlier.unit_id AS unit_id FROM earlier "
        "ORDER BY earlier.unit_id ASC NULLS LAST"
    )
    with pytest.raises(StoreRefusal) as caught:
        _lint_scope(sql, (("unit_id", "text"),), ("unit_id",), (text,))
    assert str(caught.value) == "forbidden construct"
    assert raised_in(caught, "_resolve")


def test_forward_cte_geometry_is_an_unresolved_name() -> None:
    """An earlier body cannot see a later sibling, so its shape does not resolve."""
    text, _real, geom, _rows = _scope_tables()
    sql = (
        "WITH earlier AS ("
        "SELECT x.unit_id AS unit_id FROM later_name AS x WHERE x.shape IS NULL"
        "), later_name AS ("
        "SELECT t.unit_id AS unit_id, t.shape AS shape FROM control_text AS t"
        ") SELECT earlier.unit_id AS unit_id FROM earlier "
        "ORDER BY earlier.unit_id ASC NULLS LAST"
    )
    with pytest.raises(StoreRefusal) as caught:
        _lint_scope(sql, (("unit_id", "text"),), ("unit_id",), (text, geom))
    assert str(caught.value) == "forbidden construct"
    assert raised_in(caught, "_resolve")


def test_earlier_sibling_sum_is_typed_from_that_body() -> None:
    """A later body sees an earlier sibling and sums that body's text column."""
    text, real, _geom, _rows = _scope_tables()
    sql = (
        "WITH earlier AS ("
        "SELECT t.unit_id AS unit_id, t.amount AS amount FROM control_text AS t"
        "), later AS ("
        "SELECT x.unit_id AS unit_id, SUM(x.amount) AS amount "
        "FROM earlier AS x GROUP BY x.unit_id"
        ") SELECT later.unit_id AS unit_id FROM later "
        "ORDER BY later.unit_id ASC NULLS LAST"
    )
    _lint_scope(sql, (("unit_id", "text"),), ("unit_id",), (text, real))


def test_earlier_sibling_approximate_sum_is_typed_from_that_body() -> None:
    """A later sum of an earlier sibling is refused when that body is approximate."""
    text, real, _geom, _rows = _scope_tables()
    sql = (
        "WITH earlier AS ("
        "SELECT t.unit_id AS unit_id, t.amount AS amount FROM control_real AS t"
        "), later AS ("
        "SELECT x.unit_id AS unit_id, SUM(x.amount) AS amount "
        "FROM earlier AS x GROUP BY x.unit_id"
        ") SELECT later.unit_id AS unit_id FROM later "
        "ORDER BY later.unit_id ASC NULLS LAST"
    )
    with pytest.raises(StoreRefusal) as caught:
        _lint_scope(sql, (("unit_id", "text"),), ("unit_id",), (text, real))
    assert str(caught.value) == "forbidden construct"
    assert raised_in(caught, "_sum")


def test_later_body_sum_keeps_the_earlier_cte_not_the_later_sibling() -> None:
    """A nested later sibling must not retype a sum that reads an earlier CTE."""
    text, real, _geom, _rows = _scope_tables()
    sql = (
        "WITH outer_cte AS ("
        "SELECT t.unit_id AS unit_id, t.amount AS amount FROM control_text AS t"
        "), holder AS ("
        "WITH reader AS ("
        "SELECT x.unit_id AS unit_id, SUM(x.amount) AS amount "
        "FROM outer_cte AS x GROUP BY x.unit_id"
        "), outer_cte AS ("
        "SELECT t.unit_id AS unit_id, t.amount AS amount FROM control_real AS t"
        ") SELECT reader.unit_id AS unit_id FROM reader"
        ") SELECT holder.unit_id AS unit_id FROM holder "
        "ORDER BY holder.unit_id ASC NULLS LAST"
    )
    _lint_scope(sql, (("unit_id", "text"),), ("unit_id",), (text, real))


def test_self_cte_sum_is_refused() -> None:
    """A non-recursive body cannot read its own name, so the sum does not resolve."""
    text, _real, _geom, _rows = _scope_tables()
    sql = (
        "WITH loop AS ("
        "SELECT t.unit_id AS unit_id, t.amount AS amount, SUM(l.amount) AS total_amount "
        "FROM control_text AS t INNER JOIN loop AS l ON t.unit_id = l.unit_id "
        "GROUP BY t.unit_id, t.amount"
        ") SELECT loop.unit_id AS unit_id FROM loop "
        "ORDER BY loop.unit_id ASC NULLS LAST"
    )
    with pytest.raises(StoreRefusal) as caught:
        _lint_scope(sql, (("unit_id", "text"),), ("unit_id",), (text,))
    assert str(caught.value) == "forbidden construct"
    assert raised_in(caught, "_resolve")


def test_self_cte_geometry_is_refused() -> None:
    """A non-recursive body cannot read its own name, so the shape does not resolve."""
    text, _real, geom, _rows = _scope_tables()
    sql = (
        "WITH loop AS ("
        "SELECT t.unit_id AS unit_id, t.shape AS shape "
        "FROM control_text AS t INNER JOIN loop AS l ON t.unit_id = l.unit_id "
        "WHERE l.shape IS NULL"
        ") SELECT loop.unit_id AS unit_id FROM loop "
        "ORDER BY loop.unit_id ASC NULLS LAST"
    )
    with pytest.raises(StoreRefusal) as caught:
        _lint_scope(sql, (("unit_id", "text"),), ("unit_id",), (text, geom))
    assert str(caught.value) == "forbidden construct"
    assert raised_in(caught, "_resolve")


def test_inner_cte_sum_shadows_the_outer_name() -> None:
    """The nested query uses the inner CTE, and that sum reaches the order proof."""
    text, _real, _geom, _rows = _scope_tables()
    sql = (
        "WITH outer_cte AS ("
        "SELECT t.unit_id AS unit_id, t.amount AS amount FROM control_text AS t"
        "), holder AS ("
        "WITH outer_cte AS ("
        "SELECT t.unit_id AS unit_id, x.amount AS amount FROM control_text AS t "
        "INNER JOIN outer_cte AS x ON t.unit_id = x.unit_id"
        ") SELECT y.unit_id AS unit_id, SUM(y.amount) AS amount "
        "FROM outer_cte AS y GROUP BY y.unit_id"
        ") SELECT holder.unit_id AS unit_id FROM holder "
        "ORDER BY holder.unit_id ASC NULLS LAST"
    )
    with pytest.raises(StoreRefusal) as caught:
        _lint_scope(sql, (("unit_id", "text"),), ("unit_id",), (text,))
    assert str(caught.value) == "order unproved"
    assert raised_in(caught, "_order")


def test_inner_cte_geometry_shadows_the_outer_name() -> None:
    """The nested query uses the inner CTE, and that shape reaches the order proof."""
    text, _real, geom, _rows = _scope_tables()
    sql = (
        "WITH outer_cte AS ("
        "SELECT t.unit_id AS unit_id, t.shape AS shape FROM control_text AS t"
        "), holder AS ("
        "WITH outer_cte AS ("
        "SELECT t.unit_id AS unit_id, x.shape AS shape FROM control_text AS t "
        "INNER JOIN outer_cte AS x ON t.unit_id = x.unit_id"
        ") SELECT y.unit_id AS unit_id FROM outer_cte AS y WHERE y.shape IS NULL"
        ") SELECT holder.unit_id AS unit_id FROM holder "
        "ORDER BY holder.unit_id ASC NULLS LAST"
    )
    with pytest.raises(StoreRefusal) as caught:
        _lint_scope(sql, (("unit_id", "text"),), ("unit_id",), (text, geom))
    assert str(caught.value) == "order unproved"
    assert raised_in(caught, "_order")


def test_bare_recursive_body_is_forbidden_before_depth(tmp_path: Path) -> None:
    """A recursive body that is not a select is a bare column, refused in the walk."""
    sql = (
        "WITH RECURSIVE g AS (control_rows) "
        "SELECT g.unit_id AS unit_id FROM g ORDER BY g.unit_id ASC NULLS LAST"
    )
    with pytest.raises(StoreRefusal) as caught:
        _lint_one(tmp_path, "graph_bare", sql, params="")
    assert str(caught.value) == "forbidden construct"


def test_control_query_passes_the_lint() -> None:
    from store_live_controls import FIXTURE_DIR

    lint_inventory(load_inventory(FIXTURE_DIR))


def test_sum_of_one_table_without_order_by_is_accepted(tmp_path: Path) -> None:
    """One SUM over one table, with an empty order line, is one row."""
    _lint_one(
        tmp_path,
        "syn_sum_total",
        "SELECT SUM(p.amount) AS amount FROM control_rows AS p",
        params="",
        returns="amount numeric",
        order="",
    )


def test_two_aggregates_without_order_by_are_accepted(tmp_path: Path) -> None:
    """Two aggregate items over one table, with an empty order line, are one row."""
    _lint_one(
        tmp_path,
        "syn_two_totals",
        "SELECT SUM(p.amount) AS amount, COUNT(p.label) AS count_value "
        "FROM control_rows AS p",
        params="",
        returns="amount numeric, count_value bigint",
        order="",
    )


def test_one_row_aggregates_prepare_and_fetch_one_row(tmp_path: Path) -> None:
    """Both one-row fixtures prepare and fetch one row on the embedded store."""
    from decimal import Decimal

    import duckdb
    from store_live_controls import DUCK_CREATE, DUCK_INSERT, FIXTURE_ID, ROWS

    from eii_product.store.embedded import EmbeddedStore

    folder = tmp_path / "queries"
    _write(
        folder,
        "syn_sum_total",
        "SELECT SUM(p.amount) AS amount FROM control_rows AS p",
        returns="amount numeric",
        order="",
    )
    _write(
        folder,
        "syn_two_totals",
        "SELECT SUM(p.amount) AS amount, COUNT(p.label) AS count_value "
        "FROM control_rows AS p",
        returns="amount numeric, count_value bigint",
        order="",
    )
    inventory = lint_inventory(load_inventory(folder))
    path = tmp_path / "control.duckdb"
    connection = duckdb.connect(str(path))
    connection.execute(DUCK_CREATE)
    connection.executemany(DUCK_INSERT, ROWS)
    connection.close()
    store = EmbeddedStore(path, FIXTURE_ID, inventory)
    try:
        store.plan(inventory.lookup("syn_sum_total"), {})
        summed = store.fetch(inventory.lookup("syn_sum_total"), {})
        store.plan(inventory.lookup("syn_two_totals"), {})
        paired = store.fetch(inventory.lookup("syn_two_totals"), {})
    finally:
        store.close()
    assert summed.rows == ((Decimal("3.750000"),),)
    assert paired.rows == ((Decimal("3.750000"), 2),)


@pytest.mark.parametrize(
    ("name", "sql", "returns"),
    [
        (
            "syn_bare_beside",
            "SELECT p.unit_id AS unit_id, SUM(p.amount) AS amount FROM control_rows AS p",
            "unit_id text, amount numeric",
        ),
        (
            "syn_aggregate_expr",
            "SELECT SUM(p.amount) + p.count_value AS amount FROM control_rows AS p",
            "amount numeric",
        ),
        (
            "syn_group_no_order",
            "SELECT SUM(p.amount) AS amount FROM control_rows AS p GROUP BY p.unit_id",
            "amount numeric",
        ),
        (
            "syn_having_no_order",
            "SELECT SUM(p.amount) AS amount FROM control_rows AS p "
            "HAVING SUM(p.amount) > 0",
            "amount numeric",
        ),
        (
            "syn_join_sum",
            "SELECT SUM(p.amount) AS amount FROM control_rows AS p "
            "INNER JOIN control_rows AS q ON p.unit_id = q.unit_id",
            "amount numeric",
        ),
        (
            "syn_union_sum",
            "SELECT SUM(p.amount) AS amount FROM control_rows AS p "
            "UNION ALL SELECT SUM(q.amount) AS amount FROM control_rows AS q",
            "amount numeric",
        ),
        (
            "syn_cte_sum",
            "WITH picked AS (SELECT SUM(p.amount) AS amount FROM control_rows AS p) "
            "SELECT picked.amount AS amount FROM picked",
            "amount numeric",
        ),
        (
            "syn_limit_sum",
            "SELECT SUM(p.amount) AS amount FROM control_rows AS p LIMIT 1",
            "amount numeric",
        ),
        (
            "syn_coalesce_item",
            "SELECT COALESCE(p.amount, 0) AS amount FROM control_rows AS p",
            "amount numeric",
        ),
    ],
)
def test_one_row_shape_is_refused(
    tmp_path: Path, name: str, sql: str, returns: str
) -> None:
    """Each breach of the one-row shape keeps today's order refusal."""
    with pytest.raises(StoreRefusal) as caught:
        _lint_one(
            tmp_path,
            name,
            sql,
            params="",
            returns=returns,
            order="",
        )
    assert str(caught.value) == "order unproved"


def test_one_row_order_line_that_names_a_column_is_unproved(tmp_path: Path) -> None:
    """A one-row statement whose order line names a return column is unproved."""
    with pytest.raises(StoreRefusal) as caught:
        _lint_one(
            tmp_path,
            "syn_sum_named",
            "SELECT SUM(p.amount) AS amount FROM control_rows AS p",
            params="",
            returns="amount numeric",
            order="amount",
        )
    assert str(caught.value) == "order unproved"


def test_order_by_with_the_one_row_header_is_unproved(tmp_path: Path) -> None:
    """An ORDER BY whose header holds the empty one-row form is unproved."""
    with pytest.raises(StoreRefusal) as caught:
        _lint_one(
            tmp_path,
            "syn_ordered_empty",
            "SELECT p.unit_id AS unit_id FROM control_rows AS p "
            "ORDER BY p.unit_id ASC NULLS LAST",
            params="",
            returns="unit_id text",
            order="",
        )
    assert str(caught.value) == "order unproved"


_GROUPING = {
    "syn_paren_and": (
        "SELECT p.unit_id AS unit_id FROM control_rows AS p "
        "WHERE p.label = 'SYN-a' AND (p.count_value = 1) "
        "ORDER BY p.unit_id ASC NULLS LAST"
    ),
    "syn_paren_or": (
        "SELECT p.unit_id AS unit_id FROM control_rows AS p "
        "WHERE p.label = 'SYN-a' OR (p.count_value = 1) "
        "ORDER BY p.unit_id ASC NULLS LAST"
    ),
    "syn_paren_not": (
        "SELECT p.unit_id AS unit_id FROM control_rows AS p "
        "WHERE NOT (p.label IS NULL) ORDER BY p.unit_id ASC NULLS LAST"
    ),
    "syn_paren_where": (
        "SELECT p.unit_id AS unit_id FROM control_rows AS p "
        "WHERE (p.label = 'SYN-a') ORDER BY p.unit_id ASC NULLS LAST"
    ),
    "syn_paren_having": (
        "SELECT p.unit_id AS unit_id, SUM(p.amount) AS amount FROM control_rows AS p "
        "GROUP BY p.unit_id HAVING (SUM(p.amount) > 0) "
        "ORDER BY p.unit_id ASC NULLS LAST"
    ),
    "syn_paren_when": (
        "SELECT CASE WHEN (p.label IS NULL) THEN p.unit_id ELSE p.unit_id END "
        "AS unit_id FROM control_rows AS p ORDER BY p.unit_id ASC NULLS LAST"
    ),
    "syn_paren_then": (
        "SELECT CASE WHEN p.label IS NULL THEN (p.unit_id) ELSE p.unit_id END "
        "AS unit_id FROM control_rows AS p ORDER BY p.unit_id ASC NULLS LAST"
    ),
    "syn_paren_else": (
        "SELECT CASE WHEN p.label IS NULL THEN p.unit_id ELSE (p.unit_id) END "
        "AS unit_id FROM control_rows AS p ORDER BY p.unit_id ASC NULLS LAST"
    ),
}


@pytest.mark.parametrize("name", sorted(_GROUPING))
def test_grouping_parenthesis_is_accepted(tmp_path: Path, name: str) -> None:
    """A grouping parenthesis after an allowed keyword is admitted."""
    returns = (
        "unit_id text, amount numeric" if name == "syn_paren_having" else "unit_id text"
    )
    _lint_one(
        tmp_path,
        name,
        _GROUPING[name],
        params="",
        returns=returns,
        order="unit_id",
    )


def test_on_parenthesis_reaches_the_order_proof(tmp_path: Path) -> None:
    """ON ( is not a function word. A join stays order unproved."""
    sql = (
        "SELECT p.unit_id AS unit_id FROM control_rows AS p "
        "INNER JOIN control_rows AS q ON (p.unit_id = q.unit_id) "
        "ORDER BY p.unit_id ASC NULLS LAST"
    )
    with pytest.raises(StoreRefusal) as caught:
        _lint_one(tmp_path, "syn_paren_on", sql, params="")
    assert str(caught.value) == "order unproved"
    assert raised_in(caught, "_order")


@pytest.mark.parametrize(
    ("name", "sql"),
    [
        (
            "syn_where_subquery",
            "SELECT p.unit_id AS unit_id FROM control_rows AS p "
            "WHERE (SELECT q.unit_id FROM control_rows AS q) = p.unit_id "
            "ORDER BY p.unit_id ASC NULLS LAST",
        ),
        (
            "syn_and_subquery",
            "SELECT p.unit_id AS unit_id FROM control_rows AS p "
            "WHERE p.label = 'SYN-a' AND (SELECT q.unit_id FROM control_rows AS q) "
            "= p.unit_id ORDER BY p.unit_id ASC NULLS LAST",
        ),
    ],
)
def test_subquery_inside_a_grouping_parenthesis_is_forbidden(
    tmp_path: Path, name: str, sql: str
) -> None:
    """A select inside a grouping parenthesis is still a forbidden subquery."""
    with pytest.raises(StoreRefusal) as caught:
        _lint_one(tmp_path, name, sql, params="")
    assert str(caught.value) == "forbidden construct"
    assert raised_in(caught, "_walk")


def test_ifnull_inside_a_grouping_parenthesis_is_forbidden(tmp_path: Path) -> None:
    """IFNULL inside a grouping parenthesis stays an unlisted function word."""
    sql = (
        "SELECT p.unit_id AS unit_id FROM control_rows AS p "
        "WHERE (IFNULL(p.label, 'SYN-a') = 'SYN-a') "
        "ORDER BY p.unit_id ASC NULLS LAST"
    )
    with pytest.raises(StoreRefusal) as caught:
        _lint_one(tmp_path, "syn_paren_ifnull", sql, params="")
    assert str(caught.value) == "forbidden construct"
    assert raised_in(caught, "_function_calls")


def test_from_parenthesis_is_forbidden(tmp_path: Path) -> None:
    """FROM followed by a parenthesis stays a forbidden construct."""
    sql = (
        "SELECT p.unit_id AS unit_id FROM "
        "(SELECT q.unit_id AS unit_id FROM control_rows AS q) AS p "
        "ORDER BY p.unit_id ASC NULLS LAST"
    )
    with pytest.raises(StoreRefusal) as caught:
        _lint_one(tmp_path, "syn_from_paren", sql, params="")
    assert str(caught.value) == "forbidden construct"
    assert raised_in(caught, "_function_calls")


def test_select_parenthesis_is_forbidden(tmp_path: Path) -> None:
    """SELECT followed by a parenthesis stays a forbidden construct."""
    sql = (
        "SELECT (p.unit_id) AS unit_id FROM control_rows AS p "
        "ORDER BY p.unit_id ASC NULLS LAST"
    )
    with pytest.raises(StoreRefusal) as caught:
        _lint_one(tmp_path, "syn_select_paren", sql, params="")
    assert str(caught.value) == "forbidden construct"
    assert raised_in(caught, "_function_calls")


def _scope_tables() -> tuple[
    ContractTable, ContractTable, ContractTable, ContractTable
]:
    """Text, approximate, geometry and decimal tables for scope plants."""
    from eii_product.store.registry import ContractColumn, ContractTable

    text = ContractTable(
        "control_text",
        "invented control table",
        ("unit_id",),
        (
            ContractColumn("unit_id", "string", False),
            ContractColumn("amount", "string", True),
            ContractColumn("shape", "string", True),
        ),
    )
    real = ContractTable(
        "control_real",
        "invented control table",
        ("unit_id",),
        (
            ContractColumn("unit_id", "string", False),
            ContractColumn("amount", "real", True),
        ),
    )
    geom = ContractTable(
        "control_geom",
        "invented control table",
        ("unit_id",),
        (
            ContractColumn("unit_id", "string", False),
            ContractColumn("shape", "geometry", True),
        ),
    )
    rows = ContractTable(
        "control_rows",
        "invented control table",
        ("unit_id",),
        (
            ContractColumn("unit_id", "string", False),
            ContractColumn("amount", "decimal(18,6)", True),
        ),
    )
    return text, real, geom, rows


def _lint_scope(
    sql: str,
    returns: tuple[tuple[str, str], ...],
    order: tuple[str, ...],
    tables: tuple[ContractTable, ...],
) -> None:
    """Lint one hand-built statement. Callers pass the contract tables."""
    from eii_product.store.registry import Inventory, QuerySpec, ReturnSpec

    spec = QuerySpec(
        "syn_scope",
        (),
        tuple(ReturnSpec(name, type_name) for name, type_name in returns),
        order,
        sql,
        "ab",
        tables,
    )
    lint_inventory(Inventory((spec,), object(), ()))


def _lint_one(
    folder: Path,
    name: str,
    sql: str,
    *,
    params: str = "",
    returns: str = "unit_id text",
    order: str = "unit_id",
    key: str = '["unit_id"]',
    shape: bool = False,
) -> None:
    root = folder / name
    root.mkdir()
    _write(
        root,
        name,
        sql,
        params=params,
        returns=returns,
        order=order,
        key=key,
        shape=shape,
    )
    lint_inventory(load_inventory(root))


def _write(
    folder: Path,
    name: str,
    sql: str,
    *,
    params: str = "",
    returns: str = "unit_id text",
    order: str = "unit_id",
    key: str = '["unit_id"]',
    shape: bool = False,
) -> None:
    folder.mkdir(exist_ok=True)
    marker = folder / "__init__.py"
    if not marker.exists():
        marker.write_text('"""marker"""\n', encoding="utf-8")
    header = HEADER.format(name=name, params=params, returns=returns, order=order)
    (folder / f"{name}.sql").write_text(header + sql.strip() + "\n", encoding="utf-8")
    contract = CONTRACT.format(key=key)
    if shape:
        contract += (
            '\n[[tables.columns]]\nname = "shape"\ntype = "geometry"\nnullable = true\n'
        )
    (folder / f"{name}.toml").write_text(contract, encoding="utf-8")
