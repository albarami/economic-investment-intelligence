"""Preflight row checks other than PostgreSQL store selection."""

from __future__ import annotations

import errno
import os
import re
import socket
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

import preflight_proc as proc
import preflight_store as store
import versions_record as versions_record
import versions_tools as versions_tools

API_HOST = "127.0.0.1"
API_PORT = 8000
RELEASE_ROWS = ("release", "load-receipt", "embedded-reader")
REPLAY_ROW = "recorded-replays"
NOT_CONFIGURED = "not_configured (EII_RELEASE_DIR is not set)"
NOT_BUILT = (
    "not_built (EII_RELEASE_DIR is set, and this check is not built in slice S0)"
)
WINDOWS_RE = re.compile(r"Microsoft Windows \[Version [0-9.]+\]\r?")
GIT_UNTRACKED = (
    "error: pathspec '.env' did not match any file(s) known to git\n",
    "error: pathspec '.env' did not match any file(s) known to git\n"
    "Did you forget to 'git add'?\n",
)
TOOLCHAIN_NAMES = frozenset({"python", "uv", "node", "npm"})
ToolchainFailure = tuple[str, str, str]


@dataclass(frozen=True)
class ToolchainProbe:
    """One complete S0-T12 toolchain probe."""

    record_problems: int
    failures: tuple[ToolchainFailure, ...]
    raised: str | None


@dataclass(frozen=True)
class ToolChecks:
    """Deferred preflight rows, injectable by tests."""

    python: Callable[[], store.Line]
    node_npm: Callable[[], store.Line]
    extensions: Callable[[], store.Line]
    bubblewrap: Callable[[], store.Line]


def _probe_toolchain(
    root: Path,
    environ: Mapping[str, str],
    limit: float,
    interpreter: tuple[int, int, int],
) -> ToolchainProbe:
    """Load all toolchain rows and run the S0-T12 checker once."""
    try:
        components, record_failures, _count = versions_record.load_record(root)
        if record_failures:
            return ToolchainProbe(len(record_failures), (), None)
        failures = versions_tools.check_toolchain(
            components,
            interpreter,
            environ,
            root,
            limit,
        )
    except Exception as exc:
        return ToolchainProbe(0, (), type(exc).__name__)
    return ToolchainProbe(0, tuple(failures), None)


def toolchain_row(
    check: str,
    names: frozenset[str],
    probe: ToolchainProbe,
) -> store.Line:
    """Render one row from the complete toolchain probe."""
    if probe.raised is not None:
        return store.Line("FAIL", check, f"the check raised {probe.raised}")
    if probe.record_problems:
        return store.Line(
            "FAIL",
            check,
            f"pins.toml cannot be read ({probe.record_problems} problems); "
            "run uv run --locked python scripts/check_versions.py",
        )
    selected = [
        f"{where} {detail}"
        for _rule, where, detail in probe.failures
        if where in names or where not in TOOLCHAIN_NAMES
    ]
    if selected:
        return store.Line("FAIL", check, "; ".join(selected))
    passed = (
        "Python and uv match pins.toml"
        if check == "python"
        else "Node and npm match pins.toml"
    )
    return store.Line("PASS", check, passed)


def sandbox_row(
    check: str,
    command: str,
    passed: str,
    root: Path,
    environ: Mapping[str, str],
    limit: float,
) -> store.Line:
    """Run one supported sandbox CLI under the bounded child runner."""
    diagnostic = f"run uv run --locked python scripts/sandbox_check.py {command}"
    env = proc.child_env(proc.INTERPRETER, environ, {})
    try:
        result = proc.run_child(
            sys.executable,
            (proc.SANDBOX_CHECK, command),
            env,
            root,
            limit=limit,
        )
    except proc.CommandRefused:
        return store.Line(
            "FAIL",
            check,
            f"the sandbox command was refused; {diagnostic}",
        )
    if result.start_error is not None:
        return store.Line(
            "FAIL",
            check,
            f"the sandbox command could not start ({result.start_error}); {diagnostic}",
        )
    if result.timed_out:
        return store.Line(
            "FAIL",
            check,
            f"the sandbox command timed out after {limit:g} s; {diagnostic}",
        )
    if result.status != 0:
        return store.Line(
            "FAIL",
            check,
            f"the sandbox command exited with status {result.status}; {diagnostic}",
        )
    return store.Line("PASS", check, passed)


def default_tools(
    root: Path,
    environ: Mapping[str, str],
    limit: float,
) -> ToolChecks:
    """Build the four real deferred row callables."""
    probe = _probe_toolchain(root, environ, limit, sys.version_info[:3])
    return ToolChecks(
        python=lambda: toolchain_row(
            "python",
            frozenset({"python", "uv"}),
            probe,
        ),
        node_npm=lambda: toolchain_row(
            "node-npm",
            frozenset({"node", "npm"}),
            probe,
        ),
        extensions=lambda: sandbox_row(
            "duckdb-extensions",
            "check-extensions",
            "spatial and h3 load from the local folder with network access disabled",
            root,
            environ,
            limit,
        ),
        bubblewrap=lambda: sandbox_row(
            "bubblewrap-sandbox",
            "check",
            "bubblewrap is present and the sandbox test passes",
            root,
            environ,
            limit,
        ),
    )


def foundation_mode(environ: Mapping[str, str]) -> bool:
    """Return whether EII_RELEASE_DIR is unset or empty."""
    return environ.get("EII_RELEASE_DIR", "") == ""


def release_rows(environ: Mapping[str, str]) -> dict[str, store.Line]:
    """Return release-related row lines."""
    if foundation_mode(environ):
        return {
            "release": store.Line("WARN", "release", NOT_CONFIGURED),
            "load-receipt": store.Line("WARN", "load-receipt", NOT_CONFIGURED),
            "embedded-reader": store.Line("WARN", "embedded-reader", NOT_CONFIGURED),
            "recorded-replays": store.Line("WARN", "recorded-replays", NOT_CONFIGURED),
        }
    return {
        "release": store.Line("FAIL", "release", NOT_BUILT),
        "load-receipt": store.Line("FAIL", "load-receipt", NOT_BUILT),
        "embedded-reader": store.Line("FAIL", "embedded-reader", NOT_BUILT),
        "recorded-replays": store.Line("WARN", "recorded-replays", NOT_BUILT),
    }


def freeze_bundle_count(root: Path) -> int:
    """Count freeze.json entries under data/freeze."""
    freeze_dir = root / "data" / "freeze"
    try:
        names = sorted(os.listdir(freeze_dir))
    except FileNotFoundError:
        return 0
    count = 0
    for name in names:
        entry = freeze_dir / name
        if os.path.lexists(entry / "freeze.json"):
            count += 1
    return count


def tiles_row(root: Path) -> store.Line:
    """Check for freeze bundles under data/freeze."""
    try:
        n = freeze_bundle_count(root)
    except NotADirectoryError:
        return store.Line("FAIL", "tiles-glyphs-fonts", "data/freeze is not a folder")
    except OSError as exc:
        if exc.errno is None:
            raise
        code = errno.errorcode.get(exc.errno, type(exc).__name__)
        return store.Line(
            "FAIL",
            "tiles-glyphs-fonts",
            f"data/freeze cannot be listed ({code})",
        )
    if n == 0:
        return store.Line(
            "WARN",
            "tiles-glyphs-fonts",
            "no_freeze_bundle (no freeze.json under data/freeze; "
            "checked with full severity once a freeze bundle exists)",
        )
    return store.Line(
        "FAIL",
        "tiles-glyphs-fonts",
        f"freeze bundle found ({n} freeze.json under data/freeze), "
        "and the tile, glyph and font hash check is not built in slice S0",
    )


def api_port_row(port: int = API_PORT) -> store.Line:
    """Probe whether the API port can be bound on loopback."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((API_HOST, port))
    except OSError as exc:
        if exc.errno == errno.EADDRINUSE:
            return store.Line("FAIL", "api-port", f"{API_HOST}:{port} is in use")
        if exc.errno is None:
            code = type(exc).__name__
        else:
            code = errno.errorcode.get(exc.errno, type(exc).__name__)
        return store.Line(
            "FAIL",
            "api-port",
            f"{API_HOST}:{port} cannot be bound ({code})",
        )
    else:
        return store.Line("PASS", "api-port", f"{API_HOST}:{port} is free")
    finally:
        sock.close()


def model_key_row(environ: Mapping[str, str]) -> store.Line:
    """Report whether ANTHROPIC_API_KEY is set."""
    if environ.get("ANTHROPIC_API_KEY", ""):
        return store.Line("PASS", "model-key", "present")
    return store.Line("PASS", "model-key", "absent")


def traffic_provider_key_row(environ: Mapping[str, str]) -> store.Line:
    """Report optional traffic key presence and the closed provider setting."""
    provider = environ.get("EII_TRAFFIC_PROVIDER", "") or "simulated"
    if provider not in ("simulated", "tomtom"):
        return store.Line(
            "FAIL",
            "traffic-provider-key",
            "EII_TRAFFIC_PROVIDER must be simulated or tomtom",
        )
    presence = "present" if environ.get("TOMTOM_API_KEY", "") else "absent"
    return store.Line(
        "PASS", "traffic-provider-key", f"{presence}; EII_TRAFFIC_PROVIDER {provider}"
    )


def night_lights_key_row(environ: Mapping[str, str]) -> store.Line:
    """Report optional night-lights key presence without contacting a source."""
    if environ.get("EARTHDATA_API_KEY", ""):
        return store.Line("PASS", "night-lights-key", "present")
    return store.Line("PASS", "night-lights-key", "absent")


def git_env(root: Path, environ: Mapping[str, str]) -> dict[str, str]:
    """Build git environment with ceiling directories."""
    return proc.child_env(
        "git",
        environ,
        {
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CEILING_DIRECTORIES": str(root.parent),
        },
    )


def env_tracked_row(
    root: Path,
    environ: Mapping[str, str],
    limit: float,
) -> store.Line:
    """Check whether .env is tracked by git."""
    t = f"{limit:g}"
    program = proc.find_program("git", environ)
    if program is None:
        return store.Line("FAIL", "env-not-tracked", "git not found on PATH")
    env = git_env(root, environ)
    try:
        result = proc.run_child(
            program,
            ("ls-files", "--error-unmatch", ".env"),
            env,
            root,
            limit=limit,
        )
    except proc.CommandRefused:
        return store.Line(
            "FAIL",
            "env-not-tracked",
            "a command outside the closed list was refused",
        )
    if result.start_error is not None:
        return store.Line(
            "FAIL",
            "env-not-tracked",
            f"git could not be started ({result.start_error})",
        )
    if result.timed_out:
        return store.Line(
            "FAIL",
            "env-not-tracked",
            f"git gave no answer within {t} s",
        )
    status = result.status
    if status == 1 and not result.stdout and result.stderr in GIT_UNTRACKED:
        return store.Line("PASS", "env-not-tracked", ".env is not tracked by git")
    if status == 0 and result.stdout == ".env\n":
        return store.Line("FAIL", "env-not-tracked", ".env is tracked by git")
    return store.Line(
        "FAIL",
        "env-not-tracked",
        f"git output not understood (exit status {status})",
    )


def wsl_row(root: Path, environ: Mapping[str, str], limit: float) -> store.Line:
    """Run cmd.exe /c ver as a WSL interoperability warning."""
    t = f"{limit:g}"
    program = proc.find_program("cmd.exe", environ)
    if program is None:
        return store.Line("WARN", "wsl-interop", "cmd.exe not found on PATH")
    env = proc.child_env("cmd.exe", environ, {})
    try:
        result = proc.run_child(program, ("/c", "ver"), env, root, limit=limit)
    except proc.CommandRefused:
        return store.Line(
            "FAIL",
            "wsl-interop",
            "a command outside the closed list was refused",
        )
    if result.start_error is not None:
        return store.Line(
            "WARN",
            "wsl-interop",
            f"cmd.exe could not be started ({result.start_error}); see OPS-43",
        )
    if result.timed_out:
        return store.Line("WARN", "wsl-interop", f"cmd.exe gave no answer within {t} s")
    if result.status == 0 and any(
        WINDOWS_RE.fullmatch(text) for text in result.stdout.split("\n")
    ):
        return store.Line("PASS", "wsl-interop", "cmd.exe printed a Windows version")
    if result.status != 0:
        return store.Line("WARN", "wsl-interop", f"cmd.exe exit status {result.status}")
    return store.Line("WARN", "wsl-interop", "cmd.exe output not understood")


def locked_dependencies_row(
    root: Path,
    environ: Mapping[str, str],
    scratch: Path,
    limit: float,
) -> store.Line:
    """Check uv.lock and web/package-lock.json offline."""
    t = f"{limit:g}"
    problems: list[str] = []

    program = proc.find_program("uv", environ)
    if program is None:
        problems.append("uv not found on PATH")
    else:
        env = proc.child_env("uv", environ, {"UV_NO_CONFIG": "1"})
        try:
            result = proc.run_child(
                program,
                ("lock", "--check", "--offline"),
                env,
                root,
                limit=limit,
            )
        except proc.CommandRefused:
            return store.Line(
                "FAIL",
                "locked-dependencies",
                "a command outside the closed list was refused",
            )
        if result.start_error is not None:
            problems.append(f"uv could not be started ({result.start_error})")
        elif result.timed_out:
            problems.append(f"uv gave no answer within {t} s")
        elif result.status == 0 and not result.stdout:
            pass
        elif result.status == 1:
            problems.append(
                "uv.lock does not match the manifests without the network "
                "(uv lock --check exit status 1)",
            )
        else:
            problems.append(f"uv output not understood (exit status {result.status})")

    pkg = root / "web" / "package.json"
    lock = root / "web" / "package-lock.json"
    if not pkg.is_file():
        problems.append("web/package.json is missing")
    elif not lock.is_file():
        problems.append("web/package-lock.json is missing")
    else:
        npm_prog = proc.find_program("npm", environ)
        if npm_prog is None:
            problems.append("npm not found on PATH")
        else:
            user_cfg = scratch / "absent-user"
            global_cfg = scratch / "absent-global"
            npm_env = proc.child_env(
                "npm",
                environ,
                {
                    "npm_config_userconfig": str(user_cfg),
                    "npm_config_globalconfig": str(global_cfg),
                    "npm_config_update_notifier": "false",
                    "npm_config_cache": str(scratch / "npm-cache"),
                    "TMPDIR": str(scratch),
                },
            )
            try:
                npm_result = proc.run_child(
                    npm_prog,
                    ("ls", "--package-lock-only", "--offline", "--logs-max=0"),
                    npm_env,
                    root / "web",
                    limit=limit,
                )
            except proc.CommandRefused:
                return store.Line(
                    "FAIL",
                    "locked-dependencies",
                    "a command outside the closed list was refused",
                )
            if npm_result.start_error is not None:
                problems.append(
                    f"npm could not be started ({npm_result.start_error})",
                )
            elif npm_result.timed_out:
                problems.append(f"npm gave no answer within {t} s")
            elif npm_result.status == 0 and not npm_result.stderr:
                pass
            elif npm_result.status == 1:
                problems.append(
                    "npm ls reported a problem with web/package-lock.json "
                    "(exit status 1)",
                )
            else:
                problems.append(
                    f"npm output not understood (exit status {npm_result.status})",
                )

    if not problems:
        return store.Line(
            "PASS",
            "locked-dependencies",
            "uv.lock and web/package-lock.json match their manifests "
            "with network access disabled",
        )
    joined = "; ".join(problems)
    return store.Line("FAIL", "locked-dependencies", joined)
