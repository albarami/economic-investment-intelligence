#!/usr/bin/env python3
"""Black-box tests for scripts/check_tree.py.

Run from the repository root:

    python3 -m unittest discover -s scripts/tests -p 'test_*.py' -v

Every test runs the real script in a child process (``sys.executable`` plus
the script path found from this file's own location) and asserts on its exit
code and standard output. Nothing is mocked. Fixtures are throw-away git
work trees built inside ``tempfile.TemporaryDirectory()``; git's global and
system configuration are switched off in every child process. Every rule of
the check has at least one planted violation, and one test proves that the
check changes no file.

Only the Python standard library is used.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "check_tree.py"

PINNED_FOLDERS = (
    "contracts", "core", "custodian", "product", "web",
    "evals", "gateway", "infra", "scripts", "docs",
)

# Each pattern is the only .gitignore line covering at least one probe of its rule.
PATTERN_RULES = (
    ("data/", "data-ignored"),
    (".env", "secrets-ignored"),
    (".env.*", "secrets-ignored"),
    ("*.pem", "secrets-ignored"),
    ("*.key", "secrets-ignored"),
    (".venv/", "generated-ignored"),
    ("node_modules/", "generated-ignored"),
    ("dist/", "generated-ignored"),
    ("__pycache__/", "generated-ignored"),
    (".pytest_cache/", "generated-ignored"),
    ("*.egg-info/", "generated-ignored"),
    (".coverage.*", "generated-ignored"),
    ("*.tsbuildinfo", "generated-ignored"),
    (".eslintcache", "generated-ignored"),
)

FAIL_LINE = re.compile(r"^FAIL [a-z-]+: [^ ]+: .+$")


def child_env(extra: dict | None = None) -> dict:
    env = dict(os.environ)
    env["GIT_CONFIG_GLOBAL"] = os.devnull
    env["GIT_CONFIG_SYSTEM"] = os.devnull
    if extra:
        env.update(extra)
    return env


def git(root: Path, *args: str, env_extra: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        env=child_env(env_extra), capture_output=True, check=True)


def run_check(root: Path | None = None, args: tuple = (),
              env_extra: dict | None = None) -> subprocess.CompletedProcess:
    command = [sys.executable, str(SCRIPT)]
    if root is not None:
        command += ["--root", str(root)]
    command += list(args)
    return subprocess.run(
        command, env=child_env(env_extra), capture_output=True, text=True)


def make_fixture(folder: str) -> Path:
    """A clean staged work tree: the ten pinned folders plus the real root files."""
    root = Path(folder) / "work"
    root.mkdir()
    git(root, "init", "-q")
    for name in PINNED_FOLDERS:
        pinned = root / name
        pinned.mkdir()
        (pinned / "README.md").write_text("fixture\n", encoding="utf-8")
    shutil.copyfile(REPO_ROOT / ".gitignore", root / ".gitignore")
    shutil.copyfile(REPO_ROOT / ".env.example", root / ".env.example")
    git(root, "add", "-A")
    return root


def drop_gitignore_line(root: Path, line: str) -> None:
    path = root / ".gitignore"
    lines = path.read_text(encoding="utf-8").splitlines()
    kept = [item for item in lines if item != line]
    if len(kept) != len(lines) - 1:
        raise AssertionError(f"{line!r} was not on exactly one .gitignore line")
    path.write_text("\n".join(kept) + "\n", encoding="utf-8")


def tree_snapshot(root: Path) -> dict:
    """Every file under root outside .git/, mapped to its bytes."""
    snapshot = {}
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root)
        if rel.parts[0] == ".git":
            continue
        if path.is_file():
            snapshot[rel.as_posix()] = path.read_bytes()
    return snapshot


class CheckTreeTests(unittest.TestCase):

    def assert_clean(self, done: subprocess.CompletedProcess) -> None:
        self.assertEqual(done.returncode, 0, done.stderr + done.stdout)
        self.assertEqual(done.stdout.splitlines(), ["checked 8 rules: OK"])

    def assert_line_starting(self, done: subprocess.CompletedProcess, prefix: str) -> None:
        lines = done.stdout.splitlines()
        self.assertTrue(
            any(line.startswith(prefix) for line in lines),
            f"no line starting {prefix!r} in output: {done.stdout!r}")

    def test_real_repository_passes(self):
        self.assert_clean(run_check(REPO_ROOT))

    def test_clean_fixture_passes(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assert_clean(run_check(make_fixture(folder)))

    def test_missing_pinned_folder_fails(self):
        for name in PINNED_FOLDERS:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as folder:
                root = make_fixture(folder)
                git(root, "rm", "-r", "-q", "--cached", name)
                shutil.rmtree(root / name)
                done = run_check(root)
                self.assertEqual(done.returncode, 1)
                self.assert_line_starting(done, f"FAIL committed-folder: {name}:")

    def test_pinned_folder_with_no_tracked_file_fails(self):
        with tempfile.TemporaryDirectory() as folder:
            root = make_fixture(folder)
            git(root, "rm", "-q", "--cached", "core/README.md")
            done = run_check(root)
            self.assertEqual(done.returncode, 1)
            self.assertIn(
                "FAIL committed-folder: core: no tracked file",
                done.stdout.splitlines())

    def test_unexpected_top_level_folder_fails(self):
        with tempfile.TemporaryDirectory() as folder:
            root = make_fixture(folder)
            (root / "extras").mkdir()
            (root / "extras" / "a.txt").write_text("x\n", encoding="utf-8")
            git(root, "add", "extras/a.txt")
            done = run_check(root)
            self.assertEqual(done.returncode, 1)
            self.assert_line_starting(done, "FAIL top-level-folder: extras:")

    def test_github_folder_is_allowed(self):
        with tempfile.TemporaryDirectory() as folder:
            root = make_fixture(folder)
            workflows = root / ".github" / "workflows"
            workflows.mkdir(parents=True)
            (workflows / "x.yml").write_text("x: y\n", encoding="utf-8")
            git(root, "add", ".github/workflows/x.yml")
            self.assert_clean(run_check(root))

    def test_tracked_file_under_data_fails(self):
        with tempfile.TemporaryDirectory() as folder:
            root = make_fixture(folder)
            (root / "data").mkdir()
            (root / "data" / "a.txt").write_text("x\n", encoding="utf-8")
            git(root, "add", "-f", "data/a.txt")
            done = run_check(root)
            self.assertEqual(done.returncode, 1)
            self.assert_line_starting(done, "FAIL data-untracked: data/a.txt:")

    def test_tracked_path_named_data_fails(self):
        with tempfile.TemporaryDirectory() as folder:
            root = make_fixture(folder)
            (root / "data").write_text("x\n", encoding="utf-8")
            git(root, "add", "-f", "data")
            done = run_check(root)
            self.assertEqual(done.returncode, 1)
            self.assert_line_starting(done, "FAIL data-untracked: data:")

    def test_data_as_symbolic_link_fails(self):
        with tempfile.TemporaryDirectory() as folder:
            root = make_fixture(folder)
            target = Path(folder) / "target"
            target.mkdir()
            os.symlink(target, root / "data")
            done = run_check(root)
            self.assertEqual(done.returncode, 1)
            self.assertIn(
                "FAIL data-untracked: data: not a real directory",
                done.stdout.splitlines())

    def test_probes_beyond_a_symbolic_link_count_as_not_ignored(self):
        with tempfile.TemporaryDirectory() as folder:
            root = make_fixture(folder)
            target = Path(folder) / "target"
            target.mkdir()
            os.symlink(target, root / "data")
            done = run_check(root)
            self.assertEqual(done.returncode, 1)
            self.assertEqual(done.stdout.splitlines(), [
                "FAIL data-untracked: data: not a real directory",
                "FAIL data-ignored: data/public_cache/x: not ignored by a committed rule",
                "FAIL data-ignored: data/vault/x: not ignored by a committed rule",
                "FAIL data-ignored: data/releases/x/manifest.json: not ignored by a committed rule",
                "FAIL data-ignored: data/ledger_local.sqlite: not ignored by a committed rule",
                "FAIL data-ignored: data/logs/x.jsonl: not ignored by a committed rule",
                "FAIL data-ignored: data/freeze/x/SHA256SUMS: not ignored by a committed rule",
                "checked 8 rules: 7 failure(s)",
            ])

    def test_data_folder_absent_passes(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assert_clean(run_check(make_fixture(folder)))

    def test_data_folder_present_and_ignored_passes(self):
        with tempfile.TemporaryDirectory() as folder:
            root = make_fixture(folder)
            (root / "data" / "public_cache").mkdir(parents=True)
            (root / "data" / "public_cache" / "a.bin").write_bytes(b"x\n")
            git(root, "add", "-A")
            self.assert_clean(run_check(root))

    def test_required_ignore_pattern_missing_fails(self):
        for pattern, rule in PATTERN_RULES:
            with self.subTest(pattern=pattern), tempfile.TemporaryDirectory() as folder:
                root = make_fixture(folder)
                drop_gitignore_line(root, pattern)
                git(root, "add", ".gitignore")
                done = run_check(root)
                self.assertEqual(done.returncode, 1)
                self.assert_line_starting(done, f"FAIL {rule}:")

    def test_rule_only_in_local_exclude_fails(self):
        with tempfile.TemporaryDirectory() as folder:
            root = make_fixture(folder)
            drop_gitignore_line(root, "data/")
            git(root, "add", ".gitignore")
            exclude = root / ".git" / "info" / "exclude"
            with exclude.open("a", encoding="utf-8") as handle:
                handle.write("data/\n")
            done = run_check(root)
            self.assertEqual(done.returncode, 1)
            self.assert_line_starting(done, "FAIL data-ignored:")

    def test_untracked_gitignore_fails(self):
        with tempfile.TemporaryDirectory() as folder:
            root = make_fixture(folder)
            git(root, "rm", "-q", "--cached", ".gitignore")
            done = run_check(root)
            self.assertEqual(done.returncode, 1)
            self.assert_line_starting(done, "FAIL data-ignored:")
            self.assert_line_starting(done, "FAIL secrets-ignored:")

    def test_rule_only_in_untracked_nested_gitignore_fails(self):
        with tempfile.TemporaryDirectory() as folder:
            root = make_fixture(folder)
            drop_gitignore_line(root, "dist/")
            git(root, "add", ".gitignore")
            (root / "web" / ".gitignore").write_text("dist/\n", encoding="utf-8")
            done = run_check(root)
            self.assertEqual(done.returncode, 1)
            self.assertIn(
                "FAIL generated-ignored: web/dist/x: not ignored by a committed rule",
                done.stdout.splitlines())

    def test_unstaged_gitignore_edit_does_not_count(self):
        with tempfile.TemporaryDirectory() as folder:
            root = make_fixture(folder)
            original = (root / ".gitignore").read_text(encoding="utf-8")
            drop_gitignore_line(root, "data/")
            git(root, "add", ".gitignore")
            (root / ".gitignore").write_text(original, encoding="utf-8")
            done = run_check(root)
            self.assertEqual(done.returncode, 1)
            self.assert_line_starting(done, "FAIL data-ignored:")

    def test_personal_ignore_file_does_not_count(self):
        with tempfile.TemporaryDirectory() as folder:
            root = make_fixture(folder)
            drop_gitignore_line(root, "data/")
            git(root, "add", ".gitignore")
            xdg_home = Path(folder) / "xdg"
            (xdg_home / "git").mkdir(parents=True)
            (xdg_home / "git" / "ignore").write_text("data/\n", encoding="utf-8")
            done = run_check(root, env_extra={"XDG_CONFIG_HOME": str(xdg_home)})
            self.assertEqual(done.returncode, 1)
            self.assert_line_starting(done, "FAIL data-ignored:")

    def test_env_example_ignored_fails(self):
        with tempfile.TemporaryDirectory() as folder:
            root = make_fixture(folder)
            drop_gitignore_line(root, "!.env.example")
            git(root, "add", ".gitignore")
            done = run_check(root)
            self.assertEqual(done.returncode, 1)
            self.assert_line_starting(
                done, "FAIL env-example: .env.example: ignored by")

    def test_env_example_missing_fails(self):
        with tempfile.TemporaryDirectory() as folder:
            root = make_fixture(folder)
            git(root, "rm", "-q", "--cached", ".env.example")
            (root / ".env.example").unlink()
            done = run_check(root)
            self.assertEqual(done.returncode, 1)
            self.assertIn(
                "FAIL env-example: .env.example: not tracked",
                done.stdout.splitlines())

    def test_env_example_with_a_value_fails(self):
        with tempfile.TemporaryDirectory() as folder:
            root = make_fixture(folder)
            path = root / ".env.example"
            text = path.read_text(encoding="utf-8")
            path.write_text(
                text.replace("EII_STORE=\n", "EII_STORE=postgres\n"),
                encoding="utf-8")
            git(root, "add", ".env.example")
            done = run_check(root)
            self.assertEqual(done.returncode, 1)
            self.assertTrue(any(
                line.startswith("FAIL env-example: .env.example:")
                and line.endswith("not a name with an empty value")
                for line in done.stdout.splitlines()))

    def test_env_example_names_differ_fails(self):
        edits = (
            ("removed name", lambda text: text.replace("EII_STORE=\n", "")),
            ("extra name", lambda text: text + "EXTRA_NAME=\n"),
            ("swapped names", lambda text: text.replace(
                "EII_STORE=\nEII_DATABASE_URL=", "EII_DATABASE_URL=\nEII_STORE=")),
        )
        for label, change in edits:
            with self.subTest(case=label), tempfile.TemporaryDirectory() as folder:
                root = make_fixture(folder)
                path = root / ".env.example"
                before = path.read_text(encoding="utf-8")
                after = change(before)
                if after == before:
                    raise AssertionError("the planted edit changed nothing")
                path.write_text(after, encoding="utf-8")
                git(root, "add", ".env.example")
                done = run_check(root)
                self.assertEqual(done.returncode, 1)
                self.assertIn(
                    "FAIL env-example: .env.example: names differ from the pinned list",
                    done.stdout.splitlines())

    def test_env_example_not_utf8_fails(self):
        with tempfile.TemporaryDirectory() as folder:
            root = make_fixture(folder)
            (root / ".env.example").write_bytes(bytes([255, 254]))
            git(root, "add", ".env.example")
            done = run_check(root)
            self.assertEqual(done.returncode, 1)
            self.assertIn(
                "FAIL env-example: .env.example: cannot be read as UTF-8",
                done.stdout.splitlines())

    def test_env_example_staged_value_hidden_by_work_tree_fails(self):
        with tempfile.TemporaryDirectory() as folder:
            root = make_fixture(folder)
            path = root / ".env.example"
            clean = path.read_text(encoding="utf-8")
            number = clean.splitlines().index("EII_STORE=") + 1
            path.write_text(
                clean.replace("EII_STORE=\n", "EII_STORE=postgres\n"),
                encoding="utf-8")
            git(root, "add", ".env.example")
            path.write_text(clean, encoding="utf-8")
            done = run_check(root)
            self.assertEqual(done.returncode, 1)
            self.assertEqual(done.stdout.splitlines(), [
                f"FAIL env-example: .env.example:{number}: "
                "not a name with an empty value",
                "FAIL env-example: .env.example: names differ from the pinned list",
                "checked 8 rules: 2 failure(s)",
            ])

    def test_env_example_unstaged_edit_is_not_judged(self):
        with tempfile.TemporaryDirectory() as folder:
            root = make_fixture(folder)
            path = root / ".env.example"
            text = path.read_text(encoding="utf-8")
            path.write_text(
                text.replace("EII_STORE=\n", "EII_STORE=postgres\n"),
                encoding="utf-8")
            self.assert_clean(run_check(root))

    def test_env_example_staged_symbolic_link_fails(self):
        with tempfile.TemporaryDirectory() as folder:
            root = make_fixture(folder)
            outside = Path(folder) / "outside"
            outside.mkdir()
            target = outside / ".env.example"
            shutil.copyfile(root / ".env.example", target)
            (root / ".env.example").unlink()
            os.symlink(target, root / ".env.example")
            git(root, "add", ".env.example")
            done = run_check(root)
            self.assertEqual(done.returncode, 1)
            self.assertEqual(done.stdout.splitlines(), [
                "FAIL env-example: .env.example: not a regular file in the index",
                "checked 8 rules: 1 failure(s)",
            ])

    def test_env_example_deleted_in_work_tree_is_judged_from_the_index(self):
        with tempfile.TemporaryDirectory() as folder:
            root = make_fixture(folder)
            (root / ".env.example").unlink()
            self.assert_clean(run_check(root))

    def test_force_tracked_secret_fails(self):
        with tempfile.TemporaryDirectory() as folder:
            root = make_fixture(folder)
            (root / ".env").write_text("X=\n", encoding="utf-8")
            git(root, "add", "-f", ".env")
            done = run_check(root)
            self.assertEqual(done.returncode, 1)
            self.assert_line_starting(done, "FAIL tracked-ignored: .env:")

    def test_force_tracked_generated_file_fails(self):
        with tempfile.TemporaryDirectory() as folder:
            root = make_fixture(folder)
            (root / "web" / "dist").mkdir()
            (root / "web" / "dist" / "a.js").write_text("x\n", encoding="utf-8")
            git(root, "add", "-f", "web/dist/a.js")
            done = run_check(root)
            self.assertEqual(done.returncode, 1)
            self.assert_line_starting(done, "FAIL tracked-ignored: web/dist/a.js:")

    def test_not_a_git_work_tree_exits_2(self):
        with tempfile.TemporaryDirectory() as folder:
            plain = Path(folder) / "plain"
            plain.mkdir()
            done = run_check(plain)
            self.assertEqual(done.returncode, 2)

    def test_subdirectory_of_work_tree_exits_2(self):
        with tempfile.TemporaryDirectory() as folder:
            root = make_fixture(folder)
            done = run_check(root / "scripts")
            self.assertEqual(done.returncode, 2)

    def test_linked_worktree_passes(self):
        with tempfile.TemporaryDirectory() as folder:
            root = make_fixture(folder)
            identity = {
                "GIT_AUTHOR_NAME": "fixture",
                "GIT_AUTHOR_EMAIL": "fixture",
                "GIT_COMMITTER_NAME": "fixture",
                "GIT_COMMITTER_EMAIL": "fixture",
            }
            git(root, "commit", "-q", "-m", "fixture", env_extra=identity)
            linked = Path(folder) / "linked"
            linked.mkdir()
            git(root, "worktree", "add", "-q", "--detach",
                str(linked / "wt"), "HEAD")
            self.assert_clean(run_check(linked / "wt"))

    def test_unknown_option_exits_2(self):
        done = run_check(args=("--nope",))
        self.assertEqual(done.returncode, 2)

    def test_output_format(self):
        with tempfile.TemporaryDirectory() as folder:
            root = make_fixture(folder)
            (root / "extras").mkdir()
            (root / "extras" / "a.txt").write_text("x\n", encoding="utf-8")
            git(root, "add", "extras/a.txt")
            (root / "data").mkdir()
            (root / "data" / "a.txt").write_text("x\n", encoding="utf-8")
            git(root, "add", "-f", "data/a.txt")
            done = run_check(root)
            self.assertEqual(done.returncode, 1)
            lines = done.stdout.splitlines()
            self.assertGreater(len(lines), 1)
            body, summary = lines[:-1], lines[-1]
            self.assertTrue(all(FAIL_LINE.match(line) for line in body))
            self.assertEqual(summary, f"checked 8 rules: {len(body)} failure(s)")

    def test_check_changes_nothing(self):
        with tempfile.TemporaryDirectory() as folder:
            root = make_fixture(folder)
            before = tree_snapshot(root)
            status_before = git(root, "status", "--porcelain").stdout
            run_check(root)
            self.assertEqual(tree_snapshot(root), before)
            self.assertEqual(
                git(root, "status", "--porcelain").stdout, status_before)


if __name__ == "__main__":
    unittest.main()
