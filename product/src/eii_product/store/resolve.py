"""Column types in the SELECT that holds the reference.

The lint and the geometry tie both ask this module. It cannot live in the lint:
the registry already loads before the lint, and the tie must not import the lint.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from typing import Protocol, runtime_checkable

from eii_product.store.protocol import StoreRefusal
from eii_product.store.registry import QuerySpec, _contract_column_type


@runtime_checkable
class _Node(Protocol):
    """The expression fields the resolver reads. The parser is not imported."""

    args: Mapping[str, object]
    parent: _Node | None
    this: _Node
    expressions: Sequence[_Node]
    name: str
    alias: str

    def walk(self) -> Iterator[_Node]:
        """Yield this expression and the expressions under it."""


def resolve_column_type(column: object, query: QuerySpec, reason: str) -> str:
    """Return the contract type of a column in the SELECT it stands in.

    Each SELECT, common-table expression and branch has its own alias map.
    An alias missing from that map, or held twice in it, is refused. In a
    non-recursive WITH, a body sees earlier siblings and enclosing definitions
    only; the outer query sees every sibling, and the nearer name wins. A
    reference to a common-table expression follows a bare, unrenamed projection
    back to the contract column. Any other projection is refused.

    Args:
        column: A column node from the parser.
        query: The query whose contract names the tables.
        reason: The refusal text of the caller that asked.

    Returns:
        The logical type stored on that contract column.

    Raises:
        StoreRefusal: The column cannot be tied to one contract column.
    """
    if not isinstance(column, _Node) or type(column).__name__ != "Column":
        raise StoreRefusal(reason)
    return _resolve(column, query, reason, ())


def _resolve(
    column: _Node, query: QuerySpec, reason: str, stack: tuple[_Node, ...]
) -> str:
    """Resolve one column, refusing a cycle through the same common-table body."""
    select = _owning_select(column)
    if select is None:
        raise StoreRefusal(reason)
    alias = _alias(column.args.get("table"))
    if alias == "":
        raise StoreRefusal(reason)
    sources, ambiguous = _scope(select)
    if alias in ambiguous or alias not in sources:
        raise StoreRefusal(reason)
    source = sources[alias]
    bodies = _cte_bodies(select)
    if source in bodies:
        body = bodies[source]
        if any(body is seen for seen in stack):
            raise StoreRefusal(reason)
        if type(body).__name__ != "Select":
            raise StoreRefusal(reason)
        output = column.name if isinstance(column.name, str) else ""
        projected = _unrenamed_column(body, output)
        if projected is None:
            raise StoreRefusal(reason)
        return _resolve(projected, query, reason, (*stack, body))
    if any(table.name == source for table in query.tables):
        output = column.name if isinstance(column.name, str) else ""
        return _contract_column_type(query, source, output, reason)
    raise StoreRefusal(reason)


def _owning_select(node: _Node) -> _Node | None:
    """The nearest SELECT above this node. A branch does not see its parent."""
    current = node.parent
    while current is not None:
        if type(current).__name__ == "Select":
            return current
        current = current.parent
    return None


def _scope(select: _Node) -> tuple[dict[str, str], set[str]]:
    """Alias to relation name for this SELECT's FROM and JOIN only."""
    sources: dict[str, str] = {}
    ambiguous: set[str] = set()
    for table in _from_tables(select):
        if type(table).__name__ != "Table" or not isinstance(table.name, str):
            continue
        alias = _alias(table) or table.name
        if alias == "":
            continue
        if alias in sources or alias in ambiguous:
            ambiguous.add(alias)
            sources.pop(alias, None)
            continue
        sources[alias] = table.name
    return sources, ambiguous


def _from_tables(select: _Node) -> list[_Node]:
    """Tables written in this SELECT, not tables inside another SELECT."""
    found: list[_Node] = []
    source = select.args.get("from_")
    if not isinstance(source, _Node):
        source = select.args.get("from")
    if isinstance(source, _Node):
        table = source.this if type(source).__name__ == "From" else source
        found.append(table)
    joins = select.args.get("joins")
    if isinstance(joins, Sequence) and not isinstance(joins, str):
        for join in joins:
            if isinstance(join, _Node) and isinstance(join.this, _Node):
                found.append(join.this)
    return found


def _cte_bodies(select: _Node) -> dict[str, _Node]:
    """Common-table names visible here, the nearer definition winning.

    The select that owns a WITH sees every sibling. A body of a non-recursive
    WITH sees only the earlier siblings of that WITH, plus names still visible
    further out. A recursive WITH keeps every name visible to its own bodies.
    """
    found: dict[str, _Node] = {}
    current: _Node | None = select
    container: _Node | None = None
    while current is not None:
        if type(current).__name__ == "Select":
            with_node = _with_clause(current)
            if isinstance(with_node, _Node):
                if current is select or bool(with_node.args.get("recursive")):
                    _record_visible(with_node, found, None)
                elif container is not None:
                    _record_visible(with_node, found, container)
            container = None
        elif type(current).__name__ == "CTE":
            container = current
        current = current.parent
    return found


def _with_clause(select: _Node) -> _Node | None:
    """The WITH node on this SELECT, under either argument name."""
    with_node = select.args.get("with_")
    if not isinstance(with_node, _Node):
        with_node = select.args.get("with")
    if isinstance(with_node, _Node):
        return with_node
    return None


def _record_visible(
    with_node: _Node, found: dict[str, _Node], before: _Node | None
) -> None:
    """Add visible bodies of this WITH without replacing a nearer name.

    ``before`` is the CTE whose body is being resolved. That CTE and every
    sibling after it stay hidden. ``None`` records every sibling.
    """
    raw = with_node.args.get("expressions")
    if not isinstance(raw, Sequence) or isinstance(raw, str):
        return
    if before is not None and not any(
        cte is before for cte in raw if isinstance(cte, _Node)
    ):
        return
    for cte in raw:
        if not isinstance(cte, _Node):
            continue
        if before is not None and cte is before:
            break
        name = _alias(cte)
        if name == "" or name in found:
            continue
        found[name] = cte.this


def _unrenamed_column(select: _Node, output_name: str) -> _Node | None:
    """The one bare column this SELECT projects under that name, if it is one."""
    found: list[_Node] = []
    for expr in select.expressions:
        column = _as_unrenamed(expr, output_name)
        if column is not None:
            found.append(column)
    if len(found) != 1:
        return None
    return found[0]


def _as_unrenamed(expr: _Node, output_name: str) -> _Node | None:
    """A column whose name is the output name. A rename or expression is none."""
    if output_name == "":
        return None
    if type(expr).__name__ == "Column" and expr.name == output_name:
        return expr
    if type(expr).__name__ != "Alias":
        return None
    inner = expr.this
    if type(inner).__name__ == "Column" and inner.name == output_name:
        if _alias(expr) == output_name:
            return inner
    return None


def _refuse_non_lower_name(tree: object, reason: str) -> None:
    """Refuse a table or common-table name that is not already lower case."""
    # PostgreSQL keeps the case of a quoted name and DuckDB matches names
    # without case, so a refusal is the only rule both stores obey the same way.
    if not isinstance(tree, _Node):
        raise StoreRefusal(reason)
    for node in tree.walk():
        spelling = _relation_spelling(node)
        if spelling is not None and spelling != spelling.lower():
            raise StoreRefusal(reason)


def _relation_spelling(node: object) -> str | None:
    """The name as written on a table or common-table identifier, or none.

    The spelling is the parser identifier's own ``this``. ``quoted`` says
    whether the query wrote quotes. Neither value is a folded form.
    """
    if type(node).__name__ != "Identifier":
        return None
    args = getattr(node, "args", None)
    if not isinstance(args, Mapping):
        return None
    parent = getattr(node, "parent", None)
    parent_kind = type(parent).__name__
    if parent_kind not in {"Table", "TableAlias"}:
        return None
    parent_args = getattr(parent, "args", None)
    if not isinstance(parent_args, Mapping) or parent_args.get("this") is not node:
        return None
    if parent_kind == "TableAlias":
        grand = getattr(parent, "parent", None)
        if type(grand).__name__ != "CTE":
            return None
    written = args.get("this")
    quoted = args.get("quoted")
    if not isinstance(written, str) or type(quoted) is not bool:
        return None
    return written


def _alias(node: object) -> str:
    """The alias spelling, or the name when the node has no alias of its own."""
    if node is None:
        return ""
    if isinstance(node, str):
        return node
    alias = getattr(node, "alias", None)
    if isinstance(alias, str) and alias:
        return alias
    name = getattr(node, "name", None)
    if isinstance(name, str):
        return name
    return ""
