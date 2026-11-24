"""Environment isolation and the closed API-child environment."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urlsplit

from operations.common import Refusal

API_NAMES = frozenset(
    {
        "PATH",
        "HOME",
        "LANG",
        "LC_ALL",
        "EII_ENVIRONMENT",
        "EII_LISTEN_HOST",
        "EII_API_PORT",
        "EII_RELEASE_DIR",
        "EII_DATABASE_URL",
        "EII_STATE_DIR",
        "EII_OPERATION_RECORD",
        "EII_LANG_DEFAULT",
        "EII_TRAFFIC_PROVIDER",
        "EII_PRESENTER",
        "EII_DECISION_PROVIDER",
    }
)
INSTALL_NAMES = frozenset({"EII_SOURCE_RELEASE_DIR", "EII_APPLICATION_ARCHIVE"})
RESTRICTED = frozenset(
    {
        "ANTHROPIC_API_KEY",
        "TOMTOM_API_KEY",
        "EARTHDATA_API_KEY",
        "CDSE_CLIENT_ID",
        "CDSE_CLIENT_SECRET",
        "BESTTIME_API_KEY_PRIVATE",
        "BESTTIME_API_KEY_PUBLIC",
        "JEV_PRO_API_KEY",
        "PGPASSWORD",
        "MAPTILE_API_KEY",
        "ESRI_API_KEY",
    }
)
DEFAULT_PORTS = {"development": 8000, "staging": 8089, "live": 8088}
LIVE_BACKENDS = (18088, 18089)


def api_port(value: str, default: int = 8000) -> int:
    if value == "":
        return default
    if not value.isascii() or not value.isdecimal() or not 1 <= int(value) <= 65535:
        raise Refusal("api_port_invalid", 1)
    return int(value)


def runtime_environment(
    environ: Mapping[str, str], *, installing: bool = False
) -> dict[str, str]:
    allowed = API_NAMES | (INSTALL_NAMES if installing else frozenset())
    for name, value in environ.items():
        if (
            value
            and name not in allowed
            and (
                name.startswith(("EII_", "PG"))
                or name in RESTRICTED
                or name.endswith("_API_KEY")
            )
        ):
            raise Refusal("unwanted_runtime_setting", 1)
    for name, expected, reason in (
        ("EII_DECISION_PROVIDER", "none", "decision_mode_refused"),
        ("EII_PRESENTER", "0", "presenter_mode_refused"),
        ("EII_TRAFFIC_PROVIDER", "simulated", "traffic_mode_refused"),
    ):
        if environ.get(name, "") not in ("", expected):
            raise Refusal(reason, 1)
    result = {name: value for name, value in environ.items() if name in API_NAMES}
    result.update(
        EII_DECISION_PROVIDER="none",
        EII_PRESENTER="0",
        EII_TRAFFIC_PROVIDER="simulated",
    )
    return result


def database_identity(value: str) -> tuple[str, int, str]:
    try:
        parts = urlsplit(value)
        if (
            parts.scheme not in {"postgres", "postgresql"}
            or parts.hostname not in {"localhost", "127.0.0.1"}
            or parts.query
            or parts.fragment
            or not parts.path.strip("/")
        ):
            raise ValueError
        return "127.0.0.1", parts.port or 5432, unquote(parts.path[1:])
    except ValueError:
        raise Refusal("database_url_invalid", 1) from None


def require_database_environment(name: str, database: str) -> None:
    """Reserve case-insensitive suffixes without changing the connection name."""
    if name not in DEFAULT_PORTS:
        raise Refusal("environment_invalid", 1)
    folded = database.casefold()
    if (
        folded.endswith(("_staging", "_live"))
        if name == "development"
        else not folded.endswith("_" + name)
    ):
        raise Refusal("environment_database_conflict")


@dataclass(frozen=True)
class Environment:
    name: str
    release: Path
    state: Path
    port: int
    database: tuple[str, int, str] | None

    def __post_init__(self) -> None:
        if self.database is not None:
            require_database_environment(self.name, self.database[2])

    @property
    def home(self) -> Path:
        return self.state.parent

    @property
    def applications(self) -> Path:
        return self.home / "applications"

    @property
    def count_path(self) -> Path:
        # Stable across application/release upgrades. Never initialised here.
        return self.state / "photoreal-count.log"


def isolated(environments: Sequence[Environment]) -> None:
    """A config pair cannot alias any release, application, mutable state or DB."""
    seen_paths: list[Path] = []
    databases: set[tuple[str, int, str]] = set()
    ports: set[int] = set()
    for env in environments:
        if env.release.is_symlink():
            raise Refusal("environment_path_conflict")
        for path in (env.release.parent, env.applications, env.state):
            if any(part.is_symlink() for part in (path, *path.parents)):
                raise Refusal("environment_path_conflict")
            resolved = path.resolve()
            if any(
                resolved == other
                or resolved.is_relative_to(other)
                or other.is_relative_to(resolved)
                for other in seen_paths
            ):
                raise Refusal("environment_path_conflict")
            seen_paths.append(resolved)
        if env.database is not None and env.database in databases:
            raise Refusal("environment_database_conflict")
        if env.database is not None:
            databases.add(env.database)
        elif env.name != "development":
            raise Refusal("postgres_required")
        if env.port in ports or env.port in LIVE_BACKENDS:
            raise Refusal("environment_port_conflict")
        ports.add(env.port)


def write_target(env: Environment, path: Path) -> Path:
    if any(part.is_symlink() for part in (path, *path.parents)):
        raise Refusal("cross_environment_write")
    resolved = path.resolve()
    if not any(
        resolved.is_relative_to(root.resolve())
        for root in (env.release.parent, env.applications, env.state)
    ):
        raise Refusal("cross_environment_write")
    return path


def persistent_paths(env: Environment) -> tuple[Path, Path]:
    """Check each mutable file at use, after configuration validation too."""
    return (
        write_target(env, env.state / "local-ledger.sqlite"),
        write_target(env, env.count_path),
    )


def read_environment(
    environ: Mapping[str, str], *, installing: bool = False, embedded: bool = False
) -> Environment:
    runtime_environment(environ, installing=installing)
    name = environ.get("EII_ENVIRONMENT") or "development"
    if name not in DEFAULT_PORTS:
        raise Refusal("environment_invalid", 1)
    if embedded and name != "development":
        raise Refusal("embedded_environment_refused")
    if environ.get("EII_LISTEN_HOST", "127.0.0.1") != "127.0.0.1":
        raise Refusal("host_not_loopback", 1)
    release = Path(environ.get("EII_RELEASE_DIR", ""))
    state = Path(environ.get("EII_STATE_DIR", ""))
    if not environ.get("EII_RELEASE_DIR") or not environ.get("EII_STATE_DIR"):
        raise Refusal("deployment_configuration_missing")
    if (
        not state.is_absolute()
        or not release.is_absolute()
        or state.name != "state"
        or state.parent.name != name
        or release.parent != state.parent / "releases"
    ):
        raise Refusal("environment_path_conflict")
    database = (
        database_identity(environ.get("EII_DATABASE_URL", ""))
        if not embedded or environ.get("EII_DATABASE_URL")
        else None
    )
    if database is not None:
        require_database_environment(name, database[2])
    env = Environment(
        name,
        release,
        state,
        api_port(environ.get("EII_API_PORT", ""), DEFAULT_PORTS[name]),
        None if embedded else database,
    )
    if env.port in set(DEFAULT_PORTS.values()) - {DEFAULT_PORTS[name]} or (
        name == "live" and env.port != 8088
    ):
        raise Refusal("environment_port_conflict")
    isolated((env,))
    return env
