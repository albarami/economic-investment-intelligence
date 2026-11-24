"""Pre-run immutable budget identity and deterministic budget comparisons."""

from __future__ import annotations

import hashlib
import json
import math
import subprocess
from collections.abc import Mapping, Sequence
from itertools import pairwise
from pathlib import Path

from evals.question_lab.oracles import percentile

BUDGET = "evals/question_lab/budgets.v1.json"
MAX_P95 = {
    "map": 500,
    "chip": 2000,
    "brief": 6000,
    "interrupt": 500,
    "reset": 500,
    "flight_frame": 16.7,
    "evidence_bundle": 1500,
}
MAX_WORST = {
    "map": 1000,
    "chip": 3000,
    "brief": 8000,
    "interrupt": 1000,
    "reset": 1000,
    "flight_frame": 33,
}


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def git_text(root: Path, *args: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", *args], cwd=root, capture_output=True, check=False
        )
    except OSError:
        return None
    return result.stdout.decode().strip() if result.returncode == 0 else None


def budget_problems(raw: bytes, *, committed: bytes | None) -> list[str]:
    current = json.loads(raw)
    problems = []
    limits = current.get("limits_ms", {})
    if (
        set(limits) != set(MAX_P95)
        or any(
            not isinstance(limits[key], dict)
            or type(limits[key].get("p95")) not in (int, float)
            or not math.isfinite(limits[key]["p95"])
            or limits[key]["p95"] > bound
            or limits[key]["p95"] <= 0
            for key, bound in MAX_P95.items()
        )
        or any(
            not isinstance(limits[key], dict)
            or type(limits[key].get("worst")) not in (int, float)
            or not math.isfinite(limits[key]["worst"])
            or limits[key]["worst"] > bound
            or limits[key]["worst"] <= 0
            for key, bound in MAX_WORST.items()
        )
        or any(
            not isinstance(limits[key], dict)
            or limits[key].get("p95_strict") is not True
            for key in ("map", "evidence_bundle")
        )
        or current.get("max_actions") != 6
        or current.get("layout_shift_max") != 0.1
        or current.get("evidence_samples") != 200
        or current.get("warmups") != 20
    ):
        problems.append("budget:raised_or_invalid_limit")
    if committed is None:
        problems.append("budget:uncommitted")
    elif raw != committed:
        problems.append("budget:changed_since_commit")
    if current.get("ratification") != "ratified":
        problems.append("budget:ratification_waiting")
    for key in ("native_stage", "native_phone"):
        if not isinstance(current.get(key), str) or not current[key]:
            problems.append(f"budget:{key}_undeclared")
    return problems


def locked_budget(root: Path) -> tuple[bytes, list[str]]:
    raw = (root / BUDGET).read_bytes()
    committed = subprocess.run(
        ["git", "show", f"HEAD:{BUDGET}"], cwd=root, capture_output=True, check=False
    )
    problems = budget_problems(
        raw, committed=committed.stdout if committed.returncode == 0 else None
    )
    history = git_text(root, "log", "--format=%H", "--", BUDGET)
    if history:
        revisions = history.splitlines()
        for newer, older in pairwise(revisions):
            a = git_text(root, "show", f"{newer}:{BUDGET}")
            b = git_text(root, "show", f"{older}:{BUDGET}")
            if a is None or b is None:
                problems.append("budget:history_unavailable")
            else:
                problems.extend(no_loosening(a.encode(), b.encode()))
    return raw, sorted(set(problems))


def no_loosening(current: bytes, prior: bytes) -> list[str]:
    """Changing the head cannot erase a stricter previously committed limit."""
    now, before = json.loads(current), json.loads(prior)
    for metric, limits in before["limits_ms"].items():
        for name in ("p95", "worst"):
            if name in limits and (
                name not in now["limits_ms"].get(metric, {})
                or now["limits_ms"][metric][name] > limits[name]
            ):
                return ["budget:loosened_after_run"]
    return []


def compare_limits(
    samples: Mapping[str, Sequence[float]], budgets: bytes
) -> tuple[dict[str, object], list[str]]:
    """No trimming, warmup dropping, tolerance or bound changes."""
    limits = json.loads(budgets)["limits_ms"]
    report: dict[str, object] = {}
    problems = []
    for metric, limit in limits.items():
        if metric not in samples:
            problems.append(f"timing:missing_{metric}")
            continue
        summary = percentile(samples[metric])
        report[metric] = summary
        if summary["p95"] > limit["p95"] or (
            limit.get("p95_strict") and summary["p95"] == limit["p95"]
        ):
            problems.append(f"timing:{metric}_p95")
        if "worst" in limit and summary["worst"] > limit["worst"]:
            problems.append(f"timing:{metric}_worst")
        if metric == "evidence_bundle" and summary["count"] < 200:
            problems.append("timing:evidence_sample_count")
    return report, problems
