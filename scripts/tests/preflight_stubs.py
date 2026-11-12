"""Stub programs and helpers for preflight tests (not collected)."""

from __future__ import annotations

import json
import os
import secrets
import socket
import subprocess
import sys
import textwrap
from pathlib import Path
from typing import Any

import preflight_rows as rows
import preflight_store as store
import sandbox_check

# The canonical list lives in scripts/sandbox_check.py.
BANNED_PORTS = sandbox_check.BANNED_PORTS


def write_stub(
    folder: Path,
    name: str,
    *,
    status: int = 0,
    stdout: str = "",
    stderr: str = "",
    sleep: float = 0.0,
    echo: bool = False,
    connect: bool = False,
    grandchild: bool = False,
    pid_file: Path | None = None,
) -> Path:
    """Write an executable Python stub program."""
    path = folder / name
    body = textwrap.dedent(
        f"""
        import json
        import os
        import socket
        import subprocess
        import sys
        import time
        from pathlib import Path

        STATUS = {status!r}
        STDOUT = {stdout!r}
        STDERR = {stderr!r}
        SLEEP = {sleep!r}
        ECHO = {echo!r}
        CONNECT = {connect!r}
        GRANDCHILD = {grandchild!r}
        CALLS = Path({str(folder / "calls.jsonl")!r})
        PID_FILE = {None if pid_file is None else repr(str(pid_file))}

        raw = open("/proc/self/environ", "rb").read().decode("utf-8", "replace")
        env = dict(x.split("=", 1) for x in raw.split("\\0") if "=" in x)
        rec = {{
            "program": Path(sys.argv[0]).name,
            "argv": sys.argv,
            "env": env,
            "cwd": os.getcwd(),
            "stdin": "",
        }}
        with CALLS.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(rec) + "\\n")
        if ECHO:
            payload = json.dumps({{"argv": sys.argv, "env": env}})
            sys.stdout.write(payload)
            sys.stderr.write(payload)
            sys.stdout.flush()
            sys.stderr.flush()
        if CONNECT:
            host = port = None
            for idx, arg in enumerate(sys.argv):
                if arg == "-h" and idx + 1 < len(sys.argv):
                    host = sys.argv[idx + 1]
                if arg == "-p" and idx + 1 < len(sys.argv):
                    port = int(sys.argv[idx + 1])
            conn = socket.create_connection((host, port))
            conn.recv(1)
            conn.close()
        if GRANDCHILD:
            proc = subprocess.Popen(
                [sys.executable, "-c", "import time; time.sleep(60)"],
            )
            if PID_FILE:
                Path(PID_FILE).write_text(str(proc.pid), encoding="utf-8")
        sys.stdout.write(STDOUT)
        sys.stderr.write(STDERR)
        sys.stdout.flush()
        sys.stderr.flush()
        if SLEEP:
            time.sleep(SLEEP)
        raise SystemExit(STATUS)
        """
    )
    text = "#!" + sys.executable + " -I\n" + body
    path.write_text(text, encoding="utf-8")
    path.chmod(path.stat().st_mode | 0o111)
    return path


def calls(folder: Path) -> list[dict[str, Any]]:
    """Read recorded stub calls."""
    log = folder / "calls.jsonl"
    if not log.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in log.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def dummy(prefix: str) -> str:
    """Build a secret-shaped token at run time."""
    return prefix + secrets.token_hex(16)


def fake_tools(*, failing: str = "") -> rows.ToolChecks:
    """Return deterministic deferred rows, with one optional planted failure."""

    def line(check: str, reason: str) -> store.Line:
        if check == failing:
            return store.Line("FAIL", check, "planted")
        return store.Line("PASS", check, reason)

    return rows.ToolChecks(
        python=lambda: line("python", "Python and uv match pins.toml"),
        node_npm=lambda: line("node-npm", "Node and npm match pins.toml"),
        extensions=lambda: line(
            "duckdb-extensions",
            "spatial and h3 load from the local folder with network access disabled",
        ),
        bubblewrap=lambda: line(
            "bubblewrap-sandbox",
            "bubblewrap is present and the sandbox test passes",
        ),
    )


def database_url(
    password: str | None,
    port: int,
    *,
    host: str = "127.0.0.1",
    user: str = "eii_app",
    database: str = "eii",
) -> str:
    """Build a postgresql URL with a dotted host."""
    at_host = "@" + host
    if password is None:
        return f"postgresql://{user}{at_host}:{port}/{database}"
    return f"postgresql://{user}:{password}{at_host}:{port}/{database}"


def untracked_repo(folder: Path) -> None:
    """Initialize a git repository in folder."""
    env = dict(os.environ)
    env["GIT_CONFIG_GLOBAL"] = os.devnull
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    subprocess.run(
        ["git", "init", "-q"],
        cwd=folder,
        env=env,
        check=True,
        capture_output=True,
    )


def loopback_socket(*, reuse: bool = False) -> socket.socket:
    """Bind TCP to 127.0.0.1 port 0, refusing banned ports."""
    for _ in range(50):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if reuse:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        if port in sandbox_check.BANNED_PORTS:
            sock.close()
            continue
        return sock
    msg = "could not bind loopback port outside banned set"
    raise AssertionError(msg)
