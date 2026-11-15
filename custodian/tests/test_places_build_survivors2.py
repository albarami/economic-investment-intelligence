"""The build mutants that survived the first campaign, second file. All invented."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from custodian.tests.fixtures.places.invented import (
    building_row,
    place_row,
    receipt_for,
    write_buildings,
    write_places,
)
from shapely.geometry import Polygon, box
from shapely.geometry.base import BaseGeometry

from eii_custodian.publicdata.places import PlacesError
from eii_custodian.publicdata.places.areas import (
    AreaCutoff,
    AreaError,
    AreaMode,
    AreaResult,
    ReviewedPoint,
)
from eii_custodian.publicdata.places.build import (
    FsqShown,
    _complete,
    _flagship,
    _fsq,
    _inside,
    build_places,
)
from eii_custodian.publicdata.places.display import DuplicateOutcome, PubPlace
from eii_custodian.publicdata.places_fsq.parse import ParsedRow

_LICENCE = "SYN-LICENCE"
_ATTR = (("syn-source", _LICENCE),)
_BOX = box(51.4, 25.2, 51.6, 25.4)
# The triangle's own bounds are the box, so a point can be in the frame and
# still outside the boundary: 51.55 east, 25.35 north is such a point.
_TRIANGLE = Polygon(((51.4, 25.2), (51.6, 25.2), (51.4, 25.4)))
_RING = (
    (51.45, 25.25),
    (51.55, 25.25),
    (51.55, 25.35),
    (51.45, 25.35),
    (51.45, 25.25),
)
_ZONE_69 = box(51.40, 25.20, 51.60, 25.40)
_ZONE_70 = box(51.90, 25.20, 52.00, 25.30)
_CELL = 618460705430700031
_RELEASE = "2026-01-10"
_CAVEAT_KEY = "open_listings_incomplete"
_PENDING = ("census_comparison_pending",)


def _refusal(call: Callable[[], object], whole: str) -> None:
    """Fail unless the call refuses with exactly this whole message."""
    with pytest.raises(PlacesError) as caught:
        call()
    assert str(caught.value) == whole
    assert caught.value.reason == whole


def _grid(points: Sequence[tuple[float, float]]) -> list[dict[str, int]]:
    """The ownership grid of the invented points, at resolution 9."""
    import h3

    return [
        {"cell": h3.str_to_int(h3.latlng_to_cell(lat, lon, 9))} for lat, lon in points
    ]


def _pub_place(**overrides: Any) -> PubPlace:
    """One invented pub_place row."""
    fields: dict[str, Any] = {
        "place_id": "SYN-P-A",
        "name": "SYN Cafe",
        "name_ar": None,
        "category": "syn_restaurant",
        "category_class": "restaurant",
        "lon": Decimal("51.500000"),
        "lat": Decimal("25.300000"),
        "cell": _CELL,
        "source_release": "2026-10-21.0",
        "source_provider": "syn-source",
        "licence": _LICENCE,
        "confidence": Decimal("0.8000"),
        "merged_ids": "",
    }
    fields.update(overrides)
    return PubPlace(**fields)


def _fsq_row(fsq_place_id: str, name: str, lon: str, lat: str) -> ParsedRow:
    """One invented further-source row with no closing date."""
    return ParsedRow(
        fsq_place_id,
        name,
        None,
        "syn_category",
        name,
        Decimal(lon),
        Decimal(lat),
        "QA",
        None,
        None,
        None,
    )


class _Areas:
    """An area provider that records each call and returns one invented polygon."""

    def __init__(
        self,
        polygon: BaseGeometry = _BOX,
        stand_in: bool = False,
        fails: Sequence[str] = (),
    ) -> None:
        self.polygon = polygon
        self.stand_in = stand_in
        self.fails = frozenset(fails)
        self.calls: list[tuple[str, ReviewedPoint, AreaMode, AreaCutoff]] = []

    def area(
        self,
        point_key: str,
        point: ReviewedPoint,
        mode: AreaMode,
        cutoff: AreaCutoff,
    ) -> AreaResult:
        self.calls.append((point_key, point, mode, cutoff))
        if point_key in self.fails:
            raise AreaError("engine_failed")
        return AreaResult(
            self.polygon.wkb, "stand-in.v0", "a" * 64, "b" * 64, "none", self.stand_in
        )


def _build(path: Path, **overrides: Any) -> Any:
    """One build of the invented places file with the frame's fixed inputs."""
    arguments: dict[str, Any] = {
        "arabic_tag": "ar",
        "boundary": _BOX,
        "grid": _grid(((25.3, 51.5),)),
        "attribution": _ATTR,
        "places_receipt": receipt_for(path),
    }
    arguments.update(overrides)
    return build_places(path, **arguments)


def test_the_showcase_walk_asks_with_the_place_key_and_the_point(
    tmp_path: Path,
) -> None:
    """The walk is asked for the spec's own key and the landmark's own point."""
    path = tmp_path / "places.parquet"
    write_places(path, [place_row(place_id="SYN-P-A")])
    provider = _Areas(box(51.45, 25.25, 51.46, 25.26))
    result = _build(
        path,
        area_provider=provider,
        showcase_areas=({"record_key": "SYN-P-A", "place_key": "SYN-KEY-1"},),
    )
    assert provider.calls == [
        (
            "SYN-KEY-1",
            ReviewedPoint(51.5, 25.3),
            AreaMode.WALK,
            AreaCutoff.MINUTES_10,
        )
    ]
    assert result.shown_ids == frozenset({"SYN-P-A"})


def test_a_missing_landmark_does_not_stop_the_walk_over_the_areas(
    tmp_path: Path,
) -> None:
    """A spec with no landmark is noted, and the spec after it is still asked."""
    path = tmp_path / "places.parquet"
    write_places(path, [place_row(place_id="SYN-P-A")])
    provider = _Areas(box(51.45, 25.25, 51.46, 25.26), fails=("SYN-KEY-1",))
    result = _build(
        path,
        area_provider=provider,
        showcase_areas=(
            {"record_key": "SYN-UNKNOWN", "place_key": "SYN-KEY-X"},
            {"record_key": "SYN-P-A", "place_key": "SYN-KEY-1"},
        ),
    )
    assert result.report == (
        *_PENDING,
        "showcase landmark missing",
        "showcase area error: engine_failed",
        "fsq_pending",
    )
    assert [call[0] for call in provider.calls] == ["SYN-KEY-1"]


def test_a_blocked_area_walk_still_carries_the_stand_in() -> None:
    """An area error blocks the build and the later stand-in is still reported."""
    places = (
        _pub_place(),
        _pub_place(
            place_id="SYN-P-B", lon=Decimal("51.550000"), lat=Decimal("25.350000")
        ),
    )
    provider = _Areas(box(51.45, 25.25, 51.46, 25.26), True, ("SYN-KEY-1",))
    found = _inside(
        (
            {"record_key": "SYN-P-A", "place_key": "SYN-KEY-1"},
            {"record_key": "SYN-P-A", "place_key": "SYN-KEY-2"},
        ),
        places,
        provider,
        _BOX,
    )
    assert found == (
        frozenset({"SYN-P-A", "SYN-P-B"}),
        ("showcase area error: engine_failed",),
        True,
        True,
    )


def test_the_area_walk_starts_with_no_stand_in_and_no_block() -> None:
    """A walk over one good spec reports neither a stand-in nor a block."""
    places = (
        _pub_place(),
        _pub_place(
            place_id="SYN-P-B", lon=Decimal("51.550000"), lat=Decimal("25.350000")
        ),
    )
    found = _inside(
        ({"record_key": "SYN-P-A", "place_key": "SYN-KEY-1"},),
        places,
        _Areas(_BOX),
        _BOX,
    )
    assert found == (frozenset({"SYN-P-A", "SYN-P-B"}), (), False, False)


def test_the_early_area_return_holds_no_stand_in_and_no_block() -> None:
    """No provider and no spec both give the same empty, unblocked answer."""
    places = (_pub_place(),)
    assert _inside((), (), None, _BOX) == (frozenset(), (), False, False)
    assert _inside((), places, _Areas(_BOX), _BOX) == (frozenset(), (), False, False)


def test_a_showcase_spec_with_no_provider_reports_no_landmark_note(
    tmp_path: Path,
) -> None:
    """Without a provider the specs are not read, so no landmark is missed."""
    path = tmp_path / "places.parquet"
    write_places(path, [place_row(place_id="SYN-P-A")])
    result = _build(
        path,
        showcase_areas=({"record_key": "SYN-UNKNOWN", "place_key": "SYN-KEY-X"},),
    )
    assert result.report == (*_PENDING, "fsq_pending", "showcase_areas_pending")


def test_a_stand_in_area_leaves_the_build_incomplete(tmp_path: Path) -> None:
    """A stand-in walk is not evidence, so the build is not complete."""
    path = tmp_path / "places.parquet"
    write_places(path, [place_row(place_id="SYN-P-A")])
    result = _build(
        path,
        area_provider=_Areas(box(51.45, 25.25, 51.46, 25.26), True),
        showcase_areas=({"record_key": "SYN-P-A", "place_key": "SYN-KEY-1"},),
        fsq_rows=(_fsq_row("SYN-F-A", "SYN Kiosk", "51.550000", "25.350000"),),
        fsq_release=_RELEASE,
        fsq_licence=_LICENCE,
    )
    assert result.complete is False
    assert result.shown_ids == frozenset({"SYN-P-A"})


def test_a_missing_release_leaves_the_build_incomplete(tmp_path: Path) -> None:
    """Rows without their release are not shown and the build is not complete."""
    path = tmp_path / "places.parquet"
    write_places(path, [place_row(place_id="SYN-P-A")])
    result = _build(
        path,
        area_provider=_Areas(box(51.45, 25.25, 51.46, 25.26)),
        showcase_areas=({"record_key": "SYN-P-A", "place_key": "SYN-KEY-1"},),
        fsq_rows=(_fsq_row("SYN-F-A", "SYN Kiosk", "51.550000", "25.350000"),),
        fsq_licence=_LICENCE,
    )
    assert result.complete is False
    assert result.fsq_shown == ()
    assert result.report == (*_PENDING, "fsq_release_missing")


def test_the_further_source_is_pending_without_rows(tmp_path: Path) -> None:
    """No rows at all is one pending note and nothing shown."""
    path = tmp_path / "places.parquet"
    write_places(path, [place_row(place_id="SYN-P-A")])
    result = _build(path)
    assert result.fsq_shown == ()
    assert result.report == (*_PENDING, "fsq_pending", "showcase_areas_pending")


def test_a_blank_further_source_licence_refuses_with_its_own_whole_reason(
    tmp_path: Path,
) -> None:
    """Rows with a release but no licence refuse with the whole reason."""
    path = tmp_path / "places.parquet"
    write_places(path, [place_row(place_id="SYN-P-A")])
    _refusal(
        lambda: _build(
            path,
            fsq_rows=(_fsq_row("SYN-F-A", "SYN Kiosk", "51.550000", "25.350000"),),
            fsq_release=_RELEASE,
            fsq_licence="   ",
        ),
        "fsq_licence_missing",
    )


def test_an_outside_further_source_row_does_not_stop_the_walk(
    tmp_path: Path,
) -> None:
    """A row outside the boundary is dropped and the row after it is shown."""
    path = tmp_path / "places.parquet"
    write_places(path, [place_row(place_id="SYN-P-A", lon=51.45, lat=25.25)])
    result = _build(
        path,
        boundary=_TRIANGLE,
        grid=_grid(((25.25, 51.45),)),
        fsq_rows=(
            _fsq_row("SYN-F-A", "SYN Kiosk", "51.550000", "25.350000"),
            _fsq_row("SYN-F-B", "SYN Booth", "51.450000", "25.250000"),
        ),
        fsq_release=_RELEASE,
        fsq_licence=_LICENCE,
    )
    assert [row.fsq_place_id for row in result.fsq_shown] == ["SYN-F-B"]
    assert result.report == (
        *_PENDING,
        "fsq_duplicate_not_shown: 0",
        "showcase_areas_pending",
    )


def test_a_shown_further_source_row_carries_its_whole_lineage(tmp_path: Path) -> None:
    """One shown row carries its name, point, licence, release and source."""
    path = tmp_path / "places.parquet"
    write_places(path, [place_row(place_id="SYN-P-A")])
    result = _build(
        path,
        fsq_rows=(_fsq_row("SYN-F-A", "SYN Kiosk", "51.550000", "25.350000"),),
        fsq_release=_RELEASE,
        fsq_licence=_LICENCE,
    )
    assert result.fsq_shown == (
        FsqShown(
            "SYN-F-A",
            "SYN Kiosk",
            Decimal("51.550000"),
            Decimal("25.350000"),
            _LICENCE,
            _RELEASE,
            "places_fsq",
            _CAVEAT_KEY,
        ),
    )
    assert result.report == (
        *_PENDING,
        "fsq_duplicate_not_shown: 0",
        "showcase_areas_pending",
    )


def test_the_flagship_check_carries_its_whole_inputs(tmp_path: Path) -> None:
    """The check body holds the use, the pin, the counted rows and the zones."""
    path = tmp_path / "places.parquet"
    write_places(
        path,
        [
            place_row(place_id="SYN-P-A", basic_category="syn_restaurant"),
            place_row(
                place_id="SYN-P-B",
                basic_category="syn_kiosk",
                names={"primary": "SYN Kiosk", "common": {}},
                lon=51.55,
                lat=25.35,
            ),
        ],
    )
    buildings = tmp_path / "buildings.parquet"
    write_buildings(buildings, [building_row("SYN-B-A", _RING)])
    verified = tmp_path / "verified.csv"
    verified.write_text(
        "place_id,check_date,reviewer_role,verification_link,status,source_id\n"
        "SYN-P-A,2026-11-14,reviewer,https://syn.example/check,"
        "verified_open,tenant_directory\n",
        encoding="utf-8",
    )
    from datetime import date

    result = _build(
        path,
        grid=_grid(((25.3, 51.5), (25.35, 51.55))),
        categories=(("syn_restaurant", "restaurant"), ("syn_kiosk", "other")),
        buildings_paths=(buildings,),
        buildings_receipts=(receipt_for(buildings, "bldg_ovt"),),
        verified_path=verified,
        build_date=date(2026, 11, 14),
        zones={"69": _ZONE_69, "70": _ZONE_70},
        area_provider=_Areas(),
        candidates=(
            {"place_key": "SYN-CAND-1", "record_key": "SYN-B-A", "use": "commercial"},
            {"place_key": "SYN-CAND-2", "record_key": "SYN-B-A"},
        ),
    )
    assert result.flagship is not None
    body = result.flagship.body
    assert body["provider_given"] is True
    listed: list[Mapping[str, Any]] = body["candidates"]
    assert listed[0]["use"] == "commercial"
    assert listed[1]["use"] == ""
    inputs: Mapping[str, Any] = listed[0]["inputs"]
    assert inputs["use"] == "commercial"
    assert listed[1]["inputs"]["use"] == ""
    assert inputs["lon"] == 51.5
    assert inputs["lat"] == 25.3
    assert inputs["places"] == [
        {
            "place_id": "SYN-P-A",
            "lon": 51.5,
            "lat": 25.3,
            "category_class": "restaurant",
            "status": "verified_open",
        },
        {
            "place_id": "SYN-P-B",
            "lon": 51.55,
            "lat": 25.35,
            "category_class": "other",
            "status": "",
        },
    ]
    assert inputs["zones"] == {"69": _ZONE_69.wkb.hex(), "70": _ZONE_70.wkb.hex()}


def test_a_candidate_with_no_footprint_refuses_with_its_own_whole_reason(
    tmp_path: Path,
) -> None:
    """A candidate whose record is no read footprint refuses with the whole reason."""
    path = tmp_path / "places.parquet"
    write_places(path, [place_row(place_id="SYN-P-A")])
    buildings = tmp_path / "buildings.parquet"
    write_buildings(buildings, [building_row("SYN-B-A", _RING)])
    _refusal(
        lambda: _build(
            path,
            buildings_paths=(buildings,),
            buildings_receipts=(receipt_for(buildings, "bldg_ovt"),),
            candidates=(
                {
                    "place_key": "SYN-CAND-1",
                    "record_key": "SYN-B-UNKNOWN",
                    "use": "commercial",
                },
            ),
        ),
        "footprint_missing",
    )


def test_complete_needs_the_areas_the_release_and_the_settled_pairs() -> None:
    """Each of the five reasons on its own leaves the build incomplete."""
    settled = DuplicateOutcome((), (), frozenset())
    open_pair = DuplicateOutcome((), (("SYN-P-A", "SYN-P-B"),), frozenset())
    rows = (_fsq_row("SYN-F-A", "SYN Kiosk", "51.550000", "25.350000"),)
    specs = ({"record_key": "SYN-P-A"},)
    provider = _Areas()
    assert _complete(provider, specs, False, False, rows, _RELEASE, settled) is True
    assert _complete(provider, specs, True, False, rows, _RELEASE, settled) is False
    assert _complete(provider, specs, False, True, rows, _RELEASE, settled) is False
    assert _complete(None, specs, False, False, rows, _RELEASE, settled) is False
    assert _complete(provider, (), False, False, rows, _RELEASE, settled) is False
    assert _complete(provider, specs, False, False, None, _RELEASE, settled) is False
    assert _complete(provider, specs, False, False, rows, "", settled) is False
    assert _complete(provider, specs, False, False, rows, _RELEASE, open_pair) is False


def test_the_flagship_inputs_come_from_the_given_buildings_and_zones() -> None:
    """The prepared candidate holds the footprint's own pin and the given use."""
    buildings = (_building("SYN-B-A"),)
    places = (_pub_place(),)
    record = _flagship(
        ({"place_key": "SYN-CAND-1", "record_key": "SYN-B-A", "use": "mixed"},),
        buildings,
        places,
        {"SYN-P-A": "verified_open"},
        {"69": _ZONE_69},
        _Areas(),
    )
    assert record is not None
    listed: list[Mapping[str, Any]] = record.body["candidates"]
    inputs: Mapping[str, Any] = listed[0]["inputs"]
    assert inputs["lon"] == 51.5
    assert inputs["lat"] == 25.3
    assert inputs["use"] == "mixed"
    assert inputs["footprint_wkb_hex"] == _FOOTPRINT_WKB.hex()
    assert inputs["zones"] == {"69": _ZONE_69.wkb.hex()}


def test_the_further_source_note_counts_the_links_it_found() -> None:
    """A row that duplicates a kept place is linked, not shown, and is counted."""
    places = (_pub_place(),)
    rows = (_fsq_row("SYN-F-A", "SYN Cafe", "51.500000", "25.300000"),)
    shown, notes = _fsq(rows, places, frozenset(), _BOX, _RELEASE, _LICENCE)
    assert shown == ()
    assert notes == ("fsq_duplicate_not_shown: 1",)


def _building(building_id: str) -> Any:
    """One invented read footprint pinned at the centre of its own ring."""
    from eii_custodian.publicdata.places.read import ReadBuilding

    return ReadBuilding(
        building_id,
        Decimal("51.500000"),
        Decimal("25.300000"),
        _FOOTPRINT_WKB,
    )


_FOOTPRINT_WKB = Polygon(_RING).wkb
