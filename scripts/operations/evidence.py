"""Closed operation requests and candidate-bound offline promotion evidence."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from operations.common import Refusal

CHECKS = frozenset(
    {
        "check-docs",
        "static-checks",
        "tests",
        "secret-scan",
        "planted-failures",
        "sandbox proof",
    }
)
ITEMS = frozenset(
    {"merged", "review", "whole_test", "staging", "retention", "features", "gates"}
)
OPERATIONS = frozenset(
    {
        "start_staging",
        "initial_live_activation",
        "restart",
        "promote",
        "rollback",
        "expose_public",
    }
)
FIELDS = frozenset(
    {
        "operation",
        "environment",
        "exposure",
        "release_kind",
        "code_version",
        "release_id",
        "application_sha256",
        "previous_release_id",
        "entry_port",
        "backend_port",
        "evidence",
        "gate_approval",
        "actor",
    }
)
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
HEX40 = re.compile(r"[0-9a-f]{40}\Z")


def reference_shape(value: object) -> bool:
    return (
        type(value) is dict
        and set(value) == {"file", "sha256"}
        and type(value["file"]) is str
        and type(value["sha256"]) is str
        and HEX64.fullmatch(value["sha256"]) is not None
    )


def operation(value: Mapping[str, Any]) -> dict[str, Any]:
    if (
        set(value) != FIELDS
        or any(
            type(value.get(key)) is not str
            for key in (
                "operation",
                "environment",
                "exposure",
                "actor",
                "release_kind",
                "code_version",
                "release_id",
                "application_sha256",
            )
        )
        or value.get("operation") not in OPERATIONS
        or value.get("environment") not in {"live", "staging"}
        or value.get("exposure") not in {"loopback", "public_entry"}
        or value.get("actor") not in {"lead", "operator"}
        or value.get("release_kind") not in {"public_only", "protected"}
        or not HEX40.fullmatch(str(value.get("code_version", "")))
        or any(
            not HEX64.fullmatch(str(value.get(key, "")))
            for key in ("release_id", "application_sha256")
        )
        or (
            value.get("previous_release_id") is not None
            and (
                type(value["previous_release_id"]) is not str
                or not HEX64.fullmatch(value["previous_release_id"])
            )
        )
        or any(
            type(value.get(key)) is not int or not 1 <= value[key] <= 65535
            for key in ("entry_port", "backend_port")
        )
        or type(value.get("evidence")) is not dict
        or set(value["evidence"]) - ITEMS
        or any(not reference_shape(ref) for ref in value["evidence"].values())
        or (
            value.get("gate_approval") is not None
            and not reference_shape(value["gate_approval"])
        )
    ):
        raise Refusal("operation_schema_invalid")
    if value["release_kind"] != "public_only":
        raise Refusal("protected_release_requires_s11_t09")
    if value["environment"] == "staging" and value["operation"] not in {
        "start_staging",
        "restart",
    }:
        raise Refusal("operation_schema_invalid")
    if value["environment"] == "live" and value["operation"] == "start_staging":
        raise Refusal("operation_schema_invalid")
    if value["environment"] == "staging" and value["exposure"] != "loopback":
        raise Refusal("operation_schema_invalid")
    if (
        value["environment"] == "live"
        and value["operation"]
        in {"initial_live_activation", "promote", "rollback", "expose_public"}
        and value["actor"] != "lead"
    ):
        raise Refusal("activation_lead_required")
    return dict(value)


def require_reference_shape(reference: object, reason: str) -> None:
    if not reference_shape(reference):
        raise Refusal(reason)


def read_evidence_bytes(path: Path, reason: str) -> bytes:
    """Read once; hash and decode this same byte string, never reopen it."""
    try:
        return path.read_bytes()
    except OSError:
        raise Refusal(reason) from None


def referenced(root: Path, reference: object, reason: str) -> dict[str, Any]:
    require_reference_shape(reference, reason)
    assert isinstance(reference, dict)
    path = root / reference["file"]
    if (
        Path(reference["file"]).is_absolute()
        or ".." in Path(reference["file"]).parts
        or not path.resolve().is_relative_to(root.resolve())
        or path.is_symlink()
    ):
        raise Refusal(reason)
    payload = read_evidence_bytes(path, reason)
    if hashlib.sha256(payload).hexdigest() != reference["sha256"]:
        raise Refusal(reason)
    try:
        report = json.loads(payload)
    except (ValueError, UnicodeError):
        raise Refusal(reason) from None
    if type(report) is not dict:
        raise Refusal(reason)
    return report


def bound(report: Mapping[str, Any], request: Mapping[str, Any]) -> bool:
    return all(
        report.get(key) == request[key]
        for key in ("code_version", "release_id", "application_sha256")
    )


def exposure(
    root: Path, request: Mapping[str, Any], handover: Callable[[], None] | None = None
) -> None:
    if request["exposure"] == "loopback":
        return
    gate = referenced(root, request["gate_approval"], "public_gate_approval_required")
    if (
        not bound(gate, request)
        or gate.get("verdict") != "APPROVED"
        or gate.get("gate") != "S3"
    ):
        raise Refusal("public_gate_approval_required")
    if request["operation"] != "expose_public" or request["actor"] != "lead":
        raise Refusal("public_handover_lead_required")
    if handover is None:
        raise Refusal("public_entry_requires_s3_t20")


def verify_evidence(
    root: Path,
    request: Mapping[str, Any],
    *,
    features: list[str],
    staging_probe: Callable[[Mapping[str, Any]], None],
) -> dict[str, dict[str, Any]]:
    evidence = request["evidence"]
    if set(evidence) - ITEMS:
        raise Refusal("operation_schema_invalid")
    reports = {}
    for item in sorted(ITEMS):
        reason = (
            "gate_evidence_required"
            if item == "gates"
            else "promotion_evidence_" + item
        )
        report = referenced(root, evidence.get(item), reason)
        if not bound(report, request):
            raise Refusal(reason)
        valid = False
        if item == "merged":
            checks = report.get("checks", {})
            ancestors = report.get("ancestors")
            valid = (
                report.get("branch") == "main"
                and HEX40.fullmatch(str(report.get("main_commit", ""))) is not None
                and type(ancestors) is list
                and all(
                    type(value) is str and HEX40.fullmatch(value) for value in ancestors
                )
                and request["code_version"] in ancestors
                and isinstance(checks, dict)
                and set(checks) == CHECKS
                and all(
                    isinstance(v, dict)
                    and v.get("commit") == request["code_version"]
                    and v.get("conclusion") == "success"
                    and type(v.get("run_id")) is str
                    and bool(v["run_id"])
                    for v in checks.values()
                )
            )
        elif item == "review":
            valid = (
                report.get("verdict") == "APPROVED"
                and type(report.get("builder")) is str
                and type(report.get("reviewer")) is str
                and bool(report["builder"].strip())
                and bool(report["reviewer"].strip())
                and report["builder"].strip().casefold()
                != report["reviewer"].strip().casefold()
                and bool(report.get("findings_report"))
            )
        elif item == "whole_test":
            valid = (
                type(report.get("exit_code")) is int
                and report["exit_code"] == 0
                and type(report.get("passed")) is int
                and report["passed"] > 0
                and report.get("failed") == 0
                and type(report.get("seed")) is str
                and bool(report["seed"])
                and bool(report.get("command"))
            )
        elif item == "features":
            valid = (
                report.get("enabled") == features
                and report.get("completed") == features
                and bool(report.get("review_record"))
            )
        elif item == "gates":
            required, results = report.get("required"), report.get("results")
            valid = (
                type(required) is list
                and bool(required)
                and type(results) is dict
                and set(results) == set(required)
                and "S3-T02" in required
                and all(
                    isinstance(v, dict)
                    and v.get("verdict") == "APPROVED"
                    and v.get("commit") == request["code_version"]
                    for v in results.values()
                )
            )
        elif item == "staging":
            valid = (
                report.get("environment") == "staging"
                and type(report.get("port")) is int
                and report.get("installation_verified") == request["application_sha256"]
            )
        elif item == "retention":
            target = (
                request["release_id"]
                if request["operation"] == "initial_live_activation"
                else request["previous_release_id"]
            )
            valid = report.get("retained_release_id") == target and bool(
                report.get("installation")
            )
        if not valid:
            raise Refusal(reason)
        reports[item] = report
    staging_probe(reports["staging"])
    return reports
