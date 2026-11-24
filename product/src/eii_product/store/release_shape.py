"""Closed manifest shape, canonical table paths and the public source chain."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Protocol

from eii_core.manifest import (
    FORBIDDEN_PUBLIC_ONLY,
    MANIFEST_CLASSES,
    CatalogueTable,
    ColumnSpec,
    by_name,
    engine_versions_reason,
    written_by_privacy,
)
from eii_core.source_chain import (
    SOURCE_KEYS,
    ChainTable,
    SourceChainRefusal,
    require_public_chain,
)
from eii_product.store.release_check import ReleaseRefusal


class _Fetched(Protocol):
    def fetchall(self) -> Sequence[tuple[object, ...]]: ...


class _Connection(Protocol):
    def execute(self, query: str) -> _Fetched: ...


_MANIFEST_KEYS = frozenset(
    {
        "artefacts",
        "build_id",
        "built_at",
        "code_version",
        "engine_versions",
        "release_contract_version",
        "release_id",
        "release_kind",
        "rules_version_id",
        "sources",
        "tables",
    }
)
_STRING_KEYS = frozenset(
    {
        "build_id",
        "built_at",
        "code_version",
        "release_contract_version",
        "release_id",
        "release_kind",
        "rules_version_id",
    }
)
_TABLE_KEYS = frozenset(
    {
        "file",
        "grain",
        "name",
        "provenance_class",
        "row_count",
        "schema_sha256",
        "sha256",
    }
)
_ARTEFACT_KEYS = frozenset({"path", "sha256"})
_KNOWN_KEYS = _MANIFEST_KEYS | FORBIDDEN_PUBLIC_ONLY


def refuse_document(document: Mapping[str, object]) -> None:
    """Refuse a public_only manifest that is not the closed shape."""
    _refuse_manifest_keys(document)
    for key in _STRING_KEYS:
        if type(document.get(key)) is not str:
            raise ReleaseRefusal("manifest_type_invalid")
    reason = engine_versions_reason(document.get("engine_versions"))
    if reason is not None:
        raise ReleaseRefusal(reason)
    if document.get("release_kind") != "public_only":
        raise ReleaseRefusal("release_kind_unsupported")
    tables = document.get("tables")
    if type(tables) is not list:
        raise ReleaseRefusal("manifest_type_invalid")
    if len(tables) == 0:
        raise ReleaseRefusal("empty_table_list")
    sources = document.get("sources")
    if type(sources) is not list:
        raise ReleaseRefusal("manifest_type_invalid")
    _refuse_artefacts(document.get("artefacts"))
    seen: set[str] = set()
    for entry in tables:
        name = _refuse_table_entry(entry)
        if name in seen:
            raise ReleaseRefusal("duplicate_table")
        seen.add(name)


def table_path(folder: Path, file_name: object, name: str) -> Path:
    """Accept only tables/<name>.parquet inside the release folder."""
    if type(file_name) is not str:
        raise ReleaseRefusal("release_incomplete")
    declared = Path(file_name)
    if declared.is_absolute() or file_name.startswith("/"):
        raise ReleaseRefusal("absolute_path")
    if ".." in declared.parts:
        raise ReleaseRefusal("path_traversal")
    if file_name != f"tables/{name}.parquet":
        raise ReleaseRefusal("release_incomplete")
    candidate = folder / "tables" / f"{name}.parquet"
    try:
        resolved = candidate.resolve()
        root = folder.resolve()
    except OSError:
        raise ReleaseRefusal("release_incomplete") from None
    if not _within(root, resolved):
        raise ReleaseRefusal("path_outside_release")
    if _symlink_on(folder, name):
        raise ReleaseRefusal("symbolic_link")
    if not resolved.is_file():
        raise ReleaseRefusal("release_incomplete")
    return resolved


def require_source_chain(
    folder: Path,
    document: Mapping[str, object],
    schemas: Mapping[str, tuple[ColumnSpec, ...]],
    *,
    connection: _Connection,
) -> None:
    """Refuse a public release whose sources and lineage do not resolve."""
    tables = document.get("tables")
    sources = document.get("sources")
    if type(tables) is not list or type(sources) is not list:
        raise ReleaseRefusal("manifest_type_invalid")
    built: list[ChainTable] = []
    for entry in tables:
        if type(entry) is not dict:
            raise ReleaseRefusal("digest_mismatch")
        name = entry.get("name")
        if type(name) is not str or name not in schemas:
            raise ReleaseRefusal("unknown_table")
        built.append(
            ChainTable(
                name,
                _chain_rows(
                    folder / "tables" / f"{name}.parquet",
                    name,
                    schemas[name],
                    connection,
                ),
            )
        )
    try:
        require_public_chain(sources, tuple(built))
    except SourceChainRefusal as fault:
        raise ReleaseRefusal(fault.reason) from None


def _refuse_manifest_keys(document: Mapping[str, object]) -> None:
    known_lower = {key.lower() for key in _KNOWN_KEYS}
    for key in document:
        if type(key) is not str:
            raise ReleaseRefusal("unknown_manifest_key")
        if key in FORBIDDEN_PUBLIC_ONLY:
            raise ReleaseRefusal("forbidden_manifest_field")
        if key.lower() in known_lower and key not in _MANIFEST_KEYS:
            raise ReleaseRefusal("manifest_key_case")
        if key not in _MANIFEST_KEYS:
            raise ReleaseRefusal("unknown_manifest_key")
    for key in _MANIFEST_KEYS:
        if key not in document:
            raise ReleaseRefusal("manifest_type_invalid")


def _refuse_artefacts(artefacts: object) -> None:
    if type(artefacts) is not list:
        raise ReleaseRefusal("manifest_type_invalid")
    for artefact in artefacts:
        if type(artefact) is not dict:
            raise ReleaseRefusal("manifest_type_invalid")
        _refuse_member_keys(artefact, _ARTEFACT_KEYS)
        path = artefact.get("path")
        digest = artefact.get("sha256")
        if type(path) is not str or type(digest) is not str:
            raise ReleaseRefusal("manifest_type_invalid")
        if Path(path).name == "load_receipt.json":
            raise ReleaseRefusal("receipt_listed_as_artefact")


def require_public_catalogue_class(catalogue: CatalogueTable) -> None:
    """Reject protected/simulated input independently of its writer's policy."""
    if catalogue.manifest_class in {"protected", "simulated"}:
        raise ReleaseRefusal("forbidden_table_class")


def _refuse_table_entry(entry: object) -> str:
    if type(entry) is not dict:
        raise ReleaseRefusal("unknown_table")
    name = entry.get("name")
    if type(name) is not str:
        raise ReleaseRefusal("unknown_table")
    catalogue = by_name(name)
    if catalogue is None:
        raise ReleaseRefusal("unknown_table")
    require_public_catalogue_class(catalogue)
    if written_by_privacy(catalogue):
        raise ReleaseRefusal("privacy_written_table")
    provenance = entry.get("provenance_class")
    if type(provenance) is not str or provenance not in MANIFEST_CLASSES:
        raise ReleaseRefusal("table_class_invalid")
    if provenance != catalogue.manifest_class:
        raise ReleaseRefusal("table_class_invalid")
    _refuse_member_keys(entry, _TABLE_KEYS)
    row_count = entry.get("row_count")
    if (
        type(entry.get("file")) is not str
        or type(entry.get("grain")) is not str
        or type(entry.get("sha256")) is not str
        or type(entry.get("schema_sha256")) is not str
        or type(row_count) is not int
    ):
        raise ReleaseRefusal("manifest_type_invalid")
    return name


def _refuse_member_keys(entry: Mapping[str, object], allowed: frozenset[str]) -> None:
    allowed_lower = {key.lower() for key in allowed}
    for key in entry:
        if key.lower() in allowed_lower and key not in allowed:
            raise ReleaseRefusal("manifest_key_case")
        if key not in allowed:
            raise ReleaseRefusal("unknown_manifest_key")
    for key in allowed:
        if key not in entry:
            raise ReleaseRefusal("manifest_type_invalid")


def _symlink_on(folder: Path, name: str) -> bool:
    cursor = folder
    for part in ("tables", f"{name}.parquet"):
        cursor = cursor / part
        if cursor.is_symlink():
            return True
    return False


def _within(root: Path, resolved: Path) -> bool:
    try:
        resolved.relative_to(root)
    except ValueError:
        return False
    return True


def _chain_rows(
    path: Path,
    name: str,
    columns: tuple[ColumnSpec, ...],
    connection: _Connection,
) -> tuple[dict[str, object], ...]:
    catalogue = by_name(name)
    if name == "source_registry":
        wanted = {*SOURCE_KEYS, "kind", "origin"}
        return _select(
            path,
            tuple(column for column in columns if column.name in wanted),
            connection,
        )
    if name == "fact_lineage":
        wanted = {"source_id", "table_name", "transform", "input_class"}
        return _select(
            path,
            tuple(column for column in columns if column.name in wanted),
            connection,
        )
    if catalogue is not None and catalogue.manifest_class == "public":
        if not any(column.name == "source_id" for column in columns):
            return ({},)
        return _select(
            path,
            tuple(column for column in columns if column.name == "source_id"),
            connection,
        )
    return ()


def _select(
    path: Path, columns: tuple[ColumnSpec, ...], connection: _Connection
) -> tuple[dict[str, object], ...]:
    if len(columns) == 0:
        return ()
    names = ", ".join(f'"{column.name}"' for column in columns)
    fetched = connection.execute(
        f"SELECT {names} FROM read_parquet({_literal(path)})"
    ).fetchall()
    return tuple(
        {column.name: row[index] for index, column in enumerate(columns)}
        for row in fetched
    )


def _literal(path: Path) -> str:
    return "'" + str(path).replace("'", "''") + "'"
