"""Reading plants: swapped axes, the wrong schema, a missing column."""

from __future__ import annotations

from pathlib import Path

import pytest
from custodian.tests.fixtures.places.invented import (
    building_row,
    place_row,
    write_buildings,
    write_places,
)

from eii_custodian.publicdata.places import PlacesError
from eii_custodian.publicdata.places.read import (
    read_building_file,
    read_place_file,
    record_level_source,
)


def test_swapped_axes_are_refused(tmp_path: Path) -> None:
    """Longitude stored as latitude is outside the latitude range."""
    path = tmp_path / "swapped.parquet"
    # A longitude past 90, stored in the latitude slot, is outside the axis range.
    write_places(path, [place_row(lon=25.3, lat=120.5)])
    with pytest.raises(PlacesError, match="axis_range"):
        read_place_file(path, "ar")


def test_wrong_schema_version_is_refused(tmp_path: Path) -> None:
    """schema_versions must name overture-schema-pyspark 2.0.0."""
    path = tmp_path / "old.parquet"
    write_places(path, [place_row()], schema_version="9.9.9")
    with pytest.raises(PlacesError, match="schema_versions"):
        read_place_file(path, "ar")


def test_missing_required_column_is_refused(tmp_path: Path) -> None:
    """A file without basic_category is not read."""
    path = tmp_path / "short.parquet"
    write_places(path, [place_row()], drop=("basic_category",))
    with pytest.raises(PlacesError, match="missing_column"):
        read_place_file(path, "ar")


@pytest.mark.parametrize("column", ["geometry", "id"])
def test_building_file_missing_a_required_column_is_refused(
    tmp_path: Path, column: str
) -> None:
    """A buildings file without geometry, or without id, is not read."""
    path = tmp_path / "buildings.parquet"
    ring = (
        (51.45, 25.25),
        (51.55, 25.25),
        (51.55, 25.35),
        (51.45, 25.35),
        (51.45, 25.25),
    )
    write_buildings(path, [building_row("SYN-B-1", ring)], drop=(column,))
    with pytest.raises(PlacesError, match="missing_column"):
        read_building_file(path)


def test_record_level_source_is_the_empty_property() -> None:
    """One named function: empty property, and not zero or two of them."""
    sources = [
        {"property": "names", "dataset": "syn-other"},
        {"property": "", "dataset": "syn-source"},
    ]
    found = record_level_source(sources)
    assert found.reason == "ok"
    assert found.entry is not None
    assert found.entry["dataset"] == "syn-source"
    assert (
        record_level_source([{"property": "names", "dataset": "syn-source"}]).reason
        == "absent"
    )
    doubled = record_level_source(
        [
            {"property": "", "dataset": "syn-source"},
            {"property": None, "dataset": "syn-other"},
        ]
    )
    assert doubled.reason == "not_unique"
    assert doubled.entry is None
