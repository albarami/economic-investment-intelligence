"""Hand-counted expectations for comparisons the first mutation run left alive.

Every number and reason string below was written out, not copied from a result.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from custodian.tests.fixtures.places_fsq.invented import place, write_places

import h3
from eii_custodian.publicdata.fetch.receipts import sha256_hex
from eii_custodian.publicdata.places_fsq.assemble import build_places
from eii_custodian.publicdata.places_fsq.constants import (
    ATTRIBUTION,
    LICENCE_NAME,
)
from eii_custodian.publicdata.places_fsq.errors import PlacesFsqError
from eii_custodian.publicdata.places_fsq.footer import metadata_bytes
from eii_custodian.publicdata.places_fsq.parse import account_rows, parse_file
from eii_custodian.publicdata.places_fsq.policy import (
    MAPPING_COLUMNS,
    CategoryMapping,
    PlaceStandIn,
    distance_m,
    duplicate_links,
    is_eligible,
    load_mapping,
    move_north,
    product_categories,
)
from eii_custodian.publicdata.places_fsq.select import FRAME_BOX, select_partitions

_RELEASE = "2025-01-10"
_WEST = 50.7
_SOUTH = 24.4
_EAST = 51.7
_NORTH = 26.2


def _reason(call: object) -> str:
    with pytest.raises(PlacesFsqError) as caught:
        call()
    assert isinstance(caught.value.reason, str)
    return caught.value.reason


def _group(
    name: str,
    longitude: tuple[float, float],
    latitude: tuple[float, float],
) -> dict[str, object]:
    return {
        "file_path": name,
        "longitude": longitude,
        "latitude": latitude,
        "geo_bbox": None,
    }


def test_selection_keeps_an_edge_and_an_overlap_and_names_the_release() -> None:
    """The frame edges are inside. An overlap uses the low end of each axis."""
    body = metadata_bytes(
        (
            _group("east.parquet", (_EAST, _EAST), (25.0, 25.6)),
            _group("north.parquet", (51.0, 51.4), (_NORTH, _NORTH)),
            _group("overlap-x.parquet", (51.6, 51.9), (25.0, 25.6)),
            _group("overlap-y.parquet", (51.0, 51.4), (26.0, 26.5)),
            _group("dated.parquet", (51.0, 51.4), (25.0, 25.6)),
        ),
        dataset_geo_bbox=None,
    )
    # The dated path is rewritten below; this body uses undated names.
    selected = select_partitions(body, release="2025-01-10", frame=FRAME_BOX)
    assert selected.files == (
        "dated.parquet",
        "east.parquet",
        "north.parquet",
        "overlap-x.parquet",
        "overlap-y.parquet",
    )
    assert selected.release == "2025-01-10"
    dated = metadata_bytes(
        (
            _group(
                "2025-01-10/places/near.parquet",
                (51.0, 51.4),
                (25.0, 25.6),
            ),
        ),
        dataset_geo_bbox=None,
    )
    kept = select_partitions(dated, release="2025-01-10", frame=FRAME_BOX)
    assert kept.files == ("2025-01-10/places/near.parquet",)
    assert kept.release == "2025-01-10"
    missing = dict(_group("bare.parquet", (51.0, 51.4), (25.0, 25.6)))
    missing["file_path"] = ""
    assert (
        _reason(
            lambda: select_partitions(
                metadata_bytes((missing,), dataset_geo_bbox=None),
                release="2025-01-10",
                frame=FRAME_BOX,
            )
        )
        == "file_path_missing"
    )
    unstated = dict(_group("quiet.parquet", (51.0, 51.4), (25.0, 25.6)))
    unstated["omit_latitude_stats"] = True
    assert (
        _reason(
            lambda: select_partitions(
                metadata_bytes((unstated,), dataset_geo_bbox=None),
                release="2025-01-10",
                frame=FRAME_BOX,
            )
        )
        == "statistics_missing"
    )
    wrong = _group("2025-02-06/places/32.parquet", (51.0, 51.4), (25.0, 25.6))
    assert (
        _reason(
            lambda: select_partitions(
                metadata_bytes((wrong,), dataset_geo_bbox=None),
                release="2025-01-10",
                frame=FRAME_BOX,
            )
        )
        == "release_mismatch"
    )


def test_one_kept_place_carries_the_hand_written_table_fields(tmp_path: Path) -> None:
    """One invented place. Counts are 1 kept, 0 mixed, 1 unmapped."""
    path = tmp_path / "places.parquet"
    write_places(path, [place()])
    digest = sha256_hex(path.read_bytes())
    built = build_places(
        files={"near.parquet": path},
        expected_sha256={"near.parquet": digest},
        frame=FRAME_BOX,
        grid=[
            {"cell": h3.str_to_int(h3.latlng_to_cell(25.3, 51.5, 9))},
        ],
        places=(),
        mapping=(),
        labels=("Qorvex Marker",),
        min_edit_distance=2,
        release="2025-01-10",
        attribution=ATTRIBUTION,
        receipt_sha256="a" * 64,
    )
    row = built.rows[0]
    assert row.fsq_place_id == "abcdabcdabcdabcdabcdabcd"
    assert row.name == "Invented Cafe"
    assert row.name_ar is None
    assert row.category_ids == ""
    assert row.category_labels == ""
    assert row.lon == Decimal("51.500000")
    assert row.lat == Decimal("25.300000")
    assert row.cell == h3.str_to_int(h3.latlng_to_cell(25.3, 51.5, 9))
    assert row.source_release == "2025-01-10"
    assert row.licence == LICENCE_NAME
    assert row.licence == "Apache License, Version 2.0"
    assert row.date_created == date(2020, 1, 2)
    assert row.date_refreshed == date(2024, 6, 1)
    assert row.date_closed is None
    assert built.method == "places_fsq.v1"
    assert built.release == "2025-01-10"
    assert built.coverage.name_ar_null == 1
    assert built.coverage.name_ar_filled == 0
    assert built.coverage.point_not_country == 0
    assert built.coverage.country_not_point == 0
    assert built.coverage.unmapped_places == 1
    assert built.coverage.duplicate_not_shown == 0
    assert built.coverage.closed_not_shown == 0
    assert built.eligible[0].receipt_sha256 == "a" * 64
    assert built.eligible[0].source_release == "2025-01-10"
    assert (
        _reason(
            lambda: build_places(
                files={"near.parquet": path},
                expected_sha256={"near.parquet": digest},
                frame=FRAME_BOX,
                grid=[{"cell": 1}],
                places=(),
                mapping=(),
                labels=(),
                min_edit_distance=2,
                release="2025-01-10",
                attribution=ATTRIBUTION,
                receipt_sha256="a" * 64,
            )
        )
        == "cell"
    )
    assert (
        _reason(
            lambda: build_places(
                files={"near.parquet": path},
                expected_sha256={"near.parquet": digest},
                frame=FRAME_BOX,
                grid=[{"cell": h3.str_to_int(h3.latlng_to_cell(25.3, 51.5, 9))}],
                places=(),
                mapping=(),
                labels=(),
                min_edit_distance=2,
                release="",
                attribution=ATTRIBUTION,
                receipt_sha256="a" * 64,
            )
        )
        == "source_release"
    )
    assert (
        _reason(
            lambda: build_places(
                files={"near.parquet": path},
                expected_sha256={"near.parquet": digest},
                frame=FRAME_BOX,
                grid=[{"cell": h3.str_to_int(h3.latlng_to_cell(25.3, 51.5, 9))}],
                places=(),
                mapping=(),
                labels=(),
                min_edit_distance=2,
                release=_RELEASE,
                attribution=ATTRIBUTION,
                receipt_sha256="",
            )
        )
        == "attribution"
    )
    assert (
        _reason(
            lambda: build_places(
                files={"near.parquet": path},
                expected_sha256={"near.parquet": "0" * 64},
                frame=FRAME_BOX,
                grid=[{"cell": h3.str_to_int(h3.latlng_to_cell(25.3, 51.5, 9))}],
                places=(),
                mapping=(),
                labels=(),
                min_edit_distance=2,
                release="2025-01-10",
                attribution=ATTRIBUTION,
                receipt_sha256="a" * 64,
            )
        )
        == "receipt_mismatch"
    )
    assert (
        _reason(
            lambda: build_places(
                files={},
                expected_sha256={"near.parquet": digest},
                frame=FRAME_BOX,
                grid=[{"cell": 1}],
                places=(),
                mapping=(),
                labels=(),
                min_edit_distance=2,
                release="2025-01-10",
                attribution=ATTRIBUTION,
                receipt_sha256="a" * 64,
            )
        )
        == "receipt_mismatch"
    )


def test_two_mixed_rows_add_to_two(tmp_path: Path) -> None:
    """Two rows of each mixed kind. The counts are 2 and 2, not 1."""
    path = tmp_path / "mixed.parquet"
    write_places(
        path,
        [
            place(
                fsq_place_id="dddddddddddddddddddd0001",
                country="AE",
                longitude=51.4,
                latitude=25.2,
            ),
            place(
                fsq_place_id="dddddddddddddddddddd0002",
                country="AE",
                longitude=51.45,
                latitude=25.25,
            ),
            place(
                fsq_place_id="dddddddddddddddddddd0003",
                country="QA",
                longitude=10.0,
                latitude=40.0,
            ),
            place(
                fsq_place_id="dddddddddddddddddddd0004",
                country="QA",
                longitude=11.0,
                latitude=41.0,
            ),
        ],
    )
    account = account_rows(parse_file(path), FRAME_BOX)
    assert account.kept == ()
    assert account.point_not_country == 2
    assert account.country_not_point == 2


def test_edges_of_the_frame_and_a_fifty_metre_step_are_inside(tmp_path: Path) -> None:
    """50.7 and 51.7, 24.4 and 26.2 are inside. The same point is 0 metres."""
    path = tmp_path / "edges.parquet"
    write_places(
        path,
        [
            place(
                fsq_place_id="bbbbbbbbbbbbbbbbbbbb0001", longitude=_WEST, latitude=25.3
            ),
            place(
                fsq_place_id="bbbbbbbbbbbbbbbbbbbb0002", longitude=_EAST, latitude=25.3
            ),
            place(
                fsq_place_id="bbbbbbbbbbbbbbbbbbbb0003", longitude=51.5, latitude=_SOUTH
            ),
            place(
                fsq_place_id="bbbbbbbbbbbbbbbbbbbb0004", longitude=51.5, latitude=_NORTH
            ),
            place(
                fsq_place_id="bbbbbbbbbbbbbbbbbbbb0005", longitude=10.0, latitude=25.3
            ),
        ],
    )
    rows = {row.fsq_place_id: row for row in parse_file(path)}
    for key in (
        "bbbbbbbbbbbbbbbbbbbb0001",
        "bbbbbbbbbbbbbbbbbbbb0002",
        "bbbbbbbbbbbbbbbbbbbb0003",
        "bbbbbbbbbbbbbbbbbbbb0004",
    ):
        assert is_eligible(rows[key], FRAME_BOX, ()) is True
    assert is_eligible(rows["bbbbbbbbbbbbbbbbbbbb0005"], FRAME_BOX, ()) is False
    assert distance_m(51.5, 25.3, 51.5, 25.3) == 0.0
    north = move_north(51.5, 25.3, 50.0)
    # The pure-north step of 50 m lands 1.2554e-10 m over 50, so it is not a duplicate.
    assert distance_m(51.5, 25.3, north[0], north[1]) > 50.0
    under = move_north(51.5, 25.3, 49.999999)
    assert distance_m(51.5, 25.3, under[0], under[1]) < 50.0
    link = duplicate_links(
        (rows["bbbbbbbbbbbbbbbbbbbb0001"],),
        (PlaceStandIn("p", "Invented Cafe", None, _WEST, 25.3, False),),
    )
    assert len(link) == 1
    assert link[0].place_id == "p"
    assert link[0].distance_m == 0.0
    assert link[0].in_showcase is False


def test_mapping_row_keeps_every_reviewed_field(tmp_path: Path) -> None:
    """Each column of one approved row is the text written in the file."""
    path = tmp_path / "map.csv"
    path.write_text(
        ",".join(MAPPING_COLUMNS)
        + "\n"
        + "cccccccccccccccceeee0001,food,fsq-map-1,approved,reviewer,2026-11-14,invented\n",
        encoding="utf-8",
    )
    loaded = load_mapping(path, frozenset({"food"}))
    assert loaded == (
        CategoryMapping(
            source_category_id="cccccccccccccccceeee0001",
            place_category_key="food",
            mapping_version="fsq-map-1",
            review_status="approved",
            reviewer_role="reviewer",
            review_date="2026-11-14",
            rationale="invented",
        ),
    )
    assert product_categories("cccccccccccccccceeee0001", loaded) == "food"
    with pytest.raises(PlacesFsqError, match=r"^category_unmapped$"):
        product_categories("cccccccccccccccceeee0001;dddd", loaded)
    assert product_categories("", loaded) is None
    blank = tmp_path / "blank.csv"
    blank.write_text(
        ",".join(MAPPING_COLUMNS)
        + "\n"
        + ",food,fsq-map-1,approved,reviewer,2026-11-14,invented\n",
        encoding="utf-8",
    )
    assert (
        _reason(lambda: load_mapping(blank, frozenset({"food"}))) == "mapping_unsigned"
    )
    pending = tmp_path / "pending.csv"
    pending.write_text(
        ",".join(MAPPING_COLUMNS)
        + "\n"
        + "cccccccccccccccceeee0001,food,fsq-map-1,pending,reviewer,2026-11-14,invented\n",
        encoding="utf-8",
    )
    assert (
        _reason(lambda: load_mapping(pending, frozenset({"food"})))
        == "mapping_unsigned"
    )
    unknown = tmp_path / "unknown.csv"
    unknown.write_text(
        ",".join(MAPPING_COLUMNS)
        + "\n"
        + "cccccccccccccccceeee0001,made-up,fsq-map-1,approved,reviewer,2026-11-14,invented\n",
        encoding="utf-8",
    )
    assert (
        _reason(lambda: load_mapping(unknown, frozenset({"food"})))
        == "mapping_unknown_target"
    )
    header = tmp_path / "header.csv"
    header.write_text("a,b\n", encoding="utf-8")
    assert _reason(lambda: load_mapping(header, frozenset())) == "mapping_header"
    conflict = tmp_path / "conflict.csv"
    conflict.write_text(
        ",".join(MAPPING_COLUMNS)
        + "\n"
        + "cccccccccccccccceeee0001,food,fsq-map-1,approved,reviewer,2026-11-14,invented\n"
        + "cccccccccccccccceeee0001,shop,fsq-map-1,approved,reviewer,2026-11-14,invented\n",
        encoding="utf-8",
    )
    assert (
        _reason(lambda: load_mapping(conflict, frozenset({"food", "shop"})))
        == "mapping_conflict"
    )
    repeated = tmp_path / "same.csv"
    repeated.write_text(
        ",".join(MAPPING_COLUMNS)
        + "\n"
        + "cccccccccccccccceeee0001,food,fsq-map-1,approved,reviewer,2026-11-14,invented\n"
        + "cccccccccccccccceeee0001,food,fsq-map-1,approved,reviewer,2026-11-14,invented\n",
        encoding="utf-8",
    )
    assert (
        _reason(lambda: load_mapping(repeated, frozenset({"food"})))
        == "mapping_conflict"
    )
