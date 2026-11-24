"""Prove the product split preserves every test and reports deselection."""

from __future__ import annotations

import hashlib
import shutil
import sys
import tempfile
import unittest
from collections.abc import Sequence
from pathlib import Path

import custodian_part_support as manifests
import runner_support as support
from hypothesis import given
from hypothesis import strategies as st

sys.path.insert(0, str(support.SCRIPTS))

import pytest_custodian_part as plugin
import run_tests

PLUGIN = "pytest_custodian_part"
OPTION = "--product-part"
FOLDER = "product/tests"
PART_NAMES = ("python-product-1", "python-product-2")
A, B, C = (f"{FOLDER}/test_{name}.py::test_one" for name in "abc")


def oracle(module: str, count: int) -> int:
    """Decision 0109 item 2, spelled independently of the plugin."""
    return int(hashlib.sha256(module.encode("utf-8")).hexdigest(), 16) % count + 1


def assert_partition(whole: Sequence[str], parts: Sequence[Sequence[str]]) -> None:
    manifests.assert_partition(whole, parts, suite="product", count=2)


def collect(root: Path, *args: str) -> list[str]:
    return manifests.nodeids(
        manifests.collect(root, (FOLDER, *args)), prefix=FOLDER + "/"
    )


class ProductManifest(unittest.TestCase):
    def test_real_collection_is_an_exact_partition(self) -> None:
        suites = [suite for suite in run_tests.SUITES if suite.name in PART_NAMES]
        self.assertEqual(
            [(suite.name, suite.args, suite.timeout) for suite in suites],
            [
                (name, (FOLDER, "-p", PLUGIN, OPTION, str(part)), 600)
                for part, name in enumerate(PART_NAMES, 1)
            ],
        )
        whole = collect(support.ROOT)
        assert_partition(whole, [collect(support.ROOT, *s.args[1:]) for s in suites])
        manifests.assert_modules_collected(
            whole,
            [
                path.relative_to(support.ROOT).as_posix()
                for pattern in ("test_*.py", "*_test.py")
                for path in (support.ROOT / FOLDER).rglob(pattern)
            ],
            suite="product",
        )

    def test_each_planted_violation_is_refused_by_its_own_clause(self) -> None:
        assert_partition([A, B], [[A], [B]])
        again = A.replace("test_one", "test_two")
        planted: tuple[tuple[str, list[str], list[list[str]]], ...] = (
            ("product parts overlap", [A, B], [[A, B], [B]]),
            ("product parts do not cover the whole", [A, B, C], [[A], [B]]),
            ("product parts do not cover the whole", [A, B], [[A, C], [B]]),
            ("product part counts do not add up", [A, B], [[A, A], [B]]),
            ("both product parts must be nonempty", [A, B], [[A, B], []]),
            ("both product parts must be nonempty", [A, B], [[A, B]]),
            ("both product parts must be nonempty", [A, B, C], [[A], [B], [C]]),
            ("product module belongs to multiple", [A, again], [[A], [again]]),
        )
        for reason, whole, parts in planted:
            with (
                self.subTest(reason=reason, parts=parts),
                self.assertRaisesRegex(AssertionError, reason),
            ):
                assert_partition(whole, parts)

    def test_planted_uncollected_test_file_is_refused(self) -> None:
        modules = [node.split("::", 1)[0] for node in (A, B)]
        manifests.assert_modules_collected([A, B], modules, suite="product")
        with self.assertRaisesRegex(
            AssertionError, "product collection differs from test files"
        ):
            manifests.assert_modules_collected(
                [A, B], [*modules, f"{FOLDER}/test_uncollected.py"], suite="product"
            )

    @given(st.text(), st.sampled_from((("custodian", 5), ("product", 2))))
    def test_every_path_lands_in_exactly_the_oracle_part(
        self, path: str, suite: tuple[str, int]
    ) -> None:
        name, count = suite
        part = plugin.module_part(path, count)
        self.assertIn(part, range(1, count + 1))
        self.assertEqual(part, oracle(path, count))
        if name == "custodian":
            self.assertEqual(plugin.module_part(path), part)

    def test_part_counts_are_the_decided_ones(self) -> None:
        self.assertEqual(plugin.PART_COUNTS, {"custodian": 5, "product": 2})


class ProductPlugin(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory(prefix="eii-product-part-")
        self.addCleanup(tmp.cleanup)
        self.root = support.fixture_root(Path(tmp.name))
        shutil.copy2(
            support.SCRIPTS / f"{PLUGIN}.py", self.root / "scripts" / f"{PLUGIN}.py"
        )
        for name in ("a", "b", "new_module", "nested/test_nested"):
            support.put(
                self.root,
                f"{FOLDER}/test_{name}.py",
                "import pytest\n"
                "@pytest.mark.parametrize('value', ['alpha', 'beta'])\n"
                "def test_one(value):\n    assert value\n",
            )

    def test_sha256_posix_module_paths_assign_all_cases_together(self) -> None:
        whole = collect(self.root)
        self.assertEqual(len(whole), 8)
        parts = [collect(self.root, "-p", PLUGIN, OPTION, part) for part in "12"]
        assert_partition(whole, parts)
        for part, actual in enumerate(parts, 1):
            self.assertEqual(
                actual, [t for t in whole if oracle(t.split("::")[0], 2) == part]
            )

    def test_loaded_plugin_without_option_preserves_collection(self) -> None:
        self.assertEqual(collect(self.root, "-p", PLUGIN), collect(self.root))

    def test_each_refused_command_line_names_its_own_reason(self) -> None:
        (self.root / "empty").mkdir()
        both = (OPTION, "1", "--custodian-part", "1")
        for folder, args, detail in (
            (FOLDER, (OPTION, "3"), "invalid choice"),
            (FOLDER, (OPTION, "0"), "invalid choice"),
            (FOLDER, (OPTION, ""), "invalid choice"),
            (FOLDER, (OPTION,), "expected one argument"),
            ("empty", (OPTION, "1"), "product part 1 selected no tests"),
            (FOLDER, both, "only one part option may be given"),
        ):
            with self.subTest(args=args):
                proc = manifests.collect(self.root, (folder, "-p", PLUGIN, *args))
                self.assertEqual(proc.returncode, 4, proc.stdout + proc.stderr)
                self.assertIn(detail, proc.stderr)

    def test_failed_collection_is_refused_and_never_read_as_empty(self) -> None:
        self.assertEqual(len(collect(self.root, "-p", PLUGIN, OPTION, "2")), 4)
        with self.assertRaisesRegex(AssertionError, "collection exit 4"):
            collect(self.root, "-p", PLUGIN, OPTION, "3")

    def test_excluded_items_are_deselected_and_never_skipped(self) -> None:
        proc = manifests.collect(self.root, (FOLDER, "-p", PLUGIN, OPTION, "1"))
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("4 deselected", proc.stdout)
        self.assertNotIn("skipped", proc.stdout)
