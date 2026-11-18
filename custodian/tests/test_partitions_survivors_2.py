"""Partition-boundary and retry-provenance observations, without sockets."""

from pathlib import Path

from custodian.tests.test_partitions_survivors_1 import (
    PARTITION_URL,
    _reader,
    refuses_exact,
)
from custodian.tests.test_publicdata_behaviour import _ok

from eii_custodian.publicdata.fetch import registry
from eii_custodian.publicdata.fetch.partitions import (
    bounded_partition_reader,
    load_partition_spans,
)


def test_partition_loader_uses_the_review_path(monkeypatch):
    def read(path):
        assert path == (
            Path(__file__).resolve().parents[1]
            / "publicdata/review/s2_t29_sources.yaml"
        )
        return {"accident_spans": {2001: [1, 2]}}

    monkeypatch.setattr(registry, "read_yaml", read)
    assert load_partition_spans() == {2001: (1, 2)}


def test_reader_accepts_one_byte_lower_bound():
    assert _reader({2001: (1, 1)}, lambda u: _ok(u, b"x"))(PARTITION_URL).body == b"x"


def test_reader_refuses_reversed_span_before_transport():
    def transport(url):
        raise AssertionError("SYN transport must remain unused")

    refuses_exact(_reader({2001: (5, 2)}, transport), PARTITION_URL)


def test_reader_retry_passes_the_sleep_callback():
    attempts, delays = [], []

    def transport(url):
        attempts.append(url)
        if len(attempts) == 1:
            raise OSError("SYN retry")
        return _ok(url, b"x")

    result = bounded_partition_reader(transport, {2001: (1, 1)}, delays.append)(
        PARTITION_URL
    )
    assert result.body == b"x"
    assert attempts == [PARTITION_URL, PARTITION_URL]
    assert delays == [1.0]


def test_reader_reports_undersized_body():
    refuses_exact(
        _reader({2001: (2, 3)}, lambda u: _ok(u, b"x")),
        PARTITION_URL,
        message="metadata_bytes",
    )
