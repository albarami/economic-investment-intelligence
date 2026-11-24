"""Named query files, their contracts, and bound parameters."""

from __future__ import annotations

import hashlib
import re
import threading
import tomllib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from importlib.resources import files
from pathlib import Path
from typing import final

from eii_product.store.normalise import hold_geometry, is_geometry_text, normalise
from eii_product.store.protocol import (
    EngineName,
    NormalValue,
    Param,
    QueryResult,
    StoreRefusal,
)

HEADER_KEYS = ("name", "params", "returns", "order")
NAME_RE = re.compile(r"[a-z_][a-z0-9_]*\Z")
_LOGICAL_TYPES = frozenset(
    {"string", "int", "bool", "date", "month", "timestamp", "cell", "geometry"}
)
_DECIMAL_TYPE = re.compile(r"decimal\([1-9][0-9]*,[0-9]+\)\Z")
_APPROXIMATE_TYPES = frozenset(
    {
        "double",
        "double precision",
        "float",
        "float4",
        "float8",
        "float32",
        "float64",
        "real",
    }
)
_LOADER_OPEN = False
PARAM_TYPES = frozenset(
    {"bigint", "text", "bool", "date", "list[bigint]", "list[text]"}
)
RETURN_TYPES = frozenset({"text", "bigint", "numeric", "date", "geometry"})
_BARE_COLUMN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\.[A-Za-z_][A-Za-z0-9_]*\Z")
_PLACEHOLDER = re.compile(r":([a-z_][a-z0-9_]*)(?!\w)")
_HEADER_LINE = re.compile(r"-- (?:name|params|returns|order):")


@dataclass(frozen=True)
class ParamSpec:
    """One header parameter and its logical type."""

    name: str
    type_name: str


@dataclass(frozen=True)
class ReturnSpec:
    """One result column declared by the header."""

    name: str
    type_name: str


@dataclass(frozen=True)
class ContractColumn:
    """A column of a table the query reads. The contract holds no SQL."""

    name: str
    type_name: str
    nullable: bool


@dataclass(frozen=True)
class ContractTable:
    """One table the query reads, with its key and the anchor of its definition."""

    name: str
    anchor: str
    key: tuple[str, ...]
    columns: tuple[ContractColumn, ...]


@dataclass(frozen=True)
class QuerySpec:
    """One named query: header, body, digest and contract."""

    name: str
    params: tuple[ParamSpec, ...]
    returns: tuple[ReturnSpec, ...]
    order: tuple[str, ...]
    text: str
    sha256: str
    tables: tuple[ContractTable, ...]


@final
@dataclass(frozen=True)
class QueryName:
    """One name of one inventory. Only the loader constructs it."""

    name: str
    token: object

    def __post_init__(self) -> None:
        """Refuse construction from anywhere but the loader."""
        if not _LOADER_OPEN:
            raise StoreRefusal("unknown query")


@dataclass(frozen=True)
class Inventory:
    """A folder of queries and the names only its loader minted."""

    queries: tuple[QuerySpec, ...]
    token: object
    names: tuple[QueryName, ...]

    def get(self, name: str) -> QuerySpec | None:
        """Return the query with this name, if the folder declared it."""
        for query in self.queries:
            if query.name == name:
                return query
        return None

    def lookup(self, name: str) -> QueryName:
        """Return the name this inventory minted, or refuse an unknown one."""
        for item in self.names:
            if item.name == name:
                return item
        raise StoreRefusal("unknown query")


def packaged_sql_dir() -> Path:
    """Return the packaged query folder, or refuse when the package marker is gone."""
    try:
        anchor = files("eii_product.store.sql").joinpath("__init__.py")
    except ModuleNotFoundError:
        raise StoreRefusal("query resources missing") from None
    return Path(str(anchor)).resolve().parent


def load_inventory(folder: Path) -> Inventory:
    """Read a query folder. An absent folder is not an empty success."""
    if not folder.is_dir() or not (folder / "__init__.py").is_file():
        raise StoreRefusal("query resources missing")
    specs: list[QuerySpec] = []
    for path in sorted(folder.glob("*.sql")):
        contract_path = path.with_suffix(".toml")
        if not contract_path.is_file():
            raise StoreRefusal("query header invalid")
        text = path.read_text(encoding="utf-8")
        name, params, returns, order, body = _header(text, path.stem)
        spec = QuerySpec(
            name,
            params,
            returns,
            order,
            body,
            hashlib.sha256(path.read_bytes()).hexdigest(),
            _contract(contract_path),
        )
        _refuse_contract_cte(spec)
        _tie_geometry(spec)
        specs.append(spec)
    seen = tuple(spec.name for spec in specs)
    if len(seen) != len(set(seen)):
        raise StoreRefusal("query header invalid")
    return _inventory(tuple(specs))


def _inventory(specs: tuple[QuerySpec, ...]) -> Inventory:
    """Mint names while the loader guard is open, then close it."""
    global _LOADER_OPEN
    token = object()
    _LOADER_OPEN = True
    try:
        names = tuple(QueryName(spec.name, token) for spec in specs)
    finally:
        _LOADER_OPEN = False
    return Inventory(specs, token, names)


def require_query(inventory: Inventory, query: object) -> QuerySpec:
    """Accept only a name this inventory's loader minted."""
    if not isinstance(query, QueryName) or query.token is not inventory.token:
        raise StoreRefusal("unknown query")
    found = inventory.get(query.name)
    if found is None:
        raise StoreRefusal("unknown query")
    return found


def translate(sql: str, engine: EngineName) -> str:
    """Rewrite whole-token placeholders. Literals and comments are not rewritten."""
    if engine not in ("postgres", "embedded"):
        raise StoreRefusal("unknown engine")
    _refuse_dollar_quotes(sql)
    pieces: list[str] = []
    index = 0
    length = len(sql)
    while index < length:
        if sql.startswith("--", index):
            end = sql.find("\n", index)
            end = length if end < 0 else end
            _refuse_hidden_placeholder(sql[index:end])
            pieces.append(sql[index:end])
            index = end
            continue
        if sql.startswith("/*", index):
            end = sql.find("*/", index + 2)
            if end < 0:
                raise StoreRefusal("parse invalid")
            end += 2
            _refuse_hidden_placeholder(sql[index:end])
            pieces.append(sql[index:end])
            index = end
            continue
        if sql[index] == "'":
            end = _string_end(sql, index)
            _refuse_hidden_placeholder(sql[index:end])
            pieces.append(sql[index:end])
            index = end
            continue
        if sql[index] == '"':
            end = _quoted_end(sql, index)
            pieces.append(sql[index:end])
            index = end
            continue
        if sql.startswith("::", index):
            pieces.append("::")
            index += 2
            continue
        matched = _PLACEHOLDER.match(sql, index)
        preceded = index > 0 and (sql[index - 1].isalnum() or sql[index - 1] in "_:")
        if matched and not preceded:
            name = matched.group(1)
            if engine == "postgres":
                pieces.append(f"%({name})s")
            else:
                pieces.append(f"${name}")
            index = matched.end()
            continue
        pieces.append(sql[index])
        index += 1
    return "".join(pieces)


def bind(
    spec: QuerySpec,
    params: Mapping[str, object],
    engine: EngineName,
    *,
    postgis_schema: str | None = None,
) -> tuple[str, dict[str, object]]:
    """Check names and exact types, copy lists, and bind values. Never format them."""
    expected = {item.name for item in spec.params}
    if set(params) != expected:
        raise StoreRefusal("parameter names invalid")
    bound: dict[str, object] = {}
    for item in spec.params:
        bound[item.name] = _bind_value(item.type_name, params[item.name])
    if "%" in spec.text:
        raise StoreRefusal("forbidden construct")
    wrapped = _wrap_geometry(translate(spec.text, engine), spec, engine, postgis_schema)
    return wrapped, bound


def sample_params(spec: QuerySpec) -> dict[str, Param]:
    """One typed sample per header parameter, for EXPLAIN only."""
    bound: dict[str, Param] = {}
    for item in spec.params:
        bound[item.name] = _sample(item.type_name)
    return bound


def _sample(type_name: str) -> Param:
    """A fresh sample. Lists are new objects so a caller cannot alias them."""
    if type_name == "bigint":
        return 0
    if type_name == "text":
        return "SYN-sample"
    if type_name == "bool":
        return True
    if type_name == "date":
        return date(2000, 1, 1)
    if type_name == "list[bigint]":
        return [0]
    if type_name == "list[text]":
        return ["SYN-sample"]
    raise StoreRefusal("parameter types invalid")


def checked_result(
    spec: QuerySpec, columns: Sequence[str], raw_rows: Sequence[Sequence[object]]
) -> QueryResult:
    """Normalise a driver result and refuse a shape the header did not declare."""
    expected = tuple(item.name for item in spec.returns)
    found = tuple(columns)
    if found != expected:
        raise StoreRefusal("result columns invalid")
    width = len(expected)
    rows: list[tuple[NormalValue, ...]] = []
    for raw in raw_rows:
        if len(raw) != width:
            raise StoreRefusal("result width invalid")
        values = tuple(
            hold_geometry(value) if column.type_name == "geometry" else normalise(value)
            for value, column in zip(raw, spec.returns, strict=True)
        )
        for value, column in zip(values, spec.returns, strict=True):
            if not _fits(value, column.type_name):
                raise StoreRefusal("result types invalid")
        rows.append(values)
    return QueryResult(found, tuple(rows))


def _header(
    text: str, stem: str
) -> tuple[str, tuple[ParamSpec, ...], tuple[ReturnSpec, ...], tuple[str, ...], str]:
    lines = text.splitlines()
    if len(lines) < 5:
        raise StoreRefusal("query header invalid")
    keys: list[str] = []
    values: dict[str, str] = {}
    for line in lines[:4]:
        if not line.startswith("-- ") or ":" not in line[3:]:
            raise StoreRefusal("query header invalid")
        key, raw = line[3:].split(":", 1)
        key = key.strip()
        if key in values:
            raise StoreRefusal("query header invalid")
        keys.append(key)
        values[key] = raw.strip()
    if tuple(keys) != HEADER_KEYS:
        raise StoreRefusal("query header invalid")
    if _HEADER_LINE.match(lines[4]):
        raise StoreRefusal("query header invalid")
    name = values["name"]
    if name != stem or NAME_RE.fullmatch(name) is None:
        raise StoreRefusal("query header invalid")
    params = _params(values["params"])
    returns = _returns(values["returns"])
    order = _order(values["order"], returns)
    body = "\n".join(lines[4:]).strip()
    if not body:
        raise StoreRefusal("query header invalid")
    return name, params, returns, order, body


def _params(raw: str) -> tuple[ParamSpec, ...]:
    if raw == "":
        return ()
    specs: list[ParamSpec] = []
    seen: set[str] = set()
    for part in raw.split(","):
        pieces = part.strip().split()
        if len(pieces) != 2:
            raise StoreRefusal("query header invalid")
        name, type_name = pieces
        if NAME_RE.fullmatch(name) is None or type_name not in PARAM_TYPES:
            raise StoreRefusal("query header invalid")
        if name in seen:
            raise StoreRefusal("query header invalid")
        seen.add(name)
        specs.append(ParamSpec(name, type_name))
    return tuple(specs)


def _returns(raw: str) -> tuple[ReturnSpec, ...]:
    if raw == "":
        raise StoreRefusal("query header invalid")
    specs: list[ReturnSpec] = []
    seen: set[str] = set()
    for part in raw.split(","):
        pieces = part.strip().split()
        if len(pieces) != 2:
            raise StoreRefusal("query header invalid")
        name, type_name = pieces
        if type_name == "bool" or type_name not in RETURN_TYPES:
            raise StoreRefusal("query header invalid")
        if NAME_RE.fullmatch(name) is None or name in seen:
            raise StoreRefusal("query header invalid")
        seen.add(name)
        specs.append(ReturnSpec(name, type_name))
    return tuple(specs)


def _order(raw: str, returns: tuple[ReturnSpec, ...]) -> tuple[str, ...]:
    """Column names, or an empty line for the one-row aggregate form."""
    if raw == "":
        return ()
    names = tuple(part.strip() for part in raw.split(","))
    known = {item.name for item in returns}
    if any(NAME_RE.fullmatch(name) is None or name not in known for name in names):
        raise StoreRefusal("query header invalid")
    if len(names) != len(set(names)):
        raise StoreRefusal("query header invalid")
    return names


def _contract(path: Path) -> tuple[ContractTable, ...]:
    raw = path.read_text(encoding="utf-8")
    if ";" in raw or "select" in raw.lower():
        raise StoreRefusal("query header invalid")
    try:
        data = tomllib.loads(raw)
    except tomllib.TOMLDecodeError:
        raise StoreRefusal("query header invalid") from None
    tables = data.get("tables")
    if not isinstance(tables, list) or not tables:
        raise StoreRefusal("query header invalid")
    parsed: list[ContractTable] = []
    for table in tables:
        if not isinstance(table, dict):
            raise StoreRefusal("query header invalid")
        parsed.append(_contract_table(table))
    return tuple(parsed)


def _contract_table(table: dict[str, object]) -> ContractTable:
    name = table.get("name")
    anchor = table.get("anchor")
    key = table.get("key", [])
    columns = table.get("columns")
    if not isinstance(name, str) or NAME_RE.fullmatch(name) is None:
        raise StoreRefusal("query header invalid")
    if not isinstance(anchor, str) or anchor.strip() == "":
        raise StoreRefusal("query header invalid")
    if not isinstance(key, list) or not all(isinstance(item, str) for item in key):
        raise StoreRefusal("query header invalid")
    if not isinstance(columns, list) or not columns:
        raise StoreRefusal("query header invalid")
    parsed_columns: list[ContractColumn] = []
    for column in columns:
        if not isinstance(column, dict):
            raise StoreRefusal("query header invalid")
        column_name = column.get("name")
        type_name = column.get("type")
        nullable = column.get("nullable")
        if (
            not isinstance(column_name, str)
            or NAME_RE.fullmatch(column_name) is None
            or not isinstance(type_name, str)
            or not _logical_type(type_name)
            or type(nullable) is not bool
        ):
            raise StoreRefusal("query header invalid")
        parsed_columns.append(ContractColumn(column_name, type_name, nullable))
    known = {column.name for column in parsed_columns}
    if any(item not in known for item in key):
        raise StoreRefusal("query header invalid")
    return ContractTable(name, anchor, tuple(key), tuple(parsed_columns))


def _bind_value(type_name: str, value: object) -> object:
    if type_name == "bigint" and type(value) is int:
        return value
    if type_name == "text" and type(value) is str:
        return value
    if type_name == "bool" and type(value) is bool:
        return value
    if type_name == "date" and type(value) is date:
        return value
    if type_name == "list[bigint]" and type(value) is list:
        if all(type(item) is int for item in value):
            return list(value)
    if type_name == "list[text]" and type(value) is list:
        if all(type(item) is str for item in value):
            return list(value)
    raise StoreRefusal("parameter types invalid")


def _fits(value: NormalValue, type_name: str) -> bool:
    if value is None:
        return True
    if type_name == "text":
        return type(value) is str
    if type_name == "bigint":
        return type(value) is int
    if type_name == "numeric":
        return type(value) is int or type(value) is Decimal
    if type_name == "date":
        return type(value) is date
    if type_name == "geometry":
        return is_geometry_text(value)
    return False


def _refuse_contract_cte(spec: QuerySpec) -> None:
    """A common-table name that is a contract table is refused before typing."""
    import sqlglot
    from sqlglot.errors import SqlglotError

    try:
        tree = sqlglot.parse_one(spec.text, read="postgres")
    except SqlglotError:
        return
    from eii_product.store.resolve import _refuse_non_lower_name

    _refuse_non_lower_name(tree, "query header invalid")
    contract = {table.name for table in spec.tables}
    if not contract:
        return
    for node in tree.walk():
        if type(node).__name__ != "CTE":
            continue
        alias = getattr(node, "alias", None)
        if isinstance(alias, str) and alias in contract:
            raise StoreRefusal("query header invalid")


def _tie_geometry(spec: QuerySpec) -> None:
    """A geometry return names the column reached through its table alias."""
    if not _mentions_geometry(spec):
        return
    projected = _projected_types(spec)
    for item in spec.returns:
        found = projected.get(item.name)
        if item.type_name == "geometry" and found != "geometry":
            raise StoreRefusal("query header invalid")
        if found == "geometry" and item.type_name != "geometry":
            raise StoreRefusal("query header invalid")


def _mentions_geometry(spec: QuerySpec) -> bool:
    if any(item.type_name == "geometry" for item in spec.returns):
        return True
    return any(
        column.type_name == "geometry"
        for table in spec.tables
        for column in table.columns
    )


def _projected_types(spec: QuerySpec) -> dict[str, str]:
    """Map each bare projected name to the type resolved in its own SELECT."""
    import sqlglot
    from sqlglot.errors import SqlglotError

    from eii_product.store.resolve import resolve_column_type

    try:
        tree = sqlglot.parse_one(spec.text, read="postgres")
    except SqlglotError:
        raise StoreRefusal("query header invalid") from None
    if type(tree).__name__ != "Select":
        raise StoreRefusal("query header invalid")
    found: dict[str, str] = {}
    for expr in tree.expressions:
        output, column = _bare_projected(expr)
        if output is None or column is None:
            continue
        found[output] = resolve_column_type(column, spec, "query header invalid")
    return found


def _bare_projected(expr: object) -> tuple[str | None, object | None]:
    """Return the output name and column node of a bare projection."""
    node = expr
    output: str | None = None
    if type(expr).__name__ == "Alias":
        alias = getattr(expr, "alias", None)
        output = alias if isinstance(alias, str) and alias else None
        node = getattr(expr, "this", None)
    if type(node).__name__ != "Column":
        return None, None
    name = getattr(node, "name", None)
    column = name if isinstance(name, str) and name else None
    if output is None:
        output = column
    return output, node


def _contract_column_type(
    query: QuerySpec, table_name: str | None, column_name: str, reason: str
) -> str:
    """The type of one column of one contract table. Any other shape is refused."""
    if table_name is None or column_name == "":
        raise StoreRefusal(reason)
    matches = [table for table in query.tables if table.name == table_name]
    if len(matches) != 1:
        raise StoreRefusal(reason)
    columns = [column for column in matches[0].columns if column.name == column_name]
    if len(columns) != 1:
        raise StoreRefusal(reason)
    return columns[0].type_name


def _wrap_geometry(
    sql: str, spec: QuerySpec, engine: EngineName, postgis_schema: str | None
) -> str:
    """Wrap bare geometry items in place. A query without one is unchanged."""
    if all(item.type_name != "geometry" for item in spec.returns):
        return sql
    list_start, list_end = _outer_select_list(sql)
    body = sql[list_start:list_end]
    spans = _split_commas(body)
    if len(spans) != len(spec.returns):
        raise StoreRefusal("result columns invalid")
    pieces: list[str] = []
    previous = 0
    for (start, end), column in zip(spans, spec.returns, strict=True):
        pieces.append(body[previous:start])
        item = body[start:end]
        if column.type_name == "geometry":
            stripped = item.strip()
            if _BARE_COLUMN.fullmatch(stripped) is None or not stripped.endswith(
                "." + column.name
            ):
                raise StoreRefusal("forbidden construct")
            pad = item.index(stripped)
            pieces.append(
                item[:pad]
                + _geometry_sql(engine, stripped, column.name, postgis_schema)
                + item[pad + len(stripped) :]
            )
        else:
            pieces.append(item)
        previous = end
    pieces.append(body[previous:])
    return sql[:list_start] + "".join(pieces) + sql[list_end:]


def _geometry_sql(
    engine: EngineName, reference: str, name: str, postgis_schema: str | None
) -> str:
    if engine == "embedded":
        return f"hex(ST_AsWKB({reference})) AS {name}"
    if engine == "postgres":
        if postgis_schema is None:
            raise StoreRefusal("extension schema invalid")
        return (
            f"upper(encode({postgis_schema}.ST_AsBinary({reference}, 'NDR'), 'hex'))"
            f" AS {name}"
        )
    raise StoreRefusal("unknown engine")


def _outer_select_list(sql: str) -> tuple[int, int]:
    words = _depth0_keywords(sql)
    selects = [index for word, index in words if word == "SELECT"]
    if len(selects) != 1:
        raise StoreRefusal("forbidden construct")
    froms = [index for word, index in words if word == "FROM" and index > selects[0]]
    if not froms:
        raise StoreRefusal("forbidden construct")
    return selects[0] + len("SELECT"), froms[0]


def _depth0_keywords(sql: str) -> list[tuple[str, int]]:
    found: list[tuple[str, int]] = []
    depth = 0
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
        if sql[index] == "(":
            depth += 1
            index += 1
            continue
        if sql[index] == ")":
            depth -= 1
            index += 1
            continue
        if depth == 0:
            for word in ("SELECT", "FROM"):
                if _keyword_at(sql, index, word):
                    found.append((word, index))
                    index += len(word)
                    break
            else:
                index += 1
            continue
        index += 1
    return found


def _split_commas(text: str) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    start = 0
    depth = 0
    index = 0
    length = len(text)
    while index < length:
        if text.startswith("--", index):
            end = text.find("\n", index)
            index = length if end < 0 else end
            continue
        if text.startswith("/*", index):
            end = text.find("*/", index + 2)
            if end < 0:
                raise StoreRefusal("parse invalid")
            index = end + 2
            continue
        if text[index] == "'":
            index = _string_end(text, index)
            continue
        if text[index] == '"':
            index = _quoted_end(text, index)
            continue
        if text[index] == "(":
            depth += 1
        elif text[index] == ")":
            depth -= 1
        elif text[index] == "," and depth == 0:
            spans.append((start, index))
            start = index + 1
        index += 1
    spans.append((start, length))
    return spans


def _keyword_at(sql: str, index: int, word: str) -> bool:
    end = index + len(word)
    if sql[index:end].upper() != word:
        return False
    before = index == 0 or not (sql[index - 1].isalnum() or sql[index - 1] == "_")
    after = end >= len(sql) or not (sql[end].isalnum() or sql[end] == "_")
    return before and after


def _logical_type(type_name: str) -> bool:
    """A contract type is one of document 03 section 1.2, including decimal(p,s)."""
    return type_name in _LOGICAL_TYPES or _DECIMAL_TYPE.fullmatch(type_name) is not None


def approximate_contract_type(type_name: str) -> bool:
    """An approximate spelling. None of them is in the logical-type vocabulary."""
    return type_name.strip().lower() in _APPROXIMATE_TYPES


def _refuse_dollar_quotes(sql: str) -> None:
    """A dollar-quoted literal is refused before any placeholder is rewritten."""
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
        if _dollar_open(sql, index):
            raise StoreRefusal("forbidden construct")
        index += 1


def _dollar_open(sql: str, index: int) -> bool:
    """True when index starts a plain or tagged dollar quote."""
    if index >= len(sql) or sql[index] != "$":
        return False
    if sql.startswith("$$", index):
        return True
    cursor = index + 1
    if cursor >= len(sql) or not (sql[cursor].isalpha() or sql[cursor] == "_"):
        return False
    cursor += 1
    while cursor < len(sql) and (sql[cursor].isalnum() or sql[cursor] == "_"):
        cursor += 1
    return cursor < len(sql) and sql[cursor] == "$"


def _refuse_hidden_placeholder(text: str) -> None:
    if _PLACEHOLDER.search(text):
        raise StoreRefusal("forbidden construct")


def _quoted_end(sql: str, start: int) -> int:
    """End of a double-quoted identifier. A doubled quote is an escape."""
    index = start + 1
    while index < len(sql):
        if sql[index] == '"':
            if index + 1 < len(sql) and sql[index + 1] == '"':
                index += 2
                continue
            return index + 1
        index += 1
    raise StoreRefusal("parse invalid")


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


PACKAGED: Inventory
_PACKAGED_LOCK = threading.Lock()


def __getattr__(name: str) -> Inventory:
    """Validate and cache the packaged inventory only when first requested.

    One lock makes concurrent first accesses build it once and share it.
    """
    if name != "PACKAGED":
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    with _PACKAGED_LOCK:
        cached = globals().get("PACKAGED")
        if isinstance(cached, Inventory):
            return cached
        inventory = load_inventory(packaged_sql_dir())
        globals()["PACKAGED"] = inventory
        return inventory
