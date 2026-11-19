"""S2-T08 part B, mismatch class 7: the tender chain is inspected and host-scoped.

The live shape pack's Mismatches item 7 shows the tender portal unreadable
without its issuing intermediate (no body sample). The tender reader keeps its
PEM-file convention; ``chain_context`` now refuses, before any request, a file
that is not exactly one issuing authority (the inspection S2-T29's ``load_pin``
applies, shared through ``inspect_intermediate``), a file whose hash is not the
registry's pin, a host other than the tender host on the pin allow-list, and a
context that does not verify. Trust is added from the inspected bytes only.
Without a reviewed chain the refusal is the truthful
``certificate_chain_incomplete``. Every certificate below is invented.
"""

from __future__ import annotations

import hashlib
import ssl
from dataclasses import replace
from pathlib import Path

import pytest
from custodian.tests.fixtures.invented_chain import intermediate_pem, invented_pems

from eii_custodian.publicdata.fetch.certificate_pins import (
    PinError,
    inspect_intermediate,
)
from eii_custodian.publicdata.fetch.page_requests import PIN_HOSTS
from eii_custodian.publicdata.fetch.registry import load_registry
from eii_custodian.publicdata.singles import tenders
from eii_custodian.publicdata.singles.tenders import (
    TENDER_HOST,
    TENDER_SUITE,
    TenderError,
    chain_context,
    fetch_tenders,
)

INCOMPLETE = "certificate_chain_incomplete"
MISMATCH = "certificate_host_mismatch"


def _der(pem: bytes) -> bytes:
    return ssl.PEM_cert_to_DER_cert(pem.decode("ascii"))


def _file(tmp_path: Path, body: bytes) -> tuple[Path, str]:
    path = tmp_path / "SYN-chain.pem"
    path.write_bytes(body)
    return path, hashlib.sha256(body).hexdigest()


def _plants() -> dict[str, bytes]:
    pems = invented_pems()
    return {
        "two_certificates": pems["intermediate"] + pems["root"],
        "intermediate_and_leaf": pems["intermediate"] + pems["leaf"],
        "self_signed_root": pems["root"],
        "leaf_not_authority": pems["leaf"],
        "stand_in_text": b"SYN-invented-chain-stand-in",
        "empty_file": b"",
        "der_not_pem": _der(pems["intermediate"]),
        "pem_then_text": pems["intermediate"] + b"SYN trailing text\n",
        "text_then_pem": b"SYN leading text\n" + pems["intermediate"],
    }


def test_the_tender_host_is_on_the_pin_allow_list() -> None:
    row = next(r for r in load_registry() if r.key == "tenders_pub")
    assert row.fetch_host == TENDER_HOST
    assert TENDER_HOST in PIN_HOSTS


def test_a_single_issuing_intermediate_is_admitted(tmp_path: Path) -> None:
    path, pin = _file(tmp_path, intermediate_pem())
    context = chain_context(path, pin)
    assert context.verify_mode == ssl.CERT_REQUIRED and context.check_hostname
    assert not context.verify_flags & ssl.VERIFY_X509_PARTIAL_CHAIN
    assert _der(intermediate_pem()) in context.get_ca_certs(binary_form=True)


@pytest.mark.parametrize("name", sorted(_plants()))
def test_a_file_that_is_not_one_issuing_authority_is_refused(
    tmp_path: Path, name: str
) -> None:
    # The pin matches the planted bytes: only the inspection can refuse them.
    path, pin = _file(tmp_path, _plants()[name])
    with pytest.raises(TenderError) as refused:
        chain_context(path, pin)
    assert refused.value.reason == INCOMPLETE


def test_a_missing_file_is_refused(tmp_path: Path) -> None:
    with pytest.raises(TenderError) as refused:
        chain_context(tmp_path / "absent.pem", "ab" * 32)
    assert refused.value.reason == INCOMPLETE


@pytest.mark.parametrize(
    "pin",
    ["", "ab" * 32, "ab" * 31, "SYN"],
    ids=["unreviewed", "other_hash", "short", "text"],
)
def test_a_pin_other_than_the_file_hash_is_refused(tmp_path: Path, pin: str) -> None:
    path, _right = _file(tmp_path, intermediate_pem())
    with pytest.raises(TenderError) as refused:
        chain_context(path, pin)
    assert refused.value.reason == INCOMPLETE


@pytest.mark.parametrize(
    "host",
    [
        *sorted(PIN_HOSTS - {TENDER_HOST}),
        TENDER_HOST.upper(),
        TENDER_HOST + ".",
        "SYN.invented.test",
        "",
    ],
)
def test_the_chain_is_scoped_to_the_tender_host(tmp_path: Path, host: str) -> None:
    path, pin = _file(tmp_path, intermediate_pem())
    with pytest.raises(TenderError) as refused:
        chain_context(path, pin, host=host)
    assert refused.value.reason == MISMATCH


@pytest.mark.parametrize("mode", ["no_verify", "no_hostname"])
def test_a_context_that_does_not_verify_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    def weak() -> ssl.SSLContext:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.check_hostname = False
        if mode == "no_verify":
            context.verify_mode = ssl.CERT_NONE
        return context

    monkeypatch.setattr(tenders.ssl, "create_default_context", weak)
    path, pin = _file(tmp_path, intermediate_pem())
    with pytest.raises(TenderError) as refused:
        chain_context(path, pin)
    assert refused.value.reason == INCOMPLETE


def test_trust_is_added_from_the_inspected_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    loaded: list[dict[str, object]] = []
    original = ssl.SSLContext.load_verify_locations

    def spy(self: ssl.SSLContext, *args: object, **kwargs: object) -> None:
        loaded.append(dict(kwargs, args=args))
        original(self, *args, **kwargs)  # type: ignore[arg-type]

    path, pin = _file(tmp_path, intermediate_pem())
    monkeypatch.setattr(tenders.ssl.SSLContext, "load_verify_locations", spy)
    chain_context(path, pin)
    # The file is read once; its checked bytes, not its path, extend trust.
    added = [call for call in loaded if "cadata" in call]
    assert [call["cadata"] for call in added][-1] == _der(intermediate_pem())
    assert not [call for call in loaded if "cafile" in call or call["args"]]


def test_fetch_tenders_scopes_the_chain_to_its_host(tmp_path: Path) -> None:
    path, pin = _file(tmp_path, intermediate_pem())
    calls: list[object] = []
    with pytest.raises(TenderError) as refused:
        fetch_tenders(
            calls.append,  # type: ignore[arg-type]
            chain_file=path,
            chain_sha256=pin,
            sleep=calls.append,
            clock=lambda: pytest.fail("no request is timed"),  # type: ignore[arg-type,return-value]
            host="www.qcb.gov.qa",
        )
    assert refused.value.reason == MISMATCH
    assert calls == []


def test_the_registry_holds_the_reviewed_pin() -> None:
    # The live run of 2026-11-19 placed the intermediate and its SHA-256 was
    # reviewed into the registry; the pin is one lowercase SHA-256, never empty.
    row = next(r for r in load_registry() if r.key == "tenders_pub")
    pin = row.chain_intermediate_sha256
    assert len(pin) == 64 and set(pin) <= set("0123456789abcdef")


def test_without_a_reviewed_chain_the_refusal_is_truthful(tmp_path: Path) -> None:
    # A row without a reviewed pin: even a valid invented intermediate is
    # refused before any request, with the truthful reason.
    committed = next(r for r in load_registry() if r.key == "tenders_pub")
    row = replace(committed, chain_intermediate_sha256="")
    path, _pin = _file(tmp_path, intermediate_pem())
    with pytest.raises(TenderError) as refused:
        tenders.tender_https(row, chain_file=path)
    assert refused.value.reason == INCOMPLETE
    reviewed = replace(row, chain_intermediate_sha256=_pin)
    assert callable(tenders.tender_https(reviewed, chain_file=path))


def test_inspect_intermediate_is_the_load_pin_inspection() -> None:
    pems = invented_pems()
    inspect_intermediate(_der(pems["intermediate"]))
    for planted in (
        _der(pems["root"]),
        _der(pems["leaf"]),
        _der(pems["intermediate"]) + _der(pems["root"]),
        b"SYN-not-a-certificate",
        b"",
    ):
        with pytest.raises(PinError, match=r"^certificate_chain_incomplete$"):
            inspect_intermediate(planted)


def _tls12_suites(context: ssl.SSLContext) -> set[str]:
    return {c["name"] for c in context.get_ciphers() if c["protocol"] == "TLSv1.2"}


def test_the_tender_context_adds_only_the_hosts_one_suite(tmp_path: Path) -> None:
    # LIVE-S2.r5: the tender host negotiates TLS 1.2 with RSA key exchange only
    # (AES128-GCM-SHA256); the interpreter's default list holds no such suite, so
    # every handshake closed. The tender context adds that one suite and keeps
    # every default suite, the protocol floor and certificate verification.
    default = ssl.create_default_context()
    assert TENDER_SUITE not in _tls12_suites(default)
    path, pin = _file(tmp_path, intermediate_pem())
    context = chain_context(path, pin)
    assert _tls12_suites(context) - _tls12_suites(default) == {TENDER_SUITE}
    assert _tls12_suites(default) <= _tls12_suites(context)
    assert context.minimum_version >= ssl.TLSVersion.TLSv1_2
    assert context.security_level == default.security_level
    assert context.verify_mode == ssl.CERT_REQUIRED and context.check_hostname


def test_a_wider_suite_list_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Planted: a context whose suite list grew beyond the one named suite.
    original = ssl.SSLContext.set_ciphers

    def wide(self: ssl.SSLContext, spec: str) -> None:
        original(self, spec + ":AES256-GCM-SHA384")

    monkeypatch.setattr(tenders.ssl.SSLContext, "set_ciphers", wide)
    path, pin = _file(tmp_path, intermediate_pem())
    with pytest.raises(TenderError) as refused:
        chain_context(path, pin)
    assert refused.value.reason == INCOMPLETE
