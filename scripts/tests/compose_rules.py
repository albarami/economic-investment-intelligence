"""Deterministic contract for infra/compose.yaml."""

from __future__ import annotations

import errno
import os
import re
from collections.abc import Mapping
from pathlib import Path

import yaml  # type: ignore[import-untyped]

DIGEST = "sha256:4a43e3c3e5d55b9208240fc71db543b79c638766280c625a425bd0a2390989c4"
IMAGE = "postgis/postgis@" + DIGEST
TOP_KEYS = ["name", "secrets", "services", "volumes"]
SERVICE_KEYS = [
    "environment",
    "healthcheck",
    "image",
    "ports",
    "pull_policy",
    "secrets",
    "volumes",
]
PORTS = [
    "127.0.0.1:${EII_COMPOSE_DB_PORT:?required, derived from EII_DATABASE_URL}:5432"
]
ENVIRONMENT = {
    "POSTGRES_PASSWORD_FILE": "/run/secrets/postgres_superuser_password",
}
SERVICE_SECRETS = ["postgres_superuser_password"]
TOP_SECRETS = {
    "postgres_superuser_password": {
        "file": "../data/compose/postgres_superuser_password",
    },
}
SERVICE_VOLUMES = ["eii_pgdata:/var/lib/postgresql"]
TOP_VOLUMES = {"eii_pgdata": None}
HEALTHCHECK = {
    "test": ["CMD", "pg_isready", "-h", "127.0.0.1", "-p", "5432"],
    "interval": "2s",
    "retries": 30,
}
FORBIDDEN_TEXT = ("shared_preload_libraries", "55432", "0.0.0.0", "trust")
INTERPOLATION_RE = re.compile(r"\$\{?([A-Za-z_][A-Za-z0-9_]*)")
INTERPOLATIONS = ["EII_COMPOSE_DB_PORT"]


def _line(rule: str, detail: str) -> str:
    return f"compose: {rule}: {detail}"


def _different(
    problems: list[str],
    rule: str,
    label: str,
    actual: object,
    expected: object,
) -> None:
    if actual != expected:
        problems.append(
            _line(rule, f"{label} is {actual!r}, expected {expected!r}"),
        )


def check_compose_file(path: Path) -> list[str]:
    """Read and judge the Compose file without opening an adjacent .env."""
    problems: list[str] = []
    if os.path.lexists(path.parent / ".env"):
        problems.append(
            _line(
                "env-file",
                "infra/.env exists beside compose.yaml; Compose would read it",
            ),
        )
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        return [*problems, _line("file", "infra/compose.yaml is missing")]
    except OSError as exc:
        code = (
            errno.errorcode.get(exc.errno, type(exc).__name__)
            if exc.errno is not None
            else type(exc).__name__
        )
        return [
            *problems,
            _line("file", f"infra/compose.yaml cannot be read ({code})"),
        ]
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return [*problems, _line("file", "infra/compose.yaml is not UTF-8")]
    return problems + check_compose(text)


def check_compose(text: str) -> list[str]:
    """Judge the closed Compose contract with S0-T07's YAML library call."""
    try:
        document = yaml.safe_load(text)
    except yaml.YAMLError:
        return [_line("yaml", "cannot be parsed")]
    if not isinstance(document, Mapping):
        return [_line("yaml", "top level is not a mapping")]

    problems: list[str] = []
    top = dict(document)
    _different(
        problems,
        "top-level-keys",
        "keys",
        sorted(str(key) for key in top),
        TOP_KEYS,
    )
    _different(problems, "name", "name", top.get("name"), "eii-poc")

    services = top.get("services")
    service_map = dict(services) if isinstance(services, Mapping) else {}
    _different(
        problems,
        "services",
        "services",
        sorted(str(key) for key in service_map),
        ["db"],
    )
    db = service_map.get("db")
    db_map = dict(db) if isinstance(db, Mapping) else {}
    if sorted(str(key) for key in service_map) == ["db"]:
        _different(
            problems,
            "service-keys",
            "db keys",
            sorted(str(key) for key in db_map),
            SERVICE_KEYS,
        )
    if sorted(str(key) for key in top) == TOP_KEYS and list(service_map) == ["db"]:
        if sorted(str(key) for key in db_map) == SERVICE_KEYS:
            _different(problems, "image", "image", db_map.get("image"), IMAGE)
            _different(
                problems,
                "pull-policy",
                "pull_policy",
                db_map.get("pull_policy"),
                "never",
            )
            _different(problems, "ports", "ports", db_map.get("ports"), PORTS)
            _different(
                problems,
                "environment",
                "environment",
                db_map.get("environment"),
                ENVIRONMENT,
            )
            _different(
                problems,
                "secrets",
                "db secrets",
                db_map.get("secrets"),
                SERVICE_SECRETS,
            )
            _different(
                problems,
                "volumes",
                "db volumes",
                db_map.get("volumes"),
                SERVICE_VOLUMES,
            )
            _different(
                problems,
                "healthcheck",
                "healthcheck",
                db_map.get("healthcheck"),
                HEALTHCHECK,
            )
        _different(
            problems,
            "secrets",
            "top-level secrets",
            top.get("secrets"),
            TOP_SECRETS,
        )
        _different(
            problems,
            "volumes",
            "top-level volumes",
            top.get("volumes"),
            TOP_VOLUMES,
        )

    for forbidden in FORBIDDEN_TEXT:
        if forbidden in text:
            problems.append(_line("forbidden-text", f"contains {forbidden}"))
    names = sorted(INTERPOLATION_RE.findall(text))
    _different(
        problems,
        "interpolation",
        "names",
        names,
        INTERPOLATIONS,
    )
    return problems
