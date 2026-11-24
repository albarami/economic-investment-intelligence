"""The two Overture listing parents are never read as Parquet parts (S2-P89).

The fetch stores the release listing of `places_ovt` and `bldg_ovt` under
`<key>/listing` and the lead pins it under the parent key. The places readers
must pass over those two parent keys and still read every real part, whose own
refusals stay as they were. Every file here is invented.
"""

import json
from dataclasses import replace
from pathlib import Path

import pytest
from custodian.tests.fixtures.places.invented import (
    building_row,
    place_row,
    write_buildings,
    write_places,
)
from custodian.tests.test_places_partb_survivors_b import _review
from custodian.tests.test_places_partb_survivors_c import _receipt, _row
from custodian.tests.test_places_partb_survivors_d import _PIN
from hypothesis import given
from hypothesis import strategies as st

from eii_custodian.publicdata.assembly_refusals import stage_refusals
from eii_custodian.publicdata.fetch.registry import load_registry
from eii_custodian.publicdata.fetch.snapshots import reviewed_selections
from eii_custodian.publicdata.places import integrate
from eii_custodian.publicdata.places.areas import AreaError
from eii_custodian.publicdata.review.cache_fixture import select_fixture, write_cached

_PLACE_PART = "places_ovt/part-00014"
_BUILDING_PART = "bldg_ovt/part-00384"
_INDEX_PAIR = [
    "REFUSED frame snapshot_index_invalid",
    "REFUSED frame frame_unexpected_filenotfounderror",
]
_POINTS = {
    ("places_ovt", "SYN-P-A"): (51.5, 25.3),
    ("bldg_ovt", "SYN-B-A"): (51.501, 25.301),
}


def _listing(cache: Path, key: str) -> None:
    """Publish an invented listing where the fetch stores it, pinned by key."""
    entry = next(row for row in load_registry() if row.key == key)
    stored = replace(entry, key=key + "/listing", extension="json")
    body = json.dumps({"parts": ["SYN-PART"]}).encode()
    path = write_cached(cache, stored, body, select=False)
    select_fixture(cache, key, path.stem)


def _cache(tmp_path: Path) -> tuple[Path, Path]:
    """Both pinned listing parents and one valid receipted part of each family."""
    cache = tmp_path / "data" / "public_cache"
    review = _review(tmp_path / "review")
    (review / "arabic_tag.txt").write_text("ar\n", encoding="utf-8")
    for parent in ("places_ovt", "bldg_ovt"):
        _listing(cache, parent)
    places = cache / _PLACE_PART / "syn.parquet"
    places.parent.mkdir(parents=True)
    write_places(places, [place_row()])
    _receipt(places)
    building = cache / _BUILDING_PART / "syn.parquet"
    building.parent.mkdir(parents=True)
    write_buildings(building, [building_row("SYN-B-A", _PIN)])
    _receipt(building)
    return cache, review


def _snapshot_folder(cache: Path, key: str) -> tuple[Path, str]:
    return cache / key, reviewed_selections(cache)[key]


def test_listing_parents_are_pinned_where_the_fetch_stores_them(
    tmp_path: Path,
) -> None:
    cache, _review_folder = _cache(tmp_path)
    for parent in ("places_ovt", "bldg_ovt"):
        folder, digest = _snapshot_folder(cache, parent)
        assert (folder / "listing" / "index" / (digest + ".json")).is_file()
        assert not (folder / "index").exists()


def test_listing_parents_are_never_read_as_parts(tmp_path: Path) -> None:
    cache, review = _cache(tmp_path)
    registry = load_registry()
    lines: list[str] = []
    with stage_refusals(lines, "frame"):
        points = integrate._cache_points(cache, review)
        located = integrate._place_from_registry(cache, registry)
        _paths, receipts = integrate._buildings_from_registry(cache, registry)
    assert lines == []
    assert points == _POINTS
    assert located is not None and located[1].source_key == _PLACE_PART
    assert [receipt.source_key for receipt in receipts] == [_BUILDING_PART]


def test_area_producer_logs_nothing_for_the_listing_parents(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache, review = _cache(tmp_path)
    monkeypatch.setattr(integrate, "road_receipt", lambda _cache: "0" * 64)
    monkeypatch.setattr(integrate, "area_requests", lambda _review, _points: ())
    lines: list[str] = []
    with stage_refusals(lines, "frame"):
        integrate.areas_before_stage(cache, lines, review)
    assert lines == ["areas: nothing to do"]


# --- a real part keeps its own refusals -------------------------------------


def _drop_index(cache: Path, key: str) -> None:
    folder, digest = _snapshot_folder(cache, key)
    (folder / "index" / (digest + ".json")).unlink()


def _corrupt_body(cache: Path, key: str) -> None:
    folder, digest = _snapshot_folder(cache, key)
    index = json.loads((folder / "index" / (digest + ".json")).read_text())
    body = folder / index["path"]
    body.write_bytes(body.read_bytes() + b"\n")


def test_building_part_without_its_index_still_refuses_in_the_area_producer(
    tmp_path: Path,
) -> None:
    cache, review = _cache(tmp_path)
    _drop_index(cache, _BUILDING_PART)
    lines: list[str] = []
    with (
        pytest.raises(AreaError, match=r"^places_file_digest$"),
        stage_refusals(lines, "frame"),
    ):
        integrate._cache_points(cache, review)
    assert lines == [*_INDEX_PAIR, "REFUSED frame places_file_digest"]


def test_registry_only_building_part_without_its_index_still_refuses(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A part outside the fetch list reaches the registry loop the parent hit."""
    cache, review = _cache(tmp_path)
    extra = "bldg_ovt/part-90001"
    building = cache / extra / "syn.parquet"
    building.parent.mkdir(parents=True)
    write_buildings(building, [building_row("SYN-B-B", _PIN)])
    _receipt(building)
    registry = (*load_registry(), _row(extra, "bldg_ovt"))
    monkeypatch.setattr(integrate, "load_registry", lambda: registry)
    lines: list[str] = []
    with stage_refusals(lines, "frame"):
        assert ("bldg_ovt", "SYN-B-B") in integrate._cache_points(cache, review)
    assert lines == []
    _drop_index(cache, extra)
    with (
        pytest.raises(AreaError, match=r"^places_file_digest$"),
        stage_refusals(lines, "frame"),
    ):
        integrate._cache_points(cache, review)
    assert lines == [*_INDEX_PAIR, "REFUSED frame places_file_digest"]


def test_building_part_without_its_index_still_logs_in_the_stage(
    tmp_path: Path,
) -> None:
    cache, _review_folder = _cache(tmp_path)
    _drop_index(cache, _BUILDING_PART)
    lines: list[str] = []
    with stage_refusals(lines, "frame"):
        paths, receipts = integrate._buildings_from_registry(cache, load_registry())
    assert (paths, receipts) == ((), ())
    assert lines == _INDEX_PAIR


def test_place_part_without_its_index_still_logs_in_the_stage(
    tmp_path: Path,
) -> None:
    cache, _review_folder = _cache(tmp_path)
    _drop_index(cache, _PLACE_PART)
    lines: list[str] = []
    with stage_refusals(lines, "frame"):
        located = integrate._place_from_registry(cache, load_registry())
    assert located is None
    assert lines == _INDEX_PAIR


def test_building_part_with_a_wrong_digest_still_refuses(tmp_path: Path) -> None:
    cache, review = _cache(tmp_path)
    _corrupt_body(cache, _BUILDING_PART)
    lines: list[str] = []
    with (
        pytest.raises(AreaError, match=r"^places_file_digest$"),
        stage_refusals(lines, "frame"),
    ):
        integrate._cache_points(cache, review)
    assert lines == [
        "REFUSED frame snapshot_hash_mismatch",
        "REFUSED frame places_file_digest",
    ]


def test_place_part_with_a_wrong_digest_still_refuses(tmp_path: Path) -> None:
    cache, _review_folder = _cache(tmp_path)
    _corrupt_body(cache, _PLACE_PART)
    lines: list[str] = []
    with stage_refusals(lines, "frame"):
        located = integrate._place_from_registry(cache, load_registry())
    assert located is None
    assert lines == ["REFUSED frame snapshot_hash_mismatch"]


# --- the exclusion is by exact key ------------------------------------------

_KEYS = st.sampled_from(
    [
        "bldg_ovt",
        "bldg_ovt/listing",
        "bldg_ovt/part-00384",
        "bldg_ovt/part-90001",
        "bldg_ovt/stac-collection",
        "bldg_ovt_extra/part-00001",
        "places_ovt",
        "places_ovt/part-00014",
    ]
)
_ROWS = st.builds(
    lambda key, source, skip, extension: replace(
        _row(key if "/" in key else key + "/x", source, skip=skip),
        key=key,
        extension=extension,
    ),
    _KEYS,
    st.sampled_from(["bldg_ovt", "places_ovt"]),
    st.sampled_from(["", "SYN skipped"]),
    st.sampled_from(["parquet", "json"]),
)


@given(st.lists(_ROWS, max_size=8))
def test_building_entries_drop_only_the_exact_parent_key(rows: list) -> None:
    expected = tuple(
        row
        for row in rows
        if row.source_id == "bldg_ovt"
        and row.skip_reason == ""
        and row.extension == "parquet"
        and row.key != "bldg_ovt"
    )
    assert integrate._building_entries(rows) == expected
