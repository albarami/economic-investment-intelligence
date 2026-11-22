"""The hosted suite matrix, its one-suite runner flag and the `tests` verdict."""

from __future__ import annotations

import io
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import ci_support
import ci_workflow_rules as rules
import runner_support as support
from hypothesis import given
from hypothesis import strategies as st

sys.path.insert(0, str(support.SCRIPTS))

import ci_aggregate
import ci_plant_cases as cases
import ci_plants as plants
import run_tests

NAMES = [suite.name for suite in run_tests.SUITES]
SEED = "1794000000"
GOOD = {"suite": {"result": "success"}, "web-spikes": {"result": "success"}}


def matrix_names(folder: Path) -> list[str]:
    text = (folder / "ci.yml").read_text(encoding="utf-8")
    names = rules._parse_workflow(text)["jobs"]["suite"]["strategy"]["matrix"]
    return list(names["suite"])


class SuiteMatrix(unittest.TestCase):
    def test_matrix_equals_the_suite_table(self) -> None:
        self.assertEqual(matrix_names(ci_support.WORKFLOW_DIR), NAMES)

    def test_one_suite_runs_together_equal_the_sequential_run(self) -> None:
        def ran(argv: list[str]) -> list[run_tests.Suite]:
            seen: list[run_tests.Suite] = []

            def record(suite: run_tests.Suite, *_args: object) -> object:
                seen.append(suite)
                return run_tests.SuiteResult(suite.name, None, (), ())

            with patch.object(run_tests, "run_suite", side_effect=record):
                status = run_tests.main(argv, out=io.StringIO(), err=io.StringIO())
            self.assertEqual(status, 0)
            return seen

        sequential = ran(["--seed", SEED])
        sharded = [
            suite
            for name in matrix_names(ci_support.WORKFLOW_DIR)
            for suite in ran(["--seed", SEED, "--suite", name])
        ]
        self.assertEqual(sharded, sequential)
        self.assertEqual(sequential, list(run_tests.SUITES))


class SuiteFlag(unittest.TestCase):
    def call(self, argv: list[str]) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with patch.object(
            run_tests,
            "run_suite",
            side_effect=lambda suite, *_a: run_tests.SuiteResult(
                suite.name, None, (), ()
            ),
        ):
            status = run_tests.main(argv, out=out, err=err)
        return status, out.getvalue(), err.getvalue()

    def test_one_named_suite_runs_alone_with_the_given_seed(self) -> None:
        status, out, err = self.call(["--suite", "python-core", "--seed", SEED])
        self.assertEqual((status, err), (0, ""))
        self.assertEqual(out.splitlines()[0], f"seed={SEED}")
        self.assertIn("in 1 suites", out)
        self.assertIn("suite python-core:", out)
        self.assertNotIn("suite python-guards:", out)

    def test_refusals_name_their_reason(self) -> None:
        usage = ". Usage: ./eii test [--seed N] [--suite NAME]\n"
        rows = (
            (
                ["--seed", SEED, "--suite", "python-custodian"],
                'unknown suite "python-custodian"; known suites: ' + ", ".join(NAMES),
            ),
            (
                ["--seed", SEED, "--suite", "python-core", "--suite", "web-unit"],
                "--suite given twice",
            ),
            (["--seed", SEED, "--suite"], "--suite needs a value"),
            (
                ["--seed", SEED, "--suite=python-core"],
                'unknown flag or argument "--suite=python-core"',
            ),
        )
        for argv, detail in rows:
            with self.subTest(argv=argv):
                self.assertEqual(
                    self.call(argv), (2, "", f"eii: usage error: {detail}{usage}")
                )


class Aggregate(unittest.TestCase):
    def verdict(self, needs: object) -> tuple[int, str]:
        out = io.StringIO()
        text = needs if isinstance(needs, str) else json.dumps(needs)
        return ci_aggregate.main([text], out), out.getvalue()

    def test_every_job_succeeded(self) -> None:
        self.assertEqual(self.verdict(GOOD), (0, "RESULT: PASSED\n"))

    def test_each_refusal_names_its_reason(self) -> None:
        rows: tuple[tuple[object, str], ...] = (
            ("{", "FAIL needs-unreadable: Expecting property name"),
            ([], "FAIL needs-unreadable: not a mapping of job results"),
            ({"suite": GOOD["suite"]}, "FAIL shard-missing: web-spikes"),
            ({**GOOD, "extra": GOOD["suite"]}, "FAIL shard-unexpected: extra"),
            (
                {**GOOD, "suite": {"result": "failure"}},
                "FAIL shard-result: suite: failure",
            ),
            (
                {**GOOD, "suite": {"result": "cancelled"}},
                "FAIL shard-result: suite: cancelled",
            ),
            (
                {**GOOD, "suite": {"result": "skipped"}},
                "FAIL shard-result: suite: skipped",
            ),
            ({**GOOD, "web-spikes": "success"}, "FAIL shard-result: web-spikes: None"),
            ({**GOOD, "suite": {}}, "FAIL shard-result: suite: None"),
        )
        for needs, line in rows:
            with self.subTest(needs=needs):
                status, out = self.verdict(needs)
                self.assertEqual(status, 1)
                self.assertIn(line, out)
                self.assertTrue(out.endswith("RESULT: FAILED\n"))

    def test_usage(self) -> None:
        out = io.StringIO()
        self.assertEqual(ci_aggregate.main([], out), 2)
        self.assertEqual(out.getvalue(), ci_aggregate.USAGE + "\n")
        out = io.StringIO()
        self.assertEqual(ci_aggregate.main([json.dumps(GOOD), "x"], out), 2)
        self.assertEqual(out.getvalue(), ci_aggregate.USAGE + "\n")

    @given(
        st.dictionaries(
            st.sampled_from(["suite", "web-spikes", "other", ""]),
            st.fixed_dictionaries(
                {
                    "result": st.sampled_from(
                        ["success", "failure", "cancelled", "skipped", "", None]
                    )
                }
            ),
        )
    )
    def test_passes_exactly_when_every_needed_job_succeeded(
        self, needs: dict[str, dict[str, object]]
    ) -> None:
        expected = set(needs) == set(ci_aggregate.NEEDED) and all(
            entry["result"] == "success" for entry in needs.values()
        )
        self.assertEqual(ci_aggregate.problems(json.dumps(needs)) == [], expected)


class ShardContract(unittest.TestCase):
    def planted(self, old: str, new: str, rule: str = "required-jobs") -> list[str]:
        home = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, home, True)
        folder = ci_support.workflow_fixture(home)
        path = folder / "ci.yml"
        text = path.read_text(encoding="utf-8")
        self.assertEqual(text.count(old), 1, old)
        path.write_text(text.replace(old, new), encoding="utf-8")
        return rules.rule_problems(rule, folder)

    def test_each_shard_refusal_names_its_reason(self) -> None:
        rows = (
            (
                "fail-fast: false",
                "fail-fast: true",
                "is not a matrix with fail-fast false",
            ),
            ("          - web-unit\n", "", "matrix differs from the SUITES table"),
            (
                "          - web-unit\n",
                "          - web-unit\n          - web-extra\n",
                "matrix differs from the SUITES table",
            ),
            (
                "    needs: [suite, web-spikes]\n",
                "    needs: [suite]\n",
                "does not need exactly the aggregated jobs",
            ),
            (
                "    if: ${{ always() }}\n",
                "    if: ${{ success() }}\n",
                "does not always run",
            ),
            (
                'run: python3 -I scripts/ci_aggregate.py "$NEEDS"',
                "run: python3 -I scripts/ci_aggregate.py",
                "does not run the aggregate verdict",
            ),
        )
        for old, new, reason in rows:
            with self.subTest(reason=reason, new=new):
                self.assertEqual(
                    self.planted(old, new),
                    [f"ci.yml: job suite {reason}"]
                    if "matrix" in reason
                    else [f"ci.yml: job tests {reason}"],
                )

    def test_condition_elsewhere_is_still_a_weakener(self) -> None:
        problems = self.planted(
            "    timeout-minutes: 45\n",
            "    timeout-minutes: 45\n" + rules.AGGREGATE_LINES,
            "no-weakeners",
        )
        self.assertIn("ci.yml: forbidden token 'needs:'", problems)
        self.assertIn("ci.yml: step or job condition", problems)

    def test_shards_fetch_the_scanner_before_their_suite(self) -> None:
        problems = self.planted(
            "      - name: Fetch the secret scanner\n"
            "        run: uv run --locked python scripts/hooks_gitleaks.py fetch\n"
            "      - name: Install web dependencies\n"
            "        run: npm ci\n"
            "        working-directory: web\n"
            "      - name: Build the web application\n"
            "        run: npm run build\n"
            "        working-directory: web\n"
            "      - name: Install the spike browser\n",
            "      - name: Install web dependencies\n"
            "        run: npm ci\n"
            "        working-directory: web\n"
            "      - name: Build the web application\n"
            "        run: npm run build\n"
            "        working-directory: web\n"
            "      - name: Install the spike browser\n",
            "required-steps",
        )
        self.assertIn("ci.yml: job suite does not fetch the scanner", problems)


class ShardPlants(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory(prefix="eii-shard-plants-")
        self.addCleanup(tmp.cleanup)
        self.root = support.fixture_root(Path(tmp.name))

    def test_matrix_result(self) -> None:
        self.assertEqual(plants.matrix_result([]), "success")
        self.assertEqual(plants.matrix_result(["success", "success"]), "success")
        self.assertEqual(plants.matrix_result(["success", "failure"]), "failure")
        self.assertEqual(plants.matrix_result(["skipped", "success"]), "skipped")
        self.assertEqual(plants.matrix_result(["skipped", "failure"]), "failure")

    def run_plant(self, plant: str) -> tuple[int, str]:
        cases.PLANTS[plant](self.root, support.parent_env())
        return plants.run_shards(self.root, support.parent_env())

    def test_clean_shards_pass(self) -> None:
        status, out = self.run_plant("passing-shards")
        self.assertEqual(status, 0, out)
        self.assertIn("suite planted-one: 1 passed", out)
        self.assertIn("suite planted-two: 1 passed", out)

    def test_planted_cases_fail_the_aggregate(self) -> None:
        for case in cases.CASES:
            if case.command != cases.AGGREGATE:
                continue
            with self.subTest(case=case.name):
                status, out = self.run_plant(case.plant)
                self.assertEqual(status, 1, out)
                self.assertIn(case.expect, out)


if __name__ == "__main__":
    unittest.main()
