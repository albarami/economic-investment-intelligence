"""One planted refusal for each remaining Comtrade guard."""

from __future__ import annotations

import email.message
import hashlib
import io
import json
import urllib.error
import urllib.request
from dataclasses import replace
from pathlib import Path
from typing import cast

import pytest
import yaml
from custodian.tests.fixtures.comtrade.invented import (
    body_for,
    invented_entry,
    invented_policy,
    trusted_source,
)

from eii_custodian.publicdata.comtrade.assemble import assemble
from eii_custodian.publicdata.comtrade.fetch import fetch_source
from eii_custodian.publicdata.comtrade.parse import ParseError, parse_body
from eii_custodian.publicdata.comtrade.partition import initial_partitions
from eii_custodian.publicdata.comtrade.policy import (
    PolicyError,
    SafeRefusal,
)
from eii_custodian.publicdata.comtrade.state import (
    StateError,
    fresh,
    read_ledger,
    reserve,
)
from eii_custodian.publicdata.fetch.allowlist import canonical_https
from eii_custodian.publicdata.fetch.build import run_build
from eii_custodian.publicdata.fetch.registry import RegistryError, load_registry
from eii_custodian.publicdata.fetch.transport import (
    AttemptResult,
    OpenerFault,
    PreparedRequest,
    SlotSecrets,
    open_attempt,
    perform,
)

MARKER = "invented-query-marker"


def _clock() -> str:
    return "2026-11-16T08:00:00Z"


def _sleep(_seconds: float) -> None:
    return None


def _narrow(**overrides: object):
    base: dict[str, object] = {
        "frequencies": ["annual"],
        "periods": ["2099"],
        "flows": ["flow-in"],
        "daily_calls": 4,
    }
    base.update(overrides)
    return invented_policy(**base)


def _descriptor():
    return initial_partitions(_narrow())[0].descriptor(_narrow(), "keyed")


def _payload(
    records: list[dict[str, object]],
    *,
    count: object | None = None,
    truncated: object = False,
) -> bytes:
    body = {
        "data": records,
        "count": len(records) if count is None else count,
        "error": "",
        "truncated": truncated,
    }
    return json.dumps(body).encode("utf-8")


def _row() -> dict[str, object]:
    descriptor = _descriptor()
    return {
        "typeCode": "C",
        "freqCode": descriptor.frequency,
        "period": descriptor.period,
        "flowCode": descriptor.flow_code,
        "reporterCode": descriptor.reporter_code,
        "partnerCode": descriptor.partner_code,
        "partner2Code": None,
        "cmdCode": descriptor.chapter,
        "classificationCode": "HS-INVENTED",
        "classificationRevision": descriptor.classification_revision,
        "aggregationLevel": 2,
        "customsCode": "customs-invented",
        "transportCode": "mode-invented",
        "valuationBasis": "value-invented",
        "primaryValue": "1.00",
        "qty": None,
        "flag": "",
    }


def _stored(cache: Path) -> str:
    folder = cache / "un_comtrade"
    if not folder.exists():
        return ""
    return "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(folder.rglob("*"))
        if path.is_file()
    )


def test_perform_refuses_a_non_descriptor() -> None:
    """Transport refuses a value that is not a closed descriptor before any opener call."""
    opened: list[str] = []

    def opener(request: PreparedRequest) -> AttemptResult:
        opened.append(request.url)
        return AttemptResult("ok", b"")

    with pytest.raises(OpenerFault) as caught:
        perform(invented_policy(), object(), None, opener)
    assert str(caught.value) == "descriptor"
    assert opened == []


def test_canonical_host_and_path_are_refused() -> None:
    """A host or path outside the canonical form is refused."""
    with pytest.raises(ValueError, match="host"):
        canonical_https("bad:host", "/cached", ())
    with pytest.raises(ValueError, match="path"):
        canonical_https("invented.example", "cached", ())


def test_opener_refuses_host_http_network_and_redirect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The production opener refuses before any followed request."""
    with pytest.raises(OpenerFault) as blocked:
        open_attempt(PreparedRequest("https://invented.example/data", "", "", "id"))
    assert str(blocked.value) == "blocked_host"

    def http_opener(_handler: object) -> object:
        class _Open:
            def open(self, *_args: object, **_kwargs: object) -> object:
                raise urllib.error.HTTPError(
                    "https://www.data.gov.qa/planted",
                    500,
                    "no",
                    email.message.Message(),
                    None,
                )

        return _Open()

    monkeypatch.setattr(urllib.request, "build_opener", http_opener)
    with pytest.raises(OpenerFault) as http:
        open_attempt(PreparedRequest("https://www.data.gov.qa/planted", "", "", "id"))
    assert str(http.value) == "http"

    def network_opener(_handler: object) -> object:
        class _Open:
            def open(self, *_args: object, **_kwargs: object) -> object:
                raise urllib.error.URLError("down")

        return _Open()

    monkeypatch.setattr(urllib.request, "build_opener", network_opener)
    with pytest.raises(OpenerFault) as network:
        open_attempt(PreparedRequest("https://www.data.gov.qa/planted", "", "", "id"))
    assert str(network.value) == "unreachable"

    def redirect_opener(handler: object) -> object:
        stop = cast(type[urllib.request.HTTPRedirectHandler], handler)()
        stop.redirect_request(
            urllib.request.Request("https://www.data.gov.qa/planted"),
            io.BytesIO(b""),
            302,
            "see",
            email.message.Message(),
            "https://evil.example/followed",
        )
        raise AssertionError("redirect followed")

    monkeypatch.setattr(urllib.request, "build_opener", redirect_opener)
    with pytest.raises(OpenerFault) as redirected:
        open_attempt(PreparedRequest("https://www.data.gov.qa/planted", "", "", "id"))
    assert str(redirected.value) == "redirect"


def test_policy_shape_plants() -> None:
    """Each closed policy field refuses its own bad value."""
    schema = dict(_narrow().response_schema.__dict__)
    del schema["classification_field"]
    planted = {
        "verified_on": "16-11-2026",
        "evidence_sha256": "abc",
        "daily_calls": 0,
        "response_schema": schema,
        "subdivision_values": {"product": []},
        "endpoint_templates": [
            {
                "api_class": "keyed",
                "family": "data",
                "host": "bad:host",
                "path": "/get",
            }
        ],
    }
    for name, value in planted.items():
        with pytest.raises(PolicyError) as caught:
            _narrow(**{name: value})
        assert (
            caught.value.detail
            == {
                "verified_on": "verified_on is not a date",
                "evidence_sha256": "evidence_sha256",
                "daily_calls": "daily_calls",
                "response_schema": "response_schema",
                "subdivision_values": "subdivision_values",
                "endpoint_templates": "endpoint_templates",
            }[name]
        )


def test_fetch_status_echo_terms_and_signal(tmp_path: Path) -> None:
    """Status, echo, empty terms and a foreign exhaustion signal each stop the run."""
    sent: list[str] = []

    def http(_request: PreparedRequest) -> AttemptResult:
        sent.append("http")
        return AttemptResult("http", b"")

    status = fetch_source(
        invented_entry(_narrow()),
        tmp_path / "status",
        _clock,
        _sleep,
        http,
        SlotSecrets("primary-marker", ""),
    )
    assert status.failure is not None
    assert status.failure.check == "http_status"
    assert sent == ["http"]

    def echo(request: PreparedRequest) -> AttemptResult:
        sent.append("echo")
        return AttemptResult("ok", body_for(request), header_echo=MARKER)

    echoed = fetch_source(
        invented_entry(_narrow()),
        tmp_path / "echo",
        _clock,
        _sleep,
        echo,
        SlotSecrets(MARKER, ""),
    )
    assert echoed.failure is not None
    assert echoed.failure.check == "provider_error"
    assert MARKER not in _stored(tmp_path / "echo")

    terms = fetch_source(
        replace(invented_entry(_narrow()), terms_words=""),
        tmp_path / "terms",
        _clock,
        _sleep,
        http,
        SlotSecrets("primary-marker", ""),
    )
    assert terms.failure is not None
    assert terms.failure.check == "commit_forbidden"
    assert sent == ["http", "echo"]

    signal_sent: list[str] = []

    def once(request: PreparedRequest) -> AttemptResult:
        signal_sent.append(request.header_value)
        return AttemptResult("ok", body_for(request))

    signal = fetch_source(
        invented_entry(_narrow(daily_calls=1, daily_exhaustion_signal="other")),
        tmp_path / "signal",
        _clock,
        _sleep,
        once,
        SlotSecrets("primary-marker", "secondary-marker"),
    )
    assert signal.failure is not None
    assert signal.failure.check == "exhaustion_signal"
    assert signal_sent == ["primary-marker"]


def test_parser_shape_plants() -> None:
    """Each malformed answer is refused at its own check."""
    policy = _narrow()
    descriptor = _descriptor()

    def parse(body: bytes) -> None:
        parse_body(
            body,
            policy,
            descriptor,
            source_version="invented",
            receipt_sha256="ab" * 32,
        )

    cases = {
        b"{": "metadata_unreadable",
        b"[]": "metadata_unreadable",
        json.dumps({"data": {}}).encode(): "metadata_unreadable",
        _payload([_row()], count="two"): "short_total",
        _payload([_row()], truncated="yes"): "truncation_flag",
    }
    for body, check in cases.items():
        with pytest.raises(ParseError) as caught:
            parse(body)
        assert caught.value.check == check
    with pytest.raises(ParseError) as repeated:
        parse(_payload([_row(), _row()]))
    assert repeated.value.check == "duplicate_key"
    revised = _row()
    revised["classificationRevision"] = "OTHER"
    with pytest.raises(ParseError) as membership:
        parse(_payload([revised]))
    assert membership.value.check == "selection_membership"
    text_level = _row()
    text_level["aggregationLevel"] = "2"
    with pytest.raises(ParseError) as retyped:
        parse(_payload([text_level]))
    assert retyped.value.check == "schema_retyped"


def test_ledger_shape_and_slot(tmp_path: Path) -> None:
    """A ledger of the wrong shape, and an unknown slot, are refused."""
    path = tmp_path / "state.json"
    path.write_text("{}\n", encoding="utf-8")
    with pytest.raises(StateError) as empty:
        read_ledger(path)
    assert empty.value.check == "stale_state"
    path.write_text("[]\n", encoding="utf-8")
    with pytest.raises(StateError) as listed:
        read_ledger(path)
    assert listed.value.check == "stale_state"
    ledger = fresh("a" * 64, "b" * 64, ("cell",), "2026-11-16")
    with pytest.raises(StateError) as slot:
        reserve(ledger, "other")
    assert slot.value.check == "slot"


def test_assembly_identity_plants(tmp_path: Path) -> None:
    """A missing, rehashed or non-integer manifest is refused."""
    with pytest.raises(SafeRefusal) as missing:
        assemble(
            tmp_path,
            "none",
            _narrow(),
            manifest_sha256="ab" * 32,
            **trusted_source(),
        )
    assert missing.value.check == "manifest_missing"
    fetched = fetch_source(
        invented_entry(_narrow()),
        tmp_path,
        _clock,
        _sleep,
        lambda request: AttemptResult("ok", body_for(request)),
        SlotSecrets("primary-marker", ""),
    )
    assert fetched.failure is None
    folder = tmp_path / "un_comtrade"
    manifest = folder / "manifest.json"
    with pytest.raises(SafeRefusal) as hashed:
        assemble(
            tmp_path,
            "un_comtrade",
            _narrow(),
            manifest_sha256="cd" * 32,
            **trusted_source(),
        )
    assert hashed.value.check == "manifest_hash"
    original = manifest.read_text(encoding="utf-8")
    loaded = json.loads(original)
    loaded["present_cells"] = True
    manifest.write_text(json.dumps(loaded) + "\n", encoding="utf-8")
    digest = hashlib.sha256(manifest.read_bytes()).hexdigest()
    with pytest.raises(SafeRefusal) as counted:
        assemble(
            tmp_path,
            "un_comtrade",
            _narrow(),
            manifest_sha256=digest,
            **trusted_source(),
        )
    assert counted.value.check == "manifest_unreadable"
    restored = json.loads(original)
    restored["requested_cells"] = 0
    manifest.write_text(json.dumps(restored) + "\n", encoding="utf-8")
    gap_digest = hashlib.sha256(manifest.read_bytes()).hexdigest()
    with pytest.raises(SafeRefusal) as gap:
        assemble(
            tmp_path,
            "un_comtrade",
            _narrow(),
            manifest_sha256=gap_digest,
            **trusted_source(),
        )
    assert gap.value.check == "coverage_gap"


def test_registry_policy_placement(tmp_path: Path) -> None:
    """The policy object belongs only on the Comtrade row, and that row requires it."""
    path = tmp_path / "sources.yaml"
    row = _registry_row("https_file")
    row["comtrade_policy"] = {"confirmed": False}
    path.write_text(yaml.safe_dump({"sources": [row]}), encoding="utf-8")
    with pytest.raises(RegistryError, match="comtrade_policy"):
        load_registry(path)
    bare = _registry_row("comtrade_api")
    path.write_text(yaml.safe_dump({"sources": [bare]}), encoding="utf-8")
    with pytest.raises(RegistryError, match="comtrade_policy"):
        load_registry(path)


def test_dispatcher_refuses_an_uninjected_transport(tmp_path: Path) -> None:
    """Comtrade without an injected transport stops; another kind never reads the slot."""
    seen: list[str] = []

    class _Reader:
        def read_slot(self, slot: str) -> str:
            seen.append(slot)
            return ""

    outcome = run_build(
        (invented_entry(_narrow()),),
        lambda _url: b"",
        tmp_path / "keyed",
        _clock,
        _sleep,
        None,
        _Reader(),
    )
    assert outcome.failure is not None
    assert outcome.failure.check == "transport_uninjected"
    assert seen == []

    def refuse_fetch(_url: str) -> bytes:
        raise AssertionError("citation fetched")

    citation = run_build(
        (_citation(),),
        refuse_fetch,
        tmp_path / "citation",
        _clock,
        _sleep,
        None,
        _Reader(),
    )
    assert citation.failure is None or citation.failure.check == "public_data"
    assert seen == []


def _registry_row(kind: str) -> dict[str, object]:
    return {
        "key": "planted",
        "source_id": "planted",
        "slug": "",
        "kind": kind,
        "title_en": "Planted",
        "publisher": "Planted publisher",
        "licence_id": "",
        "licence_basis": "provider_terms",
        "decision_record": "",
        "fetch_host": "",
        "url": "",
        "terms_url": "",
        "terms_words": "terms to be read",
        "terms_read_on": "2026-11-16",
        "landing_url": "",
        "nightly_live_fetch": False,
        "public_splits": [],
        "commit_allowed": False,
        "release_tables": [],
        "caveat_keys": [],
        "columns": [],
        "reconciliation": "open",
        "skip_reason": "metadata_unconfirmed",
        "extension": "json",
    }


def _citation():
    entry = invented_entry(_narrow())
    return replace(
        entry,
        key="citation",
        source_id="citation",
        kind="citation_only",
        comtrade_policy=None,
    )
