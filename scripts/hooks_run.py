"""Run one project command for a commit hook (task S0-T06).

The hook configuration calls ``python3 scripts/hooks_run.py <id>`` for the checks that
need ``uv`` or ``npm``. This script looks the id up in a closed table, refuses with a
message that names the install command when the program is missing, and otherwise runs
the very command that ``AGENTS.md`` rule 44 lists. It never rewrites a file.

Exit status: the command's own status, or 1 when it could not start; 2 for an unknown
id or wrong usage.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UV_HINT = "install uv at the version recorded in pins.toml"
NPM_HINT = "install Node and npm at the versions recorded in pins.toml, then run in web/: npm ci"


@dataclass(frozen=True)
class Command:
    """One row of the table: what to run, where, and what to say when it cannot run."""

    argv: tuple[str, ...]
    folder: str
    hint: str


TABLE: dict[str, Command] = {
    "ruff-check": Command(
        ("uv", "run", "--locked", "ruff", "check", "."), ".", UV_HINT
    ),
    "ruff-format-check": Command(
        ("uv", "run", "--locked", "ruff", "format", "--check", "."), ".", UV_HINT
    ),
    "mypy": Command(("uv", "run", "--locked", "mypy"), ".", UV_HINT),
    "versions": Command(
        ("uv", "run", "--locked", "python", "scripts/check_versions.py"), ".", UV_HINT
    ),
    "web-lint": Command(("npm", "run", "lint"), "web", NPM_HINT),
    "web-format-check": Command(("npm", "run", "format:check"), "web", NPM_HINT),
    "web-typecheck": Command(("npm", "run", "typecheck"), "web", NPM_HINT),
}


def run(hook_id: str, root: Path) -> int:
    """Run the table row for ``hook_id`` from ``root``.

    Args:
        hook_id: A key of ``TABLE``.
        root: The repository root.

    Returns:
        The exit status.
    """
    command = TABLE.get(hook_id)
    if command is None:
        known = ", ".join(sorted(TABLE))
        print(f"hooks_run: unknown hook {hook_id!r}; known: {known}", file=sys.stderr)
        return 2
    program = command.argv[0]
    if shutil.which(program) is None:
        print(
            f"hooks_run: {program} was not found on PATH; {command.hint}",
            file=sys.stderr,
        )
        return 1
    folder = root / command.folder
    if not folder.is_dir():
        print(f"hooks_run: folder {command.folder} does not exist", file=sys.stderr)
        return 1
    if command.folder == "web" and not (folder / "node_modules").is_dir():
        print(
            f"hooks_run: web/node_modules is missing; {command.hint}", file=sys.stderr
        )
        return 1
    try:
        done = subprocess.run(
            command.argv, cwd=folder, stdin=subprocess.DEVNULL, check=False
        )
    except OSError as error:
        print(
            f"hooks_run: {program} could not start ({type(error).__name__})",
            file=sys.stderr,
        )
        return 1
    if done.returncode < 0:
        return 1
    return done.returncode


def main(argv: list[str]) -> int:
    """Entry point.

    Args:
        argv: One hook id.

    Returns:
        The exit status.
    """
    if len(argv) != 1:
        print("usage: hooks_run.py <hook-id>", file=sys.stderr)
        return 2
    return run(argv[0], ROOT)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
