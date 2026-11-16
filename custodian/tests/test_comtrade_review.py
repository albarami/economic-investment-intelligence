"""Review fixes for the Comtrade adapter. Invented responses only."""

from __future__ import annotations

import json
import os
import pickle
from collections.abc import Mapping
from pathlib import Path
from urllib.parse import parse_qsl, quote, urlsplit

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
from eii_custodian.publicdata.comtrade.fetch import fetch_source
from eii_custodian.publicdata.comtrade.parse import ParseError, parse_body
from eii_custodian.publicdata.comtrade.partition import initial_partitions
from eii_custodian.publicdata.comtrade.policy import (
    SafeRefusal,
    policy_sha256,
)
from eii_custodian.publicdata.comtrade.state import StateError, fresh, load_or_new
from eii_custodian.publicdata.fetch.receipts import sha256_hex
from eii_custodian.publicdata.fetch.terms_text import terms_text_sha256
from eii_custodian.publicdata.fetch.transport import (
    AttemptResult,
    OpenerFault,
    PreparedRequest,
    SlotSecrets,
    perform,
)

PRIMARY = "primary-marker"
SECONDARY = "secondary-marker"


def _clock() -> str:
    return "2026-11-16T08:00:00Z"


def _later() -> str:
    return "2026-11-17T08:00:00Z"


def _sleep(_seconds: float) -> None:
    return None


def _narrow(**overrides: object):
    base: dict[str, object] = {
        "frequencies": ["annual"],
        "periods": ["2099"],
        "flows": ["flow-in"],
        "daily_calls": 8,
    }
    base.update(overrides)
    return invented_policy(**base)


def _record(descriptor: object) -> dict[str, object]:
    from eii_custodian.publicdata.comtrade.policy import Descriptor

    if not isinstance(descriptor, Descriptor):
        raise AssertionError("descriptor")
    return {
        "reporterCode": descriptor.reporter_code,
        "partnerCode": descriptor.partner_code,
        "partner2Code": None,
        "period": descriptor.period,
        "flowCode": descriptor.flow_code,
        "cmdCode": descriptor.chapter,
        "primaryValue": "1.25",
        "qty": None,
        "flag": "",
        "classificationCode": "HS-A",
        "classificationRevision": descriptor.classification_revision,
        "aggregationLevel": 2,
        "customsCode": "customs-invented",
        "transportCode": "mode-invented",
        "valuationBasis": "value-invented",
    }


def _parse(payload: dict[str, object], policy: object | None = None):
    chosen = invented_policy() if policy is None else policy
    cell = next(
        item for item in initial_partitions(chosen) if item.series_role == "reporter"
    )
    descriptor = cell.descriptor(chosen, "keyed")
    return parse_body(
        json.dumps(payload).encode("utf-8"),
        chosen,
        descriptor,
        source_version=chosen.version,
        receipt_sha256="ab" * 32,
    )


def test_throttle_on_the_last_primary_call_does_not_open_again(tmp_path: Path) -> None:
    """A throttle consumes the reserved call and does not open another."""
    calls: list[str] = []

    def opener(request: PreparedRequest) -> AttemptResult:
        calls.append(request.header_value)
        return AttemptResult("throttle", b"{}")

    result = fetch_source(
        invented_entry(_narrow(daily_calls=1)),
        tmp_path,
        _clock,
        _sleep,
        opener,
        SlotSecrets(PRIMARY, SECONDARY),
    )
    assert result.failure is not None
    assert result.failure.check == "throttled"
    assert calls == [PRIMARY]
    state = json.loads(
        (tmp_path / "un_comtrade" / "state.json").read_text(encoding="utf-8")
    )
    assert state["primary_calls"] == 1
    assert state["secondary_calls"] == 0
    assert not (tmp_path / "un_comtrade" / "manifest.json").exists()


def test_one_over_primary_does_not_open(tmp_path: Path) -> None:
    """The call after the primary allowance is not opened."""
    calls: list[str] = []

    def opener(request: PreparedRequest) -> AttemptResult:
        calls.append(request.header_value)
        return AttemptResult("ok", body_for(request))

    result = fetch_source(
        invented_entry(_narrow(daily_calls=1)),
        tmp_path,
        _clock,
        _sleep,
        opener,
        SlotSecrets(PRIMARY, ""),
    )
    assert result.failure is not None
    assert result.failure.check == "budget_exhausted"
    assert calls == [PRIMARY]


def test_throttle_on_the_last_secondary_call_does_not_open_again(
    tmp_path: Path,
) -> None:
    """After the primary allowance, one throttled secondary call stops the run."""
    calls: list[str] = []

    def opener(request: PreparedRequest) -> AttemptResult:
        calls.append(request.header_value)
        if request.header_value == SECONDARY:
            return AttemptResult("throttle", b"{}")
        return AttemptResult("ok", body_for(request))

    result = fetch_source(
        invented_entry(_narrow(daily_calls=1)),
        tmp_path,
        _clock,
        _sleep,
        opener,
        SlotSecrets(PRIMARY, SECONDARY),
    )
    assert result.failure is not None
    assert result.failure.check == "throttled"
    assert calls == [PRIMARY, SECONDARY]


def test_one_over_secondary_does_not_open(tmp_path: Path) -> None:
    """Both slots stop at the allowance. A further cell does not open."""
    calls: list[str] = []

    def opener(request: PreparedRequest) -> AttemptResult:
        calls.append(request.header_value)
        return AttemptResult("ok", body_for(request))

    result = fetch_source(
        invented_entry(_narrow(daily_calls=1, flows=["flow-in", "flow-out"])),
        tmp_path,
        _clock,
        _sleep,
        opener,
        SlotSecrets(PRIMARY, SECONDARY),
    )
    assert result.failure is not None
    assert result.failure.check == "budget_exhausted"
    assert calls == [PRIMARY, SECONDARY]


def test_public_throttle_and_one_over_open_only_the_allowance(tmp_path: Path) -> None:
    """Public requests stop on a throttle and do not open the call past the allowance."""
    throttled: list[str] = []

    def throttle(request: PreparedRequest) -> AttemptResult:
        throttled.append(request.header_name)
        return AttemptResult("throttle", b"{}")

    stopped = fetch_source(
        invented_entry(_narrow(daily_calls=1)),
        tmp_path / "throttle",
        _clock,
        _sleep,
        throttle,
        SlotSecrets(PRIMARY, SECONDARY),
        api_class="public",
    )
    assert stopped.failure is not None
    assert stopped.failure.check == "throttled"
    assert throttled == [""]
    opened: list[str] = []

    def ok(request: PreparedRequest) -> AttemptResult:
        opened.append(request.url)
        return AttemptResult("ok", body_for(request))

    over = fetch_source(
        invented_entry(_narrow(daily_calls=1)),
        tmp_path / "over",
        _clock,
        _sleep,
        ok,
        SlotSecrets(PRIMARY, SECONDARY),
        api_class="public",
    )
    assert over.failure is not None
    assert over.failure.check == "budget_exhausted"
    assert len(opened) == 1


def test_provider_error_and_credential_echo_are_not_stored(tmp_path: Path) -> None:
    """A provider error or a credential echo is refused before any body is stored."""

    def errored(request: PreparedRequest) -> AttemptResult:
        loaded = json.loads(body_for(request))
        loaded["error"] = "provider failed"
        return AttemptResult("ok", json.dumps(loaded).encode("utf-8"))

    refused = fetch_source(
        invented_entry(_narrow()),
        tmp_path / "error",
        _clock,
        _sleep,
        errored,
        SlotSecrets(MARKER, ""),
    )
    assert refused.failure is not None
    assert refused.failure.check == "provider_error"
    assert _stored_text(tmp_path / "error").count(MARKER) == 0
    assert "provider failed" not in _stored_text(tmp_path / "error")

    def echoed(request: PreparedRequest) -> AttemptResult:
        loaded = json.loads(body_for(request))
        loaded["data"][0]["flag"] = MARKER
        return AttemptResult("ok", json.dumps(loaded).encode("utf-8"))

    flagged = fetch_source(
        invented_entry(_narrow()),
        tmp_path / "flag",
        _clock,
        _sleep,
        echoed,
        SlotSecrets(MARKER, ""),
    )
    assert flagged.failure is not None
    assert MARKER not in _stored_text(tmp_path / "flag")
    assert MARKER not in str(flagged.failure)

    def ignored(request: PreparedRequest) -> AttemptResult:
        loaded = json.loads(body_for(request))
        loaded["note"] = MARKER
        return AttemptResult("ok", json.dumps(loaded).encode("utf-8"))

    extra = fetch_source(
        invented_entry(_narrow()),
        tmp_path / "ignored",
        _clock,
        _sleep,
        ignored,
        SlotSecrets(MARKER, ""),
    )
    assert extra.failure is not None
    assert MARKER not in _stored_text(tmp_path / "ignored")


def test_secret_in_a_selector_stays_out_of_the_refusal_and_repr() -> None:
    """An encoded selector and a header value never appear in a refusal or a repr."""
    policy = invented_policy()
    cell = initial_partitions(policy)[0].descriptor(policy, "keyed")
    planted = cell.__class__(
        **{
            **cell.__dict__,
            "chapter": MARKER,
        }
    )
    request = PreparedRequest(
        "https://invented.example/data", "Ocp-Apim-Subscription-Key", MARKER, "id"
    )
    assert MARKER not in repr(request)

    def opener(prepared: PreparedRequest) -> AttemptResult:
        raise OpenerFault(MARKER)

    with pytest.raises(SafeRefusal) as caught:
        perform(policy, planted, MARKER, opener)
    assert MARKER not in str(caught.value)
    assert quote(MARKER, safe="") not in str(caught.value)
    try:
        perform(policy, planted, MARKER, opener)
    except SafeRefusal:
        import traceback

        assert MARKER not in traceback.format_exc()
    else:
        raise AssertionError("refusal")


def test_published_dimensions_come_from_the_response() -> None:
    """Classification, customs, transport, valuation and aggregation are the published values."""
    policy = invented_policy()
    cell = next(
        item for item in initial_partitions(policy) if item.series_role == "reporter"
    )
    descriptor = cell.descriptor(policy, "keyed")
    first = _record(descriptor)
    second = dict(first)
    second["aggregationLevel"] = 6
    second["partner2Code"] = "row-b"
    payload = {"count": 2, "truncated": False, "error": None, "data": [first, second]}
    parsed = _parse(payload, policy)
    levels = sorted(
        row.aggregation_level for row in parsed.rows if row.measure == "trade_value"
    )
    assert levels == [2, 6]
    assert {row.classification for row in parsed.rows} == {"HS-A"}
    assert {row.customs_code for row in parsed.rows} == {"customs-invented"}
    assert {row.transport_mode_code for row in parsed.rows} == {"mode-invented"}
    assert {row.valuation_basis for row in parsed.rows} == {"value-invented"}
    assert parsed.rows[0].source_id == "un_comtrade"


def test_wrong_chapter_subdivision_and_missing_measure_are_refused() -> None:
    """A product outside the requested child, or a missing measure, is not a row."""
    policy = invented_policy()
    cell = next(
        item for item in initial_partitions(policy) if item.series_role == "reporter"
    )
    descriptor = cell.descriptor(policy, "keyed")
    descriptor = descriptor.__class__(
        **{**descriptor.__dict__, "subdivision": (("product", "ch-a-1"),)}
    )
    wrong = _record(descriptor)
    wrong["cmdCode"] = "ch-a-2"
    missing = _record(descriptor)
    missing["cmdCode"] = "ch-a-1"
    del missing["primaryValue"]
    explicit = _record(descriptor)
    explicit["cmdCode"] = "ch-a-1"
    explicit["primaryValue"] = None
    bodies = (
        (
            {"count": 1, "truncated": False, "error": None, "data": [wrong]},
            "product_membership",
        ),
        (
            {"count": 1, "truncated": False, "error": None, "data": [missing]},
            "measure_missing",
        ),
    )
    for payload, check in bodies:
        with pytest.raises(ParseError) as caught:
            parse_body(
                json.dumps(payload).encode("utf-8"),
                policy,
                descriptor,
                source_version=policy.version,
                receipt_sha256="",
            )
        assert caught.value.check == check
    parsed = parse_body(
        json.dumps(
            {"count": 1, "truncated": False, "error": None, "data": [explicit]}
        ).encode("utf-8"),
        policy,
        descriptor,
        source_version=policy.version,
        receipt_sha256="",
    )
    values = [row.value for row in parsed.rows if row.measure == "trade_value"]
    assert values == [None]


def test_decimal_capacity_uses_precision_and_scale() -> None:
    """Scale and integer capacity both refuse a value that does not fit."""
    policy = invented_policy()
    cell = next(
        item for item in initial_partitions(policy) if item.series_role == "reporter"
    )
    descriptor = cell.descriptor(policy, "keyed")

    def one(text: str) -> None:
        record = _record(descriptor)
        record["primaryValue"] = text
        parse_body(
            json.dumps(
                {"count": 1, "truncated": False, "error": None, "data": [record]}
            ).encode("utf-8"),
            policy,
            descriptor,
            source_version=policy.version,
            receipt_sha256="",
        )

    one("9999.99")
    one("-9999.99")
    one("0")
    one("1E+2")
    for text in ("1E+6", "123456", "10000", "9999.999", "-1E+4"):
        with pytest.raises(ParseError) as caught:
            one(text)
        assert caught.value.check == "value_overflow"


def test_count_bounds_and_last_period_block_the_manifest(tmp_path: Path) -> None:
    """Accepted leaf counts and required periods are checked before a manifest."""

    def run(folder: str, **overrides: object):
        return fetch_source(
            invented_entry(_narrow(**overrides)),
            tmp_path / folder,
            _clock,
            _sleep,
            lambda request: AttemptResult("ok", body_for(request)),
            SlotSecrets(PRIMARY, ""),
        )

    under = run("under", count_bounds={"minimum": 3, "maximum": 8})
    assert under.failure is not None
    assert under.failure.check == "count_bounds"
    assert not (tmp_path / "under" / "un_comtrade" / "manifest.json").exists()
    exact_min = run("min", count_bounds={"minimum": 2, "maximum": 8})
    assert exact_min.failure is None
    exact_max = run("max", count_bounds={"minimum": 1, "maximum": 2})
    assert exact_max.failure is None
    over = run("over", count_bounds={"minimum": 1, "maximum": 1})
    assert over.failure is not None
    assert over.failure.check == "count_bounds"
    missing = run("period", expected_last_periods=["2098"])
    assert missing.failure is not None
    assert missing.failure.check == "missing_period"
    assert not (tmp_path / "period" / "un_comtrade" / "manifest.json").exists()


def test_deleted_sidecar_blocks_assembly(tmp_path: Path) -> None:
    """Assembly reads every child receipt. A deleted sidecar is not a complete table."""
    fetch_source(
        invented_entry(_narrow()),
        tmp_path,
        _clock,
        _sleep,
        lambda request: AttemptResult("ok", body_for(request)),
        SlotSecrets(PRIMARY, ""),
    )
    folder = tmp_path / "un_comtrade"
    digest = sha256_hex((folder / "manifest.json").read_bytes())
    for path in folder.glob("*.meta.json"):
        path.unlink()
    with pytest.raises(SafeRefusal) as caught:
        assemble(
            tmp_path,
            "un_comtrade",
            _narrow(),
            manifest_sha256=digest,
            **trusted_source(),
        )
    assert caught.value.check == "receipt_missing"


def test_manifest_without_a_child_or_with_a_duplicate_is_refused(
    tmp_path: Path,
) -> None:
    """Coverage numbers do not prove the leaf set. A duplicate leaf is refused."""
    policy = _narrow()
    fetch_source(
        invented_entry(policy),
        tmp_path,
        _clock,
        _sleep,
        lambda request: AttemptResult("ok", body_for(request)),
        SlotSecrets(PRIMARY, ""),
    )
    folder = tmp_path / "un_comtrade"
    manifest_path = folder / "manifest.json"
    loaded = json.loads(manifest_path.read_text(encoding="utf-8"))
    loaded["children"].pop()
    manifest_path.write_text(json.dumps(loaded), encoding="utf-8")
    with pytest.raises(SafeRefusal):
        assemble(
            tmp_path,
            "un_comtrade",
            policy,
            manifest_sha256=sha256_hex(manifest_path.read_bytes()),
            **trusted_source(),
        )
    again = fetch_source(
        invented_entry(policy),
        tmp_path / "dup",
        _clock,
        _sleep,
        lambda request: AttemptResult("ok", body_for(request)),
        SlotSecrets(PRIMARY, ""),
    )
    assert again.failure is None
    dup_path = tmp_path / "dup" / "un_comtrade" / "manifest.json"
    dup = json.loads(dup_path.read_text(encoding="utf-8"))
    dup["children"].append(dup["children"][0])
    dup_path.write_text(json.dumps(dup), encoding="utf-8")
    with pytest.raises(SafeRefusal):
        assemble(
            tmp_path / "dup",
            "un_comtrade",
            policy,
            manifest_sha256=sha256_hex(dup_path.read_bytes()),
            **trusted_source(),
        )


def test_second_subdivision_resumes_the_next_day(tmp_path: Path) -> None:
    """A product split paused at the budget finishes the next day and assembles."""
    policy = _narrow(
        daily_calls=4,
        keyed_record_limit=2,
        subdivision_fields=["product"],
        subdivision_values={"product": ["ch-a-1", "ch-a-2"]},
    )
    seen: list[str] = []

    def opener(request: PreparedRequest) -> AttemptResult:
        seen.append(request.url)
        query = dict(parse_qsl(urlsplit(request.url).query))
        count = 1 if "product" in query else 2
        return AttemptResult("ok", body_for(request, count=count))

    cache = tmp_path / "deep"
    first = fetch_source(
        invented_entry(policy), cache, _clock, _sleep, opener, SlotSecrets(PRIMARY, "")
    )
    assert first.failure is not None
    assert first.failure.check == "budget_exhausted"
    state = json.loads(
        (cache / "un_comtrade" / "state.json").read_text(encoding="utf-8")
    )
    assert any("product=" in key for key in state["pending"])
    before = len(seen)
    second = fetch_source(
        invented_entry(policy), cache, _later, _sleep, opener, SlotSecrets(PRIMARY, "")
    )
    assert second.failure is None
    assert len(seen) > before
    assert any("product=" in url for url in seen[before:])
    assembled = assemble(
        cache,
        "un_comtrade",
        policy,
        manifest_sha256=second.digest,
        **trusted_source(),
    )
    assert assembled.rows
    body = next(
        path
        for path in (cache / "un_comtrade").glob("*.json")
        if not path.name.endswith(".meta.json")
        and path.name not in {"state.json", "coverage.json", "manifest.json"}
    )
    body.write_bytes(body.read_bytes() + b" ")
    changed = fetch_source(
        invented_entry(policy),
        cache,
        _later,
        _sleep,
        opener,
        SlotSecrets(PRIMARY, ""),
    )
    assert changed.failure is not None
    assert changed.failure.check == "child_hash"


def test_write_failure_leaves_no_partial_manifest(tmp_path: Path) -> None:
    """A failed manifest replace is a source failure and leaves no partial file."""
    real = os.replace

    def boom(src: str | os.PathLike[str], dst: str | os.PathLike[str]) -> None:
        if str(dst).endswith("manifest.json"):
            raise OSError("interrupted")
        real(src, dst)

    os.replace = boom
    try:
        result = fetch_source(
            invented_entry(_narrow()),
            tmp_path,
            _clock,
            _sleep,
            lambda request: AttemptResult("ok", body_for(request)),
            SlotSecrets(PRIMARY, ""),
        )
    finally:
        os.replace = real
    assert result.failure is not None
    assert result.failure.check == "write_failed"
    folder = tmp_path / "un_comtrade"
    assert not (folder / "manifest.json").exists()
    assert not (folder / ".manifest.json.partial").exists()


def test_retrieval_host_terms_and_source_are_the_selected_ones(tmp_path: Path) -> None:
    """The receipt keeps the clock time, the class host and the terms fingerprint."""
    public_host = "invented-public.example"
    templates = [
        {"api_class": "keyed", "family": "data", "host": HOST, "path": "/data/v1/get"},
        {
            "api_class": "public",
            "family": "data",
            "host": public_host,
            "path": "/public/v1/preview",
        },
    ]
    policy = _narrow(
        endpoint_templates=templates, allowed_redirect_hosts=[HOST, public_host]
    )
    result = fetch_source(
        invented_entry(policy),
        tmp_path,
        _clock,
        _sleep,
        lambda request: AttemptResult("ok", body_for(request)),
        None,
        api_class="public",
    )
    assert result.failure is None
    assert result.host == public_host
    folder = tmp_path / "un_comtrade"
    side = json.loads(next(folder.glob("*.meta.json")).read_text(encoding="utf-8"))
    assert side["retrieved_utc"] == "2026-11-16T08:00:00Z"
    assert side["fetch_host"] == public_host
    assert side["terms_sha256"] == terms_text_sha256(b"terms to be read")
    assembled = assemble(
        tmp_path,
        "un_comtrade",
        policy,
        manifest_sha256=result.digest,
        **trusted_source(),
    )
    assert assembled.rows[0].source_id == "un_comtrade"
    assert assembled.source_id == "un_comtrade"


def test_policy_hash_covers_schema_and_blocks_reuse(tmp_path: Path) -> None:
    """A changed schema or subdivision list changes the policy hash and refuses the ledger."""
    original = invented_policy()
    schema = dict(policy_document()["response_schema"])
    schema["error_field"] = "otherError"
    changed_schema = invented_policy(response_schema=schema)
    values = {"product": ["ch-a-1", "ch-a-9"]}
    changed_values = invented_policy(subdivision_values=values)
    redirects = invented_policy(allowed_redirect_hosts=[HOST])
    assert policy_sha256(original) != policy_sha256(changed_schema)
    assert policy_sha256(original) != policy_sha256(changed_values)
    assert policy_sha256(original) != policy_sha256(redirects)
    cache = tmp_path / "cache"
    assert (
        fetch_source(
            invented_entry(_narrow()),
            cache,
            _clock,
            _sleep,
            lambda request: AttemptResult("ok", body_for(request)),
            SlotSecrets(PRIMARY, ""),
        ).failure
        is None
    )
    reused = fetch_source(
        invented_entry(_narrow(response_schema=schema)),
        cache,
        _clock,
        _sleep,
        lambda request: AttemptResult("ok", body_for(request)),
        SlotSecrets(PRIMARY, ""),
    )
    assert reused.failure is not None
    assert reused.failure.check == "stale_state"


def test_policy_hash_changes_every_semantic_field() -> None:
    """Each semantic policy field changes the hash on its own."""
    original = policy_sha256(invented_policy())
    schema = dict(policy_document()["response_schema"])
    overrides: list[dict[str, object]] = []
    for name, value in schema.items():
        copied = dict(schema)
        copied[name] = str(value) + "X"
        overrides.append({"response_schema": copied})
    overrides.extend(
        [
            {"version": "invented-2"},
            {"verified_on": "2026-11-15"},
            {"evidence_url": "https://invented.example/evidence-2"},
            {"evidence_sha256": "ab" * 32},
            {"access_tier": "invented-other"},
            {
                "endpoint_templates": [
                    {
                        "api_class": "keyed",
                        "family": "data",
                        "host": "invented-other.example",
                        "path": "/data/v1/get",
                    },
                    {
                        "api_class": "public",
                        "family": "data",
                        "host": HOST,
                        "path": "/public/v1/preview",
                    },
                ]
            },
            {
                "endpoint_templates": [
                    {
                        "api_class": "keyed",
                        "family": "data",
                        "host": HOST,
                        "path": "/data/v2/get",
                    },
                    {
                        "api_class": "public",
                        "family": "data",
                        "host": HOST,
                        "path": "/public/v1/preview",
                    },
                ]
            },
            {
                "endpoint_templates": [
                    {
                        "api_class": "keyed",
                        "family": "preview",
                        "host": HOST,
                        "path": "/data/v1/get",
                    },
                    {
                        "api_class": "public",
                        "family": "data",
                        "host": HOST,
                        "path": "/public/v1/preview",
                    },
                ]
            },
            {"allowed_redirect_hosts": [HOST]},
            {"daily_calls": 21},
            {"keyed_record_limit": 4},
            {"public_record_limit": 3},
            {"reset_rule": "rolling_window"},
            {"quota_scope": "account"},
            {"daily_exhaustion_signal": "other_signal"},
            {"reporter_key": "QAB"},
            {"mirror_partner_keys": ["ZZB"]},
            {"frequencies": ["annual"]},
            {"periods": ["2098"], "expected_last_periods": ["2099"]},
            {"flows": ["flow-in"]},
            {"chapters": ["ch-b"]},
            {"subdivision_fields": [], "subdivision_values": {}},
            {"subdivision_values": {"product": ["ch-a-1", "ch-a-9"]}},
            {"count_bounds": {"minimum": 2, "maximum": 64}},
            {"count_bounds": {"minimum": 1, "maximum": 63}},
            {"expected_last_periods": ["2098"]},
            {"schema_reviewed": False},
            {"classification_revision": "HS-OTHER"},
            {
                "measure_units": [
                    {"measure": "trade_value", "unit": "YYY"},
                    {"measure": "net_weight", "unit": "invented-mass"},
                ]
            },
            {"value_precision": 7},
            {"value_scale": 1},
            {"price_amount": "1", "price_unavailable_reason": ""},
            {"price_currency": "XXX"},
            {"price_retrieved_on": "2026-11-15"},
            {"price_source": "invented-note"},
            {"price_unavailable_reason": "price_absent"},
        ]
    )
    for override in overrides:
        assert policy_sha256(invented_policy(**override)) != original


def test_unsupported_reset_and_a_boundary_crossing(tmp_path: Path) -> None:
    """Only the calendar-day rule is activated, and a later day clears the counters."""
    sent: list[str] = []

    def opener(request: PreparedRequest) -> AttemptResult:
        sent.append(request.url)
        return AttemptResult("ok", body_for(request))

    refused = fetch_source(
        invented_entry(_narrow(reset_rule="rolling_window")),
        tmp_path / "rule",
        _clock,
        _sleep,
        opener,
        SlotSecrets(PRIMARY, ""),
    )
    assert refused.failure is not None
    assert refused.failure.check == "reset_rule"
    assert sent == []
    assert not (tmp_path / "rule").exists()
    scoped = fetch_source(
        invented_entry(_narrow(quota_scope="account")),
        tmp_path / "scope",
        _clock,
        _sleep,
        opener,
        SlotSecrets(PRIMARY, ""),
    )
    assert scoped.failure is not None
    assert scoped.failure.check == "quota_scope"
    assert sent == []
    policy = _narrow(daily_calls=1)
    cache = tmp_path / "cross"
    first = fetch_source(
        invented_entry(policy), cache, _clock, _sleep, opener, SlotSecrets(PRIMARY, "")
    )
    assert first.failure is not None
    assert first.failure.check == "budget_exhausted"
    assert len(sent) == 1
    second = fetch_source(
        invented_entry(policy), cache, _clock, _sleep, opener, SlotSecrets(PRIMARY, "")
    )
    assert second.failure is not None
    assert second.failure.check == "budget_exhausted"
    assert len(sent) == 1
    third = fetch_source(
        invented_entry(policy), cache, _later, _sleep, opener, SlotSecrets(PRIMARY, "")
    )
    assert third.failure is None
    assert len(sent) == 2
    future = cache / "future" / "un_comtrade"
    future.mkdir(parents=True)
    ledger = fresh(policy_sha256(policy), "b" * 64, ("cell",), "2099-01-02")
    from eii_custodian.publicdata.comtrade.state import write_ledger

    write_ledger(future, ledger)
    with pytest.raises(StateError) as caught:
        load_or_new(
            future,
            policy_sha256=policy_sha256(policy),
            selection_sha256="b" * 64,
            pending=("cell",),
            today="2026-11-16",
            reset_rule="calendar_day",
        )
    assert caught.value.check == "stale_state"
    flips = {"n": 0}

    def crossing() -> str:
        flips["n"] += 1
        if flips["n"] <= 3:
            return "2026-11-16T23:50:00Z"
        return "2026-11-17T00:10:00Z"

    sent.clear()
    crossed = fetch_source(
        invented_entry(policy),
        tmp_path / "during",
        crossing,
        _sleep,
        opener,
        SlotSecrets(PRIMARY, ""),
    )
    assert crossed.failure is None
    assert len(sent) == 2
    pending_schema = fetch_source(
        invented_entry(_narrow(schema_reviewed=False)),
        tmp_path / "schema",
        _clock,
        _sleep,
        opener,
        SlotSecrets(PRIMARY, ""),
    )
    assert pending_schema.failure is not None
    assert pending_schema.failure.check == "schema_pending"
    assert len(sent) == 2


class _Spy(Mapping[str, str]):
    def __init__(self) -> None:
        self.seen: list[str] = []
        self._data = {
            "COMTRADE_PRIMARY_API_KEY": PRIMARY,
            "COMTRADE_SECONDARY_API_KEY": SECONDARY,
        }

    def __getitem__(self, key: str) -> str:
        self.seen.append(key)
        return self._data[key]

    def __iter__(self):
        return iter(self._data)

    def __len__(self) -> int:
        return len(self._data)


def test_accessor_reads_only_the_selected_slot(tmp_path: Path) -> None:
    """Skipped activation reads nothing. The secondary name is read only when used."""
    from commands.build_public import slot_secrets

    idle = _Spy()
    accessor = slot_secrets(idle, injected=False)
    assert accessor is not None
    assert idle.seen == []
    with pytest.raises(TypeError):
        pickle.dumps(accessor)
    sent: list[str] = []

    def opener(request: PreparedRequest) -> AttemptResult:
        sent.append(request.header_value)
        return AttemptResult("ok", body_for(request))

    skipped = fetch_source(
        invented_entry(_narrow(reset_rule="rolling_window")),
        tmp_path / "skip",
        _clock,
        _sleep,
        opener,
        accessor,
    )
    assert skipped.failure is not None
    assert idle.seen == []
    assert sent == []
    used = fetch_source(
        invented_entry(_narrow(daily_calls=1)),
        tmp_path / "used",
        _clock,
        _sleep,
        opener,
        accessor,
    )
    assert used.failure is None
    assert idle.seen == ["COMTRADE_PRIMARY_API_KEY", "COMTRADE_SECONDARY_API_KEY"]
    assert sent == [PRIMARY, SECONDARY]


def _stored_text(root: Path) -> str:
    return "\n".join(
        path.read_text(encoding="utf-8", errors="replace")
        for path in root.rglob("*")
        if path.is_file()
    )
