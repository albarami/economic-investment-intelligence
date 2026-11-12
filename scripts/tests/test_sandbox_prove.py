"""Proof of the hosted run by test-case identity. No sandbox is started."""

from __future__ import annotations

import ast
import io
import os
import stat
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import sandbox_support as support

import ci_junit
import ci_sandbox

ROOT = support.ROOT
GOOD = sorted((*pair, "passed") for pair in ci_junit.required_cases())
ID = "scripts.tests.test_sandbox_loading.LoadingRules::test_automatic_loading_is_off"


def _suite(
    cases: list[tuple[str, str, str]], child: dict[int, str] | None = None
) -> str:
    parts = []
    for index, (owner, name, _status) in enumerate(cases):
        extra = "" if child is None or index not in child else child[index]
        parts.append(f'<testcase classname="{owner}" name="{name}">{extra}</testcase>')
    return "<testsuite>" + "".join(parts) + "</testsuite>"


def _script(body: str) -> str:
    path = tempfile.mktemp(suffix=".sh")
    Path(path).write_text("#!/bin/sh\n" + body, encoding="utf-8")
    os.chmod(path, stat.S_IRWXU)
    return path


def marker_problems(texts: dict[str, str]) -> list[str]:
    """Compare marker modules in source texts with the required case list."""
    required = ci_junit.required_cases()
    found: set[tuple[str, str]] = set()
    others = []
    for name, text in sorted(texts.items()):
        tree = ast.parse(text)
        marked = any(_marker_assign(node) for node in tree.body)
        if marked:
            stem = name[:-3] if name.endswith(".py") else name
            for node in tree.body:
                if isinstance(node, ast.ClassDef):
                    owner = f"scripts.tests.{stem}.{node.name}"
                    for item in node.body:
                        if isinstance(item, ast.FunctionDef) and item.name.startswith(
                            "test"
                        ):
                            found.add((owner, item.name))
        elif _decorated(tree):
            others.append(name)
    seen: list[tuple[str, str]] = []
    duplicates = []
    for owner, names in ci_junit.REQUIRED.items():
        for method in names:
            pair = (ci_junit.MODULE_PREFIX + owner, method)
            if pair in seen:
                duplicates.append(f"duplicate: {pair[0]}::{pair[1]}")
            seen.append(pair)
    missing = [f"missing: {owner}::{name}" for owner, name in sorted(required - found)]
    beyond = [f"beyond: {owner}::{name}" for owner, name in sorted(found - required)]
    return missing + beyond + duplicates + [f"marker: {name}" for name in others]


def _marker_assign(node: ast.stmt) -> bool:
    if not isinstance(node, ast.Assign) or len(node.targets) != 1:
        return False
    target = node.targets[0]
    return (
        isinstance(target, ast.Name)
        and target.id == "pytestmark"
        and _sandbox(node.value)
    )


def _decorated(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        decorators = getattr(node, "decorator_list", [])
        if any(_sandbox(item) for item in decorators):
            return True
    return False


def _sandbox(node: ast.expr) -> bool:
    return (
        isinstance(node, ast.Attribute)
        and node.attr == "sandbox"
        and isinstance(node.value, ast.Attribute)
        and node.value.attr == "mark"
        and isinstance(node.value.value, ast.Name)
        and node.value.value.id == "pytest"
    )


class ProveRules(unittest.TestCase):
    def test_case_judgement(self) -> None:
        self.assertEqual(f"{GOOD[0][0]}::{GOOD[0][1]}", ID)
        first = GOOD[0]
        loading = [case for case in GOOD if case[0].endswith("LoadingRules")]
        rest = [case for case in GOOD if case not in loading]
        unrelated = [
            ("scripts.tests.test_unrelated.OtherRules", f"test_u{index}", "passed")
            for index in range(6)
        ]
        failed = [(*first[:2], "failed"), *GOOD[1:]]
        skipped = [(*first[:2], "skipped"), *GOOD[1:]]
        plants = [
            ci_junit.case_problems(GOOD, 0) == [],
            ci_junit.case_problems([], 5)
            == ["FAIL sandbox-tests: no sandbox test ran"],
            ci_junit.case_problems(GOOD[1:], 0)
            == [f"FAIL sandbox-tests: required test case missing: {ID}"],
            ci_junit.case_problems([*GOOD, first], 0)
            == [f"FAIL sandbox-tests: test case reported 2 times: {ID}"],
            ci_junit.case_problems([*GOOD, unrelated[0]], 0)
            == [
                "FAIL sandbox-tests: test case not in the required list: "
                "scripts.tests.test_unrelated.OtherRules::test_u0"
            ],
            ci_junit.case_problems(failed, 1)
            == [
                f"FAIL sandbox-tests: failed (a sandbox test must pass and is never skipped): {ID}"
            ],
            ci_junit.case_problems(skipped, 0)
            == [
                f"FAIL sandbox-tests: skipped (a sandbox test must pass and is never skipped): {ID}"
            ],
            ci_junit.case_problems(GOOD, 1)
            == ["FAIL sandbox-tests: exit status 1 disagrees with 0 failed test cases"],
            ci_junit.case_problems([*rest, *unrelated], 0)
            == [
                *[
                    f"FAIL sandbox-tests: required test case missing: {owner}::{name}"
                    for owner, name, _status in loading
                ],
                *[
                    f"FAIL sandbox-tests: test case not in the required list: {owner}::{name}"
                    for owner, name, _status in unrelated
                ],
            ],
        ]
        self.assertEqual(plants, [True] * 9)
        wrapped = "<testsuites>" + _suite(GOOD) + "</testsuites>"
        self.assertEqual(ci_junit.read_cases(wrapped), GOOD)
        self.assertEqual(ci_junit.read_cases(_suite(GOOD)), GOOD)
        mixed = _suite(
            [
                ("a.A", "t", "passed"),
                ("a.A", "u", "passed"),
                ("a.A", "v", "passed"),
            ],
            {0: "<failure/>", 1: "<error/>", 2: "<skipped/>"},
        )
        self.assertEqual(
            [status for _owner, _name, status in ci_junit.read_cases(mixed)],
            ["failed", "failed", "skipped"],
        )
        with self.assertRaises(ValueError) as caught:
            ci_junit.read_cases("x")
        self.assertEqual(str(caught.exception), "result file is not well-formed XML")
        for text in (
            "<testsuites/>",
            "<testsuites><testsuite/><testsuite/></testsuites>",
        ):
            with self.assertRaises(ValueError) as caught:
                ci_junit.read_cases(text)
            self.assertEqual(
                str(caught.exception), "result file does not hold exactly one testsuite"
            )
        with self.assertRaises(ValueError) as caught:
            ci_junit.read_cases('<testsuite><testcase name="t"/></testsuite>')
        self.assertEqual(
            str(caught.exception), "a testcase has no classname or no name"
        )
        self.assertEqual(len(plants) + 7, 16)

    def test_prove_runs(self) -> None:
        labels = []
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            labels.append("a")
            script = _script("exec sleep 30\n")
            self.addCleanup(os.remove, script)
            started = time.monotonic()
            out = self._prove(root, script, timeout=0.5)
            self.assertLess(time.monotonic() - started, 3)
            self.assertTrue(
                out.endswith(
                    "FAIL sandbox-tests: timed out after 0.5 s\nRESULT: FAILED\n"
                )
            )
            labels.append("b")
            writer = _script(self._writer(_suite(GOOD), warn=False))
            self.addCleanup(os.remove, writer)
            out = self._prove(root, writer)
            self.assertTrue(out.endswith(self._passed(GOOD)))
            labels.append("c")
            noisy = _script(self._writer(_suite(GOOD), warn=True))
            self.addCleanup(os.remove, noisy)
            out = self._prove(root, noisy)
            self.assertTrue(
                out.endswith(
                    "FAIL sandbox-tests: standard error is not empty: 'warn\\n'\nRESULT: FAILED\n"
                )
            )
            labels.append("d")
            other = [
                ("scripts.tests.test_other.OtherRules", f"test_o{index:02d}", "passed")
                for index in range(19)
            ]
            foreign = _script(self._writer(_suite(other), warn=False))
            self.addCleanup(os.remove, foreign)
            out = self._prove(root, foreign)
            self.assertIn("RESULT: FAILED", out)
            self.assertEqual(out.count("required test case missing:"), 19)
            self.assertEqual(out.count("test case not in the required list:"), 19)
            labels.append("i")
            marked = _script(
                self._writer(_suite(GOOD), warn=False).replace(
                    "exit 0\n", "echo STDOUT-MARKER\nexit 0\n", 1
                )
            )
            self.addCleanup(os.remove, marked)
            out = self._prove(root, marked)
            self.assertNotIn("STDOUT-MARKER", out)
            self.assertTrue(out.endswith(self._passed(GOOD)))
        labels.append("e")
        self._stub(expect_ok=True, change=None)
        labels.append("f")
        self._stub(expect_ok=False, change="replace-loading")
        labels.append("g")
        self._stub(expect_ok=False, change="add-unrelated")
        labels.append("h")
        self._stub(expect_ok=False, change="drop-die")
        self.assertEqual(labels, [*list("abcd"), "i", *list("efgh")])

    def test_required_cases_match_the_marker_modules(self) -> None:
        texts = {
            path.name: path.read_text(encoding="utf-8")
            for path in sorted((ROOT / "scripts/tests").glob("test_*.py"))
        }
        self.assertEqual(marker_problems(texts), [])
        plants = []
        dropped = dict(texts)
        dropped["test_sandbox_loading.py"] = dropped["test_sandbox_loading.py"].replace(
            "pytestmark = pytest.mark.sandbox\n", "", 1
        )
        missing = [
            f"missing: scripts.tests.test_sandbox_loading.LoadingRules::{name}"
            for name in sorted(ci_junit.REQUIRED["test_sandbox_loading.LoadingRules"])
        ]
        plants.append(marker_problems(dropped) == missing)
        added = dict(texts)
        added["test_sandbox_mounts.py"] = added["test_sandbox_mounts.py"].replace(
            "    def test_filesystem_modes_in_both_profiles",
            "    def test_extra(self) -> None:\n        pass\n\n    def test_filesystem_modes_in_both_profiles",
            1,
        )
        plants.append(
            marker_problems(added)
            == ["beyond: scripts.tests.test_sandbox_mounts.MountRules::test_extra"]
        )
        renamed = dict(texts)
        renamed["test_sandbox_mounts.py"] = renamed["test_sandbox_mounts.py"].replace(
            "def test_die_with_parent", "def test_die_with_parent_2", 1
        )
        plants.append(
            marker_problems(renamed)
            == [
                "missing: scripts.tests.test_sandbox_mounts.MountRules::test_die_with_parent",
                "beyond: scripts.tests.test_sandbox_mounts.MountRules::test_die_with_parent_2",
            ]
        )
        decorated = dict(texts)
        decorated["test_sandbox_argv.py"] = decorated["test_sandbox_argv.py"].replace(
            "class ArgvRules", "@pytest.mark.sandbox\nclass ArgvRules", 1
        )
        plants.append(marker_problems(decorated) == ["marker: test_sandbox_argv.py"])
        self.assertEqual(plants, [True] * 4)

    def test_pytest_child_environment(self) -> None:
        hostile = {
            "PYTEST_ADDOPTS": "-k nothing",
            "PYTHONPATH": "/tmp/planted",
            "HOME": "/tmp/home",
            "PYTEST_PLUGINS": "planted",
            "VIRTUAL_ENV": "/tmp/venv",
            "EII_PLANTED_SECRET": "planted-value-1234",
            "PATH": "/usr/bin",
        }
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            safe = ci_sandbox.pytest_environment(hostile, folder)
            self.assertEqual(
                safe,
                {
                    "HYPOTHESIS_STORAGE_DIRECTORY": str(folder / "hypothesis"),
                    "LANG": "C",
                    "NO_COLOR": "1",
                    "PATH": "/usr/bin",
                    "PYTHONDONTWRITEBYTECODE": "1",
                },
            )
            bare = ci_sandbox.pytest_environment({"HOME": "/tmp/home"}, folder)
            self.assertNotIn("PATH", bare)
            project = folder / "project"
            project.mkdir()
            (project / "pyproject.toml").write_text(
                "[tool.pytest]\nstrict = true\n", encoding="utf-8"
            )
            (project / "test_one.py").write_text(
                "import unittest\n\nclass T(unittest.TestCase):\n    def test_ok(self) -> None:\n        pass\n",
                encoding="utf-8",
            )
            result = project / "out.xml"
            self._pytest(project, safe, result)
            self.assertEqual(
                len(ci_junit.read_cases(result.read_text(encoding="utf-8"))), 1
            )
            self.assertEqual(
                ci_junit.read_cases(result.read_text(encoding="utf-8"))[0][2], "passed"
            )
            result.unlink()
            self._pytest(project, {**safe, "PYTEST_ADDOPTS": "-k nothing"}, result)
            self.assertEqual(
                ci_junit.read_cases(result.read_text(encoding="utf-8")), []
            )

    def _prove(self, root: Path, executable: str, timeout: float | None = None) -> str:
        out = io.StringIO()
        patcher = patch.object(sys, "executable", executable)
        timeout_patch = (
            patch.object(ci_sandbox, "PROVE_TIMEOUT", timeout)
            if timeout is not None
            else null()
        )
        with patcher, timeout_patch:
            status = ci_sandbox.prove(root, {"PATH": os.environ.get("PATH", "")}, out)
        self.assertIn(status, (0, 1))
        if timeout is not None:
            self.assertEqual(status, 1)
        return out.getvalue()

    def _writer(self, xml: str, warn: bool) -> str:
        warn_line = "echo warn >&2\n" if warn else ""
        return (
            'last=\nfor last in "$@"; do :; done\n'
            + f"cat > \"$last\" << 'END'\n{xml}\nEND\n"
            + warn_line
            + "exit 0\n"
        )

    def _passed(self, cases: list[tuple[str, str, str]]) -> str:
        lines = [
            f"case {status} {owner}::{name}" for owner, name, status in sorted(cases)
        ]
        return "\n".join([*lines, "RESULT: PASSED"]) + "\n"

    def _stub(self, expect_ok: bool, change: str | None) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tests = root / "scripts" / "tests"
            tests.mkdir(parents=True)
            (root / "pyproject.toml").write_text(_STUB_PROJECT, encoding="utf-8")
            for owner, names in ci_junit.REQUIRED.items():
                module, class_name = owner.split(".")
                methods = "".join(
                    f"    def {name}(self) -> None:\n        pass\n" for name in names
                )
                text = (
                    "import pytest\nimport unittest\n\n"
                    "pytestmark = pytest.mark.sandbox\n\n"
                    f"class {class_name}(unittest.TestCase):\n{methods}"
                )
                (tests / f"{module}.py").write_text(text, encoding="utf-8")
            if change == "replace-loading":
                path = tests / "test_sandbox_loading.py"
                path.write_text(
                    path.read_text(encoding="utf-8").replace(
                        "pytestmark = pytest.mark.sandbox\n", "", 1
                    ),
                    encoding="utf-8",
                )
                methods = "".join(
                    f"    def test_u{index}(self) -> None:\n        pass\n"
                    for index in range(6)
                )
                (tests / "test_unrelated.py").write_text(
                    "import pytest\nimport unittest\n\npytestmark = pytest.mark.sandbox\n\n"
                    f"class OtherRules(unittest.TestCase):\n{methods}",
                    encoding="utf-8",
                )
            elif change == "add-unrelated":
                methods = "".join(
                    f"    def test_u{index}(self) -> None:\n        pass\n"
                    for index in range(6)
                )
                (tests / "test_unrelated.py").write_text(
                    "import pytest\nimport unittest\n\npytestmark = pytest.mark.sandbox\n\n"
                    f"class OtherRules(unittest.TestCase):\n{methods}",
                    encoding="utf-8",
                )
            elif change == "drop-die":
                path = tests / "test_sandbox_mounts.py"
                path.write_text(
                    path.read_text(encoding="utf-8").replace(
                        "    def test_die_with_parent(self) -> None:\n        pass\n",
                        "",
                        1,
                    ),
                    encoding="utf-8",
                )
            out = io.StringIO()
            status = ci_sandbox.prove(root, {"PATH": os.environ.get("PATH", "")}, out)
            text = out.getvalue()
            if expect_ok:
                self.assertEqual(status, 0)
                self.assertTrue(text.endswith(self._passed(GOOD)), text[-500:])
                return
            self.assertEqual(status, 1)
            self.assertIn("RESULT: FAILED", text)
            if change == "drop-die":
                self.assertIn(
                    "FAIL sandbox-tests: required test case missing: "
                    "scripts.tests.test_sandbox_mounts.MountRules::test_die_with_parent",
                    text,
                )

    def _pytest(self, project: Path, env: dict[str, str], result: Path) -> None:
        done = subprocess.run(
            [
                sys.executable,
                "-P",
                "-s",
                "-m",
                "pytest",
                "-c",
                "pyproject.toml",
                "--rootdir",
                ".",
                "--junit-xml",
                str(result),
            ],
            cwd=project,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertTrue(result.is_file(), done.stderr)


class null:
    def __enter__(self) -> None:
        return None

    def __exit__(self, *args: object) -> None:
        return None


_STUB_PROJECT = textwrap.dedent(
    """\
    [tool.pytest]
    strict = true
    addopts = [
      "--import-mode=importlib",
      "-p",
      "no:cacheprovider",
      "-m",
      "not nightly",
    ]
    pythonpath = ["scripts", "scripts/tests"]
    markers = [
      "postgres: needs a reachable PostgreSQL; with none it is skipped with the reason OI-10",
      "sandbox: needs bubblewrap; it is never skipped",
      "nightly: not part of the pull-request run",
      "live_model: needs a live model key; with none it is skipped with the reason OI-01",
    ]
    """
)


if __name__ == "__main__":
    unittest.main()
