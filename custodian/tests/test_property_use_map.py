"""The reviewed property use map of PUB-107. Fixtures are invented."""

from __future__ import annotations

import csv
from dataclasses import asdict
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from custodian.tests.repository_root import repository_root
from hypothesis import given, settings
from hypothesis import strategies as st

from eii_custodian.publicdata.additions.common import AdditionError
from eii_custodian.publicdata.assembly_refusals import closed_reason
from eii_custodian.publicdata.property import use_map
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
    """The committed review file of PUB-107."""
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


def test_every_committed_row_loads_and_resolves() -> None:
    rows = load_use_map(_map_path())
    assert rows
    for row in rows:
        assert use_lookup(rows, row.source_id, row.arabic_label, row.usage_value) == row


def test_committed_map_still_refuses_invented_labels() -> None:
    rows = load_use_map(_map_path())
    with pytest.raises(AdditionError) as caught:
        use_lookup(rows, "prop_resi_units", "SYN-UNIT", "")
    assert caught.value.name == "unmapped_label"
    with pytest.raises(AdditionError) as other:
        use_lookup(rows, "prop_sales", "SYN-LAND-1", "SYN-USE-RESI")
    assert other.value.name == "unmapped_label"


def test_committed_use_key_outside_the_list_refuses(tmp_path: Path) -> None:
    row = asdict(load_use_map(_map_path())[0])
    row["use_key"] = "SYN-UNKNOWN-USE"
    path = tmp_path / "bad-committed-use.csv"
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=USE_MAP_COLUMNS)
        writer.writeheader()
        writer.writerow(row)
    with pytest.raises(AdditionError, match=r"^use_map_use_key$"):
        load_use_map(path)


def test_unknown_use_key_has_a_closed_assembly_reason() -> None:
    assert (
        closed_reason("gis_property_singles", AdditionError("use_map_use_key"))
        == "use_map_use_key"
    )


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
    land = use_lookup(rows, "prop_sales", "SYN-LAND-1", "SYN-USE-RESI")
    assert land.source_id == "prop_sales"
    assert land.use_key == "residential"
    assert land.marker == LAND_MARKER
    assert land.land and land.unit_type is None
    unit = use_lookup(rows, "prop_sales", "SYN-UNIT-1", "SYN-USE-RESI")
    assert unit.marker == "residential_unit"
    assert not unit.land and unit.unit_type == "residential_unit"


def test_wildcard_usage_matches_a_row_without_a_usage_field() -> None:
    rows = _map()
    matched = use_lookup(rows, "prop_resi_units", "SYN-UNIT", "")
    assert matched.source_id == "prop_resi_units"
    assert matched.usage_value == ANY_USAGE
    assert matched.unit_type == "residential_unit"


def test_a_label_reviewed_for_one_bulletin_does_not_match_the_other() -> None:
    """J29(d): the source id is part of the lookup key."""
    rows = _map()
    with pytest.raises(AdditionError) as caught:
        use_lookup(rows, "prop_resi_units", "SYN-LAND-1", "SYN-USE-RESI")
    assert caught.value.name == "unmapped_label"
    with pytest.raises(AdditionError) as other:
        use_lookup(rows, "prop_sales", "SYN-UNIT", "")
    assert other.value.name == "unmapped_label"
    land = use_lookup(rows, "prop_sales", "SYN-LAND-1", "SYN-USE-RESI")
    assert land.source_id == "prop_sales"


def test_the_same_label_usage_pair_may_exist_for_both_bulletins(
    tmp_path: Path,
) -> None:
    """A (label, usage) pair reviewed under both sources is not a conflict."""
    path = _write(
        tmp_path / "both.csv",
        [
            "prop_sales,SYN-X,SYN-U,residential,land,SYN reviewer,2026-11-15",
            "prop_resi_units,SYN-X,SYN-U,commercial,residential_unit,SYN reviewer,2026-11-15",
        ],
    )
    rows = load_use_map(path)
    assert use_lookup(rows, "prop_sales", "SYN-X", "SYN-U").use_key == "residential"
    assert use_lookup(rows, "prop_resi_units", "SYN-X", "SYN-U").use_key == "commercial"


def test_unmapped_label_and_unmapped_usage_fail_by_name() -> None:
    rows = _map()
    with pytest.raises(AdditionError) as label:
        use_lookup(rows, "prop_sales", "SYN-UNMAPPED", "SYN-USE-RESI")
    assert label.value.name == "unmapped_label"
    with pytest.raises(AdditionError) as usage:
        use_lookup(rows, "prop_sales", "SYN-LAND-1", "SYN-USE-UNMAPPED")
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


def test_built_mapping_has_neither_land_nor_a_published_unit_type(
    tmp_path: Path,
) -> None:
    rows = load_use_map(
        _write(
            tmp_path / "built.csv",
            ["prop_sales,SYN-BUILT,*,residential,built,SYN reviewer,2026-11-24"],
        )
    )
    built = use_lookup(rows, "prop_sales", "SYN-BUILT", "SYN-USAGE")
    assert not built.land
    assert built.unit_type is None


@settings(deadline=None)
@given(
    st.text().filter(
        lambda value: (
            value.strip()
            and value
            not in {
                "residential",
                "commercial",
                "mixed",
                "community",
                "agricultural",
                "unspecified",
            }
        )
    )
)
def test_use_keys_outside_the_closed_vocabulary_refuse(value: str) -> None:
    with TemporaryDirectory() as folder:
        path = Path(folder) / "use.csv"
        with path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(USE_MAP_COLUMNS)
            writer.writerow(
                [
                    "prop_sales",
                    "SYN-X",
                    "*",
                    value,
                    "land",
                    "SYN reviewer",
                    "2026-11-24",
                ]
            )
        with pytest.raises(AdditionError, match=r"^use_map_use_key$"):
            load_use_map(path)


def test_closed_use_keys_are_the_ruled_vocabulary() -> None:
    assert use_map.USE_KEYS == frozenset(
        {
            "residential",
            "commercial",
            "mixed",
            "community",
            "agricultural",
            "unspecified",
        }
    )


@pytest.mark.parametrize("key", sorted(use_map.USE_KEYS))
@pytest.mark.parametrize(
    ("marker", "land", "unit"),
    [
        ("land", True, None),
        ("built", False, None),
        ("residential_unit", False, "residential_unit"),
    ],
)
def test_closed_uses_and_markers_load(
    tmp_path: Path, key: str, marker: str, land: bool, unit: str | None
) -> None:
    rows = load_use_map(
        _write(
            tmp_path / "closed.csv",
            [f"prop_sales,SYN-X,*,{key},{marker},SYN reviewer,2026-11-24"],
        )
    )
    assert rows[0].use_key == key
    assert rows[0].land is land
    assert rows[0].unit_type == unit


def test_empty_usage_is_not_the_absent_usage_token(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "empty-usage.csv",
        ["prop_sales,SYN-X,,residential,land,SYN reviewer,2026-11-24"],
    )
    with pytest.raises(AdditionError, match=r"^use_map_field_empty$"):
        load_use_map(path)


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
        use_lookup(rows, "prop_sales", "SYN-X", "SYN-U")
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
    with pytest.raises(AdditionError, match=r"^period_form$"):
        load_use_map(bad_date)
