"""Collection and manifest assertions for the suite partition guards."""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

import runner_support as support

_EVERY = {2: "both", 5: "all five"}


def collect(root: Path, args: Sequence[str]) -> subprocess.CompletedProcess[str]:
    """Use the runner's Python flags and the suite's arguments, collecting only."""
    return subprocess.run(
        [
            sys.executable,
            "-P",
            "-s",
            "-m",
            "pytest",
            "-c",
            "pyproject.toml",
            "--rootdir",
            ".",
            "--hypothesis-seed",
            support.FIXTURE_SEED,
            *args,
            "--collect-only",
            "-q",
        ],
        cwd=root,
        env=support.parent_env({"PYTHONDONTWRITEBYTECODE": "1"}),
        capture_output=True,
        text=True,
        timeout=120,
    )


def nodeids(
    proc: subprocess.CompletedProcess[str], prefix: str = "custodian/tests/"
) -> list[str]:
    """Refuse failed collection and preserve duplicates for the count check."""
    if proc.returncode != 0:
        raise AssertionError(
            f"collection exit {proc.returncode}:\n{proc.stdout}{proc.stderr}"
        )
    return [
        line
        for line in proc.stdout.splitlines()
        if line.startswith(prefix) and "::" in line
    ]


def assert_modules_collected(
    whole: Sequence[str], modules: Sequence[str], suite: str = "custodian"
) -> None:
    """Refuse a file missing even from the unsplit collection."""
    if {node.split("::", 1)[0] for node in whole} != set(modules):
        raise AssertionError(f"{suite} collection differs from test files")


def assert_partition(
    whole: Sequence[str],
    parts: Sequence[Sequence[str]],
    suite: str = "custodian",
    count: int = 5,
) -> None:
    """Prove exact test coverage and whole-module ownership in nonempty parts."""
    if len(parts) != count or any(not part for part in parts):
        raise AssertionError(f"{_EVERY[count]} {suite} parts must be nonempty")
    seen: set[str] = set()
    modules: set[str] = set()
    for part in parts:
        selected = set(part)
        if seen & selected:
            raise AssertionError(f"{suite} parts overlap")
        selected_modules = {node.split("::", 1)[0] for node in selected}
        if modules & selected_modules:
            raise AssertionError(f"{suite} module belongs to multiple parts")
        modules.update(selected_modules)
        seen.update(selected)
    if seen != set(whole):
        raise AssertionError(f"{suite} parts do not cover the whole collection")
    if sum(map(len, parts)) != len(whole):
        raise AssertionError(f"{suite} part counts do not add up")
