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


FIRST_EXPOSURE = ("tunnel_stopped", "live_start", "handover")


def require_tunnel_start(rows: Sequence[Mapping[str, Any]], state: str) -> None:
    """Check the lead's recorded order before a tunnel start (document 13).

    For this live state the record must begin with the tunnel stopped, hold a
    successful loopback ``up`` and end its exposures with a successful
    ``expose_public``. Nothing here observes a tunnel: it checks the record.
    """
    own = []
    for row in rows:
        if (
            set(row) != {"step", "state", "exit_code"}
            or row["step"] not in FIRST_EXPOSURE
            or type(row["exit_code"]) is not int
            or type(row["state"]) is not str
            or not HEX64.fullmatch(row["state"])
        ):
            raise Refusal("runbook_result_invalid")
        if row["state"] == state:
            own.append((row["step"], row["exit_code"]))
    if own[:1] != [("tunnel_stopped", 0)]:
        raise Refusal("tunnel_stop_missing")
    started, exposure, before = False, None, False
    for step, code in own:
        started = started or (step, code) == ("live_start", 0)
        if step == "handover":
            exposure, before = code, started
    if exposure is None:
        raise Refusal("tunnel_start_before_exposure")
    if exposure != 0:
        raise Refusal("tunnel_start_after_failed_exposure")
    if not before:
        raise Refusal("runbook_step_missing")
