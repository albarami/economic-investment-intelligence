"""Invented registry parts must supply every reviewed flagship area origin."""

from pathlib import Path

import pytest
from custodian.tests.fixtures.places.invented import building_row, write_buildings
from custodian.tests.test_places_area_files import _install_road
from custodian.tests.test_places_partb_survivors_b import _flag_row, _review
from custodian.tests.test_places_partb_survivors_c import _receipt, _row
from custodian.tests.test_places_partb_survivors_d import _PIN
from hypothesis import given
from hypothesis import strategies as st

from eii_custodian.publicdata.places import PlacesError, integrate
from eii_custodian.publicdata.places.area_files import AreaRequest
from eii_custodian.publicdata.places.area_requests import _remember, area_requests
from eii_custodian.publicdata.places.areas import AreaCutoff, AreaMode
from eii_custodian.publicdata.places.fetch import FILE_KEYS


def _candidate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, part: str
) -> tuple[Path, Path]:
    cache = tmp_path / "cache"
    candidate = dict(
        _flag_row("SYN-FLAGSHIP"), source_id="bldg_ovt", record_key="SYN-B-A"
    )
    review = _review(tmp_path / "review", flag=[candidate])
    building = cache / part / "syn.parquet"
    building.parent.mkdir(parents=True)
    write_buildings(building, [building_row("SYN-B-A", _PIN)])
    _receipt(building)
    entries = (_row(part, "bldg_ovt"),)
    monkeypatch.setattr(integrate, "load_registry", lambda: entries)
    return cache, review


@pytest.mark.parametrize("part", ["bldg_ovt/part-00384", "bldg_ovt/part-90001"])
def test_registry_building_supplies_flagship_point_and_all_requests(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, part: str
) -> None:
    cache, review = _candidate(tmp_path, monkeypatch, part)
    points = integrate._cache_points(cache, review)
    assert points == {("bldg_ovt", "SYN-B-A"): (51.501, 25.301)}
    assert area_requests(review, points) == (
        AreaRequest(
            "SYN-FLAGSHIP",
            "51.501000",
            "25.301000",
            AreaMode.DRIVE,
            AreaCutoff.MINUTES_10,
        ),
        AreaRequest(
            "SYN-FLAGSHIP",
            "51.501000",
            "25.301000",
            AreaMode.WALK,
            AreaCutoff.MINUTES_5,
        ),
        AreaRequest(
            "SYN-FLAGSHIP",
            "51.501000",
            "25.301000",
            AreaMode.WALK,
            AreaCutoff.MINUTES_10,
        ),
    )


def test_missing_flagship_point_refuses_with_its_specific_reason(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache, review = _candidate(tmp_path, monkeypatch, "bldg_ovt/part-00384")
    points = integrate._cache_points(cache, review)
    assert area_requests(review, points)
    del points[("bldg_ovt", "SYN-B-A")]
    with pytest.raises(PlacesError, match=r"^flagship_point_missing$"):
        area_requests(review, points)


def test_area_producer_logs_missing_flagship_point(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache, review = _candidate(tmp_path, monkeypatch, "bldg_ovt/part-00384")
    _install_road(cache)
    points = integrate._cache_points(cache, review)
    assert area_requests(review, points)
    del points[("bldg_ovt", "SYN-B-A")]
    monkeypatch.setattr(integrate, "_cache_points", lambda _cache, _review: points)
    lines: list[str] = []
    integrate.areas_before_stage(cache, lines, review)
    assert lines == ["REFUSED flagship_point_missing"]


def test_invented_extra_part_is_outside_the_fetch_list() -> None:
    assert "bldg_ovt/part-90001" not in FILE_KEYS


@given(
    source=st.text(min_size=1),
    record=st.text(min_size=1),
    mode=st.sampled_from(AreaMode),
    cutoff=st.sampled_from(AreaCutoff),
)
def test_required_point_needs_both_exact_keys(
    source: str, record: str, mode: AreaMode, cutoff: AreaCutoff
) -> None:
    item = {"source_id": source, "record_key": record, "place_key": "SYN-FLAGSHIP"}
    points = {
        (source, record): (51.5, 25.3),
        (source + "\0", record): (51.5, 25.3),
        (source, record + "\0"): (51.5, 25.3),
    }
    found: dict[tuple[str, str, int], AreaRequest] = {}
    _remember(found, item, points, mode, cutoff, required=True)
    assert tuple(found.values()) == (
        AreaRequest("SYN-FLAGSHIP", "51.500000", "25.300000", mode, cutoff),
    )
    del points[(source, record)]
    with pytest.raises(PlacesError, match=r"^flagship_point_missing$"):
        _remember({}, item, points, mode, cutoff, required=True)
