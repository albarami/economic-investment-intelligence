"""The build mutants that survived the first campaign. Every record is invented."""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from datetime import date
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
from shapely.geometry import box

from eii_custodian.publicdata.places import PlacesError
from eii_custodian.publicdata.places.build import (
    _dataset,
    _require_fields,
    _table,
    build_places,
)
from eii_custodian.publicdata.places.display import PubPlace
from eii_custodian.publicdata.places.review import Verification

_LICENCE = "SYN-LICENCE"
_ATTR = (("syn-source", _LICENCE),)
_BOX = box(51.4, 25.2, 51.6, 25.4)
_RING = (
    (51.45, 25.25),
    (51.55, 25.25),
    (51.55, 25.35),
    (51.45, 25.35),
    (51.45, 25.25),
)
# The resolution-9 cell of 25.3 north, 51.5 east, worked out with h3 by hand.
_CELL = 618460705430700031
_BUILD_DATE = date(2026, 11, 14)
_VERIFICATION = Verification(
    "SYN-P-A",
    "2026-11-14",
    "reviewer",
    "https://syn.example/check",
    "verified_open",
    "tenant_directory",
)
_CACHED = Verification(
    "SYN-P-A",
    "2026-11-13",
    "reviewer",
    "https://syn.example/check",
    "not_found",
    "tenant_directory",
)


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


def _write_csv(
    path: Path, columns: tuple[str, ...], rows: Sequence[tuple[str, ...]]
) -> None:
    """Write one invented review file with exactly these columns."""
    lines = [",".join(columns), *[",".join(row) for row in rows]]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _pub_place(**overrides: Any) -> PubPlace:
    """One invented pub_place row, with the three required fields present."""
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


class _Loader:
    """An invented table loader that records the two arguments it is given."""

    def __init__(self, loaded: object) -> None:
        self.loaded = loaded
        self.calls: list[tuple[object, object]] = []

    def __call__(self, committed: object, cache: object) -> object:
        self.calls.append((committed, cache))
        return self.loaded


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


def test_a_blank_arabic_tag_refuses_with_its_own_whole_reason(tmp_path: Path) -> None:
    """The refusal carries the whole reason and nothing around it."""
    absent = tmp_path / "absent.parquet"
    _refusal(
        lambda: build_places(absent, arabic_tag="   ", boundary=_BOX, grid=()),
        "arabic_tag",
    )


def test_the_attribution_and_category_tables_come_from_their_files(
    tmp_path: Path,
) -> None:
    """A given file is read, and its table replaces the rows held in memory."""
    path = tmp_path / "places.parquet"
    write_places(path, [place_row(place_id="SYN-P-A")])
    attribution = tmp_path / "attribution.csv"
    _write_csv(
        attribution,
        ("dataset_token", "licence"),
        [("syn-source", "SYN-FILE-LICENCE")],
    )
    categories = tmp_path / "categories.csv"
    _write_csv(
        categories,
        ("basic_category", "category_class"),
        [("syn_restaurant", "restaurant")],
    )
    result = _build(
        path,
        attribution=(("syn-source", "SYN-MEMORY-LICENCE"),),
        attribution_path=attribution,
        categories=(("syn_restaurant", "other"),),
        categories_path=categories,
    )
    assert len(result.places) == 1
    assert result.places[0].licence == "SYN-FILE-LICENCE"
    assert result.places[0].category_class == "restaurant"


def test_the_attribution_and_category_caches_win_over_the_committed_files(
    tmp_path: Path,
) -> None:
    """A cache file that exists is the file the two tables are read from."""
    path = tmp_path / "places.parquet"
    write_places(path, [place_row(place_id="SYN-P-A")])
    attribution = tmp_path / "attribution.csv"
    _write_csv(
        attribution,
        ("dataset_token", "licence"),
        [("syn-source", "SYN-FILE-LICENCE")],
    )
    attribution_cache = tmp_path / "attribution-cache.csv"
    _write_csv(
        attribution_cache,
        ("dataset_token", "licence"),
        [("syn-source", "SYN-CACHE-LICENCE")],
    )
    categories = tmp_path / "categories.csv"
    _write_csv(
        categories,
        ("basic_category", "category_class"),
        [("syn_restaurant", "restaurant")],
    )
    categories_cache = tmp_path / "categories-cache.csv"
    _write_csv(
        categories_cache,
        ("basic_category", "category_class"),
        [("syn_restaurant", "italian_restaurant")],
    )
    result = _build(
        path,
        attribution_path=attribution,
        attribution_cache=attribution_cache,
        categories_path=categories,
        categories_cache=categories_cache,
    )
    assert result.places[0].licence == "SYN-CACHE-LICENCE"
    assert result.places[0].category_class == "italian_restaurant"


def test_a_table_loader_is_given_the_path_and_the_cache(tmp_path: Path) -> None:
    """The loader is called once, with both paths, and its table is returned."""
    committed = tmp_path / "committed.csv"
    cache = tmp_path / "cache.csv"
    table = (("syn-source", "SYN-LICENCE"),)
    loader = _Loader(("committed", table))
    assert _table((), committed, cache, loader) == table
    assert loader.calls == [(committed, cache)]


def test_a_loader_of_the_wrong_shape_refuses_with_its_own_whole_reason(
    tmp_path: Path,
) -> None:
    """Each of the three shape checks refuses with the whole reason."""
    committed = tmp_path / "committed.csv"
    _refusal(lambda: _table((), committed, None, None), "loader")
    _refusal(
        lambda: _table((), committed, None, _Loader(("origin", "syn-source", "extra"))),
        "loader",
    )
    _refusal(
        lambda: _table(
            (), committed, None, _Loader(["origin", (("syn-source", "x"),)])
        ),
        "loader",
    )
    _refusal(
        lambda: _table((), committed, None, _Loader(("origin", "syn-source"))),
        "loader",
    )


def test_a_kept_row_carries_its_own_cell_and_its_category_class(
    tmp_path: Path,
) -> None:
    """The cell is the point's own, and an unlisted category has no class."""
    path = tmp_path / "places.parquet"
    write_places(
        path,
        [
            place_row(place_id="SYN-P-A", basic_category="syn_restaurant"),
            place_row(
                place_id="SYN-P-B",
                basic_category="syn_kiosk",
                names={"primary": "SYN Kiosk", "common": {}},
            ),
        ],
    )
    result = _build(path, categories=(("syn_restaurant", "restaurant"),))
    assert [
        (place.place_id, place.cell, place.category_class) for place in result.places
    ] == [
        ("SYN-P-A", _CELL, "restaurant"),
        ("SYN-P-B", _CELL, ""),
    ]


def test_a_source_entry_with_no_dataset_has_no_token() -> None:
    """No entry and an entry without the field both give no token."""
    assert _dataset(None) is None
    assert _dataset({}) is None
    assert _dataset({"dataset": ""}) is None
    assert _dataset({"dataset": 7}) is None
    assert _dataset({"dataset": "syn-source"}) == "syn-source"


def test_a_row_with_no_source_provider_refuses_the_pub_place_field() -> None:
    """A blank provider or a blank licence refuses, and a whole row does not."""
    _refusal(lambda: _require_fields(_pub_place(source_provider="")), "pub_place_field")
    _refusal(lambda: _require_fields(_pub_place(licence="")), "pub_place_field")
    _refusal(
        lambda: _require_fields(_pub_place(confidence="0.8000")), "pub_place_field"
    )
    assert _require_fields(_pub_place()) is None


def test_an_in_memory_verification_refuses_without_the_build_date(
    tmp_path: Path,
) -> None:
    """A row held in memory still needs the build date it is checked against."""
    path = tmp_path / "places.parquet"
    write_places(path, [place_row(place_id="SYN-P-A")])
    _refusal(
        lambda: _build(path, verified=(_VERIFICATION,), build_date=None),
        "bad_check_date",
    )


def test_a_verification_file_refuses_without_the_build_date(tmp_path: Path) -> None:
    """A verification file is refused before it is opened without a build date."""
    path = tmp_path / "places.parquet"
    write_places(path, [place_row(place_id="SYN-P-A")])
    committed = tmp_path / "verified.csv"
    _write_csv(
        committed,
        (
            "place_id",
            "check_date",
            "reviewer_role",
            "verification_link",
            "status",
            "source_id",
        ),
        [
            (
                "SYN-P-A",
                "2026-11-14",
                "reviewer",
                "https://syn.example/check",
                "verified_open",
                "tenant_directory",
            )
        ],
    )
    _refusal(
        lambda: _build(path, verified_path=committed, build_date=None),
        "bad_check_date",
    )


def test_a_verification_file_is_read_with_the_known_ids_and_the_date(
    tmp_path: Path,
) -> None:
    """The loader takes the kept ids and the build date, and its rows are the result."""
    path = tmp_path / "places.parquet"
    write_places(path, [place_row(place_id="SYN-P-A")])
    committed = tmp_path / "verified.csv"
    _write_csv(
        committed,
        (
            "place_id",
            "check_date",
            "reviewer_role",
            "verification_link",
            "status",
            "source_id",
        ),
        [
            (
                "SYN-P-A",
                "2026-11-14",
                "reviewer",
                "https://syn.example/check",
                "verified_open",
                "tenant_directory",
            )
        ],
    )
    result = _build(path, verified_path=committed, build_date=_BUILD_DATE)
    assert result.verifications == (_VERIFICATION,)


def test_the_verification_cache_wins_over_the_committed_file(tmp_path: Path) -> None:
    """A cache file that exists is the file the verification rows come from."""
    path = tmp_path / "places.parquet"
    write_places(path, [place_row(place_id="SYN-P-A")])
    columns = (
        "place_id",
        "check_date",
        "reviewer_role",
        "verification_link",
        "status",
        "source_id",
    )
    committed = tmp_path / "verified.csv"
    _write_csv(
        committed,
        columns,
        [
            (
                "SYN-P-A",
                "2026-11-14",
                "reviewer",
                "https://syn.example/check",
                "verified_open",
                "tenant_directory",
            )
        ],
    )
    cache = tmp_path / "verified-cache.csv"
    _write_csv(
        cache,
        columns,
        [
            (
                "SYN-P-A",
                "2026-11-13",
                "reviewer",
                "https://syn.example/check",
                "not_found",
                "tenant_directory",
            )
        ],
    )
    result = _build(
        path, verified_path=committed, verified_cache=cache, build_date=_BUILD_DATE
    )
    assert result.verifications == (_CACHED,)


def test_the_result_carries_the_name_inventory(tmp_path: Path) -> None:
    """The inventory holds the name and the Arabic name of the kept row."""
    path = tmp_path / "places.parquet"
    write_places(path, [place_row(place_id="SYN-P-A")])
    result = _build(path)
    assert result.names == ("SYN Cafe", "مقهى تجريبي")


def test_the_points_file_carries_the_lon_and_lat_of_each_row(tmp_path: Path) -> None:
    """Both point rows are written with their own longitude and latitude text."""
    places = tmp_path / "places.parquet"
    write_places(places, [place_row(place_id="SYN-P-A")])
    buildings = tmp_path / "buildings.parquet"
    write_buildings(buildings, [building_row("SYN-B-A", _RING)])
    output = tmp_path / "out"
    _build(
        places,
        buildings_paths=(buildings,),
        buildings_receipts=(receipt_for(buildings, "bldg_ovt"),),
        output_dir=output,
    )
    written = json.loads(
        (output / "places_s2_t06" / "place_points.json").read_text(encoding="utf-8")
    )
    assert written == [
        {
            "source_id": "places_ovt",
            "record_key": "SYN-P-A",
            "lon": "51.500000",
            "lat": "25.300000",
        },
        {
            "source_id": "bldg_ovt",
            "record_key": "SYN-B-A",
            "lon": "51.500000",
            "lat": "25.300000",
        },
    ]
