"""Imagery history: a committed view list and one closed export request.

Invented views live in the test's temporary folder. The committed list is empty.
Expected parameters are literals, written out beside the builder's result.
"""

from __future__ import annotations

import inspect
import re
from dataclasses import replace
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

import pytest
from custodian.tests.support.fetch_build import run_build

from eii_custodian.publicdata.fetch.registry import load_registry
from eii_custodian.publicdata.fetch.transport import Response
from eii_custodian.publicdata.gis.imagery_views import (
    ExportRequest,
    ImageryViewsError,
    export_request,
    load_views,
    views_path,
)

_HOST = "services.gisqatar.org.qa"
_SERVICE = "https://services.gisqatar.org.qa/server/rest/services/Invented/MapServer"
_LIST = """\
version: 1
image_sr: 3857
views:
  - key: view_invented_a
    bbox_3857: [10, 20, 30, 40]
    size: [64, 32]
    format: png
    before:
      year: 1001
      layer: 0
    after:
      year: 1002
      layer: 1
"""
_BEFORE = (
    ("f", "image"),
    ("bbox", "10,20,30,40"),
    ("bboxSR", "3857"),
    ("imageSR", "3857"),
    ("size", "64,32"),
    ("format", "png"),
    ("layers", "show:0"),
)
_AFTER = (
    ("f", "image"),
    ("bbox", "10,20,30,40"),
    ("bboxSR", "3857"),
    ("imageSR", "3857"),
    ("size", "64,32"),
    ("format", "png"),
    ("layers", "show:1"),
)
_CLOSED = ("f", "bbox", "bboxSR", "imageSR", "size", "format", "layers")


def test_committed_list_loads_and_is_empty() -> None:
    """The reviewed file is empty: no service path was confirmed."""
    text = views_path().read_text(encoding="utf-8")
    assert "no service path was confirmed on 2026-11-15" in text
    assert "lead" in text.casefold()
    assert "owner" in text.casefold()
    loaded = load_views()
    assert loaded.version == 1
    assert loaded.image_sr == 3857
    assert loaded.views == ()


def test_invented_list_exports_before_and_after(tmp_path: Path) -> None:
    """Before and after each match a hand-written parameter list."""
    before = _export(tmp_path, _LIST, "view_invented_a", "before")
    after = _export(tmp_path, _LIST, "view_invented_a", "after")
    assert before.parameters == _BEFORE
    assert after.parameters == _AFTER
    _assert_parameters(before, _BEFORE)
    _assert_parameters(after, _AFTER)
    assert urlsplit(before.url).path.endswith("/export")
    assert urlsplit(before.url).hostname == _HOST


def test_jpg_view_exports_the_closed_request(tmp_path: Path) -> None:
    """jpg is the other allowed format, still with only the closed parameters."""
    text = """\
version: 1
image_sr: 3857
views:
  - key: view_invented_b
    bbox_3857: [1, 2, 3, 4]
    size: [16, 16]
    format: jpg
    before:
      year: 1003
      layer: 4
    after:
      year: 1004
      layer: 5
"""
    expected = (
        ("f", "image"),
        ("bbox", "1,2,3,4"),
        ("bboxSR", "3857"),
        ("imageSR", "3857"),
        ("size", "16,16"),
        ("format", "jpg"),
        ("layers", "show:4"),
    )
    request = _export(tmp_path, text, "view_invented_b", "before")
    assert request.parameters == expected
    _assert_parameters(request, expected)


def test_export_for_a_key_off_the_list_is_refused(tmp_path: Path) -> None:
    """The criterion's plant: a view that is not on the list builds nothing."""
    views = load_views(_write(tmp_path, _LIST))
    with pytest.raises(ImageryViewsError, match=r"^view_absent$") as caught:
        export_request(views, "view_not_on_the_list", "before", _SERVICE, _HOST)
    assert caught.value.reason == "view_absent"


def test_empty_committed_list_builds_no_request() -> None:
    """An empty list has no view to export."""
    with pytest.raises(ImageryViewsError, match=r"^view_absent$") as caught:
        export_request(load_views(), "view_invented_a", "before", _SERVICE, _HOST)
    assert caught.value.reason == "view_absent"


def test_image_sr_4326_is_refused(tmp_path: Path) -> None:
    """Web Mercator is the only image spatial reference."""
    text = _swap(_LIST, "image_sr: 3857\n", "image_sr: 4326\n")
    with pytest.raises(ImageryViewsError, match=r"^image_sr$") as caught:
        load_views(_write(tmp_path, text))
    assert caught.value.reason == "image_sr"
    refused = replace(load_views(_write(tmp_path, _LIST)), image_sr=4326)
    with pytest.raises(ImageryViewsError, match=r"^image_sr$"):
        export_request(refused, "view_invented_a", "before", _SERVICE, _HOST)


def test_unknown_field_on_a_view_is_refused(tmp_path: Path) -> None:
    """A view key other than the closed set is named in the refusal."""
    text = _swap(_LIST, "format: png\n", "format: png\n    note: planted\n")
    _refuses(tmp_path, text, "unknown_key:note")


def test_unknown_key_in_the_file_is_refused(tmp_path: Path) -> None:
    """A file key other than version, image_sr and views is named."""
    _refuses(tmp_path, _LIST + "note: planted\n", "unknown_key:note")


def test_unknown_key_on_a_side_is_refused(tmp_path: Path) -> None:
    """before and after hold year and layer only."""
    text = _swap(_LIST, "layer: 0\n", "layer: 0\n      note: planted\n")
    _refuses(tmp_path, text, "unknown_key:note")


def test_reversed_box_is_refused(tmp_path: Path) -> None:
    """xmin must be under xmax and ymin under ymax."""
    boxes = (
        "[30, 20, 10, 40]",
        "[10, 40, 30, 20]",
        "[10, 20, 10, 40]",
        "[10, 20, 30]",
        "[true, 20, 30, 40]",
    )
    for box in boxes:
        text = _swap(_LIST, "bbox_3857: [10, 20, 30, 40]", f"bbox_3857: {box}")
        _refuses(tmp_path, text, "bbox")


def test_size_over_the_bound_is_refused(tmp_path: Path) -> None:
    """Each edge is positive and at most the named bound, which is 4096."""
    for size in ("[4097, 32]", "[64, 4097]"):
        text = _swap(_LIST, "size: [64, 32]", f"size: {size}")
        _refuses(tmp_path, text, "size")
    accepted = _swap(_LIST, "size: [64, 32]", "size: [4096, 4096]")
    loaded = load_views(_write(tmp_path, accepted))
    assert loaded.views[0].width == 4096
    assert loaded.views[0].height == 4096


def test_size_that_is_not_positive_is_refused(tmp_path: Path) -> None:
    """Zero, a negative edge and a short pair are refused."""
    for size in ("[0, 32]", "[64, -1]", "[64]", "[true, 32]"):
        text = _swap(_LIST, "size: [64, 32]", f"size: {size}")
        _refuses(tmp_path, text, "size")


def test_format_outside_the_pair_is_refused(tmp_path: Path) -> None:
    """Only png and jpg are export formats."""
    for name in ("gif", "PNG", "jpeg"):
        text = _swap(_LIST, "format: png", f"format: {name}")
        _refuses(tmp_path, text, "format")


def test_before_year_not_under_after_year_is_refused(tmp_path: Path) -> None:
    """before.year must be an integer under after.year."""
    reversed_years = _swap(_LIST, "year: 1001", "year: 1009")
    _refuses(tmp_path, reversed_years, "year_order")
    equal_years = _swap(_LIST, "year: 1002", "year: 1001")
    _refuses(tmp_path, equal_years, "year_order")
    fractional = _swap(_LIST, "year: 1001", "year: 1001.5")
    _refuses(tmp_path, fractional, "year")
    boolean = _swap(_LIST, "year: 1001", "year: true")
    _refuses(tmp_path, boolean, "year")


def test_duplicate_key_is_refused(tmp_path: Path) -> None:
    """A key may occur once."""
    text = (
        _LIST
        + """\
  - key: view_invented_a
    bbox_3857: [11, 21, 31, 41]
    size: [16, 16]
    format: jpg
    before:
      year: 1003
      layer: 3
    after:
      year: 1004
      layer: 4
"""
    )
    _refuses(tmp_path, text, "duplicate_key")


def test_service_address_on_another_host_is_refused(tmp_path: Path) -> None:
    """The service host must be the row's fetch host."""
    views = load_views(_write(tmp_path, _LIST))
    other = "https://invented.example/server/rest/services/Invented/MapServer"
    with pytest.raises(ImageryViewsError, match=r"^service_host$") as caught:
        export_request(views, "view_invented_a", "before", other, _HOST)
    assert caught.value.reason == "service_host"


def test_empty_service_address_is_refused(tmp_path: Path) -> None:
    """An empty service address builds nothing."""
    views = load_views(_write(tmp_path, _LIST))
    for address in ("", "   "):
        with pytest.raises(ImageryViewsError, match=r"^service_empty$") as caught:
            export_request(views, "view_invented_a", "before", address, _HOST)
        assert caught.value.reason == "service_empty"


def test_service_address_carrying_a_token_or_user_is_refused(tmp_path: Path) -> None:
    """A query or userinfo on the service address is not part of the request."""
    views = load_views(_write(tmp_path, _LIST))
    userinfo = "https://planted:planted" + "@" + _HOST + "/Invented/MapServer"
    planted = (_SERVICE + "?token=planted", userinfo)
    for address in planted:
        with pytest.raises(ImageryViewsError, match=r"^service_address$") as caught:
            export_request(views, "view_invented_a", "before", address, _HOST)
        assert caught.value.reason == "service_address"


def test_service_address_that_is_not_https_is_refused(tmp_path: Path) -> None:
    """The export address is https, as every other fetch on this host is."""
    views = load_views(_write(tmp_path, _LIST))
    insecure = _SERVICE.replace("https://", "http://", 1)
    with pytest.raises(ImageryViewsError, match=r"^service_scheme$") as caught:
        export_request(views, "view_invented_a", "before", insecure, _HOST)
    assert caught.value.reason == "service_scheme"


def test_side_other_than_before_or_after_is_refused(tmp_path: Path) -> None:
    """The only sides are before and after."""
    views = load_views(_write(tmp_path, _LIST))
    with pytest.raises(ImageryViewsError, match=r"^side$") as caught:
        export_request(views, "view_invented_a", "middle", _SERVICE, _HOST)
    assert caught.value.reason == "side"


def test_export_request_has_no_parameter_outside_the_closed_set(
    tmp_path: Path,
) -> None:
    """An extra parameter added in the builder fails this comparison."""
    request = _export(tmp_path, _LIST, "view_invented_a", "before")
    assert tuple(name for name, _value in request.parameters) == _CLOSED
    queried = parse_qsl(urlsplit(request.url).query, keep_blank_values=True)
    assert tuple(name for name, _value in queried) == _CLOSED
    assert request.parameters == _BEFORE


def test_absent_imagery_row_makes_no_request(tmp_path: Path) -> None:
    """The absent row is skipped where every other absent row is skipped."""
    entry = next(item for item in load_registry() if item.key == "gis_imagery_history")
    calls: list[str] = []

    def transport(url: str) -> Response:
        calls.append(url)
        raise AssertionError(url)

    outcome = run_build((entry,), transport, tmp_path, _clock, _sleep)
    assert calls == []
    assert (
        entry.url
        == "https://services.gisqatar.org.qa/server/rest/services/Imagery/QatarOrtho_1995/MapServer"
    )
    assert entry.skip_reason == "schema_unconfirmed"
    assert f"SKIP {entry.key} {entry.skip_reason}" in outcome.lines
    assert outcome.failure is None
    stored = [
        path.name
        for path in tmp_path.rglob("*")
        if path.is_file() and path.name != "build-log.json"
    ]
    assert stored == []


def test_view_count_over_the_bound_is_refused(tmp_path: Path) -> None:
    """The list's own cap is 8 views."""
    assert len(load_views(_write(tmp_path, _many(8))).views) == 8
    _refuses(tmp_path, _many(9), "view_bound")


def test_view_key_outside_the_pattern_is_refused(tmp_path: Path) -> None:
    """A key is lower case, digits and underscore."""
    text = _swap(_LIST, "key: view_invented_a", "key: ViewInvented")
    _refuses(tmp_path, text, "view_key")


def test_negative_layer_is_refused(tmp_path: Path) -> None:
    """A layer id is a non-negative integer. Zero remains allowed."""
    text = _swap(_LIST, "layer: 0\n", "layer: -1\n")
    _refuses(tmp_path, text, "layer")
    boolean = _swap(_LIST, "layer: 0\n", "layer: true\n")
    _refuses(tmp_path, boolean, "layer")


def test_missing_view_field_is_refused(tmp_path: Path) -> None:
    """A view without format is refused by the missing name."""
    text = _swap(_LIST, "    format: png\n", "")
    _refuses(tmp_path, text, "missing_key:format")


def test_version_other_than_one_is_refused(tmp_path: Path) -> None:
    """The file version is 1."""
    text = _swap(_LIST, "version: 1\n", "version: 2\n")
    _refuses(tmp_path, text, "version")
    boolean = _swap(_LIST, "version: 1\n", "version: true\n")
    _refuses(tmp_path, boolean, "version")


def test_unreadable_view_list_is_refused(tmp_path: Path) -> None:
    """A file that is not YAML is refused before a view is read."""
    _refuses(tmp_path, "views: [\n", "views_file")


def test_view_list_root_must_be_a_mapping(tmp_path: Path) -> None:
    """The file root is a mapping."""
    _refuses(tmp_path, "- planted\n", "views_root")


def test_view_that_is_not_a_mapping_is_refused(tmp_path: Path) -> None:
    """Each view is a mapping."""
    text = "version: 1\nimage_sr: 3857\nviews:\n  - planted\n"
    _refuses(tmp_path, text, "view")


def test_side_that_is_not_a_mapping_is_refused(tmp_path: Path) -> None:
    """before and after are mappings of year and layer."""
    text = _swap(
        _LIST, "before:\n      year: 1001\n      layer: 0\n", "before: planted\n"
    )
    _refuses(tmp_path, text, "side_fields")


def test_builder_takes_no_box_size_year_or_layer() -> None:
    """The caller cannot pass a box, a size, a year or a layer."""
    names = tuple(inspect.signature(export_request).parameters)
    assert names == ("views", "key", "side", "service_address", "fetch_host")


def _export(tmp_path: Path, text: str, key: str, side: str) -> ExportRequest:
    return export_request(
        load_views(_write(tmp_path, text)), key, side, _SERVICE, _HOST
    )


def _assert_parameters(
    request: ExportRequest, expected: tuple[tuple[str, str], ...]
) -> None:
    queried = parse_qsl(urlsplit(request.url).query, keep_blank_values=True)
    assert tuple(queried) == expected
    for got, wanted in zip(request.parameters, expected, strict=True):
        assert got == wanted


def _refuses(tmp_path: Path, text: str, reason: str) -> None:
    with pytest.raises(ImageryViewsError, match=rf"^{re.escape(reason)}$") as caught:
        load_views(_write(tmp_path, text))
    assert caught.value.reason == reason


def _write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "gis_imagery_views.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def _swap(text: str, old: str, new: str) -> str:
    if old not in text:
        raise AssertionError(old)
    return text.replace(old, new, 1)


def _many(count: int) -> str:
    block = """\
  - key: view_invented_{index}
    bbox_3857: [10, 20, 30, 40]
    size: [64, 32]
    format: png
    before:
      year: 1001
      layer: 0
    after:
      year: 1002
      layer: 1
"""
    body = "".join(block.format(index=index) for index in range(count))
    return f"version: 1\nimage_sr: 3857\nviews:\n{body}"


def _clock() -> str:
    return "2026-11-15T00:00:00Z"


def _sleep(_seconds: float) -> None:
    return None
