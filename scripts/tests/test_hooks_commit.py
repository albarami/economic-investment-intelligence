"""Commits in a scratch repository run the hooks from the configuration."""

from __future__ import annotations

import random
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import hooks_support as support

_BEFORE: dict[str, object] = {}
GUARD = "commit guard (no staged local secret value)"
GITLEAKS = "gitleaks (staged changes)"
DOCS = "documentation check (paths, addresses, tokens, identifier numbers)"
TREE = "tree check (staged state)"
VERSIONS = "version check"
RUFF = "ruff check"
RUFF_FMT = "ruff format check"
MYPY = "mypy"
WEB_LINT = "web lint"
WEB_FMT = "web format check"
WEB_TYPES = "web typecheck"
ALWAYS = (GUARD, GITLEAKS, DOCS, TREE, VERSIONS)
PYTHON = (RUFF, RUFF_FMT, MYPY)
WEB = (WEB_LINT, WEB_FMT, WEB_TYPES)
ORDER = ALWAYS + PYTHON + WEB


def setUpModule() -> None:
    global _BEFORE
    _BEFORE = support.snapshot(support.ROOT)


def tearDownModule() -> None:
    if support.snapshot(support.ROOT) != _BEFORE:
        raise AssertionError("real hooks or git configuration changed")


class HooksCommit(unittest.TestCase):
    _tmp: tempfile.TemporaryDirectory[str]
    parent: Path
    base_env: dict[str, str]
    base_repo: Path

    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        cls.parent = Path(cls._tmp.name)
        support.write_stubs(cls.parent / "stubs", ["uv", "npm"])
        cls.base_env = support.clean_env(
            cls.parent, [cls.parent / "stubs", support.system_bin(cls.parent)]
        )
        cls.base_repo = support.scratch_repo(cls.parent, cls.base_env, True)
        (cls.base_repo / "web" / "node_modules").mkdir(parents=True, exist_ok=True)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    def _case(self) -> tuple[Path, dict[str, str], Path]:
        home_tmp = tempfile.TemporaryDirectory()
        self.addCleanup(home_tmp.cleanup)
        home = Path(home_tmp.name)
        support.write_stubs(home / "stubs", ["uv", "npm"])
        support.system_bin(home)
        repo = home / "repo"
        support.clone_scratch(type(self).base_repo, repo)
        env = support.clean_env(home, [home / "stubs", home / "sysbin"])
        return home, env, repo

    def _head(self, repo: Path, env: dict[str, str]) -> str:
        done = support.git(repo, env, "rev-parse", "HEAD")
        self.assertEqual(done.returncode, 0, done.stderr)
        return done.stdout.strip()

    def _commit(self, repo: Path, env: dict[str, str], message: str) -> tuple[int, str]:
        done = support.run(["git", "commit", "-m", message], cwd=repo, env=env)
        return done.returncode, done.stdout + done.stderr

    def _assert_report(
        self,
        output: str,
        passed: tuple[str, ...],
        skipped: tuple[str, ...],
        failed: tuple[str, ...] = (),
    ) -> None:
        report = support.hook_report(output)
        self.assertEqual([name for name, _status in report], list(ORDER), output)
        status = dict(report)
        for name in passed:
            self.assertEqual(status[name], "Passed", output)
        for name in skipped:
            self.assertEqual(status[name], "Skipped", output)
        for name in failed:
            self.assertEqual(status[name], "Failed", output)
        self.assertEqual(
            {name for name, kind in report if kind == "Failed"}, set(failed)
        )

    def test_clean_documentation_commit_passes(self) -> None:
        home, env, repo = self._case()
        (repo / "n.md").write_text("hello\n", encoding="utf-8")
        self.assertEqual(support.git(repo, env, "add", "--", "n.md").returncode, 0)
        before = self._head(repo, env)
        status, output = self._commit(repo, env, "docs: add note")
        self.assertEqual(status, 0, output)
        self.assertNotEqual(self._head(repo, env), before)
        self._assert_report(output, ALWAYS, PYTHON + WEB)
        self.assertEqual(
            support.stub_log(home / "stub.log"),
            ["uv|.|run --locked python scripts/check_versions.py"],
        )

    def test_python_commit_runs_python_hooks(self) -> None:
        home, env, repo = self._case()
        (repo / "m.py").write_text("x = 1\n", encoding="utf-8")
        self.assertEqual(support.git(repo, env, "add", "--", "m.py").returncode, 0)
        status, output = self._commit(repo, env, "chore: add module")
        self.assertEqual(status, 0, output)
        self._assert_report(output, ALWAYS + PYTHON, WEB)
        self.assertEqual(
            support.stub_log(home / "stub.log"),
            [
                "uv|.|run --locked python scripts/check_versions.py",
                "uv|.|run --locked ruff check .",
                "uv|.|run --locked ruff format --check .",
                "uv|.|run --locked mypy",
            ],
        )

    def test_web_commit_runs_web_hooks(self) -> None:
        home, env, repo = self._case()
        (repo / "web").mkdir(exist_ok=True)
        (repo / "web" / "w.ts").write_text("export {}\n", encoding="utf-8")
        self.assertEqual(support.git(repo, env, "add", "--", "web/w.ts").returncode, 0)
        status, output = self._commit(repo, env, "chore: add web file")
        self.assertEqual(status, 0, output)
        self._assert_report(output, ALWAYS + WEB, PYTHON)
        self.assertEqual(
            support.stub_log(home / "stub.log"),
            [
                "uv|.|run --locked python scripts/check_versions.py",
                "npm|web|run lint",
                "npm|web|run format:check",
                "npm|web|run typecheck",
            ],
        )

    def test_failing_command_refuses_the_commit(self) -> None:
        home, env, repo = self._case()
        (home / "stubs" / "uv.exit").write_text("1\n", encoding="utf-8")
        (repo / "m.py").write_text("x = 1\n", encoding="utf-8")
        self.assertEqual(support.git(repo, env, "add", "--", "m.py").returncode, 0)
        before = self._head(repo, env)
        status, output = self._commit(repo, env, "chore: add module")
        self.assertEqual(status, 1, output)
        self.assertEqual(self._head(repo, env), before)
        self._assert_report(
            output, (GUARD, GITLEAKS, DOCS, TREE), WEB, (VERSIONS, RUFF, RUFF_FMT, MYPY)
        )

    def test_installed_hooks_run_all_files(self) -> None:
        done = support.run(
            [sys.executable, "-m", "pre_commit", "run", "--all-files"],
            cwd=type(self).base_repo,
            env=type(self).base_env,
        )
        output = done.stdout + done.stderr
        self.assertEqual(done.returncode, 0, output)
        self._assert_report(output, ORDER, ())

    def test_identifier_number_is_refused(self) -> None:
        _home, env, repo = self._case()
        digits = support.digit_run(random.Random(support.SEED), 8)
        (repo / "note.md").write_text("id " + digits + " end\n", encoding="utf-8")
        self.assertEqual(support.git(repo, env, "add", "--", "note.md").returncode, 0)
        before = self._head(repo, env)
        status, output = self._commit(repo, env, "docs: add note")
        self.assertEqual(status, 1, output)
        self.assertEqual(self._head(repo, env), before)
        self._assert_report(
            output, (GUARD, GITLEAKS, TREE, VERSIONS), PYTHON + WEB, (DOCS,)
        )
        self.assertIn(
            "FAIL identifier-number: note.md:1: identifier-shaped number "
            "(exactly 8 or 11 digits): " + digits,
            output,
        )

    def test_secret_shaped_token_is_refused_by_both_scanners(self) -> None:
        _home, env, repo = self._case()
        token = support.cloud_key(random.Random(support.SEED))
        (repo / "cfg.txt").write_text("k = " + token + "\n", encoding="utf-8")
        self.assertEqual(support.git(repo, env, "add", "--", "cfg.txt").returncode, 0)
        before = self._head(repo, env)
        status, output = self._commit(repo, env, "chore: add config")
        self.assertEqual(status, 1, output)
        self.assertEqual(self._head(repo, env), before)
        self._assert_report(
            output, (GUARD, TREE, VERSIONS), PYTHON + WEB, (GITLEAKS, DOCS)
        )
        self.assertIn("RuleID:      aws-access-token", output)
        self.assertIn(
            "FAIL secret: cfg.txt:1: secret-shaped token: (matched text not shown)",
            output,
        )
        support.assert_free_of(self, output, token)

    def test_local_secret_value_is_refused_by_the_guard(self) -> None:
        _home, env, repo = self._case()
        value = support.random_value(random.Random(support.SEED), 30)
        env = dict(env)
        env["ANTHROPIC_API_KEY"] = value
        (repo / "n.md").write_text(value + "\n", encoding="utf-8")
        self.assertEqual(support.git(repo, env, "add", "--", "n.md").returncode, 0)
        before = self._head(repo, env)
        status, output = self._commit(repo, env, "docs: add note")
        self.assertEqual(status, 1, output)
        self.assertEqual(self._head(repo, env), before)
        self._assert_report(
            output, (GITLEAKS, DOCS, TREE, VERSIONS), PYTHON + WEB, (GUARD,)
        )
        self.assertIn(
            'guard: refused: staged content of "n.md" holds the local value of '
            "ANTHROPIC_API_KEY",
            output,
        )
        support.assert_free_of(self, output, value)

    def test_force_added_env_is_refused_by_the_tree_hook(self) -> None:
        _home, env, repo = self._case()
        (repo / ".env").write_text("EII_STORE=embedded\n", encoding="utf-8")
        added = support.git(repo, env, "add", "-f", "--", ".env")
        self.assertEqual(added.returncode, 0, added.stderr)
        before = self._head(repo, env)
        status, output = self._commit(repo, env, "chore: add env")
        self.assertEqual(status, 1, output)
        self.assertEqual(self._head(repo, env), before)
        self._assert_report(
            output, (GUARD, GITLEAKS, DOCS, VERSIONS), PYTHON + WEB, (TREE,)
        )
        self.assertIn(
            "FAIL tracked-ignored: .env: tracked although ignored by .gitignore:",
            output,
        )
