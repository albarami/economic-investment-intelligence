"""Exact refusal text for the Comtrade fetch survivors. Invented inputs only."""

from __future__ import annotations

import json
import locale
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

import pytest
from custodian.tests.fixtures.comtrade.invented import (
    body_for,
    invented_entry,
    invented_policy,
)

from eii_custodian.publicdata.comtrade.fetch import (
    fetch_source,
    refuse_committed_sentinel,
)
from eii_custodian.publicdata.comtrade.policy import (
    Policy,
    SafeRefusal,
    UnconfirmedPolicy,
)
from eii_custodian.publicdata.comtrade.state import read_ledger
from eii_custodian.publicdata.fetch.transport import (
    AttemptResult,
    PreparedRequest,
    SlotSecrets,
)

KEYED_HOST = "trade-closed.invalid"
PUBLIC_HOST = "trade-open.invalid"
STOPPED_URL = f"https://{PUBLIC_HOST}/refused"
UNCONFIRMED_URL = "https://invalid.example/refused"
DAY = "2026-11-16T08:00:00Z"
NEXT_DAY = "2026-11-17"
CHAPTER = "ch-a"
FLOW = "flow-in"
PERIOD = "2099"
REVISION = "HS-INVENTED"
HEADER = "invented-header"
PUBLISHER = "invented-café"


def _clock() -> str:
    return DAY


def _sleep(_seconds: float) -> None:
    return None


def _policy(**overrides: object) -> Policy:
    """Return a two-cell invented policy. The public template is the first host."""
    document: dict[str, object] = {
        "frequencies": ["annual"],
        "periods": [PERIOD],
        "flows": [FLOW],
        "chapters": [CHAPTER],
        "daily_calls": 8,
        "keyed_record_limit": 3,
        "public_record_limit": 2,
        "endpoint_templates": [
            {
                "api_class": "public",
                "family": "data",
                "host": PUBLIC_HOST,
                "path": "/public/v1/preview",
            },
            {
                "api_class": "keyed",
                "family": "data",
                "host": KEYED_HOST,
                "path": "/data/v1/get",
            },
        ],
        "allowed_redirect_hosts": [KEYED_HOST, PUBLIC_HOST],
        "price_amount": "9.50",
        "price_currency": "XXX",
        "price_retrieved_on": "2026-11-16",
        "price_source": "invented-price-page",
        "price_unavailable_reason": "",
    }
    document.update(overrides)
    return invented_policy(**document)


def _entry(policy: Policy, **changes: object):
    entry = invented_entry(policy)
    values: dict[str, object] = {
        "fetch_host": KEYED_HOST,
        "url": f"https://{KEYED_HOST}/data/v1/get",
        "publisher": PUBLISHER,
        "landing_url": f"https://{KEYED_HOST}/evidence",
    }
    values.update(changes)
    return replace(entry, **values)


def _full(failure: SafeRefusal, text: str) -> None:
    """Compare one refusal with a full hand-written message."""
    assert str(failure) == text
    assert failure.source_id == "un_comtrade"
    assert failure.check == text.split(" ")[2]
    assert failure.safe_url == text.split(" ")[1]
    assert failure.endpoint_id == text.split("endpoint=", 1)[1]


def _shape(
    result: object,
    text: str,
    host: str,
    requested: int,
    present: int,
    gap: int,
) -> None:
    failure = getattr(result, "failure", None)
    assert isinstance(failure, SafeRefusal)
    _full(failure, text)
    assert getattr(result, "digest", None) == ""
    assert getattr(result, "host", None) == host
    assert getattr(result, "requested_cells", None) == requested
    assert getattr(result, "present_cells", None) == present
    assert getattr(result, "gap_cells", None) == gap


def _run(
    tmp_path: Path,
    entry: object,
    opener: Callable[[PreparedRequest], AttemptResult],
    slots: SlotSecrets | None,
    *,
    clock: Callable[[], str] | None = None,
    api_class: str = "keyed",
    requested_slot: str | None = None,
):
    return fetch_source(
        entry,
        tmp_path,
        _clock if clock is None else clock,
        _sleep,
        opener,
        slots,
        api_class=api_class,
        requested_slot=requested_slot,
    )


def _ok(request: PreparedRequest) -> AttemptResult:
    return AttemptResult("ok", body_for(request))


def _silent(request: PreparedRequest) -> AttemptResult:
    raise AssertionError(request.url)


def _url(role: str, *, api: str = "keyed", flow: str = FLOW, product: str = "") -> str:
    if role == "mirror":
        reporter, partner = "ZZA", "QAT"
    else:
        reporter, partner = "QAT", "ZZA"
    host = KEYED_HOST if api == "keyed" else PUBLIC_HOST
    path = "/data/v1/get" if api == "keyed" else "/public/v1/preview"
    pairs = [
        ("chapter", CHAPTER),
        ("flow", flow),
        ("frequency", "annual"),
        ("partner", partner),
        ("period", PERIOD),
        ("reporter", reporter),
        ("revision", REVISION),
        ("role", role),
    ]
    if product:
        pairs.append(("product", product))
    query = "&".join(f"{name}={value}" for name, value in pairs)
    return f"https://{host}{path}?{query}"


def _endpoint(role: str, *, api: str = "keyed", product: str = "") -> str:
    if role == "mirror":
        reporter, partner = "ZZA", "QAT"
    else:
        reporter, partner = "QAT", "ZZA"
    base = (
        f"{api}/data/{role}/{reporter}/{partner}/annual/{PERIOD}/{FLOW}/"
        f"{CHAPTER}/{REVISION}"
    )
    if product:
        return base + f"/product={product}"
    return base


def _message(check: str, url: str, endpoint: str) -> str:
    return f"un_comtrade {url} {check} endpoint={endpoint}"


def _stopped(check: str) -> str:
    return _message(check, STOPPED_URL, check)


def _open(check: str) -> str:
    return _message(check, UNCONFIRMED_URL, "unconfirmed")


def _keyed(check: str, role: str = "mirror") -> str:
    return _message(check, _url(role), _endpoint(role))


def test_unconfirmed_and_foreign_policy_use_the_placeholder(tmp_path: Path) -> None:
    """A policy that is not activated stops before any host is chosen."""
    foreign = replace(invented_entry(_policy()), comtrade_policy=object())
    unconfirmed = replace(
        invented_entry(_policy()), comtrade_policy=UnconfirmedPolicy()
    )
    named = (("foreign", foreign), ("unconfirmed", unconfirmed))
    for name, entry in named:
        result = _run(tmp_path / name, entry, _silent, None)
        _shape(result, _open("metadata_unconfirmed"), "", 0, 0, 0)


def test_activation_failure_keeps_the_policy_out_of_the_refusal(tmp_path: Path) -> None:
    """A failed activation names its check and the unconfirmed placeholder."""
    policy = _policy()
    entry = _entry(policy, licence_basis="dataset")
    result = _run(tmp_path, entry, _silent, SlotSecrets(HEADER, ""))
    _shape(result, _open("licence_basis"), "", 0, 0, 0)


def test_commit_names_the_first_host(tmp_path: Path) -> None:
    """A committed row stops with the first template host."""
    policy = _policy()
    result = _run(
        tmp_path, _entry(policy, commit_allowed=True), _silent, SlotSecrets(HEADER, "")
    )
    _shape(result, _stopped("commit_forbidden"), PUBLIC_HOST, 0, 0, 0)


def test_pending_terms_words_still_fetch_every_cell(tmp_path: Path) -> None:
    """Ruling L-1001: empty terms words never stop the comtrade fetch."""
    from eii_custodian.publicdata.fetch.receipts import sha256_hex

    policy = _policy()
    entry = _entry(policy, terms_words="")
    result = _run(tmp_path, entry, _ok, SlotSecrets(HEADER, ""))
    assert result.failure is None
    assert result.requested_cells == 2
    assert result.present_cells == 2
    assert result.gap_cells == 0
    folder = tmp_path / entry.key
    metas = sorted(folder.glob("*.meta.json"))
    assert metas
    for path in metas:
        side = json.loads(path.read_text(encoding="utf-8"))
        assert side["terms_sha256"] == sha256_hex(b"")


def test_held_lock_names_its_check_and_the_first_host(tmp_path: Path) -> None:
    """A lock that already exists is state_locked, with the first template host."""
    folder = tmp_path / "un_comtrade"
    folder.mkdir()
    (folder / "state.lock").write_text("held", encoding="utf-8")
    result = _run(tmp_path, _entry(_policy()), _silent, SlotSecrets(HEADER, ""))
    _shape(result, _stopped("state_locked"), PUBLIC_HOST, 0, 0, 0)


def test_missing_slots_are_primary_absent_and_do_not_send(tmp_path: Path) -> None:
    """No reader means an empty header and no request."""
    result = _run(tmp_path, _entry(_policy()), _silent, None)
    _shape(
        result,
        _message("primary_absent", STOPPED_URL, "primary_absent"),
        KEYED_HOST,
        2,
        0,
        2,
    )
    ledger = read_ledger(tmp_path / "un_comtrade" / "state.json")
    assert ledger.next_eligible == NEXT_DAY
    assert ledger.incomplete == ("primary_absent",)
    assert ledger.primary_calls == 0


def test_premature_secondary_records_the_next_calendar_day(tmp_path: Path) -> None:
    """Asking for the secondary slot while the primary is open does not send."""
    result = _run(
        tmp_path,
        _entry(_policy()),
        _silent,
        SlotSecrets(HEADER, "invented-secondary"),
        requested_slot="secondary",
    )
    _shape(
        result,
        _message("premature_secondary", STOPPED_URL, "premature_secondary"),
        KEYED_HOST,
        2,
        0,
        2,
    )
    ledger = read_ledger(tmp_path / "un_comtrade" / "state.json")
    assert ledger.next_eligible == NEXT_DAY
    assert ledger.primary_calls == 0
    assert ledger.secondary_calls == 0


def test_secondary_budget_uses_the_exact_stop_and_the_next_day(tmp_path: Path) -> None:
    """The third call of a one-call day stops on the secondary budget."""
    policy = _policy(flows=["flow-in", "flow-out"], daily_calls=1)
    seen: list[str] = []

    def opener(request: PreparedRequest) -> AttemptResult:
        seen.append(request.url)
        return _ok(request)

    class _Filled:
        def read_slot(self, slot: str) -> str:
            del slot
            return HEADER

    result = _run(tmp_path, _entry(policy), opener, _Filled())
    _shape(
        result,
        _message("budget_exhausted", STOPPED_URL, "budget_exhausted"),
        KEYED_HOST,
        4,
        2,
        2,
    )
    assert seen == [
        _url("mirror", flow="flow-in"),
        _url("mirror", flow="flow-out"),
    ]
    ledger = read_ledger(tmp_path / "un_comtrade" / "state.json")
    assert ledger.primary_calls == 1
    assert ledger.secondary_calls == 1
    assert ledger.next_eligible == NEXT_DAY


def test_commit_allowed_refusal_is_the_whole_sentinel_message(tmp_path: Path) -> None:
    """A committed row is refused before the candidate is read."""
    entry = _entry(_policy(), commit_allowed=True)
    with pytest.raises(SafeRefusal) as caught:
        refuse_committed_sentinel(entry, tmp_path / "absent.txt", "invented-sentinel")
    _full(
        caught.value,
        "un_comtrade https://invalid.example/refused commit_forbidden endpoint=commit",
    )


def test_sentinel_in_a_file_uses_the_same_whole_message(tmp_path: Path) -> None:
    """A file that holds the sentinel is the same refusal, read as UTF-8."""
    entry = _entry(_policy())
    candidate = tmp_path / "candidate.txt"
    candidate.write_text("prefix invented-sentinel suffix", encoding="utf-8")
    with pytest.raises(SafeRefusal) as caught:
        refuse_committed_sentinel(entry, candidate, "invented-sentinel")
    _full(
        caught.value,
        "un_comtrade https://invalid.example/refused commit_forbidden endpoint=commit",
    )


def test_empty_sentinel_and_a_missing_file_are_not_refusals(tmp_path: Path) -> None:
    """An empty sentinel and a missing file do not refuse."""
    entry = _entry(_policy())
    present = tmp_path / "present.txt"
    present.write_text("invented-text", encoding="utf-8")
    refuse_committed_sentinel(entry, present, "")
    refuse_committed_sentinel(entry, tmp_path / "absent.txt", "invented-sentinel")


def test_non_ascii_sentinel_is_read_as_utf8(tmp_path: Path) -> None:
    """The sentinel comparison reads the candidate as UTF-8."""
    entry = _entry(_policy())
    candidate = tmp_path / "candidate.txt"
    candidate.write_bytes("invented-é".encode())
    previous = locale.setlocale(locale.LC_ALL)
    locale.setlocale(locale.LC_ALL, "C")
    try:
        with pytest.raises(SafeRefusal) as caught:
            refuse_committed_sentinel(entry, candidate, "invented-é")
    finally:
        locale.setlocale(locale.LC_ALL, previous)
    _full(
        caught.value,
        "un_comtrade https://invalid.example/refused commit_forbidden endpoint=commit",
    )


def test_class_without_a_template_uses_the_first_host(tmp_path: Path) -> None:
    """An API class with no template stops on the first template host."""
    result = _run(
        tmp_path,
        _entry(_policy()),
        _silent,
        SlotSecrets(HEADER, ""),
        api_class="absent",
    )
    assert result.failure is not None
    assert result.host == PUBLIC_HOST
    assert result.failure.check == "blocked_host"
