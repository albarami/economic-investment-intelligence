"""Planted graph violations: DAT-100 to DAT-103 and the release switch."""

from __future__ import annotations

from pathlib import Path

import pytest

from eii_custodian.publicdata.fetch.registry import load_registry, release_refused
from eii_custodian.publicdata.review.activity import (
    ActivityRow,
    IsicClass,
    ReviewRow,
    SupplierMembership,
    build_spine,
    review_binding,
)
from eii_custodian.publicdata.review.graph import (
    GraphEdge,
    GraphError,
    GraphNode,
    GraphRefused,
    build_cached_graph,
    build_graph,
    validate_graph,
    write_graph,
)

_NO_SUPPLIERS = SupplierMembership(codes=(), complete=True)
_VERSION = "licence_codes_2025_05"


def test_classified_as_rejects_another_activity_target() -> None:
    """A classified_as edge may not join an activity to another activity."""
    graph = _graph()
    planted = tuple(
        edge._replace(to_node_id="activity:561000")
        if edge.edge_type == "classified_as" and edge.from_node_id == "activity:5610101"
        else edge
        for edge in graph.edges
    )
    with pytest.raises(
        GraphError,
        match="classified_as edge does not join activity to activity_class",
    ):
        validate_graph(graph.nodes, planted, load_registry())


def test_classified_as_rejects_the_wrong_basis() -> None:
    """A classified_as edge keeps the editorial_reviewed basis."""
    graph = _graph()
    planted = tuple(
        edge._replace(basis="official")
        if edge.edge_type == "classified_as" and edge.from_node_id == "activity:5610101"
        else edge
        for edge in graph.edges
    )
    with pytest.raises(
        GraphError, match="classified_as edge basis is not editorial_reviewed"
    ):
        validate_graph(graph.nodes, planted, load_registry())


def test_activity_graph_requires_the_unmappable_node() -> None:
    """A complete activity graph keeps exactly one canonical UNMAPPABLE node."""
    graph = _graph(invented=True)
    nodes = tuple(node for node in graph.nodes if node.code != "UNMAPPABLE")
    edges = tuple(
        edge
        for edge in graph.edges
        if edge.from_node_id != "activity_class:UNMAPPABLE"
        and edge.to_node_id != "activity_class:UNMAPPABLE"
    )
    with pytest.raises(
        GraphError, match="activity graph is missing the UNMAPPABLE node"
    ):
        validate_graph(nodes, edges, load_registry())


def test_activity_graph_rejects_a_duplicate_unmappable_node() -> None:
    """A second UNMAPPABLE bucket is refused."""
    graph = _graph()
    extra = graph.nodes[0]._replace(
        node_id="activity_class:NOT_A_CLASS",
        node_type="activity_class",
        code="UNMAPPABLE",
        label_en="UNMAPPABLE",
        label_ar="",
        provenance="public",
        source_id="cls_isic4",
    )
    with pytest.raises(
        GraphError, match="activity graph has a duplicate UNMAPPABLE node"
    ):
        validate_graph((*graph.nodes, extra), graph.edges, load_registry())


def test_other_edge_types_reject_the_wrong_direction() -> None:
    """Each remaining edge type refuses a reversed pair of ends."""
    registry = load_registry()
    tariff = "1902" + "1900"
    nodes = _contract_nodes(tariff)
    classified = _edge(
        "classified_as:activity:5610101->activity_class:5610",
        "classified_as",
        "activity:5610101",
        "activity_class:5610",
        "public",
        "editorial_reviewed",
    )
    plants = (
        (
            "listed_as",
            "place_category:restaurant",
            "activity_class:5610",
            "public",
            "editorial_reviewed",
            "listed_as edge does not join activity_class to place_category",
        ),
        (
            "needs_input",
            "input:pasta",
            "activity_class:5610",
            "public",
            "editorial_reviewed",
            "needs_input edge does not join activity_class to input",
        ),
        (
            "defined_by",
            f"tariff_line:{tariff}",
            "input:pasta",
            "public",
            "editorial_reviewed",
            "defined_by edge does not join input to tariff_line",
        ),
        (
            "imported_from",
            "origin:ITA",
            f"tariff_line:{tariff}",
            "public",
            "official",
            "imported_from edge does not join tariff_line to origin",
        ),
        (
            "found_near",
            "activity_class:5610",
            "place_category:restaurant",
            "public",
            "computed",
            "found_near edge does not join place_category to place_category",
        ),
        (
            "contains",
            "table:pub_place",
            "release:rel_1",
            "lineage",
            "lineage",
            "contains edge does not join release to table",
        ),
        (
            "sourced_from",
            "source:lic_active",
            "activity:5610101",
            "lineage",
            "lineage",
            "sourced_from edge does not join a public node or table to source",
        ),
    )
    for edge_type, origin, target, provenance, basis, reason in plants:
        edge = _edge(
            edge_type + ":" + origin + "->" + target,
            edge_type,
            origin,
            target,
            provenance,
            basis,
        )
        with pytest.raises(GraphError, match=reason):
            validate_graph(nodes, (classified, edge), registry)


def test_imported_from_rejects_the_wrong_basis() -> None:
    """An imported_from edge keeps the official basis."""
    tariff = "1902" + "1900"
    nodes = _contract_nodes(tariff)
    classified = _edge(
        "classified_as:activity:5610101->activity_class:5610",
        "classified_as",
        "activity:5610101",
        "activity_class:5610",
        "public",
        "editorial_reviewed",
    )
    edge = _edge(
        "imported_from:tariff",
        "imported_from",
        f"tariff_line:{tariff}",
        "origin:ITA",
        "public",
        "editorial_reviewed",
    )
    with pytest.raises(GraphError, match="imported_from edge basis is not official"):
        validate_graph(nodes, (classified, edge), load_registry())


def test_sourced_from_rejects_the_wrong_basis() -> None:
    """A sourced_from edge keeps the lineage basis."""
    tariff = "1902" + "1900"
    nodes = _contract_nodes(tariff)
    classified = _edge(
        "classified_as:activity:5610101->activity_class:5610",
        "classified_as",
        "activity:5610101",
        "activity_class:5610",
        "public",
        "editorial_reviewed",
    )
    edge = _edge(
        "sourced_from:activity:5610101->source:lic_active",
        "sourced_from",
        "activity:5610101",
        "source:lic_active",
        "lineage",
        "editorial_reviewed",
    )
    with pytest.raises(GraphError, match="sourced_from edge basis is not lineage"):
        validate_graph(nodes, (classified, edge), load_registry())


def test_edge_unit_must_be_text() -> None:
    """A non-text edge unit is outside the contract."""
    graph = _graph()
    planted = tuple(
        edge._replace(attr_unit=1) if edge.edge_type == "classified_as" else edge
        for edge in graph.edges
    )
    with pytest.raises(GraphError, match="edge unit is not text"):
        validate_graph(graph.nodes, planted, load_registry())


def test_dat_100_public_edge_joining_a_lineage_node_fails() -> None:
    """A public edge may not touch a source node."""
    graph = _graph()
    planted = tuple(
        edge._replace(to_node_id="source:lic_active")
        if edge.edge_type == "classified_as" and edge.from_node_id == "activity:5610101"
        else edge
        for edge in graph.edges
    )
    with pytest.raises(GraphError):
        validate_graph(graph.nodes, planted, load_registry())


def test_dat_100_lineage_edge_without_a_lineage_end_fails() -> None:
    """A lineage edge needs a source, table or release end."""
    graph = _graph()
    planted = tuple(
        edge._replace(from_node_id="activity:5610101", to_node_id="activity_class:5610")
        if edge.edge_type == "sourced_from"
        else edge
        for edge in graph.edges
    )
    with pytest.raises(GraphError):
        validate_graph(graph.nodes, planted, load_registry())


def test_dat_101_synthetic_identifier_fails() -> None:
    """No node code may carry a SYN- identifier."""
    graph = _graph()
    planted = tuple(
        node._replace(code="SYN-0001") if node.node_id == "activity:5610101" else node
        for node in graph.nodes
    )
    with pytest.raises(GraphError):
        validate_graph(planted, graph.edges, load_registry())


def test_dat_101_unknown_node_type_fails() -> None:
    """A firm node type is outside the closed table."""
    graph = _graph()
    planted = tuple(
        node._replace(node_id="firm:0001", node_type="firm")
        if node.node_id == "activity:5610101"
        else node
        for node in graph.nodes
    )
    with pytest.raises(GraphError):
        validate_graph(planted, graph.edges, load_registry())


def test_dat_102_two_class_edges_for_one_activity_fails() -> None:
    """An activity carries exactly one classified_as edge."""
    graph = _graph()
    extra = GraphEdge(
        "classified_as:activity:5610101->activity_class:UNMAPPABLE",
        "classified_as",
        "activity:5610101",
        "activity_class:UNMAPPABLE",
        "public",
        "editorial_reviewed",
        None,
        None,
        None,
        None,
        None,
        "lic_active",
    )
    with pytest.raises(GraphError):
        validate_graph(graph.nodes, (*graph.edges, extra), load_registry())


def test_dat_102_activity_without_a_class_edge_fails() -> None:
    """An activity with no classified_as edge fails the degree check."""
    graph = _graph()
    planted = tuple(
        edge
        for edge in graph.edges
        if not (
            edge.edge_type == "classified_as" and edge.from_node_id == "activity:561000"
        )
    )
    with pytest.raises(GraphError):
        validate_graph(graph.nodes, planted, load_registry())


def test_dat_103_edge_without_an_admitted_licence_fails() -> None:
    """A non-lineage edge may not rest on a none_stated source."""
    graph = _graph()
    planted = tuple(
        edge._replace(source_id="cls_isic4")
        if edge.edge_type == "classified_as"
        else edge
        for edge in graph.edges
    )
    with pytest.raises(GraphError):
        validate_graph(graph.nodes, planted, load_registry())


def test_dat_103_edge_with_an_unknown_source_fails() -> None:
    """A non-lineage edge needs a registry source."""
    graph = _graph()
    planted = tuple(
        edge._replace(source_id="planted_source")
        if edge.edge_type == "classified_as"
        else edge
        for edge in graph.edges
    )
    with pytest.raises(GraphError):
        validate_graph(graph.nodes, planted, load_registry())


def test_edge_value_must_be_a_decimal() -> None:
    """A float edge value is outside the contract and fails."""
    graph = _graph()
    planted = tuple(
        edge._replace(attr_value=1.5) if edge.edge_type == "classified_as" else edge
        for edge in graph.edges
    )
    with pytest.raises(GraphError):
        validate_graph(graph.nodes, planted, load_registry())


def test_missing_endpoint_fails() -> None:
    """An edge endpoint that is not a node fails."""
    graph = _graph()
    planted = tuple(
        edge._replace(to_node_id="activity_class:0000")
        if edge.edge_type == "classified_as"
        else edge
        for edge in graph.edges
    )
    with pytest.raises(GraphError):
        validate_graph(graph.nodes, planted, load_registry())


def test_unknown_activity_source_fails_closed() -> None:
    """A direct graph caller may not discard an unknown feed identifier."""
    activity = ActivityRow("9999001", "نشاط مخترع", 10, 0)
    classes = (IsicClass("9999", "Invented class", ""),)
    spine = build_spine((activity,), classes, (), (), supplier_membership=_NO_SUPPLIERS)
    planted = ActivityRow("9999001", "نشاط مخترع", 10, 0, ("planted_source",))
    with pytest.raises(GraphError):
        build_graph(spine, (planted,), classes, (), (), load_registry())


def test_release_build_is_refused_and_writes_nothing(tmp_path: Path) -> None:
    """The real registry refuses a release graph and leaves no output."""
    entry = _entry("cls_isic4")
    assert release_refused(entry, "title") is True
    with pytest.raises(GraphRefused):
        _graph(mode="release")
    graph = _graph()
    output = tmp_path / "release"
    with pytest.raises(GraphRefused):
        write_graph(graph, output, registry=load_registry(), mode="release")
    assert not output.exists()
    assert list(tmp_path.iterdir()) == []


def test_cached_release_refusal_writes_nothing(tmp_path: Path) -> None:
    """The cache workflow refuses a release graph before any read and writes nothing."""
    with pytest.raises(GraphRefused):
        build_cached_graph(
            tmp_path,
            tmp_path / "review.csv",
            tmp_path / "allowlist.csv",
            (),
            mode="release",
            supplier_membership=_NO_SUPPLIERS,
        )
    assert list(tmp_path.iterdir()) == []


def test_fixture_mode_works_on_an_invented_class(tmp_path: Path) -> None:
    """Fixture mode builds and writes an invented class with no refusal."""
    graph = _graph(invented=True)
    assert any(edge.to_node_id == "activity_class:9999" for edge in graph.edges)
    node_path, edge_path = write_graph(
        graph, tmp_path / "fixture", registry=load_registry()
    )
    assert node_path.is_file()
    assert edge_path.is_file()


def _contract_nodes(tariff: str) -> tuple[GraphNode, ...]:
    return (
        GraphNode(
            "activity:5610101",
            "activity",
            "5610101",
            "",
            "مطعم",
            "public",
            "lic_active",
        ),
        GraphNode(
            "activity_class:5610",
            "activity_class",
            "5610",
            "Restaurants",
            "",
            "public",
            "cls_isic4",
        ),
        GraphNode(
            "activity_class:UNMAPPABLE",
            "activity_class",
            "UNMAPPABLE",
            "UNMAPPABLE",
            "",
            "public",
            "cls_isic4",
        ),
        GraphNode(
            "place_category:restaurant",
            "place_category",
            "restaurant",
            "restaurant",
            "",
            "public",
            "places_ovt",
        ),
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
            "Active",
            "",
            "lineage",
            "lic_active",
        ),
        GraphNode(
            "table:pub_place", "table", "pub_place", "Places", "", "lineage", None
        ),
        GraphNode("release:rel_1", "release", "rel_1", "Release", "", "lineage", None),
    )


def _edge(
    edge_id: str,
    edge_type: str,
    origin: str,
    target: str,
    provenance: str,
    basis: str,
) -> GraphEdge:
    return GraphEdge(
        edge_id,
        edge_type,
        origin,
        target,
        provenance,
        basis,
        None,
        None,
        None,
        None,
        None,
        "lic_active",
    )


def _graph(*, mode: str = "fixture", invented: bool = False):
    if invented:
        activities = (ActivityRow("9999001", "نشاط مخترع", 10, 0),)
        classes = (IsicClass("9999", "Invented class", ""),)
        reviews = (
            ReviewRow(
                "9999001",
                7,
                "نشاط مخترع",
                "9999",
                "mapped",
                "reviewer_approved",
                "data_reviewer",
                "2026-11-01",
            ),
        )
    else:
        activities = (
            ActivityRow("5610101", "مطعم", 10, 0),
            ActivityRow("561000", "تجارة قطع الغيار", 5, 0),
            ActivityRow("5610201", "كافيتيريا", 0, 4),
        )
        classes = (
            IsicClass("5610", "Restaurants and mobile food service activities", ""),
        )
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
    return build_graph(spine, activities, classes, (), (), load_registry(), mode=mode)


def _entry(source_id: str):
    for entry in load_registry():
        if entry.source_id == source_id:
            return entry
    raise AssertionError("registry row missing: " + source_id)
