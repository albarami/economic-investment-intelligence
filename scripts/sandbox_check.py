"""Proofs of the generator sandbox: bubblewrap and the engine extensions.

``check_bubblewrap`` and ``check_extensions`` are the entry points of the
preflight rows for bubblewrap and for DuckDB extensions. The command line of
this module is ``check`` and ``check-extensions``. Every program they start is
judged by ``output_problems``: exit status 0, nothing on standard error and
exactly the expected lines, each once and in order.
"""

from __future__ import annotations

import dataclasses
import json
import os
import re
import socket
import subprocess
import sys
import tempfile
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path

import extension_tree
import sandbox_launch as launch
import sandbox_profiles as tables

ROOT = launch.ROOT
EXTENSIONS_DEFAULT = Path("data") / "engine_extensions"
PROBE = Path("scripts") / "sandbox_inside" / "sentinel_probe.py"
EXTENSION_CHECK = Path("scripts") / "sandbox_inside" / "extension_check.py"
BANNED_PORTS = (55432, 18710, 18711)
EXIT_USAGE = 2
MAX_BIND_TRIES = 20
# Room for every connection one check makes when a planted fault lets it through.
LISTEN_BACKLOG = 16
INSIDE_LINES = {
    "read_outside": "error FileNotFoundError ENOENT",
    "tcp_loopback": "error ConnectionRefusedError ECONNREFUSED",
    "unix_abstract": "error ConnectionRefusedError ECONNREFUSED",
}
VERSION_LINE = re.compile(r"bubblewrap [0-9]+\.[0-9]+\.[0-9]+")
LOAD_LINES = (
    f"engine duckdb {extension_tree.ENGINE}",
    "settings autoinstall_known_extensions=False autoload_known_extensions=False "
    "allow_unsigned_extensions=False",
    "LOAD spatial ok",
    "LOAD h3 ok",
    "PATH h3 inside",
    "PATH spatial inside",
    "USE POINT (1 2) 8858e06829fffff",
    "LOCK autoinstall error InvalidInputException locked",
)
Expected = str | re.Pattern[str]


def _shown(line: Expected) -> str:
    """Show an expected line; a pattern is shown as its text."""
    return line.pattern if isinstance(line, re.Pattern) else line


def _matches(line: str, want: Expected) -> bool:
    """Tell whether one printed line is the expected one."""
    if isinstance(want, re.Pattern):
        return want.fullmatch(line) is not None
    return line == want


def exit_problems(what: str, returncode: int, stderr: str) -> list[str]:
    """Judge how a started program ended: exit status 0 and nothing on standard error.

    Args:
        what: The name of the run, used in the problem texts.
        returncode: Its exit status.
        stderr: Its standard error.

    Returns:
        One problem text per broken rule; empty when both hold.
    """
    problems = []
    if returncode != 0:
        problems.append(f"{what}: exit status {returncode}, expected 0")
    if stderr:
        problems.append(f"{what}: standard error is not empty: {stderr!r}")
    return problems


def output_problems(
    what: str,
    returncode: int,
    stdout: str,
    stderr: str,
    expected: Sequence[Expected],
) -> list[str]:
    """Judge what a started program did, exactly.

    Args:
        what: The name of the run, used in the problem texts.
        returncode: Its exit status.
        stdout: Its standard output.
        stderr: Its standard error.
        expected: The lines standard output must hold, each once and in this
            order; a string must be equal, a pattern must match the whole line.

    Returns:
        One problem text per broken rule (status not 0, standard error not
        empty, standard output not exactly the lines, each ended by a newline);
        empty when the run is as expected.
    """
    problems = exit_problems(what, returncode, stderr)
    lines = stdout.split("\n")
    complete = lines[-1] == ""
    got = lines[:-1] if complete else lines
    same = (
        complete
        and len(got) == len(expected)
        and all(_matches(line, want) for line, want in zip(got, expected, strict=False))
    )
    shown = [_shown(want) for want in expected]
    if not complete:
        problems.append(
            f"{what}: standard output {stdout!r} does not end with a newline, "
            f"expected {shown!r}"
        )
    elif not same:
        problems.append(f"{what}: standard output {got!r}, expected {shown!r}")
    return problems


def _bind_tcp() -> socket.socket:
    """Bind a TCP socket on the loopback interface, on a port the system chooses.

    Raises:
        SandboxError: Every try gave one of ``BANNED_PORTS``.
    """
    for _ in range(MAX_BIND_TRIES):
        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        if sock.getsockname()[1] not in BANNED_PORTS:
            return sock
        sock.close()
    raise launch.SandboxError("could not bind a loopback port outside the banned ports")


@contextmanager
def listeners() -> Iterator[tuple[int, str]]:
    """Open the test listeners on the loopback interface of this machine.

    Yields:
        The TCP port the operating system chose (never one of ``BANNED_PORTS``) and
        the name of an abstract Unix socket that is listening.
    """
    name = "eii-sandbox-" + os.urandom(6).hex()
    tcp = _bind_tcp()
    try:
        tcp.listen(LISTEN_BACKLOG)
        with socket.socket(socket.AF_UNIX) as unix:
            unix.bind("\0" + name)
            unix.listen(LISTEN_BACKLOG)
            yield tcp.getsockname()[1], name
    finally:
        tcp.close()


def probe_config(base: Path, port: int, abstract: str) -> str:
    """Return the probe configuration for the folders made by ``make_folders``."""
    return json.dumps(
        {
            "sentinel": str(base / "outside" / "sentinel.txt"),
            "outside_dir": str(base / "outside"),
            "cache_dir": str(base / "cache"),
            "vault_dir": str(base / "vault"),
            "staging_dir": str(base / "staging"),
            "hidden": [],
            "port": port,
            "abstract": abstract,
        }
    )


def make_folders(base: Path, profile: tables.Profile) -> launch.Layout:
    """Create the fixture folders of a check under ``base`` and return the layout.

    Args:
        base: An empty folder.
        profile: The profile the layout is for; a staging folder and a fixture
            scenario file are given exactly when the profile declares them.
    """
    for name in ("outside", "cache", "vault", "staging", "extensions"):
        (base / name).mkdir(exist_ok=True)
    (base / "outside" / "sentinel.txt").write_text("sentinel\n", encoding="utf-8")
    (base / "cache" / "ok.txt").write_text("cache\n", encoding="utf-8")
    scenario = base / "scenario.bin"
    scenario.write_bytes(b"scenario\n")
    return launch.Layout(
        ROOT,
        base / "cache",
        base / "vault",
        base / "extensions",
        base / "staging" if profile.staging else None,
        scenario if profile.scenario else None,
    )


def version_problems() -> list[str]:
    """Run ``bwrap --version`` and judge it: one line ``bubblewrap X.Y.Z``."""
    try:
        done = subprocess.run(
            [tables.BWRAP, "--version"],
            env={},
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as error:
        return [f"bwrap --version: not available ({type(error).__name__})"]
    return output_problems(
        "bwrap --version", done.returncode, done.stdout, done.stderr, [VERSION_LINE]
    )


def check_bubblewrap() -> list[str]:
    """Prove both profiles: the outside tooth, then the sentinel read and the network.

    Returns:
        One problem text per failure; empty when ``bwrap --version`` prints its
        version line, the probe outside the sandbox succeeds in each attempt and
        both profiles block each attempt, every run exactly as expected.
    """
    problems = version_problems()
    attempts = list(INSIDE_LINES)
    with tempfile.TemporaryDirectory() as tmp, listeners() as (port, abstract):
        base = Path(tmp).resolve()
        make_folders(base, tables.PROFILES[0])
        config = probe_config(base, port, abstract)
        probe = str(ROOT / PROBE)
        outside = subprocess.run(
            [sys.executable, "-I", "-B", probe, config, *attempts],
            env={},
            capture_output=True,
            text=True,
            check=False,
        )
        problems += output_problems(
            "outside the sandbox",
            outside.returncode,
            outside.stdout,
            outside.stderr,
            [f"{attempt} ok" for attempt in attempts],
        )
        for profile in tables.PROFILES:
            layout = make_folders(base, profile)
            try:
                result = launch.run_in_sandbox(
                    profile.name,
                    layout,
                    launch.python_command(probe, config, *attempts),
                )
            except launch.SandboxError as error:
                problems.append(f"profile {profile.name}: {error}")
                continue
            problems += output_problems(
                f"profile {profile.name}",
                result.returncode,
                result.stdout,
                result.stderr,
                [f"{attempt} {want}" for attempt, want in INSIDE_LINES.items()],
            )
    return problems


def check_extensions(extensions: Path | None = None) -> list[str]:
    """Load spatial and h3 inside the build-world profile, with the network off.

    Args:
        extensions: The extension folder; ``data/engine_extensions`` when None.

    Returns:
        One problem text per failure; empty when the loader printed exactly the
        expected lines, with exit status 0 and nothing on standard error.
    """
    folder = extensions if extensions is not None else ROOT / EXTENSIONS_DEFAULT
    if not folder.is_dir():
        return [
            f"extension folder {EXTENSIONS_DEFAULT} is missing: run "
            "'uv run --locked python scripts/engine_extensions.py fetch'"
        ]
    with tempfile.TemporaryDirectory() as tmp:
        made = make_folders(Path(tmp).resolve(), launch.profile_named("build-world"))
        layout = dataclasses.replace(made, extensions=folder)
        try:
            result = launch.run_in_sandbox(
                "build-world",
                layout,
                launch.python_command(str(ROOT / EXTENSION_CHECK), str(folder), "load"),
            )
        except launch.SandboxError as error:
            return [f"build-world: {error}"]
    return output_problems(
        "build-world", result.returncode, result.stdout, result.stderr, LOAD_LINES
    )


def bubblewrap_version() -> str:
    """Return the version line of bubblewrap for a report, or a short reason."""
    try:
        done = subprocess.run(
            [tables.BWRAP, "--version"],
            env={},
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as error:
        return f"bubblewrap: not available ({type(error).__name__})"
    return done.stdout.strip() or "bubblewrap: version not printed"


def main(argv: Sequence[str]) -> int:
    """Run ``check`` or ``check-extensions``.

    Args:
        argv: The arguments after the program name.

    Returns:
        0 when no problem was found, 1 when one was, 2 for a usage error.
    """
    if list(argv) not in (["check"], ["check-extensions"]):
        print("sandbox_check: usage: check | check-extensions", file=sys.stderr)
        return EXIT_USAGE
    if argv[0] == "check":
        print(bubblewrap_version())
        problems = check_bubblewrap()
    else:
        problems = check_extensions()
    for problem in problems:
        print(f"FAIL {problem}")
    print("sandbox: FAILED" if problems else "sandbox: OK")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
