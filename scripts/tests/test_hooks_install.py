"""Installer refusals. Every install happens in a scratch repository."""

from __future__ import annotations

import hashlib
import os
import shutil
import stat
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import hooks_support as support

import hooks_install

_BEFORE: dict[str, object] = {}
_FOREIGN = (
    "hooks_install: refused: a pre-commit hook already exists and the framework "
    "did not write it; this installer never moves, replaces or deletes a hook "
    '(see README.md, section "Commit hooks")\n'
)
_LEGACY = (
    "hooks_install: refused: a pre-commit.legacy file exists and the framework's "
    "hook would run it; this installer never moves, replaces or deletes a hook "
    '(see README.md, section "Commit hooks")\n'
)


def setUpModule() -> None:
    global _BEFORE
    _BEFORE = support.snapshot(support.ROOT)


def tearDownModule() -> None:
    if support.snapshot(support.ROOT) != _BEFORE:
        raise AssertionError("real hooks or git configuration changed")


class HooksInstall(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.home = Path(self._tmp.name)
        self.env = support.clean_env(self.home, [support.system_bin(self.home)])
        self.repo = self.home / "repo"
        self.repo.mkdir()
        self.assertEqual(
            support.git(self.repo, self.env, "init", "-q", "-b", "main").returncode, 0
        )
        scripts = self.repo / "scripts"
        scripts.mkdir()
        shutil.copy2(
            support.ROOT / "scripts" / "hooks_install.py", scripts / "hooks_install.py"
        )
        shutil.copy2(
            support.ROOT / ".pre-commit-config.yaml",
            self.repo / ".pre-commit-config.yaml",
        )

    def _install(self, cwd: Path | None = None) -> tuple[int, str, str]:
        done = support.run(
            [sys.executable, "scripts/hooks_install.py"],
            cwd=cwd or self.repo,
            env=self.env,
        )
        return done.returncode, done.stdout, done.stderr

    def _state(
        self, repo: Path | None = None
    ) -> tuple[tuple[tuple[str, int, str], ...], str]:
        root = repo or self.repo
        hooks = root / ".git" / "hooks"
        files: list[tuple[str, int, str]] = []
        for path in sorted(hooks.iterdir(), key=lambda item: item.name):
            info = path.lstat()
            if not stat.S_ISREG(info.st_mode):
                continue
            data = path.read_bytes()
            files.append((path.name, len(data), hashlib.sha256(data).hexdigest()))
        config = (root / ".git" / "config").read_bytes()
        return tuple(files), hashlib.sha256(config).hexdigest()

    def test_fresh_repository_installs_from_configuration(self) -> None:
        first_status, first_out, first_err = self._install()
        self.assertEqual(first_status, 0, first_err)
        self.assertIn("pre-commit installed at .git/hooks/pre-commit", first_out)
        hook = self.repo / ".git" / "hooks" / "pre-commit"
        self.assertEqual(hook.stat().st_mode & 0o777, 0o755)
        content = hook.read_bytes()
        self.assertIn(hooks_install.FRAMEWORK_MARKER, content)
        self.assertIn(
            b"hook-impl --config=.pre-commit-config.yaml --hook-type=pre-commit",
            content,
        )
        self.assertFalse((self.repo / ".git" / "hooks" / "pre-commit.legacy").exists())
        second_status, _second_out, second_err = self._install()
        self.assertEqual(second_status, 0, second_err)
        self.assertEqual(hook.read_bytes(), content)

    def test_foreign_hook_is_refused_and_untouched(self) -> None:
        hook = self.repo / ".git" / "hooks" / "pre-commit"
        hook.write_text("#!/bin/sh\necho foreign\n", encoding="utf-8")
        hook.chmod(0o755)
        before = self._state()
        status, _stdout, stderr = self._install()
        self.assertEqual(status, 1)
        self.assertEqual(stderr, _FOREIGN)
        self.assertEqual(self._state(), before)

    def test_orphan_legacy_file_is_refused_and_untouched(self) -> None:
        legacy = self.repo / ".git" / "hooks" / "pre-commit.legacy"
        legacy.write_text("#!/bin/sh\necho ORPHAN-LEGACY-RAN\n", encoding="utf-8")
        legacy.chmod(0o755)
        before = self._state()
        status, _stdout, stderr = self._install()
        self.assertEqual(status, 1)
        self.assertEqual(stderr, _LEGACY)
        self.assertEqual(self._state(), before)

    def test_hooks_path_set_is_refused(self) -> None:
        configured = support.git(
            self.repo, self.env, "config", "core.hooksPath", "hooks-elsewhere"
        )
        self.assertEqual(configured.returncode, 0, configured.stderr)
        before = self._state()
        status, _stdout, stderr = self._install()
        self.assertEqual(status, 1)
        self.assertEqual(
            stderr,
            "hooks_install: refused: core.hooksPath is set; this installer does not change it\n",
        )
        self.assertEqual(self._state(), before)
        self.assertFalse((self.repo / "hooks-elsewhere").exists())

    def test_linked_work_tree_is_refused(self) -> None:
        committed = support.git(
            self.repo, self.env, "commit", "--allow-empty", "-q", "-m", "chore: empty"
        )
        self.assertEqual(committed.returncode, 0, committed.stderr)
        linked = self.home / "linked"
        added = support.git(
            self.repo, self.env, "worktree", "add", "--detach", str(linked)
        )
        self.assertEqual(added.returncode, 0, added.stderr)
        scripts = linked / "scripts"
        scripts.mkdir()
        shutil.copy2(
            self.repo / "scripts" / "hooks_install.py", scripts / "hooks_install.py"
        )
        shutil.copy2(
            self.repo / ".pre-commit-config.yaml", linked / ".pre-commit-config.yaml"
        )
        before = self._state()
        status, _stdout, stderr = self._install(linked)
        self.assertEqual(status, 1)
        self.assertEqual(
            stderr,
            "hooks_install: refused: this is a linked work tree; hooks are shared, "
            "so run it in the main clone\n",
        )
        self.assertEqual(self._state(), before)

    def test_folder_inside_another_checkout_is_refused(self) -> None:
        self.assertEqual(support.git(self.repo, self.env, "add", "-A").returncode, 0)
        committed = support.git(
            self.repo, self.env, "commit", "-q", "-m", "chore: base"
        )
        self.assertEqual(committed.returncode, 0, committed.stderr)
        sub = self.repo / "sub"
        scripts = sub / "scripts"
        scripts.mkdir(parents=True)
        shutil.copy2(
            self.repo / "scripts" / "hooks_install.py", scripts / "hooks_install.py"
        )
        shutil.copy2(
            self.repo / ".pre-commit-config.yaml", sub / ".pre-commit-config.yaml"
        )
        before = self._state()
        status, stdout, stderr = self._install(sub)
        self.assertEqual(status, 2, stdout + stderr)
        self.assertEqual(stderr, "hooks_install: refused: not a git checkout\n")
        self.assertEqual(self._state(), before)

    def test_missing_configuration_is_refused(self) -> None:
        (self.repo / ".pre-commit-config.yaml").unlink()
        status, _stdout, stderr = self._install()
        self.assertEqual(status, 1)
        self.assertEqual(
            stderr, "hooks_install: refused: .pre-commit-config.yaml is missing\n"
        )

    def test_marker_equals_the_framework_constant(self) -> None:
        module = __import__("importlib").import_module(
            "pre_commit.commands.install_uninstall"
        )
        current = module.CURRENT_HASH
        self.assertIs(type(current), bytes)
        self.assertEqual(current, hooks_install.FRAMEWORK_MARKER)

    def test_argument_list_has_no_force_flag(self) -> None:
        self.assertEqual(
            hooks_install.INSTALL_ARGV,
            (
                "install",
                "--hook-type",
                "pre-commit",
                "--config",
                ".pre-commit-config.yaml",
            ),
        )

    def test_picture_sees_a_changed_hook(self) -> None:
        hook = self.repo / ".git" / "hooks" / "pre-commit"
        hook.write_text("#!/bin/sh\necho alpha\n", encoding="utf-8")
        before = support.snapshot(self.repo)
        hook.write_text("#!/bin/sh\necho bravo\n", encoding="utf-8")
        when = hook.stat().st_mtime
        os.utime(hook, (when + 1, when + 1))
        after = support.snapshot(self.repo)
        self.assertNotEqual(after, before)
        configured = support.git(self.repo, self.env, "config", "core.hooksPath", "x")
        self.assertEqual(configured.returncode, 0, configured.stderr)
        changed = support.snapshot(self.repo)
        self.assertNotEqual(changed, after)

    def test_real_repository_untouched(self) -> None:
        self.assertEqual(support.snapshot(support.ROOT), _BEFORE)
