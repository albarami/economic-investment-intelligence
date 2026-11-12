#!/usr/bin/env python3
"""Tree, symlink, bytecode and environment-name rules for the static guard."""

from __future__ import annotations

import ast
import errno
import os
import shutil
import tempfile
import unittest
from collections.abc import Callable, Iterator
from pathlib import Path
from unittest import mock

import import_boundary_cases as cases
import import_boundary_guard as guard

_PRODUCT_PLANTED = "product/src/eii_product/planted.py"
_TREES: tuple[tuple[str, str], ...] = (
    ("eii_core", "core/src/eii_core"),
    ("eii_custodian", "custodian/src/eii_custodian"),
    ("eii_product", "product/src/eii_product"),
)


def _replace_core_with_file(root: Path) -> None:
    shutil.rmtree(root / "core/src/eii_core")
    (root / "core/src/eii_core").write_bytes(b"x")


def _empty_core_python_files(root: Path) -> None:
    tree = root / "core/src/eii_core"
    for path in tree.rglob("*.py"):
        path.unlink()
    (tree / "data.txt").write_text("x\n", encoding="utf-8")


def _plant_env_notes_line2(root: Path) -> None:
    (cases.package_dir(root, "eii_product") / "notes.txt").write_text(
        "blank\nEII_DECISION_PROVIDER\n",
        encoding="utf-8",
    )


def _plant_env_blob(root: Path) -> None:
    (cases.package_dir(root, "eii_product") / "blob.bin").write_bytes(
        b"\x00\xffJEV_PRO_API_KEY\n"
    )


def _plant_env_dual_names(root: Path) -> None:
    (cases.package_dir(root, "eii_product") / "dual.py").write_text(
        "x = 1\nEII_DECISION_PROVIDER\ny = 2\nJEV_PRO_API_KEY\n",
        encoding="utf-8",
    )


def _plant_env_name_in_bytecode_cache(root: Path) -> None:
    cache = cases.package_dir(root, "eii_product") / "__pycache__"
    cache.mkdir(exist_ok=True)
    (cache / "m.cpython-314.pyc").write_bytes(b"EII_DECISION_PROVIDER")


def _plant_env_name_in_pycache_py(root: Path) -> None:
    cache = cases.package_dir(root, "eii_product") / "__pycache__"
    cache.mkdir(exist_ok=True)
    (cache / "m.py").write_text("EII_DECISION_PROVIDER\n", encoding="utf-8")


def _plant_env_name_in_deep_pyc(root: Path) -> None:
    deep = cases.package_dir(root, "eii_product") / "__pycache__" / "deep"
    deep.mkdir(parents=True, exist_ok=True)
    (deep / "m.cpython-314.pyc").write_bytes(b"JEV_PRO_API_KEY")


def _plant_env_providers_suffix(root: Path) -> None:
    cases.write_planted(root, "eii_product", "EII_DECISION_PROVIDERS\n")


def _plant_env_case_variants_pass(root: Path) -> None:
    cases.write_planted(
        root,
        "eii_product",
        "eii_decision_provider\nJev_Pro_Api_Key\n",
    )


def _plant_env_name_in_package_pyc(root: Path) -> None:
    (cases.package_dir(root, "eii_product") / "m.pyc").write_bytes(b"JEV_PRO_API_KEY")


class ImportBoundaryFilesTest(unittest.TestCase):
    """File-tree and byte-level rules for ``check_imports``."""

    def test_missing_source_tree(self) -> None:
        """Missing or empty package trees fail the src-tree rule."""
        count = 0
        scenarios: tuple[tuple[str, Callable[[Path], None], str], ...] = (
            (
                "remove_core",
                lambda root: shutil.rmtree(root / "core/src/eii_core"),
                cases.expected_src_tree_missing("core/src/eii_core"),
            ),
            (
                "remove_custodian",
                lambda root: shutil.rmtree(root / "custodian/src/eii_custodian"),
                cases.expected_src_tree_missing("custodian/src/eii_custodian"),
            ),
            (
                "remove_product",
                lambda root: shutil.rmtree(root / "product/src/eii_product"),
                cases.expected_src_tree_missing("product/src/eii_product"),
            ),
            (
                "core_is_file",
                _replace_core_with_file,
                cases.expected_src_tree_missing("core/src/eii_core"),
            ),
            (
                "core_no_py",
                _empty_core_python_files,
                cases.expected_src_tree_no_python("core/src/eii_core"),
            ),
        )
        for label, mutate, expected in scenarios:
            with self.subTest(case=label):
                with tempfile.TemporaryDirectory() as folder:
                    root = Path(folder)
                    cases.make_tree(root)
                    mutate(root)
                    failures, notes = guard.check_imports(root)
                    self.assertEqual((failures, notes), ([expected], []))
            count += 1
        self.assertEqual(count, 5)

    def test_unparsable_and_unreadable(self) -> None:
        """Unreadable or unparsable sources produce exactly one unparsable line."""
        count = 0
        planted_rel = _PRODUCT_PLANTED
        real_parse = ast.parse

        def make_parse_raiser(exc: type[BaseException]) -> Callable[..., ast.AST]:
            def fake(
                source: bytes | str,
                filename: str = "<unknown>",
                mode: str = "exec",
                *,
                type_comments: bool = False,
                feature_version: int | tuple[int, int] | None = None,
            ) -> ast.AST:
                if filename == planted_rel:
                    raise exc("planted")
                return real_parse(
                    source,
                    filename,
                    mode,
                    type_comments=type_comments,
                    feature_version=feature_version,
                )

            return fake

        byte_cases: tuple[tuple[str, bytes | str, str], ...] = (
            ("syntax_def", "def (:\n", "SyntaxError"),
            ("bad_cookie", b"x = 1\n# \xff\xfe", "SyntaxError"),
            ("nul_byte", b"\x00", "SyntaxError"),
            ("encoding_nope", "# -*- coding: nope -*-\n", "SyntaxError"),
            ("indent_error", "if 1:\nx\n", "IndentationError"),
        )
        for label, body, exc_name in byte_cases:
            with self.subTest(case=label):
                with tempfile.TemporaryDirectory() as folder:
                    root = Path(folder)
                    cases.make_tree(root)
                    cases.write_planted(root, "eii_product", body)
                    failures, notes = guard.check_imports(root)
                    expected = cases.expected_unparsable_parse(planted_rel, exc_name)
                    self.assertEqual((failures, notes), ([expected], []))
            count += 1

        for exc_name in ("ValueError", "RecursionError", "MemoryError"):
            exc_type = {
                "ValueError": ValueError,
                "RecursionError": RecursionError,
                "MemoryError": MemoryError,
            }[exc_name]
            with self.subTest(case=f"parse_{exc_name}"):
                with tempfile.TemporaryDirectory() as folder:
                    root = Path(folder)
                    cases.make_tree(root)
                    cases.write_planted(root, "eii_product", "x = 1\n")
                    with mock.patch.object(
                        ast, "parse", side_effect=make_parse_raiser(exc_type)
                    ):
                        failures, notes = guard.check_imports(root)
                    expected = cases.expected_unparsable_parse(planted_rel, exc_name)
                    self.assertEqual((failures, notes), ([expected], []))
            count += 1

        with self.subTest(case="read_EACCES"):
            with tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                cases.make_tree(root)
                planted = cases.write_planted(root, "eii_product", "x = 1\n")

                def guarded_read(path: Path) -> bytes:
                    if path == planted:
                        raise PermissionError(errno.EACCES, "denied", str(path))
                    return path.read_bytes()

                with mock.patch.object(guard, "read_file", side_effect=guarded_read):
                    failures, notes = guard.check_imports(root)
                expected = cases.expected_unparsable_read(planted_rel, "EACCES")
                self.assertEqual((failures, notes), ([expected], []))
            count += 1

        real_scandir = os.scandir

        def guarded_scandir(
            path: str | os.PathLike[str] = ".",
        ) -> Iterator[os.DirEntry[str]]:
            target = Path(path)
            if target.name == "blocked":
                raise PermissionError(errno.EACCES, "denied", str(target))
            return real_scandir(path)

        with self.subTest(case="scandir_EACCES"):
            with tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                cases.make_tree(root)
                blocked = cases.package_dir(root, "eii_product") / "blocked"
                blocked.mkdir(parents=True, exist_ok=True)
                (blocked / "x.py").write_text("x = 1\n", encoding="utf-8")
                with mock.patch.object(os, "scandir", side_effect=guarded_scandir):
                    failures, notes = guard.check_imports(root)
                expected = cases.expected_unparsable_read(
                    "product/src/eii_product/blocked", "EACCES"
                )
                self.assertEqual((failures, notes), ([expected], []))
            count += 1

        self.assertEqual(count, 10)

    def test_symbolic_links_fail(self) -> None:
        """Symbolic links under a source tree are reported and not followed."""
        count = 0
        with tempfile.TemporaryDirectory() as outer:
            aux = Path(outer)
            real_file = aux / "target.py"
            real_file.write_text("x = 1\n", encoding="utf-8")
            real_dir = aux / "pkg"
            real_dir.mkdir()
            (real_dir / "__init__.py").write_text(
                "__version__ = '0'\n", encoding="utf-8"
            )

            def plant_file_link(root: Path) -> str:
                link = cases.package_dir(root, "eii_product") / "link.py"
                os.symlink(real_file, link)
                return "product/src/eii_product/link.py"

            def plant_dir_link(root: Path) -> str:
                link = cases.package_dir(root, "eii_product") / "linkdir"
                os.symlink(real_dir, link)
                return "product/src/eii_product/linkdir"

            def plant_dangling(root: Path) -> str:
                link = cases.package_dir(root, "eii_product") / "gone.py"
                os.symlink(aux / "missing.py", link)
                return "product/src/eii_product/gone.py"

            def plant_tree_root(root: Path) -> str:
                shutil.rmtree(root / "product/src/eii_product")
                os.symlink(real_dir, root / "product/src/eii_product")
                return "product/src/eii_product"

            def plant_ancestor_src(root: Path) -> str:
                pkg_copy = aux / "product_copy"
                shutil.copytree(
                    root / "product/src/eii_product",
                    pkg_copy,
                    dirs_exist_ok=True,
                )
                shutil.rmtree(root / "product/src")
                os.symlink(pkg_copy, root / "product/src")
                return "product/src"

            def plant_pycache_link(root: Path) -> str:
                sneak_home = aux / "sneak_cache"
                sneak_home.mkdir(exist_ok=True)
                (sneak_home / "sneak.py").write_text(
                    "import eii_custodian\n", encoding="utf-8"
                )
                os.symlink(
                    sneak_home,
                    cases.package_dir(root, "eii_product") / "__pycache__",
                )
                return "product/src/eii_product/__pycache__"

            scenarios: tuple[tuple[str, Callable[[Path], str]], ...] = (
                ("file_link", plant_file_link),
                ("dir_link", plant_dir_link),
                ("dangling", plant_dangling),
                ("tree_root", plant_tree_root),
                ("ancestor_src", plant_ancestor_src),
                ("pycache_link", plant_pycache_link),
            )
            for label, plant in scenarios:
                with self.subTest(case=label):
                    with tempfile.TemporaryDirectory() as folder:
                        root = Path(folder)
                        cases.make_tree(root)
                        rel = plant(root)
                        failures, _notes = guard.check_imports(root)
                        expected = cases.expected_symlink_line(rel)
                        self.assertEqual(failures, [expected])
                count += 1
        self.assertEqual(count, 6)

    def test_pycache_is_scanned(self) -> None:
        """Python files inside ``__pycache__`` are still judged."""
        count = 0
        placements: tuple[tuple[str, str], ...] = (
            ("shallow", "product/src/eii_product/__pycache__/sneak.py"),
            ("deep", "product/src/eii_product/__pycache__/deep/sneak.py"),
        )
        for label, rel_path in placements:
            with self.subTest(case=label):
                with tempfile.TemporaryDirectory() as folder:
                    root = Path(folder)
                    cases.make_tree(root)
                    cache = cases.package_dir(root, "eii_product") / "__pycache__"
                    if label == "deep":
                        cache = cache / "deep"
                    cache.mkdir(parents=True, exist_ok=True)
                    (cache / "sneak.py").write_text(
                        "import eii_custodian\n",
                        encoding="utf-8",
                    )
                    failures, notes = guard.check_imports(root)
                    expected = cases.expected_forbidden_line(
                        rel_path,
                        1,
                        "import",
                        "eii_custodian",
                        "eii_product",
                        "eii_custodian",
                    )
                    self.assertEqual((failures, notes), ([expected], []))
            count += 1
        self.assertEqual(count, 2)

    def test_environment_names(self) -> None:
        """Forbidden environment variable names fail as exact substrings."""
        count = 0
        for package, _rel in _TREES:
            for name in guard.ENV_NAMES:
                with self.subTest(tree=package, name=name):
                    with tempfile.TemporaryDirectory() as folder:
                        root = Path(folder)
                        cases.make_tree(root)
                        cases.write_planted(root, package, f"# {name}\n")
                        failures, notes = guard.check_imports(root)
                        rel_file = cases.planted_rel_path(package)
                        expected = cases.expected_env_name_line(rel_file, 1, name)
                        self.assertEqual((failures, notes), ([expected], []))
                count += 1

        extra: tuple[
            tuple[str, Callable[[Path], None], list[str] | None],
            ...,
        ] = (
            (
                "notes_line2",
                _plant_env_notes_line2,
                [
                    cases.expected_env_name_line(
                        "product/src/eii_product/notes.txt",
                        2,
                        "EII_DECISION_PROVIDER",
                    )
                ],
            ),
            (
                "blob_bin",
                _plant_env_blob,
                [
                    cases.expected_env_name_line(
                        "product/src/eii_product/blob.bin",
                        1,
                        "JEV_PRO_API_KEY",
                    )
                ],
            ),
            (
                "two_names",
                _plant_env_dual_names,
                [
                    cases.expected_env_name_line(
                        "product/src/eii_product/dual.py",
                        2,
                        "EII_DECISION_PROVIDER",
                    ),
                    cases.expected_env_name_line(
                        "product/src/eii_product/dual.py",
                        4,
                        "JEV_PRO_API_KEY",
                    ),
                ],
            ),
            (
                "providers_suffix",
                _plant_env_providers_suffix,
                [
                    cases.expected_env_name_line(
                        "product/src/eii_product/planted.py",
                        1,
                        "EII_DECISION_PROVIDER",
                    )
                ],
            ),
            ("case_variants_pass", _plant_env_case_variants_pass, None),
            ("name_in_bytecode_cache_pass", _plant_env_name_in_bytecode_cache, None),
            (
                "name_in_package_pyc_fail",
                _plant_env_name_in_package_pyc,
                [
                    cases.expected_env_name_line(
                        "product/src/eii_product/m.pyc",
                        1,
                        "JEV_PRO_API_KEY",
                    )
                ],
            ),
            (
                "name_in_pycache_py_fail",
                _plant_env_name_in_pycache_py,
                [
                    cases.expected_env_name_line(
                        "product/src/eii_product/__pycache__/m.py",
                        1,
                        "EII_DECISION_PROVIDER",
                    )
                ],
            ),
            (
                "name_in_deep_pyc_fail",
                _plant_env_name_in_deep_pyc,
                [
                    cases.expected_env_name_line(
                        "product/src/eii_product/__pycache__/deep/m.cpython-314.pyc",
                        1,
                        "JEV_PRO_API_KEY",
                    )
                ],
            ),
        )
        for label, plant, expected_failures in extra:
            with self.subTest(case=label):
                with tempfile.TemporaryDirectory() as folder:
                    root = Path(folder)
                    cases.make_tree(root)
                    plant(root)
                    failures, notes = guard.check_imports(root)
                    if expected_failures is None:
                        self.assertEqual((failures, notes), ([], []))
                    else:
                        self.assertEqual(failures, expected_failures)
                        self.assertEqual(notes, [])
            count += 1

        self.assertEqual(count, 15)

    def test_output_order(self) -> None:
        """Failure lines follow the guard's rule sort order on a mixed tree."""
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            cases.make_tree(root)
            shutil.rmtree(root / "custodian/src/eii_custodian")
            core = cases.package_dir(root, "eii_core")
            with tempfile.TemporaryDirectory() as link_outer:
                target = Path(link_outer) / "tgt.py"
                target.write_text("x = 1\n", encoding="utf-8")
                os.symlink(target, core / "link.py")
            (core / "bad.py").write_text("def (:\n", encoding="utf-8")
            (core / "esc.py").write_text("from .. import x\n", encoding="utf-8")
            (core / "imp.py").write_text("import eii_product\n", encoding="utf-8")
            (core / "env.py").write_text("# JEV_PRO_API_KEY\n", encoding="utf-8")
            (core / "dyn.py").write_text(
                "import importlib\nimportlib.import_module(x)\n",
                encoding="utf-8",
            )
            failures, notes = guard.check_imports(root)
            self.assertEqual(
                failures,
                [
                    cases.expected_src_tree_missing("custodian/src/eii_custodian"),
                    cases.expected_symlink_line("core/src/eii_core/link.py"),
                    cases.expected_unparsable_parse(
                        "core/src/eii_core/bad.py", "SyntaxError"
                    ),
                    cases.expected_relative_escape_line("core/src/eii_core/esc.py", 1),
                    cases.expected_forbidden_line(
                        "core/src/eii_core/imp.py",
                        1,
                        "import",
                        "eii_product",
                        "eii_core",
                        "eii_product",
                    ),
                    cases.expected_env_name_line(
                        "core/src/eii_core/env.py", 1, "JEV_PRO_API_KEY"
                    ),
                ],
            )
            self.assertEqual(
                notes,
                [
                    cases.expected_dynamic_note_line(
                        "core/src/eii_core/dyn.py",
                        2,
                        "import_module",
                    )
                ],
            )

    def test_output_order_within_rule(self) -> None:
        """Forbidden-import failures in one group sort by path then line number."""
        padding = "\n".join(f"# pad {idx}" for idx in range(1, 9)) + "\n"
        twin = padding + "import eii_product\n" + "import eii_custodian\n"
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            cases.make_tree(root)
            core = cases.package_dir(root, "eii_core")
            (core / "twin.py").write_text(twin, encoding="utf-8")
            (core / "solo.py").write_text("import eii_gateway\n", encoding="utf-8")
            failures, notes = guard.check_imports(root)
            twin_base = "core/src/eii_core/twin.py"
            solo_base = "core/src/eii_core/solo.py"
            self.assertEqual(
                failures,
                [
                    cases.expected_forbidden_line(
                        solo_base,
                        1,
                        "import",
                        "eii_gateway",
                        "eii_core",
                        "eii_gateway",
                    ),
                    cases.expected_forbidden_line(
                        twin_base,
                        9,
                        "import",
                        "eii_product",
                        "eii_core",
                        "eii_product",
                    ),
                    cases.expected_forbidden_line(
                        twin_base,
                        10,
                        "import",
                        "eii_custodian",
                        "eii_core",
                        "eii_custodian",
                    ),
                ],
            )
            self.assertEqual(notes, [])
