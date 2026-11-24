"""Fixed read-only startup verification, shared by every serving boundary.

No configuration is read here. Drivers are lazy and snapshots are injectable
for engine-free contract tests. Verification never creates or reloads a schema.
"""

from __future__ import annotations

import hashlib
import os
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from eii_product.store import loader
from eii_product.store.postgres import release_schema
from eii_product.store.receipt import read_receipt
from eii_product.store.release_check import (
    CheckedRelease,
    check_release,
    digest_rows,
    manifest_rows,
)

Rows = Mapping[str, Sequence[Mapping[str, object]]]
ROLE_SQL = (
    "SELECT CURRENT_USER, r.rolsuper, r.rolbypassrls FROM pg_catalog.pg_roles AS r "
    "WHERE r.rolname = CURRENT_USER"
)
INVENTORY_SQL = (
    "SELECT c.relname FROM pg_catalog.pg_class AS c JOIN pg_catalog.pg_namespace AS n "
    "ON n.oid = c.relnamespace WHERE n.nspname = %s "
    "AND c.relkind IN ('r','p','v','m','f') ORDER BY c.relname"
)


class StartupRefusal(ValueError):
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


@dataclass(frozen=True)
class Snapshot:
    rows: Rows
    names: frozenset[str]
    interrupted: bool = False
    role: tuple[object, object, object] = ("eii_app", False, False)


def require_manifest_identity(
    snapshot: Snapshot, expected: Sequence[Mapping[str, object]]
) -> None:
    """Check full identity independently of the later data-digest defence."""
    if sorted(
        snapshot.rows["release_manifest"], key=lambda row: str(row["table_name"])
    ) != sorted(expected, key=lambda row: str(row["table_name"])):
        raise StartupRefusal("startup_identity_mismatch")


def require_receipt_inventory(
    receipt: Mapping[str, Any], names: frozenset[str]
) -> None:
    """Check the receipt's closed engine/table inventory before indexed reads."""
    if (
        receipt.get("engines") != ["embedded", "postgres"]
        or set(receipt.get("tables", [])) != names
        or set(receipt.get("digests", {})) != names
        or set(receipt.get("row_counts", {})) != names
    ):
        raise StartupRefusal("startup_parity_failed")


def verify_artefacts(checked: CheckedRelease) -> None:
    allowed = {"manifest.json", "release.duckdb", "load_receipt.json"}
    allowed.update(
        str(item["file"])
        for item in cast(list[dict[str, Any]], checked.document["tables"])
    )
    allowed.update(
        str(item["path"])
        for item in cast(list[dict[str, Any]], checked.document.get("artefacts", []))
    )
    for path in checked.folder.rglob("*"):
        if path.is_symlink() or (
            path.is_file()
            and path.relative_to(checked.folder).as_posix() not in allowed
        ):
            raise StartupRefusal("startup_inventory_mismatch")
    for item in cast(list[dict[str, Any]], checked.document.get("artefacts", [])):
        name = item["path"]
        path = checked.folder / name
        if (
            Path(name).is_absolute()
            or ".." in Path(name).parts
            or path.is_symlink()
            or not path.resolve().is_relative_to(checked.folder.resolve())
        ):
            raise StartupRefusal("startup_artefact_mismatch")
        try:
            with path.open("rb") as stream:
                if hashlib.file_digest(stream, "sha256").hexdigest() != item["sha256"]:
                    raise StartupRefusal("startup_artefact_mismatch")
        except OSError:
            raise StartupRefusal("startup_artefact_mismatch") from None


def verify_snapshots(
    checked: CheckedRelease,
    receipt: Mapping[str, Any],
    embedded: Snapshot,
    postgres: Snapshot | None,
) -> None:
    names = frozenset(checked.schemas) | {"release_manifest"}
    if embedded.interrupted or (postgres is not None and postgres.interrupted):
        raise StartupRefusal("interrupted_load_refused")
    if postgres is not None and (
        postgres.role[0] != "eii_app"
        or postgres.role[1] is not False
        or postgres.role[2] is not False
    ):
        raise StartupRefusal("startup_role_refused")
    expected_manifest = manifest_rows(checked.document)
    for snapshot in (embedded,) if postgres is None else (embedded, postgres):
        if snapshot.names != names or set(snapshot.rows) != names:
            raise StartupRefusal("startup_inventory_mismatch")
        require_manifest_identity(snapshot, expected_manifest)
    require_receipt_inventory(receipt, names)
    for name in names:
        columns = loader._columns(checked, name)
        key = loader._key(name)
        for snapshot in (embedded,) if postgres is None else (embedded, postgres):
            rows = snapshot.rows[name]
            if (
                len(rows) != receipt["row_counts"][name]
                or digest_rows(rows, columns, key) != receipt["digests"][name]
            ):
                raise StartupRefusal("startup_parity_failed")
        # The receipt cannot substitute for the immutable exported table.
        table_entries = cast(list[dict[str, Any]], checked.document["tables"])
        expected = (
            expected_manifest
            if name == "release_manifest"
            else loader._parquet_rows(
                checked.folder
                / next(str(e["file"]) for e in table_entries if e["name"] == name),
                columns,
            )
        )
        if digest_rows(expected, columns, key) != receipt["digests"][name]:
            raise StartupRefusal("startup_parity_failed")


def embedded_snapshot(checked: CheckedRelease) -> Snapshot:
    import duckdb

    path = checked.folder / loader.READER_NAME
    with duckdb.connect(str(path), read_only=True) as connection:
        access = connection.execute(
            "SELECT current_setting('enable_external_access')"
        ).fetchone()
        locked = connection.execute(
            "SELECT current_setting('lock_configuration')"
        ).fetchone()
        if access is None or locked is None:
            raise StartupRefusal("startup_identity_mismatch")
        if access[0]:
            connection.execute("SET enable_external_access = false")
        if not locked[0]:
            connection.execute("SET lock_configuration = true")
        names = frozenset(
            str(row[0])
            for row in connection.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'"
            ).fetchall()
        )
    return Snapshot(loader._read_embedded(path, checked), names)


def postgres_snapshot(checked: CheckedRelease, connection: object) -> Snapshot:
    execute = loader._execute
    schema = release_schema(str(checked.document["release_id"]))
    execute(connection, "BEGIN READ ONLY")
    try:
        execute(connection, "SET LOCAL statement_timeout = '4s'")
        role = execute(connection, ROLE_SQL)
        if len(role) != 1 or len(role[0]) != 3 or role[0] != ("eii_app", False, False):
            raise StartupRefusal("startup_role_refused")
        interrupted = loader._schema_present(connection, schema + "__loading")
        names = frozenset(
            str(row[0]) for row in execute(connection, INVENTORY_SQL, (schema,))
        )
        postgis_schema = loader.require_plain_identifier(
            loader._one(execute(connection, loader._POSTGIS_SCHEMA_SQL))[0]
        )
        rows = loader._read_postgres(connection, checked, schema, postgis_schema)
        return Snapshot(rows, names, interrupted, role[0])
    finally:
        execute(connection, "ROLLBACK")


def verify_startup(
    folder: Path,
    *,
    environment: str,
    embedded: bool = False,
    postgres_reader: Callable[[CheckedRelease], Snapshot] | None = None,
    embedded_reader: Callable[[CheckedRelease], Snapshot] = embedded_snapshot,
) -> CheckedRelease:
    if environment in {"live", "staging"} and embedded:
        raise StartupRefusal("embedded_environment_refused")
    checked = check_release(folder)
    if checked.document["release_kind"] == "public_only" and os.path.lexists(
        folder / "freeze.json"
    ):
        raise StartupRefusal("public_only_freeze_forbidden")
    if any(
        (folder / name).exists()
        for name in (loader.PARTIAL_READER, ".load_receipt.json.partial")
    ):
        raise StartupRefusal("interrupted_load_refused")
    verify_artefacts(checked)
    receipt = read_receipt(folder, str(checked.document["release_id"]))
    if not embedded and postgres_reader is None:
        raise StartupRefusal("postgres_required")
    left = embedded_reader(checked)
    right = None if embedded else postgres_reader(checked) if postgres_reader else None
    verify_snapshots(checked, receipt, left, right)
    return checked
