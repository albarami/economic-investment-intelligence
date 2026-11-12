"""Helpers for lint, format and type-check guard tests."""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import unittest
from collections.abc import Mapping, Sequence
from pathlib import Path

TIMEOUT_SECONDS = 600

ROOT = Path(__file__).resolve().parents[2]


def tool(name: str) -> Path:
    """Return the path to a CLI tool in the active virtual environment."""
    exe = Path(sys.executable).parent / (
        name + ".exe" if sys.platform == "win32" else name
    )
    if not exe.is_file():
        raise AssertionError(f"FAIL tool-missing: {name}")
    return exe


def clean_env(home: Path) -> dict[str, str]:
    """Build an allow-listed environment for isolated tool runs."""
    return {
        "PATH": str(Path(sys.executable).parent),
        "HOME": str(home),
        "TMPDIR": str(home),
        "LANG": "C.UTF-8",
        "RUFF_CACHE_DIR": str(home / "ruff_cache"),
        "MYPY_CACHE_DIR": str(home / "mypy_cache"),
    }


def fresh_copy(case: unittest.TestCase) -> Path:
    """Copy workspace sources into a temporary tree for planted violations."""
    tmp = Path(
        __import__("tempfile").mkdtemp(prefix="pychecks-", dir=str(home_tmpdir()))
    )
    case.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
    shutil.copy2(ROOT / "pyproject.toml", tmp / "pyproject.toml")
    for folder in ("scripts", "core", "custodian", "product"):
        shutil.copytree(
            ROOT / folder,
            tmp / folder,
            ignore=shutil.ignore_patterns(
                "__pycache__",
                ".mypy_cache",
                ".ruff_cache",
                "*.egg-info",
                "dist",
                "build",
            ),
        )
    return tmp


def home_tmpdir() -> Path:
    """Return the workspace temporary root."""
    base = ROOT / ".overnight" / "tmp"
    base.mkdir(parents=True, exist_ok=True)
    return base


def write_files(root: Path, files: Mapping[str, str]) -> None:
    """Write relative paths under ``root``."""
    for rel, text in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


def run(
    args: Sequence[str | Path],
    cwd: Path,
    env: Mapping[str, str],
) -> subprocess.CompletedProcess[str]:
    """Run a subprocess with captured output."""
    return subprocess.run(
        [str(a) for a in args],
        cwd=cwd,
        env=dict(env),
        capture_output=True,
        text=True,
        timeout=TIMEOUT_SECONDS,
        check=False,
    )


_CONCISE = re.compile(r"^([^:]+):(\d+):\d+: (\S+)")


def ruff_findings(text: str) -> list[tuple[str, int, str]]:
    """Parse ruff concise output into sorted (path, line, code) tuples."""
    out: list[tuple[str, int, str]] = []
    for line in text.splitlines():
        match = _CONCISE.match(line.strip())
        if match:
            out.append((match.group(1), int(match.group(2)), match.group(3)))
    return sorted(out)


_MYPY = re.compile(r"^([^:]+):(\d+): error: .+  \[(\S+)\]$")


def mypy_findings(text: str) -> list[tuple[str, int, str]]:
    """Parse mypy error lines into sorted (path, line, code) tuples."""
    out: list[tuple[str, int, str]] = []
    for line in text.splitlines():
        match = _MYPY.match(line.strip())
        if match:
            out.append((match.group(1), int(match.group(2)), match.group(3)))
    return sorted(out)


_FMT = re.compile(r"^([^:]+):\d+:\d+: unformatted:")


def format_paths(text: str) -> list[str]:
    """Parse ruff format --check concise output into sorted paths."""
    paths = [
        m.group(1) for line in text.splitlines() if (m := _FMT.match(line.strip()))
    ]
    return sorted(paths)
