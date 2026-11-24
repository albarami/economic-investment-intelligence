"""Draft the release spec from stored phase records and receipts (lead shell).

The draft carries the tables with their owning phase, their columns and the
receipt and body references with hashes computed by the producer's own
helpers, so no hash is typed by hand. It writes no scalar except
``release_contract_version`` and never writes the approval: the lead fills the
scalars, reviews the draft and renames it to ``review/release_spec.json``.
Its ``artefacts`` are the ``assembly/artefacts.json`` record's entries; a
built heights phase is first placed there through ``place_artefact``
(``heights_artefacts``, S3-T16; decision 0096 item 4).
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from eii_core.manifest import by_name
from eii_custodian.release.heights_artefacts import stage_heights
from eii_custodian.release.producer import (
    PHASES,
    _phase,
    _read,
    _recorded_artefacts,
    _source,
    _write,
)

DRAFT = "review/release_spec.draft.json"
_TYPES = {bool: "bool", int: "int", str: "string"}


def _columns(rows: Any) -> list[dict[str, Any]]:
    """Name every stored column; type it only from unambiguous stored values."""
    if not isinstance(rows, list) or not rows:
        raise ValueError("column_type_unknown")
    names: dict[str, set[type]] = {}
    for row in rows:
        for name, value in row.items():
            names.setdefault(name, set()).add(type(value))
    columns = []
    for name, types in names.items():
        logical = {_TYPES.get(kind) for kind in types - {type(None)}}
        if len(logical) != 1 or None in logical:
            raise ValueError("column_type_unknown")
        nullable = type(None) in types or any(name not in row for row in rows)
        columns.append(dict(name=name, logical_type=logical.pop(), nullable=nullable))
    return columns


def _keys(name: str, data: dict[str, Any]) -> list[str]:
    if name in data.get("table_sources", {}):
        return sorted(data["table_sources"][name])
    if "source_tables" in data:
        return sorted(k for k, names in data["source_tables"].items() if name in names)
    return sorted(data.get("source_chain", {}))


def _sources(
    cache: Path, listing: Mapping[str, Any], chain: dict[str, Any]
) -> dict[str, Any]:
    sources = {}
    for key, paths in sorted(listing.items()):
        if not isinstance(paths, dict) or set(paths) != {"format", "receipt", "body"}:
            raise ValueError("producer_schema_refused")
        if key not in chain:
            raise ValueError("producer_chain_incomplete")
        files: dict[str, str] = {}
        _read(cache, paths["receipt"], files)
        body = dict(path=paths["body"], sha256=chain[key].get("sha256"))
        ref = dict(
            format=paths["format"],
            receipt=dict(path=paths["receipt"], sha256=files[paths["receipt"]]),
            body=body,
        )
        # The producer's own source check binds both files, so a body that
        # differs from the phase record's hash fails here.
        _source(cache, key, ref, files)
        sources[key] = ref
    return sources


def draft(cache: Path, listing: Mapping[str, Any]) -> dict[str, Any]:
    """Write ``review/release_spec.draft.json``; refuse to replace an existing one.

    ``listing`` maps each source key to its receipt format and the cache paths
    of its receipt and body, with no hash: hashes come from the files and the
    phase records only.
    """
    try:
        document = _document(cache, listing)
    except (KeyError, TypeError, AttributeError):
        raise ValueError("producer_schema_refused") from None
    # Only pinned publication decides whether the draft already exists;
    # it never replaces an existing leaf.
    _write(cache, DRAFT, document, exists="spec_draft_exists")
    return document


def _document(cache: Path, listing: Mapping[str, Any]) -> dict[str, Any]:
    files: dict[str, str] = {}
    tables: dict[str, dict[str, Any]] = {}
    chain: dict[str, Any] = {}
    for phase in PHASES:
        data = _phase(cache, phase, files)
        if data is None:
            continue
        chain.update(data.get("source_chain", {}))
        for name, rows in data["tables"].items():
            if by_name(name) is None:
                raise ValueError("unknown_table")
            # A later phase that extends a table (the GIS gazetteer) owns it.
            tables[name] = dict(
                name=name,
                phase=phase,
                columns=_columns(rows),
                source_keys=_keys(name, data),
            )
    if not tables:
        raise ValueError("producer_chain_incomplete")
    sources = _sources(cache, listing, chain)
    if any(
        key not in sources for table in tables.values() for key in table["source_keys"]
    ):
        raise ValueError("producer_chain_incomplete")
    # Only after the draft's own checks: the recorded heights asset is placed
    # by the single artefact writer, then the record is read again (S3-T16).
    stage_heights(cache)
    placed = _phase(cache, "artefacts", {})
    return dict(
        version=1,
        scalars=dict(release_contract_version="release.v1"),
        sources=sources,
        tables=list(tables.values()),
        artefacts=[
            dict(path=path, sha256=digest)
            for path, digest in _recorded_artefacts(
                {} if placed is None else {"artefacts": placed}
            ).items()
        ],
    )


__all__ = ["DRAFT", "draft"]
