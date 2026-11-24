"""Bootstrap tests for the pytest table, seed and sibling imports."""

from __future__ import annotations

import ast
import itertools
import os
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import runner_support as support

ROOT = support.ROOT

# OI-409: a property whose body does file or folder work per example sets
# deadline=None; the closed call lists below mark that work.
FILE_NAMES = (
    "open",
    "Path",
    "TemporaryDirectory",
    "NamedTemporaryFile",
    "mkdtemp",
    "mkstemp",
)
FILE_METHODS = (
    "TemporaryDirectory",
    "NamedTemporaryFile",
    "mkdtemp",
    "mkstemp",
    "mktemp",
    "read_bytes",
    "read_text",
    "write_bytes",
    "write_text",
    "mkdir",
    "unlink",
    "iterdir",
    "rglob",
    "symlink_to",
    "touch",
    "rmtree",
    "copyfile",
    "copytree",
    "Popen",
    "check_output",
    "check_call",
)
FILE_QUALIFIED = (
    "subprocess.run",
    "sqlite3.connect",
    "duckdb.connect",
    "os.remove",
    "os.rename",
    "os.replace",
    "os.makedirs",
    "os.listdir",
    "os.scandir",
    "shutil.copy",
    "shutil.move",
    "glob.glob",
)
FILE_FIXTURES = ("tmp_path", "tmp_path_factory", "tmpdir", "tmpdir_factory")
PROPERTY_ROOTS = (
    "core/tests",
    "custodian/tests",
    "product/tests",
    "scripts/tests",
    "evals",
)


def _is_file_call(call: ast.Call) -> bool:
    func = call.func
    if isinstance(func, ast.Name):
        return func.id in FILE_NAMES
    if not isinstance(func, ast.Attribute):
        return False
    if isinstance(func.value, ast.Name):
        if f"{func.value.id}.{func.attr}" in FILE_QUALIFIED:
            return True
    return func.attr in FILE_METHODS


def _callee(call: ast.Call) -> str | None:
    func = call.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
        return func.attr if func.value.id in ("self", "cls") else None
    return None


def _does_file_work(
    function: ast.FunctionDef | ast.AsyncFunctionDef,
    helpers: dict[str, ast.FunctionDef | ast.AsyncFunctionDef],
    seen: set[str],
) -> bool:
    """True when the body, or a module helper it calls, does file work."""
    arguments = function.args.posonlyargs + function.args.args
    arguments += function.args.kwonlyargs
    if any(item.arg in FILE_FIXTURES for item in arguments):
        return True
    for node in ast.walk(function):
        if not isinstance(node, ast.Call):
            continue
        if _is_file_call(node):
            return True
        name = _callee(node)
        if name in helpers and name not in seen:
            seen.add(name)
            if _does_file_work(helpers[name], helpers, seen):
                return True
    return False


def _settings_names(tree: ast.Module) -> set[str]:
    names = {"settings"}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "hypothesis":
            names |= {a.asname for a in node.names if a.name == "settings" and a.asname}
    return names


def _decorator_name(decorator: ast.expr) -> str | None:
    target = decorator.func if isinstance(decorator, ast.Call) else decorator
    if isinstance(target, ast.Name):
        return target.id
    return target.attr if isinstance(target, ast.Attribute) else None


def _has_no_deadline(
    function: ast.FunctionDef | ast.AsyncFunctionDef, settings_names: set[str]
) -> bool:
    for decorator in function.decorator_list:
        if not isinstance(decorator, ast.Call):
            continue
        if _decorator_name(decorator) not in settings_names:
            continue
        for keyword in decorator.keywords:
            value = keyword.value
            if keyword.arg == "deadline" and isinstance(value, ast.Constant):
                if value.value is None:
                    return True
    return False


def deadline_violations(text: str) -> list[str]:
    """Name and line of each file-backed property still under the deadline."""
    tree = ast.parse(text)
    functions = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
    ]
    helpers = {function.name: function for function in functions}
    names = _settings_names(tree)
    return [
        f"{function.name}:{function.lineno}"
        for function in functions
        if any(_decorator_name(item) == "given" for item in function.decorator_list)
        and _does_file_work(function, helpers, {function.name})
        and not _has_no_deadline(function, names)
    ]


_PLANT = (
    "import tempfile\n"
    "from hypothesis import given, settings\n"
    "from hypothesis import strategies as st\n\n"
    "{decorator}"
    "@given(st.text())\n"
    "def test_plant(text):\n"
    "    with tempfile.TemporaryDirectory() as folder:\n"
    "        assert folder\n"
)


class TestBootstrap(unittest.TestCase):
    def test_pytest_table(self) -> None:
        data = self._table()
        pytest_table = data["tool"]["pytest"]
        self.assertIs(pytest_table["strict"], True)
        markers = [item.split(":", 1)[0].strip() for item in pytest_table["markers"]]
        for name in ("postgres", "sandbox", "nightly", "live_model"):
            self.assertIn(name, markers, f"FAIL pytest-table: markers: missing {name}")
        addopts = pytest_table["addopts"]
        pairs = list(itertools.pairwise(addopts))
        self.assertIn(("-m", "not nightly"), pairs, "FAIL pytest-table: addopts: -m")
        self.assertIn("--hypothesis-profile=eii", addopts)
        self.assertIn("--import-mode=importlib", addopts)
        for entry in (
            "scripts",
            "scripts/tests",
            "core/src",
            "custodian/src",
            "product/src",
        ):
            self.assertIn(entry, pytest_table["pythonpath"], entry)
        dev = data["dependency-groups"]["dev"]
        for name in ("pytest", "hypothesis"):
            match = [item for item in dev if re.fullmatch(rf"{name}==[0-9.]+", item)]
            self.assertTrue(match, f"FAIL pytest-table: dev: missing {name}")

    def test_seed_reaches_hypothesis_and_random(self) -> None:
        self._table()
        root = self._root()
        support.put(
            root,
            "fx/seed/test_seed.py",
            "import random\n"
            "print('RANDOM', random.random())\n"
            "from hypothesis import given, settings\n"
            "from hypothesis import strategies as st\n\n"
            "@given(st.integers())\n"
            "def test_ex(number):\n"
            "    print('EX', number)\n\n"
            "@settings(derandomize=True)\n"
            "@given(st.integers())\n"
            "def test_dx(number):\n"
            "    print('DX', number)\n",
        )
        first = self._pytest(root, ["-s", "--hypothesis-seed", "1794000000", "fx/seed"])
        second = self._pytest(
            root, ["-s", "--hypothesis-seed", "1794000000", "fx/seed"]
        )
        third = self._pytest(root, ["-s", "--hypothesis-seed", "1794000001", "fx/seed"])
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        self.assertEqual(self._lines(first, "EX "), self._lines(second, "EX "))
        self.assertEqual(self._lines(first, "RANDOM "), self._lines(second, "RANDOM "))
        self.assertNotEqual(self._lines(first, "EX "), self._lines(third, "EX "))
        self.assertNotEqual(
            self._lines(first, "RANDOM "), self._lines(third, "RANDOM ")
        )
        self.assertEqual(self._lines(first, "DX "), self._lines(third, "DX "))
        self.assertIn("eii seed=1794000000", first.stdout + first.stderr)

    def test_profile_is_eii_and_survives_a_ci_variable(self) -> None:
        self._table()
        root = self._root()
        # The profile name is printed through the public function when it exists.
        support.put(
            root,
            "fx/profile/test_profile.py",
            "from hypothesis import settings\n\n"
            "def test_profile():\n"
            "    current = settings()\n"
            "    print('NAME', settings._profiles and '')\n"
            "    name = getattr(settings, 'get_current_profile_name', None)\n"
            "    print('PROFILE', name() if name else 'missing')\n"
            "    print('MAX', current.max_examples)\n"
            "    print('DB', current.database)\n"
            "    print('BLOB', current.print_blob)\n"
            "    print('DERAND', current.derandomize)\n"
            "    deadline = current.deadline\n"
            "    print('DEADLINE', None if deadline is None else int(deadline.total_seconds() * 1000))\n",
        )
        env = self._env(root)
        env["CI"] = "true"
        proc = self._pytest(root, ["-s", "fx/profile"], env)
        text = proc.stdout + proc.stderr
        self.assertEqual(proc.returncode, 0, text)
        self.assertIn("PROFILE eii", text)
        self.assertIn("MAX 100", text)
        self.assertIn("DB None", text)
        self.assertIn("BLOB True", text)
        self.assertIn("DERAND False", text)
        self.assertIn("DEADLINE 200", text)
        control = self._temp()
        support.put(
            control,
            "test_profile.py",
            (root / "fx" / "profile" / "test_profile.py").read_text(encoding="utf-8"),
        )
        support.put(control, "pytest.ini", "[pytest]\n")
        bare = {key: value for key, value in env.items() if key != "PYTEST_ADDOPTS"}
        proc = subprocess.run(
            [
                sys.executable,
                "-P",
                "-s",
                "-m",
                "pytest",
                "-c",
                "pytest.ini",
                "--noconftest",
                "-s",
                "test_profile.py",
            ],
            cwd=control,
            env=bare,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        self.assertIn(
            "PROFILE ci", proc.stdout + proc.stderr, proc.stdout + proc.stderr
        )

    def test_file_backed_properties_carry_no_deadline(self) -> None:
        problems = [
            f"{path.relative_to(ROOT)}::{item}"
            for base in PROPERTY_ROOTS
            for path in sorted((ROOT / base).rglob("*.py"))
            for item in deadline_violations(path.read_text(encoding="utf-8"))
        ]
        self.assertEqual(problems, [], "FAIL hypothesis-deadline: file work")

    def test_deadline_guard_plant(self) -> None:
        red = _PLANT.format(decorator="")
        self.assertEqual(deadline_violations(red), ["test_plant:6"])
        green = _PLANT.format(decorator="@settings(deadline=None)\n")
        self.assertEqual(deadline_violations(green), [])
        kept = "@settings(deadline=None, max_examples=5)\n"
        self.assertEqual(deadline_violations(_PLANT.format(decorator=kept)), [])

    def test_deadline_guard_routes(self) -> None:
        body = "    with tempfile.TemporaryDirectory() as folder:\n"
        base = _PLANT.format(decorator="")
        cases = {
            "method": "    tempfile.mkdtemp()\n",
            "bare": "    open('x')\n",
            "qualified": "    subprocess.run(['x'])\n",
            "helper": "    _helper()\n",
            "self-helper": "    self._helper()\n",
        }
        for name, line in cases.items():
            with self.subTest(route=name):
                red = base.replace(body, line + "    if False:\n")
                red += "\ndef _helper():\n    Path('x').write_text('y')\n"
                self.assertEqual(deadline_violations(red), ["test_plant:6"])
        pure = base.replace(body, "    assert text == text\n    if False:\n")
        self.assertEqual(deadline_violations(pure), [])
        fixture = pure.replace("def test_plant(text)", "def test_plant(tmp_path, text)")
        self.assertEqual(deadline_violations(fixture), ["test_plant:6"])
        nested = "def test_outer():\n" + "".join(
            f"    {line}\n" for line in _PLANT.format(decorator="").splitlines()
        )
        self.assertEqual(deadline_violations(nested), ["test_plant:7"])
        other = "@settings(deadline=500)\n"
        self.assertEqual(
            deadline_violations(_PLANT.format(decorator=other)), ["test_plant:7"]
        )
        alias = _PLANT.replace("given, settings", "given, settings as hs")
        alias = alias.format(decorator="@hs(deadline=None)\n")
        self.assertEqual(deadline_violations(alias), [])
        replaced = _PLANT.format(decorator="@settings(max_examples=5)\n")
        self.assertEqual(deadline_violations(replaced), ["test_plant:7"])
        marker = _PLANT.format(decorator="@marker(deadline=None)\n")
        self.assertEqual(deadline_violations(marker), ["test_plant:7"])

    def test_bare_run_still_prints_a_seed(self) -> None:
        self._table()
        root = self._root()
        support.put(root, "fx/bare/test_one.py", "def test_one():\n    assert True\n")
        proc = self._pytest(root, ["fx/bare"])
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertTrue(
            any(
                re.fullmatch(r"eii seed=[0-9]{10}", line.strip())
                for line in (proc.stdout + proc.stderr).splitlines()
            ),
            proc.stdout + proc.stderr,
        )

    def test_unregistered_marker_is_an_error(self) -> None:
        self._table()
        root = self._root()
        support.put(
            root,
            "fx/mark/test_mark.py",
            "import pytest\n\n"
            "@pytest.mark.nightlyy\n"
            "def test_one():\n    assert True\n",
        )
        proc = self._pytest(root, ["fx/mark"])
        self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
        self.assertIn(
            "'nightlyy' not found in `markers` configuration option",
            proc.stdout + proc.stderr,
        )
        proc = self._pytest(root, ["-m", "nightlyy", "fx/mark"])
        self.assertEqual(proc.returncode, 4, proc.stdout + proc.stderr)
        self.assertIn("nightlyy", proc.stdout + proc.stderr)

    def test_default_selection(self) -> None:
        self._table()
        root = self._root()
        support.put(
            root,
            "fx/select/test_select.py",
            "import pytest\n\n"
            "@pytest.mark.nightly\n"
            "def test_night():\n    assert False\n\n"
            "@pytest.mark.postgres\n"
            "def test_pg():\n    pytest.skip('OI-10 no database')\n\n"
            "@pytest.mark.live_model\n"
            "def test_live():\n    pytest.skip('OI-01 no key')\n\n"
            "@pytest.mark.sandbox\n"
            "def test_box():\n    assert True\n\n"
            "def test_plain():\n    assert True\n",
        )
        junit = root / "result.xml"
        proc = self._pytest(root, ["--junit-xml", str(junit), "fx/select"])
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        cases = list(ET.parse(junit).getroot().iter("testcase"))
        self.assertEqual(len(cases), 4)
        skipped = [
            item for item in cases if any(child.tag == "skipped" for child in item)
        ]
        self.assertEqual(len(skipped), 2)
        messages = " ".join(
            child.get("message", "")
            for item in skipped
            for child in item
            if child.tag == "skipped"
        )
        self.assertIn("OI-10 no database", messages)
        self.assertIn("OI-01 no key", messages)
        proc = self._pytest(
            root, ["-m", "nightly", "--junit-xml", str(junit), "fx/select"]
        )
        self.assertNotEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("test_night", proc.stdout + proc.stderr)

    def test_sibling_import_in_the_test_folder(self) -> None:
        self._table()
        shapes = {
            "a": {
                "scripts/tests/sibling_tables.py": "VALUE = 3\n",
                "scripts/tests/sibling_helper.py": (
                    "import sibling_tables as tables\n\n"
                    "def value():\n    return tables.VALUE\n"
                ),
                "scripts/tests/test_uses_helper.py": (
                    "import unittest\nimport sibling_helper as helper\n\n"
                    "class Uses(unittest.TestCase):\n"
                    "    def test_value(self):\n        self.assertEqual(helper.value(), 3)\n"
                ),
                "pytest": "1 passed",
                "unittest": "Ran 1 test",
                "missing": "sibling_helper",
            },
            "b": {
                "scripts/tests/test_base_cases.py": (
                    "import unittest\n\n"
                    "class BaseCase(unittest.TestCase):\n"
                    "    def test_base(self):\n        self.assertTrue(True)\n"
                ),
                "scripts/tests/test_derived_cases.py": (
                    "import unittest\nimport test_base_cases as base\n\n"
                    "class DerivedCase(base.BaseCase):\n"
                    "    def test_derived(self):\n        self.assertTrue(True)\n"
                ),
                "pytest": "3 passed",
                "unittest": "Ran 3 tests",
                "missing": "test_base_cases",
            },
            "c": {
                "scripts/tests/test_provider.py": (
                    "import unittest\n\n"
                    "def make():\n    return 'x'\n\n"
                    "class Provider(unittest.TestCase):\n"
                    "    def test_make(self):\n        self.assertEqual(make(), 'x')\n"
                ),
                "scripts/tests/test_consumer.py": (
                    "import unittest\nimport test_provider as provider\n\n"
                    "class Consumer(unittest.TestCase):\n"
                    "    def test_make(self):\n        self.assertEqual(provider.make(), 'x')\n"
                ),
                "pytest": "2 passed",
                "unittest": "Ran 2 tests",
                "missing": "test_provider",
            },
        }
        for name, files in shapes.items():
            with self.subTest(shape=name):
                root = self._root()
                for rel, text in files.items():
                    if rel.endswith(".py"):
                        support.put(root, rel, text)
                proc = self._pytest(root, ["scripts/tests"])
                self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
                self.assertIn(str(files["pytest"]), proc.stdout + proc.stderr)
                unit = subprocess.run(
                    [
                        sys.executable,
                        "-B",
                        "-m",
                        "unittest",
                        "discover",
                        "-s",
                        "scripts/tests",
                        "-p",
                        "test_*.py",
                    ],
                    cwd=root,
                    env=self._env(root),
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    check=False,
                )
                self.assertEqual(unit.returncode, 0, unit.stdout + unit.stderr)
                self.assertIn(str(files["unittest"]), unit.stderr + unit.stdout)
                text = (root / "pyproject.toml").read_text(encoding="utf-8")
                updated, count = re.subn(r'"scripts/tests",\n', "", text, count=1)
                self.assertEqual(count, 1)
                (root / "pyproject.toml").write_text(updated, encoding="utf-8")
                proc = self._pytest(root, ["scripts/tests"])
                self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
                self.assertIn(
                    f"No module named '{files['missing']}'",
                    proc.stdout + proc.stderr,
                )

    def _table(self) -> dict[str, Any]:
        path = ROOT / "pyproject.toml"
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        tool = data.get("tool", {})
        if "pytest" not in tool:
            self.fail("FAIL pytest-table: tool.pytest: missing")
        return data

    def _root(self) -> Path:
        root = self._temp()
        shutil.copy2(ROOT / "pyproject.toml", root / "pyproject.toml")
        shutil.copy2(ROOT / "conftest.py", root / "conftest.py")
        for rel in (
            "scripts/tests",
            "core/src",
            "custodian/src",
            "product/src",
        ):
            (root / rel).mkdir(parents=True)
        return root

    def _temp(self) -> Path:
        path = Path(tempfile.mkdtemp(prefix="eii-boot-"))
        self.addCleanup(shutil.rmtree, path, ignore_errors=True)
        return path

    def _env(self, root: Path) -> dict[str, str]:
        env: dict[str, str] = {}
        for name in (
            "PATH",
            "HOME",
            "LANG",
            "LC_ALL",
            "TMPDIR",
            "XDG_DATA_HOME",
            "UV_PYTHON_INSTALL_DIR",
        ):
            if name in os.environ:
                env[name] = os.environ[name]
        env["PYTHONHASHSEED"] = support.FIXTURE_SEED
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env["EII_DECISION_PROVIDER"] = "none"
        env["NO_COLOR"] = "1"
        env["HYPOTHESIS_STORAGE_DIRECTORY"] = str(root / "hypothesis")
        return env

    def _pytest(
        self,
        root: Path,
        args: list[str],
        env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
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
                *args,
            ],
            cwd=root,
            env=env if env is not None else self._env(root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )

    def _lines(self, proc: subprocess.CompletedProcess[str], prefix: str) -> list[str]:
        text = proc.stdout + "\n" + proc.stderr
        return [line for line in text.splitlines() if prefix in line]
