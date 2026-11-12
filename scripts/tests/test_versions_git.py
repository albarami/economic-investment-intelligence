"""Rule 17 and the git candidate list."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

import versions_support as base

S1 = base.summary(1)
EXACT = (
    "pyproject.toml",
    "uv.lock",
    "uv.toml",
    "package.json",
    "package-lock.json",
    "npm-shrinkwrap.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    ".npmrc",
    ".python-version",
    ".nvmrc",
    ".node-version",
    ".tool-versions",
)
PATTERNS = ("requirements-dev.txt", "constraints.txt")


class GitRules(unittest.TestCase):
    def test_unscanned_files(self) -> None:
        names = EXACT + PATTERNS
        for name in names:
            with self.subTest(name=name, tracked=False):
                root, path = base.ready(self)
                base.write(root, f"extra/{name}", "x\n")
                self.assertEqual(
                    base.run(root, path=path), [self._line(f"extra/{name}"), S1]
                )
        extra_paths = (
            "web/npm-shrinkwrap.json",
            "web/.npmrc",
            "web/.nvmrc",
            "core/uv.lock",
            "gateway/pyproject.toml",
            "sub/data/package.json",
            "sp ace/caf\u00e9/package.json",
        )
        for rel in extra_paths:
            with self.subTest(rel=rel):
                root, path = base.ready(self)
                base.write(root, rel, "x\n")
                self.assertEqual(base.run(root, path=path), [self._line(rel), S1])
        for rel in ("uv.toml", "core/uv.toml", "extra/uv.toml"):
            with self.subTest(rel=rel):
                root, path = base.ready(self)
                base.write(root, rel, "x\n")
                self.assertEqual(
                    base.run(root, path=path),
                    [f"FAIL unscanned: {rel}: shadows tool.uv in pyproject.toml", S1],
                )
        root, path = base.ready(self)
        (root / "extra").mkdir()
        (root / "extra" / "package.json").symlink_to("missing")
        self.assertEqual(
            base.run(root, path=path),
            [self._line("extra/package.json"), S1],
        )
        root, path = base.ready(self)
        planted = [f"extra/{name}" for name in names]
        for rel in planted:
            base.write(root, rel, "x\n")
        lines = base.run(root, path=path)
        expected = [
            self._line(rel)
            if not rel.endswith("uv.toml")
            else f"FAIL unscanned: {rel}: shadows tool.uv in pyproject.toml"
            for rel in sorted(planted)
        ]
        self.assertEqual(lines, [*expected, base.summary(len(expected))])
        base.git(root, "add", "--", "extra")
        self.assertEqual(base.run(root, path=path), lines)
        for rel in (
            "extra/requirements.md",
            "extra/constraints.json",
            "extra/package.json.bak",
        ):
            with self.subTest(control=rel):
                root, path = base.ready(self)
                base.write(root, rel, "x\n")
                self.assertEqual(base.run(root, path=path), [base.SUMMARY_OK])
        root, path = base.ready(self)
        self.assertEqual(base.run(root, path=path), [base.SUMMARY_OK])

    def test_unscanned_candidates_come_from_git(self) -> None:
        root, path = self._place("extra/package.json", add=True)
        self._expect_hit(root, path, "extra/package.json")
        root, path = self._place("extra/package.json")
        self._expect_hit(root, path, "extra/package.json")
        root, path = self._place("build/package.json")
        base.write(root, ".gitignore", "build/\n")
        self._expect_ok(root, path)
        root, path = self._place("build/package.json")
        base.write(root, ".gitignore", "build/\n")
        base.git(root, "add", "--", ".gitignore")
        self._expect_ok(root, path)
        root, path = self._place("core/build/package.json")
        base.write(root, "core/.gitignore", "build/\n")
        self._expect_ok(root, path)
        root, path = self._place("hidden/package.json")
        exclude = root / ".git" / "info" / "exclude"
        exclude.parent.mkdir(parents=True, exist_ok=True)
        exclude.write_text("hidden/\n", encoding="utf-8")
        self._expect_ok(root, path)
        root, path = self._place("build/package.json")
        base.write(root, ".gitignore", "build/\n")
        base.git(root, "add", "-f", "--", "build/package.json")
        self._expect_hit(root, path, "build/package.json")
        root, path = self._place("extra/package.json", add=True)
        (root / "extra" / "package.json").unlink()
        self._expect_ok(root, path)
        root, path = self._place("extra/package.json", add=True)
        base.git(root, "rm", "--cached", "-q", "--", "extra/package.json")
        self._expect_hit(root, path, "extra/package.json")
        root, path = base.ready(self)
        base.write(root, "nested/package.json", "{}\n")
        base.git_init(root / "nested")
        self._expect_ok(root, path)
        root, path = self._place("data/package.json")
        base.write(root, ".gitignore", "data/\n")
        self._expect_ok(root, path)
        root, path = self._place("data/package.json")
        self._expect_hit(root, path, "data/package.json")
        root, path, worktree = self._worktree()
        base.write(worktree, "extra/package.json", "{}\n")
        self._expect_hit(worktree, path, "extra/package.json")
        root, path, worktree = self._worktree()
        base.write(worktree, "extra/package.json", "{}\n")
        info = root / ".git" / "info" / "exclude"
        info.parent.mkdir(parents=True, exist_ok=True)
        info.write_text("extra/\n", encoding="utf-8")
        self._expect_ok(worktree, path)
        root, path = self._place("extra/package.json")
        real = os.lstat

        def side_effect(
            target: os.PathLike[str] | str, *args: object, **kwargs: object
        ) -> os.stat_result:
            if str(target).endswith("extra/package.json"):
                raise PermissionError
            return real(target)

        with patch("os.lstat", side_effect=side_effect):
            self.assertEqual(
                base.run(root, path=path),
                ["FAIL unscanned: extra/package.json: unreadable", S1],
            )

    def test_git_listing_failures(self) -> None:
        root, path = base.ready(self)
        git_link = Path(path) / "git"
        if git_link.exists() or git_link.is_symlink():
            git_link.unlink()
        missing = ["FAIL input: git: not found on PATH", S1]
        self.assertEqual(base.run(root, path=path), missing)
        self._expect_cli_fail(root, path, missing)
        root, path = base.ready(self)
        git_link = Path(path) / "git"
        if git_link.is_symlink():
            git_link.unlink()
        git_link.write_text("#!/no/such/interpreter\n", encoding="utf-8")
        git_link.chmod(0o755)
        cannot_run = ["FAIL input: git: could not run (FileNotFoundError)", S1]
        self.assertEqual(base.run(root, path=path), cannot_run)
        self._expect_cli_fail(root, path, cannot_run)
        root, path = base.ready(self)
        shutil.rmtree(root / ".git")
        not_top = ["FAIL input: git: root is not the top of a git work tree", S1]
        self.assertEqual(base.run(root, path=path), not_top)
        self._expect_cli_fail(root, path, not_top)
        with patch("subprocess.run", side_effect=AssertionError):
            self.assertEqual(
                base.versions_inputs.list_candidates(root, {"PATH": path}),
                (None, "root is not the top of a git work tree"),
            )
        intact, intact_path = base.ready(self)
        with patch("subprocess.run", side_effect=AssertionError):
            self.assertEqual(
                base.versions_inputs.list_candidates(
                    intact / "core", {"PATH": intact_path}
                ),
                (None, "root is not the top of a git work tree"),
            )
        root, path = base.ready(self)
        sub = root / "sub"
        base.make_tree(sub)
        shutil.rmtree(sub / ".git")
        (sub / ".git").mkdir()
        self.assertEqual(
            base.versions_inputs.list_candidates(sub, {"PATH": path}),
            (None, "root is not the top of a git work tree"),
        )
        self._expect_cli_fail(sub, path, not_top)
        root, path = base.ready(self)
        shutil.rmtree(root / ".git")
        base.write(root, ".git", "gitdir: nowhere\n")
        rev_parse = ["FAIL input: git: rev-parse exit status 128", S1]
        self.assertEqual(base.run(root, path=path), rev_parse)
        self._expect_cli_fail(root, path, rev_parse)
        root, path = base.ready(self)
        (root / ".git" / "index").write_bytes(b"garbage")
        ls_files = ["FAIL input: git: ls-files exit status 128", S1]
        self.assertEqual(base.run(root, path=path), ls_files)
        self._expect_cli_fail(root, path, ls_files)
        root, path = base.ready(self)
        (root / "extra").mkdir()
        (root / "extra" / os.fsdecode(b"\xff.txt")).write_bytes(b"x")
        bad_utf = ["FAIL input: git: output is not valid UTF-8", S1]
        self.assertEqual(base.run(root, path=path), bad_utf)
        self._expect_cli_fail(root, path, bad_utf)
        _root, path, worktree = self._worktree()
        proc = base.cli(["--root", str(worktree)], {"PATH": path})
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout.splitlines(), [base.SUMMARY_OK])
        root, path = base.ready(self)
        git_link = Path(path) / "git"
        if git_link.is_symlink():
            git_link.unlink()
        base.write(root, ".python-version", "3.13\n")
        version_file = [
            "FAIL input: git: not found on PATH",
            "FAIL version-file: .python-version: holds '3.13\\n' expected '3.14'",
            base.summary(2),
        ]
        self.assertEqual(base.run(root, path=path), version_file)
        self._expect_cli_fail(root, path, version_file)
        root, path = base.ready(self)
        git_link = Path(path) / "git"
        if git_link.is_symlink():
            git_link.unlink()
        base.edit_row(root, 'name = "alpha"', base.CITE, "docs/none.md ARC-01")
        cite = [
            "FAIL record-cite: pins.toml: component[4] alpha: docs/none.md is not a file",
            S1,
        ]
        self.assertEqual(base.run(root, path=path), cite)
        self._expect_cli_fail(root, path, cite)

    def test_git_surroundings_do_not_change_the_result(self) -> None:
        root, path = base.ready(self)
        base.write(root, "extra/package.json", "{}\n")
        home = root / "home"
        base.write(home, "ignore", "package.json\n")
        base.write(
            home,
            ".gitconfig",
            "[core]\n\texcludesFile = " + str(home / "ignore") + "\n",
        )
        base.write(home, ".config/git/ignore", "package.json\n")
        config = root / ".git" / "config"
        original_config = config.read_text(encoding="utf-8")
        config.write_text(
            original_config
            + "\n[core]\n\texcludesFile = "
            + str(home / "ignore")
            + "\n",
            encoding="utf-8",
        )
        other = root.parent / "other"
        other.mkdir()
        base.git_init(other)
        base.write(other, "zzz.txt", "z\n")
        base.git(other, "add", "--", "zzz.txt")
        hostile = {
            "PATH": path,
            "HOME": str(home),
            "XDG_CONFIG_HOME": str(home / ".config"),
            "GIT_DIR": str(other / ".git"),
            "GIT_WORK_TREE": str(other),
            "GIT_INDEX_FILE": str(other / "idx"),
            "GIT_CONFIG_COUNT": "1",
            "GIT_CONFIG_KEY_0": "core.excludesFile",
            "GIT_CONFIG_VALUE_0": str(home / "ignore"),
        }
        lines, _count = base.check_versions.run_checks(
            root, interpreter=base.GOOD_INTERPRETER, environ=hostile
        )
        self.assertEqual(
            lines, ["FAIL unscanned: extra/package.json: not a judged input", S1]
        )
        proc = base.cli(["--root", str(root)], hostile)
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(proc.stdout.splitlines(), lines)
        config.write_text(original_config, encoding="utf-8")
        bare = {
            "PATH": os.environ.get("PATH", ""),
            "LANG": "C",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_SYSTEM": os.devnull,
            "HOME": str(home),
            "XDG_CONFIG_HOME": str(home / ".config"),
        }
        listed = self._listed(root, bare, switches=False)
        self.assertNotIn("extra/package.json", listed)
        self.assertIn("pins.toml", listed)
        home_only = {
            "PATH": os.environ.get("PATH", ""),
            "LANG": "C",
            "GIT_CONFIG_SYSTEM": os.devnull,
            "HOME": str(home),
            "XDG_CONFIG_HOME": str(home / "empty"),
        }
        listed = self._listed(root, home_only, switches=False)
        self.assertNotIn("extra/package.json", listed)
        self.assertIn("pins.toml", listed)
        config.write_text(
            original_config
            + "\n[core]\n\texcludesFile = "
            + str(home / "ignore")
            + "\n",
            encoding="utf-8",
        )
        repo_only = {
            "PATH": os.environ.get("PATH", ""),
            "LANG": "C",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_SYSTEM": os.devnull,
        }
        listed = self._listed(root, repo_only, switches=False)
        self.assertNotIn("extra/package.json", listed)
        self.assertIn("pins.toml", listed)
        moved = {
            "PATH": os.environ.get("PATH", ""),
            "LANG": "C",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_SYSTEM": os.devnull,
            "GIT_DIR": str(other / ".git"),
            "GIT_WORK_TREE": str(other),
        }
        listed = self._listed(root, moved, switches=False)
        self.assertEqual(listed, ["zzz.txt"])

    def test_git_child_is_the_allow_list(self) -> None:
        root, path = base.ready(self)
        bindir = Path(path)
        git_link = bindir / "git"
        if git_link.is_symlink():
            git_link.unlink()
        args_file = bindir.parent / "args"
        env_file = bindir.parent / "env"
        base.make_tool(
            bindir,
            "git",
            "printf '%s\\n' \"$@\" >> '"
            + str(args_file)
            + "'\nprintf '%s\\n' '---' >> '"
            + str(args_file)
            + "'\n/usr/bin/env | /usr/bin/sort >> '"
            + str(env_file)
            + "'\nprintf '%s\\n' '---' >> '"
            + str(env_file)
            + "'\nexec '"
            + str(base.GIT)
            + '\' "$@"\n',
        )
        hostile = {
            "PATH": path,
            "HOME": "home",
            "XDG_CONFIG_HOME": "home/.config",
            "GIT_DIR": "other/.git",
            "GIT_WORK_TREE": "other",
            "GIT_INDEX_FILE": "other/idx",
            "GIT_CONFIG_COUNT": "1",
            "GIT_CONFIG_KEY_0": "core.excludesFile",
            "GIT_CONFIG_VALUE_0": "home/ignore",
        }
        lines, _count = base.check_versions.run_checks(
            root, interpreter=base.GOOD_INTERPRETER, environ=hostile
        )
        self.assertEqual(lines, [base.SUMMARY_OK])
        self.assertTrue(args_file.is_file())
        self.assertTrue(env_file.is_file())
        chunks = args_file.read_text(encoding="utf-8").split("---\n")
        null = os.devnull
        self.assertEqual(
            chunks[0].splitlines(),
            [
                "-c",
                f"core.excludesFile={null}",
                "-C",
                str(root),
                "rev-parse",
                "--show-toplevel",
            ],
        )
        self.assertEqual(
            chunks[1].splitlines(),
            [
                "-c",
                f"core.excludesFile={null}",
                "-C",
                str(root),
                "ls-files",
                "-z",
                "--cached",
                "--others",
                "--exclude-standard",
            ],
        )
        env_chunks = env_file.read_text(encoding="utf-8").split("---\n")
        self.assertEqual(len(chunks), 3)
        self.assertEqual(chunks[2], "")
        self.assertEqual(len(env_chunks), 3)
        self.assertEqual(env_chunks[2], "")
        child_env = {
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_SYSTEM": os.devnull,
            "LANG": "C",
            "PATH": path,
        }
        for chunk in env_chunks[:2]:
            recorded = {
                key: value
                for line in chunk.splitlines()
                if "=" in line
                for key, value in [line.split("=", 1)]
                if key not in base.SHELL_ENV_KEYS
            }
            self.assertEqual(recorded, child_env)
        self.assertEqual(
            base.versions_inputs.list_candidates(root, hostile),
            (self._listed(root, base.git_env(), switches=True), None),
        )
        self.assertEqual(
            set(base.versions_inputs.git_environment({})),
            {"GIT_CONFIG_GLOBAL", "GIT_CONFIG_SYSTEM", "LANG"},
        )
        self.assertEqual(
            set(base.versions_inputs.git_environment({"PATH": "p"})),
            {"GIT_CONFIG_GLOBAL", "GIT_CONFIG_SYSTEM", "LANG", "PATH"},
        )
        wide = base.versions_inputs.git_environment(hostile)
        self.assertEqual(
            set(wide), {"GIT_CONFIG_GLOBAL", "GIT_CONFIG_SYSTEM", "LANG", "PATH"}
        )
        self.assertEqual(wide["PATH"], path)
        self.assertEqual(wide["LANG"], "C")
        self.assertEqual(wide["GIT_CONFIG_GLOBAL"], os.devnull)
        self.assertEqual(wide["GIT_CONFIG_SYSTEM"], os.devnull)

    def _expect_cli_fail(self, target: Path, path: str, expected: list[str]) -> None:
        proc = base.cli(["--root", str(target)], {"PATH": path})
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(proc.stderr, "")
        self.assertEqual(proc.stdout.splitlines(), expected)

    def _line(self, rel: str) -> str:
        if rel.endswith("uv.toml"):
            return f"FAIL unscanned: {rel}: shadows tool.uv in pyproject.toml"
        return f"FAIL unscanned: {rel}: not a judged input"

    def _place(self, rel: str, add: bool = False) -> tuple[Path, str]:
        root, path = base.ready(self)
        base.write(root, rel, "{}\n")
        if add:
            base.git(root, "add", "--", rel)
        return root, path

    def _expect_hit(self, root: Path, path: str, rel: str) -> None:
        self.assertEqual(base.run(root, path=path), [self._line(rel), S1])

    def _expect_ok(self, root: Path, path: str) -> None:
        self.assertEqual(base.run(root, path=path), [base.SUMMARY_OK])

    def _worktree(self) -> tuple[Path, str, Path]:
        root, path = base.ready(self)
        base.git(root, "add", "-A")
        base.git(root, "commit", "-q", "-m", "fixture")
        worktree = root.parent / "wt"
        base.git(root, "worktree", "add", "--detach", str(worktree))
        return root, path, worktree

    def _listed(self, root: Path, env: dict[str, str], switches: bool) -> list[str]:
        command = [
            base.GIT,
            "-C",
            str(root),
            "ls-files",
            "-z",
            "--cached",
            "--others",
            "--exclude-standard",
        ]
        if switches:
            command[1:1] = ["-c", f"core.excludesFile={os.devnull}"]
        done = subprocess.run(command, capture_output=True, env=env, check=True)
        return sorted(part for part in done.stdout.decode("utf-8").split("\0") if part)
