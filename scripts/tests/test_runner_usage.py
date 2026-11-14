"""Covers the arguments and the suite table."""

from __future__ import annotations

import json
import os
import shlex
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import runner_support as support

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

import run_tests

ROOT = support.ROOT
SEED_DETAIL = "seed must be ten decimal digits from 1000000000 to 4294967295"
ARABIC = "".join(chr(0x0660 + digit) for digit in (1, 7, 9, 4, 0, 0, 0, 0, 0, 0))


class RunnerUsage(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="eii-usage-")
        self.root = support.fixture_root(Path(self._tmp.name))

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_seed_is_printed_and_passed(self) -> None:
        support.put(
            self.root,
            "fx/seed/test_one.py",
            "def test_one():\n    assert True\n",
        )
        suite = support.fx_suite("fx-seed", "pytest", ".", ("fx/seed",))
        status, out, err = support.call(
            ["--seed", support.FIXTURE_SEED],
            (suite,),
            self.root,
            support.parent_env(),
        )
        self.assertEqual(err, [], err)
        self.assertEqual(status, 0, out)
        self.assertEqual(out[0], f"seed={support.FIXTURE_SEED}")
        status, out, err = support.call(
            [],
            (suite,),
            self.root,
            support.parent_env(),
            now=lambda: 1794000123.9,
        )
        self.assertEqual(err, [], err)
        self.assertEqual(status, 0, out)
        self.assertEqual(out[0], "seed=1794000123")

    def test_real_table(self) -> None:
        names = [suite.name for suite in run_tests.SUITES]
        self.assertEqual(len(names), len(set(names)))
        allowed = {"pytest", "node", "vitest"}
        for suite in run_tests.SUITES:
            self.assertIn(suite.kind, allowed)
            self.assertTrue((ROOT / suite.cwd).is_dir(), suite.cwd)
            if suite.kind == "pytest":
                for arg in suite.args:
                    self.assertTrue((ROOT / arg).is_dir(), arg)
        package = json.loads(
            (ROOT / "web" / "package.json").read_text(encoding="utf-8")
        )
        words = shlex.split(package["scripts"]["test:checks"])
        web = next(suite for suite in run_tests.SUITES if suite.name == "web-checks")
        self.assertEqual(web.args[-1], words[-1])
        spike = "spikes/glyphs/tests/*.node-test.mjs"
        performance = "spikes/performance/tests/*.node-test.mjs"
        script_globs = tuple(word for word in words if word.endswith(".mjs"))
        self.assertIn(spike, script_globs)
        self.assertIn(performance, script_globs)
        self.assertEqual(web.args, script_globs)
        expected = (
            "python-guards",
            "python-core",
            "python-custodian",
            "python-product",
            "web-checks",
            "web-unit",
        )
        index = 0
        for name in names:
            if index < len(expected) and name == expected[index]:
                index += 1
        self.assertEqual(index, len(expected))

    def test_web_checks_limit_on_a_hosted_runner(self) -> None:
        rows: tuple[tuple[dict[str, str], int], ...] = (
            ({}, 1800),
            (
                {
                    "GITHUB_ACTIONS": "true",
                    "RUNNER_ENVIRONMENT": "github-hosted",
                },
                3000,
            ),
            ({"GITHUB_ACTIONS": "true"}, 1800),
            ({"RUNNER_ENVIRONMENT": "github-hosted"}, 1800),
            (
                {"GITHUB_ACTIONS": "false", "RUNNER_ENVIRONMENT": "github-hosted"},
                1800,
            ),
            (
                {"GITHUB_ACTIONS": "true", "RUNNER_ENVIRONMENT": "self-hosted"},
                1800,
            ),
        )
        for environ, expected in rows:
            with self.subTest(environ=environ):
                with patch.dict(os.environ, environ, clear=True):
                    for suite in run_tests.SUITES:
                        if suite.name == "web-checks":
                            self.assertEqual(suite.timeout, 1800)
                            self.assertEqual(
                                run_tests.suite_timeout(suite, os.environ), expected
                            )
                        else:
                            self.assertEqual(
                                run_tests.suite_timeout(suite, os.environ),
                                suite.timeout,
                            )

    def test_usage_errors(self) -> None:
        rows = (
            (["--seed"], "--seed needs a value"),
            (["--seed", "abc"], SEED_DETAIL),
            (["--seed", "1" * 8], SEED_DETAIL),
            (["--seed", "1" * 9], SEED_DETAIL),
            (["--seed", "1" * 11], SEED_DETAIL),
            (["--seed", "4294967296"], SEED_DETAIL),
            (["--seed", "0999999999"], SEED_DETAIL),
            (["--seed", "-1794000000"], SEED_DETAIL),
            (["--seed", "+1794000000"], SEED_DETAIL),
            (["--seed", ARABIC], SEED_DETAIL),
            (
                ["--seed", "1794000000", "--seed", "1794000001"],
                "--seed given twice",
            ),
            (["--bogus"], 'unknown flag or argument "--bogus"'),
            (["--seed", "1794000000", "x"], 'unknown flag or argument "x"'),
            (["--seed=1794000000"], 'unknown flag or argument "--seed=1794000000"'),
        )
        for argv, detail in rows:
            with self.subTest(argv=argv):
                status, out, err = support.call(
                    argv, (), self.root, support.parent_env()
                )
                self.assertEqual(status, 2)
                self.assertEqual(out, [])
                self.assertEqual(
                    err,
                    [f"eii: usage error: {detail}. Usage: ./eii test [--seed N]"],
                )
