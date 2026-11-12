"""Start and stop the Compose database service."""

from __future__ import annotations

import errno
import os
import signal
import stat
import subprocess
import sys
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

import preflight_database
import preflight_proc

from . import exits, table

COMPOSE_PROJECT = "eii-poc"
COMPOSE_FILE = "infra/compose.yaml"
SECRET_RELATIVE = Path("data/compose/postgres_superuser_password")
ENV_FILE_NAME = "port.env"
ENV_SLOT = "<env-file>"
WAIT_TIMEOUT = "60"
UP_LIMIT_S = 90
DOWN_LIMIT_S = 60
MISSING_DOCKER = "docker: not found on PATH"
MISSING_SECRET = (
    "the Compose secret file is missing "
    "(data/compose/postgres_superuser_password); create it first"
)
_PASS = {
    "db-up": "database service started",
    "db-down": "database service stopped",
}


@dataclass(frozen=True)
class ComposeForm:
    """One closed Compose argument list."""

    name: str
    args: tuple[str, ...]
    limit_s: int
    command: str


FORMS: tuple[ComposeForm, ...] = (
    ComposeForm(
        "up",
        (
            "compose",
            "-p",
            COMPOSE_PROJECT,
            "-f",
            COMPOSE_FILE,
            "--env-file",
            ENV_SLOT,
            "up",
            "-d",
            "--wait",
            "--wait-timeout",
            WAIT_TIMEOUT,
            "db",
        ),
        UP_LIMIT_S,
        "db-up",
    ),
    ComposeForm(
        "stop",
        (
            "compose",
            "-p",
            COMPOSE_PROJECT,
            "-f",
            COMPOSE_FILE,
            "--env-file",
            ENV_SLOT,
            "stop",
            "db",
        ),
        DOWN_LIMIT_S,
        "db-down",
    ),
)


@dataclass(frozen=True)
class ComposeResult:
    """Outcome of one Compose child."""

    status: int | None
    stdout: str
    stderr: str
    timed_out: bool
    start_error: str | None


def compose_argv(form: str, env_file: str) -> list[str]:
    """Build the argument list for one closed form."""
    for row in FORMS:
        if row.name == form:
            return [env_file if part == ENV_SLOT else part for part in row.args]
    msg = f"compose form refused: {form}"
    raise ValueError(msg)


def run(
    command: str,
    environ: Mapping[str, str],
    root: Path,
    args: Sequence[str],
) -> int:
    """Run db-up or db-down. Return 0, 1 or 2."""
    if args:
        table.write_usage()
        return 2
    try:
        line = preflight_database.compose_port_env(environ)
    except ValueError as exc:
        return exits.finish(1, command, str(exc))
    program = preflight_proc.find_program("docker", environ)
    if program is None:
        return exits.finish(1, command, MISSING_DOCKER)
    secret = root / SECRET_RELATIVE
    if not _is_regular(secret):
        return exits.finish(1, command, MISSING_SECRET)
    form = _form(command)
    with tempfile.TemporaryDirectory(prefix="eii-compose-") as raw:
        env_file = Path(raw) / ENV_FILE_NAME
        env_file.write_text(line, encoding="utf-8")
        argv = compose_argv(form.name, str(env_file))
        child_env = preflight_proc.child_env("docker", environ, {})
        result = _run(program, argv, child_env, root, float(form.limit_s))
    return _finish_run(command, result, form.limit_s)


def _form(command: str) -> ComposeForm:
    for row in FORMS:
        if row.command == command:
            return row
    raise KeyError(command)


def _is_regular(path: Path) -> bool:
    try:
        mode = path.lstat().st_mode
    except OSError:
        return False
    return stat.S_ISREG(mode)


def _finish_run(command: str, result: ComposeResult, limit_s: int) -> int:
    if result.start_error is not None:
        detail = f"docker could not be started ({result.start_error})"
        return exits.finish(1, command, detail)
    sys.stdout.write(result.stdout)
    sys.stdout.flush()
    sys.stderr.write(result.stderr)
    sys.stderr.flush()
    if result.timed_out:
        return exits.finish(1, command, f"timed out after {limit_s} s")
    if result.status == 0:
        print(f"PASS {command}: {_PASS[command]}")
        return exits.finish(0, command, "")
    shown = "none" if result.status is None else str(result.status)
    return exits.finish(1, command, f"compose exit status {shown}")


def _run(
    program: str,
    args: Sequence[str],
    env: Mapping[str, str],
    cwd: Path,
    limit: float,
) -> ComposeResult:
    try:
        child = subprocess.Popen(
            [program, *args],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=dict(env),
            cwd=cwd,
            start_new_session=True,
            close_fds=True,
        )
    except OSError as exc:
        return ComposeResult(None, "", "", False, _start_error(exc))
    timed_out = False
    try:
        stdout_b, stderr_b = child.communicate(timeout=limit)
    except subprocess.TimeoutExpired:
        timed_out = True
        _kill_group(child.pid)
        stdout_b, stderr_b = child.communicate()
    stdout = stdout_b.decode("utf-8", errors="replace")
    stderr = stderr_b.decode("utf-8", errors="replace")
    return ComposeResult(child.returncode, stdout, stderr, timed_out, None)


def _kill_group(pid: int) -> None:
    try:
        os.killpg(pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        return


def _start_error(exc: OSError) -> str:
    if exc.errno is None:
        return type(exc).__name__
    code = errno.errorcode.get(exc.errno)
    if code is None:
        return type(exc).__name__
    return code
