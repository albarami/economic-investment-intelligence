"""Prove the custodian split preserves every test and reports deselection."""

from __future__ import annotations

import hashlib
import shutil
import sys
import tempfile
import unittest
from collections.abc import Callable
from pathlib import Path

import custodian_part_support as manifests
import runner_support as support

sys.path.insert(0, str(support.SCRIPTS))

import run_tests

PLUGIN = "pytest_custodian_part"
OPTION = "--custodian-part"
PART_NAMES = ("python-custodian-1", "python-custodian-2")


class CustodianManifest(unittest.TestCase):
    def test_real_collection_is_an_exact_partition(self) -> None:
        suites = [suite for suite in run_tests.SUITES if suite.name in PART_NAMES]
        self.assertEqual(tuple(suite.name for suite in suites), PART_NAMES)
        whole = manifests.nodeids(manifests.collect(support.ROOT, ("custodian/tests",)))
        parts = [
            manifests.nodeids(manifests.collect(support.ROOT, suite.args))
            for suite in suites
        ]
        manifests.assert_partition(whole, parts)

    def test_planted_part_function_drops_a_module(self) -> None:
        def dropped(module: str, part: int) -> bool:
            return module != "custodian/tests/test_a.py" and assigned(module, part)

        with self.assertRaisesRegex(AssertionError, "do not cover"):
            manifests.assert_partition(IDS, partition(dropped))

    def test_planted_part_function_duplicates_a_module(self) -> None:
        def duplicated(module: str, part: int) -> bool:
            return module == "custodian/tests/test_a.py" or assigned(module, part)

        with self.assertRaisesRegex(AssertionError, "overlap"):
            manifests.assert_partition(IDS, partition(duplicated))

    def test_planted_duplicate_id_fails_the_count_check(self) -> None:
        parts = partition(assigned)
        parts[0].append(parts[0][0])
        with self.assertRaisesRegex(AssertionError, "counts do not add up"):
            manifests.assert_partition(IDS, parts)

    def test_planted_empty_part_is_refused(self) -> None:
        with self.assertRaisesRegex(AssertionError, "nonempty"):
            manifests.assert_partition(IDS, (IDS, []))


IDS = [f"custodian/tests/test_{name}.py::test_one" for name in ("a", "b", "c")]


def assigned(module: str, part: int) -> bool:
    return part == (1 if module.endswith(("test_a.py", "test_b.py")) else 2)


def partition(select: Callable[[str, int], bool]) -> list[list[str]]:
    return [
        [test for test in IDS if select(test.split("::")[0], part)] for part in (1, 2)
    ]


class CustodianPlugin(unittest.TestCase):
    def setUp(self) -> None:
        plugin = support.ROOT / "scripts" / f"{PLUGIN}.py"
        self.assertTrue(plugin.is_file(), "the custodian partition plugin is missing")
        tmp = tempfile.TemporaryDirectory(prefix="eii-custodian-part-")
        self.addCleanup(tmp.cleanup)
        self.root = support.fixture_root(Path(tmp.name))
        shutil.copy2(plugin, self.root / "scripts" / plugin.name)
        for name in ("a", "b", "c", "new_module", "nested/test_nested"):
            support.put(
                self.root,
                f"custodian/tests/test_{name}.py",
                "import pytest\n"
                "@pytest.mark.parametrize('value', ['alpha', 'beta'])\n"
                "def test_one(value):\n    assert value\n",
            )

    def collect(self, *args: str) -> list[str]:
        return manifests.nodeids(
            manifests.collect(self.root, ("custodian/tests", *args))
        )

    def test_sha256_posix_module_paths_assign_all_cases_together(self) -> None:
        whole = self.collect()
        self.assertEqual(len(whole), 10)
        parts = [self.collect("-p", PLUGIN, OPTION, str(part)) for part in (1, 2)]
        manifests.assert_partition(whole, parts)
        for part, actual in enumerate(parts, 1):
            expected = [
                test
                for test in whole
                if int(
                    hashlib.sha256(test.split("::")[0].encode("utf-8")).hexdigest(), 16
                )
                % 2
                == part - 1
            ]
            self.assertEqual(actual, expected)

    def test_loaded_plugin_without_option_preserves_collection(self) -> None:
        self.assertEqual(self.collect("-p", PLUGIN), self.collect())

    def test_unknown_or_missing_part_is_a_usage_error(self) -> None:
        for args, detail in (
            ((OPTION, "3"), "invalid choice"),
            ((OPTION, "0"), "invalid choice"),
            ((OPTION, ""), "invalid choice"),
            ((OPTION,), "expected one argument"),
        ):
            with self.subTest(args=args):
                proc = manifests.collect(
                    self.root, ("custodian/tests", "-p", PLUGIN, *args)
                )
                self.assertEqual(proc.returncode, 4, proc.stdout + proc.stderr)
                self.assertIn(OPTION, proc.stderr)
                self.assertIn(detail, proc.stderr)

    def test_part_option_on_empty_folder_is_a_usage_error(self) -> None:
        (self.root / "empty").mkdir()
        proc = manifests.collect(self.root, ("empty", "-p", PLUGIN, OPTION, "1"))
        self.assertEqual(proc.returncode, 4, proc.stdout + proc.stderr)
        self.assertIn("custodian part 1 selected no tests", proc.stderr)

    def test_excluded_items_are_deselected_and_never_skipped(self) -> None:
        proc = manifests.collect(
            self.root, ("custodian/tests", "-p", PLUGIN, OPTION, "1")
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("deselected", proc.stdout)
        self.assertNotIn("skipped", proc.stdout)
