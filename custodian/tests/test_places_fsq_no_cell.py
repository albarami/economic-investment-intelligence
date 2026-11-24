"""L-1881: invented source-shaped rows account for gaps in an invented grid."""

from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from custodian.tests.fixtures.places_fsq.invented import place, write_places
from custodian.tests.test_places_fsq import _build, _grid
from hypothesis import example, given, settings
from hypothesis import strategies as st

from eii_custodian.publicdata.assembly_io import read_object, write_record
from eii_custodian.publicdata.places_fsq import assemble
from eii_custodian.publicdata.places_fsq.policy import PlaceStandIn


def test_no_cell_withheld_and_counted_preserves_other_rows(tmp_path):
    path = tmp_path / "places.parquet"
    valid = place()
    write_places(path, [valid])
    baseline = _build(path, ())
    write_places(
        path,
        [valid, place(fsq_place_id="abcd" * 5 + "aaaa", latitude=25.5)],
    )
    built = _build(path, ())
    assert built.rows == baseline.rows
    assert built.eligible == baseline.eligible
    assert built.names == baseline.names
    assert built.coverage.no_cell == 1
    assert replace(built.coverage, no_cell=0) == baseline.coverage
    # The adapter records the whole dataclass through the existing serializer.
    write_record(tmp_path, "assembly/fsq.json", {"coverage": built.coverage})
    assert read_object(tmp_path, "assembly/fsq.json")["coverage"]["no_cell"] == 1


def test_no_cell_duplicate_is_absent_from_links_and_name_check(tmp_path):
    path = tmp_path / "places.parquet"
    write_places(path, [place(latitude=25.5)])
    duplicate = PlaceStandIn("SYN-place", "Invented Cafe", None, 51.5, 25.5, False)
    built = _build(path, (duplicate,), labels=("Invented Cafe",))
    assert built.rows == built.eligible == built.duplicates == ()
    assert built.coverage.no_cell == 1
    assert built.coverage.duplicate_not_shown == 0
    assert built.coverage.unmapped_places == 0
    assert built.coverage.name_ar_null == 0
    assert built.names.ok
    assert built.names.collisions == ()


def test_closed_no_cell_is_counted_only_as_no_cell(tmp_path):
    path = tmp_path / "places.parquet"
    write_places(path, [place(latitude=25.5, date_closed="2024-01-08")])
    built = _build(path, ())
    assert built.rows == built.eligible == ()
    assert built.coverage.no_cell == 1
    assert built.coverage.closed_not_shown == 0


def test_no_cell_does_not_replace_country_or_frame_exclusions(tmp_path):
    path = tmp_path / "places.parquet"
    write_places(
        path,
        [
            place(),
            place(fsq_place_id="abcd" * 5 + "aaaa", country="AE"),
            place(fsq_place_id="abcd" * 5 + "bbbb", longitude=10.0, latitude=40.0),
            place(fsq_place_id="abcd" * 5 + "cccc", latitude=25.5),
        ],
    )
    built = _build(path, ())
    assert len(built.rows) == len(built.eligible) == 1
    assert built.coverage.no_cell == 1
    assert built.coverage.point_not_country == built.coverage.country_not_point == 1


@settings(deadline=None)
@given(st.lists(st.tuples(st.booleans(), st.booleans()), max_size=12))
@example([])
@example([(False, False)])
@example([(True, False)])
@example([(True, True), (False, True), (True, False), (False, False)])
def test_grid_membership_partitions_rows_once(states):
    """Input order, empty sets, repeated points and closure preserve accounting."""
    rows = [
        place(
            fsq_place_id="abcd" * 5 + f"{index:04x}",
            latitude=25.3 if has_cell else 25.5,
            date_closed="2024-01-08" if closed else None,
        )
        for index, (has_cell, closed) in enumerate(states)
    ]
    calls = []
    original = assemble.point_cell

    def point_cell(*args):
        calls.append(args[:2])
        return original(*args)

    with (
        TemporaryDirectory() as folder,
        patch.object(assemble, "point_cell", point_cell),
    ):
        path = Path(folder) / "places.parquet"
        write_places(path, rows)
        built = _build(path, (), grid=_grid((51.5, 25.3)))
    assert len(calls) == len(rows)
    assert len(built.rows) + built.coverage.no_cell == len(rows)
    assert [row.fsq_place_id for row in built.rows] == [
        row["fsq_place_id"]
        for row, (has_cell, _) in zip(rows, states, strict=True)
        if has_cell
    ]
    assert len(built.eligible) == sum(
        has_cell and not closed for has_cell, closed in states
    )
    assert built.coverage.closed_not_shown == sum(
        has_cell and closed for has_cell, closed in states
    )
    assert built.coverage.name_ar_null == len(built.rows)
    assert built.coverage.unmapped_places == len(built.rows)
    assert built.coverage.point_not_country == built.coverage.country_not_point == 0
