"""Declared row-count, schema and period checks for one fetched body."""

from __future__ import annotations

import math
from dataclasses import dataclass

from eii_custodian.publicdata.fetch.registry import FEATURE_POLYGON_SOURCES, Entry

# Rows whose reviewed shape is closed: a field the registry does not declare is
# refused. Only a row corrected by a source review joins this set (S2-T08 part B
# source review, mismatch 6); every other row keeps the open check below.
CLOSED_SHAPE_KEYS = frozenset({"price_ext/machinery-and-equipment-price-index-mepi"})


@dataclass(frozen=True)
class AttemptFailure:
    """A fetch that must not be stored. expected and observed name the compared values."""

    code: int
    url: str
    check: str
    expected: str
    observed: str


def count_failure(
    entry: Entry, rows: list[object] | None, url: str
) -> AttemptFailure | None:
    """Fail when the row count is missing or outside the declared range."""
    if entry.row_count_min is None and entry.row_count_max is None:
        return None
    return count_value_failure(entry, None if rows is None else len(rows), url)


def count_value_failure(
    entry: Entry, count: int | None, url: str
) -> AttemptFailure | None:
    """The same count gate for row streams, without retaining their records."""
    if entry.row_count_min is None and entry.row_count_max is None:
        return None
    span = _count_span(entry)
    if count is None:
        return AttemptFailure(1, url, "row_count", span, "unreadable")
    if entry.row_count_min is not None and count < entry.row_count_min:
        return AttemptFailure(1, url, "row_count", span, str(count))
    if entry.row_count_max is not None and count > entry.row_count_max:
        return AttemptFailure(1, url, "row_count", span, str(count))
    return None


def schema_failure(
    entry: Entry, rows: list[object] | None, url: str
) -> AttemptFailure | None:
    """Fail when any row lacks a declared field or gives it the wrong type."""
    if not entry.columns:
        return None
    if not rows:
        return AttemptFailure(1, url, "schema_missing", entry.columns[0][0], "missing")
    for record in rows:
        if not isinstance(record, dict):
            return AttemptFailure(
                1, url, "schema_missing", entry.columns[0][0], "missing"
            )
        if entry.key in CLOSED_SHAPE_KEYS:
            declared = {name for name, _kind in entry.columns}
            for name in record:
                if name not in declared:
                    return AttemptFailure(1, url, "extra_field", "declared", str(name))
        for name, kind in entry.columns:
            if (
                kind == "geojson_feature_polygon"
                and entry.source_id not in FEATURE_POLYGON_SOURCES
            ):
                return AttemptFailure(
                    1, url, "declaration_scope", f"{name}:{kind}", entry.source_id
                )
            if name not in record:
                return AttemptFailure(1, url, "schema_missing", name, "missing")
            if not _type_ok(record[name], kind):
                return AttemptFailure(
                    1, url, "schema_retyped", f"{name}:{kind}", _seen_type(record[name])
                )
    return None


def period_failure(
    entry: Entry, rows: list[object] | None, url: str
) -> AttemptFailure | None:
    """Fail when the latest period is earlier than the registry records.

    ``published_label`` has no canonical period. A recorded last label is not
    parsed or ordered: the attempt fails only when that exact label is absent.
    """
    if entry.period_field == "" or entry.period_last == "":
        return None
    if "form=" in entry.period_field:
        return _ruled_period_failure(entry, rows, url)
    if not rows:
        return AttemptFailure(1, url, "period_last", entry.period_last, "unreadable")
    observed: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            return AttemptFailure(
                1, url, "period_last", entry.period_last, "unreadable"
            )
        value = row.get(entry.period_field)
        if not isinstance(value, str):
            return AttemptFailure(
                1, url, "period_last", entry.period_last, "unreadable"
            )
        observed.append(value)
    latest = max(observed)
    if latest < entry.period_last:
        return AttemptFailure(1, url, "period_last", entry.period_last, latest)
    return None


def _ruled_period_failure(
    entry: Entry, rows: list[object] | None, url: str
) -> AttemptFailure | None:
    """Compare a closed period rule with the rows. A modified date is not a period."""
    from eii_custodian.publicdata.additions.common import (
        FIELD_UNCONFIRMED,
        AdditionError,
        observe_period_bounds,
        parse_period_rule,
    )

    try:
        rule = parse_period_rule(entry.period_field)
        if rule.form == "published_label":
            return _published_label_failure(entry, rows, url, rule.field)
        if rule.field == FIELD_UNCONFIRMED:
            return None
        _first, last = observe_period_bounds(rows or [], rule)
    except AdditionError as error:
        return AttemptFailure(1, url, error.name, entry.period_last, error.name)
    if last < entry.period_last:
        return AttemptFailure(1, url, "period_last", entry.period_last, last)
    return None


def _published_label_failure(
    entry: Entry, rows: list[object] | None, url: str, field: str
) -> AttemptFailure | None:
    """Fail when no fetched row carries the recorded last label.

    The label is matched exactly in the row's own field. It is not parsed,
    ordered or compared with another label. A missing or empty label is left
    for the refusal that already names it.
    """
    if rows is None:
        return AttemptFailure(1, url, "period_label", entry.period_last, "absent")
    gap = False
    for row in rows:
        if not isinstance(row, dict) or field not in row:
            gap = True
            continue
        value = row[field]
        if value is None or value == "":
            gap = True
            continue
        if value == entry.period_last:
            return None
    if gap:
        return None
    return AttemptFailure(1, url, "period_label", entry.period_last, "absent")


def _count_span(entry: Entry) -> str:
    """Return the declared row-count range as low..high."""
    low = "" if entry.row_count_min is None else str(entry.row_count_min)
    high = "" if entry.row_count_max is None else str(entry.row_count_max)
    return f"{low}..{high}"


def _seen_type(value: object) -> str:
    """Return a type name for a mismatched field. The cell value is not included."""
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    return "other"


def _type_ok(value: object, kind: str) -> bool:
    if value is None:
        return True
    if kind == "string":
        return isinstance(value, str)
    if kind == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if kind == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if kind == "object":
        return isinstance(value, dict)
    if kind == "point_2d":
        return isinstance(value, dict) and all(
            _type_ok(value.get(axis), "number") for axis in ("lon", "lat")
        )
    if kind == "geojson_geometry":
        return (
            isinstance(value, dict)
            and value.get("type") in ("Polygon", "MultiPolygon")
            and isinstance(value.get("coordinates"), list)
        )
    if kind == "geojson_feature_polygon":
        return _feature_polygon(value)
    return False


def _feature_polygon(value: object) -> bool:
    """A closed GeoJSON Feature whose geometry is a Polygon or MultiPolygon.

    S2-T08 part B, mismatch class 4. The Feature holds exactly ``type``,
    ``geometry`` and ``properties`` (an object or null); the geometry holds
    exactly ``type`` and ``coordinates``, nested to its type's depth, each ring a
    non-empty list of positions of two or three finite numbers.
    """
    if not isinstance(value, dict) or set(value) != {"type", "geometry", "properties"}:
        return False
    if value["type"] != "Feature":
        return False
    if value["properties"] is not None and not isinstance(value["properties"], dict):
        return False
    geometry = value["geometry"]
    if not isinstance(geometry, dict) or set(geometry) != {"type", "coordinates"}:
        return False
    coordinates = geometry["coordinates"]
    if geometry["type"] == "Polygon":
        return _polygon(coordinates)
    if geometry["type"] == "MultiPolygon":
        return (
            isinstance(coordinates, list)
            and len(coordinates) > 0
            and all(_polygon(polygon) for polygon in coordinates)
        )
    return False


def _polygon(rings: object) -> bool:
    return (
        isinstance(rings, list)
        and len(rings) > 0
        and all(
            isinstance(ring, list)
            and len(ring) > 0
            and all(_position(point) for point in ring)
            for ring in rings
        )
    )


def _position(point: object) -> bool:
    return (
        isinstance(point, list)
        and len(point) in (2, 3)
        and all(
            isinstance(axis, (int, float))
            and not isinstance(axis, bool)
            and math.isfinite(axis)
            for axis in point
        )
    )
