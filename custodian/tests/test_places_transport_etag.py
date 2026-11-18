"""The opener records the final response ETag and never a redirect hop's."""

from __future__ import annotations

import io
import urllib.request

import pytest

from eii_custodian.publicdata.fetch.transport import open_https

_URL = "https://download.openstreetmap.fr/syn-road"
_HOP = "https://stac.overturemaps.org/syn-hop"


class _Headers:
    def __init__(self, etag: str | None) -> None:
        self._etag = etag

    def get(self, name: str) -> str | None:
        if name == "ETag":
            return self._etag
        return None


class _Answer:
    def __init__(self, url: str, etag: str | None) -> None:
        self.headers = _Headers(etag)
        self._url = url

    def read(self, size: int = -1) -> bytes:
        # The opener reads at most the intake ceiling and one byte (S2-T08 part B,
        # mismatch class 8).
        del size
        return b"SYN"

    def geturl(self) -> str:
        return self._url

    def __enter__(self) -> _Answer:
        return self

    def __exit__(self, *_args: object) -> bool:
        return False


def test_final_etag_is_kept_quotes_included(monkeypatch: pytest.MonkeyPatch) -> None:
    """The final ETag is stored as sent, quotes included."""
    _patch(monkeypatch, '"syn-etag"', hop=False)
    response = open_https(_URL)
    assert response.etag == '"syn-etag"'
    assert response.body == b"SYN"
    assert response.hops == ()


def test_missing_etag_is_none(monkeypatch: pytest.MonkeyPatch) -> None:
    """No ETag header gives None."""
    _patch(monkeypatch, None, hop=False)
    assert open_https(_URL).etag is None


def test_a_redirect_hop_etag_is_not_taken(monkeypatch: pytest.MonkeyPatch) -> None:
    """The hop is recorded and the tag of the final response alone is kept."""
    _patch(monkeypatch, None, hop=True)
    response = open_https(_URL)
    assert response.hops == (_HOP,)
    assert response.etag is None


def _patch(monkeypatch: pytest.MonkeyPatch, etag: str | None, hop: bool) -> None:
    def build_opener(handler: type[urllib.request.HTTPRedirectHandler]) -> object:
        guard = handler()

        class _Opener:
            def open(self, request: urllib.request.Request, timeout: float) -> _Answer:
                del timeout
                if hop:
                    guard.redirect_request(
                        request,
                        io.BytesIO(b""),
                        302,
                        "Found",
                        _Headers('"hop-etag"'),
                        _HOP,
                    )
                return _Answer(_URL, etag)

        return _Opener()

    monkeypatch.setattr(urllib.request, "build_opener", build_opener)
