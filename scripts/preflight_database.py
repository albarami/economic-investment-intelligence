"""PostgreSQL and Docker probes and database URL parsing."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import unquote, urlsplit

import preflight_proc as proc
import preflight_store as store

if TYPE_CHECKING:
    from collections.abc import Mapping

SERVER_MAJOR = 18
POSTGIS_LINE = (3, 6)
SCHEMES = ("postgresql", "postgres")
LOOPBACK = "127.0.0.1"
COMPOSE_PORT_NAME = "EII_COMPOSE_DB_PORT"
FACTS_RE = re.compile(r"(\d{5,6})\|([0-9A-Za-z.]*)")
VERSION_RE = re.compile(r"[0-9]+(\.[0-9]+)+([-+~.][0-9A-Za-z.+~-]*)?")
POSTGIS_RE = re.compile(r"(\d+)\.(\d+)")
READY_RE = {
    0: "accepting connections",
    1: "rejecting connections",
    2: "no response",
}


@dataclass(frozen=True)
class DbTarget:
    """Connection target from EII_DATABASE_URL."""

    host: str
    port: int
    user: str
    password: str | None = field(repr=False)
    database: str

    def where(self) -> str:
        """Return host:port for messages."""
        host = self.host
        if ":" in host:
            host = f"[{host}]"
        return f"{host}:{self.port}"


def parse_database_url(value: str) -> DbTarget | str:
    """Parse a database URL or return a fixed reason string."""
    try:
        parts = urlsplit(value)
    except ValueError:
        return "cannot be parsed"
    scheme = parts.scheme.lower()
    if scheme not in SCHEMES:
        return "scheme is not postgresql or postgres"
    if parts.query or parts.fragment:
        return "query or fragment not allowed"
    netloc = parts.netloc
    if "," in netloc:
        return "more than one host"
    hostname = parts.hostname
    if not hostname:
        return "no host"
    try:
        port = parts.port
    except ValueError:
        return "port is not a number from 1 to 65535"
    if port is None:
        return "no port"
    if port == 0 or port < 1 or port > 65535:
        return "port is not a number from 1 to 65535"
    user = parts.username
    if not user:
        return "no user"
    path = parts.path
    if not path.startswith("/") or path == "/":
        return "no database name"
    rest = path[1:]
    if not rest or "/" in rest:
        return "no database name"
    password = unquote(parts.password) if parts.password is not None else None
    user_dec = unquote(user)
    database_dec = unquote(rest)
    if (
        "\x00" in user_dec
        or (password is not None and "\x00" in password)
        or "\x00" in database_dec
    ):
        return "user, password or database holds a NUL character"
    return DbTarget(
        hostname,
        port,
        user_dec,
        password,
        database_dec,
    )


def compose_port_env(environ: Mapping[str, str]) -> str:
    """Derive EII_COMPOSE_DB_PORT from EII_DATABASE_URL."""
    raw = environ.get("EII_DATABASE_URL", "")
    if not raw:
        msg = "EII_DATABASE_URL is not set"
        raise ValueError(msg)
    parsed = parse_database_url(raw)
    if isinstance(parsed, str):
        msg = f"EII_DATABASE_URL is not a valid connection string ({parsed})"
        raise ValueError(msg)
    if parsed.host != LOOPBACK:
        msg = "EII_DATABASE_URL host is not 127.0.0.1"
        raise ValueError(msg)
    return f"{COMPOSE_PORT_NAME}={parsed.port}\n"


def judge_server_facts(match: re.Match[str], target: DbTarget) -> store.PgOutcome:
    """Judge server version and PostGIS from psql output."""
    where = target.where()
    n = int(match.group(1))
    major = n // 10000
    minor = n % 10000
    postgis_raw = match.group(2)
    reasons: list[str] = []
    if major != SERVER_MAJOR:
        reasons.append(f"server version {major}.{minor} is not 18.x")
    if not postgis_raw:
        reasons.append(f"PostGIS is not installed in database {target.database}")
    else:
        pm = POSTGIS_RE.match(postgis_raw)
        if not pm:
            reasons.append(f"PostGIS version {postgis_raw} not understood")
        else:
            pmaj = int(pm.group(1))
            pmin = int(pm.group(2))
            if (pmaj, pmin) != POSTGIS_LINE:
                reasons.append(f"PostGIS {postgis_raw} is not 3.6.x")
    if reasons:
        joined = "; ".join(reasons)
        return store.PgOutcome(
            "fail",
            f"PostgreSQL on {where} fails its checks: {joined}",
        )
    return store.PgOutcome(
        "ok",
        f"PostgreSQL {major}.{minor} with PostGIS {postgis_raw} answers on {where}",
    )


def _run_pg_isready(
    target: DbTarget,
    environ: Mapping[str, str],
    scratch: Path,
    limit: float,
) -> store.PgOutcome:
    where = target.where()
    t = f"{limit:g}"
    program = proc.find_program("pg_isready", environ)
    if program is None:
        return store.PgOutcome(
            "absent",
            "pg_isready not found on PATH, so PostgreSQL cannot answer here",
        )
    env = proc.child_env(
        "pg_isready",
        environ,
        {"PGPASSFILE": str(scratch / "absent")},
    )
    args = (
        "-h",
        target.host,
        "-p",
        str(target.port),
        "-t",
        proc.PG_ISREADY_WAIT,
    )
    result = proc.run_child(program, args, env, scratch, limit=limit)
    if result.start_error is not None:
        return store.PgOutcome(
            "fail",
            f"pg_isready could not be started ({result.start_error})",
        )
    if result.timed_out:
        return store.PgOutcome("absent", f"no answer on {where} within {t} s")
    status = result.status
    out = result.stdout
    err = result.stderr
    if status == 2 and re.fullmatch(r"[^\n]+ - no response\n", out) and not err:
        return store.PgOutcome(
            "absent",
            f"no answer on {where} (pg_isready exit status 2)",
        )
    if (
        status == 1
        and re.fullmatch(
            r"[^\n]+ - rejecting connections\n",
            out,
        )
        and not err
    ):
        return store.PgOutcome(
            "fail",
            f"PostgreSQL on {where} rejects connections (pg_isready exit status 1)",
        )
    if status == 3:
        return store.PgOutcome(
            "fail",
            "pg_isready made no connection attempt (exit status 3)",
        )
    if (
        status == 0
        and re.fullmatch(
            r"[^\n]+ - accepting connections\n",
            out,
        )
        and not err
    ):
        return _run_psql(target, environ, scratch, limit)
    if status in (0, 1, 2):
        return store.PgOutcome(
            "fail",
            f"pg_isready output not understood (exit status {status})",
        )
    return store.PgOutcome("fail", f"pg_isready exit status {status}")


def _run_psql(
    target: DbTarget,
    environ: Mapping[str, str],
    scratch: Path,
    limit: float,
) -> store.PgOutcome:
    where = target.where()
    t = f"{limit:g}"
    program = proc.find_program("psql", environ)
    if program is None:
        return store.PgOutcome(
            "fail",
            f"PostgreSQL answers on {where}, but psql is not found on PATH, "
            "so its version and PostGIS cannot be checked",
        )
    extra: dict[str, str] = {
        "PGHOST": target.host,
        "PGPORT": str(target.port),
        "PGUSER": target.user,
        "PGDATABASE": target.database,
        "PGCONNECT_TIMEOUT": proc.PG_ISREADY_WAIT,
        "PGPASSFILE": str(scratch / "absent"),
    }
    if target.password is not None:
        extra["PGPASSWORD"] = target.password
    env = proc.child_env("psql", environ, extra)
    args = ("-X", "-w", "-q", "-t", "-A", "-F", "|", "-c", proc.CHECK_QUERY)
    result = proc.run_child(program, args, env, scratch, limit=limit)
    if result.start_error is not None:
        return store.PgOutcome(
            "fail",
            f"PostgreSQL answers on {where}, but psql could not be started "
            f"({result.start_error})",
        )
    if result.timed_out:
        return store.PgOutcome(
            "fail",
            f"PostgreSQL answers on {where}, but the check query gave no result "
            f"within {t} s",
        )
    status = result.status
    if status != 0:
        return store.PgOutcome(
            "fail",
            f"PostgreSQL answers on {where}, but the check query failed "
            f"(psql exit status {status})",
        )
    if result.stderr or not re.fullmatch(
        r"[^\n]*\n",
        result.stdout,
    ):
        return store.PgOutcome(
            "fail",
            f"PostgreSQL answers on {where}, but the check query output is not understood",
        )
    m = FACTS_RE.fullmatch(result.stdout[:-1])
    if m is None:
        return store.PgOutcome(
            "fail",
            f"PostgreSQL answers on {where}, but the check query output is not understood",
        )
    return judge_server_facts(m, target)


def probe_postgres(
    environ: Mapping[str, str],
    scratch: Path,
    limit: float,
) -> store.PgOutcome:
    """Probe PostgreSQL via pg_isready and psql."""
    raw = environ.get("EII_DATABASE_URL", "")
    if not raw:
        return store.PgOutcome("absent", "EII_DATABASE_URL is not set")
    parsed = parse_database_url(raw)
    if isinstance(parsed, str):
        return store.PgOutcome(
            "fail",
            f"EII_DATABASE_URL is not a valid connection string ({parsed})",
        )
    try:
        return _run_pg_isready(parsed, environ, scratch, limit)
    except proc.CommandRefused:
        return store.PgOutcome(
            "fail",
            "a command outside the closed list was refused",
        )


def probe_docker(
    environ: Mapping[str, str],
    scratch: Path,
    limit: float,
) -> store.DockerOutcome:
    """Probe Docker with a read-only info command."""
    t = f"{limit:g}"
    program = proc.find_program("docker", environ)
    if program is None:
        return store.DockerOutcome("not_found", "")
    env = proc.child_env("docker", environ, {})
    args = ("info", "--format", "{{.ServerVersion}}")
    result = proc.run_child(program, args, env, scratch, limit=limit)
    if result.start_error is not None:
        return store.DockerOutcome("not_started", result.start_error)
    if result.timed_out:
        return store.DockerOutcome("no_answer", t)
    if result.status == 0 and re.fullmatch(r"[^\n]*\n", result.stdout):
        line = result.stdout.rstrip("\n")
        if VERSION_RE.fullmatch(line):
            return store.DockerOutcome("reachable", line)
    return store.DockerOutcome("unreachable", "")


def check_postgres(
    environ: Mapping[str, str],
    scratch: Path,
    limit: float,
    *,
    embedded: bool = False,
    docker: bool = True,
) -> store.Selection:
    """Run PostgreSQL (and optionally Docker) probes and select a store."""
    if embedded:
        return store.select_store(None, None)
    pg = probe_postgres(environ, scratch, limit)
    if pg.kind == "absent":
        if docker:
            docker_out = probe_docker(environ, scratch, limit)
        else:
            docker_out = store.DockerOutcome("not_probed", "")
    else:
        docker_out = None
    return store.select_store(pg, docker_out)
