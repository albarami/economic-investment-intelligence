"""Fix-six plants: refusal metadata, school envelopes and unscoped pin hosts."""

import json
from copy import deepcopy
from dataclasses import replace
from http.client import HTTPMessage
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit
from urllib.request import Request

import pytest
from custodian.tests.test_s2_t29_live_acquire import school, school_transport
from custodian.tests.test_s2_t29_live_shapes import STAMP, embedded, entry

from eii_custodian.publicdata.fetch.allowlist import approve
from eii_custodian.publicdata.fetch.build import run_build
from eii_custodian.publicdata.fetch.certificate_pins import (
    PinError,
    current_pin,
    page_transport,
)
from eii_custodian.publicdata.fetch.page_acquire import validate_entry
from eii_custodian.publicdata.fetch.page_records import fetch_page, load_declaration
from eii_custodian.publicdata.fetch.page_requests import PIN_HOSTS, active
from eii_custodian.publicdata.fetch.registry import load_registry
from eii_custodian.publicdata.fetch.transport import (
    Response,
    _redirect_guard,
    open_https,
)


def test_only_four_page_pin_hosts_remain():
    assert PIN_HOSTS == {
        "www.qcb.gov.qa",
        "monaqasat.mof.gov.qa",
        "www.edu.gov.qa",
        "myschools.edu.gov.qa",
    }
    assert not approve("https://www.tawteen.com.qa/SYN").ok
    assert not approve("https://icv.qa/SYN").ok


@pytest.mark.parametrize("host", ["icv.qa", "syn-refusal.invalid"])
def test_off_list_refusal_loads_and_normal_dispatch_never_fetches(tmp_path, host):
    row = next(r for r in load_registry() if r.source_id == "suppliers_tawteen")
    dec = deepcopy(load_declaration(row.source_id))
    url = "https://" + host + "/SYN-refusal"
    terms = "https://" + host + "/SYN-terms"
    row = replace(row, url=url, terms_url=terms, fetch_host=host)
    dec.update(url=url, reviewed_urls=[url, terms])
    assert not approve(url).ok and not approve(terms).ok
    validate_entry(row, dec)
    calls = []

    def transport(address):
        calls.append(address)
        pytest.fail("refusal metadata must never fetch data or terms")

    with patch(
        "eii_custodian.publicdata.fetch.page_records.load_declaration", return_value=dec
    ):
        outcome = run_build((row,), transport, tmp_path, lambda: STAMP, lambda _: None)
    assert outcome.failure is None
    assert any(line.startswith(f"SKIP {row.key}") for line in outcome.lines)
    receipts = list((tmp_path / row.key / "failures" / "index").glob("*.json"))
    assert len(receipts) == 1
    recorded = b"".join(
        p.read_bytes() for p in (tmp_path / row.key / "failures").rglob("*.json")
    )
    assert dec["shape"]["observed_utc"].encode() in recorded
    assert dec["shape"]["reason"].encode() in recorded
    assert calls == []
    # Clearing the dispatch hold still records the refusal without a connection.
    with pytest.raises(ValueError, match=r"^anonymous_access_not_approved$"):
        fetch_page(
            row, transport, tmp_path, lambda: STAMP, lambda _: None, declaration=dec
        )
    assert calls == []


def test_off_list_fetching_row_refuses_without_transport(tmp_path):
    dec, _, _ = embedded()
    url = "https://syn-refusal.invalid/SYN-fetch"
    dec.update(url=url, reviewed_urls=[url])
    row = entry(dec)
    calls = []
    with patch(
        "eii_custodian.publicdata.fetch.page_records.load_declaration", return_value=dec
    ):
        outcome = run_build(
            (row,), lambda u: calls.append(u), tmp_path, lambda: STAMP, lambda _: None
        )
    assert outcome.failure is not None and outcome.failure.check == "blocked_host"
    assert calls == []
    assert not (tmp_path / row.key).exists()


@pytest.mark.parametrize(
    "url",
    [
        "http://syn-refusal.invalid/SYN",
        "https://syn-refusal.invalid/SYN?token=SYN",
        "https://SYN:SYN" + "@" + "syn-refusal.invalid/SYN",
        "https://syn-refusal.invalid/SYN#SYN",
    ],
)
def test_refusal_exemption_preserves_scheme_and_credential_checks(url):
    row = next(r for r in load_registry() if r.source_id == "suppliers_tawteen")
    dec = deepcopy(load_declaration(row.source_id))
    row = replace(row, url=url)
    dec.update(url=url, reviewed_urls=[url])
    with pytest.raises(ValueError, match=r"^blocked_host$"):
        validate_entry(row, dec)


def test_evidenced_school_envelope_keeps_all_inputs(tmp_path):
    dec, attrs = school()
    calls = []
    benign = school_transport(attrs, calls)

    def transport(url):
        response = benign(url)
        if "resultOffset" in parse_qs(urlsplit(url).query):
            body = json.loads(response.body)
            body.update(
                objectIdFieldName="objectid",
                hasZ=False,
                hasM=False,
                fields=[{"name": name} for name in dec["shape"]["fields"]],
            )
            return Response(url, json.dumps(body).encode(), ())
        return response

    result = fetch_page(
        entry(dec, "schools_private_directory"),
        transport,
        tmp_path,
        lambda: STAMP,
        lambda _: None,
        declaration=dec,
    )
    payload = json.loads(result.body)
    assert len(payload["rows"]) == 2 and len(calls) == 4
    assert len(payload["inputs"]) == 4
    assert all(item["representation"] == "original" for item in payload["inputs"])


@pytest.mark.parametrize("role", ["count", "page"])
def test_school_top_level_owner_refused_without_archive(tmp_path, role):
    dec, attrs = school()
    calls = []
    benign = school_transport(attrs, calls)

    def transport(url):
        response = benign(url)
        query = parse_qs(urlsplit(url).query)
        target = (
            query.get("returnCountOnly") == ["true"]
            if role == "count"
            else "resultOffset" in query
        )
        if target:
            body = json.loads(response.body)
            body["owner"] = "SYN excluded contact"
            return Response(url, json.dumps(body).encode(), ())
        return response

    with pytest.raises(ValueError, match=r"^school_field_refused$"):
        fetch_page(
            entry(dec, "schools_private_directory"),
            transport,
            tmp_path,
            lambda: STAMP,
            lambda _: None,
            declaration=dec,
        )
    assert len(calls) == (2 if role == "count" else 3)
    assert not list(tmp_path.rglob("index/*.json"))
    assert not [p for p in tmp_path.rglob("*") if p.is_file()]


@pytest.mark.parametrize("host", sorted(PIN_HOSTS))
@pytest.mark.parametrize("role", ["initial", "redirect"])
def test_unscoped_page_pin_host_refuses_before_send(host, role):
    url = "https://" + host + "/SYN-unscoped"
    initial = "https://www.data.gov.qa/SYN-initial"
    hops = []
    with (
        page_transport(None),
        patch("urllib.request.build_opener") as opener,
        patch("urllib.request.HTTPRedirectHandler.redirect_request") as redirect_base,
    ):
        response = opener.return_value.open.return_value.__enter__.return_value
        response.read.return_value = b"SYN response"
        response.geturl.return_value = url
        response.headers = {}
        assert not active() and current_pin() is None
        with pytest.raises(PinError, match=r"^certificate_chain_incomplete$"):
            if role == "initial":
                open_https(url)
            else:
                _redirect_guard(hops)().redirect_request(
                    Request(initial), None, 302, "SYN", HTTPMessage(), url
                )
        assert opener.call_count == 0
        assert opener.return_value.open.call_count == 0
        assert redirect_base.call_count == 0
        assert hops == []
