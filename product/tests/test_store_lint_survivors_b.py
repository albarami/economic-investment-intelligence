"""Kill surviving mutants of the lint walk, order proof and depth proof.

Expectations are hand-worked. Refusal text goes through the scanner file's
``full_message`` helper. A direct call is used where an earlier branch never
passes that input through ``lint_inventory``.
"""

from __future__ import annotations

import importlib
from typing import Any

import pytest
import sqlglot
from product.tests.frames import raised_in
from product.tests.test_store_lint_survivors import full_message

from eii_product.store.protocol import StoreRefusal
from eii_product.store.registry import (
    ContractColumn,
    ContractTable,
    Inventory,
    ParamSpec,
    QuerySpec,
    ReturnSpec,
)


def _mod() -> Any:
    """Reload point so a mutated module object is what the assertions call."""
    return importlib.import_module("eii_product.store.lint")


def as_any(value: object) -> Any:
    """Hand a value through so a test can pass a type the signature refuses."""
    return value


_ROWS = ContractTable(
    "control_rows",
    "invented control table",
    ("unit_id",),
    (
        ContractColumn("unit_id", "string", False),
        ContractColumn("label", "string", True),
        ContractColumn("count_value", "int", False),
        ContractColumn("amount", "decimal(18,6)", True),
        ContractColumn("period", "date", False),
    ),
)
_GEOM = ContractTable(
    "control_rows",
    "invented control table",
    ("unit_id",),
    (
        ContractColumn("unit_id", "string", False),
        ContractColumn("shape", "geometry", True),
    ),
)

_SELECT = (
    "SELECT p.unit_id AS unit_id FROM control_rows AS p "
    "ORDER BY p.unit_id ASC NULLS LAST"
)


def _spec(
    text: str,
    *,
    name: str = "syn_case",
    params: tuple[tuple[str, str], ...] = (),
    returns: tuple[tuple[str, str], ...] = (("unit_id", "text"),),
    order: tuple[str, ...] = ("unit_id",),
    tables: tuple[ContractTable, ...] = (_ROWS,),
) -> QuerySpec:
    return QuerySpec(
        name,
        tuple(ParamSpec(item, kind) for item, kind in params),
        tuple(ReturnSpec(item, kind) for item, kind in returns),
        order,
        text,
        "ab",
        tables,
    )


def _outcome(text: str, **kwargs: Any) -> str:
    try:
        _mod().lint_inventory(Inventory((_spec(text, **kwargs),), object(), ()))
    except StoreRefusal as caught:
        return str(caught)
    return "accepted"


def _parse(text: str) -> Any:
    return sqlglot.parse_one(text, read="postgres")


def _one(kind: str, tree: Any) -> Any:
    return next(node for node in tree.walk() if type(node).__name__ == kind)


def test_parse_edges_keep_their_reasons() -> None:
    """Empty text, a non-statement and a default-dialect split stay distinct."""
    mod = _mod()
    with pytest.raises(StoreRefusal) as empty:
        mod.lint_inventory(Inventory((_spec(""),), object(), ()))
    full_message(empty.value, "parse invalid")
    assert raised_in(empty, "_lint_one")
    # Both dialects return a Not node, which is neither Select nor Union.
    assert _outcome("NOT SQL") == "forbidden construct"
    assert _outcome("SELECT 'a' ~ 'a'") == "forbidden construct"
    assert _outcome("SHOW TABLES") == "parse invalid"


def test_walk_refuses_distinct_star_and_a_bad_cast() -> None:
    """Allow-list failures name forbidden construct from the walk."""
    assert (
        _outcome(
            "SELECT DISTINCT p.unit_id AS unit_id FROM control_rows AS p ORDER BY p.unit_id ASC NULLS LAST"
        )
        == "forbidden construct"
    )
    assert _outcome("SELECT * FROM control_rows AS p") == "forbidden construct"
    assert (
        _outcome(
            "SELECT CAST(p.count_value AS INT4) AS unit_id FROM control_rows AS p ORDER BY p.unit_id ASC NULLS LAST"
        )
        == "forbidden construct"
    )
    assert _outcome(_SELECT) == "accepted"


def test_order_join_union_and_missing_nulls() -> None:
    """A join and a union are order unproved. A proved key is accepted."""
    joined = (
        "WITH picked AS (SELECT 'SYN-a' AS unit_id) "
        "SELECT q.unit_id AS unit_id FROM picked "
        "INNER JOIN control_rows AS q ON picked.unit_id = q.unit_id "
        "ORDER BY q.unit_id ASC NULLS LAST"
    )
    assert _outcome(joined) == "order unproved"
    union = (
        "SELECT p.unit_id AS unit_id FROM control_rows AS p "
        "UNION ALL "
        "SELECT p.unit_id AS unit_id FROM control_rows AS p"
    )
    assert _outcome(union) == "order unproved"
    assert (
        _outcome(
            "SELECT p.unit_id AS unit_id FROM control_rows AS p ORDER BY p.unit_id ASC"
        )
        == "order unproved"
    )
    assert (
        _outcome(
            "SELECT SUM(p.amount) AS amount FROM control_rows AS p",
            returns=(("amount", "numeric"),),
            order=(),
        )
        == "accepted"
    )


def test_depth_proof_refuses_a_short_walk_and_accepts_four() -> None:
    """The recursive member must start at zero and stop before four."""
    good = (
        "WITH RECURSIVE g AS ("
        "SELECT p.unit_id AS unit_id, 0 AS depth FROM control_rows AS p "
        "UNION ALL "
        "SELECT c.unit_id AS unit_id, g.depth + 1 AS depth "
        "FROM control_rows AS c INNER JOIN g ON c.label = g.unit_id "
        "WHERE g.depth < 4) "
        "SELECT g.unit_id AS unit_id, g.depth AS depth FROM g "
        "ORDER BY g.unit_id ASC NULLS LAST, g.depth ASC NULLS LAST"
    )
    # The proved graph still ends on order unproved. That is the last raise.
    assert (
        _outcome(
            good,
            name="graph_syn",
            returns=(("unit_id", "text"), ("depth", "bigint")),
            order=("unit_id", "depth"),
        )
        == "order unproved"
    )
    short = good.replace("g.depth < 4", "g.depth < 3")
    assert (
        _outcome(
            short,
            name="graph_syn",
            returns=(("unit_id", "text"), ("depth", "bigint")),
            order=("unit_id", "depth"),
        )
        == "depth unproved"
    )
    plain = good.replace("graph_", "syn_")
    assert (
        _outcome(
            plain,
            name="syn_walk",
            returns=(("unit_id", "text"), ("depth", "bigint")),
            order=("unit_id", "depth"),
        )
        == "depth unproved"
    )


def test_geometry_projection_and_limit_parameter() -> None:
    """Geometry stays a bare outer column. A limit parameter is an integer."""
    bare = (
        "SELECT p.unit_id AS unit_id, p.shape FROM control_rows AS p "
        "ORDER BY p.unit_id ASC NULLS LAST"
    )
    assert (
        _outcome(
            bare,
            returns=(("unit_id", "text"), ("shape", "geometry")),
            tables=(_GEOM,),
        )
        == "accepted"
    )
    assert (
        _outcome(
            "SELECT p.shape AS shape FROM control_rows AS p ORDER BY p.shape ASC NULLS LAST",
            returns=(("shape", "geometry"),),
            order=("shape",),
            tables=(_GEOM,),
        )
        == "forbidden construct"
    )
    limited = (
        "SELECT p.unit_id AS unit_id FROM control_rows AS p "
        "ORDER BY p.unit_id ASC NULLS LAST LIMIT :row_limit"
    )
    assert _outcome(limited, params=(("row_limit", "bigint"),)) == "accepted"
    assert _outcome(limited, params=(("row_limit", "text"),)) == "forbidden construct"


def test_direct_join_cast_in_and_literal_helpers() -> None:
    """Helpers answer from the node, including a non-select the walk never sends."""
    mod = _mod()
    inner = _parse(
        "SELECT p.unit_id AS unit_id FROM control_rows AS p "
        "INNER JOIN control_rows AS q ON p.unit_id = q.unit_id"
    )
    left = _parse(
        "SELECT p.unit_id AS unit_id FROM control_rows AS p "
        "LEFT JOIN control_rows AS q ON p.unit_id = q.unit_id"
    )
    right = _parse(
        "SELECT p.unit_id AS unit_id FROM control_rows AS p "
        "RIGHT JOIN control_rows AS q ON p.unit_id = q.unit_id"
    )
    assert mod._allowed_join(_one("Join", inner)) is True
    assert mod._allowed_join(_one("Join", left)) is True
    assert mod._allowed_join(_one("Join", right)) is False
    assert mod._outer_joins(inner) is True
    assert mod._outer_joins(_parse(_SELECT)) is False
    union = _parse(
        "SELECT p.unit_id AS unit_id FROM control_rows AS p "
        "UNION ALL SELECT p.unit_id AS unit_id FROM control_rows AS p"
    )
    assert mod._outer_joins(union) is False
    cast = _one(
        "Cast",
        _parse("SELECT CAST(p.count_value AS INTEGER) AS unit_id FROM t AS p"),
    )
    assert mod._allowed_cast(cast) is True
    listed = _one(
        "In",
        _parse("SELECT p.unit_id FROM t AS p WHERE p.label IN ('SYN-a', 'SYN-b')"),
    )
    assert mod._literal_in(listed) is True
    any_node = _one(
        "Any",
        _parse("SELECT p.unit_id FROM t AS p WHERE p.unit_id = ANY(:units)"),
    )
    assert mod._placeholder_any(any_node) is True
    limit = _one("Limit", _parse("SELECT p.unit_id FROM t AS p LIMIT 2"))
    assert mod._allowed_limit(limit) is True
    literal = _one("Literal", _parse("SELECT 4"))
    assert mod._literal(literal, "4") is True
    assert mod._literal(literal, "1") is False
    text = _one("Literal", _parse("SELECT 'SYN-a'"))
    assert mod._literal(text, "SYN-a") is False
    assert mod._integer_or_text(literal) is True
    assert mod._integer_or_text(text) is True
    floated = _one("Literal", _parse("SELECT 1.5"))
    assert mod._integer_or_text(floated) is False


def test_alias_from_name_and_output_name() -> None:
    """Names come from the alias, then the node name, else empty."""
    mod = _mod()
    tree = _parse(_SELECT)
    assert mod._alias(None) == ""
    assert mod._alias("picked") == "picked"
    assert mod._alias(tree) == ""
    assert mod._from_name(tree) == "control_rows"
    assert mod._output_name(tree.expressions[0]) == "unit_id"
    bare = _parse("SELECT p.unit_id FROM control_rows AS p")
    assert mod._output_name(bare.expressions[0]) == "unit_id"
    with pytest.raises(StoreRefusal) as unnamed:
        mod._output_name(_one("Literal", _parse("SELECT 1")))
    full_message(unnamed.value, "forbidden construct")
    assert raised_in(unnamed, "_output_name")
    source = tree.args["from_"]
    table = source.this
    tree.args["from_"] = table
    assert mod._from_name(tree) == "control_rows"


def test_aggregate_shape_and_column_parent() -> None:
    """One bare sum is one row. A column beside the call is not."""
    mod = _mod()
    total = _parse("SELECT SUM(p.amount) AS amount FROM control_rows AS p")
    assert mod._one_row_aggregate(total) is True
    assert mod._item_is_aggregate(total.expressions[0]) is True
    mixed = _parse(
        "SELECT p.unit_id AS unit_id, SUM(p.amount) AS amount FROM control_rows AS p"
    )
    assert mod._one_row_aggregate(mixed) is False
    assert mod._bare_column_outside(mixed.expressions[0]) is True
    assert mod._bare_column_outside(mixed.expressions[1]) is False
    column = _one("Column", total)
    assert mod._under_aggregate(column) is True
    outer = _one("Column", _parse(_SELECT))
    assert mod._under_aggregate(outer) is False
    assert (
        mod._one_row_aggregate(
            _parse(
                "SELECT p.unit_id AS unit_id FROM control_rows AS p "
                "UNION ALL SELECT p.unit_id AS unit_id FROM control_rows AS p"
            )
        )
        is False
    )


def test_cte_trace_depth_column_and_nulls() -> None:
    """Unrenamed keys, depth arithmetic and explicit null ordering."""
    mod = _mod()
    traced = _parse(
        "WITH picked AS (SELECT p.unit_id AS unit_id FROM control_rows AS p) "
        "SELECT picked.unit_id AS unit_id FROM picked"
    )
    assert mod._outer_is_cte(traced) is True
    assert mod._outer_is_cte(_parse(_SELECT)) is False
    spec = _spec(
        "SELECT picked.unit_id AS unit_id FROM picked",
        order=("unit_id",),
    )
    assert mod._unrenamed_cte_key(traced, spec, ("unit_id",)) is True
    assert mod._unrenamed_cte_key(traced, spec, ("label",)) is False
    added = _parse("SELECT g.depth + 1 AS depth FROM g")
    plus = _one("Add", added)
    assert mod._added(plus, "g") is True
    assert mod._added(plus, "other") is False
    column = _one("Column", added)
    assert mod._depth_column(column, "g") is True
    assert mod._depth_column(column, "other") is False
    assert (
        mod._nulls_explicit(
            "ORDER BY p.unit_id ASC NULLS LAST",
            1,
        )
        is True
    )
    assert mod._nulls_explicit("ORDER BY p.unit_id ASC", 1) is False
    assert mod._nulls_explicit("SELECT p.unit_id", 1) is False
    assert mod._column_name(column) == "depth"


def test_limit_parameter_refuses_a_non_string_name() -> None:
    """The parser always stores a string name, so the type check is direct."""
    mod = _mod()
    tree = _parse("SELECT p.unit_id FROM t AS p LIMIT :row_limit")
    limit = _one("Limit", tree)
    placeholder = limit.args["expression"]
    placeholder.args["this"] = as_any(None)
    spec = _spec("SELECT p.unit_id AS unit_id FROM control_rows AS p LIMIT :row_limit")
    with pytest.raises(StoreRefusal) as caught:
        mod._limit_param(limit, spec)
    full_message(caught.value, "forbidden construct")
    assert raised_in(caught, "_limit_param")


def test_allowed_cast_uses_the_default_only_when_the_token_has_no_name() -> None:
    """A datatype token without a name is not one of the four cast words."""

    class _Dtype:
        pass

    class _Cast:
        def __init__(self) -> None:
            self.args = {"to": _Dtype()}

    assert _mod()._allowed_cast(as_any(_Cast())) is False


def test_placeholder_this_must_be_a_string_inside_the_walk() -> None:
    """A placeholder whose name is not text is refused from the walk."""
    mod = _mod()
    tree = _parse(
        "SELECT p.unit_id AS unit_id FROM control_rows AS p WHERE p.label = :label"
    )
    placeholder = _one("Placeholder", tree)
    placeholder.args["this"] = as_any(None)
    spec = _spec(tree.sql(dialect="postgres"), params=(("label", "text"),))
    with pytest.raises(StoreRefusal) as caught:
        mod._walk(tree, spec)
    full_message(caught.value, "forbidden construct")
    assert raised_in(caught, "_walk")


def test_geometry_direct_refuses_a_return_the_table_does_not_hold() -> None:
    """No geometry column, but the header says geometry: that raise is in _geometry."""
    mod = _mod()
    text = (
        "SELECT p.unit_id AS shape FROM control_rows AS p "
        "ORDER BY p.unit_id ASC NULLS LAST"
    )
    tree = _parse(text)
    spec = _spec(text, returns=(("shape", "geometry"),), order=("shape",))
    with pytest.raises(StoreRefusal) as caught:
        mod._geometry(tree, spec)
    full_message(caught.value, "forbidden construct")
    assert raised_in(caught, "_geometry")


def test_walk_refuses_a_cast_whose_token_is_not_one_of_the_four() -> None:
    """The cast-word scanner never builds this token, so the walk sees it directly."""
    mod = _mod()
    text = (
        "SELECT CAST(p.count_value AS INTEGER) AS unit_id FROM control_rows AS p "
        "ORDER BY p.unit_id ASC NULLS LAST"
    )
    tree = _parse(text)
    cast = _one("Cast", tree)

    class _Token:
        name = "FLOAT"

    class _Dtype:
        this = _Token()

    cast.args["to"] = as_any(_Dtype())
    with pytest.raises(StoreRefusal) as caught:
        mod._walk(tree, _spec(text))
    full_message(caught.value, "forbidden construct")
    assert raised_in(caught, "_walk")
