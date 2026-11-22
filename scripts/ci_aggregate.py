"""Judge the hosted `tests` check from the results of the jobs it needs.

Usage: ``ci_aggregate.py WORKFLOW [NEEDS_JSON]`` where WORKFLOW is the
checked-out ``ci.yml`` and NEEDS_JSON is the workflow expression
``toJSON(needs)``. Before it reads a result, the shape of WORKFLOW must hold,
as an exact allow-list, not a deny-list: the workflow root holds only its
declared keys, ``contents: read``, the bash run shell and no ``env``; jobs
``static-checks``, ``suite``, ``web-spikes`` and ``tests`` hold only their
declared keys and values and no ``env``, and their steps equal the declared
sequence of JOB_STEPS key for key, each step's ``env`` equal to its declared
mapping, every value matched by type, a null variable present, not absent; job ``suite`` has one matrix axis, ``suite``, equal to the SUITES
table, under ``fail-fast: false`` alone; job ``tests`` needs exactly ``suite``
and ``web-spikes`` and always runs. So no inherited variable such as
``SHELLOPTS: noexec``, added step, key or changed setup step can stop a suite
from running while the check stays green. A suite dropped or excused fails here and not
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
PERMISSIONS = {"contents": "read"}
# Exact allow-lists: a key, step or variable not declared here is refused.
ROOT_KEYS = ("name", True, "on", "permissions", "defaults", "jobs", "env")
SHAPE_NAME = "Check the suite matrix and the tests verdict"
SHAPE_RUN = "uv run --locked python scripts/ci_aggregate.py .github/workflows/ci.yml"
AGGREGATE_NAME = "Require the whole suite matrix and every needed job to succeed"
AGGREGATE_RUN = SHAPE_RUN + ' "$NEEDS"'
Step = dict[str, object]


def run(name: str, command: str, folder: str | None = None) -> Step:
    """Declare one ``run`` step, in folder ``web`` when FOLDER is given."""
    step: Step = {"name": name, "run": command}
    return {**step, "working-directory": folder} if folder else step


def uses(name: str, action: str, /, **with_: object) -> Step:
    """Declare one pinned action step with exactly its ``with`` inputs."""
    return {"name": name, "uses": action, "with": with_}


UV = "uv run --locked python scripts/"
CHECKOUT = uses(
    "Check out",
    "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1",
    **{"persist-credentials": False},
)
SETUP_UV = uses(
    "Install uv",
    "astral-sh/setup-uv@68559e99cc807c1eb7e9238fd43a15bba460eec2",
    version="0.11.31",
    **{"enable-cache": "false"},
)
SETUP = (
    CHECKOUT,
    SETUP_UV,
    run("Install Python from .python-version", "uv python install"),
    uses(
        "Install Node from .nvmrc",
        "actions/setup-node@949feb2413d6458794dcd2491c4babbbce0c15c1",
        **{"node-version-file": ".nvmrc", "package-manager-cache": False},
    ),
    run(
        "Sync the locked environment with the engine group",
        "uv sync --managed-python --all-packages --locked --group engine",
    ),
)
SANDBOX = (
    run(
        "Install bubblewrap and AppArmor profiles",
        "sudo apt-get update && sudo apt-get install -y --no-install-recommends"
        " bubblewrap apparmor-profiles",
    ),
    run("Print runner facts", UV + "ci_sandbox.py facts"),
    run(
        "Make namespace creation work for bubblewrap",
        UV + "ci_sandbox.py install-profile",
    ),
    run("Fetch engine extensions", UV + "engine_extensions.py fetch"),
    run("Fetch the secret scanner", UV + "hooks_gitleaks.py fetch"),
    run("Install web dependencies", "npm ci", "web"),
    run("Build the web application", "npm run build", "web"),
)
BROWSER = run(
    "Install the spike browser", "npm run spike:glyphs:install-browser", "web"
)
SUITE_STEP = {
    **run("Run one suite", './eii test --seed 2026111201 --suite "$SUITE"'),
    "env": {"SUITE": "${{ matrix.suite }}"},
}
AGGREGATE_STEP = {
    **run(AGGREGATE_NAME, AGGREGATE_RUN),
    "env": {"NEEDS": "${{ toJSON(needs) }}"},
}
# The declared step sequence of each protected job, every key and value.
JOB_STEPS: dict[str, tuple[Step, ...]] = {
    "static-checks": (
        *SETUP,
        run(
            "Print tool versions",
            "uv --version && node --version && npm --version && git --version",
        ),
        run("Check the tree", "uv run --no-project python3 scripts/check_tree.py"),
        run("Check the lock", "uv lock --check"),
        run("Check versions", UV + "check_versions.py"),
        run("Check reference notes", UV + "check_reference_notes.py"),
        run("Check Python lint", "uv run --locked ruff check ."),
        run("Check Python format", "uv run --locked ruff format --check ."),
        run("Check Python types", "uv run --locked mypy"),
        run(SHAPE_NAME, SHAPE_RUN),
        run("Install web dependencies", "npm ci", "web"),
        run("Check web structure", "npm run check", "web"),
        run("Check web lint", "npm run lint", "web"),
        run("Check web format", "npm run format:check", "web"),
        run("Check web types", "npm run typecheck", "web"),
    ),
    "suite": (*SETUP, *SANDBOX, BROWSER, SUITE_STEP),
    "web-spikes": (
        *SETUP,
        *SANDBOX,
        run("Check built hosts", "npm run check:hosts:dist", "web"),
        run("Check the development server", "npm run check:dev", "web"),
        BROWSER,
        run("Capture spike screenshots", "npm run spike:glyphs:capture", "web"),
        uses(
            "Upload spike screenshots",
            "actions/upload-artifact@cf430e030ddbb5b0abf93d22962f4752f3646cd9",
            name="spike-glyph-screenshots",
            path="data/glyph-captures/",
            **{"if-no-files-found": "error"},
        ),
        run("Compare spike screenshots", "npm run test:spike:glyphs", "web"),
    ),
    "tests": (*SETUP[:3], AGGREGATE_STEP),
}
# The declared job keys with their values; strategy, needs and if are judged
# by matrix_shape_problems and tests_problems, steps by step_problems.
RUNNER = "ubuntu-24.04"
JOB_VALUES: dict[str, dict[str, object]] = {
    name: {"name": name, "runs-on": RUNNER, "timeout-minutes": minutes}
    for name, minutes in (
        ("static-checks", 25),
        ("suite", 90),
        ("web-spikes", 45),
        ("tests", 10),
    )
}
JUDGED_ELSEWHERE = {"suite": {"strategy"}, "tests": {"needs", "if"}}
STRATEGY_REST = {"fail-fast": False}


def same(got: object, want: object) -> bool:
    """Equal by type as well as value, so 0 never matches false nor 1.0 one."""
    if type(got) is not type(want):
        return False
    if isinstance(got, dict) and isinstance(want, dict):
        keys = {(type(k), k) for k in got}
        return keys == {(type(k), k) for k in want} and all(
            same(got[k], want[k]) for k in got
        )
    return got == want


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
    if not isinstance(strategy, dict) or not isinstance(matrix, dict):
        return [NO_AXIS]
    rest = {key: value for key, value in strategy.items() if key != "matrix"}
    if not same(rest, STRATEGY_REST):
        return ["FAIL strategy-keys: the suite strategy is not fail-fast false alone"]
    extra = sorted(str(key) for key in matrix if key != "suite")
    if extra:
        return [f"FAIL matrix-keys: {', '.join(extra)}"]
    return matrix_problems(matrix.get("suite"))


def env_problems(label: str, env: object, want: Mapping[str, object]) -> list[str]:
    """Refuse an ``env`` that adds, changes or drops a variable of WANT.

    A key present with a null value is present: it never matches an absent one.
    """
    if not isinstance(env, dict):
        return [f"FAIL {label}: not a mapping"]
    bad = [k for k in env if k not in want or not same(env[k], want[k])]
    bad += [k for k in want if k not in env]
    return [f"FAIL {label}: {k}" for k in sorted({str(k) for k in bad})]


def step_problems(name: str, steps: list[object]) -> list[str]:
    """The job's steps equal the declared sequence, key for key."""
    declared = JOB_STEPS[name]
    want_names = [str(step["name"]) for step in declared]
    got = [step if isinstance(step, dict) else {} for step in steps]
    got_names = [str(step.get("name")) for step in got]
    found = [
        f"FAIL step-missing: {name}: {n}" for n in want_names if n not in got_names
    ]
    extra = [n for i, n in enumerate(got_names) if n not in got_names[:i] + want_names]
    extra += sorted({n for n in got_names if got_names.count(n) > 1})
    found += [f"FAIL step-extra: {name}: {n}" for n in extra]
    if not found and got_names != want_names:
        found.append(f"FAIL step-order: {name}: the steps are not in declared order")
    for want in declared:
        step = next((s for s in got if s.get("name") == want["name"]), None)
        if step is None:
            continue
        label = f"{name}: {want['name']}"
        found += [
            f"FAIL step-key: {label}: {k}" for k in step if k not in {*want, "env"}
        ]
        env = want.get("env")
        env = env if isinstance(env, dict) else {}
        found += env_problems(f"step-env: {label}", step.get("env", {}), env)
        if any(not same(step.get(k), v) for k, v in want.items() if k != "env"):
            found.append(f"FAIL step-missing: {label}")
    return found


def job_problems(name: str, job: object) -> list[str]:
    """Job NAME holds exactly its declared keys, values, environment and steps."""
    if not isinstance(job, dict):
        return [f"FAIL job-missing: {name}"]
    allowed = {*JOB_VALUES[name], *JUDGED_ELSEWHERE.get(name, ()), "steps", "env"}
    found = [f"FAIL job-key: {name}: {k}" for k in job if k not in allowed]
    found += [
        f"FAIL job-value: {name}: {k}"
        for k, v in JOB_VALUES[name].items()
        if not same(job.get(k), v)
    ]
    found += env_problems(f"job-env: {name}", job.get("env", {}), {})
    steps = job.get("steps")
    return found + step_problems(name, steps if isinstance(steps, list) else [])


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


def root_problems(root: Mapping[object, object]) -> list[str]:
    """The workflow root holds exactly its declared keys and no environment."""
    found = [
        f"FAIL workflow-key: {k}"
        for k in root
        if not any(same(k, key) for key in ROOT_KEYS)
    ]
    found += env_problems("workflow-env", root.get("env", {}), {})
    if root.get("permissions") != PERMISSIONS:
        found.append("FAIL workflow-permissions: not contents read alone")
    if root.get("defaults") != BASH:
        found.append("FAIL workflow-defaults: the run shell is not bash")
    return found


def shape_problems(document: object) -> list[str]:
    """Return one FAIL line per way the workflow could pass without a suite."""
    root = document if isinstance(document, dict) else {}
    found = root_problems(root)
    jobs = root.get("jobs")
    jobs = jobs if isinstance(jobs, dict) else {}
    for name in JOB_STEPS:
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
