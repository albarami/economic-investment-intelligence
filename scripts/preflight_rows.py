"""Preflight row checks other than PostgreSQL store selection."""

from __future__ import annotations

import errno
import os
import re
import socket
from collections.abc import Mapping
from pathlib import Path

import preflight_proc as proc
import preflight_store as store

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
