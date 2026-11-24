"""Invented places on the existing invented make_area land fixture."""

import json
from datetime import date
from decimal import Decimal
from hashlib import sha256
from pathlib import Path

from product.tests.make_area_support import RecordingStore, context, geometry_rows

from eii_core.calc.facts import SourceChain
from eii_product.store.registry import PACKAGED
from eii_product.tools.make_area import make_area


def fixture():
    from eii_product.tools.scan_places import RoutingBinding, ScanPlacesContext

    rows = geometry_rows()
    source_bytes = (
        Path(__file__).parent / "fixtures/scan_places/places.json"
    ).read_bytes()
    source = dict(
        source_id="roads_osm",
        publisher="SYN-publisher",
        title="SYN-dataset",
        url="https://example.invalid/SYN",
        licence="SYN-licence",
        attribution="SYN road attribution",
        licence_basis="open_licence",
        retrieved_on=date(2025, 1, 1),
        sha256=sha256(source_bytes).hexdigest(),
    )
    tables = [
        "pub_place",
        "pub_place_fsq",
        "pub_place_verification",
        "pub_venue_visits",
        "graph_edge",
        "road_link",
    ]
    lines = []
    chains = {}
    for table in tables:
        lineage = (
            "lin_" + table + ("_scan_places_distance" if table == "road_link" else "")
        )
        lines.append(
            dict(
                lineage_id=lineage,
                table_name=table,
                source_id="roads_osm",
                input_class="public",
                transform="eii_core.calc.scan_places.route_metres@v1",
            )
        )
        chains[lineage] = (
            SourceChain(
                lineage,
                table,
                "eii_core.calc.scan_places.route_metres",
                "v1",
                source["publisher"],
                source["title"],
                source["url"],
                source["licence"],
                "2025-01-01",
                source["sha256"],
            ),
        )
    records = {
        "places": json.loads(source_bytes, parse_float=Decimal),
        "fsq": [],
        "verification": [],
        "visits": [],
        "neighbours": [],
        "categories": [
            dict(
                node_id="place_category:SYN-food",
                node_type="place_category",
                code="SYN-food",
                label_en="SYN Food",
                label_ar="طعام",
                provenance="public",
                source_id="roads_osm",
            )
        ],
        "lineage": lines,
        "sources": [source],
    }
    for name, records_for_query in records.items():
        spec = next(q for q in PACKAGED.queries if q.name == "scan_places_" + name)
        rows[spec.name] = tuple(
            tuple(row[c.name] for c in spec.returns) for row in records_for_query
        )
    store = RecordingStore(PACKAGED, rows)
    area = context(PACKAGED)
    result = make_area(
        store,
        {
            "latitude": Decimal("0"),
            "longitude": Decimal("0"),
            "mode": "distance",
            "cutoff": 250,
        },
        area,
    )
    routes = []

    def route(graph, mode, origin, destination):
        routes.append((graph, mode, origin, destination))
        return Decimal("0.75"), "kilometers"

    ctx = ScanPlacesContext(
        PACKAGED,
        area,
        "2025",
        "SYN-graph",
        {"SYN-source-category": "place_category:SYN-food"},
        route,
        chains,
        RoutingBinding("SYN-graph", area, chains["lin_road_link_scan_places_distance"]),
    )
    inputs = dict(
        area_id=result.payload["area_id"],
        categories=["place_category:SYN-food"],
        limit=50,
        include_neighbours=False,
    )
    store.calls.clear()
    return store, ctx, inputs, routes


def replace_rows(store, name, records):
    spec = next(q for q in PACKAGED.queries if q.name == "scan_places_" + name)
    store._rows[spec.name] = tuple(
        tuple(row[c.name] for c in spec.returns) for row in records
    )


def records(store, name):
    spec = next(q for q in PACKAGED.queries if q.name == "scan_places_" + name)
    return [
        dict(zip((c.name for c in spec.returns), row, strict=True))
        for row in store._rows[spec.name]
    ]
