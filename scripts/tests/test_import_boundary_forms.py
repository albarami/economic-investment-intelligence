#!/usr/bin/env python3
"""Tests for judged and not-judged import forms (pack BE-04, ARC-06).

Run from the repository root:

    python3 -m unittest discover -s scripts/tests -p 'test_*.py' -v

Every case builds a throw-away fixture in ``tempfile.TemporaryDirectory()``,
plants violations under the three synthetic package trees, and asserts on the
full failure and note lists from the static guard or the fresh-interpreter
child. Only the Python standard library is used.
"""

from __future__ import annotations

import ast
import importlib.util
import py_compile
import tempfile
import unittest
from pathlib import Path

import import_boundary_cases as cases
import import_boundary_child as child
import import_boundary_guard as guard
import import_boundary_judge as judge

_PLACEMENTS: tuple[str, ...] = (
    "function",
    "async_function",
    "method",
    "class_body",
    "nested_function",
    "if_block",
    "try_body",
    "except_handler",
)

_T03_MECHANISMS: tuple[cases.Mechanism, ...] = (
    next(m for m in cases.MECHANISMS if m.id == "S1"),
    next(m for m in cases.MECHANISMS if m.id == "D1"),
)

_CHILD_MODULE_LABELS: frozenset[str] = frozenset({"N3", "N7", "N12", "N18"})


def _embed_in_placement(placement: str, body_lines: list[str]) -> list[str]:
    """Wrap ``body_lines`` in the named syntactic placement."""
    if placement == "function":
        return ["def f():", *[f"    {line}" for line in body_lines]]
    if placement == "async_function":
        return ["async def f():", *[f"    {line}" for line in body_lines]]
    if placement == "method":
        return [
            "class C:",
            "    def m(self):",
            *[f"        {line}" for line in body_lines],
        ]
    if placement == "class_body":
        return ["class C:", *[f"    {line}" for line in body_lines]]
    if placement == "nested_function":
        return [
            "def f():",
            "    def g():",
            *[f"        {line}" for line in body_lines],
        ]
    if placement == "if_block":
        return ["def f():", "    if True:", *[f"        {line}" for line in body_lines]]
    if placement == "try_body":
        return [
            "def f():",
            "    try:",
            *[f"        {line}" for line in body_lines],
            "    except Exception:",
            "        pass",
        ]
    if placement == "except_handler":
        return [
            "def f():",
            "    try:",
            "        pass",
            "    except Exception:",
            *[f"        {line}" for line in body_lines],
        ]
    msg = f"unknown placement {placement!r}"
    raise ValueError(msg)


def _mechanism_hit_line(source: str, mech: cases.Mechanism, forbidden: str) -> int:
    """Return the one-based line number of the mechanism's finding."""
    needle = mech.lines[mech.line - 1].replace("T", forbidden)
    for index, line in enumerate(source.splitlines(), start=1):
        if line.strip() == needle.strip():
            return index
    msg = f"mechanism line not found in source: {needle!r}"
    raise AssertionError(msg)


def _planted_source_in_placement(
    placement: str, mech: cases.Mechanism, forbidden: str
) -> tuple[str, int]:
    """Build placed source and the line number where the guard should report."""
    body = [line.replace("T", forbidden) for line in mech.lines]
    lines = _embed_in_placement(placement, body)
    source = "\n".join(lines) + "\n"
    return source, _mechanism_hit_line(source, mech, forbidden)


def _plant_child_case(root: Path, label: str) -> None:
    """Plant one ``CHILD_CASES`` row for ``test_not_judged_forms_in_the_child``."""
    cases.write_custodian_other(root)
    other_path = cases.planted_path(root, "eii_custodian", "other.py")
    cust_src = root / "custodian" / "src"

    if label in _CHILD_MODULE_LABELS:
        for row in cases.NOT_JUDGED:
            if row[0] == label:
                cases.write_planted(root, "eii_product", row[2])
                return
        msg = f"missing NOT_JUDGED row for {label!r}"
        raise KeyError(msg)

    if label == "N8":
        source = (
            "import importlib.util\n"
            f'spec = importlib.util.spec_from_file_location("zz", {str(other_path)!r})\n'
            "mod = importlib.util.module_from_spec(spec)\n"
            "spec.loader.exec_module(mod)\n"
        )
        cases.write_planted(root, "eii_product", source)
        return

    if label == "N9":
        source = f"import runpy\nrunpy.run_path({str(other_path)!r})\n"
        cases.write_planted(root, "eii_product", source)
        return

    if label == "N10":
        cases.write_planted(root, "eii_product", "import ctypes\nctypes.CDLL(None)\n")
        return

    if label == "N11":
        source = (
            "import subprocess\n"
            "import sys\n"
            "subprocess.run(\n"
            "    [\n"
            "        sys.executable,\n"
            '        "-I",\n'
            '        "-S",\n'
            '        "-c",\n'
            '        "import sys; sys.path.insert(0, sys.argv[1]); import eii_custodian",\n'
            f"        {str(cust_src)!r},\n"
            "    ],\n"
            "    check=True,\n"
            ")\n"
        )
        cases.write_planted(root, "eii_product", source)
        return

    product_dir = cases.package_dir(root, "eii_product")
    src_holder = product_dir / "_sneak_src.py"
    src_holder.write_text("import eii_custodian\n", encoding="utf-8")

    if label == "sneak.pyc":
        target = product_dir / "sneak.pyc"
        py_compile.compile(str(src_holder), cfile=str(target), doraise=True)
        src_holder.unlink()
        return

    if label == "ns/sneak.pyc":
        ns_dir = product_dir / "ns"
        ns_dir.mkdir(parents=True, exist_ok=True)
        target = ns_dir / "sneak.pyc"
        py_compile.compile(str(src_holder), cfile=str(target), doraise=True)
        src_holder.unlink()
        return

    msg = f"unknown child case label {label!r}"
    raise ValueError(msg)


class ImportBoundaryFormsTest(unittest.TestCase):
    """Judged and not-judged import forms for the static and fresh guards."""

    def test_every_edge_every_mechanism(self) -> None:
        """Forbidden import mechanisms fail on every documented plane edge."""
        count = 0
        for source_pkg, forbidden in cases.EDGES:
            for mech in cases.MECHANISMS:
                with self.subTest(source=source_pkg, forbidden=forbidden, mech=mech.id):
                    with tempfile.TemporaryDirectory() as folder:
                        root = Path(folder)
                        cases.make_tree(root)
                        cases.write_planted(
                            root,
                            source_pkg,
                            cases.mechanism_source(mech, forbidden),
                        )
                        failures, notes = guard.check_imports(root)
                        expected = cases.expected_mechanism_failure(
                            source_pkg, forbidden, mech
                        )
                        self.assertEqual((failures, notes), ([expected], []))
                count += 1
        self.assertEqual(count, 210)

    def test_allowed_edges_every_mechanism(self) -> None:
        """Allowed targets never produce a forbidden-import failure."""
        count = 0
        for source_pkg, target in cases.ALLOWED:
            for mech in cases.MECHANISMS:
                with self.subTest(source=source_pkg, target=target, mech=mech.id):
                    with tempfile.TemporaryDirectory() as folder:
                        root = Path(folder)
                        cases.make_tree(root)
                        cases.write_planted(
                            root,
                            source_pkg,
                            cases.mechanism_source(mech, target),
                        )
                        self.assertEqual(guard.check_imports(root), ([], []))
                count += 1
        self.assertEqual(count, 150)

    def test_local_placements(self) -> None:
        """Forbidden imports inside nested scopes are still judged."""
        count = 0
        forbidden = "eii_custodian"
        package = "eii_product"
        for placement in _PLACEMENTS:
            for mech in _T03_MECHANISMS:
                with self.subTest(placement=placement, mech=mech.id):
                    with tempfile.TemporaryDirectory() as folder:
                        root = Path(folder)
                        cases.make_tree(root)
                        source, hit_line = _planted_source_in_placement(
                            placement, mech, forbidden
                        )
                        cases.write_planted(root, package, source)
                        failures, notes = guard.check_imports(root)
                        rel_path = cases.planted_rel_path(package)
                        target = cases.substitute_target(mech.target, forbidden)
                        expected = cases.expected_forbidden_line(
                            rel_path,
                            hit_line,
                            mech.form,
                            target,
                            package,
                            forbidden,
                        )
                        self.assertEqual((failures, notes), ([expected], []))
                count += 1
        self.assertEqual(count, 16)

    def test_lookalikes_pass(self) -> None:
        """Misspelled or inert spellings of a forbidden name do not fail."""
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            cases.make_tree(root)
            planted = cases.planted_path(root, "eii_product", "planted.py")
            planted.write_text(
                "\n".join(
                    (
                        "import importlib",
                        "import eii_custodianx",
                        "import xeii_custodian",
                        "from eii_custodian_extra import y",
                        "import a.eii_custodian",
                        'x = "eii_custodian"',
                        "# import eii_custodian",
                        '"""import eii_custodian"""',
                        "from eii_core import eii_custodian",
                        'importlib.import_module("eii_custodianx")',
                        'obj.import_module("eii_custodian")',
                        'other.__import__("eii_custodian")',
                        'b.__import__("eii_custodian")',
                    )
                )
                + "\n",
                encoding="utf-8",
            )
            sub = cases.planted_path(root, "eii_product", "sub/planted.py")
            sub.parent.mkdir(parents=True, exist_ok=True)
            sub.write_text("from . import eii_custodian\n", encoding="utf-8")
            self.assertEqual(guard.check_imports(root), ([], []))

    def test_fullwidth_spelling_is_judged(self) -> None:
        """Parser-normalised identifiers are judged as their ASCII spelling."""
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            cases.make_tree(root)
            cases.write_planted(root, "eii_product", "import \uff45ii_custodian\n")
            failures, notes = guard.check_imports(root)
            mech = cases.MECHANISMS[0]
            expected = cases.expected_mechanism_failure(
                "eii_product", "eii_custodian", mech
            )
            self.assertEqual((failures, notes), ([expected], []))

    def test_non_literal_dynamic_is_a_note(self) -> None:
        """Non-literal dynamic import calls are notes, not failures."""
        count = 0
        for call_lines in cases.NOTE_CASES:
            with self.subTest(call=call_lines[0][:40]):
                with tempfile.TemporaryDirectory() as folder:
                    root = Path(folder)
                    cases.make_tree(root)
                    cases.write_planted(
                        root,
                        "eii_product",
                        cases.note_case_source(call_lines),
                    )
                    failures, notes = guard.check_imports(root)
                    expected_note = cases.expected_note_for_case(call_lines)
                    self.assertEqual((failures, notes), ([], [expected_note]))
                count += 1
        self.assertEqual(count, 21)

    def test_relative_imports(self) -> None:
        """Relative imports stay inside the package or fail as an escape."""
        count = 0
        passes: tuple[tuple[str, str], ...] = (
            ("planted.py", "from . import x\n"),
            ("planted.py", "from .sub import mod\n"),
            ("sub/planted.py", "from .. import __version__\n"),
        )
        for rel_name, content in passes:
            with self.subTest(rel=rel_name, expect="pass"):
                with tempfile.TemporaryDirectory() as folder:
                    root = Path(folder)
                    cases.make_tree(root)
                    cases.write_planted(root, "eii_product", content, rel_name)
                    self.assertEqual(guard.check_imports(root), ([], []))
                count += 1

        fails: tuple[tuple[str, str], ...] = (
            ("planted.py", "from .. import x\n"),
            ("sub/planted.py", "from ... import x\n"),
        )
        for rel_name, content in fails:
            with self.subTest(rel=rel_name, expect="fail"):
                with tempfile.TemporaryDirectory() as folder:
                    root = Path(folder)
                    cases.make_tree(root)
                    cases.write_planted(root, "eii_product", content, rel_name)
                    failures, notes = guard.check_imports(root)
                    rel_path = cases.planted_rel_path("eii_product", rel_name)
                    expected = cases.expected_relative_escape_line(rel_path, 1)
                    self.assertEqual((failures, notes), ([expected], []))
                count += 1

        with self.subTest(rel="__init__.py", expect="fail"):
            with tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                cases.make_tree(root)
                init = cases.package_dir(root, "eii_product") / "__init__.py"
                init.write_text("from .. import x\n", encoding="utf-8")
                failures, notes = guard.check_imports(root)
                rel_path = cases.planted_rel_path("eii_product", "__init__.py")
                expected = cases.expected_relative_escape_line(rel_path, 1)
                self.assertEqual((failures, notes), ([expected], []))
            count += 1
        self.assertEqual(count, 6)

    def test_relative_escape_matches_resolve_name(self) -> None:
        """Relative-escape hits match ``importlib.util.resolve_name`` per file depth."""
        package = "eii_product"
        forbidden: tuple[str, ...] = guard.FORBIDDEN[package]
        shapes: tuple[tuple[str, str, tuple[str, ...]], ...] = (
            ("mod_root", package, (package,)),
            ("init_root", package, (package,)),
            ("mod_one", f"{package}.sub", (package, "sub")),
            ("init_one", f"{package}.sub", (package, "sub")),
            ("mod_two", f"{package}.a.b", (package, "a", "b")),
            ("init_two", f"{package}.a.b", (package, "a", "b")),
        )
        count = 0
        for label, mod_package, parts in shapes:
            for level in range(1, 5):
                with self.subTest(shape=label, level=level):
                    dots = "." * level
                    source = f"from {dots} import x\n"
                    tree = ast.parse(source)
                    hits = judge.judge_tree(tree, package, parts, forbidden)
                    judge_escape = any(h.kind == "relative-escape" for h in hits)
                    rel_name = dots + "x"
                    try:
                        importlib.util.resolve_name(rel_name, mod_package)
                        resolve_refuses = False
                    except ImportError:
                        resolve_refuses = True
                    self.assertEqual(judge_escape, resolve_refuses)
                count += 1
        self.assertEqual(count, 24)

    def test_declared_not_judged_forms_pass(self) -> None:
        """Forms documented as not judged produce no static failure."""
        count = 0
        for row in cases.NOT_JUDGED:
            label = row[0]
            with self.subTest(label=label):
                with tempfile.TemporaryDirectory() as folder:
                    root = Path(folder)
                    cases.make_tree(root)
                    cases.write_not_judged(root, row)
                    self.assertEqual(guard.check_imports(root), ([], []))
                count += 1
        self.assertEqual(count, 30)

    def test_not_judged_forms_in_the_child(self) -> None:
        """Fresh interpreter visibility for selected not-judged forms."""
        count = 0
        for label, _description, expected in cases.CHILD_CASES:
            with self.subTest(label=label):
                with tempfile.TemporaryDirectory() as folder:
                    root = Path(folder)
                    cases.make_tree(root)
                    _plant_child_case(root, label)
                    result = child.run_fresh(root, "eii_product")
                    self.assertEqual(result, expected)
                count += 1
        self.assertEqual(count, 10)


if __name__ == "__main__":
    unittest.main()
