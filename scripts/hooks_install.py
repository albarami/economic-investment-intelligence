"""Install the commit hooks of this repository, and refuse to touch anyone else's (task S0-T06).

This installer calls ``pre-commit install --hook-type pre-commit`` only when that cannot
destroy, reorder or activate anything: the folder is the top of its own checkout, no
``core.hooksPath``, the main clone (not a linked work tree), the configuration file
present, no hook named ``pre-commit`` that the framework did not write, and no
``pre-commit.legacy`` file (the framework's hook would run it). It never moves,
replaces or deletes an existing hook and never passes ``-f`` or
``--allow-missing-config``.

Exit status: 0 installed (or already installed); 1 refused or the framework failed;
2 usage error or not a git checkout.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ".pre-commit-config.yaml"
HOOK_TYPE = "pre-commit"
FRAMEWORK_MARKER = b"138fd403232d2ddd5efb44317e38bf03"
INSTALL_ARGV = ("install", "--hook-type", HOOK_TYPE, "--config", CONFIG)
NOT_A_CHECKOUT = "not a git checkout"
HOW_TO = 'README.md, section "Commit hooks"'


def git(root: Path, *args: str) -> tuple[int, str]:
    """Run git in ``root`` and return (status, stripped standard output).

    Args:
        root: The repository root.
        *args: The git arguments.

    Returns:
        The exit status and the standard output without its final newline.
    """
    try:
        done = subprocess.run(
            ["git", "-C", str(root), *args],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            encoding="utf-8",
            errors="surrogateescape",
            check=False,
        )
    except OSError:
        return 127, ""
    return done.returncode, done.stdout.rstrip("\n")


def refusal(root: Path) -> str | None:
    """Return the reason the installer must not run, or None when it may.

    Args:
        root: The repository root.

    Returns:
        A one-line reason, or None.
    """
    status, top = git(root, "rev-parse", "--path-format=absolute", "--show-toplevel")
    if status != 0 or not (root / ".git").exists():
        return NOT_A_CHECKOUT
    if Path(top).resolve() != root.resolve():
        return NOT_A_CHECKOUT
    status, value = git(root, "config", "--get", "core.hooksPath")
    if status == 0 and value:
        return "core.hooksPath is set; this installer does not change it"
    _, git_dir = git(root, "rev-parse", "--absolute-git-dir")
    _, common = git(root, "rev-parse", "--path-format=absolute", "--git-common-dir")
    if Path(git_dir).resolve() != Path(common).resolve():
        return (
            "this is a linked work tree; hooks are shared, so run it in the main clone"
        )
    if not (root / CONFIG).is_file():
        return f"{CONFIG} is missing"
    _, hooks = git(root, "rev-parse", "--path-format=absolute", "--git-path", "hooks")
    existing = Path(hooks) / HOOK_TYPE
    if os.path.lexists(Path(hooks) / f"{HOOK_TYPE}.legacy"):
        return (
            f"a {HOOK_TYPE}.legacy file exists and the framework's hook would run it; "
            f"this installer never moves, replaces or deletes a hook (see {HOW_TO})"
        )
    if existing.is_symlink() or (existing.exists() and not existing.is_file()):
        return f"a {HOOK_TYPE} hook exists and is not a plain file"
    if not existing.is_file():
        return None
    try:
        content = existing.read_bytes()
    except OSError as error:
        return f"a {HOOK_TYPE} hook exists and cannot be read ({type(error).__name__})"
    if FRAMEWORK_MARKER not in content:
        return (
            f"a {HOOK_TYPE} hook already exists and the framework did not write it; "
            f"this installer never moves, replaces or deletes a hook (see {HOW_TO})"
        )
    return None


def install(root: Path) -> int:
    """Install the hooks in ``root`` unless a refusal applies.

    Args:
        root: The repository root.

    Returns:
        The exit status.
    """
    reason = refusal(root)
    if reason is not None:
        print(f"hooks_install: refused: {reason}", file=sys.stderr)
        return 2 if reason == NOT_A_CHECKOUT else 1
    try:
        done = subprocess.run(
            [sys.executable, "-m", "pre_commit", *INSTALL_ARGV],
            cwd=root,
            stdin=subprocess.DEVNULL,
            check=False,
        )
    except OSError as error:
        print(
            f"hooks_install: the framework could not start ({type(error).__name__})",
            file=sys.stderr,
        )
        return 1
    return 0 if done.returncode == 0 else 1


def main(argv: list[str]) -> int:
    """Entry point.

    Args:
        argv: The command-line arguments after the program name; none are accepted.

    Returns:
        The exit status.
    """
    if argv:
        print("usage: hooks_install.py (no arguments)", file=sys.stderr)
        return 2
    return install(ROOT)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
