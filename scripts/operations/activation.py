"""Serialized write-ahead authorisation, atomic routing and retained rollback."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from operations.common import Refusal, atomic_json, encoded, read_json
from operations.config import Environment, write_target
from operations.evidence import HEX64, ITEMS, exposure, operation, verify_evidence


@contextmanager
def operation_lock(state: Path) -> Iterator[None]:
    if (
        any(part.is_symlink() for part in (state, *state.parents))
        or (state / "operation.lock").is_symlink()
    ):
        raise Refusal("cross_environment_write")
    state.mkdir(parents=True, exist_ok=True)
    with (state / "operation.lock").open("a+b") as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise Refusal("operation_in_progress") from None
        try:
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


def entries(state: Path) -> list[dict[str, Any]]:
    path = state / "promotions.jsonl"
    if not path.exists():
        if any(
            (state / name).exists()
            for name in ("route.json", "history.json", "outcomes.jsonl")
        ) or any(state.glob("process-*.json")):
            raise Refusal("promotion_log_mismatch")
        return []
    try:
        data = path.read_bytes()
        if data and not data.endswith(b"\n"):
            raise Refusal("promotion_log_mismatch")
        found = [json.loads(line) for line in data.splitlines()]
        previous = None
        for index, entry in enumerate(found, 1):
            if (
                set(entry) != {"sequence", "previous", "request", "results", "sha256"}
                or type(entry["sequence"]) is not int
                or entry["sequence"] != index
                or entry["previous"] != previous
                or type(entry["sha256"]) is not str
                or HEX64.fullmatch(entry["sha256"]) is None
                or type(entry["results"]) is not dict
            ):
                raise Refusal("promotion_log_mismatch")
            body = {k: v for k, v in entry.items() if k != "sha256"}
            if hashlib.sha256(encoded(body)).hexdigest() != entry["sha256"]:
                raise Refusal("promotion_log_mismatch")
            request = operation(entry["request"])
            if request["environment"] == "staging" and entry["results"] != {}:
                raise Refusal("promotion_log_mismatch")
            if request["environment"] == "live" and (
                set(entry["results"]) != ITEMS
                or any(
                    not isinstance(v, dict)
                    or v.get("result") != "passed"
                    or not isinstance(v.get("report"), dict)
                    for v in entry["results"].values()
                )
            ):
                raise Refusal("promotion_log_mismatch")
            previous = entry["sha256"]
        if not found and (
            any(
                (state / name).exists()
                for name in ("history.json", "route.json", "outcomes.jsonl")
            )
            or any(state.glob("process-*.json"))
        ):
            raise Refusal("promotion_log_mismatch")
        if (state / "history.json").exists():
            witness = read_json(state / "history.json", "promotion_log_mismatch")
            if not found or witness != {
                "sequence": found[-1]["sequence"],
                "sha256": found[-1]["sha256"],
            }:
                raise Refusal("promotion_log_mismatch")
        return found
    except (OSError, ValueError, TypeError, KeyError):
        raise Refusal("promotion_log_mismatch") from None


def active_route(
    state: Path, history: list[dict[str, Any]] | None = None
) -> dict[str, Any] | None:
    path = state / "route.json"
    if not path.exists():
        return None
    route = read_json(path, "promotion_log_mismatch")
    if type(route.get("sequence")) is not int or set(route) != {
        "sequence",
        "authorization",
        "release_id",
        "application_sha256",
        "backend_port",
        "entry_port",
        "code_version",
        "environment",
        "exposure",
        "predecessor",
    }:
        raise Refusal("promotion_log_mismatch")
    log = entries(state) if history is None else history
    match = next(
        (
            entry
            for entry in log
            if entry["sequence"] == route.get("sequence")
            and entry["sha256"] == route.get("authorization")
        ),
        None,
    )
    if match is None or any(
        route.get(k) != match["request"][k]
        for k in (
            "release_id",
            "application_sha256",
            "backend_port",
            "code_version",
            "environment",
            "entry_port",
            "exposure",
        )
    ):
        raise Refusal("promotion_log_mismatch")
    require_predecessor(
        route["predecessor"], log, route["sequence"], route["environment"]
    )
    require_outcome(state, route)
    return route


def require_outcome(state: Path, route: Mapping[str, Any]) -> None:
    """Authorisation alone is not evidence that readiness and switching occurred."""
    try:
        payload = (state / "outcomes.jsonl").read_bytes()
        if not payload or not payload.endswith(b"\n"):
            raise Refusal("promotion_log_mismatch")
        outcomes = [json.loads(line) for line in payload.splitlines()]
        if dict(route, state="switched") not in outcomes:
            raise Refusal("promotion_log_mismatch")
    except (OSError, ValueError, TypeError):
        raise Refusal("promotion_log_mismatch") from None


def require_predecessor(
    predecessor: object,
    history: list[dict[str, Any]],
    before_sequence: int,
    environment: str,
) -> None:
    """Bind every retained rollback target to an earlier durable authorisation.

    The top-level route's authorisation does not authenticate arbitrary nested
    predecessor bytes. Check each retained node too, in descending sequence
    order, without accepting a fabricated target or a cyclic/forward reference.
    """
    fields = {
        "sequence",
        "authorization",
        "release_id",
        "application_sha256",
        "backend_port",
        "entry_port",
        "code_version",
        "environment",
        "exposure",
        "predecessor",
    }
    while predecessor is not None:
        if (
            type(predecessor) is not dict
            or set(predecessor) != fields
            or type(predecessor["sequence"]) is not int
            or not 0 < predecessor["sequence"] < before_sequence
            or predecessor["environment"] != environment
        ):
            raise Refusal("promotion_log_mismatch")
        match = next(
            (
                entry
                for entry in history
                if entry["sequence"] == predecessor["sequence"]
                and entry["sha256"] == predecessor["authorization"]
            ),
            None,
        )
        if match is None or any(
            predecessor[key] != match["request"][key]
            for key in (
                "release_id",
                "application_sha256",
                "backend_port",
                "entry_port",
                "code_version",
                "environment",
                "exposure",
            )
        ):
            raise Refusal("promotion_log_mismatch")
        before_sequence = predecessor["sequence"]
        predecessor = predecessor["predecessor"]


def _append_log(path: Path, payload: bytes) -> None:
    # Unbuffered writes prevent close() from flushing a torn buffered tail
    # after rollback. A short return is a failed append too, never success.
    with path.open("ab", buffering=0) as stream:
        start = stream.tell()
        try:
            if stream.write(payload) != len(payload):
                raise OSError("promotion log short write")
            os.fsync(stream.fileno())
        except OSError:
            os.ftruncate(stream.fileno(), start)
            os.fsync(stream.fileno())
            raise


def append_authorisation(
    state: Path,
    request: Mapping[str, Any],
    reports: Mapping[str, Any],
    history: list[dict[str, Any]],
    scope: Environment,
) -> dict[str, Any]:
    body = dict(
        sequence=len(history) + 1,
        previous=history[-1]["sha256"] if history else None,
        request=dict(request),
        results={item: dict(result="passed", report=reports[item]) for item in reports},
    )
    entry = dict(body, sha256=hashlib.sha256(encoded(body)).hexdigest())
    try:
        _append_log(
            write_target(scope, state / "promotions.jsonl"), encoded(entry) + b"\n"
        )
        atomic_json(
            write_target(scope, state / "history.json"),
            dict(sequence=entry["sequence"], sha256=entry["sha256"]),
        )
    except OSError:
        raise Refusal("promotion_log_unwritable") from None
    return entry


def require_previous_release(
    predecessor: Mapping[str, Any] | None,
) -> Mapping[str, Any]:
    """The initial release has no rollback target; it must be stopped explicitly."""
    if predecessor is None:
        raise Refusal("no_previous_release_for_rollback")
    return predecessor


def append_outcome(
    state: Path, entry: Mapping[str, Any], route: Mapping[str, Any], scope: Environment
) -> None:
    # Include the entire route, especially its predecessor, in the durable
    # switch witness. This detects route-only edits, not a state-folder writer.
    outcome = dict(route, state="switched")
    if outcome["authorization"] != entry["sha256"]:
        raise Refusal("promotion_log_mismatch")
    try:
        _append_log(
            write_target(scope, state / "outcomes.jsonl"), encoded(outcome) + b"\n"
        )
    except OSError:
        raise Refusal("promotion_log_unwritable") from None


def activate(
    state: Path,
    raw: Mapping[str, Any],
    *,
    scope: Environment,
    evidence_root: Path,
    features: list[str],
    verify_installation: Callable[[Mapping[str, Any]], None],
    staging_probe: Callable[[Mapping[str, Any]], None],
    retain: Callable[[Mapping[str, Any] | None], None],
    start: Callable[[Mapping[str, Any], dict[str, Any]], tuple[object, bool]],
    ready: Callable[[object, Mapping[str, Any]], None],
    stop: Callable[[object], None],
    retire: Callable[[Mapping[str, Any]], None],
    handover: Callable[[], None] | None = None,
    boundary: Callable[[str], None] = lambda _: None,
) -> dict[str, Any]:
    request = operation(raw)
    if scope.name != request["environment"] or scope.state.resolve() != state.resolve():
        raise Refusal("cross_environment_write")
    with operation_lock(state):
        history = entries(state)
        active = active_route(state, history)
        initial = request["operation"] == "initial_live_activation"
        if request["environment"] == "live":
            if initial and (history or active is not None):
                raise Refusal("bootstrap_reused")
            if initial and request["previous_release_id"] is not None:
                raise Refusal("activation_target_mismatch")
            if not initial:
                resume = (
                    active is None
                    and bool(history)
                    and request["operation"] == "restart"
                    and history[-1]["request"]["operation"] == "initial_live_activation"
                    and all(
                        request[key] == history[-1]["request"][key]
                        for key in (
                            "release_id",
                            "application_sha256",
                            "backend_port",
                            "code_version",
                        )
                    )
                    and request["previous_release_id"] == request["release_id"]
                )
                if (active is None and not resume) or request[
                    "previous_release_id"
                ] is None:
                    raise Refusal("predecessor_required")
                if (
                    active is not None
                    and request["previous_release_id"] != active["release_id"]
                ):
                    raise Refusal("activation_target_mismatch")
            if request["entry_port"] != 8088 or request["backend_port"] not in (
                18088,
                18089,
            ):
                raise Refusal("activation_target_mismatch")
            if (
                request["operation"] == "promote"
                and active is not None
                and (
                    request["backend_port"] == active["backend_port"]
                    or request["release_id"] == active["release_id"]
                )
            ):
                raise Refusal("activation_target_mismatch")
            if request["operation"] == "rollback":
                predecessor = None if active is None else active.get("predecessor")
                predecessor = require_previous_release(predecessor)
                if any(
                    request[key] != predecessor[key]
                    for key in (
                        "release_id",
                        "application_sha256",
                        "backend_port",
                        "code_version",
                    )
                ):
                    raise Refusal("activation_target_mismatch")
                retain(predecessor)
            if (
                request["operation"] in {"restart", "expose_public"}
                and active is not None
                and any(
                    request[key] != active[key]
                    for key in (
                        "release_id",
                        "application_sha256",
                        "backend_port",
                        "code_version",
                    )
                )
            ):
                raise Refusal("activation_target_mismatch")
        exposure(evidence_root, request, handover)
        verify_installation(request)
        retain(active if active is not None else request)
        reports = (
            verify_evidence(
                evidence_root, request, features=features, staging_probe=staging_probe
            )
            if request["environment"] == "live"
            else {}
        )
        boundary("before_authorisation")
        entry = append_authorisation(state, request, reports, history, scope)
        boundary("after_authorisation")
        child, launched = start(request, entry)
        switched = False
        try:
            ready(child, request)
            predecessor = (
                active.get("predecessor")
                if active is not None
                and request["operation"] in {"restart", "expose_public"}
                else active
            )
            route = {
                key: request[key]
                for key in (
                    "release_id",
                    "application_sha256",
                    "backend_port",
                    "entry_port",
                    "code_version",
                    "environment",
                    "exposure",
                )
            }
            route.update(
                sequence=entry["sequence"],
                authorization=entry["sha256"],
                predecessor=predecessor,
            )
            append_outcome(state, entry, route, scope)
            boundary("after_outcome")
            atomic_json(write_target(scope, state / "route.json"), route)
            switched = True
            boundary("after_switch")
            if request["exposure"] == "public_entry" and handover is not None:
                handover()
            if active is not None and active["backend_port"] != request["backend_port"]:
                retire(active)
            if (
                request["operation"] == "restart"
                and active is not None
                and active.get("predecessor") is not None
            ):
                retire(active["predecessor"])
            return route
        except BaseException:
            if not switched and launched:
                stop(child)
            raise
