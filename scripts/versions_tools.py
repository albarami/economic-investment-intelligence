"""Probes of uv, node, npm and the running interpreter."""

from __future__ import annotations

import re
import shutil
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path

import versions_record

PROBE_TIMEOUT = 20.0
Failure = tuple[str, str, str]

_UV_OUT = re.compile(r"uv (\d+\.\d+\.\d+)( \(.*\))?", re.ASCII)
_NODE_OUT = re.compile(r"v(\d+\.\d+\.\d+)", re.ASCII)
_NPM_OUT = re.compile(r"(\d+\.\d+\.\d+)", re.ASCII)
_PATTERNS = {"uv": _UV_OUT, "node": _NODE_OUT, "npm": _NPM_OUT}


def probe_environment(environ: Mapping[str, str]) -> dict[str, str]:
    """Return the allow-list for a toolchain child process."""
    child = {"LANG": "C", "UV_NO_CONFIG": "1"}
    if "PATH" in environ:
        child["PATH"] = environ["PATH"]
    return child


def probe_version(
    tool: str,
    environ: Mapping[str, str],
    root: Path,
    timeout: float,
) -> tuple[str | None, str | None]:
    """Return the probed version, or a toolchain error detail."""
    child = probe_environment(environ)
    found = shutil.which(tool, path=child.get("PATH", ""))
    if found is None:
        return None, "not found on PATH"
    try:
        done = subprocess.run(
            [found, "--version"],
            cwd=root,
            env=child,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return None, f"timed out after {timeout:g} s"
    except OSError as exc:
        return None, f"could not run ({type(exc).__name__})"
    if done.returncode != 0:
        return None, f"exit status {done.returncode}"
    text = done.stdout.decode("utf-8", errors="replace")
    line = ""
    for candidate in text.splitlines():
        if candidate:
            line = candidate
            break
    match = _PATTERNS[tool].fullmatch(line)
    if match is None:
        return None, "version output not understood"
    return match.group(1), None


def check_toolchain(
    components: Sequence[versions_record.Component],
    interpreter: tuple[int, int, int],
    environ: Mapping[str, str],
    root: Path,
    timeout: float,
) -> list[Failure]:
    """Judge python, uv, node and npm, at most one line each."""
    rows = {item.name: item for item in components if item.kind == "toolchain"}
    failures: list[Failure] = []
    python = rows["python"]
    running = ".".join(str(part) for part in interpreter)
    if not versions_record.version_matches(python.pin, running):
        failures.append(
            ("toolchain", "python", f"running {running} is outside {python.pin}")
        )
    for tool in ("uv", "node", "npm"):
        row = rows[tool]
        version, detail = probe_version(tool, environ, root, timeout)
        if detail is not None or version is None:
            failures.append(
                ("toolchain", tool, detail or "version output not understood")
            )
            continue
        if not versions_record.version_matches(row.pin, version):
            failures.append(
                ("toolchain", tool, f"running {version} is outside {row.pin}")
            )
            continue
        if tool == "node" and row.floor is not None and _below(version, row.floor):
            failures.append(
                (
                    "toolchain",
                    "node",
                    f"running {version} is below the floor {row.floor}",
                )
            )
    return failures


def _below(version: str, floor: str) -> bool:
    got = tuple(int(part) for part in version.split("."))
    bound = tuple(int(part) for part in floor.split("."))
    return got < bound
