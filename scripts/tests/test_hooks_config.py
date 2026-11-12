"""Closed checks for the commit-hook configuration."""

from __future__ import annotations

import importlib
import re
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any, cast

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import hooks_support as support

import hooks_run

_TOP = ("minimum_pre_commit_version", "default_stages", "repos")
_BASE = ("id", "name", "entry", "language", "pass_filenames")
_PYTHON = r"\.pyi?$|(^|/)pyproject\.toml$"
_WEB = "^web/"
_HOOKS: tuple[tuple[str, str, str, str | None], ...] = (
    (
        "commit-guard",
        "commit guard (no staged local secret value)",
        "python3 scripts/commit_guard.py",
        None,
    ),
    (
        "gitleaks",
        "gitleaks (staged changes)",
        "python3 scripts/hooks_gitleaks.py staged",
        None,
    ),
    (
        "docs",
        "documentation check (paths, addresses, tokens, identifier numbers)",
        "python3 scripts/check_docs.py",
        None,
    ),
    (
        "tree",
        "tree check (staged state)",
        "python3 scripts/check_tree.py",
        None,
    ),
    ("versions", "version check", "python3 scripts/hooks_run.py versions", None),
    ("ruff-check", "ruff check", "python3 scripts/hooks_run.py ruff-check", _PYTHON),
    (
        "ruff-format-check",
        "ruff format check",
        "python3 scripts/hooks_run.py ruff-format-check",
        _PYTHON,
    ),
    ("mypy", "mypy", "python3 scripts/hooks_run.py mypy", _PYTHON),
    ("web-lint", "web lint", "python3 scripts/hooks_run.py web-lint", _WEB),
    (
        "web-format-check",
        "web format check",
        "python3 scripts/hooks_run.py web-format-check",
        _WEB,
    ),
    (
        "web-typecheck",
        "web typecheck",
        "python3 scripts/hooks_run.py web-typecheck",
        _WEB,
    ),
)


def _load() -> object:
    module = cast(Any, importlib.import_module("yaml"))
    loaded: object = module.safe_load(
        (support.ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8")
    )
    return loaded


def config_problems(data: object) -> list[str]:
    """Return the closed-check problems of one hook configuration."""
    problems: list[str] = []
    if not isinstance(data, dict):
        return ["top level is not a mapping"]
    actual = set(data)
    expected = set(_TOP)
    for key in sorted(actual - expected):
        problems.append(f"unknown top-level key {key}")
    for key in sorted(expected - actual):
        problems.append(f"missing top-level key {key}")
    if data.get("minimum_pre_commit_version") != "4.7.0":
        problems.append("minimum_pre_commit_version is not 4.7.0")
    if data.get("default_stages") != ["pre-commit"]:
        problems.append("default_stages is not [pre-commit]")
    repos = data.get("repos")
    if not isinstance(repos, list) or len(repos) != 1 or not isinstance(repos[0], dict):
        problems.append("repos is not one local repo")
        return problems
    if repos[0].get("repo") != "local":
        problems.append("repo is not local")
    hooks = repos[0].get("hooks")
    if not isinstance(hooks, list):
        problems.append("hooks is not a list")
        return problems
    ids = [item.get("id") if isinstance(item, dict) else None for item in hooks]
    if ids != [row[0] for row in _HOOKS]:
        problems.append("hook ids are not the table in order")
    used: list[str] = []
    for index, item in enumerate(hooks):
        if not isinstance(item, dict):
            problems.append(f"hook {index + 1} is not a mapping")
            continue
        hook_id = item.get("id")
        label = hook_id if isinstance(hook_id, str) else str(index + 1)
        row = _HOOKS[index] if index < len(_HOOKS) else None
        stage = "always_run" if index < 5 else "files"
        allowed = set(_BASE) | {stage}
        for key in sorted(set(item) - allowed):
            problems.append(f"{label}: unknown key {key}")
        for key in sorted(allowed - set(item)):
            problems.append(f"{label}: missing key {key}")
        if row is None:
            continue
        if item.get("name") != row[1]:
            problems.append(f"{label}: name")
        if item.get("entry") != row[2]:
            problems.append(f"{label}: entry")
        if item.get("language") != "unsupported":
            problems.append(f"{label}: language")
        if item.get("pass_filenames") is not False:
            problems.append(f"{label}: pass_filenames")
        if stage == "always_run" and item.get("always_run") is not True:
            problems.append(f"{label}: always_run")
        if stage == "files" and item.get("files") != row[3]:
            problems.append(f"{label}: files")
        entry = item.get("entry")
        if not isinstance(entry, str):
            continue
        parts = entry.split()
        if len(parts) < 2 or parts[0] != "python3":
            problems.append(f"{label}: entry is not a python3 script")
            continue
        if not (support.ROOT / parts[1]).is_file():
            problems.append(f"{label}: missing {parts[1]}")
        if parts[1] == "scripts/hooks_run.py":
            if len(parts) != 3 or parts[2] not in hooks_run.TABLE:
                problems.append(f"{label}: hook id is not in the dispatcher table")
            else:
                used.append(parts[2])
    if sorted(used) != sorted(hooks_run.TABLE):
        problems.append("dispatcher ids are not used once each")
    return problems


class HooksConfig(unittest.TestCase):
    def test_config_matches_the_hook_table(self) -> None:
        self.assertEqual(config_problems(_load()), [])

    def test_closed_check_rejects_an_unknown_key(self) -> None:
        loaded = _load()
        self.assertIsInstance(loaded, dict)
        data = cast(dict[str, Any], loaded)
        repos = cast(list[dict[str, Any]], data["repos"])
        hooks = cast(list[dict[str, Any]], repos[0]["hooks"])
        for hook in hooks:
            if hook.get("id") == "docs":
                del hook["always_run"]
                hook["allways_run"] = True
        problems = config_problems(data)
        self.assertTrue(problems)
        self.assertTrue(
            any("docs" in item and "allways_run" in item for item in problems)
        )
        home = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(home, True))
        env = support.clean_env(home, [support.system_bin(home)])
        folder = home / "repo"
        folder.mkdir()
        module = cast(Any, importlib.import_module("yaml"))
        (folder / ".pre-commit-config.yaml").write_text(
            module.safe_dump(data), encoding="utf-8"
        )
        done = support.run(
            [
                sys.executable,
                "-m",
                "pre_commit",
                "validate-config",
                ".pre-commit-config.yaml",
            ],
            cwd=folder,
            env=env,
        )
        # Control: the framework itself does not refuse the mutated text. pre-commit 4.7.0 warns
        # about an unknown key at the root and on a repository and says nothing about one on a
        # hook, so the closed check above is the only thing that names it.
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertNotIn("allways_run", done.stdout + done.stderr)

    def test_files_filters(self) -> None:
        loaded = _load()
        self.assertIsInstance(loaded, dict)
        data = cast(dict[str, Any], loaded)
        repos = cast(list[dict[str, Any]], data["repos"])
        hooks = cast(list[dict[str, Any]], repos[0]["hooks"])
        expected = {
            "core/src/x.py": {6, 7, 8},
            "pyproject.toml": {6, 7, 8},
            "web/src/main.tsx": {9, 10, 11},
            "README.md": set(),
            "webx/a.ts": set(),
            "docs/web/a.md": set(),
        }
        for path, want in expected.items():
            with self.subTest(path=path):
                selected = {
                    index
                    for index, hook in enumerate(hooks, start=1)
                    if isinstance(hook.get("files"), str)
                    and re.search(cast(str, hook["files"]), path)
                }
                self.assertEqual(selected, want)

    def test_validate_config_accepts(self) -> None:
        home = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(home, True))
        env = support.clean_env(home, [support.system_bin(home)])
        folder = home / "repo"
        folder.mkdir()
        text = (support.ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8")
        (folder / ".pre-commit-config.yaml").write_text(text, encoding="utf-8")
        done = support.run(
            [
                sys.executable,
                "-m",
                "pre_commit",
                "validate-config",
                ".pre-commit-config.yaml",
            ],
            cwd=folder,
            env=env,
        )
        self.assertEqual(done.returncode, 0)
        self.assertEqual(done.stdout, "")
        self.assertEqual(done.stderr, "")
