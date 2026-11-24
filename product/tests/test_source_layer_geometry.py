"""Source rings/parts survive the mounted route with no rounding or reordering."""

import json
from pathlib import Path

import pytest
from product.tests.test_tools_http import service as service
from shapely.geometry import MultiPolygon, Polygon

OUTER = [(0.123456789, 0), (3, 0), (3, 3), (0, 3), (0.123456789, 0)]
HOLE = [(1, 1), (1, 2), (2, 2), (2, 1), (1, 1)]
ISLAND = [(4, 0), (5, 0), (5, 1), (4, 1), (4, 0)]


@pytest.mark.parametrize("multipart", [False, True])
@pytest.mark.parametrize(
    "key,table",
    [
        ("land_prices", "district"),
        ("zone_electricity_growth", "zone"),
        ("zoning", "pub_zoning"),
        ("property_prices", "district"),
    ],
)
def test_all_parts_and_holes_reach_http(service, multipart, key, table):
    client, _ledger, store, _calls = service
    polygon = Polygon(OUTER, [HOLE])
    geometry = MultiPolygon([polygon, Polygon(ISLAND)]) if multipart else polygon
    store.tables[table] = [
        {**row, "geometry": geometry.wkb} for row in store.tables[table]
    ]
    response = client.get("/api/layers/" + key)
    assert response.status_code == 200
    layer = response.json()["payload"]["layers"][0]
    expected = (
        {
            "type": geometry.geom_type,
            "coordinates": [
                [[list(p) for p in OUTER], [list(p) for p in HOLE]],
                [[list(p) for p in ISLAND]],
            ],
        }
        if multipart
        else {
            "type": "Polygon",
            "coordinates": [[list(p) for p in OUTER], [list(p) for p in HOLE]],
        }
    )
    for feature in [*layer["features"], *layer.get("not_ranked", [])]:
        assert feature["geometry"] == expected
        assert "ring" not in feature


def test_bad_source_orientation_refuses_without_repair(service):
    client, _ledger, store, _calls = service
    store.tables["district"] = [
        {**r, "geometry": Polygon(list(reversed(OUTER))).wkb}
        for r in store.tables["district"]
    ]
    response = client.get("/api/layers/land_prices")
    assert response.status_code == 500 and set(response.json()) == {"error"}


@pytest.mark.parametrize(
    "case",
    json.loads(Path("web/tests/fixtures/source-orientation.json").read_text()),
    ids=lambda case: case["name"],
)
def test_shared_binary_rings_survive_the_route_or_refuse_whole(service, case):
    client, _ledger, store, _calls = service
    rings = case["geometry"]["coordinates"]
    geometry = Polygon(rings[0], rings[1:]).wkb
    store.tables["district"] = [
        {**row, "geometry": geometry} for row in store.tables["district"]
    ]
    response = client.get("/api/layers/land_prices")
    if not case["accepted"]:
        assert response.status_code == 500 and set(response.json()) == {"error"}
        return
    assert response.status_code == 200
    for feature in response.json()["payload"]["layers"][0]["features"]:
        transported = feature.get(
            "geometry", {"type": "Polygon", "coordinates": [feature.get("ring")]}
        )
        assert transported == case["geometry"]
