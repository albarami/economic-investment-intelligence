"""Closed planted violations for the S0-T07 CI harness."""

from __future__ import annotations

import random
import string
import subprocess
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

DOCS = "uv run --no-project python3 scripts/check_docs.py"
TREE = "uv run --no-project python3 scripts/check_tree.py"
VERSIONS = "uv run --locked python scripts/check_versions.py"
RUFF = "uv run --locked ruff check ."
FORMAT = "uv run --locked ruff format --check ."
MYPY = "uv run --locked mypy"
WEB_LINT = "npm run lint"
WEB_FORMAT = "npm run format:check"
WEB_TYPES = "npm run typecheck"
SCAN = "uv run --locked python scripts/ci_history_scan.py scan"
RUNNER = "in-process: run_tests.main over one planted suite"
TOKEN_SEED = 7654321
TOKEN_ALPHABET = string.ascii_uppercase + "234567"
TOKEN_BODY = 16


@dataclass(frozen=True)
class Case:
    """One planted violation."""

    name: str
    check: str
    command: str
    plant: str
    expect: str
    folder: str = "."
    web: bool = False
    scanner: bool = False


Plant = Callable[[Path, Mapping[str, str]], None]


def append_line(path: str, line: str) -> Plant:
    """Return a plant that appends one line."""

    def plant(copy: Path, environment: Mapping[str, str]) -> None:
        del environment
        with (copy / path).open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")

    return plant


def write_file(path: str, text: str) -> Plant:
    """Return a plant that writes one file."""

    def plant(copy: Path, environment: Mapping[str, str]) -> None:
        del environment
        target = copy / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")

    return plant


def git(copy: Path, environment: Mapping[str, str], *args: str) -> str:
    """Run git in one scratch copy."""
    done = subprocess.run(
        ["git", "-C", str(copy), *args],
        check=True,
        capture_output=True,
        text=True,
        env=dict(environment),
    )
    return done.stdout.removesuffix("\n")


def token_line() -> str:
    """Build the planted scanner token from parts."""
    rng = random.Random(TOKEN_SEED)
    body = "".join(rng.choice(TOKEN_ALPHABET) for _ in range(TOKEN_BODY))
    return "k = " + "AK" + "IA" + body + "\n"


def plant_token_history(copy: Path, environment: Mapping[str, str]) -> None:
    """Commit and then delete a planted token file."""
    write_file("planted_token.txt", token_line())(copy, environment)
    git(copy, environment, "add", "-A")
    git(copy, environment, "commit", "-q", "-m", "chore: add")
    git(copy, environment, "rm", "-q", "planted_token.txt")
    git(copy, environment, "commit", "-q", "-m", "chore: remove")


PLANTS: dict[str, Plant] = {
    "local-path": append_line("README.md", "see /ho" + "me/planted/file"),
    "eight-digits": append_line("README.md", "number " + "1234" + "5678 here"),
    "stray-folder": write_file("extras/planted.txt", "x\n"),
    "node-pin": write_file(".nvmrc", "21\n"),
    "unused-import": write_file("scripts/planted_lint.py", "import os\n"),
    "unformatted": write_file("scripts/planted_format.py", "x=1\n"),
    "untyped": write_file("scripts/planted_types.py", "def f(x):\n    return x\n"),
    "web-fetch": write_file(
        "web/src/planted_fe11.ts",
        "export const planted = (): Promise<Response> => fetch('/x');\n",
    ),
    "web-unformatted": write_file(
        "web/src/planted_format.ts", "export const planted = {a:1}\n"
    ),
    "web-type-error": write_file(
        "web/src/planted_types.ts", "export const planted: number = 'x';\n"
    ),
    "failing-test": write_file(
        "planted_tests/test_planted.py",
        "def test_planted() -> None:\n    assert False\n",
    ),
    "passing-test": write_file(
        "planted_tests/test_planted.py",
        "def test_planted() -> None:\n    assert True\n",
    ),
    "token-history": plant_token_history,
}

CASES: tuple[Case, ...] = (
    Case(
        "docs-local-path",
        "documentation",
        DOCS,
        "local-path",
        "FAIL local-path: README.md:",
    ),
    Case(
        "identifier-eight-digits",
        "identifier",
        DOCS,
        "eight-digits",
        "FAIL identifier-number: README.md:",
    ),
    Case(
        "tree-stray-folder",
        "tree",
        TREE,
        "stray-folder",
        "FAIL top-level-folder: extras:",
    ),
    Case(
        "versions-node-file",
        "versions",
        VERSIONS,
        "node-pin",
        "FAIL version-file: .nvmrc:",
    ),
    Case("lint-unused-import", "lint", RUFF, "unused-import", "F401"),
    Case(
        "format-unformatted",
        "format",
        FORMAT,
        "unformatted",
        "would be reformatted",
    ),
    Case("types-untyped", "types", MYPY, "untyped", "no-untyped-def"),
    Case(
        "web-lint-fe11",
        "web-lint",
        WEB_LINT,
        "web-fetch",
        "FE-11",
        folder="web",
        web=True,
    ),
    Case(
        "web-format",
        "web-format",
        WEB_FORMAT,
        "web-unformatted",
        "src/planted_format.ts",
        folder="web",
        web=True,
    ),
    Case(
        "web-types",
        "web-types",
        WEB_TYPES,
        "web-type-error",
        "TS2322",
        folder="web",
        web=True,
    ),
    Case(
        "tests-failing-test",
        "tests",
        RUNNER,
        "failing-test",
        "FAIL tests-failed: planted: 1 failed",
    ),
    Case(
        "secrets-token-in-history",
        "secrets",
        SCAN,
        "token-history",
        "FAIL secret:",
        scanner=True,
    ),
)

CLASSES = (
    "documentation",
    "identifier",
    "tree",
    "versions",
    "lint",
    "format",
    "types",
    "web-lint",
    "web-format",
    "web-types",
    "tests",
    "secrets",
)
