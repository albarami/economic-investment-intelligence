"""Check the exact invented operator transcript; no command is executed here."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from operations.common import Refusal
from operations.evidence import HEX64

STEPS = (
    ("build", "build-release", "custodian"),
    ("stage_load", "load-release", "staging"),
    ("stage_probe", "preflight", "staging"),
    ("stage_start", "up", "staging"),
    ("live_load", "load-release", "live"),
    ("live_probe", "preflight", "live"),
    ("live_start", "up", "live"),
    ("candidate_build", "build-release", "custodian"),
    ("candidate_stage_load", "load-release", "staging"),
    ("candidate_stage_probe", "preflight", "staging"),
    ("candidate_stage_start", "up", "staging"),
    ("candidate_live_load", "load-release", "live"),
    ("candidate_live_probe", "preflight", "live"),
    ("promotion", "up", "live"),
    ("rollback_stage_probe", "preflight", "staging"),
    ("rollback_stage_start", "up", "staging"),
    ("rollback_live_probe", "preflight", "live"),
    ("rollback", "up", "live"),
    ("handover_probe", "preflight", "live"),
    ("handover", "up", "live"),
    ("stage_stop", "down", "staging"),
    ("live_stop", "down", "live"),
)


def require_step_count(rows: Sequence[Mapping[str, Any]]) -> None:
    """Require the complete sequence before the strict positional comparison."""
    if len(rows) != len(STEPS):
        raise Refusal("runbook_step_missing")


def verify_transcript(rows: Sequence[Mapping[str, Any]]) -> None:
    require_step_count(rows)
    bindings: dict[str, dict[str, Any]] = {}
    first: str | None = None
    candidate: str | None = None
    for row, (step, command, environment) in zip(rows, STEPS, strict=True):
        if (
            row.get("step") != step
            or row.get("command") != command
            or row.get("environment") != environment
        ):
            raise Refusal("runbook_step_missing")
        if (
            type(row.get("exit_code")) is not int
            or row["exit_code"] != 0
            or type(row.get("verified_result")) is not dict
        ):
            raise Refusal("runbook_result_invalid")
        result = row["verified_result"]
        if set(result) != {
            "release_id",
            "release_sha256",
            "application_sha256",
            "backend_port",
        } or any(
            not HEX64.fullmatch(str(result[key]))
            for key in ("release_id", "release_sha256")
        ):
            raise Refusal("runbook_result_invalid")
        identity = result["release_id"]
        if step in {"build", "candidate_build"}:
            if (
                result["application_sha256"] is not None
                or result["backend_port"] is not None
            ):
                raise Refusal("runbook_result_invalid")
            bindings[identity] = dict(
                release_sha256=result["release_sha256"], application_sha256=None
            )
            if step == "build":
                first = identity
            else:
                candidate = identity
                if candidate == first:
                    raise Refusal("runbook_result_invalid")
        else:
            expected = (
                candidate
                if step.startswith("candidate_") or step == "promotion"
                else first
            )
            if (
                identity != expected
                or identity not in bindings
                or result["release_sha256"] != bindings[identity]["release_sha256"]
            ):
                raise Refusal("runbook_result_invalid")
            if not HEX64.fullmatch(str(result["application_sha256"])):
                raise Refusal("runbook_result_invalid")
            if bindings[identity]["application_sha256"] is None:
                bindings[identity]["application_sha256"] = result["application_sha256"]
            if result["application_sha256"] != bindings[identity]["application_sha256"]:
                raise Refusal("runbook_result_invalid")
            port = (
                8089
                if environment == "staging"
                else 18089
                if step.startswith("candidate_") or step == "promotion"
                else 18088
            )
            if (
                type(result["backend_port"]) is not int
                or result["backend_port"] != port
            ):
                raise Refusal("runbook_result_invalid")
