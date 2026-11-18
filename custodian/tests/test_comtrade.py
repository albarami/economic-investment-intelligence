"""Comtrade registry, free-plan fetch and planted guards. Invented responses only."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

import pytest
from custodian.tests.fixtures.comtrade.invented import (
    HOST,
    MARKER,
    body_for,
    invented_entry,
    invented_policy,
    policy_document,
    trusted_source,
)

from eii_custodian.publicdata.comtrade.assemble import assemble
from eii_custodian.publicdata.comtrade.fetch import (
    fetch_source,
    refuse_committed_sentinel,
)
from eii_custodian.publicdata.comtrade.parse import ParseError, parse_body
from eii_custodian.publicdata.comtrade.partition import initial_partitions
from eii_custodian.publicdata.comtrade.policy import (
    PolicyError,
    SafeRefusal,
    activation_check,
    direction_ok,
    parse_policy,
)
from eii_custodian.publicdata.comtrade.state import StateError, accept, fresh
from eii_custodian.publicdata.fetch.allowlist import approve, approve_closed
from eii_custodian.publicdata.fetch.registry import load_registry, nightly_blocked
from eii_custodian.publicdata.fetch.transport import (
    AttemptResult,
    OpenerFault,
    PreparedRequest,
    SlotSecrets,
    perform,
)

ROOT = Path(__file__).resolve().parents[2]


def _clock() -> str:
    return "2026-11-16T08:00:00Z"


def _later() -> str:
    return "2026-11-17T08:00:00Z"


def _sleep(_seconds: float) -> None:
    return None


def _ok(request: PreparedRequest) -> AttemptResult:
    return AttemptResult("ok", body_for(request))


def test_query_key_is_refused_before_transport(tmp_path: Path) -> None:
    """An invented query credential is refused before any send and stays out of files."""
    url = "https://www.data.gov.qa/data/v1/get?subscription-key=" + MARKER
    sent: list[str] = []

    def transport(target: str) -> str:
        sent.append(target)
        return target

    decision = approve(url)
    if decision.ok:
        transport(url)
    assert decision.ok is False
    assert sent == []
    assert MARKER not in decision.reason
    assert MARKER not in decision.host
    (tmp_path / "diag.txt").write_text(
        decision.reason + "\n" + decision.host + "\n", encoding="utf-8"
    )
    assert MARKER not in (tmp_path / "diag.txt").read_text(encoding="utf-8")


def test_userinfo_fragment_and_closed_query_are_refused() -> None:
    """User-info, a fragment and a query outside the closed selectors are refused."""
    marked = approve(f"https://{MARKER}@www.data.gov.qa/data")
    assert marked.ok is False
    assert MARKER not in marked.reason
    assert approve("https://www.data.gov.qa/data#part").ok is False
    closed = (("reporter", "QAT"),)
    url = f"https://{HOST}/data/v1/get?reporter=QAT&extra={MARKER}"
    decision = approve_closed(url, hosts=frozenset({HOST}), selectors=closed)
    assert decision.ok is False
    assert MARKER not in decision.reason


def test_reporter_and_mirror_descriptors_and_planted_reversal(tmp_path: Path) -> None:
    """Qatar is the reporter. A mirror uses the partner as reporter. Reversals never send."""
    policy = invented_policy()
    cells = initial_partitions(policy)
    reporter = next(cell for cell in cells if cell.series_role == "reporter")
    mirror = next(cell for cell in cells if cell.series_role == "mirror")
    reporter_request = reporter.descriptor(policy, "keyed")
    mirror_request = mirror.descriptor(policy, "keyed")
    assert reporter_request.reporter_code == "QAT"
    assert reporter_request.partner_code == "ZZA"
    assert mirror_request.reporter_code == "ZZA"
    assert mirror_request.partner_code == "QAT"
    assert direction_ok(policy, reporter_request)
    assert direction_ok(policy, mirror_request)
    reversed_request = replace(
        reporter_request, reporter_code="ZZA", partner_code="QAT"
    )
    mixed = replace(mirror_request, reporter_code="QAT", partner_code="ZZA")
    sent: list[str] = []

    def opener(request: PreparedRequest) -> AttemptResult:
        sent.append(request.url)
        return _ok(request)

    for planted in (reversed_request, mixed):
        try:
            perform(policy, planted, "invented-header", opener)
        except SafeRefusal as exc:
            assert exc.check == "mirror_direction"
            assert MARKER not in str(exc)
        else:
            raise AssertionError("sent")
    assert sent == []
    result = fetch_source(
        invented_entry(),
        tmp_path,
        _clock,
        _sleep,
        opener,
        SlotSecrets("invented-header", ""),
    )
    assert result.failure is None
    assert (tmp_path / "un_comtrade" / "manifest.json").is_file()


def test_reversed_fetch_leaves_no_manifest(tmp_path: Path) -> None:
    """A fetch whose first cell is reversed does not write a complete manifest."""
    policy = invented_policy()
    entry = invented_entry(policy)

    def opener(request: PreparedRequest) -> AttemptResult:
        raise AssertionError(request.url)

    cells = initial_partitions(policy)
    bad = cells[0].descriptor(policy, "keyed")
    bad = replace(bad, series_role="reporter", reporter_code="ZZA", partner_code="QAT")
    with pytest.raises(SafeRefusal) as caught:
        perform(policy, bad, "invented-header", opener)
    assert caught.value.check == "mirror_direction"
    assert not (tmp_path / entry.key / "manifest.json").exists()


def test_header_marker_stays_in_the_opener_only(tmp_path: Path) -> None:
    """The invented marker is only the in-memory header, never a stored field."""
    seen: list[tuple[str, str]] = []

    def opener(request: PreparedRequest) -> AttemptResult:
        seen.append((request.header_name, request.header_value))
        assert MARKER not in request.url
        return _ok(request)

    result = fetch_source(
        invented_entry(),
        tmp_path,
        _clock,
        _sleep,
        opener,
        SlotSecrets(MARKER, ""),
    )
    assert result.failure is None
    assert seen
    assert {pair[0] for pair in seen} == {"Ocp-Apim-Subscription-Key"}
    assert {pair[1] for pair in seen} == {MARKER}
    blob = "\n".join(
        path.read_text(encoding="utf-8")
        for path in tmp_path.rglob("*")
        if path.is_file()
    )
    assert MARKER not in blob


def test_injected_transport_reads_no_environment() -> None:
    """An injected transport does not read the environment. The live boundary reads two names."""
    from commands.build_public import PRIMARY_ENV, SECONDARY_ENV, slot_secrets

    class Spy(Mapping[str, str]):
        def __init__(self) -> None:
            self.seen: list[str] = []
            self._data = {PRIMARY_ENV: MARKER, SECONDARY_ENV: MARKER}

        def __getitem__(self, key: str) -> str:
            self.seen.append(key)
            return self._data[key]

        def __iter__(self):
            return iter(self._data)

        def __len__(self) -> int:
            return len(self._data)

    injected = Spy()
    assert slot_secrets(injected, injected=True) is None
    assert injected.seen == []
    live = Spy()
    found = slot_secrets(live, injected=False)
    assert found is not None
    assert live.seen == []
    assert "redacted" in repr(found)
    assert MARKER not in repr(found)


def test_activation_refuses_basis_bounds_and_period_mismatches(tmp_path: Path) -> None:
    """Planted basis, count and period mismatches name the failed check and do not send."""
    entry = invented_entry()
    sent: list[str] = []

    def opener(request: PreparedRequest) -> AttemptResult:
        sent.append(request.url)
        return _ok(request)

    cases = (
        (
            replace(entry, licence_basis="owner_decision", decision_record="0026"),
            "licence_basis",
        ),
        (replace(entry, row_count_max=(entry.row_count_max or 0) + 1), "count_bounds"),
        (replace(entry, period_last="2098"), "period_bounds"),
        (
            invented_entry(invented_policy(frequencies=["monthly"], periods=["2099"])),
            "period_frequency",
        ),
    )
    for planted, check in cases:
        result = fetch_source(
            planted,
            tmp_path / check,
            _clock,
            _sleep,
            opener,
            SlotSecrets("invented-header", ""),
        )
        assert result.failure is not None
        assert result.failure.check == check
        assert not (tmp_path / check / "un_comtrade" / "manifest.json").exists()
    assert sent == []


def test_documents_and_registry_agree_on_provider_terms() -> None:
    """The row and DAT-85 / PUB-12 name provider_terms. A planted owner_decision does not."""
    entry = next(item for item in load_registry() if item.source_id == "un_comtrade")
    assert entry.licence_basis == "provider_terms"
    assert entry.decision_record == ""
    assert entry.commit_allowed is False
    assert entry.nightly_live_fetch is False
    assert entry.skip_reason == "metadata_unconfirmed"
    assert nightly_blocked(load_registry(), ("un_comtrade",)) == ("un_comtrade",)
    contracts = (ROOT / "docs/03_DATA_CONTRACTS.md").read_text(encoding="utf-8")
    pack = (ROOT / "docs/04_PUBLIC_DATA_PACK.md").read_text(encoding="utf-8")
    assert "un_comtrade" in contracts
    assert "provider_terms" in contracts
    assert "un_comtrade" in pack
    planted = activation_check(
        invented_policy(),
        row_count_min=1,
        row_count_max=64,
        period_first="2099",
        period_last="2099-01",
        licence_basis="owner_decision",
        decision_record="0026",
    )
    assert planted == "licence_basis"
    with_extra = dict(policy_document())
    with_extra["ranking"] = "invented"
    try:
        parse_policy(with_extra)
    except PolicyError as exc:
        assert "unknown" in exc.detail
    else:
        raise AssertionError("unknown field")


def test_exact_limit_splits_and_an_indivisible_leaf_does_not_complete(
    tmp_path: Path,
) -> None:
    """A count equal to the cap is split. A capped leaf with no further split writes no manifest."""
    policy = invented_policy(keyed_record_limit=2, daily_calls=40)
    entry = invented_entry(policy)

    def opener(request: PreparedRequest) -> AttemptResult:
        query = dict(parse_qsl(urlsplit(request.url).query))
        count = 1 if "product" in query else 2
        return AttemptResult("ok", body_for(request, count=count))

    result = fetch_source(
        entry,
        tmp_path / "split",
        _clock,
        _sleep,
        opener,
        SlotSecrets("invented-header", "invented-secondary"),
    )
    assert result.failure is None
    assert (tmp_path / "split" / "un_comtrade" / "manifest.json").is_file()

    def capped(request: PreparedRequest) -> AttemptResult:
        return AttemptResult("ok", body_for(request, count=1))

    leaf = invented_policy(
        keyed_record_limit=1,
        subdivision_fields=[],
        subdivision_values={},
        daily_calls=5,
        frequencies=["annual"],
        periods=["2099"],
        flows=["flow-in"],
    )
    refused = fetch_source(
        invented_entry(leaf),
        tmp_path / "leaf",
        _clock,
        _sleep,
        capped,
        SlotSecrets("invented-header", ""),
    )
    assert refused.failure is not None
    assert refused.failure.check == "unresolved_truncation"
    assert not (tmp_path / "leaf" / "un_comtrade" / "manifest.json").exists()


def test_public_cap_and_truncation_flag(tmp_path: Path) -> None:
    """The public class uses its own cap, and a truncation flag writes no manifest."""
    policy = invented_policy(
        public_record_limit=2,
        frequencies=["annual"],
        periods=["2099"],
        flows=["flow-in"],
        daily_calls=10,
    )
    seen: list[str] = []

    def opener(request: PreparedRequest) -> AttemptResult:
        seen.append(request.header_name)
        query = dict(parse_qsl(urlsplit(request.url).query))
        count = 1 if "product" in query else 2
        return AttemptResult("ok", body_for(request, count=count))

    result = fetch_source(
        invented_entry(policy),
        tmp_path / "public",
        _clock,
        _sleep,
        opener,
        SlotSecrets("", ""),
        api_class="public",
    )
    assert result.failure is None
    assert seen
    assert set(seen) == {""}
    capped_policy = invented_policy(
        frequencies=["annual"],
        periods=["2099"],
        flows=["flow-in"],
        daily_calls=1,
    )
    sent: list[str] = []

    def capped_opener(request: PreparedRequest) -> AttemptResult:
        sent.append(request.url)
        return _ok(request)

    capped = fetch_source(
        invented_entry(capped_policy),
        tmp_path / "public-day",
        _clock,
        _sleep,
        capped_opener,
        SlotSecrets("", ""),
        api_class="public",
    )
    assert capped.failure is not None
    assert capped.failure.check == "budget_exhausted"
    assert len(sent) == 1

    def flagged(request: PreparedRequest) -> AttemptResult:
        return AttemptResult("ok", body_for(request, truncated=True))

    refused = fetch_source(
        invented_entry(policy),
        tmp_path / "flag",
        _clock,
        _sleep,
        flagged,
        None,
        api_class="public",
    )
    assert refused.failure is not None
    assert refused.failure.check == "truncation"
    assert not (tmp_path / "flag" / "un_comtrade" / "manifest.json").exists()


def test_secondary_follows_only_primary_exhaustion(tmp_path: Path) -> None:
    """Secondary is used after the primary allowance, and not on auth, throttle or absence."""
    policy = invented_policy(
        daily_calls=1,
        frequencies=["annual"],
        periods=["2099"],
        flows=["flow-in"],
    )
    headers: list[str] = []

    def opener(request: PreparedRequest) -> AttemptResult:
        headers.append(request.header_value)
        return _ok(request)

    done = fetch_source(
        invented_entry(policy),
        tmp_path / "rotate",
        _clock,
        _sleep,
        opener,
        SlotSecrets("primary-marker", "secondary-marker"),
    )
    assert done.failure is None
    assert headers == ["primary-marker", "secondary-marker"]

    def auth(request: PreparedRequest) -> AttemptResult:
        headers.append("auth:" + request.header_value)
        return AttemptResult("auth", b"{}", error_text=MARKER)

    headers.clear()
    refused = fetch_source(
        invented_entry(policy),
        tmp_path / "auth",
        _clock,
        _sleep,
        auth,
        SlotSecrets("primary-marker", "secondary-marker"),
    )
    assert refused.failure is not None
    assert refused.failure.check == "authentication"
    assert headers == ["auth:primary-marker"]
    assert MARKER not in str(refused.failure)

    def throttle(request: PreparedRequest) -> AttemptResult:
        headers.append(request.header_value)
        return AttemptResult("throttle", b"{}")

    headers.clear()
    slept: list[float] = []
    throttled = fetch_source(
        invented_entry(
            invented_policy(
                daily_calls=8,
                frequencies=["annual"],
                periods=["2099"],
                flows=["flow-in"],
            )
        ),
        tmp_path / "throttle",
        _clock,
        slept.append,
        throttle,
        SlotSecrets("primary-marker", "secondary-marker"),
    )
    assert throttled.failure is not None
    assert throttled.failure.check == "throttled"
    assert headers == ["primary-marker"]
    assert slept == []

    absent_calls: list[str] = []

    def absent_opener(request: PreparedRequest) -> AttemptResult:
        absent_calls.append(request.url)
        return _ok(request)

    absent = fetch_source(
        invented_entry(policy),
        tmp_path / "absent",
        _clock,
        _sleep,
        absent_opener,
        SlotSecrets("", "secondary-marker"),
    )
    assert absent.failure is not None
    assert absent.failure.check == "primary_absent"
    assert absent_calls == []
    early = fetch_source(
        invented_entry(policy),
        tmp_path / "early",
        _clock,
        _sleep,
        absent_opener,
        SlotSecrets("primary-marker", "secondary-marker"),
        requested_slot="secondary",
    )
    assert early.failure is not None
    assert early.failure.check == "premature_secondary"
    assert absent_calls == []


def test_forbidden_hosts_and_redirects_do_not_send(tmp_path: Path) -> None:
    """Unlisted hosts, forbidden families and credential redirects are refused first."""
    policy = invented_policy()
    entry = invented_entry(policy)
    cell = initial_partitions(policy)[0].descriptor(policy, "keyed")
    sent: list[str] = []

    def opener(request: PreparedRequest) -> AttemptResult:
        sent.append(request.url)
        return AttemptResult("ok", body_for(request), location="")

    for family in ("deliver", "bulk", "async"):
        planted = replace(cell, endpoint_family=family)
        with pytest.raises(SafeRefusal) as caught:
            perform(policy, planted, "invented-header", opener)
        assert caught.value.check == "forbidden_endpoint"
    assert sent == []
    with pytest.raises(SafeRefusal) as missing:
        perform(
            policy, replace(cell, endpoint_family="missing"), "invented-header", opener
        )
    assert missing.value.check == "blocked_host"
    redirected = AttemptResult(
        "ok",
        body_for(cell and _dummy_request()),
        location=f"https://evil.example/{MARKER}",
    )

    def redirect_opener(request: PreparedRequest) -> AttemptResult:
        sent.append(request.url)
        return AttemptResult(
            "ok", body_for(request), location="https://evil.example/data"
        )

    with pytest.raises(SafeRefusal) as redirected_refusal:
        perform(policy, cell, "invented-header", redirect_opener)
    assert redirected_refusal.value.check == "redirect_host"
    assert "evil.example" not in str(redirected_refusal.value)
    assert all("evil.example" not in url for url in sent)

    def cross(request: PreparedRequest) -> AttemptResult:
        return AttemptResult(
            "ok",
            body_for(request),
            location="https://invented-redirect.example/data/v1/get",
            header_echo=MARKER,
        )

    with pytest.raises(SafeRefusal) as crossed:
        perform(policy, cell, "invented-header", cross)
    assert crossed.value.check == "cross_origin_credential"
    assert MARKER not in str(crossed.value)
    result = fetch_source(
        entry,
        tmp_path,
        _clock,
        _sleep,
        redirect_opener,
        SlotSecrets("invented-header", ""),
    )
    assert result.failure is not None
    blob = "\n".join(
        path.read_text(encoding="utf-8", errors="replace")
        for path in tmp_path.rglob("*")
        if path.is_file()
    )
    assert MARKER not in blob
    assert "evil.example" not in blob
    del redirected


def _dummy_request() -> PreparedRequest:
    return PreparedRequest("https://invented.example/data/v1/get", "", "", "id")


def test_secret_in_error_is_absent_from_message_and_files(tmp_path: Path) -> None:
    """A marker in an exception, a body, a header echo or a location is not stored."""

    def explode(request: PreparedRequest) -> AttemptResult:
        raise OpenerFault(MARKER + request.url)

    result = fetch_source(
        invented_entry(), tmp_path, _clock, _sleep, explode, SlotSecrets(MARKER, "")
    )
    assert result.failure is not None
    assert result.failure.check == "provider_error"
    assert MARKER not in str(result.failure)
    assert "https://" in str(result.failure)
    assert "un_comtrade" in str(result.failure)
    blob = "\n".join(
        path.read_text(encoding="utf-8", errors="replace")
        for path in tmp_path.rglob("*")
        if path.is_file()
    )
    assert MARKER not in blob


def test_budget_stop_resumes_the_next_day_without_a_duplicate(tmp_path: Path) -> None:
    """Exhaustion stops the same day. The next day continues and does not repeat a child."""
    policy = invented_policy(
        daily_calls=1,
        frequencies=["annual"],
        periods=["2099"],
        flows=["flow-in"],
    )
    seen: list[str] = []

    def opener(request: PreparedRequest) -> AttemptResult:
        seen.append(request.url)
        return _ok(request)

    cache = tmp_path / "cache"
    first = fetch_source(
        invented_entry(policy),
        cache,
        _clock,
        _sleep,
        opener,
        SlotSecrets("primary-marker", ""),
    )
    assert first.failure is not None
    assert first.failure.check == "budget_exhausted"
    assert not (cache / "un_comtrade" / "manifest.json").exists()
    assert len(seen) == 1
    second = fetch_source(
        invented_entry(policy),
        cache,
        _later,
        _sleep,
        opener,
        SlotSecrets("primary-marker", ""),
    )
    assert second.failure is None
    assert len(seen) == 2
    assert seen[0] != seen[1]


def test_changed_selection_and_lock_are_refused(tmp_path: Path) -> None:
    """A changed selection keeps the old counters, and a held lock does not write a manifest."""
    wide = invented_policy(frequencies=["annual"], periods=["2099"], flows=["flow-in"])
    cache = tmp_path / "cache"
    assert (
        fetch_source(
            invented_entry(wide),
            cache,
            _clock,
            _sleep,
            _ok,
            SlotSecrets("invented-header", ""),
        ).failure
        is None
    )
    narrow = invented_policy(
        frequencies=["annual"], periods=["2098"], flows=["flow-in"]
    )
    changed = fetch_source(
        invented_entry(narrow),
        cache,
        _clock,
        _sleep,
        _ok,
        SlotSecrets("invented-header", ""),
    )
    assert changed.failure is not None
    assert changed.failure.check == "selection_changed"
    locked = tmp_path / "locked"
    (locked / "un_comtrade").mkdir(parents=True)
    (locked / "un_comtrade" / "state.lock").write_text("held", encoding="utf-8")
    held = fetch_source(
        invented_entry(wide),
        locked,
        _clock,
        _sleep,
        _ok,
        SlotSecrets("invented-header", ""),
    )
    assert held.failure is not None
    assert held.failure.check == "state_locked"
    assert not (locked / "un_comtrade" / "manifest.json").exists()


def test_commit_sentinel_and_coverage_gap(tmp_path: Path) -> None:
    """Unread terms reject a committed sentinel. A missing cell keeps the gap and the price reason."""
    entry = invented_entry()
    candidate = tmp_path / "candidate.txt"
    candidate.write_text("invented-sentinel", encoding="utf-8")
    try:
        refuse_committed_sentinel(entry, candidate, "invented-sentinel")
    except SafeRefusal as exc:
        assert exc.check == "commit_forbidden"
    else:
        raise AssertionError("sentinel")
    policy = invented_policy(
        frequencies=["annual", "monthly"],
        periods=["2099"],
        flows=["flow-in"],
        price_amount="12.50",
        price_currency="XXX",
        price_retrieved_on="2026-11-16",
        price_source="invented-price-page",
        price_unavailable_reason="",
    )
    # monthly is required by the frequency list, so this policy fails activation
    # unless the period list includes a month. Use a complete selection and drop
    # one response instead.
    del policy
    called = {"n": 0}

    def drop_one(request: PreparedRequest) -> AttemptResult:
        called["n"] += 1
        if called["n"] == 1:
            raise OpenerFault("stop")
        return _ok(request)

    result = fetch_source(
        invented_entry(),
        tmp_path / "gap",
        _clock,
        _sleep,
        drop_one,
        SlotSecrets("invented-header", "invented-secondary"),
    )
    assert result.failure is not None
    coverage = json.loads(
        (tmp_path / "gap" / "un_comtrade" / "coverage.json").read_text(encoding="utf-8")
    )
    assert coverage["gap_cells"] > 0
    assert coverage["price_unavailable_reason"] == "price_not_recorded"
    assert coverage["requested_cells"] > coverage["present_cells"]
    assert not (tmp_path / "gap" / "un_comtrade" / "manifest.json").exists()


def test_null_measure_and_unit_mapping(tmp_path: Path) -> None:
    """A null quantity stays null, and a unit outside the closed mapping is refused."""
    result = fetch_source(
        invented_entry(),
        tmp_path,
        _clock,
        _sleep,
        _ok,
        SlotSecrets("invented-header", ""),
    )
    assert result.failure is None
    assembled = assemble(
        tmp_path,
        "un_comtrade",
        invented_policy(),
        manifest_sha256=result.digest,
        **trusted_source(),
    )
    quantities = [row for row in assembled.rows if row.measure == "net_weight"]
    assert quantities
    assert all(row.value is None for row in quantities)
    assert all(row.unit == "invented-mass" for row in quantities)
    assert assembled.gap_cells == 0
    bad = invented_policy(measure_units=[{"measure": "trade_value", "unit": "XXX"}])
    refused = fetch_source(
        invented_entry(bad),
        tmp_path / "unit",
        _clock,
        _sleep,
        _ok,
        SlotSecrets("invented-header", ""),
    )
    assert refused.failure is not None
    assert refused.failure.check == "unit_mapping"


def test_duplicate_accept_is_refused() -> None:
    """A second accept of the same partition is refused."""
    ledger = fresh("a" * 64, "b" * 64, ("cell",), "2026-11-16")
    once = accept(ledger, "cell", "c" * 64)
    planted = (
        once,
        replace(once, child_sha256=()),
        replace(once, completed=()),
    )
    for item in planted:
        try:
            accept(item, "cell", "d" * 64)
        except StateError as exc:
            assert exc.check == "duplicate_partition"
        else:
            raise AssertionError("duplicate")


def test_interrupted_manifest_is_not_complete(tmp_path: Path) -> None:
    """A failed manifest replace leaves no complete manifest."""
    real = os.replace

    def boom(src: str | os.PathLike[str], dst: str | os.PathLike[str]) -> None:
        if str(dst).endswith("manifest.json"):
            raise OSError("interrupted")
        real(src, dst)

    os.replace = boom
    try:
        result = fetch_source(
            invented_entry(),
            tmp_path,
            _clock,
            _sleep,
            _ok,
            SlotSecrets("invented-header", ""),
        )
    finally:
        os.replace = real
    assert result.failure is not None
    assert result.failure.check == "write_failed"
    assert not (tmp_path / "un_comtrade" / "manifest.json").exists()
    assert not (tmp_path / "un_comtrade" / ".manifest.json.partial").exists()


def test_planted_policy_shapes_are_refused() -> None:
    """Closed policy shapes that are empty, doubled or forbidden are refused."""
    document = policy_document()
    both = dict(document)
    both["price_amount"] = "1.00"
    both["price_unavailable_reason"] = "price_not_recorded"
    neither = dict(document)
    neither["price_amount"] = ""
    neither["price_unavailable_reason"] = ""
    scale = dict(document)
    scale["value_scale"] = scale["value_precision"]
    negative = dict(document)
    bounds = dict(document["count_bounds"])
    bounds["minimum"] = -1
    negative["count_bounds"] = bounds
    periods = dict(document)
    periods["periods"] = ["2099", "2099"]
    forbidden = dict(document)
    templates = [dict(item) for item in document["endpoint_templates"]]
    templates[0] = dict(templates[0])
    templates[0]["family"] = "bulk"
    forbidden["endpoint_templates"] = templates
    hidden = dict(document)
    hidden_templates = [dict(item) for item in document["endpoint_templates"]]
    hidden_templates[0] = dict(hidden_templates[0])
    hidden_templates[0]["path"] = "/data/v1/deliver"
    hidden["endpoint_templates"] = hidden_templates
    cases = (
        (both, "price evidence"),
        (neither, "price evidence"),
        (scale, "value_scale"),
        (negative, "count_bounds"),
        (
            {"confirmed": False, "version": "invented-1"},
            "unconfirmed policy has fields",
        ),
        (periods, "periods"),
        (forbidden, "endpoint_templates"),
        (hidden, "endpoint_templates"),
        ("not-a-map", "not a map"),
    )
    for raw, needle in cases:
        try:
            parse_policy(raw)
        except PolicyError as exc:
            assert needle in str(exc)
        else:
            raise AssertionError(needle)


def test_parser_refuses_a_number_a_short_total_and_extra_scale() -> None:
    """A JSON number, a short count and a too-fine decimal are named refusals."""
    policy = invented_policy()
    cell = next(
        item for item in initial_partitions(policy) if item.series_role == "reporter"
    )
    descriptor = cell.descriptor(policy, "keyed")
    record = {
        "reporterCode": descriptor.reporter_code,
        "partnerCode": descriptor.partner_code,
        "partner2Code": None,
        "period": descriptor.period,
        "flowCode": descriptor.flow_code,
        "cmdCode": descriptor.chapter,
        "primaryValue": "1.25",
        "qty": None,
        "flag": "",
        "classificationCode": "HS-INVENTED",
        "classificationRevision": descriptor.classification_revision,
        "aggregationLevel": 2,
        "customsCode": "customs-invented",
        "transportCode": "mode-invented",
        "valuationBasis": "value-invented",
    }
    numbered = dict(record)
    numbered["primaryValue"] = 1.25
    short = {"count": 2, "truncated": False, "error": None, "data": [record]}
    fine = dict(record)
    fine["primaryValue"] = "1.123"
    infinite = dict(record)
    infinite["primaryValue"] = "Infinity"
    bodies = (
        (
            {"count": 1, "truncated": False, "error": None, "data": [numbered]},
            "value_type",
        ),
        (short, "short_total"),
        (
            {"count": 1, "truncated": False, "error": None, "data": [fine]},
            "value_overflow",
        ),
        (
            {"count": 1, "truncated": False, "error": None, "data": [infinite]},
            "value_type",
        ),
    )
    for payload, check in bodies:
        try:
            parse_body(
                json.dumps(payload).encode("utf-8"),
                policy,
                descriptor,
                source_version=policy.version,
                receipt_sha256="",
            )
        except ParseError as exc:
            assert exc.check == check
        else:
            raise AssertionError(check)


def test_assemble_refuses_a_changed_child(tmp_path: Path) -> None:
    """A child whose bytes no longer match the manifest digest is refused."""
    fetched = fetch_source(
        invented_entry(),
        tmp_path,
        _clock,
        _sleep,
        _ok,
        SlotSecrets("invented-header", ""),
    )
    assert fetched.failure is None
    folder = tmp_path / "un_comtrade"
    skipped = {"manifest.json", "coverage.json", "state.json"}
    children = [
        item
        for item in folder.glob("*.json")
        if item.name not in skipped and not item.name.endswith(".meta.json")
    ]
    children[0].write_bytes(children[0].read_bytes() + b" ")
    try:
        assemble(
            tmp_path,
            "un_comtrade",
            invented_policy(),
            manifest_sha256=fetched.digest,
            **trusted_source(),
        )
    except SafeRefusal as exc:
        assert exc.check == "child_hash"
    else:
        raise AssertionError("child_hash")
