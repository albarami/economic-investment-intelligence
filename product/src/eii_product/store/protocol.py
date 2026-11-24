"""Release-store interface. One refusal type, and its message is a closed reason."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING, Literal, Protocol

if TYPE_CHECKING:
    from eii_product.store.registry import QueryName

type Param = int | str | bool | date | list[int] | list[str]
type NormalValue = int | Decimal | str | date | None
type EngineName = Literal["postgres", "embedded"]

EXACT_REASONS: frozenset[str] = frozenset(
    {
        "STORE_UNAVAILABLE",
        "column mismatch",
        "control schema cleanup failed",
        "control schema exists",
        "database environment missing",
        "depth unproved",
        "distinct engines required",
        "engine operation failed",
        "extension schema invalid",
        "fact precision missing",
        "forbidden construct",
        "non-finite number",
        "order unproved",
        "parameter names invalid",
        "parameter types invalid",
        "parse invalid",
        "query header invalid",
        "query not executed",
        "query not owned",
        "query resources missing",
        "release identity invalid",
        "release identity mismatch",
        "result columns invalid",
        "result description missing",
        "result types invalid",
        "result width invalid",
        "row count mismatch",
        "row width mismatch",
        "tool case missing",
        "unknown engine",
        "unknown query",
        "unsupported scalar",
    }
)
_IDENTITY = re.compile(r"[0-9a-f]{64}\Z")
_FIELD = re.compile(r"field mismatch row=[0-9]+ column=[0-9]+\Z")
_PREPARE = re.compile(
    r"prepare failed query=[a-z_][a-z0-9_]* engine=(?:postgres|embedded)\Z"
)


class StoreRefusal(Exception):
    """A fixed reason. Driver text, values, paths and SQL never enter it."""

    def __init__(self, reason: str) -> None:
        """Refuse any reason outside the closed list and its two patterns."""
        if (
            reason not in EXACT_REASONS
            and _FIELD.fullmatch(reason) is None
            and _PREPARE.fullmatch(reason) is None
        ):
            message = "refusal reason invalid"
            raise ValueError(message)
        super().__init__(reason)


def require_identity(identity: str) -> None:
    """Refuse anything other than a 64-character lowercase release identity."""
    if _IDENTITY.fullmatch(identity) is None:
        raise StoreRefusal("release identity invalid")


def field_mismatch(row: int, column: int) -> StoreRefusal:
    """Build a position-only field mismatch."""
    return StoreRefusal(f"field mismatch row={row} column={column}")


def prepare_failed(query: str, engine: str) -> StoreRefusal:
    """Build a prepare failure that names the query and the engine only."""
    return StoreRefusal(f"prepare failed query={query} engine={engine}")


@dataclass(frozen=True)
class QueryResult:
    """Normalised rows already checked against the query header."""

    columns: tuple[str, ...]
    rows: tuple[tuple[NormalValue, ...], ...]


@dataclass(frozen=True)
class StoreHealth:
    """A store answered. Failure raises STORE_UNAVAILABLE instead of ok=False."""

    ok: Literal[True]


class ReleaseStore(Protocol):
    """The only object a tool receives. No connection, cursor, path or SQL."""

    engine: EngineName
    release_id: str

    def fetch(self, query: QueryName, params: Mapping[str, Param]) -> QueryResult:
        """Run one registered query with bound parameters."""

    def ping(self, timeout_s: float) -> StoreHealth:
        """Require the store to answer. The statement time limit is not built."""

    def close(self) -> None:
        """Close what this store opened."""
