"""Threshold, duplicates, the caveat and the further source."""

from __future__ import annotations

from datetime import date
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
    AreaError,
    AreaMode,
    AreaResult,
    ReviewedPoint,
)
from eii_custodian.publicdata.places.build import build_places
from eii_custodian.publicdata.places.display import (
    ABSENT_CATEGORY,
    CAVEAT_AR,
    CAVEAT_EN,
    CENSUS_SOURCE,
    CONFIDENCE_MIN,
    PubPlace,
    _shown,
    category_result,
    hidden_count,
    inventory_names,
    place_stand_ins,
    resolve_duplicates,
)
from eii_custodian.publicdata.places.review import Verification
from eii_custodian.publicdata.places_fsq.constants import (
    DUPLICATE_WITHIN_M,
    PINNED_RELEASE,
)
from eii_custodian.publicdata.places_fsq.parse import ParsedRow
from eii_custodian.publicdata.places_fsq.policy import distance_m, duplicate_links

_LICENCE = "SYN-LICENCE"
_ATTR = (("syn-source", _LICENCE),)
_BOX = box(51.4, 25.2, 51.6, 25.4)


def test_threshold_shows_seven_tenths_and_hides_the_step_below(tmp_path: Path) -> None:
    """0.7000 is shown. 0.6999 is not. Both stay outside when no area is supplied."""
    path = tmp_path / "places.parquet"
    write_places(
        path,
        [
            place_row(place_id="SYN-P-IN", confidence=0.7, lon=51.50, lat=25.30),
            place_row(
                place_id="SYN-P-OUT",
                confidence=0.6999,
                lon=51.51,
                lat=25.31,
                names={"primary": "SYN Other", "common": {}},
            ),
        ],
    )
    result = build_places(
        path,
        arabic_tag="ar",
        boundary=_BOX,
        grid=_cells((25.30, 51.50), (25.31, 51.51)),
        attribution=_ATTR,
        places_receipt=receipt_for(path),
    )
    assert result.places[0].confidence == CONFIDENCE_MIN
    assert Decimal("0.6999") < CONFIDENCE_MIN
    assert result.shown_ids == frozenset({"SYN-P-IN"})
    assert result.hidden == 1
    assert hidden_count(result.places, result.shown_ids) == 1
    assert result.complete is False


def test_outside_duplicates_keep_the_higher_confidence(tmp_path: Path) -> None:
    """Within 50 m the higher confidence remains and the other id is merged."""
    path = tmp_path / "places.parquet"
    write_places(
        path,
        [
            place_row(place_id="SYN-P-HIGH", confidence=0.9, lon=51.5, lat=25.3),
            place_row(place_id="SYN-P-LOW", confidence=0.8, lon=51.5, lat=25.3),
            place_row(
                place_id="SYN-P-FAR",
                confidence=0.8,
                lon=51.5,
                lat=25.32,
                names={"primary": "SYN Cafe", "common": {}},
            ),
        ],
    )
    result = build_places(
        path,
        arabic_tag="ar",
        boundary=box(51.0, 25.0, 52.0, 26.0),
        grid=_cells((25.3, 51.5), (25.32, 51.5)),
        attribution=_ATTR,
        places_receipt=receipt_for(path),
    )
    by_id = {place.place_id: place for place in result.places}
    assert by_id["SYN-P-HIGH"].merged_ids == "SYN-P-LOW"
    assert "SYN-P-LOW" not in result.shown_ids
    assert "SYN-P-HIGH" in result.shown_ids
    assert "SYN-P-FAR" in result.shown_ids
    assert by_id["SYN-P-FAR"].merged_ids == ""


def test_fifty_metres_is_inclusive() -> None:
    """The kept side of the 50 m step merges. The next stored step does not."""
    inside, outside = _boundary_step()
    high = _place(
        "SYN-P-HIGH", Decimal("0.9000"), Decimal("51.500000"), Decimal("25.300000")
    )
    low = _place("SYN-P-LOW", Decimal("0.8000"), Decimal("51.500000"), inside)
    far = _place("SYN-P-FAR", Decimal("0.8000"), Decimal("51.500000"), outside)
    assert _metres(inside) <= DUPLICATE_WITHIN_M
    assert _metres(outside) > DUPLICATE_WITHIN_M
    merged = resolve_duplicates((high, low), frozenset(), {})
    keeper = next(place for place in merged.places if place.place_id == "SYN-P-HIGH")
    assert keeper.merged_ids == "SYN-P-LOW"
    apart = resolve_duplicates((high, far), frozenset(), {})
    assert all(place.merged_ids == "" for place in apart.places)
    assert apart.unresolved == ()


def test_a_distance_of_exactly_fifty_metres_merges(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The closed boundary keeps the pair. A strict less-than would drop it."""
    monkeypatch.setattr(
        "eii_custodian.publicdata.places.display.distance_m",
        lambda *_args: float(DUPLICATE_WITHIN_M),
    )
    high = _place(
        "SYN-P-HIGH", Decimal("0.9000"), Decimal("51.500000"), Decimal("25.300000")
    )
    low = _place(
        "SYN-P-LOW", Decimal("0.8000"), Decimal("51.500100"), Decimal("25.300000")
    )
    outcome = resolve_duplicates((high, low), frozenset(), {})
    keeper = next(place for place in outcome.places if place.place_id == "SYN-P-HIGH")
    assert keeper.merged_ids == "SYN-P-LOW"


def test_equal_confidence_stays_unresolved() -> None:
    """An equal pair is kept as two rows and listed."""
    high = _place("SYN-P-A", Decimal("0.8000"), 51.50, 25.30)
    same = _place("SYN-P-B", Decimal("0.8000"), 51.50, 25.30)
    outcome = resolve_duplicates((high, same), frozenset(), {})
    assert outcome.unresolved == (("SYN-P-A", "SYN-P-B"),)
    assert outcome.shown == frozenset({"SYN-P-A", "SYN-P-B"})
    assert all(place.merged_ids == "" for place in outcome.places)


def test_inside_status_overrides_confidence_and_only_a_review_merges() -> None:
    """verified_open is shown. The other three are hidden. A duplicate status merges."""
    low = _place(
        "SYN-P-LOW", Decimal("0.1000"), 51.50, 25.30, "syn_restaurant", "restaurant"
    )
    closed = _place(
        "SYN-P-CLOSED", Decimal("0.9000"), 51.51, 25.31, "syn_other", "other"
    )
    missing = _place("SYN-P-MISS", Decimal("0.9000"), 51.52, 25.32)
    duplicate = _place("SYN-P-DUP", Decimal("0.9000"), 51.50, 25.30)
    inside = frozenset(place.place_id for place in (low, closed, missing, duplicate))
    status = {
        "SYN-P-LOW": "verified_open",
        "SYN-P-CLOSED": "closed_or_moved",
        "SYN-P-MISS": "not_found",
        "SYN-P-DUP": "duplicate",
    }
    outcome = resolve_duplicates((low, closed, missing, duplicate), inside, status)
    assert outcome.shown == frozenset({"SYN-P-LOW"})
    keeper = next(place for place in outcome.places if place.place_id == "SYN-P-LOW")
    assert keeper.merged_ids == "SYN-P-DUP"
    assert hidden_count(outcome.places, outcome.shown) == 3
    absent = category_result(outcome.places, "syn_absent", outcome.shown)
    assert absent.found is False
    assert absent.shown is None
    assert absent.text == ABSENT_CATEGORY
    present = category_result(outcome.places, "syn_restaurant", outcome.shown)
    assert present.found is True
    assert present.shown == 1


def test_caveat_names_the_census_and_the_arabic_is_pending() -> None:
    """The standing note and the census reference travel with every result."""
    from eii_custodian.publicdata.places.display import open_listings_caveat

    caveat = open_listings_caveat()
    assert caveat.text_en == CAVEAT_EN
    assert caveat.text_ar == CAVEAT_AR
    assert caveat.arabic_review == "pending native review"
    assert caveat.census_source == ""
    assert caveat.census_establishments is None
    assert CENSUS_SOURCE == "est_census"


def test_further_source_duplicate_is_not_shown_and_the_release_is_carried(
    tmp_path: Path,
) -> None:
    """A copy that matches pub_place is dropped. A distinct copy keeps its release date."""
    path = tmp_path / "places.parquet"
    write_places(path, [place_row(place_id="SYN-P-A")])
    rows = (
        _fsq("SYN-FSQ-SAME", "SYN Cafe", Decimal("51.500000"), Decimal("25.300000")),
        _fsq("SYN-FSQ-NEW", "SYN Other", Decimal("51.510000"), Decimal("25.310000")),
    )
    result = build_places(
        path,
        arabic_tag="ar",
        boundary=_BOX,
        grid=_cells((25.3, 51.5), (25.31, 51.51)),
        attribution=_ATTR,
        places_receipt=receipt_for(path),
        fsq_rows=rows,
        fsq_release=PINNED_RELEASE,
        fsq_licence=_LICENCE,
    )
    assert [point.fsq_place_id for point in result.fsq_shown] == ["SYN-FSQ-NEW"]
    assert result.fsq_shown[0].source_release == PINNED_RELEASE
    assert result.fsq_shown[0].licence == _LICENCE
    assert result.fsq_shown[0].caveat_key == result.caveat.key
    assert "fsq_duplicate_not_shown: 1" in result.report
    assert "SYN Cafe" in inventory_names(result.places)
    assert place_stand_ins(result.places, frozenset())[0].in_showcase is False


def test_further_source_without_a_licence_is_refused(tmp_path: Path) -> None:
    """Further-source rows with a release and no licence refuse the build."""
    path = tmp_path / "places.parquet"
    write_places(path, [place_row(place_id="SYN-P-A")])
    rows = (
        _fsq("SYN-FSQ-NEW", "SYN Other", Decimal("51.510000"), Decimal("25.310000")),
    )
    with pytest.raises(PlacesError, match="fsq_licence_missing"):
        build_places(
            path,
            arabic_tag="ar",
            boundary=_BOX,
            grid=_cells((25.3, 51.5), (25.31, 51.51)),
            attribution=_ATTR,
            places_receipt=receipt_for(path),
            fsq_rows=rows,
            fsq_release=PINNED_RELEASE,
        )
    with pytest.raises(PlacesError, match="fsq_licence_missing"):
        build_places(
            path,
            arabic_tag="ar",
            boundary=_BOX,
            grid=_cells((25.3, 51.5), (25.31, 51.51)),
            attribution=_ATTR,
            places_receipt=receipt_for(path),
            fsq_rows=rows,
            fsq_release=PINNED_RELEASE,
            fsq_licence="   ",
        )


def test_complete_needs_a_real_area_and_the_further_release(tmp_path: Path) -> None:
    """complete is true only when the area is real, the release is set and no pair is open."""
    path = tmp_path / "places.parquet"
    write_places(path, [place_row(place_id="SYN-P-A")])
    result = build_places(
        path,
        arabic_tag="ar",
        boundary=_BOX,
        grid=_cells((25.3, 51.5)),
        attribution=_ATTR,
        places_receipt=receipt_for(path),
        area_provider=_Provider(
            {name: box(51.4, 25.2, 51.6, 25.4).wkb for name in ("walk_10",)},
            stand_in=False,
        ),
        showcase_areas=(
            {
                "place_key": "SYN-LAND",
                "mode": "walk",
                "cutoff_minutes": 10,
                "source_id": "places_ovt",
                "record_key": "SYN-P-A",
            },
        ),
        fsq_rows=(
            _fsq(
                "SYN-FSQ-NEW", "SYN Other", Decimal("51.510000"), Decimal("25.310000")
            ),
        ),
        fsq_release=PINNED_RELEASE,
        fsq_licence=_LICENCE,
    )
    assert result.complete is True
    assert result.unresolved == ()


def test_showcase_override_uses_the_provider_polygon(tmp_path: Path) -> None:
    """Inside the returned walk area, verified_open is shown below the threshold."""
    path = tmp_path / "places.parquet"
    write_places(path, [place_row(place_id="SYN-P-A", confidence=0.2)])
    polygon = box(51.4, 25.2, 51.6, 25.4).wkb
    result = build_places(
        path,
        arabic_tag="ar",
        boundary=_BOX,
        grid=_cells((25.3, 51.5)),
        attribution=_ATTR,
        places_receipt=receipt_for(path),
        area_provider=_Provider({"walk_10": polygon}),
        showcase_areas=(
            {
                "place_key": "SYN-LAND",
                "mode": "walk",
                "cutoff_minutes": 10,
                "source_id": "places_ovt",
                "record_key": "SYN-P-A",
            },
        ),
        verified=(
            Verification(
                "SYN-P-A",
                "2026-01-02",
                "reviewer",
                "https://example.invalid/syn",
                "verified_open",
                "tenant_directory",
            ),
        ),
        build_date=date(2026, 11, 14),
    )
    assert result.shown_ids == frozenset({"SYN-P-A"})
    assert result.complete is False


class _Provider:
    def __init__(self, polygons: dict[str, bytes], stand_in: bool = True) -> None:
        self.polygons = polygons
        self.stand_in = stand_in

    def area(
        self,
        point_key: str,
        point: ReviewedPoint,
        mode: AreaMode,
        cutoff: AreaCutoff,
    ) -> AreaResult:
        del point_key, point
        name = f"{mode.value}_{cutoff.value}"
        return AreaResult(
            self.polygons[name],
            "stand-in.v0",
            "a" * 64,
            "b" * 64,
            "none",
            self.stand_in,
        )


def test_area_failure_shows_nothing_by_confidence(tmp_path: Path) -> None:
    """An area error or a missing landmark hides every confidence-only place."""
    path = tmp_path / "places.parquet"
    write_places(
        path,
        [
            place_row(place_id="SYN-P-LAND", confidence=0.9, lon=51.50, lat=25.30),
            place_row(
                place_id="SYN-P-NEAR",
                confidence=0.9,
                lon=51.51,
                lat=25.31,
                names={"primary": "SYN Other", "common": {}},
            ),
        ],
    )
    common = {
        "arabic_tag": "ar",
        "boundary": _BOX,
        "grid": _cells((25.30, 51.50), (25.31, 51.51)),
        "attribution": _ATTR,
        "places_receipt": receipt_for(path),
        "fsq_rows": (),
        "fsq_release": "2025-01-10",
        "fsq_licence": _LICENCE,
    }
    failed = build_places(
        path,
        area_provider=_Boom(),
        showcase_areas=(_area("SYN-P-LAND"),),
        **common,
    )
    assert failed.shown_ids == frozenset()
    assert failed.complete is False
    assert "showcase area error: engine_failed" in failed.report
    missing = build_places(
        path,
        area_provider=_Provider({"walk_10": box(0, 0, 0.1, 0.1).wkb}, stand_in=False),
        showcase_areas=(_area("SYN-ABSENT"),),
        **common,
    )
    assert missing.shown_ids == frozenset()
    assert missing.complete is False
    assert "showcase landmark missing" in missing.report
    shown = build_places(
        path,
        area_provider=_Provider({"walk_10": box(0, 0, 0.1, 0.1).wkb}, stand_in=False),
        showcase_areas=(_area("SYN-P-LAND"),),
        **common,
    )
    assert shown.shown_ids == frozenset({"SYN-P-LAND", "SYN-P-NEAR"})


def test_stored_decimal_is_what_the_threshold_reads() -> None:
    """Half to even on the source double. 0.7000 is shown and 0.6999 is not."""
    from eii_custodian.publicdata.places.read import stored_confidence

    shown = stored_confidence(0.69995)
    hidden = stored_confidence(0.69994)
    assert shown == Decimal("0.7000")
    assert hidden == Decimal("0.6999")
    assert stored_confidence(0.69985) == Decimal("0.6998")
    assert stored_confidence(0.7) == Decimal("0.7000")
    assert _shown(_place("SYN-P-SHOW", shown, 51.50, 25.30), frozenset(), {}, {})
    assert not _shown(_place("SYN-P-HIDE", hidden, 51.51, 25.31), frozenset(), {}, {})


def test_case_and_arabic_names_merge_punctuation_does_not() -> None:
    """Outside, case and white space merge. Punctuation does not. Arabic still does."""
    high = _place("SYN-P-HIGH", Decimal("0.9000"), 51.50, 25.30, name="SYN Cafe")
    low = _place("SYN-P-LOW", Decimal("0.8000"), 51.50, 25.30, name="syn cafe!")
    outcome = resolve_duplicates((high, low), frozenset(), {})
    assert outcome.shown == frozenset({"SYN-P-HIGH", "SYN-P-LOW"})
    assert all(place.merged_ids == "" for place in outcome.places)
    spaced_high = _place(
        "SYN-P-HIGH", Decimal("0.9000"), 51.50, 25.30, name="SYN  Cafe "
    )
    spaced_low = _place("SYN-P-LOW", Decimal("0.8000"), 51.50, 25.30, name="syn cafe")
    spaced = resolve_duplicates((spaced_high, spaced_low), frozenset(), {})
    keeper = next(place for place in spaced.places if place.place_id == "SYN-P-HIGH")
    assert keeper.merged_ids == "SYN-P-LOW"
    arabic_high = _place(
        "SYN-P-A",
        Decimal("0.9000"),
        51.50,
        25.30,
        name="SYN Cafe",
        name_ar="مقهى تجريبي",
    )
    arabic_low = _place(
        "SYN-P-B",
        Decimal("0.8000"),
        51.50,
        25.30,
        name="SYN Other",
        name_ar="مقهى تجريبي",
    )
    arabic = resolve_duplicates((arabic_high, arabic_low), frozenset(), {})
    keeper = next(place for place in arabic.places if place.place_id == "SYN-P-A")
    assert keeper.merged_ids == "SYN-P-B"


def test_both_duplicate_paths_use_one_name_rule() -> None:
    """Punctuation links on neither path. Case and white space link on both."""
    punct_place = _place("SYN-P-HIGH", Decimal("0.9000"), 51.50, 25.30, name="SYN Cafe")
    punct_other = _place("SYN-P-LOW", Decimal("0.8000"), 51.50, 25.30, name="syn cafe!")
    punct = resolve_duplicates((punct_place, punct_other), frozenset(), {})
    assert punct.shown == frozenset({"SYN-P-HIGH", "SYN-P-LOW"})
    assert all(place.merged_ids == "" for place in punct.places)
    punct_links = duplicate_links(
        [_fsq("SYN-FSQ-LOW", "syn cafe!", Decimal("51.500000"), Decimal("25.300000"))],
        place_stand_ins((punct_place,), frozenset()),
    )
    assert punct_links == ()
    space_place = _place(
        "SYN-P-HIGH", Decimal("0.9000"), 51.50, 25.30, name="SYN  Cafe "
    )
    space_other = _place("SYN-P-LOW", Decimal("0.8000"), 51.50, 25.30, name="syn cafe")
    space = resolve_duplicates((space_place, space_other), frozenset(), {})
    space_keeper = next(
        place for place in space.places if place.place_id == "SYN-P-HIGH"
    )
    assert space_keeper.merged_ids == "SYN-P-LOW"
    space_links = duplicate_links(
        [_fsq("SYN-FSQ-LOW", "syn cafe", Decimal("51.500000"), Decimal("25.300000"))],
        place_stand_ins((space_place,), frozenset()),
    )
    assert len(space_links) == 1
    assert space_links[0].fsq_place_id == "SYN-FSQ-LOW"
    assert space_links[0].place_id == "SYN-P-HIGH"
    assert space_links[0].in_showcase is False
    assert space_links[0].distance_m == 0.0


def test_outside_duplicate_status_does_not_merge() -> None:
    """A reviewed duplicate outside every showcase area stays unresolved."""
    left = _place("SYN-P-A", Decimal("0.8000"), 51.50, 25.30)
    right = _place("SYN-P-B", Decimal("0.8000"), 51.50, 25.30)
    outcome = resolve_duplicates((left, right), frozenset(), {"SYN-P-A": "duplicate"})
    assert outcome.shown == frozenset({"SYN-P-A", "SYN-P-B"})
    assert all(place.merged_ids == "" for place in outcome.places)
    assert outcome.unresolved == (("SYN-P-A", "SYN-P-B"),)


def test_further_source_outside_a_bent_boundary_is_absent(tmp_path: Path) -> None:
    """A point inside the frame box and outside the boundary is not shown."""
    from shapely.geometry import Polygon

    path = tmp_path / "places.parquet"
    write_places(path, [place_row(place_id="SYN-P-A", lon=51.45, lat=25.25)])
    boundary = Polygon([(51.4, 25.2), (51.6, 25.2), (51.4, 25.4)])
    result = build_places(
        path,
        arabic_tag="ar",
        boundary=boundary,
        grid=_cells((25.25, 51.45)),
        attribution=_ATTR,
        places_receipt=receipt_for(path),
        fsq_rows=(
            _fsq(
                "SYN-FSQ-OUT", "SYN Other", Decimal("51.550000"), Decimal("25.350000")
            ),
        ),
        fsq_release=PINNED_RELEASE,
        fsq_licence=_LICENCE,
    )
    assert result.fsq_shown == ()


def _area(record_key: str) -> dict[str, object]:
    return {
        "place_key": "SYN-LAND",
        "mode": "walk",
        "cutoff_minutes": 10,
        "source_id": "places_ovt",
        "record_key": record_key,
    }


class _Boom:
    def area(
        self,
        point_key: str,
        point: ReviewedPoint,
        mode: AreaMode,
        cutoff: AreaCutoff,
    ) -> AreaResult:
        del point_key, point, mode, cutoff
        raise AreaError("engine_failed")


def _place(
    place_id: str,
    confidence: Decimal,
    lon: float | Decimal,
    lat: float | Decimal,
    category: str = "syn_other",
    category_class: str = "other",
    name: str = "SYN Cafe",
    name_ar: str | None = None,
) -> PubPlace:
    return PubPlace(
        place_id,
        name,
        name_ar,
        category,
        category_class,
        Decimal(str(lon)).quantize(Decimal("0.000001")),
        Decimal(str(lat)).quantize(Decimal("0.000001")),
        1,
        "2026-10-21.0",
        "syn-source",
        _LICENCE,
        confidence,
        "",
    )


def _fsq(fsq_id: str, name: str, lon: Decimal, lat: Decimal) -> ParsedRow:
    return ParsedRow(
        fsq_id,
        name,
        None,
        "",
        "",
        lon,
        lat,
        "QA",
        None,
        None,
        None,
    )


def _cells(*points: tuple[float, float]) -> list[dict[str, int]]:
    import h3

    return [
        {"cell": h3.str_to_int(h3.latlng_to_cell(lat, lon, 9))} for lat, lon in points
    ]


def _boundary_step() -> tuple[Decimal, Decimal]:
    step = Decimal("0.000001")
    lat = Decimal("25.300000")
    while _metres(lat) <= DUPLICATE_WITHIN_M:
        lat += step
    return lat - step, lat


def _metres(lat: Decimal) -> float:
    return distance_m(51.5, 25.3, 51.5, float(lat))
