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
from typing import Any, NamedTuple

import runner_support as support

ROOT = support.ROOT

# OI-409: a property whose body does file or folder work per example sets
# deadline=None; the closed call lists below mark that work. A name bound by
# `from M import N [as A]` counts when N is in FILE_NAMES or FILE_METHODS or
# M.N is in FILE_QUALIFIED; `from M import *` binds every FILE_METHODS name and
# each N of an M.N in FILE_QUALIFIED; `import M as A` makes A.N count as M.N.
# Names that are file work only on one module (walk, call, system, link) are
# qualified only, so ast.walk, mock.call and platform.system stay outside.
# Still not seen: calls into imported production code; `os.path.*` and other
# calls through a dotted module (`os.path.exists`, `xml.etree...`); a file
# call reached through a variable or getattr (`f = open; f(...)`); helpers in
# another module, or methods called through anything but self or cls;
# `importlib`/`__import__` loads; file work in a strategy, fixture or setUp
# rather than in the decorated body; relative imports; names of the closed
# lists not given here.
FILE_NAMES = (
    "open",
    "Path",
    "TemporaryDirectory",
    "NamedTemporaryFile",
    "TemporaryFile",
    "SpooledTemporaryFile",
    "mkdtemp",
    "mkstemp",
)
FILE_METHODS = (
    "TemporaryDirectory",
    "NamedTemporaryFile",
    "TemporaryFile",
    "SpooledTemporaryFile",
    "mkdtemp",
    "mkstemp",
    "mktemp",
    "open",
    "fdopen",
    "read_bytes",
    "read_text",
    "write_bytes",
    "write_text",
    "mkdir",
    "rmdir",
    "unlink",
    "truncate",
    "iterdir",
    "glob",
    "iglob",
    "rglob",
    "symlink",
    "symlink_to",
    "chmod",
    "chown",
    "touch",
    "rmtree",
    "copyfile",
    "copyfileobj",
    "copymode",
    "copy2",
    "copytree",
    "make_archive",
    "ZipFile",
    "Popen",
    "popen",
    "check_output",
    "check_call",
    "getoutput",
    "getstatusoutput",
)
FILE_QUALIFIED = (
    "subprocess.run",
    "subprocess.call",
    "subprocess.getoutput",
    "subprocess.getstatusoutput",
    "sqlite3.connect",
    "duckdb.connect",
    "io.open",
    "codecs.open",
    "os.open",
    "os.fdopen",
    "os.remove",
    "os.rename",
    "os.replace",
    "os.makedirs",
    "os.rmdir",
    "os.listdir",
    "os.scandir",
    "os.walk",
    "os.symlink",
    "os.link",
    "os.chmod",
    "os.truncate",
    "os.system",
    "os.popen",
    "shutil.copy",
    "shutil.copy2",
    "shutil.copyfileobj",
    "shutil.copymode",
    "shutil.move",
    "shutil.make_archive",
    "shutil.chown",
    "glob.glob",
    "glob.iglob",
    "pathlib.Path",
    "tempfile.TemporaryFile",
    "tempfile.SpooledTemporaryFile",
    "zipfile.ZipFile",
    "tarfile.open",
    "gzip.open",
    "bz2.open",
    "lzma.open",
    "shelve.open",
    "dbm.open",
)
FILE_FIXTURES = ("tmp_path", "tmp_path_factory", "tmpdir", "tmpdir_factory")
PROPERTY_ROOTS = (
    "core/tests",
    "custodian/tests",
    "product/tests",
    "scripts/tests",
    "evals",
)


class _Bindings(NamedTuple):
    names: frozenset[str]
    modules: dict[str, str]


def _bindings(tree: ast.Module) -> _Bindings:
    """File-call names and module aliases that the module's imports bind."""
    names = set(FILE_NAMES)
    modules: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules |= {a.asname: a.name for a in node.names if a.asname}
        elif isinstance(node, ast.ImportFrom) and node.module:
            names |= _from_names(node.module, node.names)
    return _Bindings(frozenset(names), modules)


def _from_names(module: str, aliases: list[ast.alias]) -> set[str]:
    """Names that `from module import ...` binds to closed-list calls."""
    names = set()
    for a in aliases:
        if a.name == "*":
            names |= set(FILE_METHODS)
            names |= {
                q.rpartition(".")[2]
                for q in FILE_QUALIFIED
                if q.startswith(module + ".")
            }
        elif (
            a.name in FILE_NAMES + FILE_METHODS
            or f"{module}.{a.name}" in FILE_QUALIFIED
        ):
            names.add(a.asname or a.name)
    return names


def _is_file_call(call: ast.Call, bindings: _Bindings) -> bool:
    func = call.func
    if isinstance(func, ast.Name):
        return func.id in bindings.names
    if not isinstance(func, ast.Attribute):
        return False
    if isinstance(func.value, ast.Name):
        module = bindings.modules.get(func.value.id, func.value.id)
        if f"{module}.{func.attr}" in FILE_QUALIFIED:
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
    bindings: _Bindings,
) -> bool:
    """True when the body, or a module helper it calls, does file work."""
    arguments = function.args.posonlyargs + function.args.args
    arguments += function.args.kwonlyargs
    if any(item.arg in FILE_FIXTURES for item in arguments):
        return True
    for node in ast.walk(function):
        if not isinstance(node, ast.Call):
            continue
        if _is_file_call(node, bindings):
            return True
        name = _callee(node)
        if name in helpers and name not in seen:
            seen.add(name)
            if _does_file_work(helpers[name], helpers, seen, bindings):
                return True
    return False


def _hypothesis_names(tree: ast.Module, name: str) -> set[str]:
    """`name` and every alias of it imported from hypothesis."""
    names = {name}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "hypothesis":
            names |= {a.asname for a in node.names if a.name == name and a.asname}
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
    names = _hypothesis_names(tree, "settings")
    givens = _hypothesis_names(tree, "given")
    bindings = _bindings(tree)
    return [
        f"{function.name}:{function.lineno}"
        for function in functions
        if any(_decorator_name(item) in givens for item in function.decorator_list)
        and _does_file_work(function, helpers, {function.name}, bindings)
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
_BODY = "    with tempfile.TemporaryDirectory() as folder:\n"
# S2-P80.rv1: one plant per call form the first guard missed; each value is
# (imports placed above the plant, the plant's first body line).
_ROUTES_R2 = {
    "TemporaryFile": ("", "    tempfile.TemporaryFile()\n"),
    "SpooledTemporaryFile": ("", "    tempfile.SpooledTemporaryFile()\n"),
    "path.open": ("", "    path.open('w')\n"),
    "io.open": ("", "    io.open('x')\n"),
    "os.open": ("", "    os.open('x', 0)\n"),
    "codecs.open": ("", "    codecs.open('x')\n"),
    "pathlib.Path": ("", "    pathlib.Path('x')\n"),
    "os.walk": ("", "    os.walk('x')\n"),
    "os.rmdir": ("", "    os.rmdir('x')\n"),
    "os.symlink": ("", "    os.symlink('x', 'y')\n"),
    "os.link": ("", "    os.link('x', 'y')\n"),
    "os.chmod": ("", "    os.chmod('x', 0)\n"),
    "os.fdopen": ("", "    os.fdopen(3)\n"),
    "os.truncate": ("", "    os.truncate('x', 0)\n"),
    "shutil.copy2": ("", "    shutil.copy2('x', 'y')\n"),
    "shutil.copyfileobj": ("", "    shutil.copyfileobj(a, b)\n"),
    "shutil.copymode": ("", "    shutil.copymode('x', 'y')\n"),
    "shutil.make_archive": ("", "    shutil.make_archive('x', 'zip')\n"),
    "shutil.chown": ("", "    shutil.chown('x')\n"),
    "subprocess.call": ("", "    subprocess.call(['x'])\n"),
    "subprocess.getoutput": ("", "    subprocess.getoutput('x')\n"),
    "subprocess.getstatusoutput": ("", "    subprocess.getstatusoutput('x')\n"),
    "os.system": ("", "    os.system('x')\n"),
    "os.popen": ("", "    os.popen('x')\n"),
    "path.glob": ("", "    path.glob('*')\n"),
    "glob.iglob": ("", "    glob.iglob('*')\n"),
    "zipfile.ZipFile": ("", "    zipfile.ZipFile('x')\n"),
    "tarfile.open": ("", "    tarfile.open('x')\n"),
    "gzip.open": ("", "    gzip.open('x')\n"),
    "bz2.open": ("", "    bz2.open('x')\n"),
    "lzma.open": ("", "    lzma.open('x')\n"),
    "shelve.open": ("", "    shelve.open('x')\n"),
    "dbm.open": ("", "    dbm.open('x')\n"),
    "alias Path": ("from pathlib import Path as P\n", "    P('x')\n"),
    "alias TemporaryDirectory": (
        "from tempfile import TemporaryDirectory as td\n",
        "    td()\n",
    ),
    "alias TemporaryFile": ("from tempfile import TemporaryFile as tf\n", "    tf()\n"),
    "alias open": ("from io import open as io_open\n", "    io_open('x')\n"),
    "from-import walk": ("from os import walk\n", "    walk('x')\n"),
    "alias copy2": ("from shutil import copy2 as cp\n", "    cp('x', 'y')\n"),
    "from-import call": ("from subprocess import call\n", "    call(['x'])\n"),
    "module alias": ("import os as o\n", "    o.walk('x')\n"),
    "module alias two": ("import subprocess as sp\n", "    sp.call(['x'])\n"),
}
# One route per new list member, so deleting the member alone turns a plant
# red: a bare call (FILE_NAMES), a call on a non-module receiver (FILE_METHODS)
# and a `from M import N as bound` call (FILE_QUALIFIED, N outside FILE_NAMES).
_BARE_R2 = ("TemporaryFile", "SpooledTemporaryFile")
_METHOD_R2 = (
    "TemporaryFile",
    "SpooledTemporaryFile",
    "open",
    "fdopen",
    "rmdir",
    "truncate",
    "glob",
    "iglob",
    "symlink",
    "chmod",
    "chown",
    "copyfileobj",
    "copymode",
    "copy2",
    "make_archive",
    "ZipFile",
    "popen",
    "getoutput",
    "getstatusoutput",
)
_FROM_R2 = (
    "subprocess.getoutput",
    "subprocess.getstatusoutput",
    "os.fdopen",
    "os.rmdir",
    "os.symlink",
    "os.chmod",
    "os.truncate",
    "os.popen",
    "shutil.copyfileobj",
    "shutil.copymode",
    "shutil.make_archive",
    "shutil.chown",
    "glob.iglob",
    "zipfile.ZipFile",
)
_ROUTES_R2 |= {f"bare {name}": ("", f"    {name}()\n") for name in _BARE_R2}
_ROUTES_R2 |= {f"handle.{name}": ("", f"    handle.{name}()\n") for name in _METHOD_R2}
_ROUTES_R2 |= {
    f"from {pair}": (
        "from {} import {} as bound\n".format(*pair.split(".")),
        "    bound()\n",
    )
    for pair in _FROM_R2
}
# S2-P80.cf1 F3: every closed-list name under each from-import form, bare,
# aliased and star; an unqualified name is shown on an invented module.
_FROM_FAMILY = {
    *(("anymodule", name) for name in FILE_NAMES + FILE_METHODS),
    *(tuple(pair.split(".")) for pair in FILE_QUALIFIED),
}
_ROUTES_R3 = {
    f"{form} {module}.{name}": (f"from {module} import {bound}\n", f"    {call}()\n")
    for module, name in sorted(_FROM_FAMILY)
    for form, bound, call in (
        ("bare", name, name),
        ("as", f"{name} as bound", "bound"),
        ("star", "*", name),
    )
}
_ROUTES_R3["helper copytree"] = (
    "from shutil import copytree\n",
    "    released()\n    if False:\n        pass\n"
    "def released():\n    copytree('x', 'y')\n",
)
# Same-named calls that are not file work stay outside the guard.
_NOT_FILE_WORK = {
    "ast.walk": "    ast.walk(text)\n",
    "mock.call": "    mock.call(text)\n",
    "platform.system": "    platform.system()\n",
}
_NOT_FILE_WORK_R3 = {
    "from ast import walk": ("from ast import walk\n", "    walk(text)\n"),
    "from ast import *": ("from ast import *\n", "    walk(text)\n"),
    "from unittest.mock import call": (
        "from unittest.mock import call\n",
        "    call(text)\n",
    ),
    "from platform import *": ("from platform import *\n", "    system()\n"),
}


def _route(imports: str, line: str) -> str:
    """The plant with `imports` above it and `line` opening its body."""
    return imports + _PLANT.format(decorator="").replace(
        _BODY, line + "    if False:\n"
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
        body = _BODY
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

    def test_deadline_guard_routes_round_two(self) -> None:
        self._assert_routes(_ROUTES_R2)
        for name, line in _NOT_FILE_WORK.items():
            with self.subTest(pure=name):
                self.assertEqual(deadline_violations(_route("", line)), [])

    def test_deadline_guard_from_import_family(self) -> None:
        self._assert_routes(_ROUTES_R3)
        for name, (imports, line) in _NOT_FILE_WORK_R3.items():
            with self.subTest(pure=name):
                self.assertEqual(deadline_violations(_route(imports, line)), [])

    def _assert_routes(self, routes: dict[str, tuple[str, str]]) -> None:
        for name, (imports, line) in routes.items():
            with self.subTest(route=name):
                expected = f"test_plant:{6 + imports.count(chr(10))}"
                self.assertEqual(deadline_violations(_route(imports, line)), [expected])

    def test_deadline_guard_given_alias(self) -> None:
        alias = _PLANT.replace("given, settings", "given as g, settings")
        alias = alias.replace("@given(", "@g(")
        self.assertEqual(
            deadline_violations(alias.format(decorator="")), ["test_plant:6"]
        )
        kept = alias.format(decorator="@settings(deadline=None)\n")
        self.assertEqual(deadline_violations(kept), [])
        dotted = _PLANT.replace("@given(", "@hypothesis.given(")
        dotted = "import hypothesis\n" + dotted.format(decorator="")
        self.assertEqual(deadline_violations(dotted), ["test_plant:7"])
        other = _PLANT.replace("given, settings", "settings")
        other = other.replace("@given(", "@g(").format(decorator="")
        self.assertEqual(deadline_violations(other), [])

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
