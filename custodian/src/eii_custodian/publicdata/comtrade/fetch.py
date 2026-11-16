"""Orchestrate one Comtrade run. Reservations happen before each send."""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from eii_custodian.publicdata.comtrade.parse import ParseError, parse_body
from eii_custodian.publicdata.comtrade.partition import (
    Partition,
    initial_partitions,
    missing_cells,
    next_subdivision,
    subdivide,
)
from eii_custodian.publicdata.comtrade.policy import (
    PARSER_METHOD,
    PARSER_VERSION,
    SOURCE_ID,
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
    write_ledger,
)
from eii_custodian.publicdata.fetch.receipts import sha256_hex, sidecar_for
from eii_custodian.publicdata.fetch.registry import Entry
from eii_custodian.publicdata.fetch.transport import (
    BACKOFF_S,
    MAX_RETRIES,
    AttemptResult,
    Opener,
    OpenerFault,
    SlotSecrets,
    perform,
)

Sleeper = Callable[[float], None]
Clock = Callable[[], str]
MANIFEST_NAME = "manifest.json"
COVERAGE_NAME = "coverage.json"
EXHAUSTION_SIGNAL = "calls_reached"
TERMS_MARKER = "terms to be read"


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


def fetch_source(
    entry: Entry,
    cache: Path,
    clock: Clock,
    sleep: Sleeper,
    opener: Opener,
    slots: SlotSecrets | None,
    *,
    api_class: str = "keyed",
    requested_slot: str | None = None,
) -> FetchResult:
    """Fetch one activated row through an injected opener. No complete manifest on failure."""
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
    today = _day(clock())
    try:
        acquire(directory)
    except StateError as exc:
        return _stopped(exc.check, policy)
    try:
        return _run(
            entry,
            policy,
            directory,
            clock,
            sleep,
            opener,
            slots or SlotSecrets("", ""),
            api_class,
            requested_slot,
            today,
        )
    finally:
        release(directory)


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
    sleep: Sleeper,
    opener: Opener,
    slots: SlotSecrets,
    api_class: str,
    requested_slot: str | None,
    today: str,
) -> FetchResult:
    initial = initial_partitions(policy)
    try:
        ledger = load_or_new(
            directory,
            policy_sha256=policy_sha256(policy),
            selection_sha256=selection_sha256(policy),
            pending=tuple(item.key() for item in initial),
            today=today,
        )
    except StateError as exc:
        return _stopped(exc.check, policy)
    index = {item.key(): item for item in _all_known(initial, policy)}
    while ledger.pending:
        key = ledger.pending[0]
        partition = index.get(key)
        if partition is None:
            return _fail(policy, "stale_state", ledger, directory, initial)
        slot = _slot(ledger, policy, slots, api_class, requested_slot)
        if slot.startswith("fail:"):
            reason = slot.removeprefix("fail:")
            saved = note_incomplete(ledger, reason, _next_day(today))
            write_ledger(directory, saved)
            _write_coverage(directory, policy, initial, saved)
            return _result(policy, _refusal(policy, reason), initial, saved)
        header = "" if api_class == "public" else slots.for_slot(slot)
        if api_class == "keyed" and header == "":
            return _fail(policy, "primary_absent", ledger, directory, initial)
        ledger = reserve(ledger, slot)
        write_ledger(directory, ledger)
        descriptor = partition.descriptor(policy, api_class)
        outcome, ledger = _send(
            policy, descriptor, header, opener, sleep, ledger, slot, directory
        )
        if isinstance(outcome, SafeRefusal):
            write_ledger(directory, ledger)
            _write_coverage(directory, policy, initial, ledger)
            return _result(policy, outcome, initial, ledger)
        if isinstance(outcome, _Split):
            for child in outcome.children:
                index[child.key()] = child
            ledger = replace_pending(
                ledger, key, tuple(child.key() for child in outcome.children)
            )
            write_ledger(directory, ledger)
            continue
        assert isinstance(outcome, _Accepted)
        body = outcome.body
        parsed_count = outcome.count
        limit = outcome.limit
        digest = sha256_hex(body)
        _store_child(
            entry,
            directory,
            policy,
            partition,
            digest,
            body,
            parsed_count,
            limit,
            ledger,
            api_class,
        )
        try:
            ledger = accept(ledger, key, digest)
        except StateError as exc:
            return _fail(policy, exc.check, ledger, directory, initial)
        write_ledger(directory, ledger)
    missing = missing_cells(initial, ledger.pending, ledger.completed)
    _write_coverage(directory, policy, initial, ledger, missing)
    if missing:
        return _result(policy, _refusal(policy, "coverage_gap"), initial, ledger)
    digest = _write_manifest(directory, policy, initial, ledger, missing)
    host = policy.endpoint_templates[0].host
    return FetchResult(
        None, digest, host, len(initial), len(initial) - len(missing), len(missing)
    )


def _send(
    policy: Policy,
    descriptor: object,
    header: str,
    opener: Opener,
    sleep: Sleeper,
    ledger: Ledger,
    slot: str,
    directory: Path,
) -> tuple[SafeRefusal | _Split | _Accepted, Ledger]:
    """Return a body, child partitions, or a refusal. Retries consume reservations."""
    from eii_custodian.publicdata.comtrade.policy import Descriptor

    if not isinstance(descriptor, Descriptor):
        return _refusal(policy, "mirror_direction"), ledger
    attempt = 0
    current = ledger
    while True:
        try:
            result = perform(policy, descriptor, header or None, opener)
        except SafeRefusal as exc:
            return exc, current
        except OpenerFault:
            return _refusal(policy, "provider_error", descriptor), current
        if result.category == "auth":
            return _refusal(policy, "authentication", descriptor), current
        if result.category == "throttle":
            if attempt < MAX_RETRIES:
                sleep(BACKOFF_S[attempt])
                attempt += 1
                current = reserve(current, slot)
                write_ledger(directory, current)
                continue
            return _refusal(policy, "throttled", descriptor), current
        if result.category != "ok":
            return _refusal(policy, "http_status", descriptor), current
        classified = _classify(policy, descriptor, result, header)
        return classified, current


def _classify(
    policy: Policy, descriptor: object, result: AttemptResult, header: str
) -> SafeRefusal | _Split | _Accepted:
    from eii_custodian.publicdata.comtrade.policy import Descriptor

    if not isinstance(descriptor, Descriptor):
        return _refusal(policy, "mirror_direction")
    if header and result.header_echo:
        return _refusal(policy, "provider_error", descriptor)
    if result.error_text:
        return _refusal(policy, "provider_error", descriptor)
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
        return _refusal(policy, exc.check, descriptor)
    if parsed.truncated or parsed.raw_count > limit:
        return _refusal(policy, "truncation", descriptor)
    if parsed.raw_count == limit:
        field = _field_for(policy, descriptor)
        if field is None:
            return _refusal(policy, "unresolved_truncation", descriptor)
        partition = _partition_from_descriptor(descriptor)
        children = subdivide(policy, partition, field)
        if not children:
            return _refusal(policy, "unresolved_truncation", descriptor)
        return _Split(children)
    return _Accepted(result.body, parsed.raw_count, limit)


def _field_for(policy: Policy, descriptor: object) -> str | None:
    from eii_custodian.publicdata.comtrade.policy import Descriptor

    if not isinstance(descriptor, Descriptor):
        return None
    return next_subdivision(policy, _partition_from_descriptor(descriptor))


def _partition_from_descriptor(descriptor: object) -> Partition:
    from eii_custodian.publicdata.comtrade.policy import Descriptor

    if not isinstance(descriptor, Descriptor):
        raise OpenerFault("descriptor")
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
    slots: SlotSecrets,
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
        if slots.primary == "":
            return "fail:primary_absent"
        return "primary"
    if policy.daily_exhaustion_signal != EXHAUSTION_SIGNAL:
        return "fail:exhaustion_signal"
    if ledger.secondary_calls >= policy.daily_calls or slots.secondary == "":
        return "fail:budget_exhausted"
    return "secondary"


def _store_child(
    entry: Entry,
    directory: Path,
    policy: Policy,
    partition: Partition,
    digest: str,
    body: bytes,
    count: int,
    limit: int,
    ledger: Ledger,
    api_class: str,
) -> None:
    side = sidecar_for(
        entry,
        digest=digest,
        nbytes=len(body),
        fetch_url=_fetch_url(policy, partition, api_class),
        fetch_host=policy.endpoint_templates[0].host,
        retrieved_utc=ledger.budget_period + "T00:00:00Z",
        publisher=entry.publisher,
        source_modified="",
        row_count=count,
        terms_sha256="",
    )
    side.update(
        {
            "policy_sha256": policy_sha256(policy),
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
    target = directory / f"{digest}.json"
    partial = directory / f".{digest}.json.partial"
    partial.write_bytes(body)
    os.replace(partial, target)
    meta = directory / f"{digest}.meta.json"
    meta_partial = directory / f".{digest}.meta.json.partial"
    meta_partial.write_text(
        json.dumps(side, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8"
    )
    os.replace(meta_partial, meta)


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
    path = directory / COVERAGE_NAME
    path.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")


def _write_manifest(
    directory: Path,
    policy: Policy,
    initial: tuple[Partition, ...],
    ledger: Ledger,
    missing: tuple[str, ...],
) -> str:
    children = [
        {"key": key, "sha256": digest}
        for key, digest in sorted(ledger.child_sha256, key=lambda item: item[0])
    ]
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
    partial = directory / ".manifest.json.partial"
    target = directory / MANIFEST_NAME
    partial.write_text(text, encoding="utf-8")
    os.replace(partial, target)
    return sha256_hex(text.encode("utf-8"))


def _all_known(initial: tuple[Partition, ...], policy: Policy) -> tuple[Partition, ...]:
    """Include one generation of children so a resumed split can be indexed."""
    found = list(initial)
    for partition in initial:
        field = next_subdivision(policy, partition)
        if field is not None:
            found.extend(subdivide(policy, partition, field))
    return tuple(found)


def _fail(
    policy: Policy,
    check: str,
    ledger: Ledger,
    directory: Path,
    initial: tuple[Partition, ...],
) -> FetchResult:
    write_ledger(directory, ledger)
    _write_coverage(directory, policy, initial, ledger)
    return _result(policy, _refusal(policy, check), initial, ledger)


def _result(
    policy: Policy, failure: SafeRefusal, initial: tuple[Partition, ...], ledger: Ledger
) -> FetchResult:
    missing = missing_cells(initial, ledger.pending, ledger.completed)
    host = policy.endpoint_templates[0].host
    return FetchResult(
        failure, "", host, len(initial), len(initial) - len(missing), len(missing)
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
    policy: Policy, check: str, descriptor: object | None = None
) -> SafeRefusal:
    from eii_custodian.publicdata.comtrade.policy import Descriptor, refusal

    if isinstance(descriptor, Descriptor):
        return refusal(policy, descriptor, check)
    host = policy.endpoint_templates[0].host
    return SafeRefusal(check, f"https://{host}/refused", check)


def _day(stamp: str) -> str:
    return stamp[:10]


def _next_day(today: str) -> str:
    year_text, month_text, day_text = today.split("-")
    found = date(int(year_text), int(month_text), int(day_text)) + timedelta(days=1)
    return found.isoformat()
