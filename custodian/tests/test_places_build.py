"""Invented places files. No record value of a real file is stored here."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest
from custodian.tests.fixtures.places.invented import (
    place_row,
    receipt_for,
    write_places,
)
from shapely.geometry import box

from eii_custodian.publicdata.places import PlacesError
from eii_custodian.publicdata.places.areas import (
    AreaCutoff,
    AreaMode,
    AreaResult,
    ReviewedPoint,
)
from eii_custodian.publicdata.places.build import build_places
from eii_custodian.publicdata.places.display import CAVEAT_KEY, CONFIDENCE_MIN
from eii_custodian.publicdata.places.read import SOURCE_RELEASE

_LICENCE = "SYN-LICENCE"
_ATTR = (("syn-source", _LICENCE),)
_BOX = box(51.4, 25.2, 51.6, 25.4)


def test_row_without_source_provider_is_left_out(tmp_path: Path) -> None:
    """A row with no record-level source does not enter pub_place."""
    path = tmp_path / "places.parquet"
    write_places(
        path,
        [
            place_row(
                place_id="SYN-P-NOSRC",
                sources=[{"property": "names", "dataset": "syn-source"}],
            )
        ],
    )
    result = build_places(
        path,
        arabic_tag="ar",
        boundary=_BOX,
        grid=_grid((25.3, 51.5)),
        attribution=_ATTR,
        places_receipt=receipt_for(path),
    )
    assert result.places == ()
    assert result.excluded["record_level_absent"] == 1
    assert result.complete is False
    assert "showcase_areas_pending" in result.report
    assert result.caveat.key == CAVEAT_KEY


def test_kept_row_carries_provider_licence_and_confidence(tmp_path: Path) -> None:
    """The licence comes from the token table, not from sources[].license."""
    path = tmp_path / "places.parquet"
    write_places(
        path,
        [
            place_row(
                place_id="SYN-P-A",
                sources=[
                    {
                        "property": "",
                        "dataset": "syn-source",
                        "license": "NOT-THE-LICENCE",
                    }
                ],
            )
        ],
    )
    result = build_places(
        path,
        arabic_tag="ar",
        boundary=_BOX,
        grid=_grid((25.3, 51.5)),
        attribution=_ATTR,
        categories=(("syn_restaurant", "restaurant"),),
        places_receipt=receipt_for(path),
    )
    assert len(result.places) == 1
    place = result.places[0]
    assert place.source_provider == "syn-source"
    assert place.licence == _LICENCE
    assert place.confidence == Decimal("0.8000")
    assert place.confidence >= CONFIDENCE_MIN
    assert place.category == "syn_restaurant"
    assert place.category_class == "restaurant"
    assert place.source_release == SOURCE_RELEASE
    assert place.name_ar == "مقهى تجريبي"
    assert place.place_id in result.shown_ids
    assert result.caveat.text_en == "Open listings are incomplete"


def test_blank_attribution_licence_is_pub_place_field(tmp_path: Path) -> None:
    """The kept-row fixture with an empty licence refuses pub_place_field."""
    path = tmp_path / "places.parquet"
    write_places(
        path,
        [
            place_row(
                place_id="SYN-P-A",
                sources=[
                    {
                        "property": "",
                        "dataset": "syn-source",
                        "license": "NOT-THE-LICENCE",
                    }
                ],
            )
        ],
    )
    with pytest.raises(PlacesError, match="pub_place_field"):
        build_places(
            path,
            arabic_tag="ar",
            boundary=_BOX,
            grid=_grid((25.3, 51.5)),
            attribution=(("syn-source", ""),),
            categories=(("syn_restaurant", "restaurant"),),
            places_receipt=receipt_for(path),
        )


def test_null_confidence_two_sources_missing_token_and_osm(tmp_path: Path) -> None:
    """Each refusal is counted, and a missing token is named."""
    path = tmp_path / "places.parquet"
    write_places(
        path,
        [
            place_row(place_id="SYN-P-NULL", confidence=None),
            place_row(
                place_id="SYN-P-TWO",
                sources=[
                    {"property": "", "dataset": "syn-source", "license": None},
                    {"property": "", "dataset": "syn-other", "license": None},
                ],
            ),
            place_row(
                place_id="SYN-P-MISS",
                sources=[
                    {"property": "", "dataset": "syn-missing", "license": "IGNORED"}
                ],
            ),
            place_row(
                place_id="SYN-P-OSM",
                sources=[{"property": "", "dataset": "OpenStreetMap", "license": None}],
            ),
        ],
    )
    result = build_places(
        path,
        arabic_tag="ar",
        boundary=_BOX,
        grid=_grid((25.3, 51.5)),
        attribution=_ATTR,
        places_receipt=receipt_for(path),
    )
    assert result.places == ()
    assert result.excluded["null_confidence"] == 1
    assert result.excluded["record_level_not_unique"] == 1
    assert result.excluded["attribution_missing"] == 1
    assert result.excluded["osm_not_merged"] == 1
    assert "identifier" not in result.excluded
    assert "attribution token missing: syn-missing" in result.report


def test_outside_boundary_is_counted(tmp_path: Path) -> None:
    """A point outside the national boundary is not a pub_place row."""
    path = tmp_path / "places.parquet"
    write_places(path, [place_row(place_id="SYN-P-OUT", lon=51.0, lat=25.0)])
    result = build_places(
        path,
        arabic_tag="ar",
        boundary=_BOX,
        grid=_grid((25.0, 51.0)),
        attribution=_ATTR,
        places_receipt=receipt_for(path),
    )
    assert result.places == ()
    assert result.excluded["outside_boundary"] == 1


def test_empty_arabic_tag_is_refused(tmp_path: Path) -> None:
    """The Arabic name tag is a required argument."""
    path = tmp_path / "places.parquet"
    write_places(path, [place_row()])
    with pytest.raises(PlacesError, match="arabic_tag"):
        build_places(path, arabic_tag="", boundary=_BOX, grid=_grid((25.3, 51.5)))


def test_receipt_is_checked_before_the_file_is_read(tmp_path: Path) -> None:
    """A different digest refuses the file, including bytes that are not Parquet."""
    from eii_custodian.publicdata.places.read import FileReceipt

    path = tmp_path / "places.parquet"
    write_places(path, [place_row(place_id="SYN-P-A")])
    wrong = FileReceipt("places_ovt", "a" * 64, "2026-11-14T00:00:00Z", "SYN Publisher")
    with pytest.raises(PlacesError, match="receipt_mismatch"):
        build_places(
            path,
            arabic_tag="ar",
            boundary=_BOX,
            grid=_grid((25.3, 51.5)),
            attribution=_ATTR,
            places_receipt=wrong,
        )
    raw = tmp_path / "notes.txt"
    raw.write_bytes(b"not parquet")
    with pytest.raises(PlacesError, match="receipt_mismatch"):
        build_places(
            raw,
            arabic_tag="ar",
            boundary=_BOX,
            grid=_grid((25.3, 51.5)),
            attribution=_ATTR,
            places_receipt=FileReceipt(
                "places_ovt", "b" * 64, "2026-11-14T00:00:00Z", "SYN Publisher"
            ),
        )
    digest = receipt_for(path).sha256
    with pytest.raises(PlacesError, match="receipt_missing"):
        build_places(
            path,
            arabic_tag="ar",
            boundary=_BOX,
            grid=_grid((25.3, 51.5)),
            attribution=_ATTR,
            places_receipt=FileReceipt("places_ovt", digest, "", "SYN Publisher"),
        )


def test_kept_row_lineage_is_the_receipt(tmp_path: Path) -> None:
    """The kept row resolves to the receipt's publisher, time and hash."""
    from eii_custodian.publicdata.places.read import FileReceipt

    path = tmp_path / "places.parquet"
    write_places(path, [place_row(place_id="SYN-P-A")])
    digest = receipt_for(path).sha256
    receipt = FileReceipt("places_ovt", digest, "2026-11-14T00:00:00Z", "SYN Publisher")
    result = build_places(
        path,
        arabic_tag="ar",
        boundary=_BOX,
        grid=_grid((25.3, 51.5)),
        attribution=_ATTR,
        places_receipt=receipt,
    )
    stored = result.receipts[0]
    assert stored.source_key == "places_ovt"
    assert stored.sha256 == digest
    assert stored.retrieved_utc == "2026-11-14T00:00:00Z"
    assert stored.publisher == "SYN Publisher"
    assert result.places[0].source_provider == "syn-source"
    assert result.places[0].licence == "SYN-LICENCE"


def test_buildings_outside_duplicate_and_second_file(tmp_path: Path) -> None:
    """Outside footprints are counted. A repeated id refuses. The second file is read."""
    from custodian.tests.fixtures.places.invented import building_row, write_buildings

    places = tmp_path / "places.parquet"
    write_places(places, [place_row(place_id="SYN-P-A")])
    outside = tmp_path / "outside.parquet"
    write_buildings(
        outside,
        [
            building_row(
                "SYN-B-OUT", ((50.0, 24.0), (50.1, 24.0), (50.1, 24.1), (50.0, 24.0))
            )
        ],
    )
    output = tmp_path / "out"
    result = build_places(
        places,
        arabic_tag="ar",
        boundary=_BOX,
        grid=_grid((25.3, 51.5)),
        attribution=_ATTR,
        places_receipt=receipt_for(places),
        buildings_paths=(outside,),
        buildings_receipts=(receipt_for(outside, "bldg_ovt"),),
        output_dir=output,
    )
    assert result.excluded["building_outside_boundary"] == 1
    written = (output / "places_s2_t06" / "place_points.json").read_text(
        encoding="utf-8"
    )
    assert "SYN-B-OUT" not in written

    first = tmp_path / "first.parquet"
    second = tmp_path / "second.parquet"
    ring = (
        (51.45, 25.25),
        (51.55, 25.25),
        (51.55, 25.35),
        (51.45, 25.35),
        (51.45, 25.25),
    )
    write_buildings(first, [building_row("SYN-B-1", ring)])
    write_buildings(second, [building_row("SYN-B-2", ring)])
    found = build_places(
        places,
        arabic_tag="ar",
        boundary=_BOX,
        grid=_grid((25.3, 51.5)),
        attribution=_ATTR,
        places_receipt=receipt_for(places),
        buildings_paths=(first, second),
        buildings_receipts=(
            receipt_for(first, "bldg_ovt"),
            receipt_for(second, "bldg_ovt"),
        ),
        zones={"69": _BOX},
        area_provider=_Walk(),
        candidates=(
            {
                "place_key": "SYN-CAND",
                "record_key": "SYN-B-2",
                "use": "commercial",
                "source_id": "bldg_ovt",
            },
        ),
    )
    assert found.flagship is not None
    assert found.flagship.body["candidates"][0]["candidate_key"] == "SYN-CAND"

    again = tmp_path / "again.parquet"
    write_buildings(again, [building_row("SYN-B-1", ring)])
    with pytest.raises(PlacesError, match="building_duplicate"):
        build_places(
            places,
            arabic_tag="ar",
            boundary=_BOX,
            grid=_grid((25.3, 51.5)),
            attribution=_ATTR,
            places_receipt=receipt_for(places),
            buildings_paths=(first, again),
            buildings_receipts=(
                receipt_for(first, "bldg_ovt"),
                receipt_for(again, "bldg_ovt"),
            ),
        )


class _Walk:
    def area(
        self,
        point_key: str,
        point: ReviewedPoint,
        mode: AreaMode,
        cutoff: AreaCutoff,
    ) -> AreaResult:
        del point_key, point, mode, cutoff
        return AreaResult(_BOX.wkb, "stand-in.v0", "a" * 64, "b" * 64, "none", True)


def test_confidence_name_and_category_are_left_out(tmp_path: Path) -> None:
    """Out-of-range confidence, a blank name and a null category do not fail the build."""
    path = tmp_path / "places.parquet"
    write_places(
        path,
        [
            place_row(place_id="SYN-P-LO", confidence=-0.0001),
            place_row(place_id="SYN-P-HI", confidence=1.0001),
            place_row(place_id="SYN-P-POS", confidence=float("inf")),
            place_row(place_id="SYN-P-NEG", confidence=float("-inf")),
            place_row(place_id="SYN-P-NAN", confidence=float("nan")),
            place_row(
                place_id="SYN-P-ZERO",
                confidence=0,
                names={"primary": "SYN Zero", "common": {}},
            ),
            place_row(
                place_id="SYN-P-ONE",
                confidence=1,
                names={"primary": "SYN One", "common": {}},
            ),
            place_row(place_id="SYN-P-BLANK", names={"primary": "   ", "common": {}}),
            place_row(place_id="SYN-P-CAT", basic_category=None),
            place_row(place_id="SYN-P-SPACE", basic_category="   "),
        ],
    )
    result = build_places(
        path,
        arabic_tag="ar",
        boundary=_BOX,
        grid=_grid((25.3, 51.5)),
        attribution=_ATTR,
        places_receipt=receipt_for(path),
    )
    assert result.excluded["confidence_range"] == 5
    assert result.excluded["name_missing"] == 1
    assert result.excluded["category_missing"] == 2
    assert {place.place_id for place in result.places} == {"SYN-P-ZERO", "SYN-P-ONE"}
    from decimal import Decimal

    from eii_custodian.publicdata.places.read import _confidence

    assert _confidence(Decimal("Infinity"))[1] == "range"
    assert _confidence(Decimal("NaN"))[1] == "range"


def test_range_is_checked_before_rounding(tmp_path: Path) -> None:
    """A source just outside 0 to 1 is left out before four-place rounding."""
    path = tmp_path / "places.parquet"
    write_places(
        path,
        [
            place_row(
                place_id="SYN-P-HI",
                confidence=1.00001,
                names={"primary": "SYN High", "common": {}},
            ),
            place_row(
                place_id="SYN-P-LO",
                confidence=-0.00001,
                names={"primary": "SYN Low", "common": {}},
            ),
            place_row(
                place_id="SYN-P-ZERO",
                confidence=0.0,
                names={"primary": "SYN Zero", "common": {}},
            ),
            place_row(
                place_id="SYN-P-ONE",
                confidence=1.0,
                names={"primary": "SYN One", "common": {}},
            ),
        ],
    )
    result = build_places(
        path,
        arabic_tag="ar",
        boundary=_BOX,
        grid=_grid((25.3, 51.5)),
        attribution=_ATTR,
        places_receipt=receipt_for(path),
    )
    assert result.excluded["confidence_range"] == 2
    assert {place.place_id for place in result.places} == {"SYN-P-ZERO", "SYN-P-ONE"}
    from eii_custodian.publicdata.places.read import _confidence

    assert _confidence(Decimal("1.00001"))[1] == "range"
    assert _confidence(Decimal("-0.00001"))[1] == "range"
    assert _confidence(Decimal("1"))[1] == "ok"
    assert _confidence(Decimal("0"))[1] == "ok"
    assert str(_confidence(-0.0)[0]) == "0.0000"


def test_eight_digit_source_identifier_is_kept(tmp_path: Path) -> None:
    """A public identifier is kept. The digit run is built from two parts."""
    left = "2468"
    right = "1357"
    place_id = "SYN-" + left + right
    assert len(left + right) == 8
    path = tmp_path / "places.parquet"
    write_places(path, [place_row(place_id=place_id)])
    result = build_places(
        path,
        arabic_tag="ar",
        boundary=_BOX,
        grid=_grid((25.3, 51.5)),
        attribution=_ATTR,
        places_receipt=receipt_for(path),
    )
    assert result.places[0].place_id == place_id


def test_census_input_carries_lineage_or_stays_pending(tmp_path: Path) -> None:
    """A bare number is refused. An absent input writes no figure."""
    from eii_custodian.publicdata.places.display import CensusFigure

    path = tmp_path / "places.parquet"
    write_places(path, [place_row(place_id="SYN-P-A")])
    common = {
        "arabic_tag": "ar",
        "boundary": _BOX,
        "grid": _grid((25.3, 51.5)),
        "attribution": _ATTR,
        "places_receipt": receipt_for(path),
    }
    with pytest.raises(PlacesError, match="census_lineage"):
        build_places(path, census=12, **common)
    empty = CensusFigure(
        "est_census", "pub_census_national", "establishments", "2026-11-14", "", 12
    )
    with pytest.raises(PlacesError, match="census_lineage"):
        build_places(path, census=empty, **common)
    pending = build_places(path, **common)
    assert "census_comparison_pending" in pending.report
    assert pending.caveat.census_establishments is None
    full = CensusFigure(
        "est_census",
        "pub_census_national",
        "establishments",
        "2026-11-14",
        "a" * 64,
        12,
    )
    result = build_places(path, census=full, **common)
    assert result.caveat.census_source == "est_census"
    assert result.caveat.census_table == "pub_census_national"
    assert result.caveat.census_indicator == "establishments"
    assert result.caveat.census_retrieval_date == "2026-11-14"
    assert result.caveat.census_digest == "a" * 64
    assert result.caveat.census_establishments == 12
    assert "census_comparison_pending" not in result.report


def test_dataset_token_whitespace_empty_and_missing_cell(tmp_path: Path) -> None:
    """The token is not stripped. An empty token and a missing cell are counted."""
    path = tmp_path / "places.parquet"
    spaced = " SYN-dataset "
    write_places(
        path,
        [
            place_row(
                place_id="SYN-P-SPACE",
                sources=[{"property": "", "dataset": spaced, "license": None}],
            )
        ],
    )
    spaced_result = build_places(
        path,
        arabic_tag="ar",
        boundary=_BOX,
        grid=_grid((25.3, 51.5)),
        attribution=(("SYN-dataset", _LICENCE),),
        places_receipt=receipt_for(path),
    )
    assert spaced_result.excluded["attribution_missing"] == 1
    assert f"attribution token missing: {spaced}" in spaced_result.report
    assert all(place.source_provider != "SYN-dataset" for place in spaced_result.places)

    blank = tmp_path / "blank.parquet"
    write_places(
        blank,
        [
            place_row(
                place_id="SYN-P-EMPTY",
                sources=[{"property": "", "dataset": "", "license": None}],
            ),
            place_row(
                place_id="SYN-P-NONE",
                sources=[{"property": "", "dataset": None, "license": None}],
            ),
        ],
    )
    missing = build_places(
        blank,
        arabic_tag="ar",
        boundary=_BOX,
        grid=_grid((25.3, 51.5)),
        attribution=_ATTR,
        places_receipt=receipt_for(blank),
    )
    assert missing.excluded["source_provider_missing"] == 2
    assert "attribution_missing" not in missing.excluded

    cell = tmp_path / "cell.parquet"
    write_places(cell, [place_row(place_id="SYN-P-A")])
    no_cell = build_places(
        cell,
        arabic_tag="ar",
        boundary=_BOX,
        grid=_grid((0.0, 0.0)),
        attribution=_ATTR,
        places_receipt=receipt_for(cell),
    )
    assert no_cell.excluded["no_cell"] == 1


def test_swapped_axes_and_the_two_controls(tmp_path: Path) -> None:
    """A file that fits the box only when swapped is refused. The controls are read."""
    swapped = tmp_path / "swapped.parquet"
    write_places(swapped, [place_row(place_id="SYN-P-SWAP", lon=25.3, lat=51.5)])
    with pytest.raises(PlacesError, match="axis_swapped"):
        build_places(
            swapped,
            arabic_tag="ar",
            boundary=_BOX,
            grid=_grid((25.3, 51.5)),
            attribution=_ATTR,
            places_receipt=receipt_for(swapped),
        )
    mixed = tmp_path / "mixed.parquet"
    write_places(
        mixed,
        [
            place_row(place_id="SYN-P-IN", lon=51.5, lat=25.3),
            place_row(place_id="SYN-P-FAR", lon=10.0, lat=10.0),
        ],
    )
    mixed_result = build_places(
        mixed,
        arabic_tag="ar",
        boundary=_BOX,
        grid=_grid((25.3, 51.5)),
        attribution=_ATTR,
        places_receipt=receipt_for(mixed),
    )
    assert [place.place_id for place in mixed_result.places] == ["SYN-P-IN"]
    assert mixed_result.excluded["outside_boundary"] == 1
    both = tmp_path / "both.parquet"
    write_places(
        both,
        [
            place_row(place_id="SYN-P-IN", lon=51.5, lat=25.3),
            place_row(place_id="SYN-P-SWAP", lon=25.3, lat=51.5),
        ],
    )
    both_result = build_places(
        both,
        arabic_tag="ar",
        boundary=_BOX,
        grid=_grid((25.3, 51.5)),
        attribution=_ATTR,
        places_receipt=receipt_for(both),
    )
    assert [place.place_id for place in both_result.places] == ["SYN-P-IN"]
    assert both_result.excluded["outside_boundary"] == 1
    from eii_custodian.publicdata.places.read import _in_box

    bounds = (51.4, 25.2, 51.6, 25.4)
    assert _in_box(51.4, 25.3, bounds)
    assert _in_box(51.6, 25.3, bounds)
    assert _in_box(51.5, 25.2, bounds)
    assert _in_box(51.5, 25.4, bounds)
    far = tmp_path / "far.parquet"
    write_places(far, [place_row(place_id="SYN-P-FAR", lon=10.0, lat=10.0)])
    far_result = build_places(
        far,
        arabic_tag="ar",
        boundary=_BOX,
        grid=_grid((10.0, 10.0)),
        attribution=_ATTR,
        places_receipt=receipt_for(far),
    )
    assert far_result.places == ()
    assert far_result.excluded["outside_boundary"] == 1


@pytest.mark.parametrize(
    ("row", "reason"),
    [
        (
            (
                "SYN-ORPHAN",
                "2026-11-14",
                "reviewer",
                "https://syn.example/check",
                "verified_open",
                "tenant_directory",
            ),
            "orphan_place_id",
        ),
        (
            (
                "SYN-P-A",
                "2026-11-14",
                "reviewer",
                "https://syn.example/check",
                "VERIFIED_OPEN",
                "tenant_directory",
            ),
            "unknown_status",
        ),
        (
            (
                "SYN-P-A",
                "2026-11-14",
                "reviewer",
                "https://syn.example/check",
                "verified_open",
                "review_site",
            ),
            "verification_source_refused",
        ),
        (
            (
                "SYN-P-A",
                "2026-11-14",
                "",
                "https://syn.example/check",
                "verified_open",
                "tenant_directory",
            ),
            "missing_role",
        ),
        (
            (
                "SYN-P-A",
                "2026-11-14",
                "   ",
                "https://syn.example/check",
                "verified_open",
                "tenant_directory",
            ),
            "missing_role",
        ),
        (
            (
                "SYN-P-A",
                "not-a-date",
                "reviewer",
                "https://syn.example/check",
                "verified_open",
                "tenant_directory",
            ),
            "bad_check_date",
        ),
    ],
)
def test_in_memory_verification_uses_the_row_checks(
    tmp_path: Path, row: tuple[str, str, str, str, str, str], reason: str
) -> None:
    """In-memory rows pass through the same validator as the loader."""
    from datetime import date

    from eii_custodian.publicdata.places.review import Verification

    path = tmp_path / "places.parquet"
    write_places(path, [place_row(place_id="SYN-P-A")])
    with pytest.raises(PlacesError, match=reason):
        build_places(
            path,
            arabic_tag="ar",
            boundary=_BOX,
            grid=_grid((25.3, 51.5)),
            attribution=_ATTR,
            places_receipt=receipt_for(path),
            verified=(Verification(*row),),
            build_date=date(2026, 11, 14),
        )


def _grid(
    points: tuple[float, float] | list[tuple[float, float]],
) -> list[dict[str, int]]:
    import h3

    if isinstance(points, tuple) and points and isinstance(points[0], float):
        sequence = (points,)
    else:
        sequence = points
    cells = []
    for lat, lon in sequence:
        cells.append({"cell": h3.str_to_int(h3.latlng_to_cell(lat, lon, 9))})
    return cells
