"""Fixed allocations for general HTTPS and the trade opener; invented streams."""

from __future__ import annotations

import hashlib
from types import SimpleNamespace

import pytest

from eii_custodian.publicdata.fetch import transport

URL = "https://www.data.gov.qa/invented"


class Body:
    def __init__(self, size: int, declared: int | None = None) -> None:
        self.left = size
        self.headers = {} if declared is None else {"Content-Length": str(declared)}
        self.reads: list[int] = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        pass

    def geturl(self):
        return URL

    def read(self, size=-1):
        assert 0 < size <= 65536, "unbounded_read"
        self.reads.append(size)
        count = min(self.left, size)
        self.left -= count
        return b"x" * count


def serve(monkeypatch, answer):
    monkeypatch.setattr(
        transport.urllib.request,
        "build_opener",
        lambda *_a: SimpleNamespace(open=lambda *_a, **_k: answer),
    )


@pytest.mark.parametrize("attempt", [False, True])
def test_every_read_uses_fixed_chunks(monkeypatch, attempt):
    answer = Body(2 * 65536 + 7)
    serve(monkeypatch, answer)
    result = (
        transport.open_attempt(transport.PreparedRequest(URL, "", "", "invented"))
        if attempt
        else transport.open_https(URL)
    )
    assert result.body == b"x" * (2 * 65536 + 7)
    assert len(answer.reads) == 4
    if not attempt:
        assert result.body_sha256 == hashlib.sha256(result.body).hexdigest()


def test_trade_opener_refuses_declared_oversize_before_read(monkeypatch):
    answer = Body(0, transport.INTAKE_CEILING_BYTES + 1)
    serve(monkeypatch, answer)
    with pytest.raises(transport.OpenerFault, match="body_bytes"):
        transport.open_attempt(
            transport.PreparedRequest(URL, "", "SYN-secret", "invented")
        )
    assert answer.reads == []


def test_trade_opener_refuses_undeclared_oversize(monkeypatch):
    monkeypatch.setattr(transport, "INTAKE_CEILING_BYTES", 12)
    answer = Body(13)
    serve(monkeypatch, answer)
    with pytest.raises(transport.OpenerFault, match="body_bytes"):
        transport.open_attempt(transport.PreparedRequest(URL, "", "", "invented"))
    assert answer.reads == [13]
