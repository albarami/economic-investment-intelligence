"""Load one public release, and refuse to freeze one."""

from __future__ import annotations

import json
import sys
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

import commands.exits as exits
import commands.placeholder as placeholder
import commands.table as table
import preflight_database as database
from eii_core.reasons import reason
from eii_product.store.loader import OwnerConnectFailed, PostgresNotAnswering, run_load
from eii_product.store.receipt import refuse_public_only_freeze

LOOPBACK = "127.0.0.1"


def run(
    environ: Mapping[str, str],
    rest: Sequence[str],
    connect: Callable[..., object] | None = None,
    root: Path | None = None,
) -> int:
    """Load the release named by EII_RELEASE_DIR. A bad flag exits 2."""
    if rest:
        table.write_usage()
        return 2
    if environ.get("EII_ENVIRONMENT") in {"live", "staging"}:
        from operations.common import Refusal
        from operations.deploy import load

        try:
            return load(Path.cwd() if root is None else root, environ, connect=connect)
        except Refusal as error:
            return exits.finish(error.code, "load-release", error.reason)
        except Exception as error:
            return exits.finish(4, "load-release", reason(error))
    folder = environ.get("EII_RELEASE_DIR", "")
    if folder == "":
        return exits.finish(4, "load-release", "release_missing")
    target = _target(environ)
    if isinstance(target, int):
        return target
    if target.host != LOOPBACK:
        return exits.finish(1, "load-release", "host_not_loopback")
    opener = _connect if connect is None else connect
    code = run_load(
        Path(folder),
        host=target.host,
        port=target.port,
        database=target.database,
        connect=opener,
    )
    if code == 0:
        return 0
    sys.stderr.write(f"eii: exit {code}: {exits.MEANINGS[code]}\n")
    return code


def run_freeze(environ: Mapping[str, str], rest: Sequence[str]) -> int:
    """A public_only release is refused. Any other kind stays a placeholder."""
    if rest:
        table.write_usage()
        return 2
    folder = environ.get("EII_RELEASE_DIR", "")
    if folder != "":
        reason = _freeze_reason(Path(folder))
        if reason is not None:
            return exits.finish(7, "freeze", reason)
    return placeholder.run("freeze")


def _target(environ: Mapping[str, str]) -> database.DbTarget | int:
    from operations.common import Refusal
    from operations.config import require_database_environment

    raw = environ.get("EII_DATABASE_URL", "")
    if raw == "":
        return exits.finish(3, "load-release", "postgres_not_answering")
    parsed = database.parse_database_url(raw)
    if isinstance(parsed, str):
        return exits.finish(1, "load-release", parsed)
    try:
        require_database_environment(
            environ.get("EII_ENVIRONMENT") or "development", parsed.database
        )
    except Refusal as error:
        return exits.finish(error.code, "load-release", error.reason)
    return parsed


def _connect(host: str, port: int, dbname: str, user: str) -> object:
    import psycopg
    from psycopg import errors

    del user
    try:
        return psycopg.connect(host=host, port=port, dbname=dbname, user="eii_owner")
    except errors.InvalidAuthorizationSpecification:
        raise OwnerConnectFailed() from None
    except (errors.ConnectionException, psycopg.OperationalError):
        raise PostgresNotAnswering() from None


def _freeze_reason(folder: Path) -> str | None:
    path = folder / "manifest.json"
    if not path.is_file():
        return None
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    if type(document) is not dict:
        return None
    return refuse_public_only_freeze(document)
