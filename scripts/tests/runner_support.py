"""Helpers for the test-runner guard tests."""

from __future__ import annotations

import io
import os
import shutil
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import run_tests

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
FIXTURE_SEED = "1794000000"


def fixture_root(tmp: Path) -> Path:
    """Copy runner inputs into a temporary repository and link the web install."""
    shutil.copy2(ROOT / "pyproject.toml", tmp / "pyproject.toml")
    shutil.copy2(ROOT / "conftest.py", tmp / "conftest.py")
    scripts = tmp / "web" / "scripts"
    scripts.mkdir(parents=True)
    shutil.copy2(
        ROOT / "web" / "scripts" / "count-reporter.mjs",
        scripts / "count-reporter.mjs",
    )
    shutil.copy2(ROOT / "web" / "vitest.config.ts", tmp / "web" / "vitest.config.ts")
    for rel in (
        "scripts",
        "scripts/tests",
        "core/src",
        "custodian/src",
        "product/src",
    ):
        (tmp / rel).mkdir(parents=True, exist_ok=True)
    link = tmp / "web" / "node_modules"
    link.symlink_to(ROOT / "web" / "node_modules", target_is_directory=True)
    return tmp


def put(root: Path, relpath: str, text: str) -> None:
    """Write a text file under a fixture root, creating parent folders."""
    path = root / relpath
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def parent_env(extra: Mapping[str, str] | None = None) -> dict[str, str]:
    """Copy PATH, HOME, LANG and TMPDIR, then apply extras."""
    env: dict[str, str] = {}
    for name in ("PATH", "HOME", "LANG", "TMPDIR"):
        if name in os.environ:
            env[name] = os.environ[name]
    if extra:
        env.update(extra)
    return env


def call(
    argv: Sequence[str],
    suites: Sequence[run_tests.Suite],
    root: Path,
    environ: Mapping[str, str],
    now: Callable[[], float] = time.time,
) -> tuple[int, list[str], list[str]]:
    """Run the runner in memory and return status, stdout lines and stderr lines."""
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    import run_tests

    out = io.StringIO()
    err = io.StringIO()
    status = run_tests.main(
        argv,
        suites=suites,
        root=root,
        environ=environ,
        out=out,
        err=err,
        now=now,
    )
    return status, out.getvalue().splitlines(), err.getvalue().splitlines()


def visible(lines: list[str]) -> list[str]:
    """Drop output blocks, including their header and footer lines."""
    kept: list[str] = []
    skipping = False
    for line in lines:
        if line.startswith("--- output of "):
            skipping = True
            continue
        if skipping:
            if line.startswith("--- end of output of "):
                skipping = False
            continue
        kept.append(line)
    return kept


def fx_suite(
    name: str,
    kind: str,
    cwd: str,
    args: tuple[str, ...],
    timeout: int = 120,
) -> run_tests.Suite:
    """Build one fixture suite."""
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    import run_tests

    return run_tests.Suite(name, kind, cwd, args, timeout)
