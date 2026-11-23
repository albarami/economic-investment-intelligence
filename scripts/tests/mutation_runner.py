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
from collections.abc import Callable, Iterable, Mapping
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

    def test_timeout_rows_preserve_survivors_and_exit_status(self) -> None:
        runner = importlib.import_module("scripts.mutation")
        mutation = "@@ -1 +1 @@\n-return 2\n+return 3"
        for survivor_codes, expected_exit in (({}, 0), ({"toy.z": 0, "toy.b": 5}, 1)):
            with self.subTest(survivor_codes=survivor_codes):
                with TemporaryDirectory(prefix="synthetic-timeouts-") as temporary:
                    folder = Path(temporary)
                    (folder / "pyproject.toml").write_text("")
                    ledger = folder / "ledger.toml"
                    ledger.write_text("survivors = []\n")
                    codes = {
                        "toy.timeout_z": 36,
                        **survivor_codes,
                        "toy.timeout_a": -24,
                    }

                    def fake_command(
                        work: Path,
                        *arguments: str,
                        codes: dict[str, int] = codes,
                        survivor_codes: dict[str, int] = survivor_codes,
                        **kwargs: Any,
                    ) -> subprocess.CompletedProcess[str]:
                        if arguments[0] == "run":
                            meta = work / "mutants/src/toy.py.meta"
                            meta.parent.mkdir(parents=True)
                            meta.write_text(json.dumps({"exit_code_by_key": codes}))
                            stdout = ""
                        else:
                            self.assertEqual(arguments[0], "show")
                            self.assertIn(arguments[1], survivor_codes)
                            stdout = "mutant heading\n" + mutation + arguments[1] + "\n"
                        return subprocess.CompletedProcess(arguments, 0, stdout, "")

                    output = io.StringIO()
                    with (
                        patch.object(runner, "command", side_effect=fake_command),
                        contextlib.redirect_stdout(output),
                    ):
                        code, survivors = runner.run_copy(
                            folder, ["src/toy.py"], ["tests"], ledger, "product/"
                        )
                    rows = [
                        {"module": "product/src/toy.py", "mutation": mutation + key}
                        for key in survivor_codes
                    ]
                    self.assertEqual(code, expected_exit)
                    self.assertEqual(survivors, rows)
                    lines = output.getvalue().splitlines()
                    self.assertEqual(
                        lines[1:-1],
                        [
                            json.dumps({**row, "line": "1"}, sort_keys=True)
                            for row in rows
                        ]
                        + [
                            json.dumps(
                                {
                                    "module": "product/src/toy.py",
                                    "status": "timed_out",
                                    "mutant": key,
                                    "exit_code": codes[key],
                                },
                                sort_keys=True,
                            )
                            for key in ("toy.timeout_a", "toy.timeout_z")
                        ],
                    )
                    self.assertEqual(
                        lines[-1],
                        f"product/src/toy.py: made={len(codes)} killed=0 "
                        f"survived={int(bool(survivor_codes))} timed_out=2 "
                        f"not_covered={int(bool(survivor_codes))} incomplete=0",
                    )

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
                    stdout = (
                        str(kwargs["cwd"]).encode()
                        if "rev-parse" in arguments
                        else listed
                    )
                    return subprocess.CompletedProcess(arguments, 0, stdout=stdout)
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
            (root / "pyproject.toml").write_text("")
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
            (root / "pyproject.toml").write_text("")
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
            (root / "pyproject.toml").write_text("")
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
                    if "rev-parse" in args:
                        self.assertEqual(args, ["git", "rev-parse", "--show-toplevel"])
                        self.assertEqual(kwargs["cwd"], root)
                        return subprocess.CompletedProcess(
                            args, 0, stdout=str(root).encode()
                        )
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
    def _assert_no_selection_options(self, name: str, options: Iterable[str]) -> None:
        """Refuse all suite options except the exact custodian part sequences."""
        args = tuple(options)
        if args in (
            ("custodian/tests", "-p", "pytest_custodian_part", "--custodian-part", "1"),
            ("custodian/tests", "-p", "pytest_custodian_part", "--custodian-part", "2"),
            ("custodian/tests", "-p", "pytest_custodian_part", "--custodian-part", "3"),
            ("custodian/tests", "-p", "pytest_custodian_part", "--custodian-part", "4"),
            ("custodian/tests", "-p", "pytest_custodian_part", "--custodian-part", "5"),
        ):
            return
        offenders = [option for option in args if option.startswith("-")]
        self.assertFalse(offenders, f"the suite {name} selects tests: {offenders}")

    def _assert_parts_collect_guards(
        self,
        suites: Iterable[Any],
        guards: Iterable[str],
        module_part: Callable[[str], int],
    ) -> None:
        """Refuse a part split that leaves a guard module outside every part."""
        parts: set[int] = set()
        prefixes: set[str] = set()
        for suite in suites:
            if suite.kind != "pytest" or "--custodian-part" not in suite.args:
                continue
            parts.add(int(suite.args[suite.args.index("--custodian-part") + 1]))
            prefixes.add(suite.args[0])
        for node in guards:
            if not any(node.startswith(prefix + "/") for prefix in prefixes):
                continue
            self.assertIn(
                module_part(node.split("::", 1)[0]),
                parts,
                f"the part split collects the guard {node} in no named part",
            )

    def _collect_suite(
        self, suite: Any, root: Path, parent: Mapping[str, str], tmp: Path
    ) -> subprocess.CompletedProcess[str]:
        """Probe ordinary collection with the runner's command and environment."""
        suite_runner = importlib.import_module("scripts.run_tests")
        self._assert_no_selection_options(suite.name, suite.args)
        env = suite_runner.runner_exec.child_env(
            suite.kind,
            dict(parent) | {"TMPDIR": str(tmp)},
            1,
            tmp,
        )
        command = suite_runner.runner_exec.build_command(suite, root, env, tmp, 1)
        # Pin the runner-owned prefix separately so its config and reporting
        # options cannot become exceptions for arbitrary suite arguments.
        fixed = [
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
            str(tmp / "result.xml"),
            "--hypothesis-seed",
            "1",
        ]
        self.assertEqual(command, [*fixed, *suite.args])
        self._assert_no_selection_options(suite.name, command[len(fixed) :])
        # Config addopts still apply in the real collection; a config entry
        # that removes a guard fails the ordinary-suite membership assertion.
        return subprocess.run(
            [*command, "--collect-only", "-q"],
            cwd=root / suite.cwd,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_only_exact_custodian_partition_options_accepted(self) -> None:
        for value in ("1", "2", "3", "4", "5"):
            self._assert_no_selection_options(
                "python-custodian-" + value,
                (
                    "custodian/tests",
                    "-p",
                    "pytest_custodian_part",
                    "--custodian-part",
                    value,
                ),
            )
        self._assert_no_selection_options("python-core", ("core/tests",))
        for args in (
            ("core/tests", "--co"),
            ("core/tests", "-p", "some_plugin"),
            ("custodian/tests", "-p", "pytest_custodian_part", "--custodian-part", "6"),
            ("core/tests", "-x"),
            ("core/tests", "--maxfail=1"),
            ("core/tests", "-c", "alternate.toml"),
            ("core/tests", "-o", "addopts=--co"),
            ("core/tests", "-kguard"),
            ("core/tests", "-p", "pytest_custodian_part", "--custodian-part", "1"),
            ("custodian/tests", "--custodian-part", "1", "-p", "pytest_custodian_part"),
            ("custodian/tests", "-p", "pytest_custodian_part", "--custodian-part=1"),
            (
                "custodian/tests",
                "-p",
                "pytest_custodian_part",
                "--custodian-part",
                "1",
                "--co",
            ),
        ):
            with self.subTest(args=args), self.assertRaises(AssertionError):
                self._assert_no_selection_options("synthetic-suite", args)

    def test_collection_environment_matches_ordinary_runner(self) -> None:
        suite_runner = importlib.import_module("scripts.run_tests")
        parent = dict(os.environ) | {
            "LANG": "C",
            "LC_ALL": "C",
            "XDG_DATA_HOME": "synthetic-runner-xdg",
            "UV_PYTHON_INSTALL_DIR": "synthetic-python-install",
        }
        with TemporaryDirectory(prefix="synthetic-environment-parity-") as temporary:
            root = Path(temporary)
            (root / "pyproject.toml").write_text("")
            (root / "conftest.py").write_text(
                "import os\n"
                "def pytest_collection_modifyitems(items):\n"
                "    if os.environ.get('LANG') != 'C':\n"
                "        items.clear()\n"
            )
            (root / "test_guard.py").write_text("def test_guard():\n    assert True\n")
            suite = suite_runner.Suite(
                "synthetic-environment-parity", "pytest", ".", ("test_guard.py",), 60
            )
            ordinary = suite_runner.run_suite(suite, 1, root, parent, {})
            self.assertEqual(ordinary.fail_lines, ())
            self.assertIsNotNone(ordinary.counts)
            assert ordinary.counts is not None
            self.assertEqual(ordinary.counts.passed, 1)
            with patch.object(
                suite_runner.runner_exec,
                "build_command",
                wraps=suite_runner.runner_exec.build_command,
            ) as build:
                result = self._collect_suite(suite, root, parent, root)
            self.assertEqual(
                build.call_args.args[2].get("LANG"),
                parent["LANG"],
                "the runner and collection probe must preserve the same LANG",
            )
            self.assertEqual(
                build.call_args.args[2],
                suite_runner.runner_exec.child_env(
                    suite.kind, parent | {"TMPDIR": str(root)}, 1, root
                ),
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("test_guard.py::test_guard", result.stdout.splitlines())

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
        part = importlib.import_module("scripts.pytest_custodian_part")
        suites = suite_runner.SUITES
        root = Path(__file__).resolve().parents[2]
        guards = set(runner.SOURCE_TEXT_GUARDS)
        parent = dict(os.environ)
        collected: set[str] = set()
        for suite in suites:
            if suite.kind != "pytest" or not any(
                node.startswith(suite.args[0] + "/") for node in guards
            ):
                continue
            with TemporaryDirectory(prefix="synthetic-collection-") as temporary:
                result = self._collect_suite(suite, root, parent, Path(temporary))
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            collected.update(line.strip() for line in result.stdout.splitlines())
        # The union of the named custodian parts counts as the ordinary suite.
        self.assertTrue(guards <= collected)
        self._assert_parts_collect_guards(suites, guards, part.module_part)
        # An invented listed node outside the ordinary suites must fail membership.
        with self.assertRaises(AssertionError):
            self.assertTrue(
                (guards | {"core/data_tests/test_invented.py::test_guard"}) <= collected
            )
        # A suite argument that deselects a guard must fail the option scan.
        holder = next(
            suite
            for suite in suites
            if suite.kind == "pytest"
            and any(node.startswith(suite.args[0] + "/") for node in guards)
        )
        guard = sorted(
            node for node in guards if node.startswith(holder.args[0] + "/")
        )[0]
        with self.assertRaises(AssertionError):
            self._assert_no_selection_options(
                holder.name, (*holder.args, "--deselect=" + guard)
            )
        # Dropping the part that holds a guard leaves it collected by no named
        # part and must fail the split check.
        split_guards = sorted(
            node
            for node in guards
            if any(
                suite.kind == "pytest"
                and "--custodian-part" in suite.args
                and node.startswith(suite.args[0] + "/")
                for suite in suites
            )
        )
        self.assertTrue(
            split_guards,
            "no source-text guard lives under a part-split suite; the planted "
            "neither-part case needs one",
        )
        dropped = part.module_part(split_guards[0].split("::", 1)[0])
        without_the_part = tuple(
            suite
            for suite in suites
            if not (
                suite.kind == "pytest"
                and "--custodian-part" in suite.args
                and int(suite.args[suite.args.index("--custodian-part") + 1]) == dropped
            )
        )
        with self.assertRaises(AssertionError):
            self._assert_parts_collect_guards(
                without_the_part, guards, part.module_part
            )
