"""Invented timing traces exercise the native-evidence reader, not devices."""

from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import pytest

# Match the offline eval tests under the runner's safe-path Python.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from evals.question_lab.timing import timing_report

ROOT = Path(__file__).resolve().parents[2]


def fixture() -> tuple[dict[str, Any], bytes]:
    budgets = json.loads((ROOT / "evals/question_lab/budgets.v1.json").read_text())
    budgets.update(
        ratification="ratified",
        native_stage="INVENTED-stage",
        native_phone="INVENTED-phone",
    )
    raw = json.dumps(budgets).encode()
    traces = []
    for device in ("stage", "phone"):
        for index in range(220):
            traces.append(
                {
                    "device": device,
                    "hardware": budgets["native_" + device],
                    "gpu": "INVENTED-native-gpu",
                    "browser": "INVENTED-browser-build",
                    "native": True,
                    "software_renderer": False,
                    "language": "en" if index % 2 else "ar",
                    "temperature": "warm",
                    "phase": "warmup" if index < 20 else "measured",
                    "request_id": f"INVENTED-request-{device}-{index}",
                    "pin": [index / 1000, index / 1000],
                    "data_ready": True,
                    "writer": "template",
                    "accounting_before_brief": True,
                    "layout_shift": 0.01,
                    "metrics_ms": {key: [10.0] for key in budgets["limits_ms"]},
                }
            )
    return {
        "budget_sha256": hashlib.sha256(raw).hexdigest(),
        "budget_locked_before_start": True,
        "traces": traces,
    }, raw


def test_timing_groups_keep_all_measured_samples_and_native_metadata() -> None:
    evidence, raw = fixture()
    report, problems = timing_report(evidence, raw)
    assert problems == []
    assert report["measured_requests"] == 400
    assert report["warmups"] == 40
    assert len(report["groups"]) == 4
    for group in report["groups"]:
        assert group["metrics"]["map"] == {
            "count": 100,
            "p50": 10.0,
            "p95": 10.0,
            "worst": 10.0,
        }


@pytest.mark.parametrize(
    "plant,diagnostic",
    [
        ("software", "timing:non_native"),
        ("device", "timing:device"),
        ("lock", "timing:prior_lock"),
        ("hash", "timing:budget_identity"),
        ("warmup_failure", "timing:accounting"),
        ("short", "timing:evidence_sample_count"),
        ("late_warmup", "timing:warmup_order"),
        ("shift", "timing:layout_shift"),
        ("bound", "timing:map_p95"),
        ("worst", "timing:map_worst"),
        ("missing", "timing:missing_chip"),
        ("duplicate", "timing:duplicate_request"),
    ],
)
def test_native_protocol_plants_fail_intended_guard(
    plant: str, diagnostic: str
) -> None:
    evidence, raw = fixture()
    evidence = copy.deepcopy(evidence)
    row = evidence["traces"][30]
    if plant == "software":
        row["software_renderer"] = True
    elif plant == "device":
        row["hardware"] = "INVENTED-other"
    elif plant == "lock":
        evidence["budget_locked_before_start"] = False
    elif plant == "hash":
        evidence["budget_sha256"] = "bc" * 32
    elif plant == "warmup_failure":
        evidence["traces"][0]["accounting_before_brief"] = False
    elif plant == "short":
        evidence["traces"].pop(30)
    elif plant == "late_warmup":
        row["phase"] = "warmup"
    elif plant == "shift":
        row["layout_shift"] = 0.11
    elif plant == "bound":
        for item in evidence["traces"]:
            item["metrics_ms"]["map"] = [500.0]
    elif plant == "worst":
        row["metrics_ms"]["map"] = [1001.0]
    elif plant == "missing":
        del row["metrics_ms"]["chip"]
    else:
        evidence["traces"].append(row)
    assert diagnostic in timing_report(evidence, raw)[1]


def test_unratified_budget_and_null_hardware_cannot_qualify() -> None:
    evidence, _ = fixture()
    raw = (ROOT / "evals/question_lab/budgets.v1.json").read_bytes()
    evidence["budget_sha256"] = hashlib.sha256(raw).hexdigest()
    for row in evidence["traces"]:
        row["hardware"] = None
    problems = timing_report(evidence, raw)[1]
    assert "timing:device" in problems
    assert "timing:ratification" in problems


@pytest.mark.parametrize("field", ["language", "phase", "temperature"])
def test_missing_trace_group_field_is_a_named_refusal(field: str) -> None:
    evidence, raw = fixture()
    del evidence["traces"][30][field]
    report, problems = timing_report(evidence, raw)
    assert ("timing:phase" if field == "phase" else "timing:group") in problems
    assert sum(group["requests"] for group in report["groups"]) == 399


@pytest.mark.parametrize("samples", [10.0, None, "INVENTED-invalid", {"sample": 10.0}])
def test_non_list_metric_samples_are_a_named_refusal(samples: Any) -> None:
    evidence, raw = fixture()
    evidence["traces"][30]["metrics_ms"]["map"] = samples
    assert "timing:invalid_samples" in timing_report(evidence, raw)[1]
