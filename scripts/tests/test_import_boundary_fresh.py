#!/usr/bin/env python3
"""Fresh-interpreter import-boundary tests."""

from __future__ import annotations

import tempfile
import unittest
from collections.abc import Callable
from pathlib import Path

import import_boundary_cases as cases
import import_boundary_child as child
import import_boundary_guard as guard


def _plant_missing_module(root: Path) -> None:
    cases.write_planted(root, "eii_product", "import nonexistent_module_zz\n")


def _break_product_init(root: Path) -> None:
    init = cases.package_dir(root, "eii_product") / "__init__.py"
    init.write_text('raise RuntimeError("x")\n', encoding="utf-8")


def _break_product_subpackage(root: Path) -> None:
    broken = cases.package_dir(root, "eii_product") / "broken"
    broken.mkdir()
    (broken / "__init__.py").write_text('raise RuntimeError("x")\n', encoding="utf-8")


_FRESH_FORMS: tuple[tuple[str, Callable[[str], str]], ...] = (
    ("import_stmt", lambda target: f"import {target}\n"),
    ("from_version", lambda target: f"from {target} import __version__\n"),
    (
        "import_module",
        lambda target: f"import importlib\nimportlib.import_module({target!r})\n",
    ),
    ("dunder_import", lambda target: f"__import__({target!r})\n"),
    (
        "concat",
        lambda target: (
            "import importlib\n"
            f'importlib.import_module("eii_" + "{target.removeprefix("eii_")}")\n'
        ),
    ),
)


class ImportBoundaryFreshTest(unittest.TestCase):
    """Import-time behaviour of the fresh-interpreter guard."""

    def test_fresh_every_edge_import_time(self) -> None:
        """Each forbidden edge fails under every import-time form."""
        count = 0
        needs_gateway = {"eii_gateway"}
        for source_pkg, forbidden in cases.EDGES:
            for form_name, build in _FRESH_FORMS:
                with self.subTest(
                    source=source_pkg, forbidden=forbidden, form=form_name
                ):
                    with tempfile.TemporaryDirectory() as folder:
                        root = Path(folder)
                        cases.make_tree(root, gateway=True)
                        cases.write_planted(root, source_pkg, build(forbidden))
                        paths = (
                            [cases.gateway_src(root)]
                            if forbidden in needs_gateway
                            else []
                        )
                        result = child.run_fresh(
                            root,
                            source_pkg,
                            extra_paths=paths,
                        )
                        expected = cases.expected_fresh_loaded(source_pkg, forbidden)
                        self.assertEqual(result, [expected])
                        if form_name == "concat":
                            failures, notes = guard.check_imports(root)
                            rel = cases.planted_rel_path(source_pkg)
                            self.assertEqual(failures, [])
                            self.assertEqual(
                                len(notes),
                                1,
                            )
                            self.assertTrue(
                                notes[0].startswith(f"NOTE dynamic-import: {rel}:")
                            )
                count += 1
        self.assertEqual(count, 35)

    def test_fresh_function_local_is_static_only(self) -> None:
        """Function-local imports are static-only; the child does not see them."""
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            cases.make_tree(root)
            cases.write_planted(
                root,
                "eii_product",
                "def f():\n    import eii_custodian\n",
            )
            self.assertEqual(child.run_fresh(root, "eii_product"), [])
            failures, notes = guard.check_imports(root)
            expected = cases.expected_forbidden_line(
                cases.planted_rel_path("eii_product"),
                2,
                "import",
                "eii_custodian",
                "eii_product",
                "eii_custodian",
            )
            self.assertEqual((failures, notes), ([expected], []))

    def test_fresh_swallowed_attempt(self) -> None:
        """Swallowed import attempts are still reported by the child."""
        count = 0
        plants: tuple[tuple[str, str, str], ...] = (
            (
                "gateway",
                "try:\n    import eii_gateway\nexcept ImportError:\n    pass\n",
                cases.expected_fresh_attempted("eii_product", "eii_gateway"),
            ),
            (
                "core_control",
                "try:\n    import eii_core\nexcept ImportError:\n    pass\n",
                "",
            ),
        )
        for label, source, expected_line in plants:
            with self.subTest(case=label):
                with tempfile.TemporaryDirectory() as folder:
                    root = Path(folder)
                    cases.make_tree(root)
                    cases.write_planted(root, "eii_product", source)
                    result = child.run_fresh(root, "eii_product")
                    if expected_line:
                        self.assertEqual(result, [expected_line])
                    else:
                        self.assertEqual(result, [])
            count += 1
        self.assertEqual(count, 2)

    def test_fresh_requested_while_other_forbidden_loaded(self) -> None:
        """A requested-but-unloaded forbidden name is reported when another loads."""
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            cases.make_tree(root, gateway=True)
            blocked = cases.package_dir(root, "eii_custodian") / "__init__.py"
            blocked.write_text('raise ImportError("blocked")\n', encoding="utf-8")
            cases.write_planted(
                root,
                "eii_product",
                "import eii_gateway\n"
                "try:\n"
                "    import eii_custodian\n"
                "except ImportError:\n"
                "    pass\n",
            )
            result = child.run_fresh(
                root,
                "eii_product",
                extra_paths=[cases.gateway_src(root)],
            )
            self.assertEqual(
                sorted(result),
                sorted(
                    [
                        cases.expected_fresh_attempted("eii_product", "eii_custodian"),
                        cases.expected_fresh_loaded("eii_product", "eii_gateway"),
                    ]
                ),
            )

    def test_fresh_import_errors(self) -> None:
        """Import failures in the child are reported with the exception name."""
        count = 0
        scenarios: tuple[tuple[str, Callable[[Path], None], str], ...] = (
            (
                "missing_module",
                _plant_missing_module,
                cases.expected_fresh_import_error(
                    "eii_product", "eii_product.planted", "ModuleNotFoundError"
                ),
            ),
            (
                "broken_init",
                _break_product_init,
                cases.expected_fresh_import_error(
                    "eii_product", "eii_product", "RuntimeError"
                ),
            ),
            (
                "broken_subpackage",
                _break_product_subpackage,
                cases.expected_fresh_import_error(
                    "eii_product", "eii_product.broken", "RuntimeError"
                ),
            ),
        )
        for label, plant, expected in scenarios:
            with self.subTest(case=label):
                with tempfile.TemporaryDirectory() as folder:
                    root = Path(folder)
                    cases.make_tree(root)
                    plant(root)
                    self.assertEqual(child.run_fresh(root, "eii_product"), [expected])
            count += 1
        self.assertEqual(count, 3)

    def test_fresh_outside_source_tree(self) -> None:
        """Namespace folders and unread static violations interact correctly."""
        count = 0
        with self.subTest(case="namespace_importable"):
            with tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                cases.make_tree(root)
                ns = cases.package_dir(root, "eii_product") / "ns"
                ns.mkdir(parents=True, exist_ok=True)
                (ns / "lone.py").write_text("VALUE = 1\n", encoding="utf-8")
                cases.write_planted(
                    root,
                    "eii_product",
                    "from .ns import lone\n",
                )
                self.assertEqual(child.run_fresh(root, "eii_product"), [])
                self.assertEqual(guard.check_imports(root), ([], []))
            count += 1

        with self.subTest(case="static_only_violation"):
            with tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                cases.make_tree(root)
                ns = cases.package_dir(root, "eii_product") / "ns"
                ns.mkdir(parents=True, exist_ok=True)
                (ns / "lone.py").write_text(
                    "import eii_custodian\n",
                    encoding="utf-8",
                )
                self.assertEqual(child.run_fresh(root, "eii_product"), [])
                expected = cases.expected_forbidden_line(
                    "product/src/eii_product/ns/lone.py",
                    1,
                    "import",
                    "eii_custodian",
                    "eii_product",
                    "eii_custodian",
                )
                self.assertEqual(guard.check_imports(root), ([expected], []))
            count += 1

        self.assertEqual(count, 2)


if __name__ == "__main__":
    unittest.main()
