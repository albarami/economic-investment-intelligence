"""Kill surviving mutants the public lint path does not separate.

Expectations are hand-worked. A direct call is used where an earlier branch
refuses the same input before the mutated line runs.
"""

from __future__ import annotations

import pytest
from product.tests.frames import raised_in
from product.tests.test_store_lint_survivors import (
    _parameter_result,
    full_message,
)
from product.tests.test_store_lint_survivors_b import (
    _GEOM,
    _SELECT,
    _mod,
    _one,
    _parse,
    _spec,
    as_any,
)

from eii_product.store.protocol import StoreRefusal


def test_scanners_reject_a_marker_after_a_skipped_span() -> None:
    """A comment or quote does not hide a later marker, and a bare word is safe."""
    mod = _mod()
    mod._function_calls("SELECT")
    mod._function_calls('"ab"')
    with pytest.raises(StoreRefusal) as quoted:
        mod._function_calls('"name" POWER(p.amount)')
    full_message(quoted.value, "forbidden construct")
    with pytest.raises(StoreRefusal) as commented:
        mod._function_calls("/*c*/ POWER(p.amount)")
    full_message(commented.value, "forbidden construct")
    assert mod._gap("Xab", 0) == (0, False)
    assert mod._dotted(".Xunit", 2) is False
    assert mod._skip_space("Xab", 0) == 0
    assert mod._keyword_at("_CAST", 1, "CAST") is False
    assert mod._keyword_at("x_CAST", 2, "CAST") is False
    mod._cast_words("SELECT 1")
    mod._cast_words("CAST(AS TEXT)")
    with pytest.raises(StoreRefusal) as dotted_type:
        mod._cast_words("CAST(AS.TEXT)")
    full_message(dotted_type.value, "forbidden construct")
    with pytest.raises(StoreRefusal) as second_cast:
        mod._cast_words("CAST(p.amount AS INTEGER) CAST(p.amount AS INT4)")
    full_message(second_cast.value, "forbidden construct")
    with pytest.raises(StoreRefusal) as cast_after_note:
        mod._cast_words("/*c*/ CAST(p.amount AS INT4)")
    full_message(cast_after_note.value, "forbidden construct")
    with pytest.raises(StoreRefusal) as bare_cast:
        mod._cast_words("CAST")
    full_message(bare_cast.value, "forbidden construct")
    mod._cast_words("CAST(p.amount AS text)")
    mod._cast_words("CAST(/*c*/ p.amount AS INTEGER)")
    mod._cast_words("CAST(--c\n p.amount AS INTEGER)")
    assert mod._last_as("AS TEXT") == 0
    assert mod._last_as("/*c*/AS") == 5
    assert mod._last_as("((x) AS TEXT") is None
    assert mod._last_as("x AS y AS") == 7
    assert mod._skip_lexical("x\n--a\nb\n?", 2) == 5
    assert mod._skip_lexical("*/ /*z*/", 3) == 8
    assert mod._skip_lexical("/*z*/b*/", 0) == 5


def test_mask_keeps_code_around_comments_and_quotes() -> None:
    """Each span is blanked only while its own closer rule matches."""
    mod = _mod()
    assert mod._mask("x-") == "x-"
    assert mod._mask("x\n--") == "x\n  "
    assert mod._mask("x\n-") == "x\n-"
    assert mod._mask("x\n--z") == "x\n   "
    assert mod._mask("ab/") == "ab/"
    assert mod._mask("ab/*") == "ab *"
    assert mod._mask("ab/*zz") == "ab   z"
    assert mod._mask("/*z*/'ab'") == "   */    "
    assert mod._mask("'a'X'b'") == "   X   "
    assert mod._mask("'") == " "
    assert mod._mask("/*z*/*/") == "   */*/"
    assert mod._mask("abcd'e''f'") == "abcd      "
    assert mod._skip_lexical("/**/?", 0) == 4


def test_parameters_ignore_placeholders_hidden_by_a_span() -> None:
    """A placeholder counts only in code, and a second one still counts."""
    mod = _mod()
    assert _parameter_result(mod, "x\n-- :hid\n:label", ("label",)) == "accepted"
    assert _parameter_result(mod, "x\n--:hid\n:label\n", ("label",)) == "accepted"
    assert _parameter_result(mod, "x\n-- :label", ()) == "accepted"
    assert _parameter_result(mod, "':x':label", ("label",)) == "accepted"
    assert _parameter_result(mod, '"x":label', ("label",)) == "accepted"
    assert _parameter_result(mod, ":label :other", ("label", "other")) == "accepted"
    assert _parameter_result(mod, "/*:h*/:label", ("label",)) == "accepted"
    assert _parameter_result(mod, "/*a*/:label*/", ("label",)) == "accepted"
    assert _parameter_result(mod, "/**/:label", ("label",)) == "accepted"
    assert _parameter_result(mod, "x*/ /*:hid*/:label", ("label",)) == "accepted"


def test_walk_distinct_star_and_subquery_in_are_direct() -> None:
    """The walk itself refuses these shapes. A later pass is not required."""
    mod = _mod()
    distinct = _parse("SELECT p.unit_id AS unit_id FROM control_rows AS p")
    distinct.args["distinct"] = as_any(True)
    with pytest.raises(StoreRefusal) as distinct_caught:
        mod._walk(distinct, _spec(_SELECT))
    full_message(distinct_caught.value, "forbidden construct")
    assert raised_in(distinct_caught, "_walk")
    starred = _parse("SELECT * FROM control_rows AS p")
    with pytest.raises(StoreRefusal) as star_caught:
        mod._walk(starred, _spec("SELECT * FROM control_rows AS p"))
    full_message(star_caught.value, "forbidden construct")
    nested = _parse(
        "SELECT p.unit_id AS unit_id FROM control_rows AS p "
        "WHERE p.label IN (SELECT q.label FROM control_rows AS q)"
    )
    with pytest.raises(StoreRefusal) as in_caught:
        mod._walk(nested, _spec(nested.sql(dialect="postgres")))
    full_message(in_caught.value, "forbidden construct")


def test_one_row_aggregate_direct_edges() -> None:
    """Joins, a second table, an empty list and a literal are not one row."""
    mod = _mod()
    joined = _parse(
        "SELECT SUM(p.amount) AS amount FROM control_rows AS p "
        "INNER JOIN (SELECT 1 AS unit_id) AS q ON TRUE"
    )
    assert mod._one_row_aggregate(joined) is False
    two = _parse(
        "SELECT SUM(p.amount) AS amount FROM control_rows AS p "
        "WHERE p.unit_id IN (SELECT q.unit_id FROM control_rows AS q)"
    )
    assert mod._one_row_aggregate(two) is False
    one = _parse("SELECT SUM(p.amount) AS amount FROM control_rows AS p")
    assert mod._one_row_aggregate(one) is True
    one.args["expressions"] = []
    assert mod._one_row_aggregate(one) is False
    literal = _parse("SELECT 1 AS amount FROM control_rows AS p")
    assert mod._one_row_aggregate(literal) is False
    bare = _one("Sum", _parse("SELECT SUM(p.amount) FROM control_rows AS p"))
    assert mod._item_is_aggregate(bare) is True
    added = _parse("SELECT SUM(p.amount + 0) AS amount FROM control_rows AS p")
    column = _one("Column", added)
    assert mod._under_aggregate(column) is True


def test_order_helpers_and_alias_defaults() -> None:
    """Non-select joins, empty alias slots and a short order list stay exact."""
    mod = _mod()

    class _Joined:
        def __init__(self) -> None:
            self.args = {"joins": (1,)}

    assert mod._outer_joins(as_any(_Joined())) is False
    assert mod._nulls_explicit("ORDER BY p.unit_id ASC NULLS LAST", 2) is False

    class _Named:
        name = "picked"

    class _Blank:
        alias = ""

    class _Numbered:
        alias = ""
        name = 1

    assert mod._alias(_Named()) == "picked"
    assert mod._alias(_Blank()) == ""
    assert mod._alias(_Numbered()) == ""
    no_from = _parse("SELECT 1 AS unit_id")
    assert (
        mod._unrenamed_cte_key(no_from, _spec("SELECT 1 AS unit_id"), ("unit_id",))
        is False
    )
    plain = _parse(_SELECT)
    assert mod._unrenamed_cte_key(plain, _spec(_SELECT), ()) is False


def test_depth_pieces_read_both_sides_of_an_addition() -> None:
    """``1 + g.depth`` is the depth step. A non-add and a bare object are not."""
    mod = _mod()
    step = _parse("SELECT 1 + g.depth AS depth FROM g")
    added = _one("Add", step)
    assert mod._added(added, "g") is True
    other = _parse("SELECT 2 + g.depth AS depth FROM g")
    assert mod._added(_one("Add", other), "g") is False
    literal = _one("Literal", step)
    assert mod._added(literal, "g") is False

    class _Bare:
        pass

    assert mod._depth_column(as_any(_Bare()), "g") is False
    with_node = _one(
        "With",
        _parse(
            "WITH RECURSIVE g AS (SELECT p.unit_id AS unit_id FROM control_rows AS p) "
            "SELECT g.unit_id AS unit_id FROM g"
        ),
    )
    with_node.args["expressions"] = as_any(1)
    with pytest.raises(AssertionError):
        mod._recursive_cte(with_node)


def test_geometry_raises_are_reached_one_at_a_time() -> None:
    """Each geometry refusal is the first refusal for that input."""
    mod = _mod()
    union = _parse(
        "SELECT p.shape FROM control_rows AS p "
        "UNION ALL SELECT q.shape FROM control_rows AS q"
    )
    spec = _spec(
        union.sql(dialect="postgres"),
        returns=(("shape", "geometry"),),
        tables=(_GEOM,),
    )
    with pytest.raises(StoreRefusal) as not_select:
        mod._geometry(union, spec)
    full_message(not_select.value, "forbidden construct")
    assert raised_in(not_select, "_geometry")
    aliased = _parse("SELECT p.shape AS shape FROM control_rows AS p")
    alias_spec = _spec(
        aliased.sql(dialect="postgres"),
        returns=(("shape", "geometry"),),
        order=("shape",),
        tables=(_GEOM,),
    )
    with pytest.raises(StoreRefusal) as wrapped:
        mod._geometry(aliased, alias_spec)
    full_message(wrapped.value, "forbidden construct")
    bare = _parse("SELECT p.shape FROM control_rows AS p")
    text_spec = _spec(
        bare.sql(dialect="postgres"),
        returns=(("shape", "text"),),
        tables=(_GEOM,),
    )
    with pytest.raises(StoreRefusal) as typed:
        mod._geometry(bare, text_spec)
    full_message(typed.value, "forbidden construct")
    column = _one("Column", aliased)
    column.parent = aliased
    with pytest.raises(StoreRefusal) as not_bare:
        mod._geometry(aliased, alias_spec)
    full_message(not_bare.value, "forbidden construct")
    rows = _parse(_SELECT)
    two = _spec(
        _SELECT,
        returns=(("unit_id", "text"), ("shape", "geometry")),
        order=("unit_id", "shape"),
    )
    with pytest.raises(StoreRefusal) as later:
        mod._geometry(rows, two)
    full_message(later.value, "forbidden construct")


def test_projected_type_of_a_bare_column_and_of_an_alias() -> None:
    """A bare column uses its own name. An alias uses the alias, then the column."""
    mod = _mod()
    bare = _parse("SELECT p.unit_id FROM control_rows AS p")
    spec = _spec(
        bare.sql(dialect="postgres"),
        returns=(("unit_id", "text"),),
    )
    assert mod._projected_type(bare, "unit_id", spec) == "string"
    assert mod._projected_type(bare, "missing", spec) == ""
    aliased = _parse("SELECT p.unit_id AS unit_id FROM control_rows AS p")
    assert mod._projected_type(aliased, "unit_id", _spec(_SELECT)) == "string"


def test_direct_slots_the_scanners_do_not_build() -> None:
    """These slots are reached by editing a parsed tree or by calling the helper."""
    mod = _mod()
    nested = _parse(
        "SELECT p.unit_id AS unit_id FROM control_rows AS p WHERE p.label IN (p.unit_id)"
    )
    with pytest.raises(StoreRefusal) as in_column:
        mod._walk(nested, _spec(nested.sql(dialect="postgres")))
    full_message(in_column.value, "forbidden construct")
    wrapped = _parse(
        "SELECT q.unit_id AS unit_id FROM "
        "(SELECT p.unit_id AS unit_id FROM control_rows AS p) AS q"
    )
    assert len(mod._selects(_one("Subquery", wrapped))) == 1
    traced = _parse(
        "WITH picked AS (SELECT p.unit_id FROM control_rows AS p) "
        "SELECT picked.unit_id AS unit_id FROM picked"
    )
    ctes = {
        mod._alias(node): node for node in traced.walk() if type(node).__name__ == "CTE"
    }
    assert mod._trace_unrenamed(ctes, "picked", "unit_id") == (
        "control_rows",
        "unit_id",
    )
    empty = _spec(traced.sql(dialect="postgres"), tables=())
    assert mod._unrenamed_cte_key(traced, empty, ("unit_id",)) is False
    source = _parse(_SELECT)
    source.args["from_"].args["this"] = "nope"
    assert mod._from_name(source) is None
    table = _one("Table", _parse(_SELECT))
    table.args["catalog"] = "extra"
    with pytest.raises(StoreRefusal) as catalog:
        mod._table(table, set(), {"control_rows"})
    full_message(catalog.value, "forbidden construct")
    missing = _parse("SELECT p.missing AS missing FROM control_rows AS p")
    with pytest.raises(StoreRefusal) as unresolved:
        mod._projected_type(missing, "missing", _spec(_SELECT))
    full_message(unresolved.value, "forbidden construct")
    body = _parse(
        "WITH RECURSIVE g AS (SELECT p.unit_id AS unit_id FROM control_rows AS p) "
        "SELECT g.unit_id AS unit_id FROM g"
    )
    cte = _one("CTE", body)
    cte.set("this", _one("Literal", _parse("SELECT 1 AS unit_id")))
    with pytest.raises(AssertionError):
        mod._recursive_cte(_one("With", body))
    shaped = _parse("SELECT p.unit_id, p.shape AS shape FROM control_rows AS p")
    for column in shaped.walk():
        if type(column).__name__ == "Column" and column.name == "shape":
            column.parent = shaped
    geom = _spec(
        shaped.sql(dialect="postgres"),
        returns=(("unit_id", "text"), ("shape", "geometry")),
        order=("unit_id", "shape"),
        tables=(_GEOM,),
    )
    with pytest.raises(StoreRefusal) as bare:
        mod._geometry(shaped, geom)
    full_message(bare.value, "forbidden construct")


def test_order_and_depth_read_the_first_dialect_tree() -> None:
    """The two dialect trees can differ. Order and depth read the first one."""
    import sqlglot

    mod = _mod()
    accepted = _parse("SELECT SUM(p.amount) AS amount FROM control_rows AS p")
    other = _parse(
        "WITH RECURSIVE g AS ("
        "SELECT p.amount AS amount, p.unit_id AS unit_id FROM control_rows AS p "
        "UNION ALL "
        "SELECT p.amount AS amount, p.unit_id AS unit_id FROM control_rows AS p "
        "INNER JOIN g ON p.unit_id = g.unit_id) "
        "SELECT g.amount AS amount FROM g"
    )
    calls = {"n": 0}
    real = sqlglot.parse

    def _fake(
        text: str, read: str | None = None, error_level: object = None
    ) -> list[object]:
        calls["n"] += 1
        return [accepted if calls["n"] == 1 else other]

    sqlglot.parse = _fake
    text = "SELECT SUM(p.amount) AS amount FROM control_rows AS p"
    try:
        mod._lint_one(_spec(text, returns=(("amount", "numeric"),), order=()))
    finally:
        sqlglot.parse = real
    assert calls["n"] == 2


def test_outer_is_cte_is_false_for_a_joined_common_table() -> None:
    """A join on the outer read is not the single common-table shape."""
    mod = _mod()
    text = (
        "WITH picked AS (SELECT p.unit_id AS unit_id FROM control_rows AS p) "
        "SELECT picked.unit_id AS unit_id FROM picked "
        "INNER JOIN control_rows AS q ON picked.unit_id = q.unit_id"
    )
    assert mod._outer_is_cte(_parse(text)) is False


def test_trace_stops_when_the_projection_is_renamed() -> None:
    """A renamed projection does not trace to the base key."""
    mod = _mod()
    text = (
        "WITH picked AS (SELECT p.unit_id AS label FROM control_rows AS p) "
        "SELECT picked.label AS label FROM picked"
    )
    tree = _parse(text)
    spec = _spec(text, returns=(("label", "text"),), order=("label",))
    assert mod._unrenamed_cte_key(tree, spec, ("label",)) is False


def test_one_row_aggregate_rejects_a_common_table_and_a_bare_column() -> None:
    """A common table, a join and a grouped sum are not one row."""
    mod = _mod()
    cte = _parse(
        "WITH picked AS (SELECT p.amount AS amount FROM control_rows AS p) "
        "SELECT SUM(picked.amount) AS amount FROM picked"
    )
    assert mod._one_row_aggregate(cte) is False
    joined = _parse(
        "SELECT SUM(p.amount) AS amount FROM control_rows AS p "
        "INNER JOIN control_rows AS q ON p.unit_id = q.unit_id"
    )
    assert mod._one_row_aggregate(joined) is False
    grouped = _parse(
        "SELECT SUM(p.amount) AS amount FROM control_rows AS p GROUP BY p.unit_id"
    )
    assert mod._one_row_aggregate(grouped) is False
    having = _parse(
        "SELECT SUM(p.amount) AS amount FROM control_rows AS p HAVING SUM(p.amount) > 0"
    )
    assert mod._one_row_aggregate(having) is False
    limited = _parse("SELECT SUM(p.amount) AS amount FROM control_rows AS p LIMIT 1")
    assert mod._one_row_aggregate(limited) is False


def test_from_name_falls_back_when_from_is_not_a_node() -> None:
    """sqlglot stores the source under from_. The from key is the other slot."""
    mod = _mod()
    tree = _parse(_SELECT)
    source = tree.args["from_"]
    tree.args["from_"] = "nope"
    tree.args["from"] = source
    assert mod._from_name(tree) == "control_rows"


def test_literal_in_rejects_an_empty_list_and_a_non_sequence() -> None:
    """An empty list and a non-sequence are not a literal IN list."""
    mod = _mod()
    node = _one(
        "In",
        _parse("SELECT p.unit_id FROM t AS p WHERE p.label IN ('SYN-a')"),
    )
    node.args["expressions"] = []
    assert mod._literal_in(node) is False
    node.args["expressions"] = as_any(1)
    assert mod._literal_in(node) is False


def test_depth_refuses_a_recursive_query_with_one_branch() -> None:
    """One branch has no recursive step, so the depth proof refuses it."""
    mod = _mod()
    text = (
        "WITH RECURSIVE g AS ("
        "SELECT p.unit_id AS unit_id, 0 AS depth FROM control_rows AS p) "
        "SELECT g.unit_id AS unit_id, g.depth AS depth FROM g"
    )
    tree = _parse(text)
    spec = _spec(
        text,
        name="graph_syn",
        returns=(("unit_id", "text"), ("depth", "bigint")),
        order=("unit_id", "depth"),
    )
    with pytest.raises(StoreRefusal) as caught:
        mod._depth(tree, spec)
    full_message(caught.value, "depth unproved")
    assert raised_in(caught, "_depth")


def test_projected_type_of_an_alias_and_of_a_missing_name() -> None:
    """The projected type is the column's contract type, or empty when absent."""
    mod = _mod()
    text = "SELECT p.unit_id AS unit_id, p.label AS label FROM control_rows AS p"
    tree = _parse(text)
    spec = _spec(
        text,
        returns=(("unit_id", "text"), ("label", "text")),
        order=("unit_id", "label"),
    )
    assert mod._projected_type(tree, "unit_id", spec) == "string"
    assert mod._projected_type(tree, "missing", spec) == ""
