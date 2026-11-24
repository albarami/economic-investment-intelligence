"""In-process engine seam; invented answers do not prove real graph routes."""

import pytest
import valhalla

from eii_product.tools import routing


def test_network_distance_is_not_straight_line(tmp_path, monkeypatch):
    (tmp_path / "config.json").write_text("{}")
    calls = []

    class Actor:
        def __init__(self, config):
            assert config == str(tmp_path / "config.json")

        def matrix(self, request):
            calls.append(request)
            return {"units": "kilometers", "sources_to_targets": [[{"distance": 2.75}]]}

    monkeypatch.setattr(valhalla, "Actor", Actor)
    for mode, costing in [("walk", "pedestrian"), ("drive", "auto")]:
        assert routing.network_distance(tmp_path, mode, (0.0, 0.0), (0.0, 0.001)) == (
            2.75,
            "kilometers",
        )
        assert calls[-1] == {
            "sources": [{"lat": 0.0, "lon": 0.0}],
            "targets": [{"lat": 0.0, "lon": 0.001}],
            "costing": costing,
            "costing_options": {costing: {"speed_types": []}},
            "units": "kilometers",
            "verbose": True,
        }


def test_engine_failure_is_closed(tmp_path, monkeypatch):
    (tmp_path / "config.json").write_text("{}")

    class Actor:
        def __init__(self, config):
            raise RuntimeError("SYN-engine-detail")

    monkeypatch.setattr(valhalla, "Actor", Actor)
    with pytest.raises(
        routing.RoutingTilesUnavailable, match=r"^routing tiles unavailable$"
    ) as caught:
        routing.network_distance(tmp_path, "walk", (0.0, 0.0), (0.0, 0.001))
    assert caught.value.__context__ is None


def test_all_unreachable_is_no_data():
    from dataclasses import replace

    from product.tests.scan_places_support import fixture

    from eii_product.tools.scan_places import scan_places

    store, context, request, _ = fixture()
    context = replace(context, route=lambda *args: (None, "kilometers"))
    result = scan_places(store, request, context)
    assert result.status == "NO_DATA" and not result.payload.places


def test_route_origin_mode_direction_period():
    from fractions import Fraction

    from product.tests.scan_places_support import fixture

    from eii_product.tools.scan_places import scan_places

    store, context, request, routes = fixture()
    result = scan_places(store, request, context)
    assert routes == [
        ("SYN-graph", "walk", (Fraction(0), Fraction(0)), (Fraction(0), Fraction(0)))
    ]
    assert next(f for f in result.facts if f.unit == "metres").period == context.period


@pytest.mark.parametrize("mode", ["distance", "walk", "drive", "shape"])
def test_distinct_route_endpoints_for_every_area(mode):
    from dataclasses import replace
    from decimal import Decimal

    from product.tests.make_area_support import INSIDE_RING, SHAPE_INSIDE, box_route
    from product.tests.scan_places_support import fixture, records, replace_rows

    from eii_core.shapes import canonical_ring, exact_point, representative_point
    from eii_product.tools.make_area import make_area
    from eii_product.tools.scan_places import scan_places

    store, context, request, routes = fixture()
    context = replace(context, area=replace(context.area, routing=box_route))
    arguments = (
        dict(shape_id=SHAPE_INSIDE)
        if mode == "shape"
        else dict(
            latitude=Decimal(0),
            longitude=Decimal(0),
            mode=mode,
            cutoff=250 if mode == "distance" else 5,
        )
    )
    area = make_area(store, arguments, context.area)
    assert area.status == "OK"
    destination = exact_point(Decimal("0.000001"), Decimal("0.000002"))
    replace_rows(
        store,
        "places",
        [
            dict(
                records(store, "places")[0],
                lat=Decimal("0.000001"),
                lon=Decimal("0.000002"),
            )
        ],
    )
    result = scan_places(store, dict(request, area_id=area.payload["area_id"]), context)
    assert result.status == "OK"
    origin = (
        representative_point(canonical_ring(INSIDE_RING))
        if mode == "shape"
        else exact_point(0, 0)
    )
    assert origin != destination
    assert routes == [
        (context.graph, "drive" if mode == "drive" else "walk", origin, destination)
    ]
    assert next(f for f in result.facts if f.unit == "metres").period == context.period


def test_unreachable_is_dropped():
    from dataclasses import replace
    from decimal import Decimal

    from product.tests.scan_places_support import fixture, records, replace_rows

    from eii_product.tools.scan_places import scan_places

    store, context, request, _ = fixture()
    row = records(store, "places")[0]
    replace_rows(
        store,
        "places",
        [row, dict(row, place_id="SYN-unreachable", lon=Decimal("0.001"))],
    )
    context = replace(
        context,
        route=lambda graph, mode, origin, dest: (None if dest[1] else 1, "kilometers"),
    )
    result = scan_places(store, request, context)
    assert result.status == "OK"
    assert [p.place_id for p in result.payload.places] == ["SYN-place"]


@pytest.mark.parametrize(
    "answer",
    [
        None,
        {},
        {"units": "miles"},
        {"units": "kilometers", "sources_to_targets": []},
        {"units": "kilometers", "sources_to_targets": [[{"distance": True}]]},
    ],
)
def test_invalid_matrix_answer_is_closed(tmp_path, monkeypatch, answer):
    (tmp_path / "config.json").write_text("{}")

    class Actor:
        def __init__(self, config):
            pass

        def matrix(self, request):
            return answer

    monkeypatch.setattr(valhalla, "Actor", Actor)
    with pytest.raises(
        routing.RoutingTilesUnavailable, match=r"^routing tiles unavailable$"
    ):
        routing.network_distance(tmp_path, "walk", (0.0, 0.0), (0.0, 0.001))


def test_handler_preserves_port_network_length():
    from dataclasses import replace
    from decimal import Decimal

    from product.tests.scan_places_support import fixture

    from eii_product.tools.scan_places import scan_places

    store, context, request, _ = fixture()
    context = replace(context, route=lambda *args: (Decimal("2.75"), "kilometers"))
    result = scan_places(store, request, context)
    assert result.status == "OK"
    assert [f.value for f in result.facts if f.unit == "metres"] == [Decimal(2750)]


@pytest.mark.parametrize(
    "change", ["unbound", "tiles", "release", "sources", "empty_sources"]
)
def test_routing_binding_refuses_borrowed_chain(change, tmp_path):
    from dataclasses import replace

    from product.tests.scan_places_support import fixture, records, replace_rows

    from eii_product.tools.scan_places import scan_places

    store, context, request, routes = fixture()
    if change == "unbound":
        context = replace(context, routing_binding=None)
    elif change == "tiles":
        context = replace(context, area=replace(context.area, tile_folder=tmp_path))
    elif change == "release":
        context = replace(
            context,
            routing_binding=replace(
                context.routing_binding, area=replace(context.area, release_id="b" * 64)
            ),
        )
    elif change == "empty_sources":
        context = replace(
            context, routing_binding=replace(context.routing_binding, sources=())
        )
    else:
        # A self-consistent changed release chain must still match the graph's bound source.
        sources = records(store, "sources")
        sources[0]["sha256"] = "b" * 64
        replace_rows(store, "sources", sources)
        chains = dict(context.chains)
        key = "lin_road_link_scan_places_distance"
        chains[key] = (replace(chains[key][0], sha256="b" * 64),)
        context = replace(context, chains=chains)
    result = scan_places(store, request, context)
    assert result.status == "NO_DATA"
    assert not result.payload.places and not result.facts
    assert not routes


def test_bound_tiles_supply_distance(tmp_path, monkeypatch):
    from dataclasses import replace

    from product.tests.scan_places_support import fixture

    from eii_product.tools import scan_places as module

    store, context, request, _ = fixture()
    area = replace(context.area, tile_folder=tmp_path)
    context = replace(
        context,
        area=area,
        route=None,
        routing_binding=replace(context.routing_binding, area=area),
    )
    calls = []

    def distance(folder, mode, origin, destination):
        calls.append((folder, mode, origin, destination))
        return 2, "kilometers"

    monkeypatch.setattr(module, "network_distance", distance)
    result = module.scan_places(store, request, context)
    assert result.status == "OK"
    assert calls == [(tmp_path, "walk", (0.0, 0.0), (0.0, 0.0))]
