"""Area record and area id. The schema checker is test-only."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from product.tests.make_area_support import (
    NO_CELL,
    ORIGIN,
    RELEASE_ID,
    SHAPE_INSIDE,
    RecordingStore,
    box_route,
    context,
    geometry_rows,
)

from eii_product.store.registry import PACKAGED
from eii_product.tools.areas import canonical_json
from eii_product.tools.make_area import INVALID_ARGUMENT, decode_area, make_area

_AREA_SCHEMA = next(
    (
        folder / "contracts" / "area.v1.schema.json"
        for folder in Path(__file__).resolve().parents
        if (folder / "contracts" / "area.v1.schema.json").is_file()
    ),
    None,
)
assert _AREA_SCHEMA is not None
SCHEMA = json.loads(_AREA_SCHEMA.read_text(encoding="utf-8"))


def _run(request: dict, **overrides):
    store = RecordingStore(PACKAGED, geometry_rows())
    return make_area(
        store, request, context(PACKAGED, routing=box_route, **overrides)
    ), store


def _pin(mode: str, cutoff: int, point=ORIGIN) -> dict:
    return {
        "latitude": float(point[0]),
        "longitude": float(point[1]),
        "mode": mode,
        "cutoff": cutoff,
    }


def test_area_id_is_readable_and_self_describing() -> None:
    distance, _store = _run(_pin("distance", 250))
    walk, _store = _run(_pin("walk", 5))
    drive, _store = _run(_pin("drive", 10))
    drawn, _store = _run({"shape_id": SHAPE_INSIDE})
    missing, _store = _run(_pin("distance", 500, NO_CELL))
    prefix = RELEASE_ID[:16]
    for result, mode, cutoff in (
        (distance, "distance", "250"),
        (walk, "walk", "5"),
        (drive, "drive", "10"),
    ):
        parts = result.payload["area_id"].split("/")
        assert parts[:4] == ["ma1", prefix, mode, cutoff]
        assert parts[4] == result.payload["record"]["anchor_cell"]
        assert parts[5] == "0.000000"
        assert parts[6] == "0.000000"
    assert drawn.payload["area_id"] == f"ma1/{prefix}/polygon/{SHAPE_INSIDE}"
    assert "/none/" in missing.payload["area_id"]


def test_decoding_reproduces_the_cells_and_the_outline() -> None:
    requests = (
        _pin("distance", 250),
        _pin("walk", 5),
        _pin("drive", 10),
        {"shape_id": SHAPE_INSIDE},
        _pin("distance", 1000, NO_CELL),
    )
    for request in requests:
        first, store = _run(request)
        second = decode_area(
            store, first.payload["area_id"], context(PACKAGED, routing=box_route)
        )
        assert second.payload["units"] == first.payload["units"]
        assert canonical_json(second.payload["outline"]) == canonical_json(
            first.payload["outline"]
        )


def test_same_request_twice_is_byte_identical() -> None:
    first, _store = _run(_pin("walk", 15))
    second, _store = _run(_pin("walk", 15))
    assert canonical_json(first.payload["record"]) == canonical_json(
        second.payload["record"]
    )
    assert first.payload["area_id"] == second.payload["area_id"]

    def unsorted(value) -> bytes:
        return json.dumps(value, default=str).encode("utf-8")

    def expect_canonical(serialise, record) -> None:
        assert serialise(record) == canonical_json(record)

    expect_canonical(canonical_json, first.payload["record"])
    with pytest.raises(AssertionError):
        expect_canonical(unsorted, first.payload["record"])


def test_area_record_matches_the_schema_per_shape() -> None:
    records = [
        _run(_pin("distance", 250))[0].payload["record"],
        _run(_pin("walk", 5))[0].payload["record"],
        _run(_pin("drive", 10))[0].payload["record"],
        _run({"shape_id": SHAPE_INSIDE})[0].payload["record"],
        _run(_pin("distance", 500, NO_CELL))[0].payload["record"],
    ]
    for record in records:
        assert _matches(record, SCHEMA)
    extra = dict(records[0])
    extra["note"] = "extra"
    protected = dict(records[0])
    protected["protected"] = {}
    counted = dict(records[4])
    counted["anchor_cell"] = records[0]["anchor_cell"]
    wrong_type = dict(records[4])
    wrong_type["anchor_cell"] = 3
    opened = dict(records[0])
    opened["requested_shape"] = dict(records[0]["requested_shape"])
    opened["requested_shape"]["extra"] = "plant"
    long_drive = dict(records[2])
    long_drive["request"] = dict(records[2]["request"])
    long_drive["request"]["minutes"] = 45
    for plant in (extra, protected, counted, wrong_type, opened, long_drive):
        with pytest.raises(AssertionError):
            assert _matches(plant, SCHEMA)
    both = {"oneOf": [{"type": "object"}, {"type": "object"}]}
    assert _matches({"shape": "polygon"}, both) is False


def test_refused_area_ids() -> None:
    good, store = _run(_pin("distance", 250))
    drive, _store = _run(_pin("drive", 10))
    foreign = good.payload["area_id"].replace(RELEASE_ID[:16], "ff" * 8, 1)
    malformed = "ma1/not-an-area"
    # A drive identifier, with the drive cut-off changed to 45 minutes.
    long_drive = drive.payload["area_id"].replace("/10/", "/45/")
    missing = good.payload["area_id"].replace("distance", "polygon").split("/")
    missing_shape = f"ma1/{RELEASE_ID[:16]}/polygon/{'9' * 64}"
    for area_id in (foreign, malformed, long_drive, missing_shape):
        result = decode_area(store, area_id, context(PACKAGED, routing=box_route))
        assert result.status == INVALID_ARGUMENT
        assert result.payload is None
    del missing


def test_area_id_grammar_refuses_a_malformed_or_inconsistent_id() -> None:
    good, store = _run(_pin("distance", 250))
    missing, _store = _run(_pin("distance", 500, NO_CELL))
    parts = good.payload["area_id"].split("/")
    altered = parts.copy()
    altered[4] = "2" if parts[4] == "1" else "1"
    spellings = (
        "/".join(altered),
        missing.payload["area_id"].replace("/none/", f"/{parts[4]}/"),
        good.payload["area_id"].replace(f"/{parts[4]}/", "/none/"),
    )
    for area_id in spellings:
        result = decode_area(store, area_id, context(PACKAGED, routing=box_route))
        assert result.status == INVALID_ARGUMENT
        assert result.payload is None
    taken = list(store.calls)
    latitude = parts.copy()
    for token in ("1.0e-6", "0.0000001", "00.000000"):
        latitude[5] = token
        result = decode_area(
            store, "/".join(latitude), context(PACKAGED, routing=box_route)
        )
        assert result.status == INVALID_ARGUMENT
        assert result.payload is None
    assert store.calls == taken


def _matches(value, schema) -> bool:
    """Schema keywords, then the named semantic rules they cannot express.

    ``oneOf`` matches exactly one branch.
    """
    if "oneOf" in schema:
        matched = sum(_matches(value, branch) for branch in schema["oneOf"])
        if matched != 1:
            return False
    if not _keywords(value, schema):
        return False
    return _semantics(value, schema)


def _keywords(value, schema) -> bool:
    if "const" in schema and value != schema["const"]:
        return False
    if "enum" in schema and value not in schema["enum"]:
        return False
    kind = schema.get("type")
    if kind == "object":
        if not isinstance(value, dict):
            return False
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False and set(value) - set(properties):
            return False
        for name in schema.get("required", []):
            if name not in value:
                return False
        for name, item in value.items():
            if name in properties and not _matches(item, properties[name]):
                return False
    elif kind == "string" and not isinstance(value, str):
        return False
    elif kind == "integer" and (isinstance(value, bool) or not isinstance(value, int)):
        return False
    return True


def _semantics(value, schema) -> bool:
    properties = schema.get("properties", {})
    if "area_id" in properties and "anchor_cell" in properties:
        if not anchor_cell_agrees_with_identifier(value):
            return False
    kind = properties.get("type", {}).get("const")
    if kind in ("Polygon", "Circle") and not requested_geometry_coordinates(value):
        return False
    return True


def anchor_cell_agrees_with_identifier(record: dict) -> bool:
    """``none`` agrees only with a null anchor. A cell string must be that cell.

    The schema can say the anchor is null or a string. It cannot tie that
    choice to the cell spelled in the area identifier.
    """
    parts = str(record.get("area_id", "")).split("/")
    if len(parts) == 4:
        return True
    if len(parts) != 7:
        return False
    anchor = record.get("anchor_cell")
    if parts[4] == "none":
        return anchor is None
    return anchor == parts[4]


def requested_geometry_coordinates(geometry: dict) -> bool:
    """Coordinate arrays are outside the permitted schema keywords."""
    coordinates = geometry.get("coordinates")
    if geometry.get("type") == "Circle":
        return _number_pair(coordinates)
    if geometry.get("type") != "Polygon":
        return False
    if type(coordinates) is not list or len(coordinates) != 1:
        return False
    ring = coordinates[0]
    if type(ring) is not list or len(ring) < 4 or ring[0] != ring[-1]:
        return False
    return all(_number_pair(point) for point in ring)


def _number_pair(value) -> bool:
    return (
        type(value) is list
        and len(value) == 2
        and _finite_number(value[0])
        and _finite_number(value[1])
    )


def _finite_number(value) -> bool:
    from decimal import Decimal

    if type(value) is bool:
        return False
    if type(value) is int:
        return True
    if type(value) is Decimal:
        return value.is_finite()
    if type(value) is float:
        return value == value and value not in (float("inf"), float("-inf"))
    return False
