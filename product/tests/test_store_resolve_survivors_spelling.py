"""Kills surviving mutants of relation spelling."""

from __future__ import annotations

import importlib.util
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType

import pytest

from eii_product.store.protocol import StoreRefusal
from eii_product.store.resolve import _refuse_non_lower_name

_REASON = "forbidden construct"


def full_text(caught: pytest.ExceptionInfo[BaseException], literal: str) -> None:
    """Compare the whole message with one hand-written literal."""
    assert str(caught.value) == literal


class Expr:
    """One parser node. The class name is what the spelling check matches."""

    def __init__(self) -> None:
        self.args: dict[str, object] = {}
        self.parent: Expr | None = None
        self.this: Expr | None = None
        self.expressions: tuple[object, ...] = ()
        self.name: object = ""
        self.alias: object = ""

    def walk(self) -> Iterator[object]:
        yield self


Select = type("Select", (Expr,), {})
Table = type("Table", (Expr,), {})
CTE = type("CTE", (Expr,), {})
Identifier = type("Identifier", (Expr,), {})
TableAlias = type("TableAlias", (Expr,), {})


def test_mixed_case_is_refused_only_for_a_table_or_a_common_table() -> None:
    """Table and CTE spellings are refused. An ordinary alias spelling is not."""
    with pytest.raises(StoreRefusal) as table_name:
        _refuse_non_lower_name(
            _over(_identifier("Kept", True, _table("kept"))), _REASON
        )
    full_text(table_name, _REASON)
    with pytest.raises(StoreRefusal) as caught:
        _refuse_non_lower_name(_over(_table_alias("Kept", CTE())), _REASON)
    full_text(caught, _REASON)
    _refuse_non_lower_name(_over(_table_alias("Kept", Select())), _REASON)
    detached = _identifier("Kept", True, _table("kept"))
    detached.parent.args["this"] = Expr()
    _refuse_non_lower_name(_over(detached), _REASON)
    _refuse_non_lower_name(_over(_identifier("Kept", None, _table("kept"))), _REASON)


def test_a_non_text_name_does_not_follow_a_common_table() -> None:
    """A name that is not text does not select the common-table column."""
    builders = _column_trees()
    body = builders._body("kept", "label")
    named = builders._cte("wrap", body)
    outer = builders._outer_with((named,), "wrap", _EqualLabel(), recursive=False)
    with pytest.raises(StoreRefusal) as caught:
        builders.resolve_column_type(
            outer.expressions[0], builders._query(builders._KEPT), _REASON
        )
    full_text(caught, _REASON)


def test_a_tree_that_is_not_a_node_is_refused() -> None:
    """A value that is not a parser node is refused with the caller's reason."""
    with pytest.raises(StoreRefusal) as caught:
        _refuse_non_lower_name(object(), _REASON)
    full_text(caught, _REASON)


def test_a_broken_identifier_has_no_spelling() -> None:
    """A missing args, parent or grandparent is not a spelling to refuse."""
    _refuse_non_lower_name(_over(_raw_identifier()), _REASON)
    _refuse_non_lower_name(
        _over(_raw_identifier(args={"this": "Kept", "quoted": True})), _REASON
    )
    no_parent_args = _identifier("Kept", True, Table())
    del no_parent_args.parent.args
    _refuse_non_lower_name(_over(no_parent_args), _REASON)
    no_grand = _table_alias("Kept", None)
    del no_grand.parent.parent
    _refuse_non_lower_name(_over(no_grand), _REASON)


class _EqualLabel:
    """A non-text name that compares equal to the contract column."""

    def __eq__(self, other: object) -> bool:
        return other == "label"


def _column_trees() -> ModuleType:
    """Load the resolver builders. That file is not an importable package."""
    spec = importlib.util.spec_from_file_location(
        "resolve_survivor_trees",
        Path(__file__).with_name("test_store_resolve_survivors.py"),
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("resolver survivor builders are missing")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _table(name: object) -> Expr:
    node = Table()
    node.name = name
    return node


def _attach(child: Expr, parent: Expr) -> Expr:
    child.parent = parent
    return child


def _identifier(written: str, quoted: object, parent: Expr) -> Expr:
    node = Identifier()
    node.args = {"this": written, "quoted": quoted}
    _attach(node, parent)
    parent.args["this"] = node
    parent.this = node
    return node


def _table_alias(written: str, grand: Expr | None) -> Expr:
    alias = TableAlias()
    if grand is not None:
        _attach(alias, grand)
    else:
        alias.parent = Expr()
    return _identifier(written, True, alias)


def _raw_identifier(**attrs: object) -> object:
    class Identifier:
        def __init__(self) -> None:
            for key, value in attrs.items():
                setattr(self, key, value)

    return Identifier()


def _over(node: object) -> Expr:
    root = Select()

    def walk() -> Iterator[object]:
        yield root
        yield node

    root.walk = walk
    return root
