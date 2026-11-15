"""The reviewed property use map of PUB-107. Fixtures are invented."""

from __future__ import annotations

from pathlib import Path

import pytest
from custodian.tests.repository_root import repository_root

from eii_custodian.publicdata.additions.common import AdditionError
from eii_custodian.publicdata.property.use_map import (
    ANY_USAGE,
    LAND_MARKER,
    UNIT_TYPES,
    USE_MAP_COLUMNS,
    UseMapping,
    load_use_map,
    use_lookup,
)


def _map_path() -> Path:
    """The committed review file: header and no row until the lead's read."""
    return (
        repository_root(Path(__file__))
        / "custodian"
        / "publicdata"
        / "review"
        / "property_use_map.csv"
    )


def _fixture_map() -> Path:
    return (
        repository_root(Path(__file__))
        / "custodian"
        / "tests"
        / "fixtures"
        / "property"
        / "use_map.csv"
    )


def _map() -> tuple[UseMapping, ...]:
    return load_use_map(_fixture_map())


def test_committed_map_holds_no_row_and_refuses_every_label() -> None:
    """Fail closed: a header-only committed map maps no label (PUB-107)."""
    rows = load_use_map(_map_path())
    assert rows == ()
    with pytest.raises(AdditionError) as caught:
        use_lookup(rows, "SYN-UNIT", "")
    assert caught.value.name == "unmapped_label"
    with pytest.raises(AdditionError) as other:
        use_lookup(rows, "SYN-LAND-1", "SYN-USE-RESI")
    assert other.value.name == "unmapped_label"


def _write(path: Path, rows: list[str]) -> Path:
    path.write_text(
        ",".join(USE_MAP_COLUMNS) + "\n" + "\n".join(rows) + "\n",
        encoding="utf-8",
    )
    return path


def test_fixture_map_loads_and_holds_only_reviewed_rows() -> None:
    rows = _map()
    assert rows, "the invented fixture map holds rows"
    for row in rows:
        assert row.source_id in {"prop_sales", "prop_resi_units"}
        assert row.arabic_label.strip()
        assert row.use_key.strip()
        assert row.marker == LAND_MARKER or row.marker in UNIT_TYPES
        assert row.reviewer.strip()
        assert row.reviewed_on[:4].isdigit()
    seen: set[tuple[str, str]] = set()
    for row in rows:
        pair = (row.arabic_label, row.usage_value)
        assert pair not in seen
        seen.add(pair)


def test_lookup_matches_label_and_usage_and_marks_land() -> None:
    rows = _map()
    land = use_lookup(rows, "SYN-LAND-1", "SYN-USE-RESI")
    assert land.source_id == "prop_sales"
    assert land.use_key == "residential"
    assert land.marker == LAND_MARKER
    assert land.land and land.unit_type is None
    unit = use_lookup(rows, "SYN-UNIT-1", "SYN-USE-RESI")
    assert unit.marker == "residential_unit"
    assert not unit.land and unit.unit_type == "residential_unit"


def test_wildcard_usage_matches_a_row_without_a_usage_field() -> None:
    rows = _map()
    matched = use_lookup(rows, "SYN-UNIT", "")
    assert matched.source_id == "prop_resi_units"
    assert matched.usage_value == ANY_USAGE
    assert matched.unit_type == "residential_unit"


def test_unmapped_label_and_unmapped_usage_fail_by_name() -> None:
    rows = _map()
    with pytest.raises(AdditionError) as label:
        use_lookup(rows, "SYN-UNMAPPED", "SYN-USE-RESI")
    assert label.value.name == "unmapped_label"
    with pytest.raises(AdditionError) as usage:
        use_lookup(rows, "SYN-LAND-1", "SYN-USE-UNMAPPED")
    assert usage.value.name == "unmapped_usage"


def test_ambiguous_label_usage_pair_fails(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "invented.csv",
        [
            "prop_sales,SYN-X,SYN-U,residential,land,SYN reviewer,2026-11-15",
            "prop_sales,SYN-X,SYN-U,residential,residential_unit,SYN reviewer,2026-11-15",
        ],
    )
    with pytest.raises(AdditionError) as caught:
        load_use_map(path)
    assert caught.value.name == "use_map_conflict"


def test_map_row_with_a_blank_field_or_extra_column_fails(tmp_path: Path) -> None:
    blank = _write(
        tmp_path / "blank.csv",
        ["prop_sales,SYN-X,SYN-U,,land,SYN reviewer,2026-11-15"],
    )
    with pytest.raises(AdditionError) as caught:
        load_use_map(blank)
    assert caught.value.name == "use_map_field_empty"
    extra = tmp_path / "extra.csv"
    extra.write_text(
        ",".join(USE_MAP_COLUMNS)
        + ",invented_extra\n"
        + "prop_sales,SYN-X,SYN-U,residential,land,SYN reviewer,2026-11-15,x\n",
        encoding="utf-8",
    )
    with pytest.raises(AdditionError) as caught:
        load_use_map(extra)
    assert caught.value.name == "use_map_columns"


def test_unknown_marker_fails(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "marker.csv",
        ["prop_sales,SYN-X,SYN-U,residential,invented_marker,SYN reviewer,2026-11-15"],
    )
    with pytest.raises(AdditionError) as caught:
        load_use_map(path)
    assert caught.value.name == "unknown_unit_type"


def test_a_source_id_outside_the_two_bulletins_fails(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "source.csv",
        ["invented_source,SYN-X,SYN-U,residential,land,SYN reviewer,2026-11-15"],
    )
    with pytest.raises(AdditionError) as caught:
        load_use_map(path)
    assert caught.value.name == "use_map_source"


def test_wildcard_and_exact_usage_on_one_label_disagree_in_the_map(
    tmp_path: Path,
) -> None:
    path = _write(
        tmp_path / "wild.csv",
        [
            "prop_sales,SYN-X,*,residential,land,SYN reviewer,2026-11-15",
            "prop_sales,SYN-X,SYN-U,commercial,land,SYN reviewer,2026-11-15",
        ],
    )
    rows = load_use_map(path)
    with pytest.raises(AdditionError) as caught:
        use_lookup(rows, "SYN-X", "SYN-U")
    assert caught.value.name == "use_map_ambiguous"


def test_reviewer_and_date_are_required_text(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "review.csv",
        ["prop_sales,SYN-X,SYN-U,residential,land,,2026-11-15"],
    )
    with pytest.raises(AdditionError) as caught:
        load_use_map(path)
    assert caught.value.name == "use_map_field_empty"
    bad_date = _write(
        tmp_path / "date.csv",
        ["prop_sales,SYN-X,SYN-U,residential,land,SYN reviewer,not-a-date"],
    )
    with pytest.raises(AdditionError):
        load_use_map(bad_date)
