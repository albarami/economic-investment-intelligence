"""Invented imagery inputs covering the lead's first mutation campaign."""

from __future__ import annotations

import codecs
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from custodian.tests.test_gis_imagery_views import _LIST, _write

from eii_custodian.publicdata.gis import imagery_views as subject

_SERVICE = "https://invented.example/InventedX///"


def _refusal(call: Callable[[], object], expected: str) -> None:
    with pytest.raises(subject.ImageryViewsError) as caught:
        call()
    assert str(caught.value) == expected
    assert caught.value.reason == expected


def test_missing_list_search(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(subject, "__file__", str(tmp_path / "invented.py"))
    monkeypatch.setattr(subject, "_FILE", Path("invented_missing_views.yaml"))
    monkeypatch.setattr(Path, "is_file", lambda _path: False)
    _refusal(subject.views_path, "views_file")


def test_missing_list_read(tmp_path: Path) -> None:
    _refusal(lambda: subject.load_views(tmp_path / "absent.yaml"), "views_file")


def test_read_uses_utf8(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    path = _write(tmp_path, _LIST)
    original = Path.read_text

    def read_text(self: Path, *args: Any, **kwargs: Any) -> str:
        assert codecs.lookup(kwargs["encoding"]).name == "utf-8"
        return original(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", read_text)
    assert subject.load_views(path).version == 1


@pytest.mark.parametrize(
    ("old", "new", "expected"),
    [
        ("views:\n", "views: null\nignored:\n", "unknown_key:ignored"),
        (_LIST, "version: 1\nimage_sr: 3857\nviews: null\n", "views"),
        ("version: 1", "3: invented\nversion: 1", "unknown_key:type"),
        ("[10, 20, 30, 40]", "[10, 20, 30, 20]", "bbox"),
        ("[10, 20, 30, 40]", "[.inf, 20, 30, 40]", "bbox"),
        ("[10, 20, 30, 40]", "[-.inf, 20, 30, 40]", "bbox"),
        ("[10, 20, 30, 40]", "[.nan, 20, 30, 40]", "bbox"),
        ("[64, 32]", "[64, 0]", "size"),
    ],
)
def test_list_refusals(tmp_path: Path, old: str, new: str, expected: str) -> None:
    path = _write(tmp_path, _LIST.replace(old, new))
    _refusal(lambda: subject.load_views(path), expected)


@pytest.mark.parametrize(
    ("box", "expected"),
    [
        ("[0.0, -0.0, 10.0, 20.5]", "0,0,10,20.5"),
        ("[-0.0000001, 0.0000001, 0.125, 20.5]", "0,0,0.125,20.5"),
        ("[1.2345678, 2.0, 3.0, 4.0]", "1.234568,2,3,4"),
    ],
)
def test_float_export_and_url(tmp_path: Path, box: str, expected: str) -> None:
    text = _LIST.replace("[10, 20, 30, 40]", box).replace("[64, 32]", "[1, 1]")
    views = subject.load_views(_write(tmp_path, text))
    request = subject.export_request(
        views, "view_invented_a", "before", _SERVICE, "invented.example"
    )
    assert dict(request.parameters)["bbox"] == expected
    assert dict(request.parameters)["size"] == "1,1"
    assert request.url.startswith("https://invented.example/InventedX/export?")


@pytest.mark.parametrize(
    ("address", "host", "expected"),
    [
        (
            "https://invented@invented-host/MapServer",
            "invented-host",
            "service_address",
        ),
        ("https:///Invented", "", "service_host"),
    ],
)
def test_service_refusals(
    tmp_path: Path, address: str, host: str, expected: str
) -> None:
    views = subject.load_views(_write(tmp_path, _LIST))
    _refusal(
        lambda: subject.export_request(
            views, "view_invented_a", "before", address, host
        ),
        expected,
    )


@pytest.mark.parametrize(
    ("value", "expected"), [(float("inf"), "inf"), (float("nan"), "nan")]
)
def test_number_text_nonfinite_direct(value: float, expected: str) -> None:
    # _number refuses nonfinite values before export; this helper accepts float.
    assert subject._number_text(value) == expected
