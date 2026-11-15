"""Hand-written values for mutants the second mutation run left alive.

Each expected number below was calculated from the sphere formula and then
checked once against the function. The literals are the expected values.
"""

from __future__ import annotations

import hashlib
import struct
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from custodian.tests.repository_root import repository_root

from eii_custodian.publicdata.places_fsq.errors import PlacesFsqError
from eii_custodian.publicdata.places_fsq.footer import (
    ChunkStat,
    metadata_bytes,
    read_summary,
)
from eii_custodian.publicdata.places_fsq.footer import _bbox_from_geo as footer_bbox
from eii_custodian.publicdata.places_fsq.footer import _four as footer_four
from eii_custodian.publicdata.places_fsq.parse import (
    ParsedRow,
    _categories,
    _close,
    _float,
    _local,
    _range,
    _row,
    _schema,
    _wkb_point,
    account_rows,
)
from eii_custodian.publicdata.places_fsq.policy import (
    MAPPING_COLUMNS,
    CategoryMapping,
    PlaceStandIn,
    assert_policy,
    distance_m,
    duplicate_links,
    load_mapping,
    move_north,
    product_categories,
)
from eii_custodian.publicdata.places_fsq.select import (
    FRAME_BOX,
    IgnoredGeo,
    _axis,
    select_partitions,
)

_POLICY = (
    repository_root(Path(__file__))
    / "custodian"
    / "publicdata"
    / "review"
    / "places_fsq_policy.yaml"
)
_HEADER = ",".join(MAPPING_COLUMNS)
_EXACT_50_EAST = Decimal("0.0004496608029593653")
_EAST_AT_EQUATOR_M = 111194.92664455874
_OFFSET_PAIR_M = 14987.36870789513


def _reason(call: object) -> str:
    with pytest.raises(PlacesFsqError) as caught:
        call()
    assert isinstance(caught.value.reason, str)
    return caught.value.reason


def _link_row(name: str, lon: Decimal, lat: Decimal) -> ParsedRow:
    return ParsedRow(
        fsq_place_id="abcdabcdabcdabcdabcd00aa",
        name=name,
        name_ar=None,
        category_ids="",
        category_labels="",
        lon=lon,
        lat=lat,
        country="QA",
        date_created=date(2020, 1, 2),
        date_refreshed=date(2024, 6, 1),
        date_closed=None,
    )


def test_a_north_file_is_outside_and_one_missing_end_refuses() -> None:
    """A row group wholly north of 26.2 is not fetched. One missing end refuses."""
    body = metadata_bytes(
        (
            {
                "file_path": "north-of-frame.parquet",
                "longitude": (51.0, 51.4),
                "latitude": (26.3, 26.5),
                "geo_bbox": None,
            },
        ),
        dataset_geo_bbox=None,
    )
    assert (
        _reason(lambda: select_partitions(body, release="2025-01-10", frame=FRAME_BOX))
        == "no_file_for_frame"
    )
    low_only = ChunkStat("a.parquet", ("longitude",), 51.0, None, None)
    high_only = ChunkStat("a.parquet", ("longitude",), None, 51.4, None)
    assert _reason(lambda: _axis((low_only,), ("longitude",))) == "statistics_missing"
    assert _reason(lambda: _axis((high_only,), ("longitude",))) == "statistics_missing"
    assert _reason(lambda: _axis((), ("longitude",))) == "statistics_missing"


def test_sphere_distances_match_the_written_metres() -> None:
    """One degree east at the equator, and a diagonal, are the written lengths."""
    assert distance_m(0.0, 0.0, 1.0, 0.0) == _EAST_AT_EQUATOR_M
    assert distance_m(51.5, 25.3, 51.6, 25.4) == _OFFSET_PAIR_M
    assert distance_m(0.0, 0.0, float(_EXACT_50_EAST), 0.0) == 50.0
    moved = move_north(51.5, 25.3, 50.0)
    assert moved[0] == 51.5
    assert moved[1] == 25.3 + (50.0 / 6_371_000.0) * (180.0 / 3.141592653589793)
    row = _link_row("Invented Cafe", _EXACT_50_EAST, Decimal("0"))
    place = PlaceStandIn("p", "Invented Cafe", None, 0.0, 0.0, False)
    link = duplicate_links((row,), (place,))
    assert len(link) == 1
    assert link[0].distance_m == 50.0
    assert link[0].place_id == "p"
    other = PlaceStandIn("q", "Other Name", None, 0.0, 0.0, False)
    assert duplicate_links((row,), (other,)) == ()
    arabic = PlaceStandIn("r", "Other Name", "Invented Cafe", 0.0, 0.0, False)
    matched = duplicate_links((row,), (arabic,))
    assert len(matched) == 1
    assert matched[0].place_id == "r"


def test_mapping_skips_a_comment_and_a_blank_line_and_joins_two_keys(
    tmp_path: Path,
) -> None:
    """A comment and an empty row are not mappings. Two keys stay joined by ';'."""
    path = tmp_path / "map.csv"
    path.write_bytes(
        (
            "# invented comment\n"
            + _HEADER
            + "\n"
            + ",,,,,,\n"
            + 'cccccccccccccccceeee0001,food,fsq-map-1,approved,reviewer,2026-11-14,"hello\r\nworld"\n'
            + "cccccccccccccccceeee0002,shop,fsq-map-1,approved,reviewer,2026-11-14,second\n"
        ).encode()
    )
    loaded = load_mapping(path, frozenset({"food", "shop"}))
    assert loaded == (
        CategoryMapping(
            source_category_id="cccccccccccccccceeee0001",
            place_category_key="food",
            mapping_version="fsq-map-1",
            review_status="approved",
            reviewer_role="reviewer",
            review_date="2026-11-14",
            rationale="hello\r\nworld",
        ),
        CategoryMapping(
            source_category_id="cccccccccccccccceeee0002",
            place_category_key="shop",
            mapping_version="fsq-map-1",
            review_status="approved",
            reviewer_role="reviewer",
            review_date="2026-11-14",
            rationale="second",
        ),
    )
    assert (
        product_categories("cccccccccccccccceeee0001;cccccccccccccccceeee0002", loaded)
        == "food;shop"
    )
    marked = (
        CategoryMapping(
            source_category_id="XXXX",
            place_category_key="food",
            mapping_version="fsq-map-1",
            review_status="approved",
            reviewer_role="reviewer",
            review_date="2026-11-14",
            rationale="invented",
        ),
    )
    assert product_categories("XXXX", marked) == "food"


def test_policy_refuses_a_bad_box_and_a_text_distance(tmp_path: Path) -> None:
    """Each disagreeing policy shape raises the same named reason."""
    text = _POLICY.read_text(encoding="utf-8")
    box = "frame_box:\n  west: 50.7\n  south: 24.4\n  east: 51.7\n  north: 26.2\n"
    cases = {
        "not-a-box.yaml": text.replace(box, "frame_box: nope\n"),
        "bad-west.yaml": text.replace("west: 50.7", "west: nope", 1),
        "moved-west.yaml": text.replace("west: 50.7", "west: 1.0", 1),
        "text-distance.yaml": text.replace("distance_m: 50", 'distance_m: "nope"', 1),
    }
    for name, body in cases.items():
        path = tmp_path / name
        path.write_text(body, encoding="utf-8")
        assert _reason(lambda path=path: assert_policy(path)) == "policy_disagrees"


def _footer(payload: bytes) -> bytes:
    return b"PAR1" + payload + struct.pack("<I", len(payload)) + b"PAR1"


def test_each_unreadable_footer_names_the_reason() -> None:
    """Every refusal of a summary names metadata_unreadable, including a bool bbox."""
    assert _reason(lambda: read_summary(b"short")) == "metadata_unreadable"
    assert _reason(lambda: read_summary(_footer(b""))) == "metadata_unreadable"
    assert (
        _reason(
            lambda: read_summary(b"PAR1" + b"\x00" + struct.pack("<I", 1) + b"XXXX")
        )
        == "metadata_unreadable"
    )
    assert (
        _reason(lambda: read_summary(_footer(bytes([0x05]) + bytes([0x80]) * 11)))
        == "metadata_unreadable"
    )
    assert (
        _reason(lambda: read_summary(_footer(bytes([0x18, 50]))))
        == "metadata_unreadable"
    )
    assert (
        _reason(lambda: read_summary(_footer(bytes([0x1D])))) == "metadata_unreadable"
    )
    assert (
        _reason(
            lambda: metadata_bytes(
                ({"file_path": 1, "longitude": (1.0, 2.0), "latitude": (3.0, 4.0)},),
                dataset_geo_bbox=None,
            )
        )
        == "metadata_unreadable"
    )
    assert (
        _reason(
            lambda: metadata_bytes(
                (
                    {
                        "file_path": "a.parquet",
                        "longitude": (1.0,),
                        "latitude": (3.0, 4.0),
                    },
                ),
                dataset_geo_bbox=None,
            )
        )
        == "metadata_unreadable"
    )
    assert footer_four([True, 2, 3, 4]) is None
    assert footer_four([1, 2, 3]) is None
    assert footer_four([1, 2, 3, 4]) == (1.0, 2.0, 3.0, 4.0)
    assert footer_bbox('{"columns":{"geometry":{}},"bbox":[1,2,3,4]}') == (
        1.0,
        2.0,
        3.0,
        4.0,
    )
    assert footer_bbox('{"bbox":[9,8,7,6]}') == (9.0, 8.0, 7.0, 6.0)
    body = metadata_bytes(
        (
            {
                "file_path": "near.parquet",
                "longitude": (51.0, 51.4),
                "latitude": (25.0, 25.6),
                "geo_bbox": (50.0, 24.0, 52.0, 27.0),
            },
        ),
        dataset_geo_bbox=(49.0, 23.0, 53.0, 28.0),
    )
    # Keep the original hash as the exact legacy fixture, without column orders.
    payload = body[4:-8]
    assert payload[-9:-1] == b"\x19\x2c\x1c\x00\x00\x1c\x00\x00"
    legacy_payload = payload[:-9] + b"\x00"
    legacy = b"PAR1" + legacy_payload + struct.pack("<I", len(legacy_payload)) + b"PAR1"
    assert (
        hashlib.sha256(legacy).hexdigest()
        == "0c4d72f1c0f0db4894678db318e0e09cb25ea9553cc5860c67ae1314553b3629"
    )
    selected = select_partitions(body, release="2025-01-10", frame=FRAME_BOX)
    assert selected.files == ("near.parquet",)
    assert selected.ignored_geo == (
        IgnoredGeo("", (49.0, 23.0, 53.0, 28.0)),
        IgnoredGeo("near.parquet", (50.0, 24.0, 52.0, 27.0)),
    )


def _source_row(
    lon: float,
    lat: float,
    *,
    country: object = "QA",
    refreshed: object = "2024-06-01",
    closed: object = None,
    categories: object = None,
    labels: object = None,
    geometry: object | None = None,
) -> ParsedRow:
    point = struct.pack("<BIdd", 1, 1, lon, lat) if geometry is None else geometry
    return _row(
        {
            "fsq_place_id": "abcdabcdabcdabcdabcd00aa",
            "name": "Invented Cafe",
            "longitude": lon,
            "latitude": lat,
            "country": country,
            "date_created": "2020-01-02",
            "date_refreshed": refreshed,
            "date_closed": closed,
            "fsq_category_ids": [] if categories is None else categories,
            "fsq_category_labels": [] if labels is None else labels,
            "geometry": point,
        }
    )


def test_parser_edges_match_the_written_results() -> None:
    """Bounds are closed. A big-endian point is read. A short point is refused."""
    _local(Path("HTTP-note"))
    assert _reason(lambda: _local(Path("http-note"))) == "remote_path"
    assert _reason(lambda: _local(Path("http://example/places"))) == "remote_path"
    columns = {
        name: "VARCHAR"
        for name in (
            "fsq_place_id",
            "name",
            "latitude",
            "longitude",
            "country",
            "date_created",
            "date_refreshed",
            "date_closed",
            "fsq_category_ids",
            "fsq_category_labels",
            "geometry",
        )
    }
    columns["longitude"] = "DOUBLE"
    columns["latitude"] = "DOUBLE"
    columns["geometry"] = "BLOB"
    columns["fsq_category_ids"] = "VARCHAR[]"
    columns["fsq_category_labels"] = "VARCHAR[]"
    _schema(columns)
    assert _reason(lambda: _schema({**columns, "longitude": "VARCHAR"})) == "longitude"
    assert _reason(lambda: _schema({**columns, "latitude": "VARCHAR"})) == "latitude"
    assert _reason(lambda: _schema({**columns, "geometry": "VARCHAR"})) == "geometry"
    west = _source_row(50.7, 25.3)
    east = _source_row(51.7, 25.3)
    south = _source_row(51.5, 24.4)
    north = _source_row(51.5, 26.2)
    kept = account_rows((west, east, south, north), FRAME_BOX)
    assert kept.kept == (west, east, south, north)
    assert kept.point_not_country == 0
    assert kept.country_not_point == 0
    outside = _source_row(50.6, 25.3)
    missed = account_rows((outside,), FRAME_BOX)
    assert missed.kept == ()
    assert missed.country_not_point == 1
    _range(-180.0, (-180.0, 180.0), "longitude")
    _range(180.0, (-180.0, 180.0), "longitude")
    assert _reason(lambda: _range(-180.1, (-180.0, 180.0), "longitude")) == "longitude"
    assert _reason(lambda: _range(180.1, (-180.0, 180.0), "longitude")) == "longitude"
    assert _reason(lambda: _float(True, "longitude")) == "longitude"
    assert _reason(lambda: _source_row(51.5, 25.3, country=1)) == "country"
    assert (
        _reason(lambda: _source_row(51.5, 25.3, refreshed="not-a-date"))
        == "date_refreshed"
    )
    assert _reason(lambda: _source_row(51.5, 25.3, closed=5)) == "date_closed"
    assert _reason(lambda: _source_row(51.5, 25.3, categories="nope")) == "category_ids"
    assert _categories(["alpha", "beta"], ["one", "two"]) == ("alpha;beta", "one;two")
    assert _close(51.5, 51.5 + 5e-8) is True
    assert _close(180.0, 180.0 + 1.5e-7) is False
    slipped = struct.pack("<BIdd", 1, 1, 51.5 + 5e-8, 25.3)
    parsed = _source_row(51.5, 25.3, geometry=slipped)
    assert parsed.lon == Decimal("51.500000")
    big = bytes([0]) + struct.pack(">Idd", 1, 51.5, 25.3)
    assert _wkb_point(big) == (51.5, 25.3)
    flagged = struct.pack("<BI", 1, 1 | 0x20000000) + b"\x00" * 16
    assert _reason(lambda: _wkb_point(flagged)) == "geometry"
    assert _reason(lambda: _wkb_point([0] * 21)) == "geometry"
    lone = struct.pack("<BIdd", 1, 1, 51.5, 25.4)
    assert _reason(lambda: _source_row(51.5, 25.3, geometry=lone)) == "geometry"
    partial = struct.pack("<BIdd", 1, 1, 25.3, 25.3)
    assert _reason(lambda: _source_row(51.5, 25.3, geometry=partial)) == "geometry"
    assert _reason(lambda: _source_row(200.0, 25.3)) == "longitude"
    assert _reason(lambda: _source_row(51.5, 95.0)) == "latitude"
    assert (
        _reason(lambda: _source_row(51.5, 25.3, categories=[1], labels=["one"]))
        == "category_ids"
    )
    be_srid = (
        bytes([0])
        + struct.pack(">II", 1 | 0x20000000, 0)
        + struct.pack(">dd", 51.5, 25.3)
    )
    assert _wkb_point(be_srid) == (51.5, 25.3)
    assert (
        _reason(lambda: _wkb_point(bytes([2]) + struct.pack("<Idd", 1, 51.5, 25.3)))
        == "geometry"
    )
    assert (
        _reason(lambda: _wkb_point(struct.pack("<BIdd", 1, 2, 51.5, 25.3)))
        == "geometry"
    )

    def _bad(**changed: object) -> str:
        item: dict[str, object] = {
            "fsq_place_id": "abcdabcdabcdabcdabcd00aa",
            "name": "Invented Cafe",
            "longitude": 51.5,
            "latitude": 25.3,
            "country": "QA",
            "date_created": "2020-01-02",
            "date_refreshed": "2024-06-01",
            "date_closed": None,
            "fsq_category_ids": [],
            "fsq_category_labels": [],
            "geometry": struct.pack("<BIdd", 1, 1, 51.5, 25.3),
        }
        item.update(changed)
        return _reason(lambda: _row(item))

    assert _bad(fsq_place_id="") == "fsq_place_id"
    assert _bad(longitude="bad") == "longitude"
    assert _bad(latitude="bad") == "latitude"
