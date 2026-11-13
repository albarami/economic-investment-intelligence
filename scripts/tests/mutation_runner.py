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
        runner = importlib.import_module("mutation")
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
        runner = importlib.import_module("mutation")
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
        runner = importlib.import_module("mutation")
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
        runner = importlib.import_module("mutation")
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
