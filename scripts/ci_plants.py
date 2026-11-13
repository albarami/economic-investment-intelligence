"""Run the S0-T07 planted failures in temporary scratch repositories."""

from __future__ import annotations

import io
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import TextIO

import ci_plant_cases as cases
import run_tests

ROOT = Path(__file__).resolve().parents[1]
PASS_THROUGH = (
    "PATH",
    "HOME",
    "LANG",
    "LC_ALL",
    "TMPDIR",
    "XDG_DATA_HOME",
    "XDG_CACHE_HOME",
    "UV_CACHE_DIR",
    "UV_PYTHON_INSTALL_DIR",
    "npm_config_cache",
)
FIXED_ENV = {
    "UV_OFFLINE": "1",
    "npm_config_userconfig": os.devnull,
    "npm_config_globalconfig": os.devnull,
    "NO_COLOR": "1",
    "PYTHONDONTWRITEBYTECODE": "1",
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_SYSTEM": os.devnull,
    "GIT_TERMINAL_PROMPT": "0",
    "GIT_AUTHOR_NAME": "planted",
    "GIT_COMMITTER_NAME": "planted",
    "GIT_AUTHOR_EMAIL": "planted" + "@" + "x.invalid",
    "GIT_COMMITTER_EMAIL": "planted" + "@" + "x.invalid",
}
COMMAND_TIMEOUT_SECONDS = 900
SETUP_TIMEOUT_SECONDS = 300
TAIL_LINES = 5
SHOWN_LINE = 200
SEED = "1000000001"
SUITE_TIMEOUT_SECONDS = 300
SCANNER_FOLDER = Path("data") / "tools" / "gitleaks"
USAGE = "usage: ci_plants.py run"


class PlantError(Exception):
    """A harness failure whose message is safe to print."""


def validate_cases(case_list: Sequence[cases.Case]) -> None:
    """Require the closed guard order, unique case names and registered plants."""
    if tuple(case.check for case in case_list) != cases.CLASSES:
        raise PlantError("case guards differ from the closed guard order")
    if len({case.name for case in case_list}) != len(case_list):
        raise PlantError("case names are not unique")
    if any(case.plant not in cases.PLANTS for case in case_list):
        raise PlantError("case plant is not registered")


def child_environment(parent: Mapping[str, str]) -> dict[str, str]:
    """Build a child environment from a closed allow-list."""
    kept = {name: parent[name] for name in PASS_THROUGH if name in parent}
    return {**kept, **FIXED_ENV}


def execute(
    argv: Sequence[str],
    cwd: Path,
    environment: Mapping[str, str],
    timeout: int,
) -> tuple[int, str]:
    """Run one command and return its status and merged output."""
    try:
        done = subprocess.run(
            list(argv),
            cwd=cwd,
            env=dict(environment),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return 124, f"timed out after {timeout} seconds"
    except OSError as error:
        raise PlantError(
            f"{argv[0]} could not start ({type(error).__name__})"
        ) from error
    return done.returncode, done.stdout


def listed_files(root: Path, environment: Mapping[str, str]) -> list[str]:
    """List tracked and unignored untracked files."""
    status, output = execute(
        [
            "git",
            "-C",
            str(root),
            "ls-files",
            "-z",
            "--cached",
            "--others",
            "--exclude-standard",
        ],
        root,
        environment,
        SETUP_TIMEOUT_SECONDS,
    )
    if status != 0:
        raise PlantError(f"git ls-files failed (status {status})")
    return sorted({name for name in output.split("\0") if name})


def make_copy(
    root: Path,
    destination: Path,
    environment: Mapping[str, str],
) -> Path:
    """Create one committed scratch copy."""
    root = root.resolve()
    destination = destination.resolve()
    if root.is_relative_to(destination):
        raise PlantError("copy destination is the root or contains the root")
    for name in listed_files(root, environment):
        source = root / name
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.is_symlink():
            target.symlink_to(os.readlink(source))
        elif source.is_file():
            shutil.copy2(source, target)
        else:
            raise PlantError(f"listed file is missing: {name}")
    for step in (
        ["init", "-q", "-b", "main"],
        ["add", "-A"],
        ["commit", "-q", "-m", "chore: base"],
    ):
        cases.git(destination, environment, *step)
    return destination


def prepare(
    copy: Path,
    root: Path,
    case: cases.Case,
    environment: Mapping[str, str],
) -> None:
    """Prepare engine, scanner and web dependencies when a case needs them."""
    if case.command == cases.MYPY:
        status, output = execute(
            [
                "uv",
                "sync",
                "--managed-python",
                "--all-packages",
                "--locked",
                "--group",
                "engine",
            ],
            copy,
            environment,
            SETUP_TIMEOUT_SECONDS,
        )
        if status != 0:
            raise PlantError(f"engine sync failed (status {status}): {tail(output)}")
    if case.scanner:
        source = root / SCANNER_FOLDER
        if not source.is_dir():
            raise PlantError(
                "the secret scanner is not installed; run its fetch command first"
            )
        shutil.copytree(source, copy / SCANNER_FOLDER)
    if case.web:
        status, output = execute(
            ["npm", "ci", "--offline"],
            copy / "web",
            environment,
            SETUP_TIMEOUT_SECONDS,
        )
        if status != 0:
            raise PlantError(
                f"npm ci --offline failed (status {status}): {tail(output)}"
            )


def tail(output: str) -> str:
    """Return a short one-line output tail."""
    lines = [line[:SHOWN_LINE] for line in output.splitlines() if line.strip()]
    return " | ".join(lines[-TAIL_LINES:])


def run_check(
    case: cases.Case,
    copy: Path,
    environment: Mapping[str, str],
) -> tuple[int, str]:
    """Run one case's check."""
    if case.command == cases.RUNNER:
        buffer = io.StringIO()
        suite = run_tests.Suite(
            "planted",
            "pytest",
            ".",
            ("planted_tests",),
            SUITE_TIMEOUT_SECONDS,
        )
        status = run_tests.main(
            ["--seed", SEED],
            suites=(suite,),
            root=copy,
            environ=environment,
            out=buffer,
            err=buffer,
        )
        return status, buffer.getvalue()
    return execute(
        shlex.split(case.command),
        copy / case.folder,
        environment,
        COMMAND_TIMEOUT_SECONDS,
    )


def run_case(
    case: cases.Case,
    root: Path,
    scratch: Path,
    environment: Mapping[str, str],
    controls: dict[tuple[str, str], tuple[int, str]],
) -> str | None:
    """Require a clean control to pass and a planted copy to fail."""
    key = (case.command, case.folder)
    try:
        if key not in controls:
            clean = make_copy(root, scratch / f"{case.name}-clean", environment)
            if case.command == cases.RUNNER:
                cases.PLANTS["passing-test"](clean, environment)
            prepare(clean, root, case, environment)
            controls[key] = run_check(case, clean, environment)
        status, output = controls[key]
        if status != 0:
            return f"the clean copy failed (status {status}): {tail(output)}"
        copy = make_copy(root, scratch / case.name, environment)
        prepare(copy, root, case, environment)
        cases.PLANTS[case.plant](copy, environment)
        cases.git(copy, environment, "add", "-A")
        status, output = run_check(case, copy, environment)
    except (PlantError, subprocess.CalledProcessError, OSError) as error:
        return f"could not run: {error}"
    if status == 0:
        return f"the planted copy passed: {tail(output)}"
    if case.expect not in output:
        return (
            f"status {status} but the line {case.expect!r} was not printed: "
            f"{tail(output)}"
        )
    return None


def run_all(
    root: Path,
    parent: Mapping[str, str],
    out: TextIO,
    err: TextIO,
) -> int:
    """Run every planted case."""
    validate_cases(cases.CASES)
    controls: dict[tuple[str, str], tuple[int, str]] = {}
    blocked = failed = 0
    with tempfile.TemporaryDirectory(prefix="eii-plants-") as raw:
        scratch = Path(raw)
        config_home = scratch / "config"
        config_home.mkdir(parents=True, exist_ok=True)
        empty_user = config_home / "npmrc-user"
        empty_global = config_home / "npmrc-global"
        empty_user.write_text("", encoding="utf-8")
        empty_global.write_text("", encoding="utf-8")
        environment = {
            **child_environment(parent),
            "XDG_CONFIG_HOME": str(config_home),
            "npm_config_userconfig": str(empty_user),
            "npm_config_globalconfig": str(empty_global),
        }
        for case in cases.CASES:
            reason = run_case(case, root, scratch, environment, controls)
            if reason is None:
                blocked += 1
                print(
                    f"plant {case.name} [{case.check}]: blocked",
                    file=out,
                    flush=True,
                )
            else:
                failed += 1
                print(f"FAIL plant {case.name}: {reason}", file=err, flush=True)
    print(
        f"plants: {len(cases.CASES)} cases, {blocked} blocked, {failed} failed",
        file=out,
    )
    print("RESULT: " + ("FAILED" if failed else "PASSED"), file=out)
    return 1 if failed else 0


def main(argv: Sequence[str]) -> int:
    """Run the `run` command."""
    if list(argv) != ["run"]:
        print(USAGE, file=sys.stderr)
        return 2
    return run_all(ROOT, os.environ, sys.stdout, sys.stderr)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
