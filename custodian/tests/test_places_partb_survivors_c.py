"""Kill the surviving mutants of the stage before the gazetteer.

The stage takes the frame inputs from the registry and the cache, hands them to
the places stage, and writes one closed line of the log for every refusal, its
reason taken from the refusal itself.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import locale
from collections.abc import Iterator
from dataclasses import replace
from datetime import date
from pathlib import Path
from typing import NoReturn

import pytest
from custodian.tests.fixtures.places.invented import receipt_for
from custodian.tests.test_frame_census import entry
from custodian.tests.test_places_area_files import _install_road
from custodian.tests.test_places_partb_survivors_b import _review
from shapely import bounds, box

from eii_custodian.publicdata.fetch.registry import Entry
from eii_custodian.publicdata.places import PlacesError
from eii_custodian.publicdata.places.integrate import (
    StageConfig,
    areas_before_stage,
    run_places_before_gazetteer,
)

_PUBLISHER = "SYN Publisher"
_RETRIEVED = "2026-11-14T00:00:00Z"
_BOUNDARY = box(51.0, 25.0, 51.1, 25.1)
_NO_PLACE = "stage places places_file_unreceipted"
_NO_BOUNDARY = "stage places frame_boundary_missing"
_PLANTED = "stage places planted_refusal"
_STAGE = "eii_custodian.publicdata.places.integrate.run_places_stage"


@contextlib.contextmanager
def _ascii_locale() -> Iterator[None]:
    """The C locale, where a read without an encoding name fails on our bytes."""
    previous = locale.setlocale(locale.LC_CTYPE)
    locale.setlocale(locale.LC_CTYPE, "C")
    try:
        assert locale.getencoding() == "ANSI_X3.4-1968"
        yield
    finally:
        locale.setlocale(locale.LC_CTYPE, previous)


def _row(key: str, source_id: str, *, skip: str = "") -> Entry:
    """A registry row of one places source, invented and active."""
    return replace(
        entry(source_id),
        key=key,
        slug=key.split("/", 1)[1],
        skip_reason=skip,
        extension="parquet",
    )


def _receipt(path: Path, **field: object) -> None:
    """Write the receipt of one file, its digest the digest of its own bytes."""
    payload: dict[str, object] = {
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "retrieved_utc": _RETRIEVED,
        "publisher": _PUBLISHER,
    }
    payload.update(field)
    path.parent.mkdir(parents=True, exist_ok=True)
    (path.parent / f"{path.stem}.meta.json").write_text(
        json.dumps(payload, ensure_ascii=False), encoding="utf-8"
    )


def _receipted(cache: Path, key: str, body: bytes) -> Path:
    """Write one receipted file under a registry key and return its path."""
    folder = cache / key
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "syn.parquet"
    path.write_bytes(body)
    _receipt(path)
    return path


def _ready_stage(tmp_path: Path) -> tuple[Path, Path, Entry]:
    """A cache with one receipted places file, a review with a tag, and the row."""
    cache = tmp_path / "data" / "public_cache"
    review = _review(tmp_path / "review")
    (review / "arabic_tag.txt").write_text("ar\n", encoding="utf-8")
    places = _row("places_ovt/part-00014", "places_ovt")
    _receipted(cache, "places_ovt/part-00014", b"SYN-PLACES")
    return cache, review, places


class _Recorder:
    """A stand-in stage that keeps the configuration it was handed."""

    def __init__(self) -> None:
        self.config: StageConfig | None = None

    def __call__(self, config: StageConfig) -> None:
        self.config = config


def _refusing_stage(monkeypatch: pytest.MonkeyPatch, reason: str) -> None:
    """A stand-in stage that always refuses with the given reason."""

    def _refuse(_config: StageConfig) -> NoReturn:
        raise PlacesError(reason)

    monkeypatch.setattr(_STAGE, _refuse)


# --- the stage before the gazetteer ----------------------------------------


def test_an_explicit_review_is_read_and_its_refusal_is_named(tmp_path: Path) -> None:
    """A review given by the caller is the one read, and its refusal is named.

    With a review given, the area stage reads that folder and not the one
    derived from the position of the cache. A review row outside the closed
    mode set is refused by its own reason, and the reason is one line of the
    log.
    """
    cache = tmp_path / "data" / "public_cache"
    _install_road(cache)
    review = _review(
        tmp_path / "elsewhere" / "review",
        show=[
            {
                "place_key": "SYN-KEY",
                "mode": "drive",
                "cutoff_minutes": 10,
                "source_id": "places_ovt",
                "record_key": "SYN-P-A",
            }
        ],
    )
    lines: list[str] = []
    areas_before_stage(cache, lines, review)
    assert lines == ["REFUSED showcase_area"]


def test_a_missing_places_file_is_one_fixed_line(tmp_path: Path) -> None:
    """A registry without an active places row is one line of the log."""
    cache = tmp_path / "data" / "public_cache"
    review = _review(tmp_path / "review")
    (review / "arabic_tag.txt").write_text("ar\n", encoding="utf-8")
    lines: list[str] = []
    run_places_before_gazetteer(cache, review, (), (_BOUNDARY,), (), {}, lines)
    assert lines == [_NO_PLACE]


def test_a_missing_frame_boundary_is_one_fixed_line(tmp_path: Path) -> None:
    """A frame with no boundary at all is one line of the log."""
    cache, review, places = _ready_stage(tmp_path)
    lines: list[str] = []
    run_places_before_gazetteer(cache, review, (places,), (), (), {}, lines)
    assert lines == [_NO_BOUNDARY]


def test_the_stage_receives_the_frame_inputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The stage receives the boundary, the zones and the building files.

    The places stage is handed the frame inputs that the registry and the cache
    hold: the boundary, the zones as given, the grid as given, the places file
    with its receipt, and every active building file with its own receipt.
    """
    cache = tmp_path / "data" / "public_cache"
    review = _review(tmp_path / "review")
    (review / "arabic_tag.txt").write_text("ar\n", encoding="utf-8")
    places = _row("places_ovt/part-00014", "places_ovt")
    places_path = _receipted(cache, "places_ovt/part-00014", b"SYN-PLACES")
    building = _row("bldg_ovt/part-90001", "bldg_ovt")
    building_path = _receipted(cache, "bldg_ovt/part-90001", b"SYN-BUILDING")
    recorder = _Recorder()
    monkeypatch.setattr(_STAGE, recorder)
    zones = {"SYN-Z": box(51.0, 25.0, 51.05, 25.05)}
    lines: list[str] = []
    run_places_before_gazetteer(
        cache,
        review,
        (places, building),
        (_BOUNDARY,),
        (),
        zones,
        lines,
        build_date=date(2026, 11, 17),
    )
    assert lines == []
    config = recorder.config
    assert config is not None
    assert config.build_date == date(2026, 11, 17)
    assert config.zones is zones
    assert config.grid == ()
    assert config.boundary is _BOUNDARY
    assert config.places_path == places_path
    assert config.places_receipt == receipt_for(places_path, "places_ovt/part-00014")
    assert config.buildings_paths == (building_path,)
    assert config.buildings_receipts == (
        receipt_for(building_path, "bldg_ovt/part-90001"),
    )


def test_the_arabic_tag_file_is_read_as_utf_8(tmp_path: Path) -> None:
    """The tag file is read under the name utf-8, not under the locale's.

    Under the C locale a read without an encoding name decodes the tag file as
    ASCII and fails on its bytes. The read names utf-8, so a tag that is not
    ASCII is read, and the refusal that follows is the next one in order.
    """
    cache = tmp_path / "data" / "public_cache"
    review = _review(tmp_path / "review")
    (review / "arabic_tag.txt").write_bytes("بتا\n".encode())
    lines: list[str] = []
    with _ascii_locale():
        run_places_before_gazetteer(cache, review, (), (), (), {}, lines)
    assert lines == [_NO_PLACE]


def test_a_refusal_that_is_not_a_closed_token_is_not_logged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A refusal that is not a closed token does not reach the log.

    A line of the log holds closed tokens only: lower-case letters, digits and
    the underscore. A reason that is not one is dropped, and the log stays as
    it was.
    """
    cache, review, places = _ready_stage(tmp_path)
    _refusing_stage(monkeypatch, "Planted Reason")
    lines: list[str] = []
    run_places_before_gazetteer(cache, review, (places,), (_BOUNDARY,), (), {}, lines)
    assert lines == []


def test_a_refusal_with_no_token_is_not_logged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A refusal that is the empty text does not reach the log."""
    cache, review, places = _ready_stage(tmp_path)
    _refusing_stage(monkeypatch, "")
    lines: list[str] = []
    run_places_before_gazetteer(cache, review, (places,), (_BOUNDARY,), (), {}, lines)
    assert lines == []


def test_a_stage_refusal_drops_an_earlier_points_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A stage refusal drops the points file an earlier pass wrote."""
    cache, review, places = _ready_stage(tmp_path)
    points = cache / "places_s2_t06" / "place_points.json"
    points.parent.mkdir(parents=True, exist_ok=True)
    points.write_text("[]", encoding="utf-8")
    _refusing_stage(monkeypatch, "planted_refusal")
    lines: list[str] = []
    run_places_before_gazetteer(cache, review, (places,), (_BOUNDARY,), (), {}, lines)
    assert lines == [_PLANTED]
    assert not points.exists()


def test_a_stage_refusal_tolerates_an_absent_points_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A stage refusal is complete with no earlier points file to drop."""
    cache, review, places = _ready_stage(tmp_path)
    _refusing_stage(monkeypatch, "planted_refusal")
    lines: list[str] = []
    run_places_before_gazetteer(cache, review, (places,), (_BOUNDARY,), (), {}, lines)
    assert lines == [_PLANTED]


def test_one_frame_boundary_is_handed_over_unchanged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """One boundary of the frame is handed to the stage as it stands."""
    cache, review, places = _ready_stage(tmp_path)
    recorder = _Recorder()
    monkeypatch.setattr(_STAGE, recorder)
    lines: list[str] = []
    run_places_before_gazetteer(cache, review, (places,), (_BOUNDARY,), (), {}, lines)
    assert lines == []
    config = recorder.config
    assert config is not None
    assert config.boundary is _BOUNDARY


def test_two_frame_boundaries_are_merged_for_the_stage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two boundaries of the frame reach the stage as one merged shape."""
    cache, review, places = _ready_stage(tmp_path)
    recorder = _Recorder()
    monkeypatch.setattr(_STAGE, recorder)
    lines: list[str] = []
    run_places_before_gazetteer(
        cache,
        review,
        (places,),
        (_BOUNDARY, box(51.15, 25.15, 51.2, 25.2)),
        (),
        {},
        lines,
    )
    assert lines == []
    config = recorder.config
    assert config is not None
    assert config.boundary.geom_type == "MultiPolygon"
    assert [float(value) for value in bounds(config.boundary)] == [
        51.0,
        25.0,
        51.2,
        25.2,
    ]
