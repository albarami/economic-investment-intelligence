"""Invented Public feature positions: membership belongs to the server."""

from decimal import Decimal

import pytest
from product.tests.make_area_support import (
    INSIDE_RING,
    NO_CELL,
    SHAPE_INSIDE,
    RecordingStore,
    box_route,
    context,
    geometry_rows,
)

from eii_product.store.registry import PACKAGED
from eii_product.tools.make_area import make_area


def test_p5_polygon_membership_includes_edges_and_vertices() -> None:
    # Points use the core's latitude/longitude order, not GeoJSON order.
    points = (
        ("edge", Decimal("0.005"), Decimal("0")),
        ("vertex", *INSIDE_RING[2]),
        ("inside", Decimal("0"), Decimal("0")),
        ("outside", Decimal("0.02"), Decimal("0.02")),
    )
    result = make_area(
        RecordingStore(PACKAGED, geometry_rows()),
        {"shape_id": SHAPE_INSIDE},
        context(PACKAGED, public_points={"public_places": points}),
    )
    assert result.status == "OK"
    assert result.payload["point_feature_ids"] == {
        "public_places": ["edge", "inside", "vertex"]
    }


@pytest.mark.parametrize("mode", ["distance", "walk", "drive"])
def test_membership_uses_returned_outline_even_without_base_cell(mode: str) -> None:
    lat, lon = NO_CELL
    result = make_area(
        RecordingStore(PACKAGED, geometry_rows()),
        {
            "latitude": lat,
            "longitude": lon,
            "mode": mode,
            "cutoff": 250 if mode == "distance" else 5,
        },
        context(
            PACKAGED,
            routing=box_route,
            public_points={
                "public_places": (("inside", lat, lon), ("outside", lat + 1, lon + 1)),
                "health_centres": (),
            },
        ),
    )
    assert result.status == "OK"
    assert result.payload["record"]["anchor_cell"] is None
    assert result.payload["point_feature_ids"] == {
        "health_centres": [],
        "public_places": ["inside"],
    }


def test_missing_point_snapshot_is_unavailable_not_an_empty_result() -> None:
    result = make_area(
        RecordingStore(PACKAGED, geometry_rows()),
        {"shape_id": SHAPE_INSIDE},
        context(PACKAGED),
    )
    assert result.payload["point_feature_ids"] is None
