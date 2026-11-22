"""Kill the surviving mutants of the cache read and of the registry receipts.

The cache read goes over the four file keys in order and takes the point of
every place and every building whose file is receipted, passing over a key
whose folder is not there and over a file that refuses. The registry receipts
join a row of the two places sources to the one body its receipt agrees with.
"""

from __future__ import annotations

import hashlib
from dataclasses import replace
from pathlib import Path

import pytest
from custodian.tests.fixtures.places.invented import (
    building_row,
    place_row,
    receipt_for,
    write_buildings,
    write_places,
)
from custodian.tests.test_places_partb_survivors_b import _review
from custodian.tests.test_places_partb_survivors_c import (
    _RETRIEVED,
    _ascii_locale,
    _receipt,
    _receipted,
    _row,
)

from eii_custodian.publicdata.fetch.registry import load_registry
from eii_custodian.publicdata.places.areas import AreaError
from eii_custodian.publicdata.places.integrate import (
    _buildings_from_registry,
    _cache_points,
    _opened_place,
    _place_from_registry,
    _receipt_of,
)
from eii_custodian.publicdata.places.read import FileReceipt

_PIN = (
    (51.500, 25.300),
    (51.502, 25.300),
    (51.502, 25.302),
    (51.500, 25.302),
    (51.500, 25.300),
)
_SWAPPED = (
    (25.300, 51.500),
    (25.300, 51.502),
    (25.302, 51.502),
    (25.302, 51.500),
    (25.300, 51.500),
)

# --- the points of the cache -----------------------------------------------


def test_a_missing_places_file_does_not_stop_the_buildings(tmp_path: Path) -> None:
    """A places file that is not there does not stop the building files.

    The search goes over the file keys in order. A key whose folder is not
    there is passed over, and the building file behind the next key is still
    read, with the point on the surface of its footprint as its own point.
    """
    cache = tmp_path / "data" / "public_cache"
    review = _review(tmp_path / "review")
    building = cache / "bldg_ovt" / "part-00384" / "syn.parquet"
    building.parent.mkdir(parents=True)
    write_buildings(building, [building_row("SYN-B-A", _PIN)])
    _receipt(building)
    assert _cache_points(cache, review) == {("bldg_ovt", "SYN-B-A"): (51.501, 25.301)}


def test_a_places_file_that_refuses_does_not_stop_the_buildings(tmp_path: Path) -> None:
    """A places file that refuses does not stop the building files."""
    cache = tmp_path / "data" / "public_cache"
    review = _review(tmp_path / "review")
    (review / "arabic_tag.txt").write_text("ar\n", encoding="utf-8")
    places = cache / "places_ovt" / "part-00014" / "syn.parquet"
    places.parent.mkdir(parents=True)
    write_places(places, [place_row()], drop=("basic_category",))
    _receipt(places)
    building = cache / "bldg_ovt" / "part-00384" / "syn.parquet"
    building.parent.mkdir(parents=True)
    write_buildings(building, [building_row("SYN-B-A", _PIN)])
    _receipt(building)
    assert _cache_points(cache, review) == {("bldg_ovt", "SYN-B-A"): (51.501, 25.301)}


def test_an_empty_tag_skips_only_the_places_keys(tmp_path: Path) -> None:
    """With no tag, the places keys are passed over and the buildings are read.

    The places read needs the Arabic tag and refuses without it, so a build
    with no tag does not read the places files at all. It still reads the
    building files, which need no tag.
    """
    cache = tmp_path / "data" / "public_cache"
    review = _review(tmp_path / "review")
    places = cache / "places_ovt" / "part-00014" / "syn.parquet"
    places.parent.mkdir(parents=True)
    write_places(places, [place_row()])
    _receipt(places)
    building = cache / "bldg_ovt" / "part-00384" / "syn.parquet"
    building.parent.mkdir(parents=True)
    write_buildings(building, [building_row("SYN-B-A", _PIN)])
    _receipt(building)
    assert _cache_points(cache, review) == {("bldg_ovt", "SYN-B-A"): (51.501, 25.301)}


def test_a_tag_that_is_not_empty_reads_the_places_file(tmp_path: Path) -> None:
    """A tag that is not the empty text reads the places file."""
    cache = tmp_path / "data" / "public_cache"
    review = _review(tmp_path / "review")
    (review / "arabic_tag.txt").write_text("XXXX\n", encoding="utf-8")
    places = cache / "places_ovt" / "part-00014" / "syn.parquet"
    places.parent.mkdir(parents=True)
    write_places(places, [place_row()])
    _receipt(places)
    assert _cache_points(cache, review) == {("places_ovt", "SYN-P-A"): (51.5, 25.3)}


def test_a_swapped_buildings_file_is_refused_by_the_frame_box(tmp_path: Path) -> None:
    """A building file with its axes the wrong way round is refused.

    The building read is given the frame box, so a footprint whose longitude
    and latitude are the wrong way round is refused by name and its file is
    passed over, rather than adding a point outside the frame.
    """
    cache = tmp_path / "data" / "public_cache"
    review = _review(tmp_path / "review")
    building = cache / "bldg_ovt" / "part-00384" / "syn.parquet"
    building.parent.mkdir(parents=True)
    write_buildings(building, [building_row("SYN-B-A", _SWAPPED)])
    _receipt(building)
    assert _cache_points(cache, review) == {}


def test_a_file_key_the_registry_does_not_hold_is_refused(tmp_path: Path) -> None:
    """A file key the registry does not hold is refused by name."""
    cache = tmp_path / "cache"
    assert "places_ovt/part-90001" not in {row.key for row in load_registry()}
    path = cache / "places_ovt" / "part-90001" / "syn.parquet"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"SYN-PLACES")
    _receipt(path)
    with pytest.raises(AreaError) as caught:
        _opened_place(cache, "places_ovt/part-90001")
    assert caught.value.reason == "places_file_unreceipted"


# --- the registry and its receipts -----------------------------------------


@pytest.mark.parametrize("source", ["places_ovt", "bldg_ovt"])
def test_stac_receipts_never_enter_the_parquet_stage(
    tmp_path: Path, source: str
) -> None:
    """A valid STAC snapshot before a valid part cannot become a Parquet input."""
    cache = tmp_path / "cache"
    part = _row(source + "/part-90001", source)
    path = _receipted(cache, part.key, b"SYN-PARQUET")
    metadata = []
    for suffix in ("collection", "part-00288", "part-00384", "part-00385"):
        key = source + "/stac-" + suffix
        row = replace(_row(key, source), extension="json")
        stac = cache / key / "syn.json"
        stac.parent.mkdir(parents=True)
        stac.write_bytes(b'{"type":"SYN-STAC"}')
        _receipt(stac)
        assert _receipt_of(cache, row) is not None
        metadata.append(row)
    entries = (*metadata, part)
    expected_path = next(path.parent.glob("*/*.parquet"))
    expected_receipt = receipt_for(path, part.key)
    if source == "bldg_ovt":
        assert _buildings_from_registry(cache, entries) == (
            (expected_path,),
            (expected_receipt,),
        )
    else:
        assert _place_from_registry(cache, entries) == (expected_path, expected_receipt)


def test_only_an_active_buildings_row_with_a_receipt_is_read(tmp_path: Path) -> None:
    """Only an active building row whose receipt agrees is read.

    The search takes the rows of the buildings source whose skip reason is
    empty, and of those only the ones whose receipt agrees with the file on
    disk. A row of another source, a skipped row and a row with no receipt are
    all passed over, and the search does not stop at any of them.
    """
    cache = tmp_path / "cache"
    other = _row("places_ovt/part-00014", "places_ovt")
    skipped = _row("bldg_ovt/part-90002", "bldg_ovt", skip="planted_not_fetched")
    marked = _row("bldg_ovt/part-90003", "bldg_ovt", skip="XXXX")
    bare = _row("bldg_ovt/part-90004", "bldg_ovt")
    active = _row("bldg_ovt/part-90001", "bldg_ovt")
    _receipted(cache, "places_ovt/part-00014", b"SYN-PLACES")
    _receipted(cache, "bldg_ovt/part-90002", b"SYN-B-TWO")
    _receipted(cache, "bldg_ovt/part-90003", b"SYN-B-THREE")
    bare_folder = cache / "bldg_ovt" / "part-90004"
    bare_folder.mkdir(parents=True)
    (bare_folder / "syn.parquet").write_bytes(b"SYN-B-FOUR")
    active_path = _receipted(cache, "bldg_ovt/part-90001", b"SYN-B-ONE")
    paths, receipts = _buildings_from_registry(
        cache, (other, skipped, marked, bare, active)
    )
    assert paths == (next(active_path.parent.glob("*/*.parquet")),)
    assert receipts == (receipt_for(active_path, "bldg_ovt/part-90001"),)


def test_two_bodies_under_one_receipt_are_refused(tmp_path: Path) -> None:
    """Two bodies under one receipt are refused, not read in some order."""
    cache = tmp_path / "cache"
    row = _row("bldg_ovt/part-90001", "bldg_ovt")
    folder = cache / "bldg_ovt" / "part-90001"
    folder.mkdir(parents=True)
    first = folder / "a_syn.parquet"
    first.write_bytes(b"SYN-B-ONE")
    (folder / "b_syn.parquet").write_bytes(b"SYN-B-TWO")
    _receipt(first)
    selected = _receipt_of(cache, row)
    assert selected is not None
    assert selected[0].read_bytes() == b"SYN-B-ONE"


def test_a_receipt_is_read_as_utf_8_and_kept_whole(tmp_path: Path) -> None:
    """A receipt is read under the name utf-8, and is kept whole.

    Under the C locale a read without an encoding name decodes the receipt as
    ASCII and fails on a publisher that is not ASCII. The read names utf-8, and
    the receipt it returns holds the key of the row, the digest, the retrieval
    time and the publisher of the receipt file.
    """
    cache = tmp_path / "cache"
    row = _row("bldg_ovt/part-90001", "bldg_ovt")
    path = _receipted(cache, "bldg_ovt/part-90001", b"SYN-B-ONE", publisher="ناشر")

    with _ascii_locale():
        assert _receipt_of(cache, row) == (
            next(path.parent.glob("*/*.parquet")),
            FileReceipt(
                "bldg_ovt/part-90001",
                hashlib.sha256(b"SYN-B-ONE").hexdigest(),
                _RETRIEVED,
                "ناشر",
            ),
        )


def test_a_receipt_whose_publisher_is_not_text_is_refused(tmp_path: Path) -> None:
    """A receipt whose publisher is not text is refused."""
    cache = tmp_path / "cache"
    row = _row("bldg_ovt/part-90001", "bldg_ovt")
    path = _receipted(cache, "bldg_ovt/part-90001", b"SYN-B-ONE")
    _receipt(path, publisher=5)
    assert _receipt_of(cache, row) is None


def test_a_receipt_whose_retrieval_time_is_not_text_is_refused(tmp_path: Path) -> None:
    """A receipt whose retrieval time is not text is refused."""
    cache = tmp_path / "cache"
    row = _row("bldg_ovt/part-90001", "bldg_ovt")
    path = _receipted(cache, "bldg_ovt/part-90001", b"SYN-B-ONE")
    _receipt(path, retrieved_utc=5)
    assert _receipt_of(cache, row) is None


def test_a_receipt_whose_digest_is_not_text_is_refused(tmp_path: Path) -> None:
    """A receipt whose digest is not text is refused."""
    cache = tmp_path / "cache"
    row = _row("bldg_ovt/part-90001", "bldg_ovt")
    path = _receipted(cache, "bldg_ovt/part-90001", b"SYN-B-ONE")
    _receipt(path, sha256=5)
    assert _receipt_of(cache, row) is None
