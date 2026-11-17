"""Exact listing refusals and evidence, with invented offline transports."""

import base64
import json
from dataclasses import replace

import pytest
from custodian.tests.test_places_fetch import _entry as part_entry
from custodian.tests.test_publicdata_behaviour import _entry, _ok, _sleep
from custodian.tests.test_publicdata_unblocked_round2 import listing_body

from eii_custodian.publicdata.fetch import allowlist, listing, registry
from eii_custodian.publicdata.fetch.checks import AttemptFailure
from eii_custodian.publicdata.fetch.kinds import Prepared, prepare
from eii_custodian.publicdata.fetch.transport import TransportFault

HOST = "invented-listing.invalid"
PREFIX = "invented-release/"
BASE = "https://invented-listing.invalid/?list-type=2&prefix=invented-release/"
KEY = "invented-release/invented.parquet"


def fixture(monkeypatch):
    monkeypatch.setattr(listing, "HOST", HOST)
    monkeypatch.setattr(listing, "PREFIXES", {"places_ovt": PREFIX})
    monkeypatch.setattr(
        allowlist, "ALLOWED_HOSTS", frozenset({HOST, "invented-other.invalid"})
    )
    parent = replace(
        _entry(),
        key="places_ovt",
        url=BASE,
        fetch_host=HOST,
        publisher="Invented publisher",
        landing_url=BASE,
    )
    part = replace(
        part_entry(4, "https://invented-listing.invalid/" + KEY),
        fetch_host=HOST,
        publisher="Invented publisher",
        landing_url=BASE,
    )
    monkeypatch.setattr(registry, "load_registry", lambda: (parent, part))
    return parent, part


def assert_refusal(result, url, check):
    """Compare every refusal field, including the whole diagnostic literals."""
    assert result == Prepared(
        b"",
        url,
        "",
        "Invented publisher",
        "",
        None,
        "",
        AttemptFailure(1, url, check, "registered release listing", "invalid"),
    )


@pytest.mark.parametrize(
    "plant",
    [
        "url",
        "empty",
        "unrelated",
        "size_record",
        "etag_record",
        "prefix",
        "host",
        "leading_x",
    ],
)
def test_registered_refusals(monkeypatch, plant):
    parent, part = fixture(monkeypatch)
    entries = (part,)
    check = "listing_registered_part"
    if plant == "url":
        parent = replace(parent, url=BASE + "&invented=wrong")
        check = "listing_url"
    elif plant == "empty":
        entries = ()
    elif plant == "unrelated":
        entries = (replace(part, key="places_ovt_other/invented"),)
    elif plant == "size_record":
        entries = (
            replace(
                part, basis_note="recorded_bytes: invalid\nrecorded_etag: syn-etag\n"
            ),
        )
    elif plant == "etag_record":
        entries = (replace(part, basis_note="recorded_bytes: 4\n"),)
    elif plant == "prefix":
        entries = (
            replace(
                part, url="https://invented-listing.invalid/wrong/invented.parquet"
            ),
        )
    elif plant == "host":
        entries = (replace(part, url="https://invented-other.invalid/" + KEY),)
    elif plant == "leading_x":
        entries = (replace(part, url="https://invented-listing.invalid/X" + KEY),)

    result = prepare(
        parent,
        lambda url: _ok(url, listing_body(key=KEY)),
        _sleep,
        registry_entries=entries,
    )
    assert_refusal(result, parent.url, check)


@pytest.mark.parametrize(
    ("plant", "check"),
    [
        ("malformed", "listing_xml"),
        ("root", "listing_xml"),
        ("prefix", "listing_prefix"),
        ("missing_key", "listing_prefix"),
        ("duplicate", "listing_duplicate"),
        ("size", "listing_size"),
        ("etag", "listing_etag"),
        ("missing", "listing_missing"),
        ("redirect", "listing_redirect"),
        ("final_redirect", "listing_redirect"),
        ("empty_token", "listing_continuation"),
        ("missing_token", "listing_continuation"),
        ("bad_truncated", "listing_continuation"),
        ("repeated_token", "listing_continuation"),
    ],
)
def test_page_refusals(monkeypatch, plant, check):
    parent, part = fixture(monkeypatch)
    body = listing_body(key=KEY)
    if plant == "malformed":
        body = b"<invented"
    elif plant == "root":
        body = b"<invented/>"
    elif plant == "prefix":
        body = listing_body(key="wrong/invented.parquet")
    elif plant == "missing_key":
        body = body.replace(b"<Key>invented-release/invented.parquet</Key>", b"")
    elif plant == "duplicate":
        body = listing_body(key=KEY, truncated=True, token="invented")
    elif plant == "size":
        body = listing_body(key=KEY, size="5")
    elif plant == "etag":
        body = listing_body(key=KEY, etag="invented-other")
    elif plant == "missing":
        body = listing_body(key=PREFIX + "other.parquet")
    elif plant in {"empty_token", "missing_token"}:
        body = listing_body(key=KEY, truncated=True)
        if plant == "missing_token":
            body = body.replace(b"<NextContinuationToken></NextContinuationToken>", b"")
    elif plant == "bad_truncated":
        body = listing_body(key=KEY, truncated="invented", token="invented")
    elif plant == "repeated_token":
        body = listing_body(key=KEY, truncated=True, token="invented")
    calls = []

    def transport(url):
        calls.append(url)
        assert len(calls) <= 2
        response_body = body
        if plant == "repeated_token" and len(calls) == 2:
            response_body = listing_body(
                key=PREFIX + "other.parquet", truncated=True, token="invented"
            )
        hops = (
            ("https://invented-other.invalid/invented",) if plant == "redirect" else ()
        )
        final = (
            "https://invented-other.invalid/invented"
            if plant == "final_redirect"
            else url
        )
        return _ok(final, response_body, hops)

    assert_refusal(
        prepare(parent, transport, _sleep, registry_entries=(part,)), BASE, check
    )
    assert len(calls) == (2 if plant in {"duplicate", "repeated_token"} else 1)


def test_transport_failure(monkeypatch):
    parent, part = fixture(monkeypatch)

    def transport(url):
        raise TransportFault("blocked_host", url)

    result = prepare(parent, transport, _sleep, registry_entries=(part,))
    assert result == Prepared(
        b"",
        "https://invented-listing.invalid/",
        "",
        "Invented publisher",
        "",
        None,
        "",
        AttemptFailure(
            1,
            "https://invented-listing.invalid/",
            "blocked_host",
            "allow-listed host",
            "https://invented-listing.invalid/",
        ),
    )
    assert all(
        "list-type=2" not in address and "invented-release/" not in address
        for address in (
            result.fetch_url,
            result.failure.url,
            result.failure.observed,
        )
    )


@pytest.mark.parametrize("default_registry", [False, True])
def test_prepared_pages_and_defaults(monkeypatch, default_registry):
    parent, part = fixture(monkeypatch)
    first = listing_body(
        key=PREFIX + "other.parquet", truncated=True, token="invented /+"
    )
    second = listing_body(key=KEY)
    calls = []

    def transport(url):
        calls.append(url)
        assert len(calls) <= 2
        return _ok(url, first if len(calls) == 1 else second)

    if default_registry:
        result = prepare(parent, transport, _sleep)
    else:
        result = prepare(parent, transport, _sleep, registry_entries=(parent, part))
    assert calls == [BASE, BASE + "&continuation-token=invented+%2F%2B"]
    assert result.failure is None
    assert (result.fetch_url, result.fetch_host, result.publisher) == (
        BASE,
        "invented-listing.invalid",
        "Invented publisher",
    )
    assert (result.source_modified, result.row_count, result.terms_sha256) == (
        "",
        2,
        "",
    )
    assert (result.portal_licence, result.portal_licence_url, result.terms_unread) == (
        "",
        "",
        "",
    )
    assert len(result.requests) == 2
    assert [r["row_count"] for r in result.requests] == [1, 1]
    assert [r["url"] for r in result.requests] == [
        BASE,
        BASE + "&continuation-token=invented+%2F%2B",
    ]
    envelope = json.loads(result.body)
    assert set(envelope) == {"listing_pages_base64"}
    assert [base64.b64decode(page) for page in envelope["listing_pages_base64"]] == [
        first,
        second,
    ]
