"""Exact output and refusal plants for the supplied S2-T29 survivor list."""

import hashlib
import json
from dataclasses import replace

import pytest
from custodian.tests.test_s2_t29_live_shapes import (
    STAMP,
    URL,
    classified,
    embedded,
    entry,
    workbook,
)

from eii_custodian.publicdata.fetch import page_acquire as acquire
from eii_custodian.publicdata.fetch.page_html import ShapeError
from eii_custodian.publicdata.fetch.snapshots import read_snapshot
from eii_custodian.publicdata.fetch.transport import Response, TransportFault


def run(tmp_path, dec, body, *, row=None, send=None, sleep=lambda _: None):
    return acquire.fetch(
        row or entry(dec),
        dec,
        send or (lambda u: Response(u, body, ())),
        tmp_path,
        lambda: STAMP,
        sleep,
    )


def refused(reason, call):
    with pytest.raises(ShapeError) as error:
        call()
    assert error.value.args == (reason,)


def test_html_canonical_render():
    body = (
        b'<div id="syn" disabled data-value="&quot;&amp;&lt;">a&amp;'
        b'<b>b</b>c</div><input name="__RequestVerificationToken" value="SYN-token">'
        b'<input name="SYN-other"><span name="__RequestVerificationToken">keep</span>'
        b"<script>a < b && c > d</script><style>a > b {}</style>"
    )
    assert acquire._html_without_form_secrets(body) == (
        b'<div id="syn" disabled data-value="&quot;&amp;&lt;">a&amp;'
        b'<b>b</b>c</div><input name="SYN-other">'
        b'<span name="__RequestVerificationToken">keep</span>'
        b"<script>a < b && c > d</script><style>a > b {}</style>"
    )


@pytest.mark.parametrize(
    "tag",
    "area base br col embed hr img input link meta param source track wbr".split(),
)
def test_html_void_render(tag):
    body = f'<div><{tag} data-syn="x"><i>tail</i></div>'.encode()
    assert acquire._html_without_form_secrets(body) == body


@pytest.mark.parametrize("source", ["events_qncc", "awards_owner_scrape"])
def test_validate_source_kind(source):
    dec, _, _ = embedded("script")
    if source == "awards_owner_scrape":
        dec, _ = classified()
        dec["shape"]["profile"] = "awards"
    acquire.validate_entry(entry(dec, source), dec)


@pytest.mark.parametrize(
    "plant,reason",
    [
        ("kind", "schema_missing"),
        ("commit", "commit_refused"),
        ("publisher", "receipt_missing"),
        ("decision_record", "receipt_missing"),
        ("licence_basis_unknown", "receipt_missing"),
        ("url", "blocked_host"),
        ("empty_urls", "blocked_host"),
        ("bad_url", "blocked_host"),
        ("tuple_urls", "blocked_host"),
        ("columns", "schema_missing"),
        ("bounds_min", "bounds_unconfirmed"),
        ("bounds_max", "bounds_unconfirmed"),
    ],
)
def test_validate_refusal(plant, reason):
    dec, _, _ = embedded()
    row = entry(dec)
    if plant == "kind":
        row = replace(row, source_id="SYN-unknown")
    elif plant == "commit":
        row = replace(row, commit_allowed=True)
    elif plant in {"publisher", "decision_record"}:
        row = replace(row, **{plant: ""})
        if plant == "decision_record":
            row = replace(row, licence_basis="owner_decision")
    elif plant == "licence_basis_unknown":
        # A pending basis never refuses; an unknown non-empty one still does.
        row = replace(row, licence_basis="SYN-basis")
    elif plant == "url":
        row = replace(row, url=URL + "/SYN-other")
        dec["reviewed_urls"].append(row.url)
    elif plant == "empty_urls":
        dec["reviewed_urls"] = []
    elif plant == "bad_url":
        dec["reviewed_urls"].append(5)
    elif plant == "tuple_urls":
        dec["reviewed_urls"] = tuple(dec["reviewed_urls"])
    elif plant == "columns":
        row = replace(row, columns=(("SYN-other", "string"),))
    else:
        row = replace(
            row, **{"row_count_min" if plant == "bounds_min" else "row_count_max": 1}
        )
    refused(reason, lambda: acquire.validate_entry(row, dec))


@pytest.mark.parametrize(
    "basis", ["dataset", "portal_terms", "provider_terms", "pending", ""]
)
def test_validate_licence_basis(basis):
    dec, _, _ = embedded()
    acquire.validate_entry(replace(entry(dec), licence_basis=basis), dec)


def test_pending_terms_fields_still_fetch_and_record(tmp_path):
    """Ruling L-1001: pending terms fields never refuse the page fetch."""
    dec, body, _ = embedded()
    row = replace(
        entry(dec),
        terms_words="",
        terms_read_on="",
        licence_basis="",
    )
    result = run(tmp_path, dec, body, row=row)
    payload = json.loads(result.body)
    assert payload["rows"]
    assert result.sidecar["terms_words"] == ""
    assert result.sidecar["terms_read_on"] == ""
    assert result.sidecar["licence_basis"] == ""


def test_validate_observed_bounds():
    dec, _, _ = embedded()
    dec["bounds_basis"] = "observed"
    acquire.validate_entry(replace(entry(dec), row_count_min=1), dec)


def test_missing_acquisition_bound(tmp_path):
    dec, body, _ = embedded()
    dec["max_bytes"] = None
    refused("acquisition_bound_unconfirmed", lambda: run(tmp_path, dec, body))


def test_refusal_receipt(tmp_path):
    from custodian.tests.test_s2_t29_live_shapes import declaration

    dec = declaration(
        "refusal",
        {
            "reason": "anonymous_access_not_approved",
            "observed_utc": STAMP,
            "decision": "SYN-decision",
        },
        [],
    )
    row = entry(dec, "suppliers_tawteen")
    refused(dec["shape"]["reason"], lambda: run(tmp_path, dec, b"", row=row))
    records = [
        json.loads(p.read_text(encoding="utf-8")) for p in tmp_path.rglob("*.json")
    ]
    assert any(
        r.get("reason") == dec["shape"]["reason"]
        and r.get("attempted_utc") == dec["shape"]["observed_utc"]
        for r in records
    )


@pytest.mark.parametrize("marker", ["SiGn In", "sign-in", "robot check", "paywall"])
def test_access_barrier(tmp_path, marker):
    dec, body, _ = embedded()
    refused("unavailable", lambda: run(tmp_path, dec, body + marker.encode()))


@pytest.mark.parametrize("delta", [-1, 0])
def test_byte_boundary(tmp_path, delta):
    dec, body, record = embedded()
    dec["max_bytes"] = len(body) + delta
    if delta:
        refused("metadata_bytes", lambda: run(tmp_path, dec, body))
    else:
        assert json.loads(run(tmp_path, dec, body).body)["rows"] == [
            {
                "title": "SYN > event",
                "start": "2031-02-03",
                "end": "2031-02-04",
                "published_record": record,
            }
        ]


def test_retry_sleep_and_reason(tmp_path):
    dec, _, _ = embedded()
    calls, sleeps = [], []

    def send(url):
        calls.append(url)
        raise TransportFault("unreachable", url)

    refused(
        "unreachable", lambda: run(tmp_path, dec, b"", send=send, sleep=sleeps.append)
    )
    assert calls == [URL] * 4
    assert sleeps == [1.0, 2.0, 4.0]


@pytest.mark.parametrize(
    "period_last,reason", [("2031-02-04", None), ("2031-02-05", "stale_period")]
)
def test_period_boundary(tmp_path, period_last, reason):
    dec, body, _ = embedded()
    row = replace(entry(dec), period_last=period_last)
    if reason:
        refused(reason, lambda: run(tmp_path, dec, body, row=row))
    else:
        assert (
            json.loads(run(tmp_path, dec, body, row=row).body)["period_last"]
            == period_last
        )


def test_absent_period_refusal(tmp_path):
    dec, body, _ = embedded()
    dec["period_fields"] = []
    row = replace(entry(dec), period_last="2031")
    refused("stale_period", lambda: run(tmp_path, dec, body, row=row))


@pytest.mark.parametrize(
    "lo,hi,reason", [(1, 1, None), (2, None, "row_count"), (None, 0, "row_count")]
)
def test_row_count_boundary(tmp_path, lo, hi, reason):
    dec, body, _ = embedded()
    dec["bounds_basis"] = "observed"
    row = replace(entry(dec), row_count_min=lo, row_count_max=hi)
    if reason:
        refused(reason, lambda: run(tmp_path, dec, body, row=row))
    else:
        assert len(json.loads(run(tmp_path, dec, body, row=row).body)["rows"]) == 1


@pytest.mark.parametrize("with_terms", [False, True])
def test_complete_receipt_and_canonical_envelope(tmp_path, with_terms):
    from eii_custodian.publicdata.fetch.terms_text import terms_text_sha256

    dec, body, record = embedded()
    dec["publisher_date"] = "2031-02-01" if with_terms else None
    row = entry(dec)
    term_body = b"<p>SYN terms</p>"
    if with_terms:
        row = replace(row, terms_url=URL + "/SYN-terms")
        dec["reviewed_urls"].append(row.terms_url)
    result = run(
        tmp_path,
        dec,
        body,
        row=row,
        send=lambda u: Response(u, term_body if u == row.terms_url else body, ()),
    )
    payload = json.loads(result.body)
    assert result.body == json.dumps(payload, sort_keys=True).encode()
    assert payload == {
        "version": 2,
        "source_id": row.source_id,
        "rows": [
            {
                "title": "SYN > event",
                "start": "2031-02-03",
                "end": "2031-02-04",
                "published_record": record,
            }
        ],
        "inputs": payload["inputs"],
        "as_of": STAMP[:10],
        "publisher_date": dec["publisher_date"],
        "period_first": "2031-02-03",
        "period_last": "2031-02-04",
        "retrieved_utc": STAMP,
        "method": "page_acquire.fetch@v2",
        "provenance": "Public",
        "completeness": "unknown",
        "coverage": [],
    }
    terms_hash = terms_text_sha256(term_body) if with_terms else ""
    for name, value in {
        "fetch_url": row.url,
        "fetch_host": "www.data.gov.qa",
        "publisher": row.publisher,
        "source_modified": dec["publisher_date"] or None,
        "row_count": 1,
        "terms_sha256": terms_hash or None,
        "period_first": "2031-02-03",
        "period_last": "2031-02-04",
        "method": "page_acquire.fetch@v2",
        "terms_unread": "",
    }.items():
        assert result.sidecar[name] == value
    for i, item in enumerate(payload["inputs"]):
        original = body if i == 0 else term_body
        normalized = acquire._html_without_form_secrets(original)
        digest = hashlib.sha256(normalized).hexdigest()
        upstream = hashlib.sha256(original).hexdigest()
        address = row.url if i == 0 else row.terms_url
        assert item == {
            "key": f"inputs/input-{i}",
            "identity": digest,
            "sha256": digest,
            "upstream_sha256": upstream,
            "extension": "html",
            "representation": "form_secret_removed",
            "url": address,
        }
        raw = read_snapshot(tmp_path / row.key / item["key"], item["identity"])
        assert raw.body == normalized
        for name, value in {
            "fetch_url": address,
            "fetch_host": "www.data.gov.qa",
            "publisher": row.publisher,
            "source_modified": None,
            "row_count": None,
            "terms_sha256": terms_hash or None,
            "upstream_sha256": upstream,
            "representation": "form_secret_removed",
            "as_of": STAMP[:10],
        }.items():
            assert raw.sidecar[name] == value


@pytest.mark.parametrize(
    "reason",
    ["unreachable", "http_status", "access_failed", "unavailable", "schema_missing"],
)
def test_terms_failure_policy(tmp_path, reason):
    dec, body, _ = embedded()
    row = replace(entry(dec), terms_url=URL + "/SYN-terms")
    dec["reviewed_urls"].append(row.terms_url)

    def send(url):
        if url != row.terms_url:
            return Response(url, body, ())
        if reason == "access_failed":
            raise ShapeError(reason)
        if reason in {"unreachable", "http_status"}:
            raise TransportFault(reason, url)
        return Response(url, b"paywall" if reason == "unavailable" else b"\xff", ())

    if reason == "schema_missing":
        refused(reason, lambda: run(tmp_path, dec, body, row=row, send=send))
    else:
        result = run(tmp_path, dec, body, row=row, send=send)
        assert result.sidecar["terms_unread"] == reason
        assert result.sidecar["terms_sha256"] is None


def test_xlsx_original_envelope(tmp_path):
    dec, body = workbook()
    row = entry(dec, "insurance_tables")
    result = run(tmp_path, dec, body, row=row)
    payload = json.loads(result.body)
    (item,) = payload["inputs"]
    assert item["extension"] == "xlsx" and item["representation"] == "original"
    assert (
        read_snapshot(tmp_path / row.key / item["key"], item["identity"]).body == body
    )
