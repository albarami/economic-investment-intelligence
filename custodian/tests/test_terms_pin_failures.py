"""S2-P36: invented pin failures stay within the fetch/terms boundary."""

from __future__ import annotations

import hashlib
import json
import ssl
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock

import pytest
from custodian.tests.fixtures.invented_chain import intermediate_pem

from commands import build_public
from eii_custodian.publicdata.assembly_adapters import Production
from eii_custodian.publicdata.fetch import (
    allowlist,
    certificate_pins,
    page_acquire,
    page_records,
    page_requests,
)
from eii_custodian.publicdata.fetch.build import BuildOutcome, run_build
from eii_custodian.publicdata.fetch.certificate_pins import PinError
from eii_custodian.publicdata.fetch.kinds import prepare, read_bounded
from eii_custodian.publicdata.fetch.registry import Entry
from eii_custodian.publicdata.fetch.transport import Response
from eii_custodian.publicdata.singles import tenders

HOST = "syn-chain.invalid"
OTHER = "syn-other.invalid"
URL = f"https://{HOST}/SYN-data.bin"
TERMS = f"https://{HOST}/SYN-terms"
STAMP = "2026-11-21T00:00:00Z"
INCOMPLETE = "certificate_chain_incomplete"
CLOSED_REASONS = (
    INCOMPLETE,
    "certificate_host_mismatch",
    "certificate_review_pending",
    "tls_verification_disabled",
)


def entry(key: str = "SYN-source", **changes: object) -> Entry:
    row = Entry(
        key=key,
        source_id=key,
        slug="",
        kind="https_file",
        title_en="SYN-source",
        publisher="SYN-publisher",
        licence_id="SYN-licence",
        licence_basis="dataset",
        decision_record="",
        fetch_host=HOST,
        url=URL,
        terms_url=TERMS,
        nightly_live_fetch=False,
        public_splits=(),
        commit_allowed=False,
        release_tables=(),
        caveat_keys=(),
        columns=(),
        row_count_min=None,
        row_count_max=None,
        period_first="",
        period_last="",
        period_field="",
        reconciliation="none",
        skip_reason="",
        extension="bin",
        landing_url="",
        terms_words="SYN-pending words",
        terms_read_on="pending",
    )
    return replace(row, **changes)


@pytest.fixture(autouse=True)
def invented_hosts(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(allowlist, "ALLOWED_HOSTS", frozenset({HOST, OTHER}))
    monkeypatch.setattr(page_requests, "PIN_HOSTS", frozenset({HOST}))


def test_page_acquire_pin_failure_never_uses_available_capture(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from custodian.tests.test_s2_t29_live_acquire import school

    review, _ = school()
    review.update(
        url=URL + "?f=json", reviewed_urls=[URL + "?f=json"], pins=[{"host": HOST}]
    )
    review["shape"]["layer"] = URL
    row = entry(
        "schools_private_directory",
        kind="public_page",
        url=URL + "?f=json",
        terms_url="",
        columns=tuple(tuple(column) for column in review["columns"]),
    )
    der = ssl.PEM_cert_to_DER_cert(intermediate_pem().decode())
    pin = certificate_pins.Pin(HOST, hashlib.sha256(der).hexdigest(), der, True)
    capture = certificate_pins.Capture(
        b"SYN-capture",
        row.url,
        row.url,
        (),
        "SYN-browser",
        STAMP,
        hashlib.sha256(b"SYN-capture").hexdigest(),
        pin,
        True,
        "visitor",
    )
    assert certificate_pins.admit_capture(capture, row.url)[0].body == b"SYN-capture"
    load = Mock(return_value=capture)
    admit = Mock(
        side_effect=AssertionError("certificate failure must not admit capture")
    )
    record = Mock(wraps=page_records.record_failure)
    monkeypatch.setattr(page_acquire, "load_pin", lambda *args: pin)
    monkeypatch.setattr(page_acquire, "PIN_HOSTS", frozenset({HOST}))
    monkeypatch.setattr(certificate_pins, "load_capture", load)
    monkeypatch.setattr(certificate_pins, "admit_capture", admit)
    monkeypatch.setattr(page_records, "record_failure", record)
    calls: list[str] = []

    def refused(url: str) -> Response:
        calls.append(url)
        raise PinError("certificate_host_mismatch")

    with pytest.raises(PinError, match=r"^certificate_host_mismatch$"):
        page_acquire.fetch(
            row,
            review,
            refused,
            tmp_path,
            lambda: STAMP,
            lambda _: pytest.fail("no retry"),
        )
    assert calls == [row.url]
    load.assert_not_called()
    admit.assert_not_called()
    record.assert_called_once_with(tmp_path, row, STAMP, "certificate_host_mismatch")
    assert not list((tmp_path / row.key / "inputs").rglob("*"))
    assert not list((tmp_path / row.key / "index").glob("*.json"))


def test_terms_https_refuses_other_host_before_opening_request(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    chain = tmp_path / "SYN-chain.pem"
    pem = intermediate_pem()
    chain.write_bytes(pem)
    row = entry(
        "tenders_pub", chain_intermediate_sha256=hashlib.sha256(pem).hexdigest()
    )
    monkeypatch.setattr(tenders, "TENDER_HOST", HOST)
    monkeypatch.setattr(tenders, "PIN_HOSTS", frozenset({HOST}))
    monkeypatch.setattr(tenders, "CHAIN_PATH", chain)
    opened = Mock(return_value=Response(TERMS, b"SYN-terms", ()))
    low_opened = Mock(return_value=Response(TERMS, b"SYN-terms", ()))
    monkeypatch.setattr(tenders, "open_https", opened)
    monkeypatch.setattr(tenders, "_open_https", low_opened)
    # Positive control: the invented chain is accepted for its registered host.
    assert tenders.chain_context(chain, row.chain_intermediate_sha256, host=HOST)
    with pytest.raises(PinError, match=f"^{INCOMPLETE}$"):
        tenders.terms_https(row, f"https://{OTHER}/SYN-terms")
    opened.assert_not_called()
    low_opened.assert_not_called()


@pytest.mark.parametrize("reason", (*CLOSED_REASONS, "SYN-private-error"))
@pytest.mark.parametrize("fault_at", ["page", "terms"])
def test_page_own_terms_pin_failure_is_advisory_with_its_closed_reason(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, reason: str, fault_at: str
) -> None:
    from custodian.tests.test_s2_t29_pages import BODY

    row = entry(
        "schools_private_directory",
        kind="public_page",
        extension="html",
        columns=(("syn_name", "string"), ("syn_count", "integer")),
    )
    review = {
        "url": URL,
        "reviewed_urls": [URL, TERMS],
        "table_id": "syn",
        "columns": [[name, kind] for name, kind in row.columns],
        "as_of": "2026-11-21",
        "period": "2026",
        "bounds_basis": "unconfirmed",
    }
    der = ssl.PEM_cert_to_DER_cert(intermediate_pem().decode())
    pin = certificate_pins.Pin(HOST, hashlib.sha256(der).hexdigest(), der, True)
    monkeypatch.setattr(page_records, "load_declaration", lambda _: review)
    monkeypatch.setattr(page_records, "load_pin", lambda *args: pin)
    calls: list[str] = []

    def transport(url: str) -> Response:
        calls.append(url)
        assert certificate_pins.current_pin() is pin
        if url == (TERMS if fault_at == "terms" else URL):
            raise PinError(reason)
        assert url == URL
        return Response(url, BODY, ())

    expected = INCOMPLETE if reason == "SYN-private-error" else reason
    if fault_at == "page":
        with pytest.raises(PinError, match=f"^{expected}$"):
            page_records.fetch_page(
                row,
                transport,
                tmp_path,
                lambda: STAMP,
                lambda _: pytest.fail("no retry"),
            )
        assert calls == [URL]
        assert not list(tmp_path.rglob("*.json"))
        return
    snapshot = page_records.fetch_page(
        row,
        transport,
        tmp_path,
        lambda: STAMP,
        lambda _: pytest.fail("no retry"),
    )
    assert calls == [URL, TERMS]
    assert json.loads(snapshot.body)["rows"] == [
        {"syn_name": "SYN-item", "syn_count": 7}
    ]
    assert snapshot.sidecar["terms_sha256"] is None
    assert snapshot.sidecar["terms_unread"] == expected
    assert not (tmp_path / row.key / "terms").exists()


@pytest.mark.parametrize("kind", ["https_file", "terms_page"])
@pytest.mark.parametrize("reason", (*CLOSED_REASONS, "SYN-private-error"))
def test_terms_pin_failure_keeps_build_and_other_source_intact(
    tmp_path: Path, kind: str, reason: str
) -> None:
    row = entry(kind=kind)
    other = entry("SYN-other", url=f"https://{OTHER}/SYN-other.bin", terms_url="")
    seen: list[str] = []
    sleeps: list[float] = []

    def transport(url: str) -> Response:
        seen.append(url)
        if url == TERMS:
            raise PinError(reason)
        assert url in {URL, other.url}
        return Response(url, b"SYN-data", ())

    outcome = run_build(
        (row, other),
        transport,
        tmp_path,
        lambda: STAMP,
        sleeps.append,
        _fetch_only=True,
    )
    assert outcome.failure is None
    assert seen == [URL, TERMS, other.url]
    assert sleeps == []
    expected = INCOMPLETE if reason == "SYN-private-error" else reason
    assert f"TERMS {row.key} not read: {expected} ({TERMS})" in outcome.lines
    assert sum(line.startswith(f"PASS {other.key} ") for line in outcome.lines) == 1
    log = json.loads((tmp_path / "build-log.json").read_text())
    assert log["terms"] == []
    assert log["terms_attempts"] == [
        {
            "key": row.key,
            "terms_url": TERMS,
            "terms_attempted_utc": STAMP,
            "terms_unread_reason": expected,
            "terms_read_on": "pending",
            "terms_words": "SYN-pending words",
        }
    ]
    assert list(outcome.terms_attempts) == log["terms_attempts"]
    for current in (row, other):
        bodies = list((tmp_path / current.key).glob("*.bin"))
        assert len(bodies) == 1 and bodies[0].read_bytes() == b"SYN-data"


@pytest.mark.parametrize(
    "kind", ["https_file", "terms_page", "portal_dataset", "paged_layer"]
)
@pytest.mark.parametrize("reason", (*CLOSED_REASONS, "SYN-private-error"))
def test_pin_failure_on_every_call_url_kind_is_structured(
    kind: str, reason: str
) -> None:
    seen: list[str] = []
    sleeps: list[float] = []

    def refused(url: str) -> Response:
        seen.append(url)
        raise PinError(reason)

    prepared = prepare(entry(kind=kind, layer=0), refused, sleeps.append)
    assert prepared.body == b""
    assert prepared.failure is not None
    expected = INCOMPLETE if reason == "SYN-private-error" else reason
    assert prepared.failure.check == expected
    assert prepared.failure.code == 1
    assert prepared.failure.url == seen[0]
    assert len(seen) == 1 and sleeps == []
    assert "SYN-private-error" not in repr(prepared.failure)
    from eii_custodian.publicdata.fetch.kinds import require_verified_chain

    with pytest.raises(PinError, match=f"^{expected}$"):
        require_verified_chain(prepared.failure)


def test_bounded_pin_failure_is_structured_but_unrelated_defect_escapes() -> None:
    def pin_fault(url: str) -> Response:
        raise PinError(INCOMPLETE)

    response, failure = read_bounded(pin_fault, lambda _: pytest.fail("no retry"), URL)
    assert response is None and failure is not None and failure.check == INCOMPLETE
    from eii_custodian.publicdata.fetch.kinds import require_verified_chain

    require_verified_chain(None)

    def defect(url: str) -> Response:
        raise ValueError("SYN-defect")

    with pytest.raises(ValueError, match="SYN-defect"):
        read_bounded(defect, lambda _: pytest.fail("no retry"), URL)


def test_dataset_pin_failure_retains_its_fetch_code_above_assembly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Use the real assembly fetch stage without requiring unrelated producer inputs.
    monkeypatch.setattr(Production, "run", Production.fetch_archive)

    def refused(url: str) -> Response:
        raise PinError(INCOMPLETE)

    outcome = run_build(
        (entry(),),
        refused,
        tmp_path,
        lambda: STAMP,
        lambda _: pytest.fail("no retry"),
        seed=36,
    )
    assert outcome.failure is not None
    assert outcome.failure.source_id == "SYN-source"
    assert outcome.failure.check == INCOMPLETE
    assert outcome.failure.code == 1
    assert all("assembly_build_refused" not in line for line in outcome.lines)


@pytest.mark.parametrize(
    "plant", ["valid", "missing", "hash", "malformed", "unregistered"]
)
def test_command_terms_reader_uses_only_the_existing_checked_chain(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, plant: str
) -> None:
    from custodian.tests.method_pin_config_fixture import stage_tracked_configuration

    stage_tracked_configuration(tmp_path)

    chain = tmp_path / "SYN-chain.pem"
    pem = intermediate_pem()
    if plant != "missing":
        chain.write_bytes(b"SYN-malformed" if plant == "malformed" else pem)
    pin = hashlib.sha256(chain.read_bytes() if chain.exists() else pem).hexdigest()
    row = entry()
    chain_row = entry(
        "tenders_pub",
        terms_url="",
        chain_intermediate_sha256="a" * 64 if plant == "hash" else pin,
    )
    entries = (row,) if plant == "unregistered" else (row, chain_row)
    monkeypatch.setattr(tenders, "TENDER_HOST", HOST)
    monkeypatch.setattr(tenders, "PIN_HOSTS", frozenset({HOST}))
    monkeypatch.setattr(tenders, "CHAIN_PATH", chain)
    monkeypatch.setattr(build_public, "load_registry", lambda: entries)
    monkeypatch.setattr(build_public, "load_policies", dict)
    seen: list[tuple[str, dict[str, object]]] = []

    def open_page(url: str, **options: object) -> Response:
        seen.append((url, options))
        if url == TERMS:
            context = options.get("ssl_context")
            assert isinstance(context, ssl.SSLContext)
            assert context.verify_mode == ssl.CERT_REQUIRED and context.check_hostname
            assert not context.verify_flags & ssl.VERIFY_X509_PARTIAL_CHAIN
            assert ssl.PEM_cert_to_DER_cert(pem.decode()) in context.get_ca_certs(
                binary_form=True
            )
            assert options.get("legacy_chain_sha256") == pin
        else:
            assert options.get("ssl_context") is None
            assert options.get("legacy_chain_sha256") is None
        return Response(url, b"SYN-page", ())

    monkeypatch.setattr(build_public, "open_https", open_page)
    monkeypatch.setattr(tenders, "_open_https", open_page)

    def build(rows, transport, *args, **kwargs):
        if plant == "valid":
            assert transport(TERMS).body == b"SYN-page"
            assert tenders._TENDER_CHAIN.get() is None
        else:
            with pytest.raises(PinError, match=f"^{INCOMPLETE}$"):
                transport(TERMS)
        assert transport(URL).body == b"SYN-page"
        assert transport(f"https://{OTHER}/SYN-terms").body == b"SYN-page"
        return BuildOutcome((), None)

    monkeypatch.setattr(build_public, "run_build", build)
    assert build_public.run(tmp_path, {}, ()) == 0
    assert [url for url, _ in seen] == (
        [TERMS, URL, f"https://{OTHER}/SYN-terms"]
        if plant == "valid"
        else [URL, f"https://{OTHER}/SYN-terms"]
    )
