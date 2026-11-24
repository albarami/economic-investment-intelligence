"""The parity guard. The second engine is a stand-in, so this is not two-engine parity."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest
from product.tests.make_area_support import (
    FRAME,
    ORIGIN,
    RELEASE_ID,
    SHAPE_INSIDE,
    StandInStore,
    box_route,
    context,
    geometry_rows,
    write_database,
)

from eii_core.grid import base_cell
from eii_product.store.embedded import EmbeddedStore
from eii_product.store.parity import ToolDescriptor, run_parity
from eii_product.store.protocol import StoreRefusal
from eii_product.store.registry import PACKAGED, Inventory
from eii_product.tools.areas import canonical_json
from eii_product.tools.make_area import QUERY_NAMES, make_area
from eii_product.tools.registry import (
    descriptor,
    parity_cases,
    require_cases,
    resolve_descriptor,
    resolve_parity_cases,
    tool_keys,
)
from eii_product.tools.resolve import ResolveContext


def every_registered_run(
    area_payloads: list[bytes], resolve_payloads: list[bytes]
) -> tuple[tuple, tuple]:
    """make_area and resolve with every parity case, so coverage sees each of their queries."""
    tools = (
        descriptor(context(PACKAGED, routing=box_route), area_payloads),
        resolve_descriptor(ResolveContext(PACKAGED), resolve_payloads),
    )
    cases = parity_cases(SHAPE_INSIDE) + resolve_parity_cases()
    return tools, cases


# The parity guard checks coverage of the inventory it is given. Since the
# sector_facts tool joined the packaged folder, make_area's cases are checked
# against make_area's own queries (forced by the S3 join of S3-T04 and S3-T06).
MAKE_AREA_INVENTORY = Inventory(
    tuple(q for q in PACKAGED.queries if q.name.startswith("make_area_")),
    PACKAGED.token,
    tuple(q for q in PACKAGED.names if q.name.startswith("make_area_")),
)
# make_area and resolve run together against their own queries; sector_facts' queries
# are covered by test_sector_facts_parity.py against its own inventory (forced by the S3 join of S3-T03, S3-T04 and S3-T06).
JOINED_INVENTORY = Inventory(
    tuple(q for q in PACKAGED.queries if q.name.startswith(("make_area_", "resolve_"))),
    PACKAGED.token,
    tuple(q for q in PACKAGED.names if q.name.startswith(("make_area_", "resolve_"))),
)


def _round_fact(value, places):
    del value, places
    raise AssertionError("round_fact called")


def _payloads_equal(left: bytes, right: bytes) -> None:
    assert left == right


def _resolve_rows() -> dict[str, tuple]:
    places = tuple(
        (key, "locality", key, key, None, lon, lat, None)
        for key, lon, lat in geometry_rows()["make_area_gazetteer_point"]
    )
    return {
        "resolve_gazetteer": places,
        "resolve_district": (),
        "resolve_zone": (),
        "resolve_municipality": geometry_rows()["make_area_municipalities"],
        "resolve_graph_node": (),
        "resolve_graph_edge": (),
    }


def _add_resolve_tables(path: Path) -> None:
    import duckdb

    connection = duckdb.connect(str(path))
    connection.execute("ALTER TABLE gazetteer ADD COLUMN kind VARCHAR")
    connection.execute("ALTER TABLE gazetteer ADD COLUMN name_en VARCHAR")
    connection.execute("ALTER TABLE gazetteer ADD COLUMN name_ar VARCHAR")
    connection.execute("ALTER TABLE gazetteer ADD COLUMN aliases VARCHAR")
    connection.execute("ALTER TABLE gazetteer ADD COLUMN cell BIGINT")
    connection.execute(
        "UPDATE gazetteer SET kind = 'locality', "
        "name_en = place_key, name_ar = place_key"
    )
    connection.execute(
        "CREATE TABLE district (district_key VARCHAR, name_en VARCHAR, name_ar VARCHAR)"
    )
    connection.execute(
        "CREATE TABLE zone (zone_code VARCHAR, name_en VARCHAR, name_ar VARCHAR)"
    )
    connection.execute(
        "CREATE TABLE graph_node ("
        "node_id VARCHAR, node_type VARCHAR, code VARCHAR, "
        "label_en VARCHAR, label_ar VARCHAR)"
    )
    connection.execute(
        "CREATE TABLE graph_edge ("
        "edge_id VARCHAR, edge_type VARCHAR, from_node_id VARCHAR, to_node_id VARCHAR)"
    )
    connection.close()


def _open(tmp_path: Path):
    path = tmp_path / "parity.duckdb"
    write_database(path)
    _add_resolve_tables(path)
    embedded = EmbeddedStore(path, RELEASE_ID, PACKAGED)
    rows = geometry_rows()
    rows.update(_resolve_rows())
    stand_in = StandInStore(PACKAGED, rows)
    ctx = context(PACKAGED, routing=box_route)
    return embedded, stand_in, ctx


def test_registry_is_closed_and_holds_make_area() -> None:
    assert tool_keys() == (
        "make_area",
        "resolve",
        "sector_facts",
        "stage",
        "scan_places",
        "night_lights",
        "venue_busyness",
        "population_age_sex",
    )
    assert {q.name for q in MAKE_AREA_INVENTORY.queries} == set(QUERY_NAMES)
    cases = parity_cases(SHAPE_INSIDE)
    assert {case.tool for case in cases} == {"make_area"}
    assert all(case.tool == "make_area" for case in cases)


def test_tool_without_a_parity_case_fails_the_registry_test() -> None:
    other = ToolDescriptor("other_tool", descriptor(context(PACKAGED), []).run, ())
    with pytest.raises(StoreRefusal, match="tool case missing"):
        require_cases((other,), ())


def test_make_area_guard_parity_on_a_stand_in_second_engine(tmp_path: Path) -> None:
    embedded, stand_in, _ctx = _open(tmp_path)
    payloads: list[bytes] = []
    resolve_payloads: list[bytes] = []
    try:
        result = run_parity(
            (embedded, stand_in),
            *every_registered_run(payloads, resolve_payloads),
            JOINED_INVENTORY,
            unit_precision={},
            round_fact=_round_fact,
        )
    finally:
        embedded.close()
    assert result.coverage.passed
    assert len(payloads) == 6
    for index in range(0, 6, 2):
        _payloads_equal(payloads[index], payloads[index + 1])
    names = set(result.traces["embedded"])
    assert names == {query.name for query in JOINED_INVENTORY.queries}
    assert set(result.traces["postgres"]) == names


def test_a_case_set_that_skips_a_query_fails_coverage(tmp_path: Path) -> None:
    embedded, stand_in, ctx = _open(tmp_path)
    cases = tuple(
        case
        for case in parity_cases(SHAPE_INSIDE)
        if "place_key" not in dict(case.inputs)
    )
    try:
        with pytest.raises(StoreRefusal, match="query not executed"):
            run_parity(
                (embedded, stand_in),
                (descriptor(ctx, []),),
                cases,
                MAKE_AREA_INVENTORY,
                unit_precision={},
                round_fact=_round_fact,
            )
    finally:
        embedded.close()


def test_a_query_the_tool_does_not_own_is_refused(tmp_path: Path) -> None:
    embedded, stand_in, ctx = _open(tmp_path)
    built = descriptor(ctx, [])
    short = ToolDescriptor(built.key, built.run, built.queries[:2])
    try:
        with pytest.raises(StoreRefusal, match="query not owned"):
            run_parity(
                (embedded, stand_in),
                (short,),
                parity_cases(SHAPE_INSIDE)[:1],
                MAKE_AREA_INVENTORY,
                unit_precision={},
                round_fact=_round_fact,
            )
    finally:
        embedded.close()


def test_one_changed_cell_fails_the_case(tmp_path: Path) -> None:
    embedded, _stand_in, ctx = _open(tmp_path)
    origin = base_cell(float(ORIGIN[0]), float(ORIGIN[1]), FRAME)
    rows = geometry_rows()
    rows.update(_resolve_rows())
    rows["make_area_grid_cells"] = tuple(
        row for row in rows["make_area_grid_cells"] if row[0] != origin
    )
    changed = StandInStore(PACKAGED, rows)
    payloads: list[bytes] = []
    resolve_payloads: list[bytes] = []
    try:
        run_parity(
            (embedded, changed),
            (
                descriptor(ctx, payloads),
                resolve_descriptor(ResolveContext(PACKAGED), resolve_payloads),
            ),
            parity_cases(SHAPE_INSIDE)[:1] + resolve_parity_cases(),
            JOINED_INVENTORY,
            unit_precision={},
            round_fact=_round_fact,
        )
    finally:
        embedded.close()
    with pytest.raises(AssertionError):
        _payloads_equal(payloads[0], payloads[1])


def test_one_changed_outline_vertex_fails_the_case(tmp_path: Path) -> None:
    path = tmp_path / "outline.duckdb"
    write_database(path)
    store = EmbeddedStore(path, RELEASE_ID, PACKAGED)
    request = {"place_key": "SYN-pin", "mode": "walk", "cutoff": 5}
    try:
        first = canonical_json(
            make_area(store, request, context(PACKAGED, routing=box_route)).payload
        )

        def shifted(mode, minutes, latitude, longitude):
            ring = list(box_route(mode, minutes, latitude, longitude))
            ring[1] = (ring[1][0], ring[1][1] + Decimal("0.00002"))
            return tuple(ring)

        second = canonical_json(
            make_area(store, request, context(PACKAGED, routing=shifted)).payload
        )
    finally:
        store.close()
    _payloads_equal(first, first)
    with pytest.raises(AssertionError):
        _payloads_equal(first, second)
