"""Public source chain shared by the release writer and the loader.

A manifest source is complete when it carries the contract names for the
citation: publisher, title (dataset or page), url, licence or licence_basis,
retrieved_on and sha256. Those fields must equal the source_registry row.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime

from eii_core.manifest import by_name

_REASONS = frozenset(
    {
        "source_link_incomplete",
        "source_link_mismatch",
        "source_link_missing",
        "source_link_unknown",
    }
)
SOURCE_KEYS = (
    "licence",
    "licence_basis",
    "publisher",
    "retrieved_on",
    "sha256",
    "source_id",
    "title",
    "url",
)
_REQUIRED = frozenset(SOURCE_KEYS)
_DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}\Z")
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_METHOD = re.compile(r"[A-Za-z_][A-Za-z0-9_.]*@[A-Za-z0-9][A-Za-z0-9._-]*\Z")
_LINEAGE = "fact_lineage"
_REGISTRY = "source_registry"


class SourceChainRefusal(Exception):
    """A fixed source-chain reason. Nothing has been written or connected."""

    def __init__(self, reason: str) -> None:
        """Refuse a reason outside the chain's closed list."""
        if reason not in _REASONS:
            message = "refusal reason invalid"
            raise ValueError(message)
        self.reason = reason
        super().__init__(reason)


@dataclass(frozen=True)
class ChainTable:
    """One release table and the rows the chain reads."""

    name: str
    rows: tuple[Mapping[str, object], ...]


def require_public_chain(
    sources: Sequence[object],
    tables: Sequence[ChainTable],
) -> None:
    """Refuse a public_only release whose source chain is not closed."""
    by_table = {table.name: table for table in tables}
    if _REGISTRY not in by_table or _LINEAGE not in by_table:
        raise SourceChainRefusal("source_link_missing")
    registry = _registry(by_table[_REGISTRY])
    cited = _sources(sources, registry)
    for table in tables:
        catalogue = by_name(table.name)
        if catalogue is None or catalogue.manifest_class != "public":
            continue
        _public_rows(table, registry, cited)
    _lineage(by_table[_LINEAGE], by_table, registry)


def _registry(table: ChainTable) -> dict[str, dict[str, str]]:
    found: dict[str, dict[str, str]] = {}
    for row in table.rows:
        # A Public-shaped citation cannot disguise an explicitly generated
        # producer (DAT-107). Do not infer origin from publisher prose or ids.
        if row.get("kind") in ("synthetic_feed", "simulation_output") or row.get(
            "origin"
        ) in ("synthetic", "simulated"):
            raise SourceChainRefusal("source_link_mismatch")
        parsed = _record(row, closed=False)
        if parsed is None:
            raise SourceChainRefusal("source_link_incomplete")
        source_id = parsed["source_id"]
        if source_id in found:
            raise SourceChainRefusal("source_link_mismatch")
        found[source_id] = parsed
    return found


def _sources(
    sources: Sequence[object],
    registry: Mapping[str, Mapping[str, str]],
) -> set[str]:
    cited: set[str] = set()
    for source in sources:
        if type(source) is not dict:
            raise SourceChainRefusal("source_link_incomplete")
        held: dict[str, object] = {}
        for key, value in source.items():
            if type(key) is not str:
                raise SourceChainRefusal("source_link_incomplete")
            held[key] = value
        parsed = _record(held, closed=True)
        if parsed is None:
            raise SourceChainRefusal("source_link_incomplete")
        source_id = parsed["source_id"]
        if source_id in cited:
            raise SourceChainRefusal("source_link_mismatch")
        row = registry.get(source_id)
        if row is None:
            raise SourceChainRefusal("source_link_unknown")
        if row != parsed:
            raise SourceChainRefusal("source_link_mismatch")
        cited.add(source_id)
    return cited


def _public_rows(
    table: ChainTable,
    registry: Mapping[str, Mapping[str, str]],
    cited: set[str],
) -> None:
    for row in table.rows:
        if "source_id" not in row:
            raise SourceChainRefusal("source_link_missing")
        source_id = row["source_id"]
        if type(source_id) is not str or source_id not in registry:
            raise SourceChainRefusal("source_link_unknown")
        if source_id not in cited:
            raise SourceChainRefusal("source_link_missing")


def _lineage(
    table: ChainTable,
    by_table: Mapping[str, ChainTable],
    registry: Mapping[str, Mapping[str, str]],
) -> None:
    covered: set[str] = set()
    for row in table.rows:
        if row.get("input_class") in ("synthetic", "simulated"):
            raise SourceChainRefusal("source_link_mismatch")
        name = row.get("table_name")
        transform = row.get("transform")
        source_id = row.get("source_id")
        if type(name) is not str:
            continue
        catalogue = by_name(name)
        if catalogue is None or catalogue.manifest_class != "public":
            continue
        if type(transform) is not str or _METHOD.fullmatch(transform) is None:
            raise SourceChainRefusal("source_link_incomplete")
        if type(source_id) is not str or source_id not in registry:
            raise SourceChainRefusal("source_link_unknown")
        covered.add(name)
    for name, held in by_table.items():
        catalogue = by_name(name)
        if catalogue is None or catalogue.manifest_class != "public":
            continue
        if held.name not in covered:
            raise SourceChainRefusal("source_link_missing")


def _record(row: Mapping[str, object], *, closed: bool) -> dict[str, str] | None:
    keys = set(row)
    if closed and keys != _REQUIRED:
        return None
    if not closed and not _REQUIRED <= keys:
        return None
    parsed: dict[str, str] = {}
    for key in SOURCE_KEYS:
        text = _text(row[key])
        if text is None:
            return None
        parsed[key] = text
    if parsed["licence"] == "" and parsed["licence_basis"] == "":
        return None
    if parsed["publisher"] == "" or parsed["title"] == "" or parsed["url"] == "":
        return None
    if parsed["source_id"] == "":
        return None
    if _DATE.fullmatch(parsed["retrieved_on"]) is None:
        return None
    if _SHA.fullmatch(parsed["sha256"]) is None:
        return None
    return parsed


def _text(value: object) -> str | None:
    if type(value) is str:
        return value
    if type(value) is date:
        return value.isoformat()
    if type(value) is datetime:
        return value.date().isoformat()
    return None
