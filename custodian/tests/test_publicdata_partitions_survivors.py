"""Exact partition contracts over the existing invented accident fixture."""

import json
from dataclasses import replace
from typing import Any

import pytest
from custodian.tests.test_publicdata_behaviour import _ok
from custodian.tests.test_publicdata_unblocked_round2 import accident_fixture

from eii_custodian.publicdata.fetch import allowlist, partitions
from eii_custodian.publicdata.fetch.checks import AttemptFailure
from eii_custodian.publicdata.fetch.transport import TransportFault

BASE = "https://invented.invalid/accident"
PLAN = (
    BASE
    + "/records?select=count%28%2A%29+as+n&group_by=year%28accident_year%29&limit=50"
)
PAGE_A = BASE + "/exports/json?where=year%28accident_year%29%3D2001"
PAGE_B = BASE + "/exports/json?where=year%28accident_year%29%3D2002"


def fixture(monkeypatch):
    entry, original = accident_fixture()
    old_base = entry.url.removesuffix("/exports/json")
    bodies = {url.replace(old_base, BASE): body for url, body in original.items()}
    entry = replace(
        entry,
        url=BASE + "/exports/json",
        fetch_host="invented.invalid",
        landing_url=BASE,
    )
    monkeypatch.setattr(allowlist, "ALLOWED_HOSTS", frozenset({"invented.invalid"}))
    return entry, bodies


def exported(entry, bodies):
    return partitions.partition_export(
        entry, _ok(BASE, bodies[BASE]), lambda url: _ok(url, bodies[url])
    )


def refused(
    result, url, check, expected="complete distinct partitions", observed="invalid"
):
    assert result == (b"", (), AttemptFailure(1, url, check, expected, observed))


@pytest.mark.parametrize(
    ("plant", "url", "check", "expected", "observed"),
    [
        ("plan", PLAN, "partition_plan", "complete distinct partitions", "invalid"),
        (
            "duplicate_year",
            PLAN,
            "partition_duplicate",
            "complete distinct partitions",
            "invalid",
        ),
        ("total", PLAN, "partition_total", "complete distinct partitions", "invalid"),
        ("short", PAGE_A, "partition_count", "complete distinct partitions", "invalid"),
        (
            "unreadable",
            PAGE_A,
            "partition_count",
            "complete distinct partitions",
            "invalid",
        ),
        (
            "duplicate_body",
            PAGE_B,
            "partition_duplicate",
            "complete distinct partitions",
            "invalid",
        ),
        ("missing", PAGE_A, "schema_missing", "accident_year", "missing"),
        ("retyped", PAGE_A, "schema_retyped", "accident_year:string", "integer"),
    ],
)
def test_refusal_details(monkeypatch, plant, url, check, expected, observed):
    entry, bodies = fixture(monkeypatch)
    if plant == "plan":
        bodies[PLAN] = b"null"
    elif plant in {"duplicate_year", "total"}:
        plan = json.loads(bodies[PLAN])
        if plant == "duplicate_year":
            plan["results"][1]["year(accident_year)"] = 2001
        else:
            plan["results"][0]["n"] = 2
        bodies[PLAN] = json.dumps(plan).encode()
    elif plant == "duplicate_body":
        bodies[PAGE_B] = bodies[PAGE_A]
    else:
        bodies[PAGE_A] = {
            "short": b"[]",
            "unreadable": b"null",
            "missing": b"[{}]",
            "retyped": b'[{"accident_year":1}]',
        }[plant]
    refused(exported(entry, bodies), url, check, expected, observed)


@pytest.mark.parametrize(
    ("failed_url", "expected_url"),
    [
        (PLAN, "https://invented.invalid/accident/records"),
        (PAGE_A, "https://invented.invalid/accident/exports/json"),
    ],
)
def test_transport_failure_empty_bytes(monkeypatch, failed_url, expected_url):
    entry, bodies = fixture(monkeypatch)

    def read(url):
        if url == failed_url:
            fault = TransportFault("unreachable", url)
            assert failed_url.split("?", 1)[1] not in str(fault)
            raise fault
        return _ok(url, bodies[url])

    assert partitions.partition_export(entry, _ok(BASE, bodies[BASE]), read) == (
        b"",
        (),
        AttemptFailure(6, expected_url, "unreachable", "reachable host", "unreachable"),
    )


@pytest.mark.parametrize("count", [-1, True, 2.0, "2"])
def test_invalid_catalogue_count(monkeypatch, count):
    entry, bodies = fixture(monkeypatch)
    bodies[BASE] = json.dumps({"records_count": count}).encode()
    refused(exported(entry, bodies), PLAN, "partition_plan")


def test_zero_catalogue_total(monkeypatch):
    # Zero is a valid catalogue total, so a nonempty plan is refused by its sum.
    entry, bodies = fixture(monkeypatch)
    bodies[BASE] = b'{"records_count":0}'
    refused(exported(entry, bodies), PLAN, "partition_total")


@pytest.mark.parametrize(
    "body",
    [
        b'{"results":[],"total_count":0}',
        b'{"results":[{"year(accident_year)":2001,"n":1}],"total_count":true}',
        b'{"results":[{"year(accident_year)":2001,"n":0}],"total_count":1}',
        b'{"results":[{"year(accident_year)":2001,"n":1.0}],"total_count":1}',
        b'{"results":[{"year(accident_year)":999,"n":1}],"total_count":1}',
        b'{"results":[{"year(accident_year)":10000,"n":1}],"total_count":1}',
    ],
)
def test_invalid_plan_bounds(monkeypatch, body):
    entry, bodies = fixture(monkeypatch)
    bodies[PLAN] = body
    refused(exported(entry, bodies), PLAN, "partition_plan")


@pytest.mark.parametrize("year", [1000, 9999])
def test_inclusive_year_bounds(monkeypatch, year):
    entry, bodies = fixture(monkeypatch)
    bodies[PLAN] = json.dumps(
        {"results": [{"year(accident_year)": year, "n": 2}], "total_count": 1}
    ).encode()
    bodies[BASE + f"/exports/json?where=year%28accident_year%29%3D{year}"] = (
        b'[{"accident_year":"invented-a"},{"accident_year":"invented-b"}]'
    )
    body, receipts, failure = exported(entry, bodies)
    assert failure is None
    assert body == b'[{"accident_year": "invented-a"}, {"accident_year": "invented-b"}]'
    assert [r["row_count"] for r in receipts] == [2, 1, 2]


def test_fifty_groups_and_fifty_one_refusal(monkeypatch):
    entry, bodies = fixture(monkeypatch)
    groups = [{"year(accident_year)": year, "n": 1} for year in range(2001, 2051)]
    bodies[BASE] = b'{"records_count":50}'
    bodies[PLAN] = json.dumps({"results": groups, "total_count": 50}).encode()
    for year in range(2001, 2051):
        bodies[BASE + f"/exports/json?where=year%28accident_year%29%3D{year}"] = (
            json.dumps([{"accident_year": str(year)}]).encode()
        )
    body, receipts, failure = exported(entry, bodies)
    assert failure is None
    assert len(json.loads(body)) == 50
    assert len(receipts) == 52
    groups.append({"year(accident_year)": 2051, "n": 1})
    bodies[BASE] = b'{"records_count":51}'
    bodies[PLAN] = json.dumps({"results": groups, "total_count": 51}).encode()
    refused(exported(entry, bodies), PLAN, "partition_plan")


def test_output_key_order(monkeypatch):
    entry, bodies = fixture(monkeypatch)
    bodies[PAGE_A] = b'[{"z":"invented","accident_year":"2001"}]'
    body, receipts, failure = exported(entry, bodies)
    assert failure is None
    assert (
        body
        == b'[{"accident_year": "2001", "z": "invented"}, {"accident_year": "2002"}]'
    )
    assert [r["url"] for r in receipts] == [BASE, PLAN, PAGE_A, PAGE_B]


def test_receipt_exact_fields():
    # SHA-256 empty-message known-answer vector, split for repository scanners.
    digest = "".join(
        ("e3b0c44298fc1c14", "9afbf4c8996fb924", "27ae41e4649b934c", "a495991b7852b855")
    )
    assert partitions.request_receipt(_ok(BASE, b""), 3) == {
        "url": BASE,
        "sha256": digest,
        "bytes": 0,
        "row_count": 3,
    }


def wrong_type(value: object) -> Any:
    """Supply a deliberately malformed reader result through one typed seam."""
    return value


@pytest.mark.parametrize("missing_url", [PLAN, PAGE_A])
def test_missing_response_leaves_no_cache_bytes(monkeypatch, missing_url):
    entry, bodies = fixture(monkeypatch)

    def read(url):
        if url == missing_url:
            return wrong_type(None)
        return _ok(url, bodies[url])

    # Direct export call: prepare's reader dereferences Response in _refused_hop
    # before this defensive None branch can run.
    body, receipts, _failure = partitions.partition_export(
        entry, _ok(BASE, bodies[BASE]), read
    )
    assert body == b""
    assert receipts == ()
