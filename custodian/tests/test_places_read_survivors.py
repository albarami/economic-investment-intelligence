"""Mutation survivors for custodian/src/eii_custodian/publicdata/places/read.py.

Each test targets one or more survived mutants from the mutation campaign.
New tests only - no changes to existing code.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from custodian.tests.fixtures.places.invented import (
    building_row,
    place_row,
    write_buildings,
    write_places,
)

from eii_custodian.publicdata.places import PlacesError
from eii_custodian.publicdata.places.read import (
    FileReceipt,
    ReadPlace,
    _building_row,
    _column_names,
    _connect,
    _place_row,
    _require_schema,
    axes_look_swapped,
    geometry_wkb,
    read_building_file,
    read_place_file,
    record_level_source,
    require_receipt,
    stored_confidence,
)

# =============================================================================
# record_level_source survivors
# =============================================================================


def test_record_level_source_non_list_returns_absent() -> None:
    """Non-list sources returns RecordLevel(None, 'absent')."""
    result = record_level_source(None)
    assert result.reason == "absent"
    assert result.entry is None


def test_record_level_source_empty_list_returns_absent() -> None:
    """Empty list returns RecordLevel(None, 'absent')."""
    result = record_level_source([])
    assert result.reason == "absent"
    assert result.entry is None


def test_record_level_source_no_empty_property_returns_absent() -> None:
    """List with no empty property returns RecordLevel(None, 'absent')."""
    sources = [
        {"property": "names", "dataset": "syn-1"},
        {"property": "address", "dataset": "syn-2"},
    ]
    result = record_level_source(sources)
    assert result.reason == "absent"
    assert result.entry is None


def test_record_level_source_one_empty_property_returns_ok() -> None:
    """List with exactly one empty property returns RecordLevel(entry, 'ok')."""
    sources = [
        {"property": "", "dataset": "syn-1"},
    ]
    result = record_level_source(sources)
    assert result.reason == "ok"
    assert result.entry == {"property": "", "dataset": "syn-1"}


def test_record_level_source_two_empty_properties_returns_not_unique() -> None:
    """List with two empty properties returns RecordLevel(None, 'not_unique')."""
    sources = [
        {"property": "", "dataset": "syn-1"},
        {"property": None, "dataset": "syn-2"},
    ]
    result = record_level_source(sources)
    assert result.reason == "not_unique"
    assert result.entry is None


def test_record_level_source_none_property_returns_ok() -> None:
    """Property value of None is considered empty."""
    sources = [
        {"property": None, "dataset": "syn-1"},
    ]
    result = record_level_source(sources)
    assert result.reason == "ok"
    assert result.entry == {"property": None, "dataset": "syn-1"}


def test_record_level_source_whitespace_only_property_is_empty() -> None:
    """Property with whitespace only IS considered empty."""
    sources = [
        {"property": "  ", "dataset": "syn-1"},
    ]
    result = record_level_source(sources)
    assert result.reason == "ok"
    assert result.entry == {"property": "  ", "dataset": "syn-1"}


# =============================================================================
# stored_confidence survivors
# =============================================================================


def test_stored_confidence_decimal_finite() -> None:
    """Finite Decimal uses format(value, 'f')."""
    result = stored_confidence(Decimal("0.123456"))
    # format(Decimal('0.123456'), 'f') gives '0.123456'
    # Then quantized to 4 decimal places: 0.1235 (half to even)
    assert result == Decimal("0.1235")


def test_stored_confidence_decimal_needs_rounding() -> None:
    """Decimal that needs rounding is rounded to 4 decimal places."""
    result = stored_confidence(Decimal("0.12345"))
    # 0.12345 rounds to 0.1234 (half to even, 4 is even)
    assert result == Decimal("0.1234")


def test_stored_confidence_decimal_needs_rounding_up() -> None:
    """Decimal that needs rounding up is rounded to 4 decimal places."""
    result = stored_confidence(Decimal("0.12346"))
    # 0.12346 rounds to 0.1235 (6 > 5)
    assert result == Decimal("0.1235")


def test_stored_confidence_float() -> None:
    """Float value uses str(value)."""
    result = stored_confidence(0.123456)
    # str(0.123456) gives '0.123456'
    # Quantized to 4 decimal places
    assert result == Decimal("0.1235")


def test_stored_confidence_int() -> None:
    """Int value uses str(value)."""
    result = stored_confidence(1)
    assert result == Decimal("1.0000")


def test_stored_confidence_rounding_half_even() -> None:
    """Rounding mode is half to even."""
    # 0.12345 -> rounds to 0.1234 or 0.1235?
    # With half-to-even: 0.12345 -> 0.1234 (4 is even)
    result = stored_confidence(0.12345)
    assert result == Decimal("0.1234")


def test_stored_confidence_rounding_half_even_up() -> None:
    """Rounding mode is half to even - round up when odd."""
    # 0.12355 -> rounds to 0.1236 (6 is even)
    result = stored_confidence(0.12355)
    assert result == Decimal("0.1236")


# =============================================================================
# require_receipt survivors
# =============================================================================


def test_require_receipt_missing_raises_receipt_missing(tmp_path: Path) -> None:
    """Missing receipt raises PlacesError with 'receipt_missing'."""
    path = tmp_path / "test.parquet"
    path.write_text("dummy", encoding="utf-8")
    with pytest.raises(PlacesError) as exc_info:
        require_receipt(path, None)
    # KILLS: mutations that change "receipt_missing" error message
    assert exc_info.value.args[0] == "receipt_missing"


def test_require_receipt_none_raises_receipt_missing(tmp_path: Path) -> None:
    """None receipt raises PlacesError with 'receipt_missing'."""
    path = tmp_path / "test.parquet"
    path.write_text("dummy", encoding="utf-8")
    with pytest.raises(PlacesError) as exc_info:
        require_receipt(path, None)
    assert exc_info.value.args[0] == "receipt_missing"


def test_require_receipt_incomplete_raises_receipt_missing(tmp_path: Path) -> None:
    """Incomplete receipt raises PlacesError with 'receipt_missing'."""
    path = tmp_path / "test.parquet"
    path.write_text("dummy", encoding="utf-8")
    # Incomplete receipt (empty strings)
    incomplete = FileReceipt("", "", "", "")
    with pytest.raises(PlacesError) as exc_info:
        require_receipt(path, incomplete)
    assert exc_info.value.args[0] == "receipt_missing"


def test_require_receipt_hash_mismatch_raises_receipt_mismatch(tmp_path: Path) -> None:
    """Hash mismatch raises PlacesError with 'receipt_mismatch'."""
    path = tmp_path / "test.parquet"
    path.write_text("dummy", encoding="utf-8")
    # Receipt with wrong hash
    wrong = FileReceipt(
        "test",
        "0000000000000000000000000000000000000000000000000000000000000000",
        "2026-11-14T00:00:00Z",
        "SYN",
    )
    with pytest.raises(PlacesError) as exc_info:
        require_receipt(path, wrong)
    # KILLS: mutations that change "receipt_mismatch" error message
    assert exc_info.value.args[0] == "receipt_mismatch"


def test_require_receipt_valid_returns_receipt(tmp_path: Path) -> None:
    """Valid receipt with matching hash returns the receipt."""
    from custodian.tests.fixtures.places.invented import receipt_for

    path = tmp_path / "test.parquet"
    path.write_text("dummy content", encoding="utf-8")
    receipt = receipt_for(path, source_key="test")
    result = require_receipt(path, receipt)
    assert result == receipt


# =============================================================================
# read_place_file survivors
# =============================================================================


def test_read_place_file_empty_arabic_tag_raises_arabic_tag(tmp_path: Path) -> None:
    """Empty arabic_tag raises PlacesError with 'arabic_tag'."""
    path = tmp_path / "places.parquet"
    write_places(path, [place_row()])
    with pytest.raises(PlacesError) as exc_info:
        read_place_file(path, "")
    # KILLS: mutations that change "arabic_tag" error message
    assert exc_info.value.args[0] == "arabic_tag"


def test_read_place_file_whitespace_arabic_tag_raises_arabic_tag(
    tmp_path: Path,
) -> None:
    """Whitespace-only arabic_tag raises PlacesError with 'arabic_tag'."""
    path = tmp_path / "places.parquet"
    write_places(path, [place_row()])
    with pytest.raises(PlacesError) as exc_info:
        read_place_file(path, "   ")
    assert exc_info.value.args[0] == "arabic_tag"


def test_read_place_file_non_string_arabic_tag_raises_arabic_tag(
    tmp_path: Path,
) -> None:
    """Non-string arabic_tag raises PlacesError with 'arabic_tag'."""
    path = tmp_path / "places.parquet"
    write_places(path, [place_row()])
    wrong_tag: Any = 123
    with pytest.raises(PlacesError) as exc_info:
        read_place_file(path, wrong_tag)
    assert exc_info.value.args[0] == "arabic_tag"


def test_read_place_file_missing_column_raises_missing_column(tmp_path: Path) -> None:
    """Missing required column raises PlacesError with 'missing_column'."""
    path = tmp_path / "places.parquet"
    write_places(path, [place_row()], drop=("basic_category",))
    with pytest.raises(PlacesError) as exc_info:
        read_place_file(path, "ar")
    # KILLS: mutations that change "missing_column" error message
    assert exc_info.value.args[0] == "missing_column"


def test_read_place_file_wrong_schema_raises_schema_versions(tmp_path: Path) -> None:
    """Wrong schema version raises PlacesError with 'schema_versions'."""
    path = tmp_path / "places.parquet"
    write_places(path, [place_row()], schema_version="1.0.0")
    with pytest.raises(PlacesError) as exc_info:
        read_place_file(path, "ar")
    # KILLS: mutations that change "schema_versions" error message
    assert exc_info.value.args[0] == "schema_versions"


def test_read_place_file_no_schema_versions_raises_schema_versions(
    tmp_path: Path,
) -> None:
    """Missing schema_versions raises PlacesError with 'schema_versions'."""
    import duckdb

    path = tmp_path / "places.parquet"
    # Write a parquet without schema_versions
    connection = duckdb.connect()
    connection.execute("CREATE TABLE places (id VARCHAR, geometry BLOB)")
    connection.execute(
        "COPY places TO ? (FORMAT PARQUET)",
        [str(path)],
    )
    connection.close()

    conn = _connect()
    try:
        with pytest.raises(PlacesError) as exc_info:
            _require_schema(conn, path)
        assert exc_info.value.args[0] == "schema_versions"
    finally:
        conn.close()


def test_read_place_file_valid_returns_places(tmp_path: Path) -> None:
    """Valid place file returns ReadPlace tuples."""
    path = tmp_path / "places.parquet"
    write_places(path, [place_row()])
    result = read_place_file(path, "ar")
    assert len(result) == 1
    assert isinstance(result[0], ReadPlace)


# =============================================================================
# read_building_file survivors
# =============================================================================


def test_read_building_file_missing_column_raises_missing_column(
    tmp_path: Path,
) -> None:
    """Missing required column in building file raises PlacesError with 'missing_column'."""
    path = tmp_path / "buildings.parquet"
    ring = (
        (51.45, 25.25),
        (51.55, 25.25),
        (51.55, 25.35),
        (51.45, 25.35),
        (51.45, 25.25),
    )
    write_buildings(path, [building_row("SYN-B-1", ring)], drop=("geometry",))
    with pytest.raises(PlacesError) as exc_info:
        read_building_file(path)
    # KILLS: mutations that change "missing_column" error message in building context
    assert exc_info.value.args[0] == "missing_column"


def test_read_building_file_valid_returns_buildings(tmp_path: Path) -> None:
    """Valid building file returns ReadBuilding tuples."""
    path = tmp_path / "buildings.parquet"
    ring = (
        (51.45, 25.25),
        (51.55, 25.25),
        (51.55, 25.35),
        (51.45, 25.35),
        (51.45, 25.25),
    )
    write_buildings(path, [building_row("SYN-B-1", ring)])
    result = read_building_file(path)
    assert len(result) == 1


# =============================================================================
# _require_schema survivors
# =============================================================================


def test_require_schema_invalid_json_raises_schema_versions(tmp_path: Path) -> None:
    """Invalid JSON in schema_versions raises PlacesError with 'schema_versions'."""
    import duckdb

    path = tmp_path / "invalid.parquet"
    connection = duckdb.connect()
    connection.execute("CREATE TABLE t (id VARCHAR)")
    # Write invalid JSON as schema_versions
    connection.execute(
        "COPY t TO ? (FORMAT PARQUET, KV_METADATA {schema_versions: 'invalid json'})",
        [str(path)],
    )
    connection.close()

    conn = _connect()
    try:
        with pytest.raises(PlacesError) as exc_info:
            _require_schema(conn, path)
        assert exc_info.value.args[0] == "schema_versions"
    finally:
        conn.close()


def test_require_schema_not_dict_raises_schema_versions(tmp_path: Path) -> None:
    """schema_versions is not a dict raises PlacesError with 'schema_versions'."""
    import duckdb

    path = tmp_path / "not_dict.parquet"
    connection = duckdb.connect()
    connection.execute("CREATE TABLE t (id VARCHAR)")
    # schema_versions is a string, not a dict
    connection.execute(
        "COPY t TO ? (FORMAT PARQUET, KV_METADATA {schema_versions: 'not a dict'})",
        [str(path)],
    )
    connection.close()

    conn = _connect()
    try:
        with pytest.raises(PlacesError) as exc_info:
            _require_schema(conn, path)
        assert exc_info.value.args[0] == "schema_versions"
    finally:
        conn.close()


def test_require_schema_wrong_pyspark_version_raises_schema_versions(
    tmp_path: Path,
) -> None:
    """Wrong pyspark version raises PlacesError with 'schema_versions'."""
    import duckdb

    path = tmp_path / "wrong_version.parquet"
    connection = duckdb.connect()
    connection.execute("CREATE TABLE t (id VARCHAR)")
    # Wrong pyspark version
    connection.execute(
        'COPY t TO ? (FORMAT PARQUET, KV_METADATA {schema_versions: \'{"overture-schema-pyspark": "1.0.0"}\'})',
        [str(path)],
    )
    connection.close()

    conn = _connect()
    try:
        with pytest.raises(PlacesError) as exc_info:
            _require_schema(conn, path)
        assert exc_info.value.args[0] == "schema_versions"
    finally:
        conn.close()


# =============================================================================
# _place_row survivors
# =============================================================================


def test_place_row_non_point_geometry_raises_geometry_type() -> None:
    """Non-Point geometry raises PlacesError with 'geometry_type'."""
    import struct

    def line_wkb() -> bytes:
        # WKB for LineString with 2 points
        return (
            struct.pack("<BII", 1, 2, 2)
            + struct.pack("<dd", 0.0, 0.0)
            + struct.pack("<dd", 1.0, 1.0)
        )

    with pytest.raises(PlacesError) as exc_info:
        _place_row(("SYN-P-A", line_wkb(), 0.8, {}, [], "syn_cat"), "ar")
    # KILLS: mutations that change "geometry_type" error message
    assert exc_info.value.args[0] == "geometry_type"


def test_place_row_empty_place_id_raises_place_id() -> None:
    """Empty place_id raises PlacesError with 'place_id'."""
    from custodian.tests.fixtures.places.invented import point_wkb

    with pytest.raises(PlacesError) as exc_info:
        _place_row(("", point_wkb(0.0, 0.0), 0.8, {}, [], "syn_cat"), "ar")
    # KILLS: mutations that change "place_id" error message
    assert exc_info.value.args[0] == "place_id"


def test_place_row_non_string_place_id_raises_place_id() -> None:
    """Non-string place_id raises PlacesError with 'place_id'."""
    from custodian.tests.fixtures.places.invented import point_wkb

    with pytest.raises(PlacesError) as exc_info:
        _place_row((123, point_wkb(0.0, 0.0), 0.8, {}, [], "syn_cat"), "ar")
    assert exc_info.value.args[0] == "place_id"


def test_place_row_valid_returns_read_place() -> None:
    """Valid place row returns ReadPlace."""
    from custodian.tests.fixtures.places.invented import point_wkb

    result = _place_row(
        ("SYN-P-A", point_wkb(51.5, 25.3), 0.8, {"primary": "Test"}, [], "syn_cat"),
        "ar",
    )
    assert isinstance(result, ReadPlace)
    assert result.place_id == "SYN-P-A"


# =============================================================================
# _building_row survivors
# =============================================================================


def test_building_row_non_polygon_geometry_raises_geometry_type() -> None:
    """Non-Polygon/MultiPolygon geometry raises PlacesError with 'geometry_type'."""
    from custodian.tests.fixtures.places.invented import point_wkb

    with pytest.raises(PlacesError) as exc_info:
        _building_row(("SYN-B-1", point_wkb(0.0, 0.0)))
    # KILLS: mutations that change "geometry_type" error message
    assert exc_info.value.args[0] == "geometry_type"


def test_building_row_empty_building_id_raises_building_id() -> None:
    """Empty building_id raises PlacesError with 'building_id'."""
    from custodian.tests.fixtures.places.invented import polygon_wkb

    ring = ((0, 0), (1, 0), (1, 1), (0, 1), (0, 0))
    with pytest.raises(PlacesError) as exc_info:
        _building_row(("", polygon_wkb(ring)))
    assert exc_info.value.args[0] == "building_id"


def test_building_row_non_string_building_id_raises_building_id() -> None:
    """Non-string building_id raises PlacesError with 'building_id'."""
    from custodian.tests.fixtures.places.invented import polygon_wkb

    ring = ((0, 0), (1, 0), (1, 1), (0, 1), (0, 0))
    with pytest.raises(PlacesError) as exc_info:
        _building_row((123, polygon_wkb(ring)))
    assert exc_info.value.args[0] == "building_id"


# =============================================================================
# _column_names survivors
# =============================================================================


def test_column_names_returns_columns(tmp_path: Path) -> None:
    """_column_names returns column names from parquet file."""
    import duckdb

    path = tmp_path / "test.parquet"
    connection = duckdb.connect()
    connection.execute("CREATE TABLE t (ID VARCHAR, Geometry BLOB)")
    connection.execute("COPY t TO ? (FORMAT PARQUET)", [str(path)])
    connection.close()

    conn = _connect()
    try:
        result = _column_names(conn, path)
        # DuckDB DESCRIBE returns column names as they are
        assert "ID" in result or "id" in result
    finally:
        conn.close()


# =============================================================================
# _shape / geometry_wkb / geometry_bounds survivors
# =============================================================================


def test_geometry_wkb_returns_bytes() -> None:
    """geometry_wkb returns bytes for valid geometries."""
    from shapely.geometry import Point

    shape = Point(51.5, 25.3)
    result = geometry_wkb(shape)
    assert isinstance(result, bytes)


# =============================================================================
# axes_look_swapped / _refuse_swapped / _in_box survivors
# =============================================================================


def test_axes_look_swapped_empty_points(tmp_path: Path) -> None:
    """Empty points list does not look swapped."""
    from eii_custodian.publicdata.places.read import axes_look_swapped

    result = axes_look_swapped([], (0, 0, 1, 1))
    assert result is False


def test_axes_look_swapped_points_in_box(tmp_path: Path) -> None:
    """Points inside box do not look swapped."""
    from eii_custodian.publicdata.places.read import axes_look_swapped

    points = [(0.5, 0.5), (0.6, 0.6)]
    result = axes_look_swapped(points, (0, 0, 1, 1))
    assert result is False


def test_axes_look_swapped_swapped_points() -> None:
    """Points outside box but inside when swapped look swapped."""
    # We need points that are ALL outside the box as-is, but at least one is inside when swapped
    # Box: lon [50,60], lat [0,1]
    # Points: (0.5, 55) - lon=0.5 (outside [50,60]), lat=55 (outside [0,1])
    # When swapped: (55, 0.5) - lon=55 (inside [50,60]), lat=0.5 (inside [0,1]) - inside!
    box = (50.0, 0.0, 60.0, 1.0)
    points_swapped = [(0.5, 55.0)]
    result = axes_look_swapped(points_swapped, box)
    assert result is True


# =============================================================================
# _confidence survivors
# =============================================================================


def test_confidence_none_returns_null() -> None:
    """None confidence returns (None, 'null')."""
    from eii_custodian.publicdata.places.read import _confidence

    result = _confidence(None)
    assert result == (None, "null")


def test_confidence_bool_returns_null() -> None:
    """Bool confidence returns (None, 'null')."""
    from eii_custodian.publicdata.places.read import _confidence

    result = _confidence(True)
    assert result == (None, "null")


def test_confidence_string_returns_null() -> None:
    """String confidence returns (None, 'null')."""
    from eii_custodian.publicdata.places.read import _confidence

    result = _confidence("0.5")
    assert result == (None, "null")


def test_confidence_negative_returns_range() -> None:
    """Negative confidence returns (None, 'range')."""
    from eii_custodian.publicdata.places.read import _confidence

    result = _confidence(-0.5)
    assert result == (None, "range")


def test_confidence_greater_than_one_returns_range() -> None:
    """Confidence > 1 returns (None, 'range')."""
    from eii_custodian.publicdata.places.read import _confidence

    result = _confidence(1.5)
    assert result == (None, "range")


def test_confidence_decimal_infinite_returns_range() -> None:
    """Infinite Decimal confidence returns (None, 'range')."""
    from eii_custodian.publicdata.places.read import _confidence

    result = _confidence(Decimal("Infinity"))
    assert result == (None, "range")


def test_confidence_decimal_negative_infinite_returns_range() -> None:
    """Negative infinite Decimal confidence returns (None, 'range')."""
    from eii_custodian.publicdata.places.read import _confidence

    result = _confidence(Decimal("-Infinity"))
    assert result == (None, "range")


def test_confidence_float_infinite_returns_range() -> None:
    """Infinite float confidence returns (None, 'range')."""
    from eii_custodian.publicdata.places.read import _confidence

    result = _confidence(float("inf"))
    assert result == (None, "range")


def test_confidence_float_negative_infinite_returns_range() -> None:
    """Negative infinite float confidence returns (None, 'range')."""
    from eii_custodian.publicdata.places.read import _confidence

    result = _confidence(float("-inf"))
    assert result == (None, "range")


def test_confidence_zero_returns_positive_zero() -> None:
    """Zero confidence returns positive zero."""
    from eii_custodian.publicdata.places.read import _confidence

    result = _confidence(0)
    assert result[0] == Decimal("0.0000")
    assert result[1] == "ok"
    # Check it's positive zero
    assert result[0].is_zero()
    assert not result[0].is_signed()


def test_confidence_valid_decimal() -> None:
    """Valid Decimal confidence returns stored value."""
    from eii_custodian.publicdata.places.read import _confidence

    result = _confidence(Decimal("0.8"))
    assert result[0] == Decimal("0.8000")
    assert result[1] == "ok"


def test_confidence_valid_float() -> None:
    """Valid float confidence returns stored value."""
    from eii_custodian.publicdata.places.read import _confidence

    result = _confidence(0.8)
    assert result[0] == Decimal("0.8000")
    assert result[1] == "ok"


def test_confidence_valid_int() -> None:
    """Valid int confidence returns stored value."""
    from eii_custodian.publicdata.places.read import _confidence

    result = _confidence(1)
    assert result[0] == Decimal("1.0000")
    assert result[1] == "ok"
