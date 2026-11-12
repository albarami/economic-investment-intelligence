"""Sentinel probe of the generator sandbox (ARC-11, TST-61).

Usage: python -I -B sentinel_probe.py CONFIG_JSON ATTEMPT [ATTEMPT ...]

Each attempt prints one line, ``<id> <outcome>``. An outcome is ``ok`` or
``error <ExceptionClass> <errno name>``. The probe contacts no host but the
listeners that the caller opened on the loopback interface of this machine.
Exit status: 0 all attempts ran, 2 usage error (nothing is attempted).
"""

from __future__ import annotations

import errno
import json
import os
import socket
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

PROFILE_VARIABLE = "EII_SANDBOX_PROFILE"
EXIT_USAGE = 2
CONNECT_TIMEOUT = 2.0
UNROUTED_ADDRESS = ("192.0.2.1", 80)
UNKNOWN_NAME = "example.invalid"
LOOPBACK = "127.0.0.1"
# /proc is not mounted inside, so every number from 3 to 1023 is tried.
FD_RANGE = range(3, 1024)
ROOT_FILE = "/probe-write"
USR_FILE = "/usr/probe-write"
TMP_FILE = "/tmp/probe-write"
SCENARIO_FILE = "/scenario/scenario.bin"
CLEAN_FILE = "eii-probe-write"

Action = Callable[[], None]


def _read(path: str) -> Action:
    def action() -> None:
        with open(path, "rb") as handle:
            handle.read()

    return action


def _write(path: str) -> Action:
    def action() -> None:
        with open(path, "wb") as handle:
            handle.write(b"x")

    return action


def _write_clean(path: str) -> Action:
    """Write a file and delete it again, so a leak leaves nothing on the host."""

    def action() -> None:
        with open(path, "wb") as handle:
            handle.write(b"x")
        os.unlink(path)

    return action


def _tcp(host: str, port: int) -> Action:
    def action() -> None:
        with socket.socket() as sock:
            sock.settimeout(CONNECT_TIMEOUT)
            sock.connect((host, port))

    return action


def _abstract(name: str) -> Action:
    def action() -> None:
        with socket.socket(socket.AF_UNIX) as sock:
            sock.settimeout(CONNECT_TIMEOUT)
            sock.connect("\0" + name)

    return action


def _lookup(name: str) -> Action:
    def action() -> None:
        socket.getaddrinfo(name, 80)

    return action


def outcome(action: Action) -> str:
    """Run one attempt and describe how it ended.

    Args:
        action: The operation to try.

    Returns:
        ``ok``, or ``error`` followed by the exception class and the errno name
        (``none`` when the exception has no errno, the number when it has no name).
    """
    try:
        action()
    except OSError as error:
        code = (
            "none"
            if error.errno is None
            else errno.errorcode.get(error.errno, str(error.errno))
        )
        return f"error {type(error).__name__} {code}"
    except ImportError as error:
        return f"error {type(error).__name__} none"
    return "ok"


def open_descriptors() -> str:
    """List the open descriptors of ``FD_RANGE`` (above standard error), or ``none``."""
    found = []
    for number in FD_RANGE:
        try:
            os.fstat(number)
        except OSError:
            continue
        found.append(str(number))
    return ",".join(found) or "none"


def single_attempts(config: dict[str, Any]) -> dict[str, Action]:
    """Build the attempts that need one action each.

    Args:
        config: The decoded configuration; a key is read only when its attempt runs.

    Returns:
        Attempt id to action. Actions read their keys lazily.
    """

    def key(name: str) -> str:
        return str(config[name])

    return {
        "read_outside": lambda: _read(key("sentinel"))(),
        "write_outside": lambda: _write(str(Path(key("outside_dir")) / "w.txt"))(),
        "read_cache": lambda: _read(str(Path(key("cache_dir")) / "ok.txt"))(),
        "write_cache": lambda: _write(str(Path(key("cache_dir")) / "new.txt"))(),
        "write_vault": lambda: _write(str(Path(key("vault_dir")) / "v.txt"))(),
        "write_staging": lambda: _write(str(Path(key("staging_dir")) / "s.txt"))(),
        "write_root": _write(ROOT_FILE),
        "write_usr": _write(USR_FILE),
        "write_tmp": _write(TMP_FILE),
        "read_scenario": _read(SCENARIO_FILE),
        "write_scenario": _write(SCENARIO_FILE),
        "write_venv": lambda: _write_clean(str(Path(key("venv_dir")) / CLEAN_FILE))(),
        "write_code": lambda: _write_clean(str(Path(key("code_dir")) / CLEAN_FILE))(),
        "write_interpreter": lambda: _write_clean(
            str(Path(key("interpreter_dir")) / CLEAN_FILE)
        )(),
        "write_inside": lambda: _write_clean(
            str(Path(key("inside_dir")) / CLEAN_FILE)
        )(),
        "write_extensions": lambda: _write_clean(
            str(Path(key("extensions_dir")) / CLEAN_FILE)
        )(),
        "tcp_loopback": lambda: _tcp(LOOPBACK, int(config["port"]))(),
        "unix_abstract": lambda: _abstract(key("abstract"))(),
        "tcp_unrouted": _tcp(*UNROUTED_ADDRESS),
        "dns_lookup": _lookup(UNKNOWN_NAME),
    }


SPECIAL = ("profile", "env", "fds", "hidden")
WRITES = (
    "write_root",
    "write_usr",
    "write_tmp",
    "write_scenario",
    "write_venv",
    "write_code",
    "write_interpreter",
    "write_inside",
    "write_extensions",
)


def run_attempt(
    attempt: str, config: dict[str, Any], table: dict[str, Action]
) -> list[str]:
    """Run one attempt id.

    Args:
        attempt: A key of the table or one of ``SPECIAL``.
        config: The decoded configuration.
        table: The result of ``single_attempts``.

    Returns:
        The output lines of this attempt.
    """
    if attempt == "profile":
        return [f"profile {os.environ.get(PROFILE_VARIABLE, 'unset')}"]
    if attempt == "env":
        return ["env " + ",".join(sorted(os.environ))]
    if attempt == "fds":
        return [f"fds {open_descriptors()}"]
    if attempt == "hidden":
        return [
            f"hidden {index} {outcome(_read(str(path)))}"
            for index, path in enumerate(config["hidden"])
        ]
    return [f"{attempt} {outcome(table[attempt])}"]


def main(argv: list[str]) -> int:
    """Run the attempts named on the command line.

    Args:
        argv: Arguments after the program name.

    Returns:
        0, or ``EXIT_USAGE`` when the arguments are wrong (then nothing was attempted).
    """
    if len(argv) < 2:
        print(
            "sentinel_probe: usage: CONFIG_JSON ATTEMPT [ATTEMPT ...]", file=sys.stderr
        )
        return EXIT_USAGE
    try:
        config = json.loads(argv[0])
    except ValueError:
        print("sentinel_probe: config is not valid JSON", file=sys.stderr)
        return EXIT_USAGE
    table = single_attempts(config if isinstance(config, dict) else {})
    unknown = [name for name in argv[1:] if name not in table and name not in SPECIAL]
    if not isinstance(config, dict) or unknown:
        print(
            f"sentinel_probe: unknown attempt: {unknown[0] if unknown else 'config is not an object'}",
            file=sys.stderr,
        )
        return EXIT_USAGE
    if PROFILE_VARIABLE not in os.environ and any(name in WRITES for name in argv[1:]):
        print(
            "sentinel_probe: write attempts run only inside a sandbox profile",
            file=sys.stderr,
        )
        return EXIT_USAGE
    for attempt in argv[1:]:
        try:
            lines = run_attempt(attempt, config, table)
        except KeyError as error:
            print(
                f"sentinel_probe: config key missing: {error.args[0]}", file=sys.stderr
            )
            return EXIT_USAGE
        for line in lines:
            print(line, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
