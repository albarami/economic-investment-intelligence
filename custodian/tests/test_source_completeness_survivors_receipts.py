"""Invented in-process receipt edge cases; no cache access or live inputs."""

import pytest
from custodian.tests.test_source_completeness import entry, inputs, receipt

from eii_custodian.publicdata import completeness as c


@pytest.mark.parametrize("digest", ["a" * 64, "", "CITATION_ONLY", None])
def test_citation_digest_is_exact_marker(digest):
    row = entry(kind="citation_only", release_tables=())
    evidence = receipt(row)
    evidence["sha256"] = digest
    assert c.receipt_valid(row, evidence) is (digest == "CITATION_ONLY")


@pytest.mark.parametrize(
    "field,value",
    [
        ("source_modified", "Invented last modified"),
        ("row_count", 4),
        ("portal_licence", "Invented portal licence"),
        ("portal_licence_url", "https://example.org/invented-licence"),
        ("fetch_url", "https://example.org/invented-redirect"),
        ("fetch_host", "invented.example.org"),
    ],
)
def test_receipt_variable_fields_are_not_registry_constants(field, value):
    row = entry()
    evidence = receipt(row)
    evidence[field] = value
    assert c.receipt_valid(row, evidence) is True


@pytest.mark.parametrize("value", ["", " ", 3, False, None])
def test_receipt_fetch_url_requires_nonblank_text(value):
    row = entry()
    evidence = receipt(row)
    evidence["fetch_url"] = value
    assert c.receipt_valid(row, evidence) is False


@pytest.mark.parametrize(
    "stamp,valid",
    [
        (None, False),
        (17, False),
        ("invented invalid date", False),
        ("2026-11-17T00:00:00", False),
        ("2026-11-17T00:00:00Z", True),
        ("2026-11-17T00:00:00+03:00", True),
        ("2026-11-17Z00:00:00+00:00", False),
    ],
)
def test_receipt_timestamp_shape_and_timezone(stamp, valid):
    row = entry()
    evidence = receipt(row)
    evidence["retrieved_utc"] = stamp
    assert c.receipt_valid(row, evidence) is valid


@pytest.mark.parametrize(
    "nbytes,valid_count",
    [
        (-1, False),
        (0, True),
        (1, True),
        (False, False),
        (True, False),
        (0.0, False),
        (None, False),
        ("0", False),
    ],
)
@pytest.mark.parametrize("switched_off", [False, True, None])
def test_receipt_byte_count_and_explicit_off_flag(nbytes, valid_count, switched_off):
    row = entry()
    evidence = receipt(row)
    evidence.update(bytes=nbytes, switched_off=switched_off)
    expected = valid_count if switched_off is False else False
    assert c.receipt_valid(row, evidence) is expected


def test_empty_check_and_independent_inventory_are_in_process():
    counts = {"invented_family": 77}
    returned, sources = c.independent_inventory(
        counts, {"invented_decision"}, {"invented_citation"}
    )
    assert returned is counts
    assert {"invented_decision", "invented_citation"} <= sources
    args = inputs()
    args.update(
        entries=[], pack=c.Pack({}, frozenset()), inventory={}, receipts={}, outputs={}
    )
    assert c.check(**args) == [
        {"id": "biz_register", "state": "not yet read", "reason": ""},
        {"id": "fc_register", "state": "not yet read", "reason": ""},
    ]
    assert c.committed_derived_check({}, []) == []
