"""M2: run the pinned mutation tool on a tiny invented temporary module."""

import contextlib
import importlib
import io
import json
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
            package = root / "custodian"
            (package / "src/synthetic").mkdir(parents=True)
            (package / "tests").mkdir()
            (package / "src/synthetic/__init__.py").write_text("")
            (package / "src/synthetic/toy.py").write_text(
                "def value():\n    return 2\n"
            )
            (package / "tests/test_toy.py").write_text(
                "from synthetic.toy import value\n\ndef test_value():\n    assert value() == 2\n"
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
                    ],
                ),
            ):
                code = runner.main()
            self.assertEqual(code, 0)
            for name in ("custodian", "product"):
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

    def test_cli_refuses_git_listed_file_outside_package_sources(self) -> None:
        root = Path(__file__).resolve().parents[2]
        result = subprocess.run(
            [sys.executable, "scripts/mutation.py", "core/src/eii_core/__init__.py"],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn(
            "Every module must be inside custodian/src or product/src", result.stderr
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
