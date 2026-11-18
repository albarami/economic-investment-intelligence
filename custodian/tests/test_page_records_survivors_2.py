"""The page fetch seam: delegation, pin loading, capture branches, receipts, terms.

Every transport is an invented in-process callable; no socket is opened.
"""

import hashlib
import json
import ssl
from dataclasses import replace

import pytest
from custodian.tests import test_certificate_pins_survivors_1 as pin_tests
from custodian.tests import test_s2_t29_fix10 as fix10
from custodian.tests import test_s2_t29_pages as pages

from eii_custodian.publicdata.fetch import certificate_pins, page_acquire, page_records
from eii_custodian.publicdata.fetch.page_records import PageError
from eii_custodian.publicdata.fetch.snapshots import read_snapshot
from eii_custodian.publicdata.fetch.terms_text import terms_text_sha256
from eii_custodian.publicdata.fetch.transport import Response, TransportFault

STAMP = pages.STAMP
URL = pages.URL
HOST = "www.data.gov.qa"
TERMS = "https://www.data.gov.qa/SYN-terms"
SCHOOL = "schools_private_directory"

# The shared module fixture generates one disposable chain, never a host certificate.
invented_certs = fix10.invented_certs
isolated_trust = pin_tests.isolated_trust


def test_default_context_trust_is_only_the_invented_root(invented_certs):
    context = ssl.create_default_context()
    assert context.get_ca_certs(binary_form=True) == [invented_certs["root"]]
    assert context.verify_mode == ssl.CERT_REQUIRED and context.check_hostname


def exact(reason):
    return "^" + reason + "$"


def school_row(**changes):
    return replace(pages.page_entry(), source_id=SCHOOL, key=SCHOOL, **changes)


def fake_pin():
    der = b"SYN-intermediate"
    return certificate_pins.Pin(HOST, hashlib.sha256(der).hexdigest(), der, True)


def ok(url):
    return Response(url, pages.BODY, ())


def unreachable(url):
    raise TransportFault("unreachable", url)


def run(row, transport, cache, sleep=lambda _: None, **options):
    options.setdefault("declaration", pages.review(row))
    return page_records.fetch_page(
        row, transport, cache, lambda: STAMP, sleep, **options
    )


def failure_record(cache, row, reason):
    expected = json.dumps(
        {
            "source_id": row.source_id,
            "attempted_utc": STAMP,
            "reason": reason,
            "coverage": "NO_DATA",
        },
        sort_keys=True,
    ).encode()
    snapshot = read_snapshot(
        cache / row.key / "failures", hashlib.sha256(expected).hexdigest()
    )
    assert snapshot.body == expected
    return snapshot


def test_supplier_page_needs_a_reviewed_refusal(tmp_path):
    row = replace(pages.page_entry(), source_id="suppliers_tawteen")
    with pytest.raises(PageError, match=exact("anonymous_access_not_approved")):
        run(row, ok, tmp_path)


def test_version_two_delegates_every_argument(tmp_path, monkeypatch):
    seen = []
    result = object()

    def fetch(*args):
        seen.append(args)
        return result

    monkeypatch.setattr(page_acquire, "fetch", fetch)
    row = pages.page_entry()
    declaration = dict(pages.review(row), version=2)

    def clock():
        return STAMP

    def sleep(_):
        return None

    assert (
        page_records.fetch_page(
            row, ok, tmp_path, clock, sleep, declaration=declaration
        )
        is result
    )
    assert len(seen) == 1
    assert seen[0][0] is row and seen[0][1] is declaration
    assert seen[0][2] is ok and seen[0][3] == tmp_path
    assert seen[0][4] is clock and seen[0][5] is sleep


def test_pinned_source_loads_reviewed_pin_config(tmp_path, monkeypatch, invented_certs):
    calls = []
    host = "www.edu.gov.qa"
    url = "https://" + host + "/SYN-page"
    config = fix10.config_file(tmp_path, invented_certs["intermediate"], host, SCHOOL)
    real_load_pin = page_records.load_pin

    def load_pin(cache, source, value):
        calls.append((cache, source, value))
        return real_load_pin(cache, source, value)

    monkeypatch.setattr(page_records, "load_pin", load_pin)
    row = school_row(url=url, fetch_host=host)
    declaration = dict(pages.review(row), url=url, reviewed_urls=[url], pin=config)
    result = run(row, ok, tmp_path, declaration=declaration)
    assert calls == [(tmp_path, SCHOOL, config)]
    assert calls[0][2] is config
    assert json.loads(result.body)["rows"] == [{"syn_name": "SYN-item", "syn_count": 7}]


def test_published_page_receipt_fields(tmp_path):
    row = pages.page_entry()
    result = run(row, ok, tmp_path)
    digest = hashlib.sha256(pages.BODY).hexdigest()
    side = result.sidecar
    assert side["fetch_url"] == URL
    assert side["fetch_host"] == HOST
    assert side["publisher"] == row.publisher
    assert side["source_modified"] is None
    assert side["row_count"] == 1
    assert side["terms_sha256"] is None
    assert side["as_of"] == "2024-02-03"
    assert side["source_period"] == "2024"
    assert side["method"] == "page_records.parse_page_snapshot@v1"
    assert side["capture"] == {}
    assert side["page_sha256"] == digest
    assert side["raw_identity"] == digest
    assert "terms_unread" not in side
    payload = json.loads(result.body)
    assert result.body == json.dumps(payload, sort_keys=True).encode()
    assert payload["page_sha256"] == payload["raw_identity"] == digest
    raw = read_snapshot(tmp_path / row.key / "raw", digest)
    assert raw.sidecar["capture"] == {}
    assert raw.sidecar["fetch_url"] == URL and raw.sidecar["row_count"] == 1


def test_other_page_failure_keeps_transport_reason(tmp_path):
    with pytest.raises(PageError, match=exact("unreachable")):
        run(pages.page_entry(), unreachable, tmp_path)


def test_redirect_hop_outside_review_refused(tmp_path):
    def redirected(url):
        return Response(URL, pages.BODY, (HOST.join(("https://", "/SYN-hop")),))

    with pytest.raises(PageError, match=exact("blocked_host")):
        run(pages.page_entry(), redirected, tmp_path)


def write_capture(cache, pin, record_changes=None, raw=None):
    folder = cache / "intake" / SCHOOL
    folder.mkdir(parents=True)
    (folder / "SYN.html").write_bytes(pages.BODY)
    record = {
        "file": "SYN.html",
        "initial_url": URL,
        "final_url": URL,
        "hops": [],
        "tool": "SYN browser",
        "captured_utc": STAMP,
        "sha256": hashlib.sha256(pages.BODY).hexdigest(),
        "intermediate_host": pin.host,
        "intermediate_sha256": pin.sha256,
        "tls_verified": True,
        "access": "visitor",
    }
    record.update(record_changes or {})
    (folder / "capture.json").write_bytes(
        raw if raw is not None else json.dumps(record).encode()
    )


def test_school_capture_from_intake_admitted_with_evidence(tmp_path, invented_certs):
    pin = fix10.make_pin(invented_certs["intermediate"], HOST)
    write_capture(tmp_path, pin)
    result = run(school_row(), unreachable, tmp_path, pin=pin)
    assert json.loads(result.body)["rows"] == [{"syn_name": "SYN-item", "syn_count": 7}]
    assert result.sidecar["capture"] == {
        "initial_url": URL,
        "final_url": URL,
        "redirect_urls": [],
        "tool": "SYN browser",
        "captured_utc": STAMP,
        "sha256": hashlib.sha256(pages.BODY).hexdigest(),
        "intermediate_host": HOST,
        "intermediate_sha256": pin.sha256,
        "tls_verified": True,
        "access": "visitor",
    }


@pytest.mark.parametrize(
    "changes,raw",
    [({"SYN": "extra"}, None), ({}, b'{"file": "\xff"}')],
    ids=["typed-pin-error", "undecodable"],
)
def test_school_intake_capture_failure_recorded(tmp_path, invented_certs, changes, raw):
    pin = fix10.make_pin(invented_certs["intermediate"], HOST)
    write_capture(tmp_path, pin, changes, raw)
    row = school_row()
    with pytest.raises(PageError, match=exact("capture_evidence_missing")):
        run(row, unreachable, tmp_path, pin=pin)
    failure_record(tmp_path, row, "capture_evidence_missing")
    assert not (tmp_path / row.key / "index").exists()


def test_school_without_capture_refused_as_access_failed(tmp_path, invented_certs):
    pin = fix10.make_pin(invented_certs["intermediate"], HOST)
    row = school_row()
    with pytest.raises(PageError, match=exact("access_failed")):
        run(row, unreachable, tmp_path, pin=pin)
    failure_record(tmp_path, row, "access_failed")


def test_school_supplied_capture_untyped_error_recorded(tmp_path, invented_certs):
    pin = fix10.make_pin(invented_certs["intermediate"], HOST)
    body = pages.BODY
    capture = certificate_pins.Capture(
        body,
        URL,
        URL,
        ("https://[SYN-hop",),
        "SYN browser",
        STAMP,
        hashlib.sha256(body).hexdigest(),
        pin,
        True,
        "visitor",
    )
    row = school_row()
    with pytest.raises(PageError, match=exact("capture_evidence_missing")):
        run(row, unreachable, tmp_path, pin=pin, capture=capture)
    failure_record(tmp_path, row, "capture_evidence_missing")


def terms_transport(seen, fail=False):
    def transport(url):
        seen.append((url, certificate_pins.current_pin()))
        if url == TERMS:
            if fail:
                raise TransportFault("unreachable", url)
            return Response(url, b"<p>SYN-terms</p>", ())
        return ok(url)

    return transport


def test_terms_read_inside_the_page_pin_and_archived_with_its_url(tmp_path):
    pin = fake_pin()
    row = school_row(terms_url=TERMS)
    seen = []
    result = run(row, terms_transport(seen), tmp_path, pin=pin)
    assert [url for url, _ in seen] == [URL, TERMS]
    assert all(current is pin for _, current in seen)
    assert result.sidecar["terms_sha256"] == terms_text_sha256(b"<p>SYN-terms</p>")
    assert result.sidecar["terms_unread"] == ""
    index = list((tmp_path / row.key / "terms" / "index").glob("*.json"))
    assert len(index) == 1
    terms = read_snapshot(tmp_path / row.key / "terms", index[0].stem)
    assert terms.sidecar["fetch_url"] == TERMS
    assert terms.sidecar["fetch_host"] == HOST


def test_terms_failure_retried_and_recorded_as_unread(tmp_path):
    row = replace(pages.page_entry(), terms_url=TERMS)
    seen = []
    pauses = []
    result = run(row, terms_transport(seen, fail=True), tmp_path, sleep=pauses.append)
    assert pauses == [1.0, 2.0, 4.0]
    assert [url for url, _ in seen] == [URL, TERMS, TERMS, TERMS, TERMS]
    assert result.sidecar["terms_unread"] == "unreachable"
    assert result.sidecar["terms_sha256"] is None
    assert not (tmp_path / row.key / "terms").exists()
