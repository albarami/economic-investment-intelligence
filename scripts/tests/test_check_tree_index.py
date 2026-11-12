#!/usr/bin/env python3
"""Black-box tests for scripts/check_tree.py.

These tests plant a difference between git's index and the work tree and
prove that the env-example rule judges the staged content and mode of
.env.example and that tracked .gitignore files equal their staged content.
They are run by the same command as the other module, from
the repository root:

    python3 -m unittest discover -s scripts/tests -p 'test_*.py' -v

Only the Python standard library is used.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from pathlib import Path

import test_check_tree as base

ENV_EXAMPLE_UNJUDGED = (
    "FAIL env-example: .env.example: cannot be judged: "
    ".gitignore differs from its staged content"
)
ROOT_GITIGNORE_DIFFERENT = (
    "FAIL tracked-ignored: .gitignore: differs from its staged content"
)


def stage_data_rule_removal(root: Path, index_flag: str) -> None:
    """Stage a root ignore file without ``data/``, restore it, then set the flag."""
    path = root / ".gitignore"
    original = path.read_text(encoding="utf-8")
    base.drop_gitignore_line(root, "data/")
    base.git(root, "add", ".gitignore")
    path.write_text(original, encoding="utf-8")
    base.git(root, "update-index", index_flag, ".gitignore")


class CheckTreeIndexTests(base.CheckTreeCase):

    def test_env_example_staged_value_hidden_by_work_tree_fails(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = base.make_fixture(folder)
            path = root / ".env.example"
            clean = path.read_text(encoding="utf-8")
            number = clean.splitlines().index("EII_STORE=") + 1
            path.write_text(
                clean.replace("EII_STORE=\n", "EII_STORE=postgres\n"),
                encoding="utf-8")
            base.git(root, "add", ".env.example")
            path.write_text(clean, encoding="utf-8")
            done = base.run_check(root)
            self.assertEqual(done.returncode, 1)
            self.assertEqual(done.stdout.splitlines(), [
                f"FAIL env-example: .env.example:{number}: "
                "not a name with an empty value",
                "FAIL env-example: .env.example: names differ from the pinned list",
                "checked 8 rules: 2 failure(s)",
            ])

    def test_env_example_unstaged_edit_is_not_judged(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = base.make_fixture(folder)
            path = root / ".env.example"
            text = path.read_text(encoding="utf-8")
            path.write_text(
                text.replace("EII_STORE=\n", "EII_STORE=postgres\n"),
                encoding="utf-8")
            self.assert_clean(base.run_check(root))

    def test_env_example_staged_symbolic_link_fails(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = base.make_fixture(folder)
            outside = Path(folder) / "outside"
            outside.mkdir()
            target = outside / ".env.example"
            shutil.copyfile(root / ".env.example", target)
            (root / ".env.example").unlink()
            os.symlink(target, root / ".env.example")
            base.git(root, "add", ".env.example")
            done = base.run_check(root)
            self.assertEqual(done.returncode, 1)
            self.assertEqual(done.stdout.splitlines(), [
                "FAIL env-example: .env.example: not a regular file in the index",
                "checked 8 rules: 1 failure(s)",
            ])

    def test_env_example_deleted_in_work_tree_is_judged_from_the_index(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = base.make_fixture(folder)
            (root / ".env.example").unlink()
            self.assert_clean(base.run_check(root))

    def test_assume_unchanged_hides_staged_removal_of_data_rule(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = base.make_fixture(folder)
            stage_data_rule_removal(root, "--assume-unchanged")
            done = base.run_check(root)
            self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
            self.assert_line_starting(done, "FAIL data-ignored:")

    def test_skip_worktree_hides_staged_removal_of_data_rule(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = base.make_fixture(folder)
            stage_data_rule_removal(root, "--skip-worktree")
            done = base.run_check(root)
            self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
            self.assert_line_starting(done, "FAIL data-ignored:")

    def test_assume_unchanged_reports_env_example_and_root_ignore_file(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = base.make_fixture(folder)
            stage_data_rule_removal(root, "--assume-unchanged")
            done = base.run_check(root)
            self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
            lines = done.stdout.splitlines()
            self.assertEqual(lines.count(ENV_EXAMPLE_UNJUDGED), 1)
            self.assertEqual(lines.count(ROOT_GITIGNORE_DIFFERENT), 1)

    def test_work_tree_gitignore_symlink_is_not_the_staged_file(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = base.make_fixture(folder)
            payload = (root / ".gitignore").read_bytes()
            target = Path(folder) / "same-bytes"
            target.write_bytes(payload)
            (root / ".gitignore").unlink()
            os.symlink(target, root / ".gitignore")
            done = base.run_check(root)
            self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
            self.assert_line_starting(done, "FAIL data-ignored:")
            self.assertIn(ROOT_GITIGNORE_DIFFERENT, done.stdout.splitlines())

    def test_index_symlink_gitignore_is_not_the_staged_file(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = base.make_fixture(folder)
            blob = base.git(
                root, "hash-object", "-w", ".gitignore").stdout.decode("utf-8").strip()
            base.git(
                root, "update-index", "--cacheinfo",
                f"120000,{blob},.gitignore")
            done = base.run_check(root)
            self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
            self.assertIn(ROOT_GITIGNORE_DIFFERENT, done.stdout.splitlines())

    def test_unsynced_nested_gitignore_affects_only_its_folder(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = base.make_fixture(folder)
            nested = root / "web" / ".gitignore"
            nested.write_text("!.env\n", encoding="utf-8")
            base.git(root, "add", "web/.gitignore")
            nested.write_text("# comment\n", encoding="utf-8")
            done = base.run_check(root)
            self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
            lines = done.stdout.splitlines()
            self.assertIn(
                "FAIL secrets-ignored: web/.env: not ignored by a committed rule",
                lines)
            self.assertIn(
                "FAIL tracked-ignored: web/.gitignore: differs from its staged content",
                lines)
            self.assertNotIn(ENV_EXAMPLE_UNJUDGED, lines)
            for line in lines:
                if not line.startswith("FAIL "):
                    continue
                path = line.split(": ", 2)[1]
                self.assertTrue(path.startswith("web/"), line)

    def test_synced_nested_gitignore_passes(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = base.make_fixture(folder)
            (root / "docs" / ".gitignore").write_text("*.tmp\n", encoding="utf-8")
            base.git(root, "add", "docs/.gitignore")
            self.assert_clean(base.run_check(root))

    def test_unsynced_harmless_nested_gitignore_reports_only_itself(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = base.make_fixture(folder)
            nested = root / "docs" / ".gitignore"
            nested.write_text("*.tmp\n", encoding="utf-8")
            base.git(root, "add", "docs/.gitignore")
            nested.write_text("# comment\n", encoding="utf-8")
            done = base.run_check(root)
            self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
            self.assertEqual(done.stdout.splitlines(), [
                "FAIL tracked-ignored: docs/.gitignore: differs from its staged content",
                "checked 8 rules: 1 failure(s)",
            ])


if __name__ == "__main__":
    unittest.main()
