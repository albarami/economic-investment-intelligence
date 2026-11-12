"""Stub folders and checkers for the command tests (not collected)."""

from __future__ import annotations

import ast
import contextlib
import io
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import preflight_stubs as stubs

import preflight_proc as proc

ROOT = Path(__file__).resolve().parents[2]
STUB_NAMES = (
    "docker",
    "docker-compose",
    "podman",
    "systemctl",
    "service",
    "sudo",
    "pg_ctl",
    "pg_ctlcluster",
    "pg_isready",
    "psql",
    "uv",
    "npm",
    "git",
    "cmd.exe",
)
DATABASE_PROGRAMS = frozenset(
    {
        "docker",
        "docker-compose",
        "podman",
        "systemctl",
        "service",
        "sudo",
        "pg_ctl",
        "pg_ctlcluster",
    }
)
PROBE_ARGV = ("info", "--format", "{{.ServerVersion}}")
FORBIDDEN_WORDS = ("subprocess", "docker", "compose", "systemctl")
DOCKER_FLAG = re.compile(r"\bdocker\s*=\s*False\b")
BANNED_COMPOSE = frozenset(
    {"-v", "--volumes", "rm", "down", "kill", "pull", "run", "exec"}
)
USAGE_PREFIX = "eii: usage error: unknown command or flag."
TEST_FORM = "test [--seed N]"
ENV_FILE_NAME = "port.env"
LOOPBACK_PORT = 18080
ARCH_HEADER = "| Command | Plane | Does | Network | Sandbox |"
EXIT_HEADER = "| Code | Meaning |"


def make_temp(test: unittest.TestCase, prefix: str) -> Path:
    """Create a temporary folder and remove it when the test ends."""
    path = Path(tempfile.mkdtemp(prefix=prefix))

    def remove(folder: Path = path) -> None:
        shutil.rmtree(folder, ignore_errors=True)

    test.addCleanup(remove)
    return path


def stub_folder(test: unittest.TestCase) -> Path:
    """Write one stub for every program the command tests record."""
    folder = make_temp(test, "eii-cmd-stubs-")
    for name in STUB_NAMES:
        stubs.write_stub(folder, name)
    return folder


def write_fake_uv(folder: Path) -> None:
    """Write a uv stand-in that prints its arguments and exits 7."""
    path = folder / "uv"
    path.write_text(
        '#!/bin/sh\nfor arg in "$@"; do\n  printf \'%s\\n\' "$arg"\ndone\nexit 7\n',
        encoding="utf-8",
    )
    path.chmod(path.stat().st_mode | stat.S_IEXEC)


def calls(folder: Path) -> list[dict[str, Any]]:
    """Read the stub call record."""
    return stubs.calls(folder)


def command_url() -> str:
    """Build a loopback URL on a port the tests are allowed to name."""
    if LOOPBACK_PORT in stubs.BANNED_PORTS:
        raise AssertionError("command tests named a banned port")
    return stubs.database_url(None, LOOPBACK_PORT)


def write_secret(root: Path) -> None:
    """Create an empty regular file at the Compose secret path."""
    path = root / "data" / "compose" / "postgres_superuser_password"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"")


def snapshot(root: Path) -> dict[str, bytes | None]:
    """Record every file and folder under root."""
    found: dict[str, bytes | None] = {}
    for path in root.rglob("*"):
        key = path.relative_to(root).as_posix()
        if path.is_file():
            found[key] = path.read_bytes()
        else:
            found[key] = None
    return found


def tree_problems(
    before: Mapping[str, bytes | None],
    after: Mapping[str, bytes | None],
) -> list[str]:
    """Report files added, removed or changed."""
    problems: list[str] = []
    for key in sorted(before):
        if key not in after:
            problems.append(f"removed: {key}")
        elif before[key] != after[key]:
            problems.append(f"changed: {key}")
    for key in sorted(after):
        if key not in before:
            problems.append(f"added: {key}")
    return problems


def architecture_table(root: Path) -> tuple[tuple[str, str], ...]:
    """Read the twelve command rows from the architecture document."""
    lines = (
        (root / "docs" / "02_ARCHITECTURE.md").read_text(encoding="utf-8").splitlines()
    )
    start = _header_index(lines, ARCH_HEADER) + 2
    rows: list[tuple[str, str]] = []
    for line in lines[start:]:
        if not line.startswith("|"):
            break
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        raw = cells[0].strip("`").strip()
        prefix = "./eii "
        if not raw.startswith(prefix):
            raise AssertionError(raw)
        rows.append((raw[len(prefix) :], cells[1].strip()))
    return tuple(rows)


def usage_form(command: str) -> str:
    """Map an architecture command to the usage line."""
    if command == "test":
        return TEST_FORM
    return command


def expected_usage(root: Path) -> str:
    """Build the usage text from the architecture table."""
    forms = [usage_form(command) for command, _plane in architecture_table(root)]
    return USAGE_PREFIX + "\n" + "\n".join(forms) + "\n"


def pinned_words(root: Path) -> tuple[str, ...]:
    """Return the eleven command words in architecture order."""
    words: list[str] = []
    seen: set[str] = set()
    for command, _plane in architecture_table(root):
        word = command.split()[0]
        if word not in seen:
            seen.add(word)
            words.append(word)
    return tuple(words)


def exit_meanings(root: Path) -> dict[int, str]:
    """Read exit-code meanings from the operations document."""
    lines = (
        (root / "docs" / "13_DEPLOYMENT_AND_OPERATIONS.md")
        .read_text(encoding="utf-8")
        .splitlines()
    )
    start = _header_index(lines, EXIT_HEADER) + 2
    meanings: dict[int, str] = {}
    for line in lines[start:]:
        if not line.startswith("|"):
            break
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) < 2 or not cells[0].isdigit():
            break
        meanings[int(cells[0])] = cells[1]
    return meanings


def shell_words(root: Path) -> tuple[str, ...]:
    """Read the launcher's closed word list."""
    for line in (root / "eii").read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("preflight|") and stripped.endswith(")"):
            return tuple(stripped[:-1].split("|"))
    raise AssertionError("launcher word list missing")


def compose_project(root: Path) -> str:
    """Read the Compose project name."""
    for line in (
        (root / "infra" / "compose.yaml").read_text(encoding="utf-8").splitlines()
    ):
        if line.startswith("name:"):
            return line.split(":", 1)[1].strip()
    raise AssertionError("compose project name missing")


def command_sources(root: Path) -> dict[str, str]:
    """Read every module under scripts/commands."""
    folder = root / "scripts" / "commands"
    files = sorted(folder.glob("*.py"))
    if not files:
        raise FileNotFoundError(folder)
    return {path.name: path.read_text(encoding="utf-8") for path in files}


def source_problems(sources: Mapping[str, str]) -> list[str]:
    """Report a forbidden word or a database import outside main.py.

    The probe switch ``docker=False`` is the one allowed spelling of that
    word: ``run_preflight`` takes it as a keyword-only argument, and this
    task does not edit that function. ``main.py`` may import the commands
    module ``database``. Every other module of that package may not.
    ``database.py`` is the module itself and is not scanned.
    """
    problems: list[str] = []
    for name in sorted(sources):
        if name == "database.py":
            continue
        text = sources[name]
        for word in FORBIDDEN_WORDS:
            scanned = DOCKER_FLAG.sub("", text) if word == "docker" else text
            if re.search(rf"\b{word}\b", scanned):
                problems.append(f"{name}: contains {word}")
        if name != "main.py" and _imports_commands_database(text):
            problems.append(f"{name}: imports database")
    return problems


def _imports_commands_database(text: str) -> bool:
    """Return whether text imports the commands module database."""
    tree = ast.parse(text)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import) and _import_names_database(node):
            return True
        if isinstance(node, ast.ImportFrom) and _import_from_database(node):
            return True
    return False


def _import_names_database(node: ast.Import) -> bool:
    return any(_module_is_commands_database(alias.name) for alias in node.names)


def _import_from_database(node: ast.ImportFrom) -> bool:
    module = node.module or ""
    names = {alias.name for alias in node.names}
    if node.level == 1 and module == "" and "database" in names:
        return True
    if node.level == 1 and _module_is_relative_database(module):
        return True
    if node.level == 0 and module == "commands" and "database" in names:
        return True
    return node.level == 0 and _module_is_commands_database(module)


def _module_is_commands_database(name: str) -> bool:
    return name == "commands.database" or name.startswith("commands.database.")


def _module_is_relative_database(name: str) -> bool:
    return name == "database" or name.startswith("database.")


def probe_problems(records: Sequence[Mapping[str, Any]]) -> list[str]:
    """Report a call that is not a closed preflight probe."""
    problems: list[str] = []
    for rec in records:
        program = str(rec.get("program", ""))
        args = _args(rec)
        if not proc.command_allowed(program, args):
            shown = " ".join(args)
            problems.append(f"call not on the closed list: {program} {shown}")
        if program == "docker" and tuple(args) != PROBE_ARGV:
            problems.append(f"docker call is not the info probe: {args}")
    return problems


def database_start_problems(records: Sequence[Mapping[str, Any]]) -> list[str]:
    """Report a program that starts or stops a database."""
    problems: list[str] = []
    for rec in records:
        program = str(rec.get("program", ""))
        if program in DATABASE_PROGRAMS:
            problems.append(f"database program started: {program} {_args(rec)}")
    return problems


def one_compose_problems(
    records: Sequence[Mapping[str, Any]],
    *,
    tail: Sequence[str],
    root: Path,
    project: str,
) -> list[str]:
    """Report a db-up or db-down record that is not the one closed call."""
    if len(records) != 1:
        return [f"expected one program call, saw {len(records)}"]
    rec = records[0]
    problems: list[str] = []
    program = str(rec.get("program", ""))
    if program != "docker":
        problems.append(f"program {program}")
    argv = _argv(rec)
    if not argv or Path(argv[0]).name != "docker":
        problems.append("argv0 is not docker")
    body = argv[1:]
    head = ["compose", "-p", project, "-f", "infra/compose.yaml", "--env-file"]
    if body[: len(head)] != head:
        problems.append(f"prefix {body[: len(head)]}")
    else:
        env_file = body[len(head)]
        rest = body[len(head) + 1 :]
        if rest != list(tail):
            problems.append(f"tail {rest}")
        path = Path(env_file)
        if path.name != ENV_FILE_NAME:
            problems.append(f"env file name {path.name}")
        if not path.is_absolute():
            problems.append("env file is not absolute")
        try:
            path.relative_to(root)
        except ValueError:
            pass
        else:
            problems.append("env file is inside the command root")
    for arg in body:
        if arg in BANNED_COMPOSE:
            problems.append(f"banned argument {arg}")
    env = rec.get("env")
    if isinstance(env, dict):
        if "EII_DATABASE_URL" in env:
            problems.append("database url was passed to the child")
        if "EII_COMPOSE_DB_PORT" in env:
            problems.append("compose port was passed in the environment")
    return problems


def failure_problems(code: int, stderr: str, meaning: str) -> list[str]:
    """Report an exit that is outside the table or missing its lines."""
    problems: list[str] = []
    if code < 0 or code > 7:
        problems.append(f"exit {code} is outside 0 to 7")
    fail_lines = [line for line in stderr.splitlines() if line.startswith("FAIL ")]
    if not fail_lines:
        problems.append("FAIL line missing")
    prefix = f"eii: exit {code}: "
    matches = [line for line in stderr.splitlines() if line.startswith("eii: exit ")]
    if matches != [prefix + meaning]:
        problems.append(f"meaning line {matches}")
    return problems


def run_launcher(
    args: Sequence[str],
    env: Mapping[str, str],
    root: Path,
) -> subprocess.CompletedProcess[str]:
    """Run the eii script with a closed environment."""
    return subprocess.run(
        [str(root / "eii"), *args],
        cwd=root,
        env=dict(env),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def run_main(
    argv: Sequence[str],
    environ: Mapping[str, str],
    root: Path,
) -> tuple[int, str, str]:
    """Call commands.main in process and capture both streams."""
    import commands.main as main

    stdout = io.StringIO()
    stderr = io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        code = main.main(argv, environ, root)
    return code, stdout.getvalue(), stderr.getvalue()


def run_finish(code: int, command: str, detail: str) -> tuple[int, str]:
    """Call exits.finish and capture standard error."""
    import commands.exits as exits

    stderr = io.StringIO()
    with contextlib.redirect_stderr(stderr):
        result = exits.finish(code, command, detail)
    return result, stderr.getvalue()


def _header_index(lines: Sequence[str], header: str) -> int:
    for index, line in enumerate(lines):
        if line.startswith(header):
            return index
    raise AssertionError(header)


def _argv(rec: Mapping[str, Any]) -> list[str]:
    raw = rec.get("argv")
    if not isinstance(raw, list):
        return []
    return [str(part) for part in raw]


def _args(rec: Mapping[str, Any]) -> list[str]:
    argv = _argv(rec)
    return argv[1:]
