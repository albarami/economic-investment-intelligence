"""Complete portal and transport refusals on invented responses."""

import json
from dataclasses import replace

import pytest
from custodian.tests.test_fetch_kinds_survivors import message
from custodian.tests.test_publicdata_behaviour import (
    FILE_URL,
    META,
    PORTAL,
    _entry,
    _ok,
    _portal_meta,
    _sleep,
)

from eii_custodian.publicdata.fetch import kinds
from eii_custodian.publicdata.fetch.checks import AttemptFailure
from eii_custodian.publicdata.fetch.transport import TransportFault


def portal(**changes):
    return replace(_entry(), kind="portal_dataset", url=PORTAL, **changes)


def transport(meta, rows):
    def read(url):
        assert url in (META, PORTAL)
        return _ok(url, json.dumps(meta if url == META else rows).encode())

    return read


def refusal(result, url, check, expected, observed, publisher="Planted publisher"):
    assert result == kinds.Prepared(
        b"",
        url,
        "",
        publisher,
        "",
        None,
        "",
        AttemptFailure(1, url, check, expected, observed),
    )


@pytest.mark.parametrize(
    "meta,publisher,check,expected,observed",
    [
        (
            {},
            "Planted publisher",
            "metadata_unreadable",
            "portal metadata",
            "unreadable",
        ),
        (
            _portal_meta(""),
            "Planted publisher",
            "publisher_missing",
            "Planted publisher",
            "",
        ),
        (_portal_meta(""), "", "publisher_missing", "publisher", ""),
        (
            _portal_meta("Invented mismatch"),
            "Planted publisher",
            "publisher_mismatch",
            "Planted publisher",
            "Invented mismatch",
        ),
        (
            _portal_meta("Planted publisher", licence="invented licence"),
            "Planted publisher",
            "licence_mismatch",
            "text:CC BY url:https://creativecommons.org/licenses/by/4.0/",
            "text:invented licence url:https://creativecommons.org/licenses/by/4.0/",
        ),
    ],
)
def test_portal_metadata_failure(meta, publisher, check, expected, observed):
    result = kinds.prepare(portal(publisher=publisher), transport(meta, []), _sleep)
    refusal(result, META, check, expected, observed, publisher)


@pytest.mark.parametrize(
    "changes,rows,check,expected,observed",
    [
        ({"row_count_min": 2}, [{}], "row_count", "2..", "1"),
        (
            {"columns": (("SYN_VALUE", "integer"),)},
            [{}],
            "schema_missing",
            "SYN_VALUE",
            "missing",
        ),
        (
            {"period_field": "year", "period_last": "2022"},
            [{"year": "2021"}],
            "period_last",
            "2022",
            "2021",
        ),
        (
            {
                "source_id": "trade_ext",
                "period_field": "sit=row;form=published_label;field=year",
            },
            [{}],
            "period_label",
            "trade_ext",
            "year",
        ),
        (
            {"source_id": "trade_ext", "period_field": "year"},
            [{"year": "2021"}],
            "period_label",
            "trade_ext",
            "period_form",
        ),
        (
            {"source_id": "trade_ext"},
            [{"nationality": "invented"}],
            "public_split_undeclared",
            "declared Public split",
            "undeclared",
        ),
    ],
)
def test_portal_row_failure(changes, rows, check, expected, observed):
    result = kinds.prepare(
        portal(**changes), transport(_portal_meta("Planted publisher"), rows), _sleep
    )
    refusal(result, PORTAL, check, expected, observed)


@pytest.mark.parametrize("stage", [META, PORTAL])
def test_portal_transport_failure(stage):
    def read(url):
        if url == stage:
            raise TransportFault("blocked_host", stage)
        return _ok(url, json.dumps(_portal_meta("Planted publisher")).encode())

    refusal(
        kinds.prepare(portal(), read, _sleep),
        stage,
        "blocked_host",
        "allow-listed host",
        stage,
    )


def test_portal_success_record():
    result = kinds.prepare(
        portal(),
        transport(
            _portal_meta("Planted publisher", modified="2026-01-02"), [{"invented": 7}]
        ),
        _sleep,
    )
    assert result == kinds.Prepared(
        b'[{"invented": 7}]',
        PORTAL,
        "www.data.gov.qa",
        "Planted publisher",
        "2026-01-02",
        1,
        "",
        None,
        "CC BY",
        "https://creativecommons.org/licenses/by/4.0/",
    )


@pytest.mark.parametrize(
    "kind,code,check,expected,observed",
    [
        ("blocked_host", 1, "blocked_host", "allow-listed host", FILE_URL),
        ("unreachable", 6, "unreachable", "reachable host", "unreachable"),
        ("http", 1, "http_status", "http success", "http status"),
    ],
)
def test_bounded_transport_failure(kind, code, check, expected, observed):
    sleeps = []

    def read(url):
        raise TransportFault(kind, url)

    assert kinds.read_bounded(read, sleeps.append, FILE_URL) == (
        None,
        AttemptFailure(code, FILE_URL, check, expected, observed),
    )
    assert sleeps == ([] if kind == "blocked_host" else [1.0, 2.0, 4.0])


@pytest.mark.parametrize("redirect", [False, True])
def test_bounded_host_failure(redirect):
    blocked = "https://invented.invalid/refused"

    def read(url):
        assert redirect
        return _ok(url, b"invented", hops=(blocked,))

    assert kinds.read_bounded(read, _sleep, FILE_URL if redirect else blocked) == (
        None,
        AttemptFailure(1, blocked, "blocked_host", "allow-listed host", blocked),
    )


def test_hop_exception_message():
    error = kinds._HopRefused("https://invented.invalid/refused")
    message(error, "https://invented.invalid/refused")
    assert error.url == "https://invented.invalid/refused"
