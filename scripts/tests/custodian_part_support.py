"""Collection and manifest assertions for the custodian partition guards."""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

import runner_support as support


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


def nodeids(proc: subprocess.CompletedProcess[str]) -> list[str]:
    """Refuse failed collection and preserve duplicates for the count check."""
    if proc.returncode != 0:
        raise AssertionError(
            f"collection exit {proc.returncode}:\n{proc.stdout}{proc.stderr}"
        )
    return [
        line
        for line in proc.stdout.splitlines()
        if line.startswith("custodian/tests/") and "::" in line
    ]


def assert_partition(whole: Sequence[str], parts: Sequence[Sequence[str]]) -> None:
    """Prove no test id is lost, duplicated, or assigned to an empty part."""
    if len(parts) != 2 or any(not part for part in parts):
        raise AssertionError("both custodian parts must be nonempty")
    first, second = (set(part) for part in parts)
    if first & second:
        raise AssertionError("custodian parts overlap")
    if first | second != set(whole):
        raise AssertionError("custodian parts do not cover the whole collection")
    if sum(map(len, parts)) != len(whole):
        raise AssertionError("custodian part counts do not add up")
