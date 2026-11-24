"""Portable-subset lint. A query is never accepted only because it parsed."""

from __future__ import annotations

import re
from collections.abc import Iterator, Mapping, Sequence
from typing import Protocol, runtime_checkable

from eii_product.store.protocol import StoreRefusal
from eii_product.store.registry import (
    Inventory,
    QuerySpec,
    _quoted_end,
    approximate_contract_type,
)
from eii_product.store.resolve import _refuse_non_lower_name, resolve_column_type


@runtime_checkable
class _Node(Protocol):
    """The expression fields the lint reads. The parser is not imported for this."""

    args: Mapping[str, object]
    parent: _Node | None
    this: _Node
    expression: _Node
    expressions: Sequence[_Node]
    name: str
    alias: str

    def walk(self) -> Iterator[_Node]:
        """Yield this expression and the expressions under it."""


_PLACEHOLDER = re.compile(r":([a-z_][a-z0-9_]*)(?!\w)")
_NULLS = re.compile(r"\bNULLS\s+(?:FIRST|LAST)\b", re.IGNORECASE)
_DIRECTION = re.compile(r"\b(?:ASC|DESC)\b", re.IGNORECASE)
_ORDER = re.compile(r"\bORDER\s+BY\b(?P<body>.*)\Z", re.IGNORECASE | re.DOTALL)
_LIMIT = re.compile(r"\bLIMIT\b.*\Z", re.IGNORECASE | re.DOTALL)
_CASTS = frozenset({"INT", "BIGINT", "TEXT", "DATE"})
_CAST_WORDS = frozenset({"BIGINT", "INTEGER", "TEXT", "DATE"})
_BARE_INT = re.compile(r"\bAS\s+INT\b(?!EGER)", re.IGNORECASE)
_INTEGER_LITERAL = re.compile(r"[0-9]+\Z")
# Document 08 section 3.2. A word before "(" must be one of these,
# or a grouping keyword in _GROUPING_PAREN.
# Functions: COALESCE, NULLIF, CAST (expressions); SUM, COUNT, MIN, MAX (aggregates).
# Parenthesis keywords: IN and ANY (predicates); AS (WITH); NOT (predicates, grouped).
_CALL_WORDS = frozenset(
    {
        "ANY",
        "AS",
        "CAST",
        "COALESCE",
        "COUNT",
        "IN",
        "MAX",
        "MIN",
        "NOT",
        "NULLIF",
        "SUM",
    }
)
# A grouping "(" after one of these is syntax, not a function call.
_GROUPING_PAREN = frozenset(
    {
        "AND",
        "ELSE",
        "HAVING",
        "NOT",
        "ON",
        "OR",
        "THEN",
        "WHEN",
        "WHERE",
    }
)
_AGGREGATE_CALLS = frozenset({"Count", "Max", "Min", "Sum"})
_ALLOWED = frozenset(
    {
        "Add",
        "Alias",
        "And",
        "Any",
        "Between",
        "CTE",
        "Case",
        "Cast",
        "Coalesce",
        "Column",
        "Count",
        "DataType",
        "Distinct",
        "EQ",
        "From",
        "GT",
        "GTE",
        "Group",
        "Having",
        "Identifier",
        "If",
        "In",
        "Is",
        "Join",
        "LT",
        "LTE",
        "Limit",
        "Literal",
        "Max",
        "Min",
        "Mul",
        "NEQ",
        "Neg",
        "Not",
        "Null",
        "Nullif",
        "Or",
        "Order",
        "Ordered",
        "Paren",
        "Placeholder",
        "Select",
        "Star",
        "Sub",
        "Sum",
        "Table",
        "TableAlias",
        "Union",
        "Where",
        "With",
    }
)


def lint_inventory(inventory: Inventory) -> Inventory:
    """Parse every query under both dialects and walk the allow-list."""
    for query in inventory.queries:
        _lint_one(query)
    return inventory


def _lint_one(query: QuerySpec) -> None:
    import sqlglot
    from sqlglot.errors import SqlglotError

    _lexical(query.text)
    _cast_words(query.text)
    _function_calls(query.text)
    trees: list[_Node] = []
    for dialect in ("postgres", "duckdb"):
        try:
            parsed = sqlglot.parse(
                query.text, read=dialect, error_level=sqlglot.ErrorLevel.RAISE
            )
        except SqlglotError:
            raise StoreRefusal("parse invalid") from None
        if len(parsed) != 1 or parsed[0] is None or not isinstance(parsed[0], _Node):
            raise StoreRefusal("parse invalid")
        trees.append(parsed[0])
    for tree in trees:
        if type(tree).__name__ == "Command":
            raise StoreRefusal("parse invalid")
        if type(tree).__name__ not in {"Select", "Union"}:
            raise StoreRefusal("forbidden construct")
        _refuse_non_lower_name(tree, "forbidden construct")
        _refuse_contract_cte(tree, query)
        _walk(tree, query)
        _projection(tree, query)
        _geometry(tree, query)
    _parameters(query)
    _order(trees[0], query)
    _depth(trees[0], query)


def _lexical(sql: str) -> None:
    if "%" in sql:
        raise StoreRefusal("forbidden construct")
    if _BARE_INT.search(_mask(sql)):
        raise StoreRefusal("forbidden construct")
    index = 0
    length = len(sql)
    while index < length:
        if sql.startswith("--", index):
            end = sql.find("\n", index)
            end = length if end < 0 else end
            _hidden(sql[index:end])
            index = end
            continue
        if sql.startswith("/*", index):
            end = sql.find("*/", index + 2)
            if end < 0:
                raise StoreRefusal("parse invalid")
            end += 2
            _hidden(sql[index:end])
            index = end
            continue
        if sql[index] == "'":
            end = _string_end(sql, index)
            _hidden(sql[index:end])
            index = end
            continue
        if sql[index] == '"':
            end = _quoted_end(sql, index)
            _hidden(sql[index:end])
            index = end
            continue
        if sql[index] == "?":
            raise StoreRefusal("forbidden construct")
        if sql[index] == ";":
            raise StoreRefusal("parse invalid")
        if sql.startswith("::", index):
            raise StoreRefusal("forbidden construct")
        index += 1


def _function_calls(sql: str) -> None:
    """Every word before "(" is an admitted function or parenthesis keyword."""
    index = 0
    length = len(sql)
    while index < length:
        if sql[index] == '"':
            end = _quoted_end(sql, index)
            cursor, _saw = _gap(sql, end)
            if cursor < length and sql[cursor] == "(":
                raise StoreRefusal("forbidden construct")
            index = end
            continue
        skipped = _skip_lexical(sql, index)
        if skipped != index:
            index = skipped
            continue
        if sql[index].isalpha() or sql[index] == "_":
            end = index + 1
            while end < length and (sql[end].isalnum() or sql[end] == "_"):
                end += 1
            word = sql[index:end]
            cursor, saw_comment = _gap(sql, end)
            if cursor < length and sql[cursor] == "(":
                admitted = (
                    word.upper() in _CALL_WORDS or word.upper() in _GROUPING_PAREN
                )
                if saw_comment or _dotted(sql, index) or not admitted:
                    raise StoreRefusal("forbidden construct")
            index = end
            continue
        index += 1


def _gap(sql: str, index: int) -> tuple[int, bool]:
    """Skip space and comments. The flag is true when a comment was skipped."""
    saw_comment = False
    length = len(sql)
    while index < length:
        if sql[index] in " \t\r\n":
            index += 1
            continue
        if sql.startswith("--", index) or sql.startswith("/*", index):
            saw_comment = True
            nxt = _skip_lexical(sql, index)
            if nxt == index:
                break
            index = nxt
            continue
        break
    return index, saw_comment


def _dotted(sql: str, word_at: int) -> bool:
    """True when a dot, ignoring space, qualifies the word."""
    index = word_at - 1
    while index >= 0 and sql[index] in " \t\r\n":
        index -= 1
    return index >= 0 and sql[index] == "."


def _walk(tree: _Node, query: QuerySpec) -> None:
    cte_names = _cte_names(tree)
    contract = {table.name for table in query.tables}
    for node in tree.walk():
        kind = type(node).__name__
        if kind not in _ALLOWED:
            raise StoreRefusal("forbidden construct")
        if kind == "Select" and node.args.get("distinct"):
            raise StoreRefusal("forbidden construct")
        if kind == "Distinct" and type(node.parent).__name__ != "Count":
            raise StoreRefusal("forbidden construct")
        if kind == "Distinct" and type(node.parent).__name__ == "Count":
            expressions = node.args.get("expressions")
            if (
                isinstance(expressions, Sequence)
                and not isinstance(expressions, str)
                and len(expressions) > 1
            ):
                raise StoreRefusal("forbidden construct")
        if kind == "Literal" and not _integer_or_text(node):
            raise StoreRefusal("forbidden construct")
        if kind == "Placeholder" and not isinstance(node.args.get("this"), str):
            raise StoreRefusal("forbidden construct")
        if kind == "Star" and type(node.parent).__name__ != "Count":
            raise StoreRefusal("forbidden construct")
        if kind == "Union" and node.args.get("distinct") is not False:
            raise StoreRefusal("forbidden construct")
        if kind == "Join" and not _allowed_join(node):
            raise StoreRefusal("forbidden construct")
        if kind == "Limit" and not _allowed_limit(node):
            raise StoreRefusal("forbidden construct")
        if kind == "Limit":
            _limit_param(node, query)
        if kind == "In" and not _literal_in(node):
            raise StoreRefusal("forbidden construct")
        if kind == "Any" and not _placeholder_any(node):
            raise StoreRefusal("forbidden construct")
        if kind == "Cast" and not _allowed_cast(node):
            raise StoreRefusal("forbidden construct")
        if kind == "Column" and node.args.get("table") is None:
            raise StoreRefusal("forbidden construct")
        if kind == "Table":
            _table(node, cte_names, contract)
        if kind == "Sum":
            _sum(node, query)


def _order(tree: _Node, query: QuerySpec) -> None:
    if type(tree).__name__ == "Union" or _outer_joins(tree):
        if not _recursive(tree):
            raise StoreRefusal("order unproved")
    ordered = (
        _child(tree.args.get("order")) if type(tree).__name__ == "Select" else None
    )
    if ordered is None:
        if query.order == () and _one_row_aggregate(tree):
            return
        raise StoreRefusal("order unproved")
    names: list[str] = []
    for item in ordered.expressions:
        if item.args.get("desc") is None:
            raise StoreRefusal("order unproved")
        names.append(_column_name(item.this))
    if tuple(names) != query.order or not _nulls_explicit(query.text, len(names)):
        raise StoreRefusal("order unproved")
    if _recursive(tree):
        keys = [key for table in query.tables for key in table.key]
        if not keys or not set(keys).issubset(names):
            raise StoreRefusal("order unproved")
        return
    if _outer_is_cte(tree):
        if not _unrenamed_cte_key(tree, query, tuple(names)):
            raise StoreRefusal("order unproved")
        return
    group = _child(tree.args.get("group"))
    if group is not None:
        grouped = tuple(_column_name(expr) for expr in group.expressions)
        if tuple(names) != grouped:
            raise StoreRefusal("order unproved")
        return
    base = _base_tables(tree)
    if len(base) != 1:
        raise StoreRefusal("order unproved")
    key = _key(query, base[0])
    if not key or not set(key).issubset(names):
        raise StoreRefusal("order unproved")


def _one_row_aggregate(tree: _Node) -> bool:
    """One select, one table, no group: every item an aggregate, so one row."""
    if type(tree).__name__ != "Select":
        return False
    if _cte_names(tree) or _recursive(tree):
        return False
    if _outer_joins(tree) or _from_name(tree) is None:
        return False
    if len(_base_tables(tree)) != 1:
        return False
    if _child(tree.args.get("group")) is not None:
        return False
    if _child(tree.args.get("having")) is not None:
        return False
    if _child(tree.args.get("limit")) is not None:
        return False
    expressions = tree.expressions
    if not expressions:
        return False
    return all(
        _item_is_aggregate(expr) and not _bare_column_outside(expr)
        for expr in expressions
    )


def _item_is_aggregate(expr: _Node) -> bool:
    """The projected item is an allowed aggregate call at its top."""
    node = expr.this if type(expr).__name__ == "Alias" else expr
    return type(node).__name__ in _AGGREGATE_CALLS


def _bare_column_outside(expr: _Node) -> bool:
    """True when a column of the item sits outside every aggregate call."""
    for node in expr.walk():
        if type(node).__name__ == "Column" and not _under_aggregate(node):
            return True
    return False


def _under_aggregate(node: _Node) -> bool:
    """True when an aggregate call is between this column and the root."""
    current = node.parent
    while current is not None:
        if type(current).__name__ in _AGGREGATE_CALLS:
            return True
        current = current.parent
    return False


def _depth(tree: _Node, query: QuerySpec) -> None:
    found = _recursive_with(tree)
    if found is None:
        return
    if not query.name.startswith("graph_"):
        raise StoreRefusal("depth unproved")
    cte = _recursive_cte(found)
    parts = _selects(_child(cte.args.get("this")))
    if len(parts) < 2:
        raise StoreRefusal("depth unproved")
    cte_name = _alias(cte)
    if not _zero_depth(parts[0]):
        raise StoreRefusal("depth unproved")
    for branch in parts[1:]:
        if not _plus_one(branch, cte_name) or not _bounded(branch, cte_name):
            raise StoreRefusal("depth unproved")
    raise StoreRefusal("order unproved")


def _hidden(text: str) -> None:
    if _PLACEHOLDER.search(text):
        raise StoreRefusal("forbidden construct")


def _string_end(sql: str, start: int) -> int:
    index = start + 1
    while index < len(sql):
        if sql[index] == "'":
            if index + 1 < len(sql) and sql[index + 1] == "'":
                index += 2
                continue
            return index + 1
        index += 1
    raise StoreRefusal("parse invalid")


def _child(value: object) -> _Node | None:
    """Return a parser node, or none when the slot holds a token or nothing."""
    if isinstance(value, _Node):
        return value
    return None


def _allowed_join(node: _Node) -> bool:
    side = node.args.get("side")
    kind = node.args.get("kind")
    return (side is None and kind == "INNER") or (side == "LEFT" and kind is None)


def _allowed_limit(node: _Node) -> bool:
    return type(node.args.get("expression")).__name__ in {"Literal", "Placeholder"}


def _literal_in(node: _Node) -> bool:
    expressions = node.args.get("expressions")
    if not isinstance(expressions, Sequence) or isinstance(expressions, str):
        return False
    return bool(expressions) and all(
        type(item).__name__ == "Literal" for item in expressions
    )


def _placeholder_any(node: _Node) -> bool:
    inner = node.this
    if type(inner).__name__ == "Paren":
        inner = inner.this
    return type(inner).__name__ == "Placeholder"


def _allowed_cast(node: _Node) -> bool:
    dtype = node.args.get("to")
    token = getattr(dtype, "this", None)
    label = getattr(token, "name", "")
    return label in _CASTS


def _refuse_contract_cte(tree: _Node, query: QuerySpec) -> None:
    """A common-table name that is a contract table is refused before typing."""
    contract = {table.name for table in query.tables}
    if not contract:
        return
    for node in tree.walk():
        if type(node).__name__ == "CTE" and _alias(node) in contract:
            raise StoreRefusal("forbidden construct")


def _table(node: _Node, cte_names: set[str], contract: set[str]) -> None:
    if node.args.get("db") or node.args.get("catalog"):
        raise StoreRefusal("forbidden construct")
    if node.name not in contract and node.name not in cte_names:
        raise StoreRefusal("forbidden construct")


def _sum(node: _Node, query: QuerySpec) -> None:
    for child in node.walk():
        if type(child).__name__ != "Column":
            continue
        resolved = resolve_column_type(child, query, "forbidden construct")
        if approximate_contract_type(resolved):
            raise StoreRefusal("forbidden construct")


def _outer_joins(tree: _Node) -> bool:
    return bool(tree.args.get("joins")) if type(tree).__name__ == "Select" else False


def _recursive(tree: _Node) -> bool:
    return _recursive_with(tree) is not None


def _recursive_with(tree: _Node) -> _Node | None:
    for node in tree.walk():
        if type(node).__name__ == "With" and node.args.get("recursive"):
            return node
    return None


def _recursive_cte(with_node: _Node) -> _Node:
    """The recursive member. A query that reaches here has a select in that member."""
    raw = with_node.args.get("expressions")
    chosen: _Node | None = None
    if isinstance(raw, Sequence) and not isinstance(raw, str):
        for item in raw:
            cte = _child(item)
            if cte is not None and _selects(_child(cte.args.get("this"))):
                chosen = cte
                break
    # A bare body is refused in the walk, so this return is the only path.
    assert chosen is not None
    return chosen


def _selects(node: _Node | None) -> list[_Node]:
    if node is None:
        return []
    if type(node).__name__ == "Union":
        return _selects(_child(node.this)) + _selects(
            _child(node.args.get("expression"))
        )
    if type(node).__name__ == "Select":
        return [node]
    return _selects(_child(node.this))


def _zero_depth(select: _Node) -> bool:
    for expr in select.expressions:
        if _alias(expr) == "depth" and _literal(expr.this, "0"):
            return True
    return False


def _plus_one(select: _Node, cte_name: str) -> bool:
    for expr in select.expressions:
        if _alias(expr) == "depth" and _added(expr.this, cte_name):
            return True
    return False


def _bounded(select: _Node, cte_name: str) -> bool:
    where = _child(select.args.get("where"))
    if where is None:
        return False
    expr = where.this
    if any(type(node).__name__ == "Or" for node in expr.walk()):
        return False
    for node in expr.walk():
        if (
            type(node).__name__ == "LT"
            and _depth_column(node.this, cte_name)
            and _literal(node.expression, "4")
        ):
            return True
    return False


def _added(node: _Node, cte_name: str) -> bool:
    if type(node).__name__ != "Add":
        return False
    left, right = node.this, node.expression
    return (_depth_column(left, cte_name) and _literal(right, "1")) or (
        _depth_column(right, cte_name) and _literal(left, "1")
    )


def _depth_column(node: _Node, cte_name: str) -> bool:
    table = node.args.get("table") if hasattr(node, "args") else None
    return (
        type(node).__name__ == "Column"
        and node.name == "depth"
        and _alias(table) == cte_name
    )


def _literal(node: _Node, expected: str) -> bool:
    return (
        type(node).__name__ == "Literal"
        and not node.args.get("is_string")
        and str(node.this) == expected
    )


def _alias(node: object) -> str:
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


def _column_name(node: _Node) -> str:
    if type(node).__name__ != "Column" or not isinstance(node.name, str):
        raise StoreRefusal("order unproved")
    return node.name


def _cte_names(tree: _Node) -> set[str]:
    names: set[str] = set()
    for node in tree.walk():
        if type(node).__name__ == "CTE":
            names.add(_alias(node))
    return names


def _outer_is_cte(tree: _Node) -> bool:
    """The outer read is one common-table expression and nothing joined to it."""
    if type(tree).__name__ != "Select" or tree.args.get("joins"):
        return False
    name = _from_name(tree)
    return name is not None and name in _cte_names(tree)


def _unrenamed_cte_key(tree: _Node, query: QuerySpec, names: tuple[str, ...]) -> bool:
    """Ordered columns trace to one table's key through projections that do not rename."""
    ctes = {_alias(node): node for node in tree.walk() if type(node).__name__ == "CTE"}
    outer = _from_name(tree)
    if outer is None:
        return False
    traced: list[tuple[str, str]] = []
    for name in names:
        found = _trace_unrenamed(ctes, outer, name)
        if found is None:
            return False
        traced.append(found)
    tables = {table for table, _column in traced}
    if len(tables) != 1:
        return False
    key = _key(query, tables.pop())
    traced_names = {column for _table, column in traced}
    return bool(key) and set(key).issubset(traced_names)


def _trace_unrenamed(
    ctes: Mapping[str, _Node], cte_name: str, output_name: str
) -> tuple[str, str] | None:
    cte = ctes.get(cte_name)
    if cte is None:
        return None
    select = cte.this if type(cte.this).__name__ == "Select" else None
    if select is None or select.args.get("joins"):
        return None
    projection = None
    for expr in select.expressions:
        if _alias(expr) == output_name:
            projection = expr
            break
    if projection is None:
        return None
    column = projection.this if type(projection).__name__ == "Alias" else projection
    if type(column).__name__ != "Column" or column.name != output_name:
        return None
    source = _from_name(select)
    if source is None:
        return None
    if source in ctes:
        return _trace_unrenamed(ctes, source, column.name)
    return (source, column.name)


def _from_name(select: _Node) -> str | None:
    source = select.args.get("from_")
    if not isinstance(source, _Node):
        source = select.args.get("from")
    if not isinstance(source, _Node):
        return None
    table = source.this if type(source.this).__name__ == "Table" else source
    if type(table).__name__ != "Table" or not isinstance(table.name, str):
        return None
    return table.name


def _base_tables(tree: _Node) -> list[str]:
    skipped = _cte_names(tree)
    found: list[str] = []
    for node in tree.walk():
        if type(node).__name__ == "Table" and node.name not in skipped:
            found.append(node.name)
    return found


def _key(query: QuerySpec, table_name: str) -> tuple[str, ...]:
    for table in query.tables:
        if table.name == table_name:
            return table.key
    return ()


def _nulls_explicit(sql: str, count: int) -> bool:
    masked = _mask(sql)
    matched = _ORDER.search(masked)
    if matched is None:
        return False
    body = _LIMIT.sub("", matched.group("body"))
    items = [item.strip() for item in body.split(",") if item.strip()]
    if len(items) != count:
        return False
    return all(_DIRECTION.search(item) and _NULLS.search(item) for item in items)


def _mask(sql: str) -> str:
    chars = list(sql)
    index = 0
    while index < len(chars):
        if chars[index] == "-" and index + 1 < len(chars) and chars[index + 1] == "-":
            end = index
            while end < len(chars) and chars[end] != "\n":
                chars[end] = " "
                end += 1
            index = end
            continue
        if chars[index] == "/" and index + 1 < len(chars) and chars[index + 1] == "*":
            end = index
            while end + 1 < len(chars) and not (
                chars[end] == "*" and chars[end + 1] == "/"
            ):
                chars[end] = " "
                end += 1
            index = min(end + 2, len(chars))
            continue
        if chars[index] == "'":
            chars[index] = " "
            index += 1
            while index < len(chars):
                if (
                    chars[index] == "'"
                    and index + 1 < len(chars)
                    and chars[index + 1] == "'"
                ):
                    chars[index] = " "
                    chars[index + 1] = " "
                    index += 2
                    continue
                mark = chars[index]
                chars[index] = " "
                index += 1
                if mark == "'":
                    break
            continue
        index += 1
    return "".join(chars)


def _integer_or_text(node: _Node) -> bool:
    """A numeric literal is an integer. Text literals stay text."""
    if node.args.get("is_string"):
        return True
    return _INTEGER_LITERAL.fullmatch(str(node.this)) is not None


def _limit_param(node: _Node, query: QuerySpec) -> None:
    """A row-limit placeholder is an integer parameter."""
    expression = node.args.get("expression")
    if not isinstance(expression, _Node) or type(expression).__name__ != "Placeholder":
        return
    name = expression.args.get("this")
    if not isinstance(name, str):
        raise StoreRefusal("forbidden construct")
    types = {item.name: item.type_name for item in query.params}
    if types.get(name) != "bigint":
        raise StoreRefusal("forbidden construct")


def _projection(tree: _Node, query: QuerySpec) -> None:
    """The outermost names, in order, are the header's return names."""
    if type(tree).__name__ != "Select":
        return
    names = tuple(_output_name(expr) for expr in tree.expressions)
    expected = tuple(item.name for item in query.returns)
    if names != expected:
        raise StoreRefusal("forbidden construct")


def _output_name(expr: _Node) -> str:
    if type(expr).__name__ == "Column" and isinstance(expr.name, str) and expr.name:
        return expr.name
    if type(expr).__name__ == "Alias":
        name = _alias(expr)
        if name:
            return name
    raise StoreRefusal("forbidden construct")


def _parameters(query: QuerySpec) -> None:
    """Every placeholder is declared, and every declared parameter is used."""
    used: set[str] = set()
    sql = query.text
    index = 0
    length = len(sql)
    while index < length:
        if sql.startswith("--", index):
            end = sql.find("\n", index)
            index = length if end < 0 else end
            continue
        if sql.startswith("/*", index):
            end = sql.find("*/", index + 2)
            if end < 0:
                raise StoreRefusal("parse invalid")
            index = end + 2
            continue
        if sql[index] == "'":
            index = _string_end(sql, index)
            continue
        if sql[index] == '"':
            index = _quoted_end(sql, index)
            continue
        matched = _PLACEHOLDER.match(sql, index)
        preceded = index > 0 and (sql[index - 1].isalnum() or sql[index - 1] in "_:")
        if matched and not preceded:
            used.add(matched.group(1))
            index = matched.end()
            continue
        index += 1
    declared = {item.name for item in query.params}
    if used != declared:
        raise StoreRefusal("forbidden construct")


def _geometry(tree: _Node, query: QuerySpec) -> None:
    """A geometry column is only a bare item of the outermost projection."""
    geometric = any(
        column.type_name == "geometry"
        for table in query.tables
        for column in table.columns
    )
    if not geometric and all(item.type_name != "geometry" for item in query.returns):
        return
    if type(tree).__name__ != "Select":
        raise StoreRefusal("forbidden construct")
    for node in tree.walk():
        if type(node).__name__ != "Column":
            continue
        if resolve_column_type(node, query, "forbidden construct") != "geometry":
            continue
        if node.args.get("table") is None or node.parent is not tree:
            raise StoreRefusal("forbidden construct")
    for item in query.returns:
        projected = _projected_type(tree, item.name, query)
        if item.type_name == "geometry" and projected != "geometry":
            raise StoreRefusal("forbidden construct")
        if projected == "geometry" and item.type_name != "geometry":
            raise StoreRefusal("forbidden construct")
        if item.type_name != "geometry":
            continue
        bare = any(
            type(expr).__name__ == "Column" and expr.name == item.name
            for expr in tree.expressions
        )
        if not bare:
            raise StoreRefusal("forbidden construct")


def _projected_type(tree: _Node, name: str, query: QuerySpec) -> str:
    """The resolved type of a bare projection with this output name, or empty."""
    for expr in tree.expressions:
        column = expr
        output = expr.name if type(expr).__name__ == "Column" else ""
        if type(expr).__name__ == "Alias":
            output = _alias(expr)
            column = expr.this
        if output != name or type(column).__name__ != "Column":
            continue
        return resolve_column_type(column, query, "forbidden construct")
    return ""


def _cast_words(sql: str) -> None:
    """The cast type is the word after AS in the query text, one of the four."""
    index = 0
    length = len(sql)
    while index < length:
        skipped = _skip_lexical(sql, index)
        if skipped != index:
            index = skipped
            continue
        if _keyword_at(sql, index, "CAST"):
            index = _one_cast(sql, index)
            continue
        index += 1


def _one_cast(sql: str, index: int) -> int:
    cursor = _skip_space(sql, index + 4)
    if cursor >= len(sql) or sql[cursor] != "(":
        raise StoreRefusal("forbidden construct")
    end = _match_paren(sql, cursor)
    inner = sql[cursor + 1 : end]
    _cast_words(inner)
    _require_cast_word(inner)
    return end + 1


def _require_cast_word(inner: str) -> None:
    as_at = _last_as(inner)
    if as_at is None:
        raise StoreRefusal("forbidden construct")
    cursor = _skip_space(inner, as_at + 2)
    if inner.startswith("/*", cursor) or inner.startswith("--", cursor):
        raise StoreRefusal("forbidden construct")
    matched = re.match(r"[A-Za-z_][A-Za-z0-9_]*", inner[cursor:])
    if matched is None or matched.group(0).upper() not in _CAST_WORDS:
        raise StoreRefusal("forbidden construct")
    rest = _skip_space(inner, cursor + matched.end())
    if rest != len(inner):
        raise StoreRefusal("forbidden construct")


def _last_as(inner: str) -> int | None:
    depth = 0
    found: int | None = None
    index = 0
    length = len(inner)
    while index < length:
        skipped = _skip_lexical(inner, index)
        if skipped != index:
            index = skipped
            continue
        if inner[index] == "(":
            depth += 1
        elif inner[index] == ")":
            depth -= 1
        elif depth == 0 and _keyword_at(inner, index, "AS"):
            found = index
            index += 2
            continue
        index += 1
    return found


def _match_paren(sql: str, open_at: int) -> int:
    depth = 0
    index = open_at
    length = len(sql)
    while index < length:
        skipped = _skip_lexical(sql, index)
        if skipped != index:
            index = skipped
            continue
        if sql[index] == "(":
            depth += 1
        elif sql[index] == ")":
            depth -= 1
            if depth == 0:
                return index
        index += 1
    raise StoreRefusal("parse invalid")


def _skip_lexical(sql: str, index: int) -> int:
    """Move past a comment, string or quoted identifier. Otherwise stay."""
    if sql.startswith("--", index):
        end = sql.find("\n", index)
        return len(sql) if end < 0 else end
    if sql.startswith("/*", index):
        end = sql.find("*/", index + 2)
        if end < 0:
            raise StoreRefusal("parse invalid")
        return end + 2
    if index < len(sql) and sql[index] == "'":
        return _string_end(sql, index)
    if index < len(sql) and sql[index] == '"':
        return _quoted_end(sql, index)
    return index


def _skip_space(sql: str, index: int) -> int:
    while index < len(sql) and sql[index] in " \t\r\n":
        index += 1
    return index


def _keyword_at(sql: str, index: int, word: str) -> bool:
    end = index + len(word)
    if sql[index:end].upper() != word:
        return False
    before = index == 0 or not (sql[index - 1].isalnum() or sql[index - 1] == "_")
    after = end >= len(sql) or not (sql[end].isalnum() or sql[end] == "_")
    return before and after
