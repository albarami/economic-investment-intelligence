"""Scratch repositories, stub programs and token builders for the hook tests."""

from __future__ import annotations

import hashlib
import os
import random
import re
import shutil
import stat
import subprocess
import sys
import unittest
from collections.abc import Mapping, Sequence
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import commit_guard
import hooks_gitleaks
import hooks_install
import hooks_run

ROOT = Path(__file__).resolve().parents[2]
SEED = 7141592
STUB_TEXT = """#!/bin/sh
case "$PWD" in */web) d=web ;; *) d=. ;; esac
printf '%s|%s|%s\\n' "${0##*/}" "$d" "$*" >> "$STUB_LOG"
code=0
if [ -f "$0.exit" ]; then IFS= read -r code < "$0.exit"; fi
exit "$code"
"""
REPORT_LINE = re.compile(
    r"^(?P<name>.+?)\.{3,}(?:\(no files to check\))?(?P<status>Passed|Failed|Skipped)$"
)
_LOADED = (commit_guard, hooks_gitleaks, hooks_install, hooks_run)
_CLOUD = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"
_LETTERS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
_DIGITS = "0123456789"
_MODEL = _LETTERS + _DIGITS + "-_"
_KEY_BODY = _LETTERS + _DIGITS + "+/"


def system_bin(home: Path) -> Path:
    """Create ``home/sysbin`` with links for git, bash and sh, plus ``python3``.

    Args:
        home: The temporary home directory.

    Returns:
        The program folder.
    """
    folder = home / "sysbin"
    folder.mkdir(parents=True, exist_ok=True)
    for name in ("git", "bash", "sh"):
        _link(folder, name)
    _python_script(folder)
    return folder


def python_bin(home: Path) -> Path:
    """Create ``home/pybin`` holding only the ``python3`` script.

    Args:
        home: The temporary home directory.

    Returns:
        The program folder.
    """
    folder = home / "pybin"
    folder.mkdir(parents=True, exist_ok=True)
    _python_script(folder)
    return folder


def clean_env(
    home: Path,
    dirs: Sequence[Path],
    extra: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Build an allow-list environment for one child process.

    Args:
        home: The temporary home directory.
        dirs: Program folders, joined into ``PATH`` in the given order.
        extra: Values copied in after the allow-list.

    Returns:
        The environment dictionary. Nothing is taken from the parent environment.
    """
    env = {
        "PATH": os.pathsep.join(str(path) for path in dirs),
        "HOME": str(home),
        "TMPDIR": str(home),
        "LANG": "C.UTF-8",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_SYSTEM": os.devnull,
        "GIT_CEILING_DIRECTORIES": str(home.parent),
        "GIT_AUTHOR_NAME": "Scratch Author",
        "GIT_COMMITTER_NAME": "Scratch Author",
        "GIT_AUTHOR_EMAIL": "author" + "@" + "scratch.invalid",
        "GIT_COMMITTER_EMAIL": "author" + "@" + "scratch.invalid",
        "PRE_COMMIT_HOME": str(home / "pre-commit-store"),
        "STUB_LOG": str(home / "stub.log"),
    }
    if extra:
        env.update(extra)
    return env


def run(
    argv: Sequence[str],
    cwd: Path,
    env: Mapping[str, str],
    stdin: str | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run a command with no shell and a bounded wait.

    Args:
        argv: The program and its arguments.
        cwd: The working directory.
        env: The child environment.
        stdin: Text for standard input, or None.

    Returns:
        The completed process.
    """
    return subprocess.run(
        list(argv),
        cwd=cwd,
        env=dict(env),
        input=stdin,
        capture_output=True,
        text=True,
        errors="replace",
        timeout=300,
        check=False,
    )


def git(
    repo: Path, env: Mapping[str, str], *args: str
) -> subprocess.CompletedProcess[str]:
    """Run git against a scratch repository.

    Args:
        repo: The repository directory.
        env: The child environment.
        *args: The git arguments.

    Returns:
        The completed process.
    """
    return run(["git", "-C", str(repo), *args], cwd=repo, env=env)


def plain_repo(parent: Path, env: Mapping[str, str]) -> Path:
    """Create a one-commit repository that copies nothing from the real tree.

    Args:
        parent: The directory that will hold ``repo``.
        env: The child environment.

    Returns:
        The repository path.
    """
    repo = parent / "repo"
    repo.mkdir(parents=True)
    _require(git(repo, env, "init", "-q", "-b", "main"))
    (repo / "base.txt").write_text("base\n", encoding="utf-8")
    _require(git(repo, env, "add", "--", "base.txt"))
    _require(git(repo, env, "commit", "-q", "-m", "chore: base"))
    return repo


def copy_tree(dest: Path, env: Mapping[str, str]) -> None:
    """Copy the listed files of the real tree into ``dest``.

    Args:
        dest: The destination directory.
        env: The child environment, used only to find git.
    """
    listed = run(
        [
            "git",
            "-c",
            f"core.excludesFile={os.devnull}",
            "ls-files",
            "-z",
            "--cached",
            "--others",
            "--exclude-standard",
        ],
        cwd=ROOT,
        env=env,
    )
    _require(listed)
    dest.mkdir(parents=True, exist_ok=True)
    for rel in listed.stdout.split("\0"):
        if not rel:
            continue
        source = ROOT / rel
        if not source.exists():
            continue
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target, follow_symlinks=False)


def place_binary(repo: Path, copy: bool = False) -> Path:
    """Put the installed scanner binary at the same relative place under ``repo``.

    Args:
        repo: The scratch repository.
        copy: When True, always copy, so a later edit cannot change the cache.

    Returns:
        The placed binary.

    Raises:
        AssertionError: The binary is not installed.
    """
    version = hooks_gitleaks.read_version(ROOT)
    source = ROOT / "data" / "tools" / "gitleaks" / version / "gitleaks"
    if not source.is_file():
        raise AssertionError(
            "FAIL gitleaks-missing: run: uv run --locked python scripts/hooks_gitleaks.py fetch"
        )
    target = repo / "data" / "tools" / "gitleaks" / version / "gitleaks"
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() or target.is_symlink():
        target.unlink()
    if copy:
        shutil.copy2(source, target, follow_symlinks=True)
    else:
        try:
            os.link(source, target)
        except OSError:
            shutil.copy2(source, target, follow_symlinks=True)
    return target


def scratch_repo(parent: Path, env: Mapping[str, str], hooks: bool) -> Path:
    """Copy the tree, commit it, and optionally install the hooks.

    Args:
        parent: The directory that will hold ``repo``.
        env: The child environment.
        hooks: When True, the installer must exit 0.

    Returns:
        The repository path.
    """
    repo = parent / "repo"
    copy_tree(repo, env)
    place_binary(repo)
    _require(git(repo, env, "init", "-q", "-b", "main"))
    _require(git(repo, env, "add", "-A"))
    _require(git(repo, env, "commit", "-q", "-m", "chore: scratch base"))
    if hooks:
        installed = run([sys.executable, "scripts/hooks_install.py"], cwd=repo, env=env)
        if installed.returncode != 0:
            raise AssertionError(installed.stderr or installed.stdout)
    return repo


def clone_scratch(src: Path, dest: Path) -> None:
    """Copy a scratch repository, leaving out its top-level data folder.

    Args:
        src: The prepared repository.
        dest: The new path. The scanner binary is placed afterwards.
    """

    def ignore(directory: str, names: list[str]) -> set[str]:
        if Path(directory).resolve() == src.resolve() and "data" in names:
            return {"data"}
        return set()

    shutil.copytree(src, dest, symlinks=True, ignore=ignore)
    place_binary(dest)


def write_stubs(stub_dir: Path, names: Sequence[str]) -> None:
    """Write one executable stub per name.

    Args:
        stub_dir: The folder that receives the stubs.
        names: Stub file names.
    """
    stub_dir.mkdir(parents=True, exist_ok=True)
    for name in names:
        path = stub_dir / name
        path.write_text(STUB_TEXT, encoding="utf-8")
        path.chmod(0o755)


def stub_log(path: Path) -> list[str]:
    """Return the stub log lines, or an empty list when the file is absent.

    Args:
        path: The log file named by ``STUB_LOG``.

    Returns:
        The lines, without their trailing newlines.
    """
    if not path.is_file():
        return []
    return path.read_text(encoding="utf-8").splitlines()


def hook_report(output: str) -> list[tuple[str, str]]:
    """Return the hook names and statuses printed by the framework.

    Args:
        output: Combined standard output and standard error.

    Returns:
        One pair per report line, in order.
    """
    found: list[tuple[str, str]] = []
    for line in output.splitlines():
        match = REPORT_LINE.match(line)
        if match is not None:
            found.append((match.group("name"), match.group("status")))
    return found


def random_value(rng: random.Random, n: int) -> str:
    """Return ``n`` lowercase letters from ``rng``.

    Args:
        rng: The seeded generator.
        n: The length.

    Returns:
        The value.
    """
    alphabet = "abcdefghijklmnopqrstuvwxyz"
    return "".join(rng.choice(alphabet) for _ in range(n))


def cloud_key(rng: random.Random) -> str:
    """Return a cloud-key-shaped token.

    Args:
        rng: The seeded generator.

    Returns:
        The token.
    """
    body = "".join(rng.choice(_CLOUD) for _ in range(16))
    return "AK" + "IA" + body


def model_key(rng: random.Random) -> str:
    """Return a model-key-shaped token.

    Args:
        rng: The seeded generator.

    Returns:
        The token.
    """
    body = "".join(rng.choice(_MODEL) for _ in range(93))
    return "sk-" + "ant-" + "api03-" + body + "AA"


def github_token(rng: random.Random) -> str:
    """Return a personal-token-shaped token.

    Args:
        rng: The seeded generator.

    Returns:
        The token.
    """
    body = "".join(rng.choice(_LETTERS + _DIGITS) for _ in range(36))
    return "gh" + "p_" + body


def private_key_block(rng: random.Random) -> str:
    """Return a private-key-shaped block.

    Args:
        rng: The seeded generator.

    Returns:
        The block, including its header and footer.
    """
    lines = ["".join(rng.choice(_KEY_BODY) for _ in range(64)) for _ in range(6)]
    header = "-----BEGIN " + "RSA PRIVATE KEY-----"
    footer = "-----END " + "RSA PRIVATE KEY-----"
    return header + "\n" + "\n".join(lines) + "\n" + footer + "\n"


def digit_run(rng: random.Random, n: int) -> str:
    """Return a run of exactly ``n`` digits.

    Args:
        rng: The seeded generator.
        n: The length.

    Returns:
        The digits.
    """
    return "".join(rng.choice(_DIGITS) for _ in range(n))


def assert_free_of(
    case: unittest.TestCase, text: str, secret: str, size: int = 8
) -> None:
    """Fail when any window of ``secret`` occurs in ``text``.

    Args:
        case: The running test.
        text: The output under test.
        secret: The value that must not appear. It is never printed.
        size: The window length.
    """
    if size <= 0 or len(secret) < size:
        return
    for start in range(len(secret) - size + 1):
        if secret[start : start + size] in text:
            case.fail(
                f"output holds a {size}-character window of a secret (seed {SEED})"
            )


def snapshot_real() -> dict[str, object]:
    """Return a read-only picture of the real hooks folder and git configuration.

    Returns:
        Sorted regular-file records, the configuration digest, and the
        ``core.hooksPath`` status. Nothing is printed or written.
    """
    env = {
        "PATH": os.environ.get("PATH", ""),
        "LANG": "C",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_SYSTEM": os.devnull,
    }

    def invoke(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", "-C", str(ROOT), *args],
            capture_output=True,
            text=True,
            errors="replace",
            check=False,
            env=env,
        )

    hooks_proc = invoke("rev-parse", "--path-format=absolute", "--git-path", "hooks")
    if hooks_proc.returncode != 0:
        raise AssertionError("FAIL snapshot: hooks path")
    hooks = Path(hooks_proc.stdout.strip())
    files: list[tuple[str, int, str]] = []
    if hooks.is_dir():
        for path in sorted(hooks.iterdir(), key=lambda item: item.name):
            info = path.lstat()
            if not stat.S_ISREG(info.st_mode):
                continue
            data = path.read_bytes()
            files.append((path.name, len(data), hashlib.sha256(data).hexdigest()))
    config_proc = invoke("rev-parse", "--path-format=absolute", "--git-path", "config")
    config_hash = ""
    if config_proc.returncode == 0:
        config = Path(config_proc.stdout.strip())
        if config.is_file():
            config_hash = hashlib.sha256(config.read_bytes()).hexdigest()
    setting = invoke("config", "--get", "core.hooksPath")
    return {
        "hooks": tuple(files),
        "config": config_hash,
        "hooks_path": (setting.returncode, setting.stdout),
    }


def _link(folder: Path, name: str) -> None:
    found = shutil.which(name)
    if found is None:
        raise AssertionError(f"FAIL tool-missing: {name}")
    dest = folder / name
    if not dest.exists():
        dest.symlink_to(found)


def _python_script(folder: Path) -> None:
    path = folder / "python3"
    interpreter = Path(sys.executable).resolve()
    path.write_text(
        "#!/bin/sh\n" + f'exec {interpreter} "$@"\n',
        encoding="utf-8",
    )
    path.chmod(0o755)


def _require(done: subprocess.CompletedProcess[str]) -> None:
    if done.returncode != 0:
        raise AssertionError(done.stderr or done.stdout)
