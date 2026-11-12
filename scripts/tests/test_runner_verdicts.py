"""Acceptance tests for suite verdicts and skip reasons."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import runner_support as support

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

import run_tests

PASS = "def test_one():\n    assert True\n"
TWO = "def test_one():\n    assert True\n\ndef test_two():\n    assert True\n"
THREE = (
    "def test_one():\n    assert True\n\n"
    "def test_two():\n    assert True\n\n"
    "import unittest\n\n"
    "class Cases(unittest.TestCase):\n"
    "    def test_three(self):\n"
    "        self.assertTrue(True)\n"
)


class RunnerVerdicts(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="eii-verdict-")
        self.root = support.fixture_root(Path(self._tmp.name))

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_clean_suites_exit_zero(self) -> None:
        support.put(self.root, "fx/a/test_a.py", TWO)
        support.put(self.root, "fx/b/test_b.py", THREE)
        status, out, err = self._run(
            (
                support.fx_suite("fx-a", "pytest", ".", ("fx/a",)),
                support.fx_suite("fx-b", "pytest", ".", ("fx/b",)),
            )
        )
        self.assertEqual(err, [])
        self.assertEqual(status, 0, out)
        self.assertEqual(
            out,
            [
                f"seed={support.FIXTURE_SEED}",
                "suite fx-a: 2 passed, 0 failed, 0 skipped",
                "suite fx-b: 3 passed, 0 failed, 0 skipped",
                "total: 5 passed, 0 failed, 0 skipped in 2 suites, 0 with problems",
                "RESULT: PASSED",
            ],
        )

    def test_failing_test_exits_one_and_later_suites_still_run(self) -> None:
        support.put(self.root, "fx/ok/test_ok.py", TWO)
        support.put(
            self.root,
            "fx/fail/test_fail.py",
            "def test_one():\n    assert True\n\ndef test_two():\n    assert False\n",
        )
        support.put(self.root, "fx/after/test_after.py", PASS)
        status, out, err = self._run(
            (
                support.fx_suite("fx-ok", "pytest", ".", ("fx/ok",)),
                support.fx_suite("fx-fail", "pytest", ".", ("fx/fail",)),
                support.fx_suite("fx-after", "pytest", ".", ("fx/after",)),
            )
        )
        self.assertEqual(err, [])
        self.assertEqual(status, 1)
        self.assertEqual(
            support.visible(out),
            [
                f"seed={support.FIXTURE_SEED}",
                "suite fx-ok: 2 passed, 0 failed, 0 skipped",
                "suite fx-fail: 1 passed, 1 failed, 0 skipped",
                "FAIL tests-failed: fx-fail: 1 failed",
                "suite fx-after: 1 passed, 0 failed, 0 skipped",
                "total: 4 passed, 1 failed, 0 skipped in 3 suites, 1 with problems",
                "RESULT: FAILED",
            ],
        )
        block = "\n".join(out)
        self.assertIn("--- output of fx-fail (last 200 lines) ---", block)
        self.assertIn("assert False", block)
        self.assertNotIn("--- output of fx-ok", block)
        self.assertNotIn("--- output of fx-after", block)

    def test_error_counts_as_failed(self) -> None:
        support.put(
            self.root,
            "fx/err/test_err.py",
            "import pytest\n\n"
            "@pytest.fixture\n"
            "def boom():\n"
            "    raise RuntimeError('boom')\n\n"
            "def test_one(boom):\n"
            "    assert True\n",
        )
        status, out, _err = self._run(
            (support.fx_suite("fx-err", "pytest", ".", ("fx/err",)),)
        )
        visible = support.visible(out)
        self.assertIn("suite fx-err: 0 passed, 1 failed, 0 skipped", visible)
        self.assertIn("FAIL tests-failed: fx-err: 1 failed", visible)
        self.assertEqual(status, 1)

    def test_skip_reasons(self) -> None:
        rows: tuple[tuple[str, str, int, str | None], ...] = (
            (
                "mark",
                "@pytest.mark.skip(reason='not today')\ndef test_one():\n    assert True\n",
                1,
                "not today",
            ),
            (
                "oi100",
                "@pytest.mark.skip(reason='OI-100 later')\ndef test_one():\n    assert True\n",
                1,
                "OI-100 later",
            ),
            (
                "oi1",
                "@pytest.mark.skip(reason='see OI-1')\ndef test_one():\n    assert True\n",
                1,
                "see OI-1",
            ),
            (
                "oi10",
                "@pytest.mark.skip(reason='OI-10 no database answers')\n"
                "def test_one():\n    assert True\n",
                0,
                None,
            ),
            (
                "oi01",
                "@pytest.mark.skip(reason='OI-01 no live model key')\n"
                "def test_one():\n    assert True\n",
                0,
                None,
            ),
            (
                "unittest",
                "import unittest\n\n"
                "@unittest.skip('not today')\n"
                "def test_one():\n    assert True\n",
                1,
                "not today",
            ),
            (
                "xfail",
                "@pytest.mark.xfail(reason='later')\ndef test_one():\n    assert False\n",
                1,
                "later",
            ),
            (
                "empty",
                "import unittest\n\n"
                "@unittest.skip('')\n"
                "def test_one():\n    assert True\n",
                1,
                "Skipped",
            ),
            (
                "bare",
                "@pytest.mark.skip\ndef test_one():\n    assert True\n",
                1,
                "unconditional skip",
            ),
        )
        for name, body, expect_status, reason in rows:
            with self.subTest(name=name):
                text = body if body.startswith("import") else f"import pytest\n\n{body}"
                self._expect_skip(text, expect_status, reason, "test_one")
        module = (
            "import pytest\npytest.importorskip('nosuchmod')\n\n"
            "def test_one():\n    assert True\n"
        )
        with self.subTest(name="importorskip"):
            self._expect_module(module)
        module = (
            "import pytest\n"
            "pytest.skip('OI-10 no database answers', allow_module_level=True)\n\n"
            "def test_one():\n    assert True\n"
        )
        with self.subTest(name="module-level"):
            self._expect_module(module)

    def test_zero_tests_fail(self) -> None:
        support.put(self.root, "fx/empty/test_none.py", "VALUE = 1\n")
        status, out, _err = self._run(
            (support.fx_suite("fx-empty", "pytest", ".", ("fx/empty",)),)
        )
        visible = support.visible(out)
        self.assertIn("suite fx-empty: 0 passed, 0 failed, 0 skipped", visible)
        self.assertIn("FAIL no-tests: fx-empty: the suite ran no tests", visible)
        self.assertEqual(status, 1)

    def test_subtests_are_part_of_their_test(self) -> None:
        support.put(
            self.root,
            "fx/sub/test_sub.py",
            "import unittest\n\n"
            "def test_plain():\n    assert True\n\n"
            "class Blocks(unittest.TestCase):\n"
            "    def test_blocks(self):\n"
            "        for index in range(3):\n"
            "            with self.subTest(index=index):\n"
            "                self.assertTrue(True)\n",
        )
        status, out, _err = self._run(
            (support.fx_suite("fx-sub", "pytest", ".", ("fx/sub",)),)
        )
        self.assertEqual(status, 0, out)
        self.assertIn("suite fx-sub: 2 passed, 0 failed, 0 skipped", out)
        support.put(
            self.root,
            "fx/subfail/test_sub.py",
            "import unittest\n\n"
            "def test_plain():\n    assert True\n\n"
            "class Blocks(unittest.TestCase):\n"
            "    def test_blocks(self):\n"
            "        for index in range(3):\n"
            "            with self.subTest(index=index):\n"
            "                self.assertNotEqual(index, 1)\n",
        )
        status, out, _err = self._run(
            (support.fx_suite("fx-subfail", "pytest", ".", ("fx/subfail",)),)
        )
        visible = support.visible(out)
        self.assertEqual(status, 1)
        self.assertIn("suite fx-subfail: 1 passed, 1 failed, 0 skipped", visible)
        self.assertIn("FAIL tests-failed: fx-subfail: 1 failed", visible)
        self.assertFalse(
            any(line.startswith("FAIL exit-mismatch:") for line in visible)
        )
        self.assertIn("subTest", "\n".join(out))

    def _expect_skip(
        self, text: str, expect_status: int, reason: str | None, test_name: str
    ) -> None:
        support.put(self.root, "fx/skip/test_one.py", text)
        status, out, _err = self._run(
            (support.fx_suite("fx-skip", "pytest", ".", ("fx/skip",)),)
        )
        visible = support.visible(out)
        self.assertIn("suite fx-skip: 0 passed, 0 failed, 1 skipped", visible)
        self.assertEqual(status, expect_status, visible)
        if reason is None:
            self.assertFalse(any(line.startswith("FAIL ") for line in visible))
        else:
            self.assertIn(
                f"FAIL unexplained-skip: fx-skip: {test_name}: {reason}", visible
            )

    def _expect_module(self, text: str) -> None:
        folder = self.root / "fx" / "skip"
        if folder.exists():
            for child in folder.iterdir():
                child.unlink()
        support.put(self.root, "fx/skip/test_mod.py", text)
        status, out, _err = self._run(
            (support.fx_suite("fx-skip", "pytest", ".", ("fx/skip",)),)
        )
        visible = support.visible(out)
        self.assertEqual(status, 1, visible)
        self.assertIn("suite fx-skip: 0 passed, 0 failed, 1 skipped", visible)
        self.assertEqual(
            visible[visible.index("suite fx-skip: 0 passed, 0 failed, 1 skipped") + 1],
            "FAIL unexplained-skip: fx-skip: fx.skip.test_mod: collection skipped",
        )
        self.assertIn(
            "FAIL exit-mismatch: fx-skip: exit status 5 disagrees with 0 failed tests",
            visible,
        )

    def _run(
        self, suites: tuple[run_tests.Suite, ...]
    ) -> tuple[int, list[str], list[str]]:
        return support.call(
            ["--seed", support.FIXTURE_SEED],
            suites,
            self.root,
            support.parent_env(),
        )
