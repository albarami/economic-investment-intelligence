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
import run_tests_counts as counts

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
                for arg in suite.args[:1]:
                    self.assertTrue((ROOT / arg).is_dir(), arg)
        package = json.loads(
            (ROOT / "web" / "package.json").read_text(encoding="utf-8")
        )
        words = shlex.split(package["scripts"]["test:checks"])
        web = next(suite for suite in run_tests.SUITES if suite.name == "web-checks")
        self.assertEqual(web.args[-1], words[-1])
        # The browser run is the first test file and Node's test-file
        # concurrency is bounded to two, in the suite table and the npm
        # script both (S2-T10 part B).
        self.assertEqual(words[:2], ["node", "--test"])
        self.assertEqual(web.args, tuple(words[2:]))
        self.assertEqual(web.args[0], "--test-concurrency=2")
        self.assertEqual(web.args[1], "spikes/performance/tests/run.node-test.mjs")
        spike = "spikes/glyphs/tests/*.node-test.mjs"
        performance = "spikes/performance/tests/*.node-test.mjs"
        script_globs = tuple(word for word in words if word.endswith(".mjs"))
        self.assertIn(spike, script_globs)
        self.assertIn(performance, script_globs)
        expected = (
            "python-guards",
            "python-core",
            "python-custodian-1",
            "python-custodian-2",
            "python-custodian-3",
            "python-custodian-4",
            "python-custodian-5",
            "python-product-1",
            "python-product-2",
            "web-checks",
            "web-unit",
        )
        self.assertEqual(tuple(names), expected)
        expected_python = (
            ("python-guards", ("scripts/tests",), 3600),
            ("python-core", ("core/tests",), 600),
            (
                "python-custodian-1",
                (
                    "custodian/tests",
                    "-p",
                    "pytest_custodian_part",
                    "--custodian-part",
                    "1",
                ),
                1800,
            ),
            (
                "python-custodian-2",
                (
                    "custodian/tests",
                    "-p",
                    "pytest_custodian_part",
                    "--custodian-part",
                    "2",
                ),
                1800,
            ),
            (
                "python-custodian-3",
                (
                    "custodian/tests",
                    "-p",
                    "pytest_custodian_part",
                    "--custodian-part",
                    "3",
                ),
                1800,
            ),
            (
                "python-custodian-4",
                (
                    "custodian/tests",
                    "-p",
                    "pytest_custodian_part",
                    "--custodian-part",
                    "4",
                ),
                1800,
            ),
            (
                "python-custodian-5",
                (
                    "custodian/tests",
                    "-p",
                    "pytest_custodian_part",
                    "--custodian-part",
                    "5",
                ),
                1800,
            ),
            *(
                (
                    f"python-product-{part}",
                    (
                        "product/tests",
                        "-p",
                        "pytest_custodian_part",
                        "--product-part",
                        part,
                    ),
                    600,
                )
                for part in "12"
            ),
        )
        self.assertEqual(
            tuple(
                (suite.name, suite.args, suite.timeout)
                for suite in run_tests.SUITES
                if suite.kind == "pytest"
            ),
            expected_python,
        )

    def test_web_checks_limit_on_a_hosted_runner(self) -> None:
        rows: tuple[tuple[dict[str, str], int], ...] = (
            ({}, 1800),
            (
                {
                    "GITHUB_ACTIONS": "true",
                    "RUNNER_ENVIRONMENT": "github-hosted",
                },
                1800,
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
                        elif not suite.name.startswith("python-custodian-"):
                            # The custodian parts have their own hosted limit
                            # (decision 0101), tested below.
                            self.assertEqual(
                                run_tests.suite_timeout(suite, os.environ),
                                suite.timeout,
                            )

    def test_custodian_limit_on_a_hosted_runner(self) -> None:
        # Decision 0101: 2,400 s on a GitHub-hosted runner, 1,800 s everywhere
        # else; only both hosted variables with their exact values select it.
        parts = [
            suite
            for suite in run_tests.SUITES
            if suite.name.startswith("python-custodian-")
        ]
        self.assertEqual(len(parts), 5)
        rows: tuple[tuple[dict[str, str], int], ...] = (
            ({}, 1800),
            ({"GITHUB_ACTIONS": "true", "RUNNER_ENVIRONMENT": "github-hosted"}, 2400),
            ({"GITHUB_ACTIONS": "true"}, 1800),
            ({"RUNNER_ENVIRONMENT": "github-hosted"}, 1800),
            ({"GITHUB_ACTIONS": "false", "RUNNER_ENVIRONMENT": "github-hosted"}, 1800),
            ({"GITHUB_ACTIONS": "true", "RUNNER_ENVIRONMENT": "self-hosted"}, 1800),
        )
        for environ, expected in rows:
            with self.subTest(environ=environ):
                self.assertEqual(
                    tuple(run_tests.suite_timeout(suite, environ) for suite in parts),
                    (expected,) * 5,
                )
        others = [suite for suite in run_tests.SUITES if suite not in parts]
        self.assertTrue(all(suite.hosted_timeout is None for suite in others))
        self.assertTrue(all(suite.hosted_timeout == 2400 for suite in parts))

    def test_each_suite_prints_its_own_duration(self) -> None:
        first = run_tests.SuiteResult("first", counts.Counts(2, 0, 1, (), True), (), ())
        second = run_tests.SuiteResult(
            "second", counts.Counts(1, 0, 0, (), True), (), ()
        )
        suites = (
            support.fx_suite("first", "pytest", ".", ()),
            support.fx_suite("second", "pytest", ".", ()),
        )
        with patch.object(run_tests, "run_suite", side_effect=[first, second]):
            status, out, err = support.call(
                [],
                suites,
                self.root,
                support.parent_env(),
                now=iter([1794000123.9, 100.0, 102.5, 200.0, 200.3]).__next__,
            )
        self.assertEqual(err, [], err)
        self.assertEqual(status, 0, out)
        self.assertEqual(
            out,
            [
                "seed=1794000123",
                "suite first: 2 passed, 0 failed, 1 skipped in 2.5 s (2.1% of 120 s limit)",
                "suite second: 1 passed, 0 failed, 0 skipped in 0.3 s (0.3% of 120 s limit)",
                "total: 3 passed, 0 failed, 1 skipped in 2 suites, 0 with problems",
                "RESULT: PASSED",
            ],
        )

    def test_unavailable_counts_and_internal_error_print_duration(self) -> None:
        suites = (
            support.fx_suite("unavailable", "pytest", ".", ()),
            support.fx_suite("internal", "pytest", ".", ()),
        )
        result = run_tests.SuiteResult(
            "unavailable", None, ("FAIL invented-no-counts",), ()
        )
        with patch.object(
            run_tests, "run_suite", side_effect=[result, ValueError("invented")]
        ):
            status, out, err = support.call(
                ["--seed", support.FIXTURE_SEED],
                suites,
                self.root,
                support.parent_env(),
                now=iter([10.0, 11.5, 20.0, 24.25]).__next__,
            )
        self.assertEqual(err, [], err)
        self.assertEqual(status, 1, out)
        self.assertEqual(
            out,
            [
                f"seed={support.FIXTURE_SEED}",
                "suite unavailable: counts unavailable in 1.5 s (1.2% of 120 s limit)",
                "FAIL invented-no-counts",
                "suite internal: counts unavailable in 4.2 s (3.5% of 120 s limit)",
                "FAIL internal-error: internal: ValueError: invented",
                "total: 0 passed, 0 failed, 0 skipped in 2 suites, 2 with problems",
                "RESULT: FAILED",
            ],
        )

    def test_duration_normalisation_preserves_other_lines(self) -> None:
        self.assertEqual(
            support.untimed(
                [
                    "suite invented: counts unavailable in 1.5 s",
                    "suite invented: counts unavailable in 1.5 s (1.2% of 120 s limit)",
                    "FAIL invented in 1.5 s",
                    "suite invented: counts unavailable in unexpected s",
                ]
            ),
            [
                "suite invented: counts unavailable",
                "suite invented: counts unavailable",
                "FAIL invented in 1.5 s",
                "suite invented: counts unavailable in unexpected s",
            ],
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
                    [
                        f"eii: usage error: {detail}. Usage: ./eii test [--seed N] [--suite NAME]"
                    ],
                )
