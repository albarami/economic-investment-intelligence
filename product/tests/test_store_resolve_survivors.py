"""Kills surviving mutants of column resolution."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest

from eii_product.store.protocol import StoreRefusal
from eii_product.store.registry import ContractColumn, ContractTable, QuerySpec
from eii_product.store.resolve import resolve_column_type

_REASON = "forbidden construct"
_KEPT = ContractTable(
    "kept",
    "SYN-anchor",
    ("label",),
    (
        ContractColumn("label", "text", False),
        ContractColumn("qty", "bigint", False),
        ContractColumn("XXXX", "text", False),
    ),
)
_OTHER = ContractTable(
    "other",
    "SYN-anchor",
    ("qty",),
    (ContractColumn("qty", "bigint", False),),
)


def full_text(caught: pytest.ExceptionInfo[BaseException], literal: str) -> None:
    """Compare the whole message with one hand-written literal."""
    assert str(caught.value) == literal


def unchecked(value: object) -> Any:
    """Pass one value the annotation rejects through a single typed boundary."""
    return value


class Expr:
    """One parser node. The class name is what the resolver matches."""

    def __init__(self) -> None:
        self.args: dict[str, object] = {}
        self.parent: Expr | None = None
        self.this: Expr | None = None
        self.expressions: tuple[object, ...] = ()
        self.name: object = ""
        self.alias: object = ""

    def walk(self) -> Iterator[object]:
        yield self


Column = type("Column", (Expr,), {})
Select = type("Select", (Expr,), {})
Table = type("Table", (Expr,), {})
From = type("From", (Expr,), {})
Join = type("Join", (Expr,), {})
Alias = type("Alias", (Expr,), {})
CTE = type("CTE", (Expr,), {})
With = type("With", (Expr,), {})
Subquery = type("Subquery", (Expr,), {})


def test_a_bare_kept_column_resolves_and_xxxx_is_a_real_alias() -> None:
    """kept.label is text. The marker spelling is an ordinary alias too."""
    assert _resolve(_direct("label", "kept")) == "text"
    assert _resolve(_direct("label", "XXXX", _table("kept", "XXXX"))) == "text"


def test_a_column_that_is_not_a_node_is_refused() -> None:
    """The class name Column is not enough. The node fields have to be there."""

    class Column:
        """A class of the parser's name with none of the parser's fields."""

    bare = Column()
    with pytest.raises(StoreRefusal) as caught:
        resolve_column_type(bare, _query(_KEPT), _REASON)
    full_text(caught, _REASON)
    with pytest.raises(StoreRefusal) as plain:
        resolve_column_type(object(), _query(_KEPT), _REASON)
    full_text(plain, _REASON)


def test_a_column_with_no_select_or_no_alias_is_refused() -> None:
    """No owning SELECT, and an empty table alias, are the same refusal."""
    orphan = Column()
    orphan.name = "label"
    orphan.args["table"] = "kept"
    with pytest.raises(StoreRefusal) as caught:
        resolve_column_type(orphan, _query(_KEPT), _REASON)
    full_text(caught, _REASON)
    with pytest.raises(StoreRefusal) as empty:
        resolve_column_type(_direct("label", None), _query(_KEPT), _REASON)
    full_text(empty, _REASON)
    hidden = _select((_table("kept", "XXXX"),), "label", None)
    with pytest.raises(StoreRefusal) as marker:
        resolve_column_type(hidden.expressions[0], _query(_KEPT), _REASON)
    full_text(marker, _REASON)


def test_an_unknown_alias_is_refused() -> None:
    """An alias that no FROM item owns is refused, not looked up anyway."""
    with pytest.raises(StoreRefusal) as caught:
        resolve_column_type(_direct("label", "missing"), _query(_KEPT), _REASON)
    full_text(caught, _REASON)


def test_a_repeated_alias_is_ambiguous() -> None:
    """Three copies of one alias stay ambiguous. The first copy does not win."""
    select = _select(
        (_table("kept", "item"), _table("other", "item"), _table("kept", "item")),
        "label",
        "item",
    )
    with pytest.raises(StoreRefusal) as caught:
        resolve_column_type(select.expressions[0], _query(_KEPT, _OTHER), _REASON)
    full_text(caught, _REASON)


def test_a_later_table_survives_a_blank_and_a_duplicate() -> None:
    """A blank alias and a repeated alias do not hide the table after them."""
    blank = _select((_table("", ""), _table("kept")), "label", "kept")
    assert _resolve(blank.expressions[0]) == "text"
    repeated = _select(
        (_table("other", "item"), _table("kept", "item"), _table("kept")),
        "label",
        "kept",
    )
    assert _resolve(repeated.expressions[0]) == "text"
    skipped = _select((Subquery(), _table("kept")), "label", "kept")
    assert _resolve(skipped.expressions[0]) == "text"


def test_a_non_table_does_not_become_a_source() -> None:
    """A subquery that happens to carry a name is not a FROM source."""
    decoy = Subquery()
    decoy.alias = "decoy"
    decoy.name = "kept"
    select = _select((decoy,), "label", "decoy")
    with pytest.raises(StoreRefusal) as caught:
        resolve_column_type(select.expressions[0], _query(_KEPT), _REASON)
    full_text(caught, _REASON)


def test_from_is_read_by_that_name_and_a_table_is_not_unwrapped() -> None:
    """The fallback key is from. A table standing there is the table itself."""
    select = _select((_table("kept"),), "label", "kept")
    assert _resolve(select.expressions[0]) == "text"
    wrapped = Select()
    table = _table("kept")
    wrapper = From()
    wrapper.this = table
    table.parent = wrapper
    wrapped.args["from"] = wrapper
    wrapper.parent = wrapped
    column = _column("label", "kept", wrapped)
    wrapped.expressions = (column,)
    assert _resolve(column) == "text"


def test_a_join_that_is_not_a_node_is_ignored() -> None:
    """Only a join node contributes its table. A bag with a table does not."""
    table = _table("kept")
    select = Select()
    select.args["joins"] = (_Bag(table),)
    column = _column("label", "kept", select)
    select.expressions = (column,)
    with pytest.raises(StoreRefusal) as caught:
        resolve_column_type(column, _query(_KEPT), _REASON)
    full_text(caught, _REASON)


def test_alias_and_name_attributes_are_optional() -> None:
    """A missing alias falls through to the name. A missing name is no alias."""
    blob = Expr()
    del blob.alias
    blob.name = "kept"
    assert _resolve(_direct("label", blob)) == "text"
    blob = Expr()
    blob.alias = ""
    del blob.name
    with pytest.raises(StoreRefusal) as caught:
        resolve_column_type(_direct("label", blob), _query(_KEPT), _REASON)
    full_text(caught, _REASON)
    named = Expr()
    named.alias = ""
    named.name = None
    select_x = _select((_table("kept", "XXXX"),), "label", named)
    with pytest.raises(StoreRefusal) as marker:
        resolve_column_type(select_x.expressions[0], _query(_KEPT), _REASON)
    full_text(marker, _REASON)


def test_a_recursive_with_sees_a_later_body() -> None:
    """A recursive WITH lets the earlier body read the later body."""
    kept = _body("kept", "label")
    later = _cte("later", kept)
    earlier_body = _body_ref("later", "label")
    earlier = _cte("earlier", earlier_body)
    outer = _outer_with((earlier, later), "earlier", "label", recursive=True)
    assert _resolve(outer.expressions[0]) == "text"


def test_the_with_clause_is_read_under_with() -> None:
    """The fallback key is with. An earlier sibling stays visible through it."""
    kept = _body("kept", "label")
    first = _cte("earlier", kept)
    second_body = _body_ref("earlier", "label")
    second = _cte("later", second_body)
    outer = _outer_with((first, second), "later", "label", recursive=False)
    assert _resolve(outer.expressions[0]) == "text"


def test_a_stray_container_does_not_reveal_an_outer_name() -> None:
    """A CTE that is not in this WITH does not unlock the names of the WITH."""
    kept = _body("kept", "label")
    seen = _cte("seen", kept)
    stray = CTE()
    inner = Select()
    inner.parent = stray
    stray.parent = None
    column = _column("label", "seen", inner)
    inner.expressions = (column,)
    inner.args["from"] = _attach(_table("seen"), inner)
    outer = Select()
    holder = With()
    holder.args["expressions"] = (seen,)
    holder.args["recursive"] = False
    _attach(seen, holder)
    _attach(holder, outer)
    outer.args["with"] = holder
    _attach(stray, holder)
    with pytest.raises(StoreRefusal) as caught:
        resolve_column_type(column, _query(_KEPT), _REASON)
    full_text(caught, _REASON)


def test_a_nearer_common_table_is_kept() -> None:
    """The nearer body wins when both WITH clauses reuse one name."""
    far = _cte("wrap", _body("kept", "label"))
    pad = _cte("pad", _body("kept", "label"))
    inner = _outer_with(
        (_cte("wrap", _body("other", "qty")),), "wrap", "qty", recursive=False
    )
    outer = Select()
    holder = With()
    holder.args["expressions"] = (far, pad)
    holder.args["recursive"] = False
    _attach(holder, outer)
    outer.args["with"] = holder
    _attach(far, holder)
    _attach(pad, holder)
    pad.this = inner
    _attach(inner, pad)
    assert _resolve(inner.expressions[0], _KEPT, _OTHER) == "bigint"


def test_a_common_table_named_xxxx_is_visible() -> None:
    """The marker spelling is a normal common-table name."""
    body = _body("kept", "label")
    named = _cte("XXXX", body)
    outer = _outer_with((named,), "XXXX", "label", recursive=False)
    assert _resolve(outer.expressions[0]) == "text"


def test_common_table_lists_skip_non_nodes_and_reject_a_bare_node() -> None:
    """A non-node is skipped. One node where a list belongs hides the name."""
    body = _body("kept", "label")
    named = _cte("earlier", body)
    listed = _outer_with(("SYN-skip", named), "earlier", "label", recursive=False)
    assert _resolve(listed.expressions[0]) == "text"
    bare = _outer_with(named, "earlier", "label", recursive=False)
    with pytest.raises(StoreRefusal) as caught:
        resolve_column_type(bare.expressions[0], _query(_KEPT), _REASON)
    full_text(caught, _REASON)


def test_an_empty_common_table_name_does_not_hide_the_next() -> None:
    """A body with no name is skipped. The named body after it stays visible."""
    blank = _cte("", _body("other", "qty"))
    named = _cte("earlier", _body("kept", "label"))
    outer = _outer_with((blank, named), "earlier", "label", recursive=False)
    assert _resolve(outer.expressions[0]) == "text"


def test_only_a_bare_column_of_that_name_is_a_projection() -> None:
    """A rename, another column, and a non-text name are not the asked output."""
    renamed = _projected(_aliased(_col_node("qty"), "label"), "label")
    with pytest.raises(StoreRefusal) as caught:
        resolve_column_type(renamed, _query(_KEPT), _REASON)
    full_text(caught, _REASON)
    other = _projected(_col_node("qty"), "label")
    with pytest.raises(StoreRefusal) as other_caught:
        resolve_column_type(other, _query(_KEPT), _REASON)
    full_text(other_caught, _REASON)
    marker = _projected(_col_node("XXXX"), "XXXX")
    assert resolve_column_type(marker, _query(_KEPT), _REASON) == "text"
    by_object = _projected(_col_node(7), 7)
    with pytest.raises(StoreRefusal) as object_name:
        resolve_column_type(by_object, _query(_kept_named(7)), _REASON)
    full_text(object_name, _REASON)
    forced = _projected(_col_node("XXXX"), None)
    with pytest.raises(StoreRefusal) as forced_name:
        resolve_column_type(forced, _query(_KEPT), _REASON)
    full_text(forced_name, _REASON)


def test_a_direct_name_must_be_text_to_name_a_contract_column() -> None:
    """A non-text column name does not select a contract column."""
    numbered = _select((_table("kept"),), 7, "kept")
    with pytest.raises(StoreRefusal) as caught:
        resolve_column_type(numbered.expressions[0], _query(_kept_named(7)), _REASON)
    full_text(caught, _REASON)
    marked = _select((_table("kept"),), None, "kept")
    with pytest.raises(StoreRefusal) as marker:
        resolve_column_type(marked.expressions[0], _query(_KEPT), _REASON)
    full_text(marker, _REASON)
    missing = _select((_table("kept"),), "absent", "kept")
    with pytest.raises(StoreRefusal) as absent:
        resolve_column_type(missing.expressions[0], _query(_KEPT), _REASON)
    full_text(absent, _REASON)


def test_a_cycle_and_a_non_select_body_are_refused() -> None:
    """A body that reads itself, and a body that is not a SELECT, are refused."""
    self_body = _body_ref("loop", "label")
    looping = _cte("loop", self_body)
    outer = _outer_with((looping,), "loop", "label", recursive=True)
    with pytest.raises(StoreRefusal) as caught:
        resolve_column_type(outer.expressions[0], _query(_KEPT), _REASON)
    full_text(caught, _REASON)
    table = _table("kept")
    bad = _cte("earlier", table)
    holder = _outer_with((bad,), "earlier", "label", recursive=False)
    with pytest.raises(StoreRefusal) as body:
        resolve_column_type(holder.expressions[0], _query(_KEPT), _REASON)
    full_text(body, _REASON)


def _resolve(column: object, *tables: ContractTable) -> str:
    chosen = tables or (_KEPT,)
    return resolve_column_type(column, _query(*chosen), _REASON)


def _query(*tables: ContractTable) -> QuerySpec:
    return QuerySpec("syn_q", (), (), (), "select syn_kept", "ab" * 32, tables)


def _kept_named(name: object) -> ContractTable:
    return ContractTable(
        "kept",
        "SYN-anchor",
        ("label",),
        (ContractColumn(unchecked(name), "bigint", False),),
    )


def _direct(column_name: object, table: object, source: Expr | None = None) -> Expr:
    select = Select()
    if source is None:
        source = _table("kept")
    _attach(source, select)
    select.args["from"] = source
    column = _column(column_name, table, select)
    select.expressions = (column,)
    return column


def _select(sources: tuple[Expr, ...], column_name: object, table: object) -> Expr:
    select = Select()
    first, *rest = sources
    _attach(first, select)
    select.args["from"] = first
    joins = []
    for source in rest:
        join = Join()
        join.this = source
        _attach(source, join)
        _attach(join, select)
        joins.append(join)
    if joins:
        select.args["joins"] = tuple(joins)
    column = _column(column_name, table, select)
    select.expressions = (column,)
    return select


def _table(name: object, alias: object = "") -> Expr:
    node = Table()
    node.name = name
    node.alias = alias
    return node


def _column(name: object, table: object, parent: Expr) -> Expr:
    node = Column()
    node.name = name
    node.args["table"] = table
    node.parent = parent
    return node


def _attach(child: Expr, parent: Expr) -> Expr:
    child.parent = parent
    return child


def _col_node(name: object) -> Expr:
    node = Column()
    node.name = name
    node.args["table"] = "kept"
    return node


def _aliased(inner: Expr, alias: str) -> Expr:
    node = Alias()
    node.this = inner
    node.alias = alias
    _attach(inner, node)
    return node


def _body(table_name: str, column_name: object) -> Expr:
    select = Select()
    table = _attach(_table(table_name), select)
    select.args["from"] = table
    column = _column(column_name, table_name, select)
    select.expressions = (column,)
    return select


def _body_ref(alias: str, column_name: object) -> Expr:
    return _body(alias, column_name)


def _cte(alias: str, body: Expr) -> Expr:
    node = CTE()
    node.alias = alias
    node.this = body
    _attach(body, node)
    return node


def _outer_with(
    expressions: object, alias: str, column_name: object, *, recursive: bool
) -> Expr:
    outer = Select()
    holder = With()
    holder.args["expressions"] = expressions
    holder.args["recursive"] = recursive
    _attach(holder, outer)
    outer.args["with"] = holder
    if isinstance(expressions, tuple):
        for item in expressions:
            if isinstance(item, Expr):
                _attach(item, holder)
    elif isinstance(expressions, Expr):
        _attach(expressions, holder)
    table = _attach(_table(alias), outer)
    outer.args["from"] = table
    column = _column(column_name, alias, outer)
    outer.expressions = (column,)
    return outer


def _projected(expr: Expr, output: object) -> Expr:
    """A reference whose common-table body projects expr under output."""
    body = Select()
    _attach(expr, body)
    body.expressions = (expr,)
    body.args["from"] = _attach(_table("kept"), body)
    if isinstance(expr, Alias):
        expr.this.args["table"] = "kept"
        _attach(expr.this, body)
    else:
        expr.args["table"] = "kept"
    named = _cte("wrap", body)
    return _outer_with((named,), "wrap", output, recursive=False).expressions[0]


class _Bag:
    """A join that is not a parser node."""

    def __init__(self, this: Expr) -> None:
        self.this = this
