"""Scratch repositories and helpers for the CI workflow and plant tests."""

from __future__ import annotations

import hashlib
import io
import os
import random
import shutil
import string
import subprocess
import sys
import tempfile
import unittest
from collections.abc import Mapping, Sequence
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ci_history_scan as history
import ci_plant_cases as plant_cases
import hooks_gitleaks

ROOT = Path(__file__).resolve().parents[2]
KNOWN_DIGEST = history.KNOWN_LINES[0][2]
WORKFLOW_DIR = ROOT / ".github/workflows"


def run_module(
    module: str,
    argv: Sequence[str],
    *,
    cwd: Path | None = None,
    env: Mapping[str, str] | None = None,
) -> tuple[int, str, str]:
    """Run a script under ``scripts/`` and capture output."""
    child = {
        **os.environ,
        "PYTHONPATH": os.pathsep.join(
            (str(ROOT / "scripts"), os.environ.get("PYTHONPATH", ""))
        ),
    }
    if env is not None:
        child.update(env)
    done = subprocess.run(
        [sys.executable, f"scripts/{module}", *argv],
        cwd=cwd or ROOT,
        env=child,
        capture_output=True,
        text=True,
        errors="replace",
        timeout=900,
        check=False,
    )
    return done.returncode, done.stdout, done.stderr


def workflow_fixture(parent: Path) -> Path:
    """Copy the three workflow files into a temporary directory."""
    folder = parent / "workflows"
    folder.mkdir(parents=True)
    for name in ("ci.yml", "docs.yml", "sandbox.yml"):
        shutil.copy2(WORKFLOW_DIR / name, folder / name)
    return folder


def git(env: Mapping[str, str], repo: Path, *args: str) -> None:
    """Run git against a scratch repository."""
    done = subprocess.run(
        ["git", "-C", str(repo), *args],
        env=dict(env),
        capture_output=True,
        text=True,
        check=False,
    )
    if done.returncode != 0:
        raise AssertionError(done.stderr or done.stdout)


def history_repo(parent: Path, env: Mapping[str, str], *, shallow: bool) -> Path:
    """Create a repository with two clean commits for history-scan tests."""
    repo = parent / "history"
    repo.mkdir(parents=True)
    git(env, repo, "init", "-q", "-b", "main")
    (repo / "README.md").write_text("base\n", encoding="utf-8")
    shutil.copy2(ROOT / ".gitleaks.toml", repo / ".gitleaks.toml")
    (repo / "pins.toml").write_text(
        (ROOT / "pins.toml").read_text(encoding="utf-8"), encoding="utf-8"
    )
    git(env, repo, "add", "-A")
    git(env, repo, "commit", "-q", "-m", "chore: base")
    (repo / "notes.txt").write_text("second\n", encoding="utf-8")
    git(env, repo, "add", "notes.txt")
    git(env, repo, "commit", "-q", "-m", "chore: second")
    if shallow:
        git(env, repo, "fetch", "--depth", "1", "origin", "main")
    return repo


def place_scanner(repo: Path) -> None:
    """Place the installed scanner where the history scan expects it."""
    version = hooks_gitleaks.read_version(ROOT)
    source = ROOT / "data" / "tools" / "gitleaks" / version / "gitleaks"
    if not source.is_file():
        raise unittest.SkipTest(
            "scanner missing; run uv run --locked python scripts/hooks_gitleaks.py fetch"
        )
    target = repo / "data" / "tools" / "gitleaks" / version / "gitleaks"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target, follow_symlinks=True)
    shutil.copy2(ROOT / ".gitleaks.toml", repo / ".gitleaks.toml")


def known_ledger_line() -> str:
    """Return the PROGRESS.md line whose digest is listed in ``KNOWN_LINES``."""
    for line in (ROOT / "PROGRESS.md").read_text(encoding="utf-8").splitlines():
        digest = hashlib.sha256(line.encode("utf-8")).hexdigest()
        if digest == KNOWN_DIGEST:
            return line
    raise AssertionError("PROGRESS.md has no line whose SHA-256 matches KNOWN_LINES[0]")


def shaped_probe_line() -> str:
    """Build a generic-api-key-shaped line that is not a known ledger line."""
    rng = random.Random(1794000001)
    body = "".join(
        rng.choice(string.ascii_lowercase + string.digits) for _ in range(24)
    )
    return f"PLANT_PROBE_TOKEN={body}"


def history_with_ledger_line(parent: Path, env: Mapping[str, str], line: str) -> Path:
    """Scratch repository whose history holds ``line`` in ``PROGRESS.md`` twice."""
    repo = history_repo(parent, env, shallow=False)
    progress = repo / "PROGRESS.md"
    progress.write_text(line + "\n", encoding="utf-8")
    git(env, repo, "add", "PROGRESS.md")
    git(env, repo, "commit", "-q", "-m", "chore: ledger once")
    progress.write_text(line + "\nsecond entry\n", encoding="utf-8")
    git(env, repo, "add", "PROGRESS.md")
    git(env, repo, "commit", "-q", "-m", "chore: ledger twice")
    return repo


def scanner_output(
    *,
    status: int,
    commits: int | None,
    err_line: str | None = None,
    finding_line: str | None = None,
    leak_count: int | None = None,
) -> str:
    """Build a synthetic scanner log for judge tests."""
    if leak_count is not None:
        finding_line = f"gitleaks WRN leaks found: {leak_count}"
    lines = ["gitleaks INF no leaks found: 0"]
    if finding_line:
        lines.append(finding_line)
    if err_line:
        lines.append(err_line)
    if commits is not None:
        lines.append(f"gitleaks INF {commits} commits scanned")
    return "\n".join(lines) + "\n"


def token_in_history(repo: Path, env: Mapping[str, str]) -> None:
    """Plant one AWS-shaped token into the history of a scratch repository."""
    plant_cases.plant_token_history(repo, env)


def capture_run_all(root: Path, env: Mapping[str, str]) -> tuple[int, str, str]:
    """Run ``ci_plants.run_all`` and capture combined output."""
    import ci_plants

    out = io.StringIO()
    err = io.StringIO()
    status = ci_plants.run_all(root, env, out, err)
    return status, out.getvalue(), err.getvalue()


def temp_home(testcase: unittest.TestCase) -> tuple[Path, dict[str, str]]:
    """Create an isolated home directory and environment."""
    home = Path(tempfile.mkdtemp())
    testcase.addCleanup(shutil.rmtree, home, True)
    env = {
        "HOME": str(home),
        "TMPDIR": str(home),
        "LANG": "C.UTF-8",
        "PATH": os.environ.get("PATH", ""),
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_SYSTEM": os.devnull,
        "GIT_AUTHOR_NAME": "Scratch Author",
        "GIT_COMMITTER_NAME": "Scratch Author",
        "GIT_AUTHOR_EMAIL": "author" + "@" + "scratch.invalid",
        "GIT_COMMITTER_EMAIL": "author" + "@" + "scratch.invalid",
    }
    return home, env
