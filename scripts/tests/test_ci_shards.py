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
WORKFLOW = str(ci_support.WORKFLOW_DIR / "ci.yml")
GUARDS_LINE = "          - python-guards\n"
PLANTED_VARIABLES = ("SHELLOPTS", "BASHOPTS", "BASH_ENV", "ENV", "PATH", "CI")
# YAML values a variable can hold: null, false and 0 included.
ENV_VALUES = st.one_of(st.none(), st.just("x"), st.booleans(), st.integers(-1, 1))
SCALARS = st.one_of(
    st.none(),
    st.booleans(),
    st.integers(-1, 1),
    st.sampled_from([0.0, 1.0]),
    st.text(max_size=1),
)
FORBIDDEN_JOB_KEYS = (
    "container",
    "services",
    "defaults",
    "concurrency",
    "outputs",
    "continue-on-error",
    "if",
    "needs",
    "strategy",
)
FORBIDDEN_STEP_KEYS = (
    "env",
    "shell",
    "working-directory",
    "if",
    "continue-on-error",
    "timeout-minutes",
    "id",
)


SUITE_RUN = '        run: ./eii test --seed 2026111201 --suite "$SUITE"\n'
SUITE_ENV = "        env:\n          SUITE: ${{ matrix.suite }}\n"
NEEDS_LINE = "          NEEDS: ${{ toJSON(needs) }}\n"
COMPARE = "        run: npm run test:spike:glyphs\n"
AGGREGATE_STEP = "Require the whole suite matrix and every needed job to succeed"
TESTS_CHECKOUT = (
    "    if: ${{ always() }}\n    steps:\n      - name: Check out\n"
    "        uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1\n"
    "        with:\n          persist-credentials: false\n"
)
LOCK = "      - name: Check the lock\n        run: uv lock --check\n"
VERSIONS = (
    "      - name: Check versions\n"
    "        run: uv run --locked python scripts/check_versions.py\n"
)
PRINT_VERSIONS = (
    "      - name: Sync the locked environment with the engine group\n"
    "        run: uv sync --managed-python --all-packages --locked --group engine\n"
    "      - name: Print tool versions\n"
)


def job_env(minutes: str, name: str) -> str:
    return f"    timeout-minutes: {minutes}\n    env:\n      {name}: noexec\n"


# Vector 1: a workflow, job or step environment differing from its declaration.
ENV_ROWS: tuple[tuple[str, str, str], ...] = (
    (
        "permissions:\n",
        "env:\n  SHELLOPTS: noexec\npermissions:\n",
        "FAIL workflow-env: SHELLOPTS",
    ),
    (
        "    timeout-minutes: 150\n",
        job_env("150", "SHELLOPTS"),
        "FAIL job-env: suite: SHELLOPTS",
    ),
    (
        "    timeout-minutes: 10\n",
        job_env("10", "BASHOPTS"),
        "FAIL job-env: tests: BASHOPTS",
    ),
    (
        "    timeout-minutes: 45\n",
        job_env("45", "BASH_ENV"),
        "FAIL job-env: web-spikes: BASH_ENV",
    ),
    (
        "    timeout-minutes: 25\n",
        job_env("25", "ENV"),
        "FAIL job-env: static-checks: ENV",
    ),
    (
        "    timeout-minutes: 150\n",
        "    timeout-minutes: 150\n    env: ${{ fromJSON(vars.E) }}\n",
        "FAIL job-env: suite: not a mapping",
    ),
    (
        SUITE_ENV,
        SUITE_ENV + "          PATH: /tmp/fake\n",
        "FAIL step-env: suite: Run one suite: PATH",
    ),
    (SUITE_ENV, "", "FAIL step-env: suite: Run one suite: SUITE"),
    (
        NEEDS_LINE,
        "          NEEDS: '{}'\n",
        f"FAIL step-env: tests: {AGGREGATE_STEP}: NEEDS",
    ),
    (
        COMPARE,
        COMPARE + "        env:\n          SHELLOPTS: noexec\n",
        "FAIL step-env: web-spikes: Compare spike screenshots: SHELLOPTS",
    ),
    # A null value is a present key: it never matches an absent declaration.
    (
        "permissions:\n",
        "env:\n  SHELLOPTS:\npermissions:\n",
        "FAIL workflow-env: SHELLOPTS",
    ),
    (
        "    timeout-minutes: 150\n",
        "    timeout-minutes: 150\n    env:\n      SHELLOPTS: null\n",
        "FAIL job-env: suite: SHELLOPTS",
    ),
    (
        SUITE_ENV,
        SUITE_ENV + "          SHELLOPTS: ~\n",
        "FAIL step-env: suite: Run one suite: SHELLOPTS",
    ),
    (
        COMPARE,
        COMPARE + "        env:\n          CI: null\n",
        "FAIL step-env: web-spikes: Compare spike screenshots: CI",
    ),
    (
        SUITE_ENV,
        SUITE_ENV + "          1: x\n",
        "FAIL step-env: suite: Run one suite: 1",
    ),
    # An explicit null env is not a mapping at any scope.
    ("permissions:\n", "env:\npermissions:\n", "FAIL workflow-env: not a mapping"),
    (
        "    timeout-minutes: 150\n",
        "    timeout-minutes: 150\n    env: null\n",
        "FAIL job-env: suite: not a mapping",
    ),
    (
        COMPARE,
        COMPARE + "        env: null\n",
        "FAIL step-env: web-spikes: Compare spike screenshots: not a mapping",
    ),
)
# Family sweep: a declared value is matched by type as well as value, so
# 0 never passes for false, 150.0 never for 150 and a key 1 never for true.
TYPE_ROWS: tuple[tuple[str, str, str], ...] = (
    (
        "      fail-fast: false\n",
        "      fail-fast: 0\n",
        "FAIL strategy-keys: the suite strategy is not fail-fast false alone",
    ),
    (
        "    timeout-minutes: 150\n",
        "    timeout-minutes: 150.0\n",
        "FAIL job-value: suite: timeout-minutes",
    ),
    (
        TESTS_CHECKOUT,
        TESTS_CHECKOUT.replace("false", "0"),
        "FAIL step-missing: tests: Check out",
    ),
    (
        "          package-manager-cache: false\n" + PRINT_VERSIONS,
        "          package-manager-cache: 0\n" + PRINT_VERSIONS,
        "FAIL step-missing: static-checks: Install Node from .nvmrc",
    ),
    ("\non:\n", "\n1:\n", "FAIL workflow-key: 1"),
)
# Vector 2: a step not declared, a reordered step, a changed setup step.
STEP_ROWS: tuple[tuple[str, str, str], ...] = (
    (
        "      - name: Run one suite\n",
        '      - name: Poison\n        run: echo SHELLOPTS=noexec >> "$GITHUB_ENV"\n'
        "      - name: Run one suite\n",
        "FAIL step-extra: suite: Poison",
    ),
    (
        NEEDS_LINE,
        NEEDS_LINE + '      - name: Path\n        run: echo /tmp >> "$GITHUB_PATH"\n',
        "FAIL step-extra: tests: Path",
    ),
    (
        "      - name: Compare spike screenshots\n",
        "      - run: echo x\n      - name: Compare spike screenshots\n",
        "FAIL step-extra: web-spikes: None",
    ),
    (
        NEEDS_LINE,
        NEEDS_LINE + "      - name: Install uv\n        run: true\n",
        "FAIL step-extra: tests: Install uv",
    ),
    (
        LOCK + VERSIONS,
        VERSIONS + LOCK,
        "FAIL step-order: static-checks: the steps are not in declared order",
    ),
    (
        TESTS_CHECKOUT,
        TESTS_CHECKOUT.replace("3d3c42e5", "0000000a"),
        "FAIL step-missing: tests: Check out",
    ),
    (
        TESTS_CHECKOUT,
        TESTS_CHECKOUT.replace("false", "true"),
        "FAIL step-missing: tests: Check out",
    ),
    (
        TESTS_CHECKOUT,
        TESTS_CHECKOUT + "          path: elsewhere\n",
        "FAIL step-missing: tests: Check out",
    ),
    (
        "        run: uv --version && node --version && npm --version && git --version\n",
        "        run: echo ok\n",
        "FAIL step-missing: static-checks: Print tool versions",
    ),
    (
        "      - name: Print tool versions\n"
        "        run: uv --version && node --version && npm --version && git --version\n",
        "",
        "FAIL step-missing: static-checks: Print tool versions",
    ),
)
# Vector 3: job keys and workflow root keys are exact allow-lists.
JOB_ROWS: tuple[tuple[str, str, str], ...] = (
    (
        "    timeout-minutes: 150\n",
        "    timeout-minutes: 150\n    container: ubuntu:24.04\n",
        "FAIL job-key: suite: container",
    ),
    (
        "    timeout-minutes: 150\n",
        "    timeout-minutes: 150\n    services:\n      db:\n        image: postgres\n",
        "FAIL job-key: suite: services",
    ),
    (
        "    runs-on: ubuntu-24.04\n    timeout-minutes: 150\n",
        "    runs-on: ubuntu-22.04\n    timeout-minutes: 150\n",
        "FAIL job-value: suite: runs-on",
    ),
    (
        "    timeout-minutes: 150\n",
        "    timeout-minutes: 1\n",
        "FAIL job-value: suite: timeout-minutes",
    ),
    ("    timeout-minutes: 10\n", "", "FAIL job-value: tests: timeout-minutes"),
    (
        "  tests:\n    name: tests\n",
        "  tests:\n    name: test\n",
        "FAIL job-value: tests: name",
    ),
    (
        "    timeout-minutes: 10\n",
        "    timeout-minutes: 10\n    concurrency: one\n",
        "FAIL job-key: tests: concurrency",
    ),
    (
        "    timeout-minutes: 45\n",
        "    timeout-minutes: 45\n    outputs:\n      x: y\n",
        "FAIL job-key: web-spikes: outputs",
    ),
    (
        "    timeout-minutes: 45\n",
        "    timeout-minutes: 45\n    defaults:\n      run:\n        shell: sh\n",
        "FAIL job-key: web-spikes: defaults",
    ),
    (
        "      fail-fast: false\n",
        "      fail-fast: false\n      max-parallel: 1\n",
        "FAIL strategy-keys: the suite strategy is not fail-fast false alone",
    ),
    (
        "      fail-fast: false\n",
        "      fail-fast: true\n",
        "FAIL strategy-keys: the suite strategy is not fail-fast false alone",
    ),
    (
        "permissions:\n",
        "concurrency:\n  group: x\npermissions:\n",
        "FAIL workflow-key: concurrency",
    ),
    (
        "  contents: read\n",
        "  contents: write\n",
        "FAIL workflow-permissions: not contents read alone",
    ),
    (
        "    shell: bash\n\njobs:\n",
        "    shell: bash\n    working-directory: web\n\njobs:\n",
        "FAIL workflow-defaults: the run shell is not bash",
    ),
)
# Vector 4: step keys are an exact allow-list; env is vector 1.
STEP_KEY_ROWS: tuple[tuple[str, str, str], ...] = (
    *(
        (
            SUITE_RUN,
            SUITE_RUN + f"        {key}: {value}\n",
            f"FAIL step-key: suite: Run one suite: {key}",
        )
        for key, value in (
            ("shell", "sh {0}"),
            ("working-directory", "web"),
            ("if", "${{ true }}"),
            ("continue-on-error", "true"),
            ("timeout-minutes", "0"),
            ("id", "x"),
        )
    ),
    (
        COMPARE + "        working-directory: web\n",
        COMPARE + "        working-directory: .\n",
        "FAIL step-missing: web-spikes: Compare spike screenshots",
    ),
)


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
    def verdict(self, needs: object, workflow: str = WORKFLOW) -> tuple[int, str]:
        out = io.StringIO()
        text = needs if isinstance(needs, str) else json.dumps(needs)
        return ci_aggregate.main([workflow, text], out), out.getvalue()

    def edited(self, old: str, new: str) -> str:
        home = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, home, True)
        path = ci_support.workflow_fixture(home) / "ci.yml"
        text = path.read_text(encoding="utf-8")
        self.assertEqual(text.count(old), 1, old)
        path.write_text(text.replace(old, new), encoding="utf-8")
        return str(path)

    def test_dropped_python_guards_fails_without_its_own_suite(self) -> None:
        self.assertIn("python-guards", NAMES)
        status, out = self.verdict(GOOD, self.edited(GUARDS_LINE, ""))
        self.assertEqual(
            (status, out),
            (1, "FAIL matrix-missing: python-guards\nRESULT: FAILED\n"),
        )

    def test_each_matrix_refusal_names_its_reason(self) -> None:
        listed = "".join(f"          - {name}\n" for name in NAMES)
        rows = (
            (
                "        suite:\n" + listed,
                "        suite: []\n",
                "FAIL matrix-empty: the suite matrix lists no suite",
            ),
            (
                "        suite:\n" + listed,
                "        suite: python-guards\n",
                "FAIL matrix-unreadable: the suite matrix is not a list of names",
            ),
            (
                "          - web-unit\n",
                "          - web-unit\n          - web-extra\n",
                "FAIL matrix-unexpected: web-extra",
            ),
            (
                "          - web-unit\n",
                "          - web-unit\n          - web-checks\n",
                "FAIL matrix-duplicate: web-checks",
            ),
            (
                GUARDS_LINE + "          - python-core\n",
                "          - python-core\n" + GUARDS_LINE,
                "FAIL matrix-order: the suite matrix is not in SUITES order",
            ),
            (
                "      matrix:\n",
                "      matrix-off:\n",
                ci_aggregate.NO_AXIS,
            ),
        )
        for old, new, line in rows:
            with self.subTest(line=line):
                status, out = self.verdict(GOOD, self.edited(old, new))
                self.assertEqual((status, out), (1, f"{line}\nRESULT: FAILED\n"))

    def test_each_shape_refusal_names_its_reason(self) -> None:
        """Rows 1 to 10 of the S2-CI round-3 family, one change each."""
        listed = "".join(f"          - {name}\n" for name in NAMES)
        matrix = "      matrix:\n        suite:\n" + listed
        run = '        run: ./eii test --seed 2026111201 --suite "$SUITE"\n'
        env = "        env:\n          SUITE: ${{ matrix.suite }}\n"
        compare = "        run: npm run test:spike:glyphs\n"
        aggregate = f"        run: {rules.AGGREGATE_RUN}\n"
        shape = f"        run: {ci_aggregate.SHAPE_RUN}\n"
        shell = "\n".join(
            [
                "      - name: Run one suite",
                '        run: ./eii test --seed 2026111201 --suite "$SUITE"',
                "        shell: sh {0}",
                "",
            ]
        )
        rows = (
            # 1 exclude, 2 include, 3 another axis
            (
                "          - web-unit\n",
                "          - web-unit\n        exclude:\n          - suite: python-guards\n",
                "FAIL matrix-keys: exclude",
            ),
            (
                "          - web-unit\n",
                "          - web-unit\n        include:\n          - suite: web-unit\n"
                "            extra: x\n",
                "FAIL matrix-keys: include",
            ),
            (
                "      matrix:\n",
                "      matrix:\n        os: [ubuntu-24.04]\n",
                "FAIL matrix-keys: os",
            ),
            # 4 the matrix, the strategy or the list written as an expression
            (matrix, "      matrix: ${{ fromJSON(vars.M) }}\n", ci_aggregate.NO_AXIS),
            (
                "    strategy:\n      fail-fast: false\n" + matrix,
                "    strategy: ${{ fromJSON(vars.S) }}\n",
                ci_aggregate.NO_AXIS,
            ),
            (
                "        suite:\n" + listed,
                "        suite: ${{ fromJSON(vars.L) }}\n",
                ci_aggregate.NOT_A_LIST,
            ),
            # 5 job continue-on-error, 9 job condition
            (
                "    timeout-minutes: 150\n",
                "    timeout-minutes: 150\n    continue-on-error: true\n",
                "FAIL job-key: suite: continue-on-error",
            ),
            (
                "    timeout-minutes: 150\n",
                "    timeout-minutes: 150\n    if: ${{ true }}\n",
                "FAIL job-key: suite: if",
            ),
            (
                "    timeout-minutes: 150\n",
                "    timeout-minutes: 150\n    defaults:\n      run:\n        shell: sh\n",
                "FAIL job-key: suite: defaults",
            ),
            (
                "    timeout-minutes: 150\n",
                "    timeout-minutes: 150\n    needs: [static-checks]\n",
                "FAIL job-key: suite: needs",
            ),
            # 6 step continue-on-error, 7 step condition, shell or command
            (
                run,
                run + "        continue-on-error: true\n",
                "FAIL step-key: suite: Run one suite: continue-on-error",
            ),
            (
                run,
                run + "        if: ${{ true }}\n",
                "FAIL step-key: suite: Run one suite: if",
            ),
            (
                run,
                shell.split("\n", 1)[1],
                "FAIL step-key: suite: Run one suite: shell",
            ),
            (
                run,
                '        run: ./eii test --seed 2026111201 --suite "$SUITE" || true\n',
                "FAIL step-missing: suite: Run one suite",
            ),
            (
                run,
                '        run: ./eii test --seed 2026111201 --suite "$SUITE"; true\n',
                "FAIL step-missing: suite: Run one suite",
            ),
            (
                run,
                '        run: set +e; ./eii test --seed 2026111201 --suite "$SUITE"\n',
                "FAIL step-missing: suite: Run one suite",
            ),
            (
                run,
                "        run: ./eii test --seed 2026111201 --suite python-core\n",
                "FAIL step-missing: suite: Run one suite",
            ),
            (
                env,
                "        env:\n          SUITE: python-core\n",
                "FAIL step-env: suite: Run one suite: SUITE",
            ),
            # 8 the tests job
            (
                "    if: ${{ always() }}\n",
                "",
                "FAIL tests-condition: job tests does not always run",
            ),
            (
                "    if: ${{ always() }}\n",
                "    if: ${{ success() }}\n",
                "FAIL tests-condition: job tests does not always run",
            ),
            (
                "    needs: [suite, web-spikes]\n",
                "    needs: [suite]\n",
                "FAIL tests-needs: job tests does not need exactly suite, web-spikes",
            ),
            (
                "    needs: [suite, web-spikes]\n",
                "    needs: [web-spikes]\n",
                "FAIL tests-needs: job tests does not need exactly suite, web-spikes",
            ),
            (
                "    timeout-minutes: 10\n",
                "    timeout-minutes: 10\n    continue-on-error: true\n",
                "FAIL job-key: tests: continue-on-error",
            ),
            (
                aggregate,
                aggregate + "        continue-on-error: true\n",
                "FAIL step-key: tests: "
                + ci_aggregate.AGGREGATE_NAME
                + ": continue-on-error",
            ),
            (
                aggregate,
                aggregate.rstrip("\n") + " || true\n",
                "FAIL step-missing: tests: " + ci_aggregate.AGGREGATE_NAME,
            ),
            # 10 web-spikes
            (
                "    timeout-minutes: 45\n",
                "    timeout-minutes: 45\n    continue-on-error: true\n",
                "FAIL job-key: web-spikes: continue-on-error",
            ),
            (
                "    timeout-minutes: 45\n",
                "    timeout-minutes: 45\n    if: ${{ true }}\n",
                "FAIL job-key: web-spikes: if",
            ),
            (
                "    timeout-minutes: 45\n",
                "    timeout-minutes: 45\n    strategy:\n      matrix:\n        x: [1]\n",
                "FAIL job-key: web-spikes: strategy",
            ),
            (
                compare,
                compare + "        continue-on-error: true\n",
                "FAIL step-key: web-spikes: Compare spike screenshots: continue-on-error",
            ),
            (
                compare,
                compare + "        if: ${{ false }}\n",
                "FAIL step-key: web-spikes: Compare spike screenshots: if",
            ),
            (
                compare,
                "        run: npm run test:spike:glyphs || true\n",
                "FAIL step-missing: web-spikes: Compare spike screenshots",
            ),
            # the independent shape check in static-checks
            (
                shape,
                shape.rstrip("\n") + " || true\n",
                "FAIL step-missing: static-checks: " + ci_aggregate.SHAPE_NAME,
            ),
            (
                "    timeout-minutes: 25\n",
                "    timeout-minutes: 25\n    needs: [suite]\n",
                "FAIL job-key: static-checks: needs",
            ),
            (
                "defaults:\n  run:\n    shell: bash\n",
                "defaults:\n  run:\n    shell: sh\n",
                "FAIL workflow-defaults: the run shell is not bash",
            ),
            (
                "  suite:\n    name: suite\n",
                "  suites:\n    name: suite\n",
                "FAIL job-missing: suite",
            ),
        )
        for old, new, line in rows:
            with self.subTest(line=line, new=new):
                status, out = self.verdict(GOOD, self.edited(old, new))
                self.assertEqual((status, out), (1, f"{line}\nRESULT: FAILED\n"))

    def assert_rows(self, rows: tuple[tuple[str, str, str], ...]) -> None:
        for old, new, line in rows:
            with self.subTest(line=line, new=new):
                status, out = self.verdict(GOOD, self.edited(old, new))
                self.assertEqual((status, out), (1, f"{line}\nRESULT: FAILED\n"))

    def test_vector_1_no_inherited_or_changed_environment(self) -> None:
        self.assert_rows(ENV_ROWS)

    def test_vector_2_no_extra_or_changed_step(self) -> None:
        self.assert_rows(STEP_ROWS)

    def test_vector_3_job_and_root_keys_are_an_allow_list(self) -> None:
        self.assert_rows(JOB_ROWS)

    def test_vector_4_step_keys_are_an_allow_list(self) -> None:
        self.assert_rows(STEP_KEY_ROWS)

    def test_vector_5_declared_values_match_by_type(self) -> None:
        self.assert_rows(TYPE_ROWS)

    def test_shape_alone_refuses_without_any_job_result(self) -> None:
        """Row 8 is refused by static-checks, which needs no job and is never skipped."""
        out = io.StringIO()
        self.assertEqual(ci_aggregate.main([WORKFLOW], out), 0)
        self.assertEqual(out.getvalue(), "RESULT: PASSED\n")
        out = io.StringIO()
        edited = self.edited("    if: ${{ always() }}\n", "")
        self.assertEqual(ci_aggregate.main([edited], out), 1)
        self.assertEqual(
            out.getvalue(),
            "FAIL tests-condition: job tests does not always run\nRESULT: FAILED\n",
        )
        jobs = rules._parse_workflow(Path(WORKFLOW).read_text(encoding="utf-8"))["jobs"]
        static = jobs["static-checks"]
        self.assertFalse({"needs", "if", "continue-on-error"} & set(static))
        self.assertIn(ci_aggregate.SHAPE_RUN, [s.get("run") for s in static["steps"]])

    @given(st.sets(st.sampled_from(["suite", "exclude", "include", "os", ""])))
    def test_matrix_passes_exactly_with_the_one_suite_axis(
        self, keys: set[str]
    ) -> None:
        matrix = {key: list(NAMES) for key in keys}
        job = {"strategy": {"fail-fast": False, "matrix": matrix}}
        self.assertEqual(
            ci_aggregate.matrix_shape_problems(job) == [], keys == {"suite"}
        )

    @given(
        st.sets(st.sampled_from([*FORBIDDEN_JOB_KEYS, "timeout-minutes", "name"])),
        st.dictionaries(st.sampled_from(PLANTED_VARIABLES), ENV_VALUES),
    )
    def test_job_passes_exactly_with_its_declared_keys(
        self, keys: set[str], env: dict[str, str]
    ) -> None:
        job: dict[str, object] = {
            **ci_aggregate.JOB_VALUES["web-spikes"],
            "steps": [dict(step) for step in ci_aggregate.JOB_STEPS["web-spikes"]],
            **{key: "x" for key in keys},
        }
        if env:
            job["env"] = env
        clean = not (keys & set(FORBIDDEN_JOB_KEYS)) and not keys and not env
        self.assertEqual(ci_aggregate.job_problems("web-spikes", job) == [], clean)

    @given(
        st.integers(0, len(ci_aggregate.JOB_STEPS["suite"]) - 1),
        st.sets(st.sampled_from([*FORBIDDEN_STEP_KEYS, "name"])),
        st.dictionaries(st.sampled_from([*PLANTED_VARIABLES, "SUITE"]), ENV_VALUES),
    )
    def test_step_passes_exactly_with_its_declared_keys_and_env(
        self, index: int, keys: set[str], env: dict[str, str]
    ) -> None:
        steps = [dict(step) for step in ci_aggregate.JOB_STEPS["suite"]]
        want = dict(steps[index])
        steps[index].update({key: "x" for key in keys - {"env"}})
        if env or "env" in keys:
            steps[index]["env"] = env
        job = {**ci_aggregate.JOB_VALUES["suite"], "steps": steps}
        found = [
            line
            for line in ci_aggregate.job_problems("suite", job)
            if not line.startswith("FAIL job-")
        ]
        env_now = steps[index].get("env") or {}
        clean = not (keys - {"env"}) and env_now == (want.get("env") or {})
        self.assertEqual(found == [], clean, (keys, env, found))

    @given(st.permutations(range(len(ci_aggregate.JOB_STEPS["tests"]))))
    def test_steps_pass_exactly_in_declared_order(self, order: list[int]) -> None:
        declared = ci_aggregate.JOB_STEPS["tests"]
        steps: list[object] = [dict(declared[i]) for i in order]
        found = ci_aggregate.step_problems("tests", steps)
        self.assertEqual(found == [], order == sorted(order))

    @given(
        st.dictionaries(
            st.one_of(st.sampled_from(PLANTED_VARIABLES), st.integers(0, 2)),
            st.one_of(st.just("noexec"), ENV_VALUES),
        )
    )
    def test_any_inherited_variable_fails(self, env: dict[object, object]) -> None:
        self.assertEqual(ci_aggregate.env_problems("e", env, {}) == [], not env)
        self.assertEqual(
            ci_aggregate.env_problems("e", env, {}),
            [f"FAIL e: {k}" for k in sorted(str(k) for k in env)],
        )

    @given(SCALARS, SCALARS)
    def test_same_is_equality_by_type_and_value(self, a: object, b: object) -> None:
        strict = type(a) is type(b) and a == b
        self.assertEqual(ci_aggregate.same(a, b), strict)
        self.assertEqual(ci_aggregate.same({"k": a}, {"k": b}), strict)
        self.assertEqual(ci_aggregate.same({a: 0}, {b: 0}), strict)

    def test_unreadable_workflow_names_its_reason(self) -> None:
        status, out = self.verdict(GOOD, self.edited("jobs:\n", "jobs: [\n"))
        self.assertEqual(status, 1)
        self.assertTrue(out.startswith("FAIL workflow-unreadable: "), out)
        status, out = self.verdict(GOOD, WORKFLOW + ".absent")
        self.assertEqual(status, 1)
        self.assertTrue(out.startswith("FAIL workflow-unreadable: "), out)

    def test_cancelled_only_matrix_fails(self) -> None:
        needs = {**GOOD, "suite": {"result": plants.matrix_result(["cancelled"])}}
        self.assertEqual(
            self.verdict(needs),
            (1, "FAIL shard-result: suite: cancelled\nRESULT: FAILED\n"),
        )

    @given(
        st.lists(st.sampled_from([*NAMES, "web-extra", ""]), max_size=len(NAMES) + 2)
    )
    def test_matrix_passes_exactly_when_it_equals_the_table(
        self, matrix: list[str]
    ) -> None:
        self.assertEqual(ci_aggregate.matrix_problems(matrix) == [], matrix == NAMES)

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
        self.assertEqual(ci_aggregate.main([WORKFLOW, json.dumps(GOOD), "x"], out), 2)
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
            ("          - web-unit\n", "", "matrix-missing: web-unit"),
            (
                "      matrix:\n",
                "      matrix:\n        os: [ubuntu-24.04]\n",
                "matrix-keys: os",
            ),
            (
                "          - web-unit\n",
                "          - web-unit\n          - web-extra\n",
                "matrix-unexpected: web-extra",
            ),
            (
                "    needs: [suite, web-spikes]\n",
                "    needs: [suite]\n",
                "tests-needs: job tests does not need exactly suite, web-spikes",
            ),
            (
                "    if: ${{ always() }}\n",
                "    if: ${{ success() }}\n",
                "tests-condition: job tests does not always run",
            ),
            (
                f"run: {rules.AGGREGATE_RUN}",
                'run: uv run --locked python scripts/ci_aggregate.py "$NEEDS"',
                "step-missing: tests: " + ci_aggregate.AGGREGATE_NAME,
            ),
        )
        for old, new, reason in rows:
            with self.subTest(reason=reason, new=new):
                self.assertEqual(
                    self.planted(old, new),
                    [f"ci.yml: job suite {reason}"]
                    if "fail-fast" in reason
                    else [f"ci.yml: {reason}"],
                )

    def test_guard_shares_the_aggregate_shape_check(self) -> None:
        """An excluded suite fails the workflow guard with the aggregate's reason."""
        self.assertEqual(
            self.planted(
                "          - web-unit\n",
                "          - web-unit\n        exclude:\n          - suite: python-guards\n",
            ),
            ["ci.yml: matrix-keys: exclude"],
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
        workflow = self.root / plants.WORKFLOW
        workflow.parent.mkdir(parents=True)
        shutil.copy2(ci_support.WORKFLOW_DIR / "ci.yml", workflow)

    def test_matrix_result(self) -> None:
        self.assertEqual(plants.matrix_result([]), "failure")
        self.assertEqual(plants.matrix_result(["cancelled"]), "cancelled")
        self.assertEqual(plants.matrix_result(["success", "cancelled"]), "cancelled")
        self.assertEqual(plants.matrix_result(["success", "unknown"]), "failure")
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

    def test_dropped_or_excluded_suite_plant_fails_the_aggregate_alone(self) -> None:
        self.assertEqual(run_tests.SUITES[0].name, "python-guards")
        for check in (
            "tests-matrix-dropped",
            "tests-matrix-excluded",
            "tests-suite-env",
        ):
            with self.subTest(check=check):
                case = next(c for c in cases.CASES if c.check == check)
                shutil.copy2(
                    ci_support.WORKFLOW_DIR / "ci.yml", self.root / plants.WORKFLOW
                )
                cases.PLANTS["passing-shards"](self.root, support.parent_env())
                status, out = plants.run_shards(self.root, support.parent_env())
                self.assertEqual(status, 0, out)
                cases.PLANTS[case.plant](self.root, support.parent_env())
                status, out = plants.run_shards(self.root, support.parent_env())
                self.assertEqual(status, 1, out)
                self.assertIn(case.expect, out)
                self.assertEqual(out.count("FAIL "), 1, out)


if __name__ == "__main__":
    unittest.main()
