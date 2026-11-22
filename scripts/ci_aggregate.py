"""Judge the hosted `tests` check from the results of the jobs it needs.

Usage: ``ci_aggregate.py WORKFLOW [NEEDS_JSON]`` where WORKFLOW is the
checked-out ``ci.yml`` and NEEDS_JSON is the workflow expression
``toJSON(needs)``. Before it reads a result, the shape of WORKFLOW must hold:
job ``suite`` has one matrix axis, ``suite``, equal to the SUITES table, with no
``exclude``, ``include`` or other axis; jobs ``static-checks``, ``suite``,
``web-spikes`` and ``tests`` carry no ``continue-on-error``, condition, shell
default or other escape key, on the job or on a step, and each still runs its
own commands unchanged; job ``tests`` needs exactly ``suite`` and
``web-spikes`` and always runs. A suite dropped or excused fails here and not
only in the guard tests that suite runs. With WORKFLOW alone, only the shape is
judged: job ``static-checks`` runs that form, needs no job and so is never
skipped by a failed suite. A matrix job's result is ``success`` only when every
leg succeeded; a failed, cancelled or skipped job, a missing job or an extra job
fails the check.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import TextIO

import yaml

import run_tests

NEEDED = ("suite", "web-spikes")
USAGE = "usage: ci_aggregate.py WORKFLOW [NEEDS_JSON]"
NOT_A_LIST = "FAIL matrix-unreadable: the suite matrix is not a list of names"
NO_AXIS = "FAIL matrix-unreadable: the suite strategy matrix is not a mapping"
BASH = {"run": {"shell": "bash"}}
# Keys that let a job or a step pass, or not run, while its command failed.
JOB_KEYS = ("continue-on-error", "if", "needs", "defaults", "strategy")
STEP_KEYS = ("continue-on-error", "if", "shell")
ALLOWED_JOB_KEYS = {"suite": {"strategy"}, "tests": {"needs", "if"}}
SHAPE_NAME = "Check the suite matrix and the tests verdict"
SHAPE_RUN = "uv run --locked python scripts/ci_aggregate.py .github/workflows/ci.yml"
AGGREGATE_NAME = "Require the whole suite matrix and every needed job to succeed"
AGGREGATE_RUN = SHAPE_RUN + ' "$NEEDS"'
WEB = {"working-directory": "web"}
REQUIRED_STEPS: dict[str, tuple[dict[str, object], ...]] = {
    "static-checks": ({"name": SHAPE_NAME, "run": SHAPE_RUN},),
    "suite": (
        {
            "name": "Run one suite",
            "run": './eii test --seed 2026111201 --suite "$SUITE"',
            "env": {"SUITE": "${{ matrix.suite }}"},
        },
    ),
    "web-spikes": (
        {"name": "Check built hosts", "run": "npm run check:hosts:dist", **WEB},
        {"name": "Check the development server", "run": "npm run check:dev", **WEB},
        {
            "name": "Capture spike screenshots",
            "run": "npm run spike:glyphs:capture",
            **WEB,
        },
        {
            "name": "Compare spike screenshots",
            "run": "npm run test:spike:glyphs",
            **WEB,
        },
    ),
    "tests": (
        {
            "name": AGGREGATE_NAME,
            "run": AGGREGATE_RUN,
            "env": {"NEEDS": "${{ toJSON(needs) }}"},
        },
    ),
}


def matrix_problems(matrix: object) -> list[str]:
    """Return one FAIL line per difference between the matrix list and SUITES."""
    if not isinstance(matrix, list) or not all(isinstance(n, str) for n in matrix):
        return [NOT_A_LIST]
    if not matrix:
        return ["FAIL matrix-empty: the suite matrix lists no suite"]
    names = [suite.name for suite in run_tests.SUITES]
    found = [f"FAIL matrix-missing: {name}" for name in names if name not in matrix]
    found += [f"FAIL matrix-unexpected: {n}" for n in sorted(set(matrix) - set(names))]
    twice = sorted({name for name in matrix if matrix.count(name) > 1})
    found += [f"FAIL matrix-duplicate: {name}" for name in twice]
    if not found and matrix != names:
        found.append("FAIL matrix-order: the suite matrix is not in SUITES order")
    return found


def matrix_shape_problems(job: Mapping[str, object]) -> list[str]:
    """Require job ``suite``'s matrix to hold exactly the axis ``suite``."""
    strategy = job.get("strategy")
    matrix = strategy.get("matrix") if isinstance(strategy, dict) else None
    if not isinstance(matrix, dict):
        return [NO_AXIS]
    extra = sorted(str(key) for key in matrix if key != "suite")
    if extra:
        return [f"FAIL matrix-keys: {', '.join(extra)}"]
    return matrix_problems(matrix.get("suite"))


def job_problems(name: str, job: object) -> list[str]:
    """Refuse an escape key on job NAME or its steps, or a changed own command."""
    if not isinstance(job, dict):
        return [f"FAIL job-missing: {name}"]
    allowed = ALLOWED_JOB_KEYS.get(name, set())
    found = [
        f"FAIL job-key: {name}: {k}" for k in JOB_KEYS if k in job and k not in allowed
    ]
    steps = [step for step in job.get("steps") or [] if isinstance(step, dict)]
    for step in steps:
        label = f"{name}: {step.get('name')}"
        found += [f"FAIL step-key: {label}: {k}" for k in STEP_KEYS if k in step]
    for want in REQUIRED_STEPS[name]:
        if not any(all(s.get(k) == v for k, v in want.items()) for s in steps):
            found.append(f"FAIL step-missing: {name}: {want['name']}")
    return found


def tests_problems(job: Mapping[str, object]) -> list[str]:
    """Job ``tests`` always runs and needs exactly the aggregated jobs."""
    found: list[str] = []
    if job.get("if") != "${{ always() }}":
        found.append("FAIL tests-condition: job tests does not always run")
    if job.get("needs") != list(NEEDED):
        found.append(
            "FAIL tests-needs: job tests does not need exactly " + ", ".join(NEEDED)
        )
    return found


def shape_problems(document: object) -> list[str]:
    """Return one FAIL line per way the workflow could pass without a suite."""
    root = document if isinstance(document, dict) else {}
    found: list[str] = []
    if root.get("defaults") != BASH:
        found.append("FAIL workflow-defaults: the run shell is not bash")
    jobs = root.get("jobs")
    jobs = jobs if isinstance(jobs, dict) else {}
    for name in REQUIRED_STEPS:
        found += job_problems(name, jobs.get(name))
    if isinstance(jobs.get("suite"), dict):
        found += matrix_shape_problems(jobs["suite"])
    if isinstance(jobs.get("tests"), dict):
        found += tests_problems(jobs["tests"])
    return found


def workflow_problems(path: Path) -> list[str]:
    """Read WORKFLOW and judge its shape."""
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as error:
        return [f"FAIL workflow-unreadable: {type(error).__name__}"]
    return shape_problems(document)


def problems(text: str) -> list[str]:
    """Return one FAIL line per fault; an empty list means every job succeeded."""
    try:
        needs = json.loads(text)
    except json.JSONDecodeError as error:
        return [f"FAIL needs-unreadable: {error.msg}"]
    if not isinstance(needs, dict):
        return ["FAIL needs-unreadable: not a mapping of job results"]
    found: list[str] = []
    for job in sorted(set(NEEDED) - set(needs)):
        found.append(f"FAIL shard-missing: {job}")
    for job in sorted(set(needs) - set(NEEDED)):
        found.append(f"FAIL shard-unexpected: {job}")
    for job in NEEDED:
        entry = needs.get(job)
        if job not in needs:
            continue
        result = entry.get("result") if isinstance(entry, dict) else None
        if result != "success":
            found.append(f"FAIL shard-result: {job}: {result}")
    return found


def main(argv: Sequence[str], out: TextIO = sys.stdout) -> int:
    """Print the verdict: 0 when the shape holds and every given job succeeded."""
    if len(argv) not in (1, 2):
        print(USAGE, file=out)
        return 2
    found = workflow_problems(Path(argv[0]))
    if len(argv) == 2:
        found += problems(argv[1])
    for line in found:
        print(line, file=out)
    print("RESULT: " + ("FAILED" if found else "PASSED"), file=out)
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
