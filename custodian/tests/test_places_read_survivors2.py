"""Second mutation pass for the local place and building readers."""

from __future__ import annotations

import json
from decimal import ROUND_UP, Decimal, localcontext
from pathlib import Path
from typing import Any

import pytest
import shapely
from custodian.tests.fixtures.places.invented import (
    building_row,
    point_wkb,
    polygon_wkb,
    receipt_for,
    write_buildings,
)
from shapely.geometry import MultiPolygon, Point, Polygon

from eii_custodian.publicdata.places import PlacesError
from eii_custodian.publicdata.places.read import (
    ReadPlace,
    _assert_axis,
    _building_row,
    _in_box,
    _place_row,
    _primary,
    _require_schema,
    _shape,
    _six,
    decode_wkb,
    geometry_bounds,
    geometry_wkb,
    load_boundary_buildings,
    read_building_file,
    record_level_source,
    require_receipt,
    stored_confidence,
    write_place_points,
)


def _any(value: object) -> Any:
    return value


def _assert_reason(info: pytest.ExceptionInfo[PlacesError], expected: str) -> None:
    assert info.value.args == (expected,)


class _Result:
    def __init__(self, rows: list[tuple[object, object]]) -> None:
        self._rows = rows

    def fetchall(self) -> list[tuple[object, object]]:
        return self._rows


class _Connection:
    def __init__(self, rows: list[tuple[object, object]]) -> None:
        self._rows = rows

    def execute(self, _query: str, _parameters: list[str]) -> _Result:
        return _Result(self._rows)


class _Bounds:
    def __init__(self, bounds: object) -> None:
        self.bounds = bounds


class _Wkb:
    def __init__(self, wkb: object) -> None:
        self.wkb = wkb


def _require_metadata(rows: list[tuple[object, object]]) -> None:
    _require_schema(_any(_Connection(rows)), Path("invented.parquet"))


def test_stored_confidence_non_finite_nan_stays_nan() -> None:
    assert stored_confidence(Decimal("NaN")).is_nan()


def test_stored_confidence_rounding_does_not_use_process_context() -> None:
    with localcontext() as context:
        context.rounding = ROUND_UP
        assert stored_confidence(Decimal("0.12345")) == Decimal("0.1234")


def test_six_rounding_does_not_use_process_context() -> None:
    with localcontext() as context:
        context.rounding = ROUND_UP
        assert _six(1.2342645) == Decimal("1.234264")


def test_schema_without_metadata_has_no_json_cause() -> None:
    with pytest.raises(PlacesError) as info:
        _require_metadata([("other", b"value")])
    _assert_reason(info, "schema_versions")
    assert info.value.__cause__ is None


def test_schema_accepts_text_keys_and_values() -> None:
    _require_metadata([("schema_versions", '{"overture-schema-pyspark":"2.0.0"}')])


def test_schema_ignores_unrelated_metadata_before_the_schema() -> None:
    _require_metadata(
        [
            (b"other", b"value"),
            (b"schema_versions", b'{"overture-schema-pyspark":"2.0.0"}'),
        ]
    )


def test_schema_rejects_a_json_non_mapping_with_exact_reason() -> None:
    with pytest.raises(PlacesError) as info:
        _require_metadata([(b"schema_versions", b"[]")])
    _assert_reason(info, "schema_versions")


def test_place_row_has_complete_independent_value() -> None:
    wkb = point_wkb(51.5, 25.3)
    result = _place_row(
        (
            "SYN-P-COMPLETE",
            wkb,
            0.8,
            {"primary": "SYN Cafe", "common": {"ar": "مقهى تجريبي"}},
            [{"property": "", "dataset": "syn-source"}],
            "syn_restaurant",
        ),
        "ar",
    )
    assert result == ReadPlace(
        place_id="SYN-P-COMPLETE",
        name="SYN Cafe",
        name_ar="مقهى تجريبي",
        category="syn_restaurant",
        lon=Decimal("51.500000"),
        lat=Decimal("25.300000"),
        confidence=Decimal("0.8000"),
        confidence_kind="ok",
        source=record_level_source([{"property": "", "dataset": "syn-source"}]),
        wkb=wkb,
    )


def test_building_row_accepts_multi_polygon_and_returns_its_wkb() -> None:
    shape = MultiPolygon([Polygon(((0, 0), (1, 0), (1, 1), (0, 1), (0, 0)))])
    result = _building_row(("SYN-B-MULTI", shape.wkb))
    assert result.building_id == "SYN-B-MULTI"
    assert result.lon == Decimal("0.500000")
    assert result.lat == Decimal("0.500000")
    assert result.footprint_wkb == shape.wkb


def test_building_row_refuses_a_non_point_surface_pin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "eii_custodian.publicdata.places.read.point_on_surface",
        lambda _shape: _any(object()),
    )
    ring = ((0, 0), (1, 0), (1, 1), (0, 1), (0, 0))
    with pytest.raises(PlacesError) as info:
        _building_row(("SYN-B-PIN", polygon_wkb(ring)))
    _assert_reason(info, "geometry_type")


def test_geometry_wkb_converts_memoryview() -> None:
    raw = point_wkb(1.0, 2.0)
    assert geometry_wkb(_any(_Wkb(memoryview(raw)))) == raw


def test_geometry_wkb_refuses_non_bytes_with_exact_reason() -> None:
    with pytest.raises(PlacesError) as info:
        geometry_wkb(_any(_Wkb("not-bytes")))
    _assert_reason(info, "geometry_wkb")


def test_geometry_bounds_rejects_a_four_item_list() -> None:
    with pytest.raises(PlacesError) as info:
        geometry_bounds(_any(_Bounds([1, 2, 3, 4])))
    _assert_reason(info, "axis_range")


def test_geometry_bounds_rejects_bad_bounds_with_exact_reason() -> None:
    with pytest.raises(PlacesError) as info:
        geometry_bounds(_any(_Bounds((1, 2, 3))))
    _assert_reason(info, "axis_range")


def test_geometry_bounds_preserves_coordinate_order() -> None:
    assert geometry_bounds(_any(_Bounds((1, 2, 3, 4)))) == (1.0, 2.0, 3.0, 4.0)


def test_decode_wkb_bad_bytes_has_exact_reason() -> None:
    with pytest.raises(PlacesError) as info:
        decode_wkb(b"not-wkb")
    _assert_reason(info, "geometry_wkb")


def test_decode_wkb_refuses_a_non_geometry_with_exact_reason(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(shapely, "from_wkb", lambda _value: object())
    with pytest.raises(PlacesError) as info:
        decode_wkb(b"input")
    _assert_reason(info, "geometry_wkb")


def test_shape_converts_memoryview() -> None:
    assert _shape(memoryview(point_wkb(3.0, 4.0))).equals(Point(3, 4))


def test_shape_refuses_non_bytes_with_exact_reason() -> None:
    with pytest.raises(PlacesError) as info:
        _shape("not-bytes")
    _assert_reason(info, "geometry_not_bytes")


@pytest.mark.parametrize("point", [Point(-180, -90), Point(180, 90)])
def test_axis_limits_are_inclusive(point: Point) -> None:
    _assert_axis(point)


@pytest.mark.parametrize(
    "point",
    [
        Point(-180.000001, 0),
        Point(180.000001, 0),
        Point(0, -90.000001),
        Point(0, 90.000001),
    ],
)
def test_axis_values_beyond_each_limit_have_exact_reason(point: Point) -> None:
    with pytest.raises(PlacesError) as info:
        _assert_axis(point)
    _assert_reason(info, "axis_range")


def test_primary_empty_fallbacks_are_empty_strings() -> None:
    assert _primary(None) == ""
    assert _primary({"primary": 7}) == ""


def test_arabic_marker_text_is_a_real_value() -> None:
    row = _place_row(
        (
            "SYN-P-MARKER",
            point_wkb(1, 2),
            None,
            {"common": {"ar": "XXXX"}},
            [],
            "syn",
        ),
        "ar",
    )
    assert row.name_ar == "XXXX"


def test_receipt_marker_text_is_not_an_empty_required_field(tmp_path: Path) -> None:
    path = tmp_path / "receipt.parquet"
    path.write_bytes(b"invented")
    receipt = receipt_for(path, source_key="XXXX")
    receipt = type(receipt)(receipt.source_key, receipt.sha256, "time", "XXXX")
    assert require_receipt(path, receipt) is receipt


def test_in_box_requires_both_coordinate_ranges() -> None:
    assert _in_box(5, 20, (0, 0, 10, 10)) is False


def test_building_axis_swap_is_refused_by_file_and_boundary_loader(
    tmp_path: Path,
) -> None:
    path = tmp_path / "swapped.parquet"
    ring = ((25.2, 51.4), (25.2, 51.6), (25.4, 51.6), (25.4, 51.4), (25.2, 51.4))
    write_buildings(path, [building_row("SYN-B-SWAP", ring)])
    boundary = Polygon(((50, 24), (52, 24), (52, 26), (50, 26), (50, 24)))
    with pytest.raises(PlacesError) as file_info:
        read_building_file(path, frame_box=(50, 24, 52, 26))
    _assert_reason(file_info, "axis_swapped")
    with pytest.raises(PlacesError) as loader_info:
        load_boundary_buildings([path], [receipt_for(path)], boundary)
    _assert_reason(loader_info, "axis_swapped")


def test_boundary_loader_receipt_count_mismatch_has_exact_reason() -> None:
    boundary = Polygon(((0, 0), (1, 0), (1, 1), (0, 1), (0, 0)))
    with pytest.raises(PlacesError) as info:
        load_boundary_buildings([Path("invented.parquet")], [], boundary)
    _assert_reason(info, "receipt_missing")


def test_boundary_loader_duplicate_id_has_exact_reason(tmp_path: Path) -> None:
    path = tmp_path / "duplicates.parquet"
    ring = ((0, 0), (1, 0), (1, 1), (0, 1), (0, 0))
    write_buildings(
        path,
        [building_row("SYN-B-DUP", ring), building_row("SYN-B-DUP", ring)],
    )
    boundary = Polygon(((-1, -1), (2, -1), (2, 2), (-1, 2), (-1, -1)))
    with pytest.raises(PlacesError) as info:
        load_boundary_buildings([path], [receipt_for(path)], boundary)
    _assert_reason(info, "building_duplicate")


def test_boundary_loader_counts_every_outside_footprint(tmp_path: Path) -> None:
    path = tmp_path / "outside.parquet"
    inside = ((0.1, 0.1), (0.2, 0.1), (0.2, 0.2), (0.1, 0.2), (0.1, 0.1))
    outside_a = ((10, 10), (11, 10), (11, 11), (10, 11), (10, 10))
    outside_b = ((20, 20), (21, 20), (21, 21), (20, 21), (20, 20))
    write_buildings(
        path,
        [
            building_row("SYN-B-IN", inside),
            building_row("SYN-B-OUT-A", outside_a),
            building_row("SYN-B-OUT-B", outside_b),
        ],
    )
    boundary = Polygon(((0, 0), (1, 0), (1, 1), (0, 1), (0, 0)))
    kept, receipts, outside = load_boundary_buildings(
        [path], [receipt_for(path)], boundary
    )
    assert [row.building_id for row in kept] == ["SYN-B-IN"]
    assert receipts == (receipt_for(path),)
    assert outside == 2


def test_write_place_points_has_exact_payload_and_is_repeatable(
    tmp_path: Path,
) -> None:
    directory = tmp_path / "absent" / "nested"
    arguments = (
        (("syn-place", "SYN-P-A", "51.500000", "25.300000"),),
        (("syn-building", "SYN-B-A", "51.600000", "25.400000"),),
    )
    write_place_points(directory, *arguments)
    write_place_points(directory, *arguments)
    target = directory / "places_s2_t06" / "place_points.json"
    assert target.read_text(encoding="utf-8") == (
        '[{"lat": "25.300000", "lon": "51.500000", '
        '"record_key": "SYN-P-A", "source_id": "syn-place"}, '
        '{"lat": "25.400000", "lon": "51.600000", '
        '"record_key": "SYN-B-A", "source_id": "syn-building"}]\n'
    )
    assert json.loads(target.read_text(encoding="utf-8"))[0]["lat"] == "25.300000"
