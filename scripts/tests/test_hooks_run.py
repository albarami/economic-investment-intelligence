"""Dispatcher rows for the hooks that need uv or npm."""

from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import hooks_support as support

_IDS = (
    "ruff-check",
    "ruff-format-check",
    "mypy",
    "versions",
    "web-lint",
    "web-format-check",
    "web-typecheck",
)
_LINES = {
    "ruff-check": "uv|.|run --locked ruff check .",
    "ruff-format-check": "uv|.|run --locked ruff format --check .",
    "mypy": "uv|.|run --locked mypy",
    "versions": "uv|.|run --locked python scripts/check_versions.py",
    "web-lint": "npm|web|run lint",
    "web-format-check": "npm|web|run format:check",
    "web-typecheck": "npm|web|run typecheck",
}
_UV_MISSING = (
    "hooks_run: uv was not found on PATH; "
    "install uv at the version recorded in pins.toml\n"
)
_NPM_MISSING = (
    "hooks_run: npm was not found on PATH; install Node and npm at the versions "
    "recorded in pins.toml, then run in web/: npm ci\n"
)
_MODULES_MISSING = (
    "hooks_run: web/node_modules is missing; install Node and npm at the versions "
    "recorded in pins.toml, then run in web/: npm ci\n"
)
_UNKNOWN = (
    "hooks_run: unknown hook 'nosuch'; known: mypy, ruff-check, ruff-format-check, "
    "versions, web-format-check, web-lint, web-typecheck\n"
)


class HooksRun(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.home = Path(self._tmp.name)
        self.stubs = self.home / "stubs"
        support.write_stubs(self.stubs, ["uv", "npm"])
        self.pybin = support.python_bin(self.home)
        self.work = self.home / "work"
        scripts = self.work / "scripts"
        scripts.mkdir(parents=True)
        shutil.copy2(
            support.ROOT / "scripts" / "hooks_run.py", scripts / "hooks_run.py"
        )
        (self.work / "web" / "node_modules").mkdir(parents=True)
        self.env = support.clean_env(self.home, [self.stubs, self.pybin])

    def _run(
        self, hook_id: str, env: dict[str, str] | None = None
    ) -> tuple[int, str, str]:
        done = support.run(
            [sys.executable, "-I", "scripts/hooks_run.py", hook_id],
            cwd=self.work,
            env=env or self.env,
        )
        return done.returncode, done.stdout, done.stderr

    def _clear_log(self) -> None:
        log = self.home / "stub.log"
        if log.exists():
            log.unlink()

    def test_each_id_runs_its_command(self) -> None:
        for hook_id in _IDS:
            with self.subTest(hook_id=hook_id):
                self._clear_log()
                status, _stdout, stderr = self._run(hook_id)
                self.assertEqual(status, 0, stderr)
                self.assertEqual(
                    support.stub_log(self.home / "stub.log"), [_LINES[hook_id]]
                )

    def test_status_passes_through(self) -> None:
        (self.stubs / "uv.exit").write_text("3\n", encoding="utf-8")
        (self.stubs / "npm.exit").write_text("3\n", encoding="utf-8")
        for hook_id in _IDS:
            with self.subTest(hook_id=hook_id):
                status, _stdout, stderr = self._run(hook_id)
                self.assertEqual(status, 3, stderr)

    def test_missing_program_names_the_remedy(self) -> None:
        no_uv = support.clean_env(self.home, [self.pybin])
        status, stdout, stderr = self._run("ruff-check", no_uv)
        self.assertEqual(status, 1)
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, _UV_MISSING)
        no_npm = support.clean_env(self.home, [self.pybin])
        status, stdout, stderr = self._run("web-lint", no_npm)
        self.assertEqual(status, 1)
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, _NPM_MISSING)

    def test_web_needs_node_modules(self) -> None:
        shutil.rmtree(self.work / "web" / "node_modules")
        self._clear_log()
        status, stdout, stderr = self._run("web-lint")
        self.assertEqual(status, 1)
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, _MODULES_MISSING)
        self.assertEqual(support.stub_log(self.home / "stub.log"), [])

    def test_unknown_id(self) -> None:
        status, stdout, stderr = self._run("nosuch")
        self.assertEqual(status, 2)
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, _UNKNOWN)
