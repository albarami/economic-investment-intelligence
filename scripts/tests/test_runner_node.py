"""Node suite tests for the runner."""

from __future__ import annotations

import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path

import runner_support as support

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

import run_tests


def _js(body: str) -> str:
    return (
        "import test from 'node:test';\nimport assert from 'node:assert/strict';\n"
        + body
    )


class RunnerNode(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="eii-node-")
        self.root = support.fixture_root(Path(self._tmp.name))
        self.assertTrue(run_tests.SUITES)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_node_suites(self) -> None:
        rows: tuple[tuple[str, str, str, int], ...] = (
            (
                "clean",
                _js(
                    "test('top', () => { assert.equal(1, 1); });\n"
                    "test.describe('group', () => {\n"
                    "  test('a', () => { assert.equal(1, 1); });\n"
                    "  test('b', () => { assert.equal(1, 1); });\n"
                    "});\n"
                ),
                "3 passed, 0 failed, 0 skipped",
                0,
            ),
            (
                "fail",
                _js(
                    "test('bad', () => { assert.equal(1, 2); });\n"
                    "test('good', () => { assert.equal(1, 1); });\n"
                ),
                "1 passed, 1 failed, 0 skipped",
                1,
            ),
            (
                "skip-reason",
                _js("test('alpha', { skip: 'later' }, () => {});\n"),
                "0 passed, 0 failed, 1 skipped",
                1,
            ),
            (
                "skip-flag",
                _js("test('alpha', (t) => { t.skip(); });\n"),
                "0 passed, 0 failed, 1 skipped",
                1,
            ),
            (
                "skip-standing",
                _js("test('alpha', { skip: 'OI-10 no database' }, () => {});\n"),
                "0 passed, 0 failed, 1 skipped",
                0,
            ),
            (
                "todo",
                _js("test('alpha', { todo: 'later' }, () => {});\n"),
                "0 passed, 0 failed, 1 skipped",
                1,
            ),
            (
                "todo-fail",
                _js(
                    "test('alpha', { todo: 'later' }, () => { throw new Error('x'); });\n"
                ),
                "0 passed, 0 failed, 1 skipped",
                1,
            ),
            (
                "suite-skip",
                _js(
                    "test.describe('skipped suite', { skip: 'suite reason' }, () => {\n"
                    "  test('a', () => {});\n  test('b', () => {});\n});\n"
                ),
                "0 passed, 0 failed, 1 skipped",
                1,
            ),
            (
                "suite-flag",
                _js(
                    "test.describe('skipped suite', { skip: true }, () => {\n"
                    "  test('a', () => {});\n});\n"
                ),
                "0 passed, 0 failed, 1 skipped",
                1,
            ),
            (
                "empty-file",
                "",
                "0 passed, 0 failed, 1 skipped",
                1,
            ),
            (
                "empty-describe",
                _js("test.describe('empty', () => {});\n"),
                "0 passed, 0 failed, 0 skipped",
                1,
            ),
            (
                "import",
                "import './missing-module.mjs';\n",
                "0 passed, 1 failed, 0 skipped",
                1,
            ),
            (
                "syntax",
                "export const = ;\n",
                "0 passed, 1 failed, 0 skipped",
                1,
            ),
            (
                "before",
                _js(
                    "test.describe('group', () => {\n"
                    "  test.before(() => { throw new Error('boom'); });\n"
                    "  test('a', () => {});\n  test('b', () => {});\n});\n"
                ),
                "0 passed, 2 failed, 0 skipped",
                1,
            ),
            (
                "t-before",
                _js(
                    "test('parent', async (t) => {\n"
                    "  t.before(() => { throw new Error('boom'); });\n"
                    "  await t.test('child', () => {});\n"
                    "});\n"
                ),
                "0 passed, 2 failed, 0 skipped",
                1,
            ),
            (
                "subtests",
                _js(
                    "test('parent', async (t) => {\n"
                    "  await t.test('ok', () => {});\n"
                    "  await t.test('bad', () => { throw new Error('x'); });\n"
                    "});\n"
                ),
                "1 passed, 1 failed, 0 skipped",
                1,
            ),
            (
                "hang",
                _js("test('hangs', { timeout: 50 }, () => new Promise(() => {}));\n"),
                "0 passed, 1 failed, 0 skipped",
                1,
            ),
        )
        for name, body, counts, expect in rows:
            with self.subTest(name=name):
                folder = self.root / "web" / "fx"
                if folder.exists():
                    for child in folder.iterdir():
                        child.unlink()
                support.put(self.root, "web/fx/case.node-test.mjs", body)
                status, out, _err = self._run()
                visible = support.visible(out)
                self.assertEqual(status, expect, visible)
                self.assertIn(f"suite fx-node: {counts}", visible)
                if name == "skip-reason":
                    self.assertIn(
                        "FAIL unexplained-skip: fx-node: alpha: later", visible
                    )
                if name == "skip-flag":
                    self.assertTrue(
                        any(
                            line.startswith("FAIL unexplained-skip: fx-node:")
                            and line.endswith(": no reason given")
                            for line in visible
                        ),
                        visible,
                    )
                if name == "skip-standing":
                    self.assertFalse(any(line.startswith("FAIL ") for line in visible))
                if name in {"todo", "todo-fail"}:
                    self.assertIn(
                        "FAIL unexplained-skip: fx-node: alpha: later", visible
                    )
                    self.assertFalse(
                        any(line.startswith("FAIL exit-mismatch:") for line in visible)
                    )
                if name == "suite-skip":
                    self.assertIn(
                        "FAIL unexplained-skip: fx-node: skipped suite: suite reason",
                        visible,
                    )
                if name == "suite-flag":
                    self.assertTrue(
                        any(line.endswith(": no reason given") for line in visible)
                    )
                if name == "empty-file":
                    self.assertTrue(
                        any(
                            "the file registers no test" in line
                            and line.startswith("FAIL unexplained-skip: fx-node:")
                            for line in visible
                        ),
                        visible,
                    )
                if name == "empty-describe":
                    self.assertIn(
                        "FAIL no-tests: fx-node: the suite ran no tests", visible
                    )
        with self.subTest(name="no-match"):
            folder = self.root / "web" / "fx"
            for child in folder.iterdir():
                child.unlink()
            status, out, _err = self._run()
            visible = support.visible(out)
            self.assertEqual(status, 1, visible)
            self.assertIn("FAIL no-tests: fx-node: the suite ran no tests", visible)
        with self.subTest(name="missing-reporter"):
            (self.root / "web" / "scripts" / "count-reporter.mjs").unlink()
            support.put(
                self.root, "web/fx/case.node-test.mjs", _js("test('a', () => {});\n")
            )
            status, out, _err = self._run()
            visible = support.visible(out)
            self.assertEqual(status, 1, visible)
            self.assertIn("suite fx-node: counts unavailable", visible)
            self.assertIn("FAIL no-counts: fx-node: result file is empty", visible)

    def test_missing_node_is_cannot_start(self) -> None:
        empty = Path(tempfile.mkdtemp(prefix="eii-nopath-"))
        self.addCleanup(lambda: __import__("shutil").rmtree(empty, ignore_errors=True))
        support.put(
            self.root,
            "web/fx/case.node-test.mjs",
            _js("test('a', () => {});\n"),
        )
        status, out, _err = support.call(
            ["--seed", support.FIXTURE_SEED],
            (support.fx_suite("fx-node", "node", "web", ("fx/*.node-test.mjs",)),),
            self.root,
            support.parent_env({"PATH": str(empty)}),
        )
        self.assertEqual(status, 1, out)
        self.assertIn("FAIL cannot-start: fx-node: node not found on PATH", out)

    def test_process_that_cannot_be_executed(self) -> None:
        bindir = Path(tempfile.mkdtemp(prefix="eii-badnode-"))
        self.addCleanup(lambda: __import__("shutil").rmtree(bindir, ignore_errors=True))
        node = bindir / "node"
        node.write_text("", encoding="utf-8")
        node.chmod(node.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
        support.put(
            self.root,
            "web/fx/case.node-test.mjs",
            _js("test('a', () => {});\n"),
        )
        status, out, _err = support.call(
            ["--seed", support.FIXTURE_SEED],
            (support.fx_suite("fx-exec", "node", "web", ("fx/*.node-test.mjs",)),),
            self.root,
            support.parent_env({"PATH": str(bindir)}),
        )
        visible = support.visible(out)
        self.assertEqual(status, 1, visible)
        self.assertIn("suite fx-exec: counts unavailable", visible)
        self.assertIn(
            "FAIL cannot-start: fx-exec: could not start the process (OSError)",
            visible,
        )

    def _run(self) -> tuple[int, list[str], list[str]]:
        return support.call(
            ["--seed", support.FIXTURE_SEED],
            (support.fx_suite("fx-node", "node", "web", ("fx/*.node-test.mjs",)),),
            self.root,
            support.parent_env({"PATH": os.environ.get("PATH", "")}),
        )
