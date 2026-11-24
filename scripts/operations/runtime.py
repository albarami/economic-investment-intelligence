"""Read-only installed environment and store checks used by start and preflight."""

from __future__ import annotations

import os
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from operations.common import Refusal, read_json
from operations.config import (
    Environment,
    database_identity,
    isolated,
)
from operations.install import public_kind, verify_application


def installed(
    env: Environment, request: Mapping[str, Any]
) -> tuple[Path, dict[str, Any]]:
    from eii_product.store.release_check import check_release

    application = env.applications / request["application_sha256"]
    manifest = verify_application(
        application,
        code_version=request["code_version"],
        application_sha256=request["application_sha256"],
    )
    public_kind(env.release, application / "infra/export_register.jsonl")
    checked = check_release(env.release)
    if (
        env.release.name != request["release_id"]
        or checked.document["release_id"] != request["release_id"]
        or checked.document["code_version"] != request["code_version"]
    ):
        raise Refusal("activation_target_mismatch")
    return application, manifest


def app_connection(environ: Mapping[str, str]) -> Any:
    from urllib.parse import urlsplit

    database_identity(environ.get("EII_DATABASE_URL", ""))

    try:
        target = urlsplit(environ["EII_DATABASE_URL"])
        if target.username != "eii_app":
            raise Refusal("startup_role_refused")
        import psycopg

        return psycopg.connect(
            environ["EII_DATABASE_URL"],
            hostaddr="127.0.0.1",
            passfile=os.devnull,
            autocommit=True,
            connect_timeout=4,
            options="-c statement_timeout=4000 -c lock_timeout=4000",
        )
    except Refusal:
        raise
    except Exception:
        raise Refusal("postgres_required", 3) from None


def check_stores(
    env: Environment,
    environ: Mapping[str, str],
    *,
    embedded: bool = False,
    connect: Callable[[Mapping[str, str]], Any] = app_connection,
) -> Any:
    from eii_product.store.startup import postgres_snapshot, verify_startup

    if (
        not embedded
        and database_identity(environ.get("EII_DATABASE_URL", "")) != env.database
    ):
        raise Refusal("cross_environment_write")
    if embedded:
        return verify_startup(env.release, environment=env.name, embedded=True)
    connection = connect(environ)
    try:
        return verify_startup(
            env.release,
            environment=env.name,
            postgres_reader=lambda checked: postgres_snapshot(checked, connection),
        )
    finally:
        connection.close()


def inspect_schema(
    env: Environment,
    environ: Mapping[str, str],
    *,
    connect: Callable[[Mapping[str, str]], Any] | None = None,
) -> bool:
    """Read role and exact selected namespace only; never reload an existing one."""
    from eii_product.store import loader
    from eii_product.store.postgres import release_schema
    from eii_product.store.startup import ROLE_SQL

    if database_identity(environ.get("EII_DATABASE_URL", "")) != env.database:
        raise Refusal("cross_environment_write")
    connection = (app_connection if connect is None else connect)(environ)
    try:
        role = loader._execute(connection, ROLE_SQL)
        if (
            len(role) != 1
            or len(role[0]) != 3
            or role[0][0] != "eii_app"
            or role[0][1] is not False
            or role[0][2] is not False
        ):
            raise Refusal("startup_role_refused")
        return loader._schema_present(connection, release_schema(env.release.name))
    finally:
        connection.close()


def verify_peers(env: Environment) -> None:
    peers = [env]
    for name in ("development", "staging", "live"):
        if name == env.name:
            continue
        home = env.home.parent / name
        path = home / "state/environment.json"
        if not path.exists():
            continue
        record = read_json(path, "environment_path_conflict")
        peers.append(
            Environment(
                name,
                home / "releases" / record["release_id"],
                home / "state",
                record["port"],
                None if record["database"] is None else tuple(record["database"]),
            )
        )
    isolated(peers)
