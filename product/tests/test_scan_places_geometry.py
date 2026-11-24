"""Exact outline tests on invented public candidates."""

from decimal import Decimal

import pytest
from product.tests.scan_places_support import fixture, records, replace_rows

from eii_product.tools.scan_places import scan_places


def test_exact_outline_decides():
    store, context, request, _ = fixture()
    row = records(store, "places")[0]
    replace_rows(
        store,
        "places",
        [dict(row, cell=999), dict(row, place_id="SYN-outside", lon=Decimal("0.01"))],
    )
    result = scan_places(store, request, context)
    assert [p.place_id for p in result.payload.places] == ["SYN-place"]


def test_area_identity_and_seat_refusals():
    store, context, request, routes = fixture()
    result = scan_places(store, dict(request, area_id="invalid"), context)
    assert result.status == "INVALID_ARGUMENT"
    assert not routes and not store.calls


def test_no_base_cell_uses_outline_only():
    from product.tests.make_area_support import NO_CELL

    from eii_product.tools.make_area import make_area

    store, context, request, _ = fixture()
    area = make_area(
        store,
        dict(latitude=NO_CELL[0], longitude=NO_CELL[1], mode="distance", cutoff=250),
        context.area,
    )
    assert area.payload["units"] == {}
    assert area.payload["record"]["anchor_cell"] is None
    row = records(store, "places")[0]
    replace_rows(
        store,
        "places",
        [
            dict(row, lat=NO_CELL[0], lon=NO_CELL[1], cell=999),
            dict(row, place_id="SYN-outside"),
        ],
    )
    result = scan_places(store, dict(request, area_id=area.payload["area_id"]), context)
    assert result.status == "OK"
    assert [p.place_id for p in result.payload.places] == ["SYN-place"]


@pytest.mark.parametrize(
    "plant", ["release", "cell", "canonical", "seat", "missing_shape"]
)
def test_invalid_area_never_reads_places_or_routes(plant):
    from product.tests.make_area_support import SHAPE_OTHER

    from eii_product.tools.areas import build_area_id

    store, context, request, routes = fixture()
    parts = request["area_id"].split("/")
    if plant == "release":
        parts[1] = "cd" * 8
    elif plant == "cell":
        parts[4] = "none"
    elif plant == "canonical":
        parts[5] = "-0.000000"
    if plant in {"seat", "missing_shape"}:
        area_id = build_area_id(
            release_id=context.area.release_id,
            shape_id=SHAPE_OTHER if plant == "seat" else "ab" * 32,
        )
    else:
        area_id = "/".join(parts)
    result = scan_places(store, dict(request, area_id=area_id), context)
    assert result.status == "INVALID_ARGUMENT"
    assert not routes
    assert not any(name.startswith("scan_places_") for name in store.calls)
    assert result.payload.outline is None


def test_polygon_edges_vertices_and_coordinate_order():
    from product.tests.make_area_support import SHAPE_INSIDE

    from eii_product.tools.make_area import make_area

    store, context, request, _ = fixture()
    # Asymmetric invented ring makes a lat/lon swap observable.
    ring = (
        (Decimal("0"), Decimal("0")),
        (Decimal("0"), Decimal("0.02")),
        (Decimal("0.001"), Decimal("0.02")),
        (Decimal("0.001"), Decimal("0")),
        (Decimal("0"), Decimal("0")),
    )
    context.area.shapes._rings[SHAPE_INSIDE] = ring
    area = make_area(store, dict(shape_id=SHAPE_INSIDE), context.area)
    assert area.status == "OK"
    base = records(store, "places")[0]
    replace_rows(
        store,
        "places",
        [
            dict(
                base, place_id="SYN-vertex", lat=Decimal("0.001"), lon=Decimal("0.02")
            ),
            dict(base, place_id="SYN-edge", lat=Decimal("0"), lon=Decimal("0.01")),
            dict(
                base, place_id="SYN-inside", lat=Decimal("0.0005"), lon=Decimal("0.01")
            ),
            dict(
                base, place_id="SYN-outside", lat=Decimal("0.01"), lon=Decimal("0.0005")
            ),
        ],
    )
    result = scan_places(store, dict(request, area_id=area.payload["area_id"]), context)
    assert result.status == "OK"
    assert {p.place_id for p in result.payload.places} == {
        "SYN-vertex",
        "SYN-edge",
        "SYN-inside",
    }


def test_circle_uses_analytic_boundary(monkeypatch):
    import eii_product.tools.scan_places as module
    from eii_core.shapes import exact_point

    calls = []

    def radius(origin, point, metres):
        calls.append((origin, point, metres))
        return True

    monkeypatch.setattr(module, "within_radius", radius)
    payload = dict(
        record=dict(shape="radius", request=dict(radius_m=250)),
        outline=dict(type="Circle"),
    )
    assert module._inside(
        dict(lat=Decimal("0.001"), lon=Decimal("0.002")), payload, exact_point(0, 0)
    )
    assert calls == [((0.0, 0.0), (0.001, 0.002), 250)]


def test_true_circle_edge_and_drawing_approximation():
    from eii_core.shapes import exact_point, great_circle_m
    from eii_product.tools.scan_places import _inside

    point = (0.001, 0.002)
    payload = dict(
        record=dict(
            shape="radius",
            request=dict(radius_m=great_circle_m((0.0, 0.0), point)),
        ),
        # Deliberately smaller drawing; the analytic radius owns selection.
        outline=dict(
            type="Polygon",
            coordinates=[[[0, 0], [0.0001, 0], [0, 0.0001], [0, 0]]],
        ),
    )
    assert _inside(dict(lat=point[0], lon=point[1]), payload, exact_point(0, 0))
    assert not _inside(dict(lat=0.01, lon=0.02), payload, exact_point(0, 0))
