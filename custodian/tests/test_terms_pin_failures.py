"""S2-P36: invented pin failures stay within the fetch/terms boundary."""

from __future__ import annotations

import hashlib
import json
import ssl
from dataclasses import replace
from pathlib import Path

import pytest
from custodian.tests.fixtures.invented_chain import intermediate_pem

from commands import build_public
from eii_custodian.publicdata.assembly_adapters import Production
from eii_custodian.publicdata.fetch import allowlist, page_requests
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


@pytest.mark.parametrize("kind", ["https_file", "terms_page"])
def test_terms_pin_failure_keeps_build_and_other_source_intact(
    tmp_path: Path, kind: str
) -> None:
    row = entry(kind=kind)
    other = entry("SYN-other", url=f"https://{OTHER}/SYN-other.bin", terms_url="")
    seen: list[str] = []
    sleeps: list[float] = []

    def transport(url: str) -> Response:
        seen.append(url)
        if url == TERMS:
            raise PinError(INCOMPLETE)
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
    assert f"TERMS {row.key} not read: {INCOMPLETE} ({TERMS})" in outcome.lines
    assert sum(line.startswith(f"PASS {other.key} ") for line in outcome.lines) == 1
    log = json.loads((tmp_path / "build-log.json").read_text())
    assert log["terms"] == []
    assert log["terms_attempts"] == [
        {
            "key": row.key,
            "terms_url": TERMS,
            "terms_attempted_utc": STAMP,
            "terms_unread_reason": INCOMPLETE,
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
@pytest.mark.parametrize(
    "reason", [INCOMPLETE, "tls_verification_disabled", "SYN-private-error"]
)
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
    assert prepared.failure.check == INCOMPLETE
    assert prepared.failure.code == 1
    assert prepared.failure.url == seen[0]
    assert len(seen) == 1 and sleeps == []
    assert "SYN-private-error" not in repr(prepared.failure)
    from eii_custodian.publicdata.fetch.kinds import require_verified_chain

    expected = INCOMPLETE if reason == "SYN-private-error" else reason
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
