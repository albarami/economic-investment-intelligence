"""Deterministic native-trace grading, independently fixture-tested.

No traces are manufactured by the runner. Actual native capture and its prior
budget/identity proof remain external prerequisites. This reader cannot approve
hardware, an owner decision, or a held-out boundary from a JSON assertion.
"""

from __future__ import annotations

import json
import math
from collections import defaultdict
from collections.abc import Mapping
from typing import Any

from evals.question_lab.locks import compare_limits, digest
from evals.question_lab.oracles import percentile


def timing_report(
    evidence: Mapping[str, Any], raw_budget: bytes
) -> tuple[dict[str, Any], list[str]]:
    budgets = json.loads(raw_budget)
    problems = []
    if budgets.get("ratification") != "ratified":
        problems.append("timing:ratification")
    if evidence.get("budget_sha256") != digest(raw_budget):
        problems.append("timing:budget_identity")
    if evidence.get("budget_locked_before_start") is not True:
        problems.append("timing:prior_lock")
    devices: dict[str, list[dict[str, Any]]] = defaultdict(list)
    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    seen = set()
    measured, warmups = 0, 0
    for row in evidence.get("traces", []):
        device = row.get("device")
        declared = budgets.get("native_" + str(device))
        if (
            device not in {"stage", "phone"}
            or not isinstance(declared, str)
            or not declared
            or row.get("hardware") != declared
        ):
            problems.append("timing:device")
        if row.get("native") is not True or row.get("software_renderer") is not False:
            problems.append("timing:non_native")
        if not row.get("gpu") or not row.get("browser"):
            problems.append("timing:environment")
        if (
            row.get("data_ready") is not True
            or row.get("writer") != "template"
            or row.get("accounting_before_brief") is not True
        ):
            problems.append("timing:accounting")
        if row.get("request_id") in seen:
            problems.append("timing:duplicate_request")
        seen.add(row.get("request_id"))
        shift = row.get("layout_shift")
        if (
            type(shift) not in (float, int)
            or not math.isfinite(shift)
            or shift < 0
            or shift > budgets["layout_shift_max"]
        ):
            problems.append("timing:layout_shift")
        phase, language, temperature = (
            row.get("phase"),
            row.get("language"),
            row.get("temperature"),
        )
        valid_group = language in {"en", "ar"} and temperature in {"cold", "warm"}
        if not valid_group:
            problems.append("timing:group")
        prior = devices[str(device)]
        if phase == "warmup":
            warmups += 1
            if any(item.get("phase") == "measured" for item in prior):
                problems.append("timing:warmup_order")
        elif phase == "measured":
            measured += 1
            if valid_group:
                groups[(str(device), str(language), str(temperature))].append(row)
        else:
            problems.append("timing:phase")
        metrics = row.get("metrics_ms", {})
        if not isinstance(metrics, dict):
            problems.append("timing:invalid_samples")
            metrics = {}
        for metric in budgets["limits_ms"]:
            if metric not in metrics:
                problems.append(f"timing:missing_{metric}")
            elif not isinstance(metrics[metric], list):
                problems.append("timing:invalid_samples")
        prior.append(row)

    def samples_for(entries: list[dict[str, Any]], metric: str) -> list[Any]:
        samples: list[Any] = []
        for entry in entries:
            values = entry.get("metrics_ms", {})
            if not isinstance(values, dict) or not isinstance(values.get(metric), list):
                problems.append("timing:invalid_samples")
            else:
                samples.extend(values[metric])
        return samples

    summaries = []
    for device in ("stage", "phone"):
        entries = devices[device]
        if sum(item.get("phase") == "warmup" for item in entries) != 20:
            problems.append("timing:warmup_count")
        requests = [item for item in entries if item.get("phase") == "measured"]
        if len(requests) < 200:
            problems.append("timing:evidence_sample_count")
        samples = {
            metric: samples_for(requests, metric) for metric in budgets["limits_ms"]
        }
        try:
            _, failures = compare_limits(samples, raw_budget)
            problems.extend(failures)
        except (ValueError, TypeError):
            problems.append("timing:invalid_samples")
    for (device, language, temperature), entries in sorted(groups.items()):
        metrics = {}
        for metric, limits in budgets["limits_ms"].items():
            group_samples = samples_for(entries, metric)
            try:
                stats = percentile(group_samples)
                metrics[metric] = stats
                if stats["p95"] > limits["p95"] or (
                    limits.get("p95_strict") and stats["p95"] == limits["p95"]
                ):
                    problems.append(f"timing:{metric}_p95")
                if "worst" in limits and stats["worst"] > limits["worst"]:
                    problems.append(f"timing:{metric}_worst")
            except (ValueError, TypeError):
                problems.append("timing:invalid_samples")
        summaries.append(
            {
                "device": device,
                "language": language,
                "temperature": temperature,
                "requests": len(entries),
                "metrics": metrics,
            }
        )
    return {
        "measured_requests": measured,
        "warmups": warmups,
        "groups": summaries,
    }, sorted(set(problems))
