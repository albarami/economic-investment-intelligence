"""S2-T29 kill-pass tests for the live accident-partition adapter (partitions.py)."""

import pytest
from custodian.tests.test_publicdata_behaviour import _ok, _sleep

from eii_custodian.publicdata.fetch import registry
from eii_custodian.publicdata.fetch.partitions import (
    PartitionError,
    bounded_partition_reader,
    load_partition_spans,
)

PORTAL = "https://www.data.gov.qa/api/explore/v2.1/catalog/datasets/"
PARTITION_URL = PORTAL + "syn/exports/json?where=year%28accident_year%29%3D2001"
MESSAGE = "partition_byte_bound_unconfirmed"


def refuses_exact(call, *args, message=MESSAGE, **kwargs):
    with pytest.raises(PartitionError) as excinfo:
        call(*args, **kwargs)
    assert str(excinfo.value) == message


def yaml_spans(monkeypatch, document):
    monkeypatch.setattr(registry, "read_yaml", lambda _path: document)


# load_partition_spans


def test_partition_spans_load_the_reviewed_document(monkeypatch):
    yaml_spans(
        monkeypatch,
        {"accident_spans": {2001: [2, 5], 2002: [9, 9], 1000: [1, 3], 9999: [4, 4]}},
    )
    assert load_partition_spans() == {
        2001: (2, 5),
        2002: (9, 9),
        1000: (1, 3),
        9999: (4, 4),
    }


def test_partition_spans_refused_when_document_is_not_usable(monkeypatch):
    yaml_spans(monkeypatch, None)
    refuses_exact(load_partition_spans)
    yaml_spans(monkeypatch, {"accident_spans": "[LEAD: accepted byte spans]"})
    refuses_exact(load_partition_spans)
    yaml_spans(monkeypatch, {"accident_spans": {}})
    refuses_exact(load_partition_spans)
    yaml_spans(monkeypatch, {"other": "SYN"})
    refuses_exact(load_partition_spans)


@pytest.mark.parametrize(
    "year",
    ["2001", True, 999, 10000],
)
def test_partition_span_year_bounds(monkeypatch, year):
    yaml_spans(monkeypatch, {"accident_spans": {year: [1, 3]}})
    refuses_exact(load_partition_spans)


@pytest.mark.parametrize(
    "span",
    [(1, 3), "SYN", [1], [1, 2, 3], ["1", 3], [1, True], [1.0, 3], [0, 3], [5, 2]],
)
def test_partition_span_shapes(monkeypatch, span):
    yaml_spans(monkeypatch, {"accident_spans": {2001: span}})
    refuses_exact(load_partition_spans)


def test_partition_spans_message_from_missing_review_key(monkeypatch):
    yaml_spans(monkeypatch, {"SYN": []})
    refuses_exact(load_partition_spans)


# bounded_partition_reader


def _reader(spans, transport):
    return bounded_partition_reader(transport, spans, _sleep)


def test_reader_refuses_unconfirmed_year_with_exact_message():
    def transport(url):
        pytest.fail("no byte bound means no request")

    refuses_exact(_reader({}, transport), PARTITION_URL, message=MESSAGE)


def test_reader_refuses_malformed_where_clause():
    def transport(url):
        pytest.fail("unreviewed query shape means no request")

    refuses_exact(
        _reader({2001: (2, 5)}, transport),
        PORTAL + "syn/exports/json?where=SYN",
        message=MESSAGE,
    )


def test_reader_refuses_absent_where_clause():
    def transport(url):
        pytest.fail("absent where means no request")

    refuses_exact(
        _reader({2001: (2, 5)}, transport),
        PORTAL + "syn/exports/json",
        message=MESSAGE,
    )


def test_reader_refuses_doubled_where_clause():
    def transport(url):
        pytest.fail("doubled where means no request")

    refuses_exact(
        _reader({2001: (2, 5)}, transport),
        PORTAL + "syn/exports/json?where=year%28accident_year%29%3D2001&where=SYN",
        message=MESSAGE,
    )


def test_reader_refuses_malformed_span_with_exact_message():
    def transport(url):
        pytest.fail("malformed span means no request")

    for span in [(3,), (3, 3, 3), ("3", 3), (0, 3)]:
        refuses_exact(_reader({2001: span}, transport), PARTITION_URL, message=MESSAGE)


def test_reader_refuses_unapproved_host_with_exact_message():
    def transport(url):
        pytest.fail("unapproved host means no request")

    refuses_exact(
        _reader({2001: (2, 5)}, transport),
        "https://invented.invalid/syn/exports/json?where=year%28accident_year%29%3D2001",
        message="blocked_host",
    )


def test_reader_passes_non_export_urls_through_unchanged():
    requested = []

    def transport(url):
        requested.append(url)
        return _ok(url, b"SYN passthrough")

    url = PORTAL + "syn/records?select=count"
    assert _reader({2001: (2, 5)}, transport)(url).body == b"SYN passthrough"
    assert requested == [url]


def test_reader_returns_the_reviewed_partition_response():
    requested = []

    def transport(url):
        requested.append(url)
        return _ok(url, b"xxx")

    response = _reader({2001: (3, 3)}, transport)(PARTITION_URL)
    assert response.body == b"xxx"
    assert requested == [PARTITION_URL]
