"""M2: run the pinned mutation tool on a tiny invented temporary module."""

import contextlib
import hashlib
import importlib
import io
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from unittest.mock import patch


class MutationRunnerTests(unittest.TestCase):
    def test_unexplained_survivor_refused_and_explained_survivor_accepted(self) -> None:
        self.assertTrue(
            (Path(__file__).parents[1] / "mutation.py").is_file(),
            "mutation runner required",
        )
        runner = importlib.import_module("scripts.mutation")
        with TemporaryDirectory(prefix="synthetic-mutation-test-") as temporary:
            folder = Path(temporary)
            (folder / "src").mkdir()
            (folder / "tests").mkdir()
            (folder / "src/toy.py").write_text("def value():\n    return 2\n")
            (folder / "tests/test_toy.py").write_text(
                "from toy import value\n\ndef test_value():\n    assert value() > 0\n"
            )
            (folder / "pyproject.toml").write_text(
                '[tool.pytest]\npythonpath = ["src"]\n'
            )
            ledger = folder / "explained.toml"
            ledger.write_text("survivors = []\n")
            code, survivors = runner.run_copy(folder, ["src/toy.py"], ["tests"], ledger)
            self.assertEqual(code, 1)
            self.assertGreater(len(survivors), 0)
            # Only this invented runner test permits a deliberately non-equivalent explanation.
            ledger.write_text(
                "\n".join(
                    "[[survivors]]\nmodule = "
                    + json.dumps(row["module"])
                    + "\nmutation = "
                    + json.dumps(row["mutation"])
                    + '\nreason = "Invented runner fixture; exercises approval matching only."'
                    for row in survivors
                )
            )
            self.assertEqual(runner.judge(survivors, ledger), 0)
            self.assertFalse((folder / "mutants").exists())

    def test_not_covered_mutant_requires_explanation(self) -> None:
        runner = importlib.import_module("scripts.mutation")
        with TemporaryDirectory(prefix="synthetic-uncovered-") as temporary:
            folder = Path(temporary)
            (folder / "src").mkdir()
            (folder / "tests").mkdir()
            (folder / "src/toy.py").write_text(
                "def value():\n    return 2\n\ndef unused():\n    return 7\n"
            )
            (folder / "tests/test_toy.py").write_text(
                "from toy import value\n\ndef test_value():\n    assert value() == 2\n"
            )
            (folder / "pyproject.toml").write_text(
                '[tool.pytest]\npythonpath = ["src"]\n'
            )
            ledger = folder / "explained.toml"
            ledger.write_text("survivors = []\n")
            code, survivors = runner.run_copy(folder, ["src/toy.py"], ["tests"], ledger)
            self.assertEqual(code, 1)
            self.assertTrue(survivors)
            self.assertIn("unused", survivors[0]["mutation"])

    def test_package_run_uses_src_and_own_tests(self) -> None:
        runner = importlib.import_module("scripts.mutation")
        self.assertTrue(callable(getattr(runner, "run_packages", None)))
        with TemporaryDirectory(prefix="synthetic-package-mutation-") as temporary:
            root = Path(temporary)
            (root / "pyproject.toml").write_text("")
            (root / "docs").mkdir()
            (root / "docs/synthetic.txt").write_text("invented reference")
            package = root / "custodian"
            (package / "src/synthetic").mkdir(parents=True)
            (package / "tests").mkdir()
            (package / "src/synthetic/__init__.py").write_text("")
            (package / "src/synthetic/toy.py").write_text(
                "def value():\n    return 2\n"
            )
            (package / "tests/test_toy.py").write_text(
                "from synthetic.toy import value\nfrom pathlib import Path\n"
                "def test_value():\n    assert value() == 2\n"
                "    assert (Path(__file__).parents[2] / 'docs/synthetic.txt').read_text() == 'invented reference'\n"
            )
            (package / "pyproject.toml").write_text("")
            (root / "scripts/tests").mkdir(parents=True)
            (root / "scripts/tests/test_forbidden.py").write_text(
                'raise AssertionError("cross-plane tests must not run")\n'
            )
            ledger = root / "explained.toml"
            ledger.write_text("survivors = []\n")
            import shutil

            shutil.copytree(package, root / "product")
            shutil.copytree(package, root / "core")
            output = io.StringIO()
            (root / "scripts/mutation_explained.toml").write_text("survivors = []\n")
            listed = "\0".join(
                str(path.relative_to(root))
                for path in root.rglob("*")
                if path.is_file()
            ).encode()
            real_run = subprocess.run

            def git_boundary(
                arguments: list[str], **kwargs: Any
            ) -> subprocess.CompletedProcess[Any]:
                if arguments[0] == "git":
                    return subprocess.CompletedProcess(arguments, 0, stdout=listed)
                return real_run(arguments, **kwargs)

            with (
                contextlib.redirect_stdout(output),
                patch.object(runner, "ROOT", root),
                patch.object(runner.subprocess, "run", side_effect=git_boundary),
                patch.object(
                    sys,
                    "argv",
                    [
                        "mutation.py",
                        "custodian/src/synthetic/toy.py",
                        "product/src/synthetic/toy.py",
                        "core/src/synthetic/toy.py",
                    ],
                ),
            ):
                code = runner.main()
            self.assertEqual(code, 0)
            for name in ("custodian", "product", "core"):
                self.assertIn(
                    name + "/src/synthetic/toy.py: made=1 killed=1 survived=0",
                    output.getvalue(),
                )
            self.assertEqual((package / "pyproject.toml").read_text(), "")
            self.assertFalse((package / "mutants").exists())

    def test_package_survivor_returns_nonzero_and_keeps_repository_module_name(
        self,
    ) -> None:
        runner = importlib.import_module("scripts.mutation")
        with TemporaryDirectory(prefix="synthetic-survivor-package-") as temporary:
            root = Path(temporary)
            package = root / "product"
            (package / "src/synthetic").mkdir(parents=True)
            (package / "tests").mkdir()
            (package / "src/synthetic/__init__.py").write_text("")
            (package / "src/synthetic/toy.py").write_text(
                "def value():\n    return 2\n"
            )
            (package / "tests/test_toy.py").write_text(
                "from synthetic.toy import value\n\ndef test_value():\n    assert value() > 0\n"
            )
            (package / "pyproject.toml").write_text("")
            ledger = root / "explained.toml"
            ledger.write_text("survivors = []\n")
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = runner.run_packages(
                    root, ["product/src/synthetic/toy.py"], ledger
                )
            self.assertEqual(code, 1)
            rows = [
                json.loads(line)
                for line in output.getvalue().splitlines()
                if line.startswith('{"line":')
            ]
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["module"], "product/src/synthetic/toy.py")
            self.assertEqual((package / "pyproject.toml").read_text(), "")
            self.assertFalse((package / "mutants").exists())

    def test_package_test_imports_script_modules_by_bare_name(self) -> None:
        # The project's own test path holds scripts and scripts/tests; the copy's must too.
        runner = importlib.import_module("scripts.mutation")
        with TemporaryDirectory(prefix="synthetic-script-path-") as temporary:
            root = Path(temporary)
            package = root / "custodian"
            (package / "src/synthetic").mkdir(parents=True)
            (package / "tests").mkdir()
            (package / "src/synthetic/__init__.py").write_text("")
            (package / "src/synthetic/toy.py").write_text(
                "def value():\n    return 2\n"
            )
            (package / "tests/test_toy.py").write_text(
                "from synthetic_probe import EXPECTED\n"
                "from synthetic_helper import same\n"
                "from synthetic.toy import value\n\n"
                "def test_value():\n    assert same(value(), EXPECTED)\n"
            )
            (package / "pyproject.toml").write_text("")
            (root / "scripts/tests").mkdir(parents=True)
            (root / "scripts/synthetic_probe.py").write_text("EXPECTED = 2\n")
            (root / "scripts/tests/synthetic_helper.py").write_text(
                "def same(left, right):\n    return left == right\n"
            )
            ledger = root / "explained.toml"
            ledger.write_text("survivors = []\n")
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = runner.run_packages(
                    root, ["custodian/src/synthetic/toy.py"], ledger
                )
            self.assertEqual(code, 0, output.getvalue())
            self.assertIn(
                "custodian/src/synthetic/toy.py: made=1 killed=1 survived=0",
                output.getvalue(),
            )
            self.assertEqual((package / "pyproject.toml").read_text(), "")
            self.assertFalse((package / "mutants").exists())

    def test_package_test_gets_git_own_answer_on_an_ignore_rule(self) -> None:
        # The copy's root is a repository, so git itself evaluates the copied ignore file.
        runner = importlib.import_module("scripts.mutation")
        ambient = dict(os.environ)
        with (
            TemporaryDirectory(prefix="synthetic-ignore-rule-") as temporary,
            TemporaryDirectory(prefix="synthetic-sentinel-") as outside,
        ):
            root = Path(temporary)
            package = root / "custodian"
            (package / "src/synthetic").mkdir(parents=True)
            (package / "tests").mkdir()
            (package / "src/synthetic/__init__.py").write_text("")
            (package / "src/synthetic/toy.py").write_text(
                "def value():\n    return 2\n"
            )
            (package / "tests/test_toy.py").write_text(
                "import subprocess\n"
                "from pathlib import Path\n\n"
                "from synthetic.toy import value\n\n"
                "ROOT = Path(__file__).resolve().parents[3]\n\n"
                "def answer(path):\n"
                "    done = subprocess.run(\n"
                '        ["git", "check-ignore", "-q", "--", path], cwd=ROOT, check=False\n'
                "    )\n"
                "    return done.returncode\n\n"
                "def test_value():\n"
                '    assert (ROOT / ".gitignore").is_file()\n'
                '    assert answer("data/synthetic_cache") == 0\n'
                '    assert answer("kept/synthetic_cache") == 1\n'
                "    assert value() == 2\n"
            )
            (package / "pyproject.toml").write_text("")
            (root / ".gitignore").write_text("data/\n")
            ledger = root / "explained.toml"
            ledger.write_text("survivors = []\n")
            # A caller's git variables name another repository, whose rule is the
            # opposite one: a redirected answer differs, a redirected write shows.
            sentinel = Path(outside) / "sentinel"
            subprocess.run(
                ["git", "init", "--quiet", str(sentinel)],
                check=True,
                capture_output=True,
                env={
                    name: value
                    for name, value in os.environ.items()
                    if not name.startswith("GIT_")
                },
            )
            (sentinel / ".gitignore").write_text("kept/\n")
            # git init puts a missing template file back: a redirected init shows.
            (sentinel / ".git/description").unlink()

            def state() -> dict[str, str]:
                return {
                    path.relative_to(sentinel).as_posix(): (
                        hashlib.sha256(path.read_bytes()).hexdigest()
                        if path.is_file()
                        else "folder"
                    )
                    for path in sorted(sentinel.rglob("*"))
                }

            before = state()
            self.assertIn(".git/HEAD", before)
            output = io.StringIO()
            with (
                contextlib.redirect_stdout(output),
                patch.dict(
                    os.environ,
                    {
                        "GIT_DIR": str(sentinel / ".git"),
                        "GIT_WORK_TREE": str(sentinel),
                    },
                ),
            ):
                code = runner.run_packages(
                    root, ["custodian/src/synthetic/toy.py"], ledger
                )
            self.assertNotIn("GIT_DIR", os.environ.keys() - ambient.keys())
            self.assertEqual(state(), before, "the caller's repository was written")
            self.assertTrue((root / ".git").is_dir(), "the copy is not a repository")
            self.assertEqual(code, 0, output.getvalue())
            self.assertIn(
                "custodian/src/synthetic/toy.py: made=1 killed=1 survived=0",
                output.getvalue(),
            )
            self.assertEqual((package / "pyproject.toml").read_text(), "")
            self.assertFalse((package / "mutants").exists())

    def test_cli_refuses_git_listed_file_outside_package_sources(self) -> None:
        root = Path(__file__).resolve().parents[2]
        result = subprocess.run(
            [sys.executable, "scripts/mutation.py", "scripts/mutation.py"],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn(
            "Every module must be inside core/src, custodian/src or product/src",
            result.stderr,
        )


class EvalMutationRunnerTest(unittest.TestCase):
    def test_only_the_four_named_evaluation_modules_are_allowed(self) -> None:
        mutation = importlib.import_module("scripts.mutation")
        self.assertEqual(
            mutation.EVAL_MODULES,
            {
                "evals/typed_decisions/interval.py",
                "evals/typed_decisions/reproduction.py",
                "evals/typed_decisions/route.py",
                "evals/typed_decisions/requalify.py",
            },
        )
        result = subprocess.run(
            [
                sys.executable,
                "scripts/mutation.py",
                "evals/typed_decisions/__init__.py",
            ],
            cwd=Path(__file__).resolve().parents[2],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("four typed-decision modules", result.stderr)

    def test_git_listed_evals_run_and_unexplained_survivor(self) -> None:
        for assertion, expected in (("== 2", 0), ("> 0", 1)):
            with self.subTest(assertion=assertion):
                self.exercise_runner(assertion, expected)

    def exercise_runner(self, assertion: str, expected: int) -> None:
        mutation = importlib.import_module("scripts.mutation")
        with TemporaryDirectory() as name:
            root = Path(name)
            files = {
                "pyproject.toml": '[tool.pytest]\npythonpath = ["."]\n',
                "evals/__init__.py": "",
                "evals/typed_decisions/__init__.py": "",
                "evals/typed_decisions/interval.py": "def value():\n    return 2\n",
                "scripts/tests/test_requalify.py": (
                    "from evals.typed_decisions.interval import value\n"
                    f"def test_value():\n    assert value() {assertion}\n"
                ),
                "scripts/tests/test_forbidden.py": (
                    'raise AssertionError("unrelated tests must not run")\n'
                ),
                "scripts/mutation_explained.toml": "survivors = []\n",
            }
            for relative, content in files.items():
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content)
            (root / "unlisted.py").write_text("synthetic unlisted sentinel\n")
            real_run = subprocess.run

            def boundary(
                args: list[str], **kwargs: Any
            ) -> subprocess.CompletedProcess[Any]:
                if args[0] == "git":
                    self.assertEqual(
                        args,
                        [
                            "git",
                            "ls-files",
                            "--cached",
                            "--others",
                            "--exclude-standard",
                            "-z",
                        ],
                    )
                    return subprocess.CompletedProcess(
                        args, 0, stdout="\0".join(files).encode()
                    )
                self.assertNotEqual(Path(kwargs["cwd"]), root)
                self.assertFalse((Path(kwargs["cwd"]) / "unlisted.py").exists())
                return real_run(args, **kwargs)

            output = io.StringIO()
            with (
                patch.object(mutation, "ROOT", root),
                patch.object(mutation.subprocess, "run", side_effect=boundary),
                patch.object(
                    sys,
                    "argv",
                    ["mutation.py", "evals/typed_decisions/interval.py"],
                ),
                contextlib.redirect_stdout(output),
            ):
                code = mutation.main()
            self.assertEqual(code, expected, output.getvalue())
            self.assertIn(
                "evals/typed_decisions/interval.py: made=1", output.getvalue()
            )
            if expected:
                row = next(
                    json.loads(line)
                    for line in output.getvalue().splitlines()
                    if line.startswith('{"line":')
                )
                self.assertEqual(row["module"], "evals/typed_decisions/interval.py")
                self.assertIn("return 3", row["mutation"])
            self.assertEqual(
                {
                    p.relative_to(root).as_posix(): p.read_text()
                    for p in root.rglob("*")
                    if p.is_file()
                },
                {**files, "unlisted.py": "synthetic unlisted sentinel\n"},
            )


class SourceGuardSelectionTests(unittest.TestCase):
    def test_unlisted_deselection_refused_by_name(self) -> None:
        runner = importlib.import_module("scripts.mutation")
        with TemporaryDirectory(prefix="synthetic-selection-") as temporary:
            folder = Path(temporary)
            (folder / "pyproject.toml").write_text("")
            output = io.StringIO()
            with contextlib.redirect_stderr(output):
                code, _ = runner.run_copy(
                    folder,
                    ["src/toy.py"],
                    ["tests", "--deselect=tests/test_toy.py::test_value"],
                    folder / "ledger.toml",
                )
            self.assertEqual(code, 2)
            self.assertIn(
                "Refusing test selection option: --deselect=tests/test_toy.py::test_value",
                output.getvalue(),
            )
            self.assertEqual((folder / "pyproject.toml").read_text(), "")
            with (
                patch.dict("os.environ", {"PYTEST_ADDOPTS": "--deselect=unlisted"}),
                contextlib.redirect_stderr(output),
            ):
                code, _ = runner.run_copy(
                    folder, ["src/toy.py"], ["tests"], folder / "ledger.toml"
                )
            self.assertEqual(code, 2)
            self.assertIn("PYTEST_ADDOPTS", output.getvalue())

    def test_closed_guards_collected_by_ordinary_suite(self) -> None:
        runner = importlib.import_module("scripts.mutation")
        suite_runner = importlib.import_module("scripts.run_tests")
        suites = suite_runner.SUITES
        root = Path(__file__).resolve().parents[2]
        collected: set[str] = set()
        for suite in suites:
            if suite.kind != "pytest" or not any(
                node.startswith(suite.args[0] + "/")
                for node in runner.SOURCE_TEXT_GUARDS
            ):
                continue
            self.assertFalse(any(arg.startswith("-") for arg in suite.args))
            with TemporaryDirectory(prefix="synthetic-collection-") as temporary:
                command = suite_runner.runner_exec.build_command(
                    suite, root, {}, Path(temporary), 1
                )
                self.assertFalse(any(arg.startswith("--deselect") for arg in command))
                result = subprocess.run(
                    [*command, "--collect-only", "-q"],
                    cwd=root / suite.cwd,
                    text=True,
                    capture_output=True,
                    check=False,
                )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            collected.update(line.strip() for line in result.stdout.splitlines())
        self.assertTrue(set(runner.SOURCE_TEXT_GUARDS) <= collected)
        # An invented listed node outside the ordinary suite must fail membership.
        with self.assertRaises(AssertionError):
            self.assertTrue(
                set(runner.SOURCE_TEXT_GUARDS)
                | {"core/data_tests/test_invented.py::test_guard"}
                <= collected
            )
