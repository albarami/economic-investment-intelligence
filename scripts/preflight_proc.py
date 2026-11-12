"""Child process runner and closed command table for preflight probes."""

from __future__ import annotations

import errno
import os
import re
import shutil
import signal
import subprocess
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

PROBE_TIMEOUT_S = 5.0
PG_ISREADY_WAIT = "5"
HOST = "<host>"
PORT = "<port>"
INTERPRETER = Path(sys.executable).name
SANDBOX_CHECK = "scripts/sandbox_check.py"
CHECK_QUERY = (
    "SELECT current_setting('server_version_num'), "
    "coalesce((SELECT extversion FROM pg_extension WHERE extname = 'postgis'), '')"
)
COMMANDS = (
    ("pg_isready", ("-h", HOST, "-p", PORT, "-t", PG_ISREADY_WAIT)),
    ("psql", ("-X", "-w", "-q", "-t", "-A", "-F", "|", "-c", CHECK_QUERY)),
    ("docker", ("info", "--format", "{{.ServerVersion}}")),
    ("git", ("ls-files", "--error-unmatch", ".env")),
    ("cmd.exe", ("/c", "ver")),
    ("uv", ("lock", "--check", "--offline")),
    ("npm", ("ls", "--package-lock-only", "--offline", "--logs-max=0")),
    (INTERPRETER, (SANDBOX_CHECK, "check-extensions")),
    (INTERPRETER, (SANDBOX_CHECK, "check")),
)
FIXED_ENV = {"LANG": "C", "LC_ALL": "C"}
PASS_THROUGH = {
    "pg_isready": ("PATH",),
    "psql": ("PATH",),
    "docker": (
        "PATH",
        "HOME",
        "WSL_DISTRO_NAME",
        "DOCKER_HOST",
        "DOCKER_CONTEXT",
        "DOCKER_CONFIG",
    ),
    "git": ("PATH",),
    "cmd.exe": ("PATH",),
    "uv": ("PATH",),
    "npm": ("PATH",),
    INTERPRETER: ("PATH",),
}

_PORT_RE = re.compile(r"^[1-9][0-9]{0,4}$")


class CommandRefused(ValueError):
    """A command is not on the closed list."""


@dataclass(frozen=True)
class ChildResult:
    """Outcome of one child process."""

    status: int | None
    stdout: str
    stderr: str
    timed_out: bool
    start_error: str | None


def command_allowed(name: str, args: Sequence[str]) -> bool:
    """Return whether the program and arguments match the closed command table."""
    base = Path(name).name
    for prog, template in COMMANDS:
        if prog != base:
            continue
        if len(args) != len(template):
            continue
        ok = True
        for arg, slot in zip(args, template, strict=True):
            if slot is HOST:
                if not arg or any(str.isspace(ch) for ch in arg) or arg.startswith("-"):
                    ok = False
                    break
            elif slot is PORT:
                if not _PORT_RE.fullmatch(arg):
                    ok = False
                    break
                if int(arg) > 65535:
                    ok = False
                    break
            elif arg != slot:
                ok = False
                break
        if ok:
            return True
    return False


def find_program(name: str, environ: Mapping[str, str]) -> str | None:
    """Locate a program on PATH."""
    found = shutil.which(name, path=environ.get("PATH", ""))
    if found is None:
        return None
    return os.path.abspath(found)


def child_env(
    name: str,
    environ: Mapping[str, str],
    extra: Mapping[str, str],
) -> dict[str, str]:
    """Build the environment passed to a closed-list child."""
    out: dict[str, str] = {}
    for key in PASS_THROUGH[name]:
        if key in environ:
            out[key] = environ[key]
    out.update(FIXED_ENV)
    out.update(extra)
    return out


def _kill_group(pid: int) -> None:
    try:
        os.killpg(pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass


def run_child(
    program: str,
    args: Sequence[str],
    env: Mapping[str, str],
    cwd: Path,
    *,
    limit: float = PROBE_TIMEOUT_S,
) -> ChildResult:
    """Run one allowed child with a time limit and process-group kill."""
    name = Path(program).name
    if not command_allowed(name, args):
        msg = f"command refused: {name}"
        raise CommandRefused(msg)
    try:
        proc = subprocess.Popen(
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
        code = errno.errorcode.get(exc.errno) if exc.errno is not None else None
        start_error = code if code is not None else type(exc).__name__
        return ChildResult(None, "", "", False, start_error)
    timed_out = False
    try:
        stdout_b, stderr_b = proc.communicate(timeout=limit)
    except subprocess.TimeoutExpired:
        timed_out = True
        _kill_group(proc.pid)
        stdout_b, stderr_b = proc.communicate()
    stdout = stdout_b.decode("utf-8", errors="replace")
    stderr = stderr_b.decode("utf-8", errors="replace")
    return ChildResult(proc.returncode, stdout, stderr, timed_out, None)
