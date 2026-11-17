"""Budget ledger, single-writer lock and resume. Counters survive a changed selection."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from eii_custodian.publicdata.comtrade.policy import SCHEMA_VERSION

STATE_NAME = "state.json"
LOCK_NAME = "state.lock"
CLOCK_DATE_LENGTH = 10


class StateError(Exception):
    """The ledger cannot be read or written. The check name is the message."""

    def __init__(self, check: str) -> None:
        self.check = check
        super().__init__(check)


@dataclass(frozen=True)
class Ledger:
    """Persisted counters and partition progress. No address, header or credential."""

    schema_version: int
    policy_sha256: str
    selection_sha256: str
    pending: tuple[str, ...]
    completed: tuple[str, ...]
    child_sha256: tuple[tuple[str, str], ...]
    primary_calls: int
    secondary_calls: int
    budget_period: str
    incomplete: tuple[str, ...]
    next_eligible: str

    def calls(self, slot: str) -> int:
        """Return the reserved calls of one slot."""
        if slot == "primary":
            return self.primary_calls
        if slot == "secondary":
            return self.secondary_calls
        raise StateError("slot")


def fresh(
    policy_sha256: str,
    selection_sha256: str,
    pending: tuple[str, ...],
    budget_period: str,
) -> Ledger:
    """Return an empty ledger for one selection and one budget period."""
    return Ledger(
        schema_version=SCHEMA_VERSION,
        policy_sha256=policy_sha256,
        selection_sha256=selection_sha256,
        pending=pending,
        completed=(),
        child_sha256=(),
        primary_calls=0,
        secondary_calls=0,
        budget_period=budget_period,
        incomplete=(),
        next_eligible="",
    )


def acquire(directory: Path) -> None:
    """Create the lock exclusively. A filesystem failure keeps any lock already created."""
    try:
        directory.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise StateError("write_failed") from exc
    try:
        fd = os.open(directory / LOCK_NAME, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        raise StateError("state_locked") from exc
    except OSError as exc:
        raise StateError("write_failed") from exc
    try:
        os.close(fd)
    except OSError as exc:
        raise StateError("write_failed") from exc


def release(directory: Path) -> None:
    """Remove the lock. A filesystem failure leaves the lock in place."""
    try:
        (directory / LOCK_NAME).unlink(missing_ok=True)
    except OSError as exc:
        raise StateError("write_failed") from exc


def load_or_new(
    directory: Path,
    *,
    policy_sha256: str,
    selection_sha256: str,
    pending: tuple[str, ...],
    today: str,
    reset_rule: str,
) -> Ledger:
    """Load the ledger. A changed selection keeps the old counters and is refused."""
    path = directory / STATE_NAME
    if not path.is_file():
        return fresh(policy_sha256, selection_sha256, pending, today)
    ledger = read_ledger(path)
    if ledger.schema_version != SCHEMA_VERSION:
        raise StateError("stale_state")
    if ledger.selection_sha256 != selection_sha256:
        raise StateError("selection_changed")
    if ledger.policy_sha256 != policy_sha256:
        raise StateError("stale_state")
    return roll_budget(ledger, today, reset_rule)


def roll_budget(ledger: Ledger, today: str, reset_rule: str) -> Ledger:
    """Apply the one supported reset. A later calendar day clears both slot counters."""
    if reset_rule != "calendar_day":
        raise StateError("reset_rule")
    if (
        len(today) != CLOCK_DATE_LENGTH
        or len(ledger.budget_period) != CLOCK_DATE_LENGTH
    ):
        raise StateError("stale_state")
    if ledger.budget_period > today:
        raise StateError("stale_state")
    if ledger.budget_period < today:
        return Ledger(
            schema_version=ledger.schema_version,
            policy_sha256=ledger.policy_sha256,
            selection_sha256=ledger.selection_sha256,
            pending=ledger.pending,
            completed=ledger.completed,
            child_sha256=ledger.child_sha256,
            primary_calls=0,
            secondary_calls=0,
            budget_period=today,
            incomplete=ledger.incomplete,
            next_eligible="",
        )
    return ledger


def reserve(ledger: Ledger, slot: str) -> Ledger:
    """Consume one call before the send. A crash leaves the reservation consumed."""
    if slot == "primary":
        return _replace(ledger, primary_calls=ledger.primary_calls + 1)
    if slot == "secondary":
        return _replace(ledger, secondary_calls=ledger.secondary_calls + 1)
    raise StateError("slot")


def replace_pending(ledger: Ledger, key: str, children: tuple[str, ...]) -> Ledger:
    """Drop one pending key and enqueue its disjoint children."""
    pending = tuple(item for item in ledger.pending if item != key)
    return _replace(ledger, pending=pending + children)


def accept(ledger: Ledger, key: str, digest: str) -> Ledger:
    """Record one accepted child. A second accept of the same key is refused."""
    if key in ledger.completed or any(
        found == key for found, _digest in ledger.child_sha256
    ):
        raise StateError("duplicate_partition")
    pending = tuple(item for item in ledger.pending if item != key)
    return _replace(
        ledger,
        pending=pending,
        completed=(*ledger.completed, key),
        child_sha256=(*ledger.child_sha256, (key, digest)),
    )


def note_incomplete(ledger: Ledger, reason: str, next_eligible: str) -> Ledger:
    """Record why the run stopped. The next eligible time is a date, not a sleep."""
    return _replace(
        ledger,
        incomplete=(*ledger.incomplete, reason),
        next_eligible=next_eligible,
    )


def write_ledger(directory: Path, ledger: Ledger) -> None:
    """Atomically replace the ledger. A failed write removes its partial."""
    partial = directory / ".state.json.partial"
    try:
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / STATE_NAME
        partial.write_text(_dump(ledger), encoding="utf-8")
        os.replace(partial, target)
    except OSError:
        partial.unlink(missing_ok=True)
        raise


def read_ledger(path: Path) -> Ledger:
    """Read a ledger. Unknown fields and bad types are a stale state."""
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise StateError("stale_state") from exc
    if not isinstance(loaded, dict):
        raise StateError("stale_state")
    expected = {
        "budget_period",
        "child_sha256",
        "completed",
        "incomplete",
        "next_eligible",
        "pending",
        "policy_sha256",
        "primary_calls",
        "schema_version",
        "secondary_calls",
        "selection_sha256",
    }
    if set(loaded) != expected:
        raise StateError("stale_state")
    return Ledger(
        schema_version=_int(loaded, "schema_version"),
        policy_sha256=_text(loaded, "policy_sha256"),
        selection_sha256=_text(loaded, "selection_sha256"),
        pending=_texts(loaded, "pending"),
        completed=_texts(loaded, "completed"),
        child_sha256=_pairs(loaded.get("child_sha256")),
        primary_calls=_int(loaded, "primary_calls"),
        secondary_calls=_int(loaded, "secondary_calls"),
        budget_period=_text(loaded, "budget_period"),
        incomplete=_texts(loaded, "incomplete"),
        next_eligible=_text(loaded, "next_eligible"),
    )


def _replace(ledger: Ledger, **changes: object) -> Ledger:
    data = {
        "schema_version": ledger.schema_version,
        "policy_sha256": ledger.policy_sha256,
        "selection_sha256": ledger.selection_sha256,
        "pending": ledger.pending,
        "completed": ledger.completed,
        "child_sha256": ledger.child_sha256,
        "primary_calls": ledger.primary_calls,
        "secondary_calls": ledger.secondary_calls,
        "budget_period": ledger.budget_period,
        "incomplete": ledger.incomplete,
        "next_eligible": ledger.next_eligible,
    }
    data.update(changes)
    return Ledger(
        schema_version=_as_int(data["schema_version"]),
        policy_sha256=str(data["policy_sha256"]),
        selection_sha256=str(data["selection_sha256"]),
        pending=_as_texts(data["pending"]),
        completed=_as_texts(data["completed"]),
        child_sha256=_as_pairs(data["child_sha256"]),
        primary_calls=_as_int(data["primary_calls"]),
        secondary_calls=_as_int(data["secondary_calls"]),
        budget_period=str(data["budget_period"]),
        incomplete=_as_texts(data["incomplete"]),
        next_eligible=str(data["next_eligible"]),
    )


def _as_int(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise StateError("stale_state")
    return value


def _as_texts(value: object) -> tuple[str, ...]:
    if not isinstance(value, tuple) or not all(isinstance(item, str) for item in value):
        raise StateError("stale_state")
    return tuple(item for item in value if isinstance(item, str))


def _as_pairs(value: object) -> tuple[tuple[str, str], ...]:
    if not isinstance(value, tuple):
        raise StateError("stale_state")
    found: list[tuple[str, str]] = []
    for item in value:
        if not isinstance(item, tuple) or len(item) != 2:
            raise StateError("stale_state")
        left, right = item
        if not isinstance(left, str) or not isinstance(right, str):
            raise StateError("stale_state")
        found.append((left, right))
    return tuple(found)


def _dump(ledger: Ledger) -> str:
    payload = {
        "budget_period": ledger.budget_period,
        "child_sha256": [list(item) for item in ledger.child_sha256],
        "completed": list(ledger.completed),
        "incomplete": list(ledger.incomplete),
        "next_eligible": ledger.next_eligible,
        "pending": list(ledger.pending),
        "policy_sha256": ledger.policy_sha256,
        "primary_calls": ledger.primary_calls,
        "schema_version": ledger.schema_version,
        "secondary_calls": ledger.secondary_calls,
        "selection_sha256": ledger.selection_sha256,
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n"


def _int(raw: dict[str, object], name: str) -> int:
    value = raw[name]
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise StateError("stale_state")
    return value


def _text(raw: dict[str, object], name: str) -> str:
    value = raw[name]
    if not isinstance(value, str):
        raise StateError("stale_state")
    return value


def _texts(raw: dict[str, object], name: str) -> tuple[str, ...]:
    value = raw[name]
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise StateError("stale_state")
    return tuple(item for item in value if isinstance(item, str))


def _pairs(value: object) -> tuple[tuple[str, str], ...]:
    if not isinstance(value, list):
        raise StateError("stale_state")
    found: list[tuple[str, str]] = []
    for item in value:
        if not isinstance(item, list) or len(item) != 2:
            raise StateError("stale_state")
        left, right = item
        if not isinstance(left, str) or not isinstance(right, str):
            raise StateError("stale_state")
        found.append((left, right))
    return tuple(found)
