"""Full text of the graph-table refusals the activity-graph survivors still change.

Two unequal nodes with one id are handed to the node and edge adders directly:
the builder only re-adds an id when the fields match.
"""

from __future__ import annotations

from typing import Any

import pytest

from eii_custodian.publicdata.fetch.registry import load_registry
from eii_custodian.publicdata.review.graph import (
    _EDGE_ENDS,
    LINEAGE_EDGE_TYPES,
    LINEAGE_NODE_TYPES,
    UNMAPPABLE,
    GraphEdge,
    GraphError,
    GraphNode,
    _add_edge,
    _add_node,
    validate_graph,
)

_NAME = "اسم مخترع"
_CODE = "5610001"


def _as_any(value: Any) -> Any:
    """Return the argument unchanged."""
    return value


def _refuses(call: object, message: str) -> None:
    """The call raises GraphError with this full text."""
    assert callable(call)
    with pytest.raises(GraphError) as caught:
        call()
    found = caught.value
    assert str(found) == message
    assert found.detail == message


def _activity(code: str = _CODE, **changes: object) -> GraphNode:
    """An activity node, with any field replaced."""
    node = GraphNode(
        "activity:" + code,
        "activity",
        code,
        "",
        _NAME,
        "public",
        "lic_active",
    )
    if not changes:
        return node
    return node._replace(**_as_any(changes))


def _class_node(**changes: object) -> GraphNode:
    """The canonical UNMAPPABLE class node, with any field replaced."""
    node = GraphNode(
        "activity_class:" + UNMAPPABLE,
        "activity_class",
        UNMAPPABLE,
        UNMAPPABLE,
        "",
        "public",
        "cls_isic4",
    )
    if not changes:
        return node
    return node._replace(**_as_any(changes))


def _source(**changes: object) -> GraphNode:
    """A source node for the active feed."""
    node = GraphNode(
        "source:lic_active",
        "source",
        "lic_active",
        "Active certificates",
        "",
        "lineage",
        "lic_active",
    )
    if not changes:
        return node
    return node._replace(**_as_any(changes))


def _classified(code: str = _CODE, **changes: object) -> GraphEdge:
    """A classified_as edge onto the UNMAPPABLE class."""
    target = "activity_class:" + UNMAPPABLE
    edge = GraphEdge(
        f"classified_as:activity:{code}->{target}",
        "classified_as",
        "activity:" + code,
        target,
        "public",
        "editorial_reviewed",
        None,
        None,
        None,
        None,
        None,
        "lic_active",
    )
    if not changes:
        return edge
    return edge._replace(**_as_any(changes))


def _sourced(**changes: object) -> GraphEdge:
    """A sourced_from edge from the activity to the active feed."""
    edge = GraphEdge(
        f"sourced_from:activity:{_CODE}->source:lic_active",
        "sourced_from",
        "activity:" + _CODE,
        "source:lic_active",
        "lineage",
        "lineage",
        None,
        None,
        None,
        None,
        None,
        "lic_active",
    )
    if not changes:
        return edge
    return edge._replace(**_as_any(changes))


def _validate(nodes: tuple[GraphNode, ...], edges: tuple[GraphEdge, ...] = ()) -> None:
    """Validate against the committed registry."""
    validate_graph(nodes, edges, load_registry())


def test_duplicate_node_is_named() -> None:
    """Two nodes with one id are refused with that id."""
    _refuses(
        lambda: _validate((_activity(), _activity())),
        "duplicate node activity:" + _CODE,
    )


def test_duplicate_edge_is_named() -> None:
    """Two edges with one id are refused with that id."""
    edge = _classified()
    _refuses(
        lambda: _validate((_activity(), _class_node()), (edge, edge)),
        "duplicate edge " + edge.edge_id,
    )


def test_activity_without_a_class_edge_is_named_after_a_source() -> None:
    """A leading source node does not hide an activity that has no class edge."""
    _refuses(
        lambda: _validate((_source(), _activity(), _class_node())),
        "activity without one classified_as edge: activity:" + _CODE,
    )


def test_unknown_node_type_is_named() -> None:
    """A node type outside the closed list is refused with that type."""
    node = _source(node_id="made_up:1", node_type="made_up", code="made_up")
    _refuses(lambda: _validate((node,)), "unknown node type made_up")


def test_node_id_prefix_that_differs_from_the_type_is_named() -> None:
    """The text before the first colon has to be the node type."""
    node = _source(node_id="activity:lic_active", node_type="source")
    _refuses(
        lambda: _validate((node,)),
        "node id prefix differs from its type: activity:lic_active",
    )


def test_node_id_may_contain_a_second_colon() -> None:
    """Only the text before the first colon is the type."""
    node = _activity(node_id="activity:ab:cd")
    edge = _classified(from_node_id="activity:ab:cd")
    _validate((node, _class_node()), (edge,))


def test_empty_node_code_is_named() -> None:
    """A code of spaces is an empty code."""
    _refuses(lambda: _validate((_source(code="   "),)), "node code is empty")


def test_node_code_xxxx_is_a_real_code() -> None:
    """The marker text is a code when a node actually carries it."""
    _validate((_source(code="XXXX"),))


def test_unknown_node_provenance_is_named() -> None:
    """A provenance outside the closed pair is refused."""
    _refuses(
        lambda: _validate((_source(provenance="secret"),)),
        "unknown node provenance",
    )


def test_synthetic_marker_in_a_label_is_named() -> None:
    """A synthetic marker in a label is refused with the node id."""
    _refuses(
        lambda: _validate((_source(label_en="SYN-mark"),)),
        "synthetic identifier in the graph: source:lic_active",
    )


def test_node_source_missing_from_the_registry_is_named() -> None:
    """A source id the registry does not hold is refused with the node id."""
    node = _source(source_id="no_such_source")
    _refuses(
        lambda: _validate((node,)),
        "node source is not in the registry: source:lic_active",
    )


def test_unknown_edge_type_is_named() -> None:
    """An edge type outside the closed list is refused with that type."""
    edge = _classified(edge_type="invented")
    _refuses(
        lambda: _validate((_activity(), _class_node()), (edge,)),
        "unknown edge type invented",
    )


def test_unknown_edge_provenance_is_named() -> None:
    """An edge provenance outside the closed pair is refused."""
    edge = _classified(provenance="secret")
    _refuses(
        lambda: _validate((_activity(), _class_node()), (edge,)),
        "unknown edge provenance",
    )


def test_unknown_edge_basis_is_named() -> None:
    """An edge basis outside the closed set is refused with that basis."""
    edge = _classified(basis="guessed")
    _refuses(
        lambda: _validate((_activity(), _class_node()), (edge,)),
        "unknown edge basis guessed",
    )


def test_edge_value_that_is_not_a_decimal_is_named() -> None:
    """An integer attribute value is refused."""
    edge = _classified(attr_value=_as_any(1))
    _refuses(
        lambda: _validate((_activity(), _class_node()), (edge,)),
        "edge value is not a decimal",
    )


def test_edge_unit_that_is_not_text_is_named() -> None:
    """An integer attribute unit is refused."""
    edge = _classified(attr_unit=_as_any(1))
    _refuses(
        lambda: _validate((_activity(), _class_node()), (edge,)),
        "edge unit is not text",
    )


def test_edge_endpoint_missing_from_the_nodes_is_named() -> None:
    """An endpoint that is not a node is refused with that endpoint."""
    edge = _classified(from_node_id="activity:missing")
    _refuses(
        lambda: _validate((_activity(), _class_node()), (edge,)),
        "edge endpoint is not a node: activity:missing",
    )


def test_lineage_provenance_on_a_class_edge_is_named() -> None:
    """A class edge marked lineage is refused as a public edge type."""
    edge = _classified(provenance="lineage")
    _refuses(
        lambda: _validate((_activity(), _class_node()), (edge,)),
        "lineage edge has a public edge type",
    )


def test_public_edge_onto_a_lineage_node_is_named() -> None:
    """A public class edge that starts at a lineage node is refused."""
    activity = _activity(provenance="lineage")
    _refuses(
        lambda: _validate((activity, _class_node()), (_classified(),)),
        "public edge joins a lineage node",
    )


def test_public_sourced_from_edge_is_named() -> None:
    """A sourced_from edge with public provenance is refused."""
    edge = _sourced(provenance="public")
    _refuses(
        lambda: _validate((_activity(), _source()), (edge,)),
        "lineage edge type with public provenance",
    )


def test_edge_source_without_an_admitted_licence_is_named() -> None:
    """A public edge sourced from cls_isic4 is refused."""
    edge = _classified(source_id="cls_isic4")
    _refuses(
        lambda: _validate((_activity(), _class_node()), (edge,)),
        "edge source has no release-admitted licence",
    )


def test_sourced_from_between_two_sources_is_named() -> None:
    """A sourced_from edge from one source to another is refused."""
    origin = _source()
    target = _source(
        node_id="source:cls_isic4", code="cls_isic4", source_id="cls_isic4"
    )
    edge = _sourced(
        from_node_id=origin.node_id,
        to_node_id=target.node_id,
        edge_id="sourced_from:source:lic_active->source:cls_isic4",
    )
    _refuses(
        lambda: _validate((origin, target), (edge,)),
        "sourced_from edge does not join a public node or table to source",
    )


def test_sourced_from_basis_that_is_not_lineage_is_named() -> None:
    """A sourced_from edge with an official basis is refused."""
    edge = _sourced(basis="official", provenance="public")
    _refuses(
        lambda: _validate((_activity(), _source()), (edge,)),
        "sourced_from edge basis is not lineage",
    )


def test_activity_graph_missing_unmappable_is_named() -> None:
    """An activity graph with no UNMAPPABLE class node is refused."""
    other = GraphNode(
        "activity_class:5610",
        "activity_class",
        "5610",
        "Restaurants",
        "",
        "public",
        "cls_isic4",
    )
    edge = _classified(to_node_id=other.node_id)
    _refuses(
        lambda: _validate((_activity(), other), (edge,)),
        "activity graph is missing the UNMAPPABLE node",
    )


def test_unmappable_node_with_another_id_is_named() -> None:
    """One class node coded UNMAPPABLE under another id is refused."""
    other = _class_node(node_id="activity_class:OTHER")
    edge = _classified(to_node_id=other.node_id)
    _refuses(
        lambda: _validate((_activity(), other), (edge,)),
        "activity graph has a duplicate UNMAPPABLE node",
    )


def test_conflicting_node_is_named() -> None:
    """A second node with the same id and a different label is refused."""
    nodes: dict[str, GraphNode] = {}
    _add_node(nodes, _activity())
    _refuses(
        lambda: _add_node(nodes, _activity(label_en="other")),
        "conflicting node activity:" + _CODE,
    )


def test_conflicting_edge_is_named() -> None:
    """A second edge with the same id and a different basis is refused."""
    edges: dict[str, GraphEdge] = {}
    edge = _classified()
    _add_edge(edges, edge)
    _refuses(
        lambda: _add_edge(edges, _classified(basis="official")),
        "conflicting edge " + edge.edge_id,
    )


def test_every_lineage_edge_type_has_a_lineage_node_at_one_end() -> None:
    """Every lineage edge type has a lineage node type at one end."""
    unlisted = set(LINEAGE_EDGE_TYPES) - set(_EDGE_ENDS)
    assert unlisted == {"sourced_from"}
    assert "source" in LINEAGE_NODE_TYPES
    for edge_type in sorted(set(LINEAGE_EDGE_TYPES) - unlisted):
        origin, target, _basis = _EDGE_ENDS[edge_type]
        assert {origin, target} & LINEAGE_NODE_TYPES


def test_lineage_edge_with_no_lineage_end_is_refused_by_the_ends_check() -> None:
    """A contains edge between two classes is refused by the ends check."""
    origin = _class_node()
    target = _class_node(
        node_id="activity_class:5610",
        code="5610",
        label_en="Restaurants",
    )
    edge = GraphEdge(
        "contains:activity_class:UNMAPPABLE->activity_class:5610",
        "contains",
        origin.node_id,
        target.node_id,
        "lineage",
        "lineage",
        None,
        None,
        None,
        None,
        None,
        "cls_isic4",
    )
    _refuses(
        lambda: _validate((origin, target), (edge,)),
        "contains edge does not join release to table",
    )
