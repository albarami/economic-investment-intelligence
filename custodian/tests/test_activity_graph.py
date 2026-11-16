"""Graph tables: one class edge per activity, the allow-list and the writer."""

from __future__ import annotations

import io
import json
import zipfile
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import duckdb
import pytest

from eii_custodian.publicdata.fetch.registry import load_registry
from eii_custodian.publicdata.fetch.snapshots import reviewed_selections
from eii_custodian.publicdata.review import graph as graph_module
from eii_custodian.publicdata.review.activity import (
    ActivityRow,
    IsicClass,
    ReviewRow,
    Spine,
    SpineError,
    SupplierMembership,
    build_spine,
    load_activity_inputs,
    review_binding,
)
from eii_custodian.publicdata.review.cache_fixture import (
    CacheError,
    class_csv,
    read_cached,
    read_csv,
    read_json,
    read_parquet,
    read_xlsx,
    real_feed_body,
    write_cached,
)
from eii_custodian.publicdata.review.graph import (
    EDGE_COLUMNS,
    EDGE_FILE,
    NODE_COLUMNS,
    NODE_FILE,
    AllowlistRow,
    Graph,
    GraphEdge,
    GraphError,
    GraphNode,
    build_cached_graph,
    build_graph,
    parse_place_categories,
    read_allowlist,
    validate_graph,
    write_graph,
)

_NO_SUPPLIERS = SupplierMembership(codes=(), complete=True)
_VERSION = "licence_codes_2025_05"
_RESTAURANT = "Restaurants and mobile food service activities"


# Document 03 section 10, stated here and not taken from the implementation.
_DOCUMENTED_NODE_COLUMNS = (
    "node_id",
    "node_type",
    "code",
    "label_en",
    "label_ar",
    "provenance",
    "source_id",
)
_DOCUMENTED_EDGE_COLUMNS = (
    "edge_id",
    "edge_type",
    "from_node_id",
    "to_node_id",
    "provenance",
    "basis",
    "period",
    "attr_value",
    "attr_unit",
    "attr_value_2",
    "attr_unit_2",
    "source_id",
)
_DOCUMENTED_EDGE_TYPES = {
    "edge_id": "VARCHAR",
    "edge_type": "VARCHAR",
    "from_node_id": "VARCHAR",
    "to_node_id": "VARCHAR",
    "provenance": "VARCHAR",
    "basis": "VARCHAR",
    "period": "VARCHAR",
    "attr_value": "DECIMAL(18,4)",
    "attr_unit": "VARCHAR",
    "attr_value_2": "DECIMAL(18,4)",
    "attr_unit_2": "VARCHAR",
    "source_id": "VARCHAR",
}


def test_graph_schema_is_the_documented_contract(tmp_path: Path) -> None:
    """Node and edge columns, order and types are document 03 section 10."""
    assert GraphNode._fields == _DOCUMENTED_NODE_COLUMNS
    assert GraphEdge._fields == _DOCUMENTED_EDGE_COLUMNS
    tariff = "1902" + "1900"
    nodes = (
        GraphNode("input:pasta", "input", "pasta", "Pasta", "", "public", "lic_active"),
        GraphNode("origin:ITA", "origin", "ITA", "Italy", "", "public", "lic_active"),
        GraphNode(
            f"tariff_line:{tariff}",
            "tariff_line",
            tariff,
            "Pasta",
            "",
            "public",
            "lic_active",
        ),
        GraphNode(
            "source:lic_active",
            "source",
            "lic_active",
            "Active certificates",
            "",
            "lineage",
            "lic_active",
        ),
    )
    edge = GraphEdge(
        f"imported_from:tariff_line:{tariff}->origin:ITA",
        "imported_from",
        f"tariff_line:{tariff}",
        "origin:ITA",
        "public",
        "official",
        "2025-05",
        Decimal("12.5000"),
        "QAR",
        Decimal("3.2500"),
        "kg",
        "lic_active",
    )
    written = Graph(nodes=nodes, edges=(edge,))
    _, edge_path = write_graph(written, tmp_path / "graph", registry=load_registry())
    connection = duckdb.connect()
    try:
        described = connection.execute(
            f"DESCRIBE SELECT * FROM read_parquet('{edge_path.as_posix()}')"
        ).fetchall()
    finally:
        connection.close()
    names = tuple(row[0] for row in described)
    kinds = {row[0]: row[1] for row in described}
    nullable = {row[0]: row[2] for row in described}
    assert names == _DOCUMENTED_EDGE_COLUMNS
    assert kinds == _DOCUMENTED_EDGE_TYPES
    assert nullable["attr_unit"] == "YES"
    assert nullable["attr_unit_2"] == "YES"
    stored = read_parquet(edge_path.read_bytes())
    imported = next(row for row in stored if row["edge_type"] == "imported_from")
    assert imported["attr_unit"] == "QAR"
    assert imported["attr_unit_2"] == "kg"
    assert imported["attr_value"] == Decimal("12.5000")
    assert imported["attr_value_2"] == Decimal("3.2500")


def test_build_graph_refuses_an_unsigned_mapped_row() -> None:
    """A mapped row with a blank reviewer role is not an admitted mapping."""
    activities, classes, spine = _mapped_inputs()
    planted = _replace_row(spine, "5610101", reviewed_by_role="", reviewed_on="")
    with pytest.raises(GraphError, match="mapped edge without a reviewer role"):
        build_graph(planted, activities, classes, (), (), load_registry())


def test_build_graph_refuses_a_stale_signed_name() -> None:
    """A signed mapping whose Arabic name differs from the cache is refused."""
    activities, classes, spine = _mapped_inputs()
    planted = _replace_row(spine, "5610101", name_ar="اسم قديم")
    with pytest.raises(
        GraphError, match="mapped edge name differs from the cached name"
    ):
        build_graph(planted, activities, classes, (), (), load_registry())


def test_build_graph_refuses_each_inconsistent_mapped_row() -> None:
    """Each mapped-row guard refuses with its own reason."""
    activities, classes, spine = _mapped_inputs()
    legacy = _replace_row(spine, "561000", status="mapped", isic_class="5610")
    wrong_class = _replace_row(spine, "5610101", isic_class="4100")
    missing_class = _replace_row(spine, "5610101", isic_class="5610")
    # The prefix matches, but the class list offered to the graph omits it.
    dropped = tuple(row for row in classes if row.code != "5610")
    wrong_reason = _replace_row(spine, "5610101", reason="reviewer_rejected")
    blank_date = _replace_row(spine, "5610101", reviewed_on="")
    bad_date = _replace_row(spine, "5610101", reviewed_on="2026-02-31")
    plants = (
        (legacy, activities, classes, "mapped edge is not a seven-digit code"),
        (wrong_class, activities, classes, "mapped edge class differs from the prefix"),
        (missing_class, activities, dropped, "mapped edge class is not an ISIC class"),
        (
            wrong_reason,
            activities,
            classes,
            "mapped edge without the reviewer_approved reason",
        ),
        (blank_date, activities, classes, "mapped edge without an ISO review date"),
        (bad_date, activities, classes, "mapped edge with a malformed date"),
    )
    for planted, rows, titles, reason in plants:
        with pytest.raises(GraphError, match=reason):
            build_graph(planted, rows, titles, (), (), load_registry())


def test_every_activity_has_one_class_edge() -> None:
    """Mapped rows reach their class; every other code reaches UNMAPPABLE."""
    graph = _graph()
    classed = [edge for edge in graph.edges if edge.edge_type == "classified_as"]
    assert len(classed) == 3
    targets = {edge.from_node_id: edge.to_node_id for edge in classed}
    assert targets["activity:5610101"] == "activity_class:5610"
    assert targets["activity:561000"] == "activity_class:UNMAPPABLE"
    assert targets["activity:5610201"] == "activity_class:UNMAPPABLE"
    assert "activity_class:UNMAPPABLE" in {node.node_id for node in graph.nodes}
    assert all(edge.basis == "editorial_reviewed" for edge in classed)
    assert all(edge.source_id in {"lic_active", "lic_cancelled"} for edge in classed)


def test_legacy_code_never_reaches_the_class_it_resembles() -> None:
    """No edge joins 561000 to 5610."""
    graph = _graph()
    assert not [
        edge
        for edge in graph.edges
        if edge.from_node_id == "activity:561000"
        and edge.to_node_id == "activity_class:5610"
    ]


def test_node_and_edge_fields_are_the_contract() -> None:
    """The tuples carry exactly the contract fields in order."""
    assert GraphNode._fields == NODE_COLUMNS
    assert GraphEdge._fields == EDGE_COLUMNS
    graph = _graph()
    assert graph.nodes == tuple(sorted(graph.nodes, key=lambda node: node.node_id))
    assert graph.edges == tuple(sorted(graph.edges, key=lambda edge: edge.edge_id))


def test_source_nodes_and_lineage_edges() -> None:
    """Every used source has a node and a sourced_from edge."""
    graph = _graph()
    sources = {node.code for node in graph.nodes if node.node_type == "source"}
    assert sources == {"lic_active", "lic_cancelled", "cls_isic4"}
    lineage = [edge for edge in graph.edges if edge.edge_type == "sourced_from"]
    assert lineage
    assert all(edge.provenance == "lineage" for edge in lineage)
    assert all(edge.to_node_id.startswith("source:") for edge in lineage)


def test_category_allowlist_builds_listed_as() -> None:
    """A signed class and a cached category give one listed_as edge."""
    allow = (AllowlistRow("5610", "restaurant", "data_reviewer", "2026-11-01"),)
    graph = _graph(allowlist=allow, categories=("cafe", "restaurant"))
    listed = [edge for edge in graph.edges if edge.edge_type == "listed_as"]
    assert len(listed) == 1
    assert listed[0].from_node_id == "activity_class:5610"
    assert listed[0].to_node_id == "place_category:restaurant"
    assert listed[0].source_id == "places_ovt"
    node = {item.node_id: item for item in graph.nodes}["place_category:restaurant"]
    assert node.label_en == "restaurant"
    assert node.label_ar == ""


def test_allowlist_refuses_a_missing_class_category_or_sign_off() -> None:
    """An unknown class, an unknown category and no sign-off each fail."""
    with pytest.raises(GraphError):
        _graph(
            allowlist=(
                AllowlistRow("9999", "restaurant", "data_reviewer", "2026-11-01"),
            ),
            categories=("restaurant",),
        )
    with pytest.raises(GraphError):
        _graph(
            allowlist=(
                AllowlistRow("5610", "pizzeria", "data_reviewer", "2026-11-01"),
            ),
            categories=("restaurant",),
        )
    with pytest.raises(GraphError):
        _graph(
            allowlist=(AllowlistRow("5610", "restaurant", "", ""),),
            categories=("restaurant",),
        )


def test_committed_allowlist_is_empty_and_reviewed() -> None:
    """The committed allow-list has the fixed header and no seed mapping."""
    rows = read_allowlist(_allowlist_path())
    assert rows == ()


def test_parquet_writes_are_byte_identical(tmp_path: Path) -> None:
    """Two writes of the same fixture graph give identical bytes."""
    graph = _graph()
    first = write_graph(graph, tmp_path / "one", registry=load_registry())
    second = write_graph(graph, tmp_path / "two", registry=load_registry())
    assert first[0].read_bytes() == second[0].read_bytes()
    assert first[1].read_bytes() == second[1].read_bytes()


def test_parquet_schema_and_row_order(tmp_path: Path) -> None:
    """Both files keep the fixed columns and the sorted row order."""
    graph = _graph()
    node_path, edge_path = write_graph(
        graph, tmp_path / "graph", registry=load_registry()
    )
    nodes = read_parquet(node_path.read_bytes())
    edges = read_parquet(edge_path.read_bytes())
    assert tuple(nodes[0]) == NODE_COLUMNS
    assert tuple(edges[0]) == EDGE_COLUMNS
    assert [row["node_id"] for row in nodes] == sorted(row["node_id"] for row in nodes)
    assert [row["edge_id"] for row in edges] == sorted(row["edge_id"] for row in edges)
    assert node_path.name == NODE_FILE
    assert edge_path.name == EDGE_FILE


def test_writer_refuses_to_overwrite(tmp_path: Path) -> None:
    """A second write into the same directory fails and keeps the first."""
    graph = _graph()
    write_graph(graph, tmp_path / "graph", registry=load_registry())
    with pytest.raises(GraphError):
        write_graph(graph, tmp_path / "graph", registry=load_registry())
    assert sorted(path.name for path in (tmp_path / "graph").iterdir()) == [
        EDGE_FILE,
        NODE_FILE,
    ]


def test_contract_types_validate() -> None:
    """Input, tariff line, origin, table and release nodes validate."""
    registry = load_registry()
    tariff = "1902" + "1900"
    nodes = (
        GraphNode("input:pasta", "input", "pasta", "Pasta", "", "public", "lic_active"),
        GraphNode("origin:ITA", "origin", "ITA", "Italy", "", "public", "lic_active"),
        GraphNode("release:rel_1", "release", "rel_1", "Release", "", "lineage", None),
        GraphNode(
            "source:lic_active",
            "source",
            "lic_active",
            "Active certificates",
            "",
            "lineage",
            "lic_active",
        ),
        GraphNode(
            "table:pub_place",
            "table",
            "pub_place",
            "Places",
            "",
            "lineage",
            None,
        ),
        GraphNode(
            f"tariff_line:{tariff}",
            "tariff_line",
            tariff,
            "Pasta",
            "",
            "public",
            "lic_active",
        ),
    )
    edges = (
        GraphEdge(
            "contains:release:rel_1->table:pub_place",
            "contains",
            "release:rel_1",
            "table:pub_place",
            "lineage",
            "lineage",
            None,
            None,
            None,
            None,
            None,
            "lic_active",
        ),
        GraphEdge(
            f"defined_by:input:pasta->tariff_line:{tariff}",
            "defined_by",
            "input:pasta",
            f"tariff_line:{tariff}",
            "public",
            "editorial_reviewed",
            None,
            None,
            None,
            None,
            None,
            "lic_active",
        ),
        GraphEdge(
            f"imported_from:tariff_line:{tariff}->origin:ITA",
            "imported_from",
            f"tariff_line:{tariff}",
            "origin:ITA",
            "public",
            "official",
            "2025-05",
            Decimal("1.5000"),
            None,
            Decimal("2.0000"),
            None,
            "lic_active",
        ),
        GraphEdge(
            "sourced_from:table:pub_place->source:lic_active",
            "sourced_from",
            "table:pub_place",
            "source:lic_active",
            "lineage",
            "lineage",
            None,
            None,
            None,
            None,
            None,
            "lic_active",
        ),
    )
    validate_graph(nodes, edges, registry)


def test_place_categories_read_nested_and_alias() -> None:
    """The nested primary category and the flat alias both parse."""
    nested = parse_place_categories(({"categories": {"primary": "restaurant"}},))
    flat = parse_place_categories(({"category": "cafe"},))
    assert nested == ("restaurant",)
    assert flat == ("cafe",)
    with pytest.raises(GraphError):
        parse_place_categories(({"categories": {}},))


def test_cache_reader_accepts_a_written_pair(tmp_path: Path) -> None:
    """A written body and sidecar read back with their bytes."""
    entry = _entry("lic_active")
    body = real_feed_body(
        "lic_active",
        [
            {
                "activity_code": "5610101",
                "activity_name_ar": "مطعم",
                "active_count": 10,
            }
        ],
    )
    write_cached(tmp_path, entry, body)
    cached = read_cached(
        tmp_path, entry, digest=reviewed_selections(tmp_path).get((entry).key, "0" * 64)
    )
    assert cached.body == body
    assert cached.sidecar["key"] == "lic_active"
    assert read_json(cached.body) == json.loads(body)


def test_cache_reader_refuses_a_stale_pair(tmp_path: Path) -> None:
    """A sidecar digest that differs from the body fails."""
    entry = _entry("lic_active")
    with pytest.raises(ValueError, match="snapshot_hash_mismatch"):
        write_cached(tmp_path, entry, b"{}", digest="0" * 64)


def test_cache_reader_refuses_missing_ambiguous_and_switched_off(
    tmp_path: Path,
) -> None:
    """No body, two bodies and a switched-off body each fail."""
    entry = _entry("lic_active")
    with pytest.raises(CacheError):
        read_cached(
            tmp_path,
            entry,
            digest=reviewed_selections(tmp_path).get((entry).key, "0" * 64),
        )
    write_cached(tmp_path, entry, b"{}")
    write_cached(tmp_path, entry, b"[]", select=False)
    assert (
        read_cached(
            tmp_path, entry, digest=reviewed_selections(tmp_path)[entry.key]
        ).body
        == b"{}"
    )
    with pytest.raises(CacheError):
        read_cached(tmp_path, entry, digest="0" * 64)
    other = tmp_path / "other"
    write_cached(other, entry, b"{}", switched_off=True)
    with pytest.raises(CacheError):
        read_cached(
            other, entry, digest=reviewed_selections(other).get((entry).key, "0" * 64)
        )


def test_cache_reader_refuses_another_key(tmp_path: Path) -> None:
    """A sidecar of another key is not accepted for this key."""
    entry = _entry("lic_active")
    path = write_cached(tmp_path, entry, b"{}")
    side = path.with_name(path.stem + ".meta.json")
    sidecar = json.loads(side.read_text(encoding="utf-8"))
    sidecar["key"] = "lic_cancelled"
    side.write_text(json.dumps(sidecar), encoding="utf-8")
    with pytest.raises(CacheError):
        read_cached(
            tmp_path,
            entry,
            digest=reviewed_selections(tmp_path).get((entry).key, "0" * 64),
        )


def test_csv_and_xlsx_bodies_read(tmp_path: Path) -> None:
    """A CSV body and an XLSX body give the same rows."""
    entry = _entry("lic_active")
    body = b"code,label\n5610,Restaurants\n"
    write_cached(tmp_path, entry, body, extension="csv")
    rows = read_csv(
        read_cached(
            tmp_path,
            entry,
            extension="csv",
            digest=reviewed_selections(tmp_path).get((entry).key, "0" * 64),
        ).body
    )
    assert rows == ({"code": "5610", "label": "Restaurants"},)
    sheet = _xlsx((("code", "label"), ("5610", "Restaurants")))
    assert read_xlsx(sheet) == ({"code": "5610", "label": "Restaurants"},)


def test_parquet_places_fixture_feeds_the_graph(tmp_path: Path) -> None:
    """A Parquet places body is read and its categories reach the graph."""
    entry = _entry("places_ovt")
    body = _places_parquet(tmp_path, ("restaurant", "cafe"))
    write_cached(tmp_path, entry, body)
    rows = read_parquet(
        read_cached(
            tmp_path,
            entry,
            digest=reviewed_selections(tmp_path).get((entry).key, "0" * 64),
        ).body
    )
    categories = parse_place_categories(rows)
    assert categories == ("cafe", "restaurant")
    allow = (AllowlistRow("5610", "restaurant", "data_reviewer", "2026-11-01"),)
    graph = _graph(allowlist=allow, categories=categories)
    assert any(edge.edge_type == "listed_as" for edge in graph.edges)


def test_cached_feeds_refuse_a_count_written_as_text(tmp_path: Path) -> None:
    """A count carried as text refuses the feed."""
    write_cached(
        tmp_path,
        _entry("lic_active"),
        real_feed_body(
            "lic_active",
            [
                {
                    "activity_code": "5610101",
                    "activity_name_ar": "مطعم",
                    "active_count": "10",
                }
            ],
        ),
    )
    write_cached(tmp_path, _entry("lic_cancelled"), real_feed_body("lic_cancelled", []))
    write_cached(tmp_path, _entry("cls_isic4"), class_csv([("5610", "Restaurants")]))
    review = _review_csv(tmp_path)
    _binding_beside(review)
    with pytest.raises(SpineError, match="lic_active"):
        load_activity_inputs(
            tmp_path,
            (),
            review_path=review,
            supplier_membership=_NO_SUPPLIERS,
        )


def test_build_cached_graph_requires_a_supplier_membership(tmp_path: Path) -> None:
    """The cached graph path refuses an omitted supplier membership."""
    _write_cached_feeds(tmp_path)
    with pytest.raises(TypeError, match="supplier_membership"):
        build_cached_graph(
            tmp_path,
            _review_csv(tmp_path),
            _allowlist_csv(tmp_path),
            (),
        )


def test_cache_to_graph_refuses_a_signed_row_without_a_binding(
    tmp_path: Path,
) -> None:
    """A signed review with no binding file cannot build the cached graph."""
    _write_cached_feeds(tmp_path)
    with pytest.raises(SpineError, match="review binding is missing"):
        build_cached_graph(
            tmp_path,
            _review_csv(tmp_path),
            _allowlist_csv(tmp_path),
            (),
            supplier_membership=_NO_SUPPLIERS,
        )


def test_cache_to_graph_refuses_a_changed_class_title(tmp_path: Path) -> None:
    """A class-title change with the same code and name refuses the cached graph."""
    _write_cached_feeds(tmp_path, label_en="Eating places")
    review = _review_csv(tmp_path)
    _binding_beside(review, titles=(("5610", _RESTAURANT, ""),))
    with pytest.raises(
        SpineError, match="classification title differs from the reviewed title"
    ):
        build_cached_graph(
            tmp_path,
            review,
            _allowlist_csv(tmp_path),
            (),
            supplier_membership=_NO_SUPPLIERS,
        )


def test_cache_to_graph_refuses_a_changed_code_system_version(
    tmp_path: Path,
) -> None:
    """A binding recorded against another code-system version refuses the graph."""
    _write_cached_feeds(tmp_path)
    review = _review_csv(tmp_path)
    _binding_beside(review, version="licence_codes_2026_06")
    with pytest.raises(
        SpineError, match="code-system version differs from the reviewed version"
    ):
        build_cached_graph(
            tmp_path,
            review,
            _allowlist_csv(tmp_path),
            (),
            supplier_membership=_NO_SUPPLIERS,
        )


def test_cache_to_graph_accepts_a_matching_recorded_binding(tmp_path: Path) -> None:
    """Matching recorded inputs still classify the signed activity."""
    _write_cached_feeds(tmp_path)
    review = _review_csv(tmp_path)
    _binding_beside(review, titles=(("5610", _RESTAURANT, ""),))
    graph = build_cached_graph(
        tmp_path,
        review,
        _allowlist_csv(tmp_path),
        (),
        supplier_membership=_NO_SUPPLIERS,
    )
    targets = {
        edge.from_node_id: edge.to_node_id
        for edge in graph.edges
        if edge.edge_type == "classified_as"
    }
    assert targets["activity:5610101"] == "activity_class:5610"


def test_cache_to_graph_fixture_end_to_end(tmp_path: Path) -> None:
    """Invented cached feeds, a signed review and a signed allow-list build the graph."""
    _write_cached_feeds(tmp_path)
    review = _review_csv(tmp_path)
    _binding_beside(review, titles=(("5610", _RESTAURANT, ""),))
    graph = build_cached_graph(
        tmp_path,
        review,
        _allowlist_csv(tmp_path),
        (),
        supplier_membership=_NO_SUPPLIERS,
    )
    targets = {
        edge.from_node_id: edge.to_node_id
        for edge in graph.edges
        if edge.edge_type == "classified_as"
    }
    assert targets == {
        "activity:561000": "activity_class:UNMAPPABLE",
        "activity:5610101": "activity_class:5610",
        "activity:5610201": "activity_class:UNMAPPABLE",
    }
    activities = {node.node_id for node in graph.nodes if node.node_type == "activity"}
    assert activities == {
        "activity:561000",
        "activity:5610101",
        "activity:5610201",
    }
    sources = {node.code for node in graph.nodes if node.node_type == "source"}
    assert sources == {"lic_active", "lic_cancelled", "cls_isic4", "places_ovt"}
    lineage = {
        (edge.from_node_id, edge.to_node_id)
        for edge in graph.edges
        if edge.edge_type == "sourced_from"
    }
    assert ("activity:5610101", "source:lic_active") in lineage
    assert ("activity:5610101", "source:lic_cancelled") in lineage
    assert ("activity:5610201", "source:lic_cancelled") in lineage
    listed = [edge for edge in graph.edges if edge.edge_type == "listed_as"]
    assert [(edge.from_node_id, edge.to_node_id) for edge in listed] == [
        ("activity_class:5610", "place_category:restaurant")
    ]


def test_cancelled_only_code_survives_the_cache_workflow(tmp_path: Path) -> None:
    """A code that only the cancelled feed names reaches the graph."""
    _write_cached_feeds(tmp_path)
    review = _review_csv(tmp_path)
    _binding_beside(review, titles=(("5610", _RESTAURANT, ""),))
    graph = build_cached_graph(
        tmp_path,
        review,
        _allowlist_csv(tmp_path),
        (),
        supplier_membership=_NO_SUPPLIERS,
    )
    node = {item.node_id: item for item in graph.nodes}["activity:5610201"]
    assert node.source_id == "lic_cancelled"
    assert node.label_ar == "كافيتيريا"


def test_source_presence_adds_both_feeds() -> None:
    """A code in both feeds carries a lineage edge to each source."""
    activities = (
        ActivityRow("5610101", "مطعم", 10, 0, ("lic_active", "lic_cancelled")),
    )
    classes = (IsicClass("5610", _RESTAURANT, ""),)
    reviews = (
        ReviewRow(
            "5610101",
            7,
            "مطعم",
            "5610",
            "mapped",
            "reviewer_approved",
            "data_reviewer",
            "2026-11-01",
        ),
    )
    spine = build_spine(
        activities,
        classes,
        reviews,
        (),
        supplier_membership=_NO_SUPPLIERS,
        reviewed_binding=review_binding(_VERSION, classes),
    )
    graph = build_graph(spine, activities, classes, (), (), load_registry())
    lineage = {
        (edge.from_node_id, edge.to_node_id)
        for edge in graph.edges
        if edge.edge_type == "sourced_from"
    }
    assert ("activity:5610101", "source:lic_active") in lineage
    assert ("activity:5610101", "source:lic_cancelled") in lineage
    node = {item.node_id: item for item in graph.nodes}["activity:5610101"]
    assert node.source_id == "lic_active"
    sources = {item.code for item in graph.nodes if item.node_type == "source"}
    assert sources == {"lic_active", "lic_cancelled", "cls_isic4"}


def test_edge_parquet_types_are_decimal_and_period_is_nullable(
    tmp_path: Path,
) -> None:
    """attr_value and attr_value_2 are DECIMAL(18,4) and a builder period is null."""
    graph = _graph()
    _, edge_path = write_graph(graph, tmp_path / "graph", registry=load_registry())
    connection = duckdb.connect()
    try:
        described = connection.execute(
            f"DESCRIBE SELECT * FROM read_parquet('{edge_path.as_posix()}')"
        ).fetchall()
    finally:
        connection.close()
    kinds = {row[0]: row[1] for row in described}
    assert kinds["attr_value"] == "DECIMAL(18,4)"
    assert kinds["attr_value_2"] == "DECIMAL(18,4)"
    assert kinds["period"] == "VARCHAR"
    assert all(edge.period is None for edge in graph.edges)
    assert all(edge.attr_value is None for edge in graph.edges)
    assert all(edge.attr_value_2 is None for edge in graph.edges)
    stored = read_parquet(edge_path.read_bytes())
    assert stored[0]["period"] is None
    assert stored[0]["attr_value"] is None


def test_writer_refuses_an_existing_target_directory(tmp_path: Path) -> None:
    """An existing target directory is refused before anything is written."""
    target = tmp_path / "graph"
    target.mkdir()
    with pytest.raises(GraphError):
        write_graph(_graph(), target, registry=load_registry())
    assert list(target.iterdir()) == []
    assert sorted(path.name for path in tmp_path.iterdir()) == ["graph"]


def test_writer_failure_leaves_no_target_or_staging(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failure on the second file leaves no target and no staging directory."""
    graph = _graph()
    real = graph_module._write_parquet
    calls = {"count": 0}

    def failing(path, columns, types, rows):
        calls["count"] += 1
        if calls["count"] == 2:
            raise OSError("planted write failure")
        real(path, columns, types, rows)

    monkeypatch.setattr(graph_module, "_write_parquet", failing)
    with pytest.raises(OSError):
        write_graph(graph, tmp_path / "graph", registry=load_registry())
    assert not (tmp_path / "graph").exists()
    assert list(tmp_path.iterdir()) == []


def test_writer_escapes_a_quoted_directory(tmp_path: Path) -> None:
    """A target directory holding a single quote still writes both files."""
    target = tmp_path / "graph'one"
    node_path, edge_path = write_graph(_graph(), target, registry=load_registry())
    assert node_path.is_file()
    assert edge_path.is_file()
    assert sorted(path.name for path in target.iterdir()) == [EDGE_FILE, NODE_FILE]


def test_parquet_reader_batches_preserve_order(tmp_path: Path) -> None:
    """A body larger than one batch reads back in its stored order."""
    entry = _entry("places_ovt")
    categories = tuple(f"category-{index}" for index in range(2500))
    write_cached(tmp_path, entry, _places_parquet(tmp_path, categories))
    rows = read_parquet(
        read_cached(
            tmp_path,
            entry,
            digest=reviewed_selections(tmp_path).get((entry).key, "0" * 64),
        ).body
    )
    assert len(rows) == 2500
    assert [row["place_id"] for row in rows] == sorted(
        f"place-{index}" for index in range(2500)
    )


def test_cache_reader_refuses_a_malformed_sidecar(tmp_path: Path) -> None:
    """A sidecar that is not JSON is a cache error, not a parse error."""
    entry = _entry("lic_active")
    path = write_cached(tmp_path, entry, b"{}")
    side = path.with_name(path.stem + ".meta.json")
    side.write_text("{not json", encoding="utf-8")
    with pytest.raises(CacheError):
        read_cached(
            tmp_path,
            entry,
            digest=reviewed_selections(tmp_path).get((entry).key, "0" * 64),
        )


def _mapped_inputs() -> tuple[tuple[ActivityRow, ...], tuple[IsicClass, ...], Spine]:
    activities = (
        ActivityRow("5610101", "مطعم", 10, 0),
        ActivityRow("561000", "تجارة قطع الغيار", 5, 0),
    )
    classes = (IsicClass("5610", _RESTAURANT, ""),)
    reviews = (
        ReviewRow(
            "5610101",
            7,
            "مطعم",
            "5610",
            "mapped",
            "reviewer_approved",
            "data_reviewer",
            "2026-11-01",
        ),
    )
    return (
        activities,
        classes,
        build_spine(
            activities,
            classes,
            reviews,
            (),
            supplier_membership=_NO_SUPPLIERS,
            reviewed_binding=review_binding(_VERSION, classes),
        ),
    )


def _replace_row(spine: Spine, code: str, **changes: object) -> Spine:
    rows = tuple(
        replace(row, **changes) if row.code == code else row for row in spine.rows
    )
    return replace(spine, rows=rows)


def _graph(
    *,
    allowlist: tuple[AllowlistRow, ...] = (),
    categories: tuple[str, ...] = (),
):
    activities = (
        ActivityRow("5610101", "مطعم", 10, 0),
        ActivityRow("561000", "تجارة قطع الغيار", 5, 0),
        ActivityRow("5610201", "كافيتيريا", 0, 4),
    )
    classes = (IsicClass("5610", _RESTAURANT, ""),)
    reviews = (
        ReviewRow(
            "5610101",
            7,
            "مطعم",
            "5610",
            "mapped",
            "reviewer_approved",
            "data_reviewer",
            "2026-11-01",
        ),
    )
    spine = build_spine(
        activities,
        classes,
        reviews,
        (),
        supplier_membership=_NO_SUPPLIERS,
        reviewed_binding=review_binding(_VERSION, classes),
    )
    return build_graph(
        spine,
        activities,
        classes,
        allowlist,
        categories,
        load_registry(),
    )


def _entry(source_id: str, registry=None):
    for entry in load_registry() if registry is None else registry:
        if entry.source_id == source_id:
            return entry
    raise AssertionError("registry row missing: " + source_id)


def _allowlist_path() -> Path:
    from eii_custodian.publicdata.review.activity import allowlist_path

    return allowlist_path()


def _places_parquet(folder: Path, categories: tuple[str, ...]) -> bytes:
    path = folder / "places.parquet"
    connection = duckdb.connect()
    try:
        connection.execute(
            "CREATE TABLE places (place_id VARCHAR, "
            'categories STRUCT("primary" VARCHAR))'
        )
        connection.executemany(
            'INSERT INTO places VALUES (?, struct_pack("primary" := ?))',
            [[f"place-{index}", name] for index, name in enumerate(categories)],
        )
        connection.execute(
            f"COPY (SELECT * FROM places ORDER BY place_id) TO "
            f"'{path.as_posix()}' (FORMAT parquet)"
        )
    finally:
        connection.close()
    return path.read_bytes()


def _xlsx(rows: tuple[tuple[str, ...], ...]) -> bytes:
    shared: list[str] = []
    index: dict[str, int] = {}

    def string_id(text: str) -> int:
        if text not in index:
            index[text] = len(shared)
            shared.append(text)
        return index[text]

    sheet_rows = []
    for number, row in enumerate(rows, start=1):
        cells = "".join(
            f'<c r="{chr(65 + column)}{number}" t="s"><v>{string_id(value)}</v></c>'
            for column, value in enumerate(row)
        )
        sheet_rows.append(f'<row r="{number}">{cells}</row>')
    main = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    rel = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    package = "http://schemas.openxmlformats.org/package/2006/relationships"
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(
            "xl/workbook.xml",
            f'<workbook xmlns="{main}" xmlns:r="{rel}"><sheets>'
            '<sheet name="Sheet1" sheetId="1" r:id="rId1"/>'
            "</sheets></workbook>",
        )
        archive.writestr(
            "xl/_rels/workbook.xml.rels",
            f'<Relationships xmlns="{package}">'
            '<Relationship Id="rId1" Target="worksheets/sheet1.xml"/>'
            "</Relationships>",
        )
        archive.writestr(
            "xl/sharedStrings.xml",
            f'<sst xmlns="{main}">'
            + "".join(f"<si><t>{text}</t></si>" for text in shared)
            + "</sst>",
        )
        archive.writestr(
            "xl/worksheets/sheet1.xml",
            f'<worksheet xmlns="{main}"><sheetData>'
            + "".join(sheet_rows)
            + "</sheetData></worksheet>",
        )
    return buffer.getvalue()


def _write_cached_feeds(folder: Path, *, label_en: str = _RESTAURANT) -> None:
    write_cached(
        folder,
        _entry("lic_active"),
        real_feed_body(
            "lic_active",
            [
                {
                    "activity_code": "5610101",
                    "activity_name_ar": "مطعم",
                    "active_count": 10,
                },
                {
                    "activity_code": "561000",
                    "activity_name_ar": "تجارة قطع الغيار",
                    "active_count": 5,
                },
            ],
        ),
    )
    write_cached(
        folder,
        _entry("lic_cancelled"),
        real_feed_body(
            "lic_cancelled",
            [
                {
                    "activity_code": "5610201",
                    "activity_name_ar": "كافيتيريا",
                    "cancelled_count": 4,
                },
                {
                    "activity_code": "5610101",
                    "activity_name_ar": "مطعم",
                    "cancelled_count": 0,
                },
            ],
        ),
    )
    write_cached(folder, _entry("cls_isic4"), class_csv([("5610", label_en)]))
    write_cached(
        folder, _entry("places_ovt"), _places_parquet(folder, ("cafe", "restaurant"))
    )


def _binding_beside(
    review: Path,
    *,
    version: str = "licence_codes_2025_05",
    titles: tuple[tuple[str, str, str], ...] = (("5610", "Restaurants", ""),),
) -> Path:
    import hashlib

    payload = {
        "code_system_version": version,
        "inputs": [
            {
                "code": code,
                "name": "class_title",
                "sha256": hashlib.sha256(
                    f"{code}\t{label_en}\t{label_ar}".encode()
                ).hexdigest(),
            }
            for code, label_en, label_ar in titles
        ],
    }
    path = review.with_name(review.stem + ".binding.json")
    path.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def _review_csv(folder: Path) -> Path:
    path = folder / "review.csv"
    path.write_text(
        "code,code_length,name_ar,isic_class,status,reason,"
        "reviewed_by_role,reviewed_on\n"
        "5610101,7,مطعم,5610,mapped,reviewer_approved,data_reviewer,2026-11-01\n",
        encoding="utf-8",
    )
    return path


def _allowlist_csv(folder: Path) -> Path:
    path = folder / "allowlist.csv"
    path.write_text(
        "isic_class,category,reviewed_by_role,reviewed_on\n"
        "5610,restaurant,data_reviewer,2026-11-01\n",
        encoding="utf-8",
    )
    return path


@pytest.mark.parametrize("consumer", ["activity", "graph"])
def test_activity_and_graph_retain_reviewed_older_snapshot(tmp_path, consumer):
    from eii_custodian.publicdata.fetch.snapshots import (
        read_snapshot,
        reviewed_selections,
    )

    _write_cached_feeds(tmp_path)
    review = _review_csv(tmp_path)
    _binding_beside(review, titles=(("5610", _RESTAURANT, ""),))
    entry = _entry("lic_active")
    older = read_snapshot(
        tmp_path / entry.key, reviewed_selections(tmp_path)[entry.key]
    )
    write_cached(tmp_path, entry, b"syn-newer-invalid-rows", select=False)

    def consume():
        if consumer == "activity":
            return load_activity_inputs(
                tmp_path, (), review_path=review, supplier_membership=_NO_SUPPLIERS
            ).activities
        return build_cached_graph(
            tmp_path,
            review,
            _allowlist_csv(tmp_path),
            (),
            supplier_membership=_NO_SUPPLIERS,
        ).nodes

    assert consume()
    older.path.write_bytes(b"syn-tamper")
    with pytest.raises(CacheError, match=r"^snapshot_hash_mismatch$"):
        consume()
