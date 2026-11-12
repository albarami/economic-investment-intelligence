"""Child environments, commands and process control for the test runner."""

from __future__ import annotations

import json
import os
import re
import shutil
import signal
import subprocess
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


class StartError(Exception):
    """A suite command could not be built or the process could not be started."""


class SuiteCommand(Protocol):
    """Fields of a suite the command builder reads."""

    @property
    def kind(self) -> str: ...

    @property
    def cwd(self) -> str: ...

    @property
    def args(self) -> tuple[str, ...]: ...


SECRET_SUFFIXES = ("_KEY", "_TOKEN", "_SECRET")
SECRET_MIN_LENGTH = 8
OUTPUT_TAIL_LINES = 200
REDACTED = "[redacted]"
KINDS = ("pytest", "node", "vitest")
RESULT_FILES = {
    "pytest": "result.xml",
    "node": "records.jsonl",
    "vitest": "result.json",
}
PYTHON_PASS_THROUGH = (
    "PATH",
    "HOME",
    "LANG",
    "LC_ALL",
    "TMPDIR",
    "XDG_DATA_HOME",
    "UV_PYTHON_INSTALL_DIR",
)


@dataclass(frozen=True)
class Launched:
    """Combined output of one child, its status, and whether it timed out."""

    status: int | None
    output: str
    timed_out: bool


def is_secret_name(name: str) -> bool:
    """Return whether a variable name ends with a secret suffix."""
    upper = name.upper()
    return any(upper.endswith(suffix) for suffix in SECRET_SUFFIXES)


def child_env(
    kind: str, parent: Mapping[str, str], seed: int, tmp: Path
) -> dict[str, str]:
    """Build an allow-list environment for one suite kind."""
    if kind not in KINDS:
        raise ValueError(f"unknown suite kind: {kind}")
    env: dict[str, str] = {}
    if kind == "pytest":
        for name in PYTHON_PASS_THROUGH:
            if name in parent:
                env[name] = parent[name]
        env["PYTHONHASHSEED"] = str(seed)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env["EII_DECISION_PROVIDER"] = "none"
        env["NO_COLOR"] = "1"
        env["HYPOTHESIS_STORAGE_DIRECTORY"] = str(tmp / "hypothesis")
        return env
    if "PATH" in parent:
        env["PATH"] = parent["PATH"]
    env["HOME"] = str(tmp)
    env["TMPDIR"] = str(tmp)
    env["LANG"] = "C"
    env["NO_COLOR"] = "1"
    env["EII_DECISION_PROVIDER"] = "none"
    return env


def build_command(
    suite: SuiteCommand,
    root: Path,
    env: Mapping[str, str],
    tmp: Path,
    seed: int,
) -> list[str]:
    """Build the argument list for one suite, or raise StartError."""
    cwd = root / suite.cwd
    if not cwd.is_dir():
        raise StartError(f"working folder {suite.cwd} does not exist")
    if suite.kind == "pytest":
        return [
            sys.executable,
            "-P",
            "-s",
            "-m",
            "pytest",
            "-c",
            "pyproject.toml",
            "--rootdir",
            ".",
            "--junit-xml",
            str(tmp / RESULT_FILES["pytest"]),
            "--hypothesis-seed",
            str(seed),
            *suite.args,
        ]
    node = _node_binary(env)
    if suite.kind == "node":
        reporter = (root / "web" / "scripts" / "count-reporter.mjs").as_uri()
        return [
            node,
            "--test",
            "--test-reporter=spec",
            "--test-reporter-destination=stdout",
            f"--test-reporter={reporter}",
            f"--test-reporter-destination={tmp / RESULT_FILES['node']}",
            *suite.args,
        ]
    binary = _vitest_binary(root)
    return [
        node,
        binary,
        "run",
        "--config",
        "vitest.config.ts",
        "--reporter=default",
        "--reporter=json",
        f"--outputFile.json={tmp / RESULT_FILES['vitest']}",
        "--sequence.shuffle.tests",
        f"--sequence.seed={seed}",
        *suite.args,
    ]


def launch(
    cmd: Sequence[str], cwd: Path, env: Mapping[str, str], timeout: int
) -> Launched:
    """Start a child in its own session and return its combined output."""
    try:
        proc = subprocess.Popen(
            list(cmd),
            cwd=cwd,
            env=dict(env),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            start_new_session=True,
        )
    except OSError as error:
        raise StartError(
            f"could not start the process ({type(error).__name__})"
        ) from error
    try:
        try:
            output, _unused = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            output, _unused = proc.communicate()
            return Launched(proc.returncode, output, True)
        return Launched(proc.returncode, output, False)
    except BaseException:
        os.killpg(proc.pid, signal.SIGKILL)
        proc.communicate()
        raise


def redact(text: str, secrets: Mapping[str, str]) -> tuple[str, list[str]]:
    """Replace secret values found in text and name every variable that matched."""
    found = sorted(name for name, value in secrets.items() if value in text)
    if not found:
        return text, []
    values = sorted(
        {secrets[name] for name in found}, key=lambda item: (-len(item), item)
    )
    pattern = "|".join(re.escape(value) for value in values)
    return re.sub(pattern, REDACTED, text), found


def tail(text: str) -> list[str]:
    """Return the last lines of combined output for an output block."""
    return text.splitlines()[-OUTPUT_TAIL_LINES:]


def _node_binary(env: Mapping[str, str]) -> str:
    found = shutil.which("node", path=env.get("PATH", ""))
    if not found:
        raise StartError("node not found on PATH")
    return found


def _vitest_binary(root: Path) -> str:
    package = root / "web" / "node_modules" / "vitest"
    manifest = package / "package.json"
    if not manifest.is_file():
        raise StartError("vitest is not installed (run npm ci in web/)")
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise StartError(
            "node_modules/vitest/package.json is not valid JSON"
        ) from error
    bin_field = data.get("bin") if isinstance(data, dict) else None
    relative: str | None = None
    if isinstance(bin_field, str):
        relative = bin_field
    elif isinstance(bin_field, dict) and isinstance(bin_field.get("vitest"), str):
        relative = bin_field["vitest"]
    if relative is None:
        raise StartError(
            "node_modules/vitest/package.json has no bin entry named vitest"
        )
    joined = os.path.normpath(os.path.join(package, relative))
    if not os.path.isfile(joined):
        shown = os.path.relpath(joined, root)
        raise StartError(f"vitest binary not found: {shown}")
    return joined
