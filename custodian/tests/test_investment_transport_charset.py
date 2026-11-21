"""``open_https`` must surface ``Content-Type`` charset for receipt lineage."""

from __future__ import annotations

import io
import urllib.request

import pytest

from eii_custodian.publicdata.fetch.transport import open_https
from eii_custodian.publicdata.investment_build import header_charset

_URL = "https://services.gisqatar.org.qa/server/rest/services/Vector/QARS/MapServer?f=pjson"


class _Headers:
    def __init__(self, content_type: str | None) -> None:
        self._content_type = content_type

    def get(self, name: str) -> str | None:
        if name == "Content-Type":
            return self._content_type
        return None

    def __getitem__(self, name: str) -> str:
        value = self.get(name)
        if value is None:
            raise KeyError(name)
        return value


class _Answer:
    def __init__(self, url: str, content_type: str) -> None:
        self.headers = _Headers(content_type)
        self._url = url
        self._body = io.BytesIO(b"<html>SYN</html>")

    def read(self, size: int = -1) -> bytes:
        return self._body.read(size)

    def geturl(self) -> str:
        return self._url

    def __enter__(self) -> _Answer:
        return self

    def __exit__(self, *_args: object) -> bool:
        return False


def test_open_https_passes_content_type_charset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def build_opener(*_handlers: object) -> object:
        class _Opener:
            def open(self, request: urllib.request.Request, timeout: float) -> _Answer:
                del request, timeout
                return _Answer(_URL, "text/html; charset=windows-1256")

        return _Opener()

    monkeypatch.setattr(urllib.request, "build_opener", build_opener)
    response = open_https(_URL)
    assert header_charset(response.headers) == "windows-1256"
