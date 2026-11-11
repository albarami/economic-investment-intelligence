#!/usr/bin/env python3
"""Black-box tests for scripts/check_tree.py.

These tests plant a difference between git's index and the work tree and
prove that the env-example rule judges the staged content and mode of
.env.example. They are run by the same command as the other module, from
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


if __name__ == "__main__":
    unittest.main()
