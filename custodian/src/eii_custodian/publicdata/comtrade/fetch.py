"""Orchestrate one Comtrade run. One reservation is consumed before each send."""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import quote

from eii_custodian.publicdata.comtrade.assemble import VerifiedChild, verify_child
from eii_custodian.publicdata.comtrade.parse import (
    ParseError,
    decode_members,
    parse_body,
    reject_duplicate_rows,
)
from eii_custodian.publicdata.comtrade.partition import (
    Partition,
    closed_partitions,
    initial_partitions,
    missing_cells,
    next_subdivision,
    subdivide,
)
from eii_custodian.publicdata.comtrade.policy import (
    PARSER_METHOD,
    PARSER_VERSION,
    SOURCE_ID,
    Descriptor,
    Policy,
    SafeRefusal,
    UnconfirmedPolicy,
    activation_check,
    policy_sha256,
    selection_sha256,
)
from eii_custodian.publicdata.comtrade.state import (
    Ledger,
    StateError,
    accept,
    acquire,
    load_or_new,
    note_incomplete,
    release,
    replace_pending,
    reserve,
    roll_budget,
    write_ledger,
)
from eii_custodian.publicdata.fetch.receipts import commit_pair, sha256_hex, sidecar_for
from eii_custodian.publicdata.fetch.registry import Entry
from eii_custodian.publicdata.fetch.terms_text import terms_text_sha256
from eii_custodian.publicdata.fetch.transport import (
    AttemptResult,
    Opener,
    SlotReader,
    perform,
)

Sleeper = Callable[[float], None]
Clock = Callable[[], str]
MANIFEST_NAME = "manifest.json"
COVERAGE_NAME = "coverage.json"
EXHAUSTION_SIGNAL = "calls_reached"


@dataclass(frozen=True)
class _Split:
    children: tuple[Partition, ...]


@dataclass(frozen=True)
class _Accepted:
    body: bytes
    count: int
    limit: int


@dataclass(frozen=True)
class FetchResult:
    """A finished or stopped run. failure is set whenever no complete manifest exists."""

    failure: SafeRefusal | None
    digest: str
    host: str
    requested_cells: int
    present_cells: int
    gap_cells: int


class _EmptySlots:
    """A reader for a run that was not given credentials."""

    def read_slot(self, slot: str) -> str:
        """Return an empty header. Nothing is read from the environment."""
        del slot
        return ""


def fetch_source(
    entry: Entry,
    cache: Path,
    clock: Clock,
    sleep: Sleeper,
    opener: Opener,
    slots: SlotReader | None,
    *,
    api_class: str = "keyed",
    requested_slot: str | None = None,
) -> FetchResult:
    """Fetch one activated row through an injected opener. No complete manifest on failure."""
    del sleep
    policy = entry.comtrade_policy
    check = activation_check(
        policy if isinstance(policy, (Policy, UnconfirmedPolicy)) else None,
        row_count_min=entry.row_count_min,
        row_count_max=entry.row_count_max,
        period_first=entry.period_first,
        period_last=entry.period_last,
        licence_basis=entry.licence_basis,
        decision_record=entry.decision_record,
    )
    if check is not None or not isinstance(policy, Policy):
        held = policy if isinstance(policy, UnconfirmedPolicy) else None
        return _stopped(check or "metadata_unconfirmed", held)
    if entry.commit_allowed or entry.terms_words == "":
        return _stopped("commit_forbidden", policy)
    directory = cache / entry.key
    try:
        acquire(directory)
    except StateError as exc:
        return _stopped(exc.check, policy)
    result: FetchResult | None = None
    try:
        try:
            result = _run(
                entry,
                policy,
                directory,
                clock,
                opener,
                slots if slots is not None else _EmptySlots(),
                api_class,
                requested_slot,
            )
        except OSError:
            result = _stopped("write_failed", policy)
    finally:
        try:
            release(directory)
        except StateError:
            result = _stopped("write_failed", policy)
    if result is None:
        return _stopped("write_failed", policy)
    return result


def refuse_committed_sentinel(entry: Entry, candidate: Path, sentinel: str) -> None:
    """Refuse a candidate committed file that holds a fetched sentinel."""
    if entry.commit_allowed:
        raise SafeRefusal(
            "commit_forbidden", "https://invalid.example/refused", "commit"
        )
    if (
        sentinel
        and candidate.is_file()
        and sentinel in candidate.read_text(encoding="utf-8")
    ):
        raise SafeRefusal(
            "commit_forbidden", "https://invalid.example/refused", "commit"
        )


def _run(
    entry: Entry,
    policy: Policy,
    directory: Path,
    clock: Clock,
    opener: Opener,
    slots: SlotReader,
    api_class: str,
    requested_slot: str | None,
) -> FetchResult:
    initial = initial_partitions(policy)
    today = _day(clock())
    try:
        ledger = load_or_new(
            directory,
            policy_sha256=policy_sha256(policy),
            selection_sha256=selection_sha256(policy),
            pending=tuple(item.key() for item in initial),
            today=today,
            reset_rule=policy.reset_rule,
        )
    except StateError as exc:
        return _stopped(exc.check, policy)
    problem, _stored = _verified(directory, ledger, policy, entry)
    if problem is not None:
        return _fail(policy, problem, ledger, directory, initial, api_class)
    index = {item.key(): item for item in closed_partitions(policy)}
    while ledger.pending:
        today = _day(clock())
        try:
            rolled = roll_budget(ledger, today, policy.reset_rule)
        except StateError as exc:
            return _fail(policy, exc.check, ledger, directory, initial, api_class)
        if rolled is not ledger:
            ledger = rolled
            write_ledger(directory, ledger)
        key = ledger.pending[0]
        partition = index.get(key)
        if partition is None:
            return _fail(policy, "stale_state", ledger, directory, initial, api_class)
        slot = _slot(ledger, policy, api_class, requested_slot)
        if slot.startswith("fail:"):
            reason = slot.removeprefix("fail:")
            saved = note_incomplete(ledger, reason, _next_day(today))
            write_ledger(directory, saved)
            _write_coverage(directory, policy, initial, saved)
            return _result(policy, _refusal(policy, reason), initial, saved, api_class)
        header = ""
        if api_class != "public":
            header = slots.read_slot(slot)
            if header == "":
                reason = "primary_absent" if slot == "primary" else "budget_exhausted"
                saved = note_incomplete(ledger, reason, _next_day(today))
                write_ledger(directory, saved)
                _write_coverage(directory, policy, initial, saved)
                return _result(
                    policy, _refusal(policy, reason), initial, saved, api_class
                )
        ledger = reserve(ledger, slot)
        write_ledger(directory, ledger)
        descriptor = partition.descriptor(policy, api_class)
        outcome, ledger = _send(policy, descriptor, header, opener, ledger)
        if isinstance(outcome, SafeRefusal):
            write_ledger(directory, ledger)
            _write_coverage(directory, policy, initial, ledger)
            return _result(policy, outcome, initial, ledger, api_class)
        if isinstance(outcome, _Split):
            for child in outcome.children:
                index[child.key()] = child
            ledger = replace_pending(
                ledger, key, tuple(child.key() for child in outcome.children)
            )
            write_ledger(directory, ledger)
            continue
        assert isinstance(outcome, _Accepted)
        try:
            receipt_sha = _store_child(
                entry,
                directory,
                policy,
                partition,
                outcome.body,
                outcome.count,
                outcome.limit,
                ledger,
                api_class,
                clock(),
            )
        except OSError:
            return _fail(policy, "write_failed", ledger, directory, initial, api_class)
        try:
            ledger = accept(ledger, key, receipt_sha)
        except StateError as exc:
            return _fail(policy, exc.check, ledger, directory, initial, api_class)
        write_ledger(directory, ledger)
    problem, stored = _verified(directory, ledger, policy, entry)
    if problem is not None:
        return _fail(policy, problem, ledger, directory, initial, api_class)
    total = sum(item.count for item in stored)
    if total < policy.count_bounds.minimum or total > policy.count_bounds.maximum:
        return _fail(policy, "count_bounds", ledger, directory, initial, api_class)
    seen_periods = {period for item in stored for period in item.periods}
    if any(period not in seen_periods for period in policy.expected_last_periods):
        return _fail(policy, "missing_period", ledger, directory, initial, api_class)
    try:
        reject_duplicate_rows([row for item in stored for row in item.rows])
    except ParseError:
        return _fail(policy, "duplicate_key", ledger, directory, initial, api_class)
    missing = missing_cells(initial, ledger.pending, ledger.completed)
    _write_coverage(directory, policy, initial, ledger, missing)
    if missing:
        return _result(
            policy, _refusal(policy, "coverage_gap"), initial, ledger, api_class
        )
    try:
        digest = _write_manifest(directory, policy, initial, ledger, missing)
    except OSError:
        return _fail(policy, "write_failed", ledger, directory, initial, api_class)
    return FetchResult(
        None,
        digest,
        _host_for(policy, api_class),
        len(initial),
        len(initial) - len(missing),
        len(missing),
    )


def _send(
    policy: Policy,
    descriptor: Descriptor,
    header: str,
    opener: Opener,
    ledger: Ledger,
) -> tuple[SafeRefusal | _Split | _Accepted, Ledger]:
    """Send once. A throttle stops the run and does not reserve another call."""
    try:
        result = perform(policy, descriptor, header or None, opener)
    except SafeRefusal as exc:
        return exc, ledger
    if result.category == "auth":
        return _refusal(policy, "authentication", descriptor, header), ledger
    if result.category == "throttle":
        return _refusal(policy, "throttled", descriptor, header), ledger
    if result.category != "ok":
        return _refusal(policy, "http_status", descriptor, header), ledger
    return _classify(policy, descriptor, result, header), ledger


def _classify(
    policy: Policy, descriptor: Descriptor, result: AttemptResult, header: str
) -> SafeRefusal | _Split | _Accepted:
    if header and (result.header_echo or _body_holds(result.body, header)):
        return _refusal(policy, "provider_error", descriptor, header)
    if result.error_text or _body_holds(result.body, header):
        return _refusal(policy, "provider_error", descriptor, header)
    limit = policy.limit_for(descriptor.api_class)
    try:
        parsed = parse_body(
            result.body,
            policy,
            descriptor,
            source_version=policy.version,
            receipt_sha256="",
        )
    except ParseError as exc:
        return _refusal(policy, exc.check, descriptor, header)
    if parsed.truncated or parsed.raw_count > limit:
        return _refusal(policy, "truncation", descriptor, header)
    if parsed.raw_count == limit:
        field = next_subdivision(policy, _partition_from_descriptor(descriptor))
        if field is None:
            return _refusal(policy, "unresolved_truncation", descriptor, header)
        children = subdivide(policy, _partition_from_descriptor(descriptor), field)
        return _Split(children)
    return _Accepted(result.body, parsed.raw_count, limit)


def _body_holds(body: bytes, secret: str) -> bool:
    if secret == "":
        return False
    raw = secret.encode("utf-8")
    if raw in body:
        return True
    encoded = quote(secret, safe="").encode("utf-8")
    if encoded != raw and encoded in body:
        return True
    return _json_holds(body, secret)


def _json_holds(body: bytes, secret: str) -> bool:
    try:
        loaded = decode_members(body)
    except ParseError:
        return False
    return _value_holds(loaded, secret)


def _value_holds(value: object, secret: str) -> bool:
    if isinstance(value, str):
        return secret in value
    if isinstance(value, dict):
        return any(
            (isinstance(key, str) and secret in key) or _value_holds(item, secret)
            for key, item in value.items()
        )
    if isinstance(value, list):
        return any(_value_holds(item, secret) for item in value)
    return False


def _partition_from_descriptor(descriptor: Descriptor) -> Partition:
    return Partition(
        series_role=descriptor.series_role,
        partner_code=descriptor.partner_code
        if descriptor.series_role == "reporter"
        else descriptor.reporter_code,
        frequency=descriptor.frequency,
        period=descriptor.period,
        flow_code=descriptor.flow_code,
        chapter=descriptor.chapter,
        subdivision=descriptor.subdivision,
    )


def _slot(
    ledger: Ledger,
    policy: Policy,
    api_class: str,
    requested: str | None,
) -> str:
    if api_class == "public":
        if ledger.primary_calls >= policy.daily_calls:
            return "fail:budget_exhausted"
        return "primary"
    primary_open = ledger.primary_calls < policy.daily_calls
    if requested == "secondary" and primary_open:
        return "fail:premature_secondary"
    if primary_open:
        return "primary"
    if policy.daily_exhaustion_signal != EXHAUSTION_SIGNAL:
        return "fail:exhaustion_signal"
    if ledger.secondary_calls >= policy.daily_calls:
        return "fail:budget_exhausted"
    return "secondary"


def _store_child(
    entry: Entry,
    directory: Path,
    policy: Policy,
    partition: Partition,
    body: bytes,
    count: int,
    limit: int,
    ledger: Ledger,
    api_class: str,
    retrieved_utc: str,
) -> str:
    body_sha = sha256_hex(body)
    host = _host_for(policy, api_class)
    side = sidecar_for(
        entry,
        digest=body_sha,
        nbytes=len(body),
        fetch_url=_fetch_url(policy, partition, api_class),
        fetch_host=host,
        retrieved_utc=retrieved_utc,
        publisher=entry.publisher,
        source_modified="",
        row_count=count,
        terms_sha256=terms_text_sha256(entry.terms_words.encode("utf-8")),
    )
    side.update(
        {
            "policy_sha256": policy_sha256(policy),
            "evidence_sha256": policy.evidence_sha256,
            "source_version": policy.version,
            "partition_key": partition.key(),
            "parent_key": partition.parent_key,
            "api_class": api_class,
            "applied_limit": limit,
            "count": count,
            "budget_period": ledger.budget_period,
            "daily_counts": {
                "primary": ledger.primary_calls,
                "secondary": ledger.secondary_calls,
            },
        }
    )
    text = json.dumps(side, sort_keys=True, ensure_ascii=True) + "\n"
    receipt_sha = sha256_hex(text.encode("utf-8"))
    commit_pair(directory, receipt_sha, "json", body, side)
    written = (directory / f"{receipt_sha}.meta.json").read_bytes()
    if sha256_hex(written) != receipt_sha:
        raise OSError("receipt")
    return receipt_sha


def _fetch_url(policy: Policy, partition: Partition, api_class: str) -> str:
    from eii_custodian.publicdata.comtrade.policy import safe_url

    return safe_url(policy, partition.descriptor(policy, api_class))


def _write_coverage(
    directory: Path,
    policy: Policy,
    initial: tuple[Partition, ...],
    ledger: Ledger,
    missing: tuple[str, ...] | None = None,
) -> None:
    absent = (
        missing
        if missing is not None
        else missing_cells(initial, ledger.pending, ledger.completed)
    )
    present = len(initial) - len(absent)
    payload = {
        "gap_cells": len(absent),
        "missing": list(absent),
        "present_cells": present,
        "price_amount": policy.price_amount,
        "price_currency": policy.price_currency,
        "price_retrieved_on": policy.price_retrieved_on,
        "price_source": policy.price_source,
        "price_unavailable_reason": policy.price_unavailable_reason,
        "requested_cells": len(initial),
        "source_id": SOURCE_ID,
    }
    _atomic_text(directory / COVERAGE_NAME, json.dumps(payload, sort_keys=True) + "\n")


def _write_manifest(
    directory: Path,
    policy: Policy,
    initial: tuple[Partition, ...],
    ledger: Ledger,
    missing: tuple[str, ...],
) -> str:
    children = []
    for key, receipt_sha in sorted(ledger.child_sha256, key=lambda item: item[0]):
        side = json.loads(
            (directory / f"{receipt_sha}.meta.json").read_text(encoding="utf-8")
        )
        body_sha = side.get("sha256") if isinstance(side, dict) else ""
        children.append({"key": key, "receipt_sha256": receipt_sha, "sha256": body_sha})
    payload = {
        "children": children,
        "complete": True,
        "gap_cells": len(missing),
        "missing": list(missing),
        "parser_method": PARSER_METHOD,
        "parser_version": PARSER_VERSION,
        "policy_sha256": policy_sha256(policy),
        "present_cells": len(initial) - len(missing),
        "requested_cells": len(initial),
        "selection_sha256": selection_sha256(policy),
        "source_id": SOURCE_ID,
    }
    text = json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n"
    _atomic_text(directory / MANIFEST_NAME, text)
    return sha256_hex(text.encode("utf-8"))


def _atomic_text(path: Path, text: str) -> None:
    partial = path.with_name("." + path.name + ".partial")
    try:
        partial.write_text(text, encoding="utf-8")
        os.replace(partial, path)
    except OSError:
        partial.unlink(missing_ok=True)
        raise


def _verified(
    directory: Path, ledger: Ledger, policy: Policy, entry: Entry
) -> tuple[str | None, tuple[VerifiedChild, ...]]:
    terms = terms_text_sha256(entry.terms_words.encode("utf-8"))
    found: list[VerifiedChild] = []
    for key, receipt_sha in ledger.child_sha256:
        try:
            found.append(
                verify_child(
                    directory,
                    policy,
                    child_key=key,
                    receipt_sha256=receipt_sha,
                    publisher=entry.publisher,
                    licence_basis=entry.licence_basis,
                    terms_sha256=terms,
                )
            )
        except SafeRefusal as exc:
            return exc.check, ()
    return None, tuple(found)


def _host_for(policy: Policy, api_class: str) -> str:
    template = policy.template(api_class, "data")
    if template is None:
        return policy.endpoint_templates[0].host
    return template.host


def _fail(
    policy: Policy,
    check: str,
    ledger: Ledger,
    directory: Path,
    initial: tuple[Partition, ...],
    api_class: str,
) -> FetchResult:
    write_ledger(directory, ledger)
    _write_coverage(directory, policy, initial, ledger)
    return _result(policy, _refusal(policy, check), initial, ledger, api_class)


def _result(
    policy: Policy,
    failure: SafeRefusal,
    initial: tuple[Partition, ...],
    ledger: Ledger,
    api_class: str,
) -> FetchResult:
    missing = missing_cells(initial, ledger.pending, ledger.completed)
    return FetchResult(
        failure,
        "",
        _host_for(policy, api_class),
        len(initial),
        len(initial) - len(missing),
        len(missing),
    )


def _stopped(check: str, policy: Policy | UnconfirmedPolicy | None) -> FetchResult:
    if isinstance(policy, Policy):
        refusal = _refusal(policy, check)
        host = policy.endpoint_templates[0].host
    else:
        refusal = SafeRefusal(check, "https://invalid.example/refused", "unconfirmed")
        host = ""
    return FetchResult(refusal, "", host, 0, 0, 0)


def _refusal(
    policy: Policy,
    check: str,
    descriptor: Descriptor | None = None,
    secret: str = "",
) -> SafeRefusal:
    from eii_custodian.publicdata.comtrade.policy import refusal

    if descriptor is not None:
        return refusal(policy, descriptor, check, secret)
    host = policy.endpoint_templates[0].host
    return SafeRefusal(check, f"https://{host}/refused", check)


def _day(stamp: str) -> str:
    return stamp[:10]


def _next_day(today: str) -> str:
    year_text, month_text, day_text = today.split("-")
    found = date(int(year_text), int(month_text), int(day_text)) + timedelta(days=1)
    return found.isoformat()
