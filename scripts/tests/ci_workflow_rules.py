"""Closed required workflow shape for S0-T07 continuous integration."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_DIR = ROOT / ".github/workflows"
WORKFLOW_NAMES = frozenset({"ci.yml", "docs.yml", "sandbox.yml"})
# A workflow file change changes its pin in the same commit, so it is seen in review.
PINNED_SHA256 = {
    "ci.yml": "1fa31a3034a2d2ae6677d1ba95116b033fafe80ffa5c31be6cee3cc55777d45b",
    "docs.yml": "9c3ed0f74b8106e6797d5d010f9da20d4166d52a6f693d195a9920d0e95727a6",
    "sandbox.yml": "e33d0f21d42874da8d944d65b3824fff44ceaba4f17a538e06df9d8c087852e3",
}
RULES = (
    "workflow-files",
    "events-and-permissions",
    "required-jobs",
    "required-steps",
    "no-weakeners",
)
REQUIRED_CHECKS: tuple[tuple[str, str, str], ...] = (
    ("docs.yml", "check-docs", "check-docs"),
    ("ci.yml", "static-checks", "static-checks"),
    ("ci.yml", "tests", "tests"),
    ("ci.yml", "secret-scan", "secret-scan"),
    ("ci.yml", "planted-failures", "planted-failures"),
    ("sandbox.yml", "sandbox-proof", "sandbox proof"),
)
RUNNER = "ubuntu-24.04"
PIN_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+@[0-9a-f]{40}$")
FORBIDDEN_TOKENS = (
    "continue-on-error",
    "retry:",
    "needs:",
    "workflow_dispatch",
    "schedule:",
    "paths:",
    "paths-ignore:",
)
RUN_WEAKENERS = ("|| true", "set +e", "||true")
SCANNER_FETCH = "uv run --locked python scripts/hooks_gitleaks.py fetch"

_WEAKENER_STEP_RE = re.compile(r"(?m)^\s*continue-on-error:\s*true\s*$")


def _strip_action_ref(value: str) -> str:
    return value.split("#", 1)[0].strip()


def _norm_step(step: object) -> tuple[object, ...]:
    if not isinstance(step, dict):
        return ("invalid", step)
    name = step.get("name")
    if "uses" in step:
        with_block = step.get("with") or {}
        if not isinstance(with_block, dict):
            with_block = {}
        items = tuple(sorted((str(k), str(v)) for k, v in with_block.items()))
        return ("uses", name, _strip_action_ref(str(step["uses"])), items)
    if "run" in step:
        wd = step.get("working-directory")
        return ("run", name, str(step["run"]).strip(), wd)
    return ("unknown", name, tuple(sorted(step.items())))


def _norm_job(job: dict[str, Any]) -> dict[str, object]:
    steps = job.get("steps") or []
    return {
        "name": job.get("name"),
        "runs-on": job.get("runs-on"),
        "timeout-minutes": job.get("timeout-minutes"),
        "steps": tuple(_norm_step(step) for step in steps),
    }


def _parse_workflow(text: str) -> Any:
    """Parse workflow YAML without treating the ``on`` key as boolean true."""
    fixed = re.sub(r"(?m)^on:\s*$", '"on":', text, count=1)
    return yaml.safe_load(fixed)


def _load_workflows(workflows_dir: Path) -> dict[str, Any] | None:
    documents: dict[str, Any] = {}
    for name in sorted(WORKFLOW_NAMES):
        path = workflows_dir / name
        if not path.is_file():
            return None
        try:
            documents[name] = _parse_workflow(path.read_text(encoding="utf-8"))
        except yaml.YAMLError:
            return None
    return documents


def _reference_workflows() -> dict[str, Any]:
    """Load job diagnostics; PINNED_SHA256 defines the closed text reference."""
    return _load_workflows(WORKFLOW_DIR) or {}


def pinned_text_problems(workflows_dir: Path) -> list[str]:
    """Refuse missing workflow files or bytes differing from the closed pins."""
    problems: list[str] = []
    for name in sorted(WORKFLOW_NAMES):
        path = workflows_dir / name
        if not path.is_file():
            problems.append(f"{name}: pinned workflow file is missing")
        elif hashlib.sha256(path.read_bytes()).hexdigest() != PINNED_SHA256[name]:
            problems.append(f"{name}: workflow text differs from its pin")
    return problems


def check_workflow_files(workflows_dir: Path) -> list[str]:
    """Rule 1: exactly three workflow files exist."""
    if not workflows_dir.is_dir():
        return ["workflows directory is missing"]
    found = {path.name for path in workflows_dir.glob("*.yml")}
    extra = sorted(found - WORKFLOW_NAMES)
    missing = sorted(WORKFLOW_NAMES - found)
    problems: list[str] = []
    if extra:
        problems.append(f"unexpected workflow files: {', '.join(extra)}")
    if missing:
        problems.append(f"missing workflow files: {', '.join(missing)}")
    return problems


def check_events_and_permissions(
    workflows: dict[str, Any], raw_texts: dict[str, str]
) -> list[str]:
    """Rule 2: pull requests, push to main, contents read."""
    problems: list[str] = []
    for name, document in workflows.items():
        text = raw_texts[name]
        if not isinstance(document, dict):
            problems.append(f"{name}: workflow is not a mapping")
            continue
        trigger = document.get("on") or {}
        if not isinstance(trigger, dict):
            problems.append(f"{name}: on-trigger is not a mapping")
            continue
        if "pull_request" not in trigger:
            problems.append(f"{name}: missing pull_request trigger")
        push = trigger.get("push")
        if not isinstance(push, dict) or push.get("branches") != ["main"]:
            problems.append(f"{name}: push to main is missing")
        permissions = document.get("permissions")
        if permissions != {"contents": "read"}:
            problems.append(f"{name}: permissions are not exactly contents read")
        if name in {"ci.yml", "docs.yml"}:
            defaults = document.get("defaults") or {}
            run = defaults.get("run") if isinstance(defaults, dict) else None
            if not isinstance(run, dict) or run.get("shell") != "bash":
                problems.append(f"{name}: defaults.run.shell is not bash")
        if not re.search(r"(?m)^permissions:\n  contents: read\n", text):
            problems.append(f"{name}: permissions block shape differs")
    return problems


def check_required_jobs(workflows: dict[str, Any]) -> list[str]:
    """Rule 3: six required jobs with exact ids, names and runner."""
    problems: list[str] = []
    seen: list[tuple[str, str, str]] = []
    for filename, job_id, display in REQUIRED_CHECKS:
        document = workflows.get(filename)
        if not isinstance(document, dict):
            problems.append(f"{filename}: missing workflow")
            continue
        jobs = document.get("jobs")
        if not isinstance(jobs, dict):
            problems.append(f"{filename}: jobs block is missing")
            continue
        job = jobs.get(job_id)
        if not isinstance(job, dict):
            problems.append(f"{filename}: job {job_id} is missing")
            continue
        if job.get("name") != display:
            problems.append(
                f"{filename}: job {job_id} name is {job.get('name')!r}, not {display!r}"
            )
        if job.get("runs-on") != RUNNER:
            problems.append(f"{filename}: job {job_id} runs-on is not {RUNNER}")
        if "timeout-minutes" not in job:
            problems.append(f"{filename}: job {job_id} has no timeout-minutes")
        seen.append((filename, job_id, display))
    if len(seen) != len(REQUIRED_CHECKS):
        problems.append("required job count differs")
    return problems


def check_required_steps(
    workflows: dict[str, Any], reference: dict[str, Any]
) -> list[str]:
    """Rule 4 job diagnostics; the closed reference is text pinned by SHA-256."""
    problems: list[str] = []
    for filename in WORKFLOW_NAMES:
        document = workflows.get(filename)
        reference_doc = reference.get(filename)
        if not isinstance(document, dict) or not isinstance(reference_doc, dict):
            continue
        jobs = document.get("jobs")
        ref_jobs = reference_doc.get("jobs")
        if not isinstance(jobs, dict) or not isinstance(ref_jobs, dict):
            problems.append(f"{filename}: jobs block is missing")
            continue
        for job_id, job in jobs.items():
            if not isinstance(job, dict):
                continue
            ref_job = ref_jobs.get(job_id)
            if not isinstance(ref_job, dict):
                problems.append(f"{filename}: unexpected job {job_id}")
                continue
            if _norm_job(job) != _norm_job(ref_job):
                problems.append(f"{filename}: job {job_id} steps differ")
        for job_id in ref_jobs:
            if job_id not in jobs:
                problems.append(f"{filename}: missing job {job_id}")
    problems.extend(_checkout_pins(workflows))
    problems.extend(_scanner_before_tests(workflows))
    return problems


def _checkout_pins(workflows: dict[str, Any]) -> list[str]:
    """Require full history on the secret-scan checkout and no persisted credentials."""
    problems: list[str] = []
    ci = workflows.get("ci.yml")
    if not isinstance(ci, dict):
        return problems
    jobs = ci.get("jobs")
    if not isinstance(jobs, dict):
        return problems
    secret = jobs.get("secret-scan")
    if isinstance(secret, dict):
        steps = secret.get("steps") or []
        history = False
        for step in steps:
            if not isinstance(step, dict):
                continue
            uses = step.get("uses", "")
            if "actions/checkout@" in str(uses):
                with_block = step.get("with") or {}
                if (
                    isinstance(with_block, dict)
                    and with_block.get("fetch-depth") == 0
                    and with_block.get("persist-credentials") is False
                ):
                    history = True
        if not history:
            problems.append("ci.yml: secret-scan checkout lacks fetch-depth 0")
    for filename, document in workflows.items():
        if not isinstance(document, dict):
            continue
        jobs = document.get("jobs")
        if not isinstance(jobs, dict):
            continue
        for job_id, job in jobs.items():
            if not isinstance(job, dict):
                continue
            for step in job.get("steps") or []:
                if not isinstance(step, dict):
                    continue
                uses = step.get("uses", "")
                if "actions/checkout@" in str(uses):
                    with_block = step.get("with") or {}
                    if isinstance(with_block, dict):
                        if with_block.get("persist-credentials") is not False:
                            problems.append(
                                f"{filename}: job {job_id} checkout persists credentials"
                            )
                    action = _strip_action_ref(str(uses))
                    if not PIN_RE.match(action):
                        problems.append(
                            f"{filename}: job {job_id} checkout action not pinned"
                        )
    return problems


def _scanner_before_tests(workflows: dict[str, Any]) -> list[str]:
    """Jobs that run the full test suite must fetch the scanner first."""
    problems: list[str] = []
    ci = workflows.get("ci.yml")
    if not isinstance(ci, dict):
        return problems
    jobs = ci.get("jobs")
    if not isinstance(jobs, dict):
        return problems
    for job_id in ("tests", "planted-failures"):
        job = jobs.get(job_id)
        if not isinstance(job, dict):
            continue
        runs = [
            step.get("run") for step in job.get("steps") or [] if isinstance(step, dict)
        ]
        runs = [str(item).strip() for item in runs if item]
        if SCANNER_FETCH not in runs:
            problems.append(f"ci.yml: job {job_id} does not fetch the scanner")
            continue
        test_markers = ("./eii test", "ci_plants.py run")
        saw_fetch = False
        for command in runs:
            if not command:
                continue
            if any(marker in command for marker in test_markers):
                if not saw_fetch:
                    problems.append(
                        f"ci.yml: job {job_id} runs tests before fetching the scanner"
                    )
                    break
            if command == SCANNER_FETCH:
                saw_fetch = True
    return problems


def check_no_weakeners(raw_texts: dict[str, str]) -> list[str]:
    """Rule 5: refuse continue-on-error, retries, conditions and softened commands."""
    problems: list[str] = []
    for name, text in raw_texts.items():
        for token in FORBIDDEN_TOKENS:
            if token in text:
                problems.append(f"{name}: forbidden token {token!r}")
        if _WEAKENER_STEP_RE.search(text):
            problems.append(f"{name}: continue-on-error on a step")
        if re.search(r"(?m)^\s*if:\s*", text):
            problems.append(f"{name}: step or job condition")
        for token in RUN_WEAKENERS:
            if token in text:
                problems.append(f"{name}: softened run command {token!r}")
        for value in re.findall(r"(?m)^\s*(?:- )?uses:\s*(\S+)", text):
            action = _strip_action_ref(value)
            if not PIN_RE.match(action):
                problems.append(f"{name}: action not pinned by commit: {action}")
    return problems


def rule_problems(
    rule: str, workflows_dir: Path, reference: dict[str, Any] | None = None
) -> list[str]:
    """Return problems for one named rule."""
    ref = reference if reference is not None else _reference_workflows()
    if rule == "workflow-files":
        return check_workflow_files(workflows_dir)
    pinned = pinned_text_problems(workflows_dir) if rule == "required-steps" else []
    workflows = _load_workflows(workflows_dir)
    if workflows is None:
        return [*pinned, "workflow files are missing or not valid YAML"]
    raw_texts = {
        name: (workflows_dir / name).read_text(encoding="utf-8")
        for name in WORKFLOW_NAMES
    }
    if rule == "events-and-permissions":
        return check_events_and_permissions(workflows, raw_texts)
    if rule == "required-jobs":
        return check_required_jobs(workflows)
    if rule == "required-steps":
        return [*pinned, *check_required_steps(workflows, ref)]
    if rule == "no-weakeners":
        return check_no_weakeners(raw_texts)
    return [f"unknown rule {rule!r}"]


def validate(workflows_dir: Path) -> list[str]:
    """Return every problem, prefixed by rule name, in rule order."""
    reference = _reference_workflows()
    problems: list[str] = []
    for rule in RULES:
        for item in rule_problems(rule, workflows_dir, reference):
            problems.append(f"{rule}: {item}")
    return problems


def required_check_names() -> list[str]:
    """Return the six required hosted check names in table order."""
    return [display for _file, _job, display in REQUIRED_CHECKS]


def sandbox_unchanged(workflows_dir: Path) -> list[str]:
    """Return problems when sandbox.yml differs from the S0-T07 reference."""
    path = workflows_dir / "sandbox.yml"
    if not path.is_file():
        return ["sandbox.yml is missing"]
    if hashlib.sha256(path.read_bytes()).hexdigest() != PINNED_SHA256["sandbox.yml"]:
        return ["sandbox.yml changed from the S0-T07 reference"]
    return []


def pin_commit_hashes() -> frozenset[str]:
    """Return the pinned action commit hashes used in the closed workflows."""
    hashes: set[str] = set()
    for text in (
        (WORKFLOW_DIR / name).read_text(encoding="utf-8") for name in WORKFLOW_NAMES
    ):
        for match in re.findall(r"@[0-9a-f]{40}", text):
            hashes.add(match[1:])
    return frozenset(hashes)
