"""Kill the surviving mutants of the request pairing and of the frame build.

The request pairing joins a review row to a point the cache read, and refuses a
row whose source key, record key or place key is empty. The frame build opens
only from its own boundary source, and it publishes the build log the stage
below takes its refusals from.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import replace
from pathlib import Path
from typing import Any, NoReturn

import pytest
from custodian.tests.test_frame_census import entry
from custodian.tests.test_places_pass2 import _empty_review

from eii_custodian.publicdata.fetch.registry import Entry
from eii_custodian.publicdata.frame.checks import FrameError
from eii_custodian.publicdata.places.area_files import AreaRequest
from eii_custodian.publicdata.places.area_requests import _remember, area_requests
from eii_custodian.publicdata.places.areas import AreaCutoff, AreaMode
from eii_custodian.publicdata.places.integrate import (
    _BUILD_LINES,
    frame_when_ready,
    run_places_before_gazetteer,
)

_TAG_MISSING = "stage places arabic_tag_missing"
_FRAME_BUILD = "eii_custodian.publicdata.frame.build.build_frame"


def _review(
    folder: Path,
    *,
    show: Sequence[Mapping[str, object]] = (),
    flag: Sequence[Mapping[str, object]] = (),
) -> Path:
    """A review folder with the given showcase and flagship rows."""
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "showcase_areas.yaml").write_text(_body(show), encoding="utf-8")
    (folder / "flagship_candidates.yaml").write_text(_body(flag), encoding="utf-8")
    return folder


def _body(rows: Sequence[Mapping[str, object]]) -> str:
    """The YAML of a list of rows. No rows is the empty list."""
    return "".join(_yaml(row) for row in rows) or "[]\n"


def _yaml(row: Mapping[str, object]) -> str:
    """One YAML list item, one line per key, its keys in the row's own order."""
    names = list(row)
    lines = []
    for position, name in enumerate(names):
        value = row[name]
        text = f"'{value}'" if isinstance(value, str) else str(value)
        lines.append(f"{'- ' if position == 0 else '  '}{name}: {text}\n")
    return "".join(lines)


def _show_row(place_key: str, source_id: str, record_key: str) -> dict[str, object]:
    """One showcase row, always walk at ten minutes."""
    return {
        "place_key": place_key,
        "mode": "walk",
        "cutoff_minutes": 10,
        "source_id": source_id,
        "record_key": record_key,
    }


def _flag_row(place_key: str) -> dict[str, object]:
    """One flagship row of the whole closed key set."""
    return {
        "place_key": place_key,
        "kind": "syn_kind",
        "name_en": "SYN Place",
        "name_ar": "مكان",
        "aliases": "SYN Alias",
        "source_id": "places_ovt",
        "record_key": "SYN-P-A",
        "arabic_review": "none",
    }


# --- the request pairing ---------------------------------------------------


def test_a_showcase_row_with_no_closed_key_makes_no_request(tmp_path: Path) -> None:
    """An empty source key or record key is refused, whatever the points hold.

    A row whose source key or record key is empty makes no request even when
    the points map happens to hold that empty key. A key that is not empty is
    taken as it stands.
    """
    review = _review(
        tmp_path / "review",
        show=[
            _show_row("SYN-NO-SOURCE", "", "SYN-P-A"),
            _show_row("SYN-NO-RECORD", "places_ovt", ""),
            _show_row("SYN-MARK-SOURCE", "XXXX", "SYN-P-A"),
            _show_row("SYN-MARK-RECORD", "places_ovt", "XXXX"),
            _show_row("SYN-GOOD", "places_ovt", "SYN-P-A"),
        ],
    )
    points = {
        ("", "SYN-P-A"): (51.5, 25.3),
        ("places_ovt", ""): (51.5, 25.3),
        ("XXXX", "SYN-P-A"): (51.5, 25.3),
        ("places_ovt", "XXXX"): (51.5, 25.3),
        ("places_ovt", "SYN-P-A"): (51.5, 25.3),
    }
    assert area_requests(review, points) == (
        AreaRequest(
            "SYN-GOOD", "51.500000", "25.300000", AreaMode.WALK, AreaCutoff.MINUTES_10
        ),
        AreaRequest(
            "SYN-MARK-RECORD",
            "51.500000",
            "25.300000",
            AreaMode.WALK,
            AreaCutoff.MINUTES_10,
        ),
        AreaRequest(
            "SYN-MARK-SOURCE",
            "51.500000",
            "25.300000",
            AreaMode.WALK,
            AreaCutoff.MINUTES_10,
        ),
    )


def test_a_flagship_row_with_no_place_key_makes_no_request(tmp_path: Path) -> None:
    """A flagship row without a place key makes no request.

    The review load checks only that the closed keys are present, so an empty
    place key reaches the pairing, and the pairing refuses it. A place key that
    is not empty is taken as it stands, and its row makes one request for each
    candidate area.
    """
    review = _review(tmp_path / "review", flag=[_flag_row(""), _flag_row("XXXX")])
    points = {("places_ovt", "SYN-P-A"): (51.5, 25.3)}
    assert area_requests(review, points) == (
        AreaRequest(
            "XXXX", "51.500000", "25.300000", AreaMode.DRIVE, AreaCutoff.MINUTES_10
        ),
        AreaRequest(
            "XXXX", "51.500000", "25.300000", AreaMode.WALK, AreaCutoff.MINUTES_5
        ),
        AreaRequest(
            "XXXX", "51.500000", "25.300000", AreaMode.WALK, AreaCutoff.MINUTES_10
        ),
    )


def test_a_request_without_a_closed_mode_or_cutoff_is_not_remembered() -> None:
    """A row with no closed mode, or no closed cutoff, is left out."""
    points = {("places_ovt", "SYN-P-A"): (51.5, 25.3)}
    row: Mapping[str, object] = {
        "source_id": "places_ovt",
        "record_key": "SYN-P-A",
        "place_key": "SYN-KEY",
    }
    found: dict[tuple[str, str, int], AreaRequest] = {}
    _remember(found, row, points, None, AreaCutoff.MINUTES_10)
    _remember(found, row, points, AreaMode.WALK, None)
    assert found == {}


# --- the frame build and its log -------------------------------------------


def _opened_boundary(tmp_path: Path) -> tuple[Path, Path, Entry]:
    """A cache holding the boundary source's receipt, and the review beside it."""
    cache = tmp_path / "data" / "public_cache"
    review = _empty_review(tmp_path)
    boundary = entry("bnd_hdx")
    (cache / boundary.key).mkdir(parents=True)
    (cache / boundary.key / "planted.meta.json").write_text("{}", encoding="utf-8")
    return cache, review, boundary


def _frame_stand_in(calls: list[tuple[Any, ...]]) -> Any:
    """A stand-in frame build: it records what it was handed, then refuses."""

    def _stand_in(
        cache_given: Path,
        registry: tuple[Entry, ...],
        review_given: Path,
        output: Any = None,
        *,
        build_date: Any = None,
    ) -> NoReturn:
        calls.append((cache_given, registry, review_given, output))
        raise FrameError("planted")

    return _stand_in


def test_a_frame_is_built_only_from_its_own_boundary_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A boundary source that is skipped does not open the frame build.

    The search for the boundary source takes a row whose skip reason is empty.
    A row that is skipped is passed over, and with nothing left the frame build
    is not opened at all, however full the cache of another source is.
    """
    cache = tmp_path / "data" / "public_cache"
    _empty_review(tmp_path)
    calls: list[tuple[Any, ...]] = []
    monkeypatch.setattr(_FRAME_BUILD, _frame_stand_in(calls))
    active = entry("util_elec")
    (cache / active.key).mkdir(parents=True)
    (cache / active.key / "planted.meta.json").write_text("{}", encoding="utf-8")
    planted = replace(entry("bnd_hdx"), skip_reason="planted_not_fetched")
    lines: list[str] = []
    frame_when_ready(cache, (active, planted), lines)
    assert calls == []
    assert lines == []


def test_the_frame_build_receives_the_cache_the_rows_and_the_review(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The frame build is handed the cache, every row and the review.

    The build opens with the cache, the whole registry the caller handed over,
    the review folder beside the cache, and no generated review output of its
    own. Its own refusal is one line of the log.
    """
    cache, review, boundary = _opened_boundary(tmp_path)
    calls: list[tuple[Any, ...]] = []
    monkeypatch.setattr(_FRAME_BUILD, _frame_stand_in(calls))
    lines: list[str] = []
    frame_when_ready(cache, (boundary,), lines)
    assert calls == [(cache, (boundary,), review, None)]
    assert lines == ["stage frame frame_refused"]


def test_a_frame_build_hands_its_log_to_the_places_stage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The frame build publishes the log it was given, and the stage writes it.

    The stage called from inside the frame build takes its log from the build
    log of the context, which the frame set to the very list it was given. The
    refusal of the stage therefore reaches the caller's own list.
    """
    cache, _, boundary = _opened_boundary(tmp_path)

    def _stand_in(
        cache_given: Path,
        registry: tuple[Entry, ...],
        review_given: Path,
        output: Any = None,
        *,
        build_date: Any = None,
    ) -> None:
        run_places_before_gazetteer(cache_given, review_given, (), (), (), {})

    monkeypatch.setattr(_FRAME_BUILD, _stand_in)
    lines: list[str] = []
    frame_when_ready(cache, (boundary,), lines)
    assert lines == [_TAG_MISSING]


def test_a_frame_build_publishes_a_log_even_when_it_has_none(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With no list of its own, the frame build still publishes one.

    The stage below takes its log from the build log of the context. With no
    list given, the frame publishes an empty list when the build opens, not
    nothing, so a refusal of the stage still has somewhere to go.
    """
    cache, _, boundary = _opened_boundary(tmp_path)
    seen: list[Any] = []

    def _stand_in(
        cache_given: Path,
        registry: tuple[Entry, ...],
        review_given: Path,
        output: Any = None,
        *,
        build_date: Any = None,
    ) -> NoReturn:
        published = _BUILD_LINES.get()
        seen.append(None if published is None else list(published))
        raise FrameError("planted")

    monkeypatch.setattr(_FRAME_BUILD, _stand_in)
    frame_when_ready(cache, (boundary,))
    assert seen == [[]]


def test_the_places_stage_takes_the_build_log_of_the_context(tmp_path: Path) -> None:
    """With no list given, the stage writes the build log of the context."""
    cache = tmp_path / "data" / "public_cache"
    review = tmp_path / "review"
    review.mkdir(parents=True)
    log: list[str] = []
    token = _BUILD_LINES.set(log)
    try:
        run_places_before_gazetteer(cache, review, (), (), (), {})
    finally:
        _BUILD_LINES.reset(token)
    assert log == [_TAG_MISSING]
