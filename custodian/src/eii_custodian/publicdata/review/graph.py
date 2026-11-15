"""Economic graph tables: nodes, edges, validation and Parquet writes.

Every activity carries exactly one ``classified_as`` edge. Only a signed mapped
row reaches its ISIC class; every other code reaches the single ``UNMAPPABLE``
node, so a legacy code can never be filed under a class its prefix resembles.
"""

from __future__ import annotations

import csv
import os
import re
import shutil
import tempfile
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import NamedTuple

from eii_custodian.publicdata.fetch.registry import (
    Entry,
    load_registry,
    release_refused,
)
from eii_custodian.publicdata.review.activity import (
    FEED_KEYS,
    ActivityRow,
    IsicClass,
    Spine,
    SpineRow,
    SupplierMembership,
    entry_by_key,
    load_activity_inputs,
)
from eii_custodian.publicdata.review.cache_fixture import read_cached, read_rows

NODE_COLUMNS = (
    "node_id",
    "node_type",
    "code",
    "label_en",
    "label_ar",
    "provenance",
    "source_id",
)
EDGE_COLUMNS = (
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
NODE_TYPES = (
    "activity",
    "activity_class",
    "place_category",
    "input",
    "tariff_line",
    "origin",
    "source",
    "table",
    "release",
)
EDGE_TYPES = (
    "classified_as",
    "listed_as",
    "needs_input",
    "defined_by",
    "imported_from",
    "found_near",
    "sourced_from",
    "contains",
)
LINEAGE_NODE_TYPES = frozenset({"source", "table", "release"})
LINEAGE_EDGE_TYPES = frozenset({"sourced_from", "contains"})
_EDGE_ENDS = {
    "classified_as": ("activity", "activity_class", "editorial_reviewed"),
    "listed_as": ("activity_class", "place_category", "editorial_reviewed"),
    "needs_input": ("activity_class", "input", "editorial_reviewed"),
    "defined_by": ("input", "tariff_line", "editorial_reviewed"),
    "imported_from": ("tariff_line", "origin", "official"),
    "found_near": ("place_category", "place_category", "computed"),
    "contains": ("release", "table", "lineage"),
}
BASES = frozenset({"official", "computed", "editorial_reviewed", "lineage"})
PROVENANCES = frozenset({"public", "lineage"})
UNMAPPABLE = "UNMAPPABLE"
ALLOWLIST_COLUMNS = ("isic_class", "category", "reviewed_by_role", "reviewed_on")
NODE_FILE = "graph_node.parquet"
EDGE_FILE = "graph_edge.parquet"
_DIGITS = re.compile(r"\A[0-9]+\Z")
_ISO_DATE = re.compile(r"\A[0-9]{4}-[0-9]{2}-[0-9]{2}\Z")


class GraphError(Exception):
    """The graph inputs or the graph tables are not acceptable."""

    def __init__(self, detail: str) -> None:
        self.detail = detail
        super().__init__(detail)


class GraphRefused(GraphError):
    """A release graph was requested while its source is refused."""


class GraphNode(NamedTuple):
    """One ``graph_node`` row."""

    node_id: str
    node_type: str
    code: str
    label_en: str
    label_ar: str
    provenance: str
    source_id: str | None


class GraphEdge(NamedTuple):
    """One ``graph_edge`` row of document 03 section 10."""

    edge_id: str
    edge_type: str
    from_node_id: str
    to_node_id: str
    provenance: str
    basis: str
    period: str | None
    attr_value: Decimal | None
    attr_unit: str | None
    attr_value_2: Decimal | None
    attr_unit_2: str | None
    source_id: str | None


@dataclass(frozen=True)
class AllowlistRow:
    """One reviewed ISIC-class to place-category row."""

    isic_class: str
    category: str
    reviewed_by_role: str
    reviewed_on: str


@dataclass(frozen=True)
class Graph:
    """The node and edge tuples, sorted and deduplicated."""

    nodes: tuple[GraphNode, ...]
    edges: tuple[GraphEdge, ...]


def read_allowlist(path: Path) -> tuple[AllowlistRow, ...]:
    """Read the reviewed category allow-list."""
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != ALLOWLIST_COLUMNS:
            raise GraphError("allow-list header is not the fixed header")
        rows = tuple(_allowlist_row(item) for item in reader)
    pairs = [(row.isic_class, row.category) for row in rows]
    if len(pairs) != len(set(pairs)):
        raise GraphError("duplicate allow-list pair")
    return rows


def parse_place_categories(
    rows: Iterable[Mapping[str, object]],
) -> tuple[str, ...]:
    """Read the primary category of each cached Overture-like place row."""
    found: set[str] = set()
    for row in rows:
        nested = row.get("categories")
        value: object = None
        if isinstance(nested, Mapping):
            value = nested.get("primary")
        elif "category" in row:
            value = row["category"]
        if not isinstance(value, str) or value.strip() == "":
            raise GraphError("place row has no primary category")
        found.add(value)
    return tuple(sorted(found))


def build_graph(
    spine: Spine,
    activities: Sequence[ActivityRow],
    classes: Sequence[IsicClass],
    allowlist: Sequence[AllowlistRow],
    place_categories: Sequence[str],
    registry: Sequence[Entry],
    *,
    mode: str = "fixture",
) -> Graph:
    """Build the graph tuples for a fixture or a release request."""
    _refuse_release(registry, mode)
    by_code = {row.code: row for row in activities}
    if set(by_code) != {row.code for row in spine.rows}:
        raise GraphError("spine and activities name different codes")
    titles = {row.code: row for row in classes}
    categories = set(place_categories)
    nodes: dict[str, GraphNode] = {}
    edges: dict[str, GraphEdge] = {}
    extra_sources: dict[str, tuple[str, ...]] = {}
    for row in spine.rows:
        sources = _activity_sources(by_code[row.code])
        source = sources[0]
        if len(sources) > 1:
            extra_sources[row.code] = sources[1:]
        if row.status == "mapped":
            _require_mapped_row(row, by_code[row.code], titles)
        _add_node(
            nodes,
            GraphNode(
                node_id="activity:" + row.code,
                node_type="activity",
                code=row.code,
                label_en="",
                label_ar=row.name_ar,
                provenance="public",
                source_id=source,
            ),
        )
        target = (
            "activity_class:" + row.isic_class
            if row.status == "mapped"
            else "activity_class:" + UNMAPPABLE
        )
        _add_edge(
            edges,
            GraphEdge(
                edge_id=f"classified_as:activity:{row.code}->{target}",
                edge_type="classified_as",
                from_node_id="activity:" + row.code,
                to_node_id=target,
                basis="editorial_reviewed",
                period=None,
                attr_value=None,
                attr_unit=None,
                attr_value_2=None,
                attr_unit_2=None,
                provenance="public",
                source_id=source,
            ),
        )
    for row in spine.rows:
        if row.status != "mapped":
            continue
        title = titles.get(row.isic_class)
        if title is None:
            raise GraphError("mapped class has no ISIC title: " + row.isic_class)
        _add_node(nodes, _class_node(title))
    _add_node(
        nodes,
        GraphNode(
            node_id="activity_class:" + UNMAPPABLE,
            node_type="activity_class",
            code=UNMAPPABLE,
            label_en=UNMAPPABLE,
            label_ar="",
            provenance="public",
            source_id="cls_isic4",
        ),
    )
    for link in allowlist:
        title = titles.get(link.isic_class)
        if title is None:
            raise GraphError("allow-list class is not in cls_isic4")
        if link.category not in categories:
            raise GraphError("allow-list category is not in the places cache")
        _require_sign_off(link)
        _add_node(nodes, _class_node(title))
        _add_node(
            nodes,
            GraphNode(
                node_id="place_category:" + link.category,
                node_type="place_category",
                code=link.category,
                label_en=link.category,
                label_ar="",
                provenance="public",
                source_id="places_ovt",
            ),
        )
        _add_edge(
            edges,
            GraphEdge(
                edge_id=(
                    f"listed_as:activity_class:{link.isic_class}"
                    f"->place_category:{link.category}"
                ),
                edge_type="listed_as",
                from_node_id="activity_class:" + link.isic_class,
                to_node_id="place_category:" + link.category,
                basis="editorial_reviewed",
                period=None,
                attr_value=None,
                attr_unit=None,
                attr_value_2=None,
                attr_unit_2=None,
                provenance="public",
                source_id="places_ovt",
            ),
        )
    used = {node.source_id for node in nodes.values() if node.source_id}
    used.update(source for sources in extra_sources.values() for source in sources)
    for source_id in sorted(used):
        entry = _entry_for(registry, source_id)
        if entry is None:
            raise GraphError("source is not in the registry: " + source_id)
        _add_node(
            nodes,
            GraphNode(
                node_id="source:" + source_id,
                node_type="source",
                code=source_id,
                label_en=entry.title_en,
                label_ar="",
                provenance="lineage",
                source_id=source_id,
            ),
        )
    for node in tuple(nodes.values()):
        if node.source_id is None or node.node_type == "source":
            continue
        _add_edge(
            edges,
            GraphEdge(
                edge_id=f"sourced_from:{node.node_id}->source:{node.source_id}",
                edge_type="sourced_from",
                from_node_id=node.node_id,
                to_node_id="source:" + node.source_id,
                basis="lineage",
                period=None,
                attr_value=None,
                attr_unit=None,
                attr_value_2=None,
                attr_unit_2=None,
                provenance="lineage",
                source_id=node.source_id,
            ),
        )
    for code, sources in sorted(extra_sources.items()):
        for source_id in sources:
            _add_edge(
                edges,
                GraphEdge(
                    edge_id=f"sourced_from:activity:{code}->source:{source_id}",
                    edge_type="sourced_from",
                    from_node_id="activity:" + code,
                    to_node_id="source:" + source_id,
                    basis="lineage",
                    period=None,
                    attr_value=None,
                    attr_unit=None,
                    attr_value_2=None,
                    attr_unit_2=None,
                    provenance="lineage",
                    source_id=source_id,
                ),
            )
    graph = Graph(
        nodes=tuple(nodes[key] for key in sorted(nodes)),
        edges=tuple(edges[key] for key in sorted(edges)),
    )
    validate_graph(graph.nodes, graph.edges, registry)
    return graph


def build_cached_graph(
    cache: Path,
    review_path: Path,
    allowlist_path: Path,
    playbook_codes: Sequence[str],
    *,
    supplier_membership: SupplierMembership,
    registry: Sequence[Entry] | None = None,
    mode: str = "fixture",
) -> Graph:
    """Read the cached feeds, the review file and the allow-list, then build."""
    entries = load_registry() if registry is None else registry
    _refuse_release(entries, mode)
    inputs = load_activity_inputs(
        cache,
        playbook_codes,
        supplier_membership=supplier_membership,
        registry=entries,
        review_path=review_path,
    )
    categories = parse_place_categories(
        read_rows(read_cached(cache, entry_by_key(entries, "places_ovt")))
    )
    allowlist = read_allowlist(allowlist_path)
    return build_graph(
        inputs.spine,
        inputs.activities,
        inputs.classes,
        allowlist,
        categories,
        entries,
        mode=mode,
    )


def validate_graph(
    nodes: Sequence[GraphNode],
    edges: Sequence[GraphEdge],
    registry: Sequence[Entry],
) -> None:
    """Check the closed types, the endpoints and DAT-100 to DAT-103."""
    by_id: dict[str, GraphNode] = {}
    for node in nodes:
        _check_node(node, registry)
        if node.node_id in by_id:
            raise GraphError("duplicate node " + node.node_id)
        by_id[node.node_id] = node
    seen: set[str] = set()
    degrees: dict[str, int] = {}
    for edge in edges:
        _check_edge(edge, by_id, registry)
        if edge.edge_id in seen:
            raise GraphError("duplicate edge " + edge.edge_id)
        seen.add(edge.edge_id)
        if edge.edge_type == "classified_as":
            degrees[edge.from_node_id] = degrees.get(edge.from_node_id, 0) + 1
    for node in nodes:
        if node.node_type != "activity":
            continue
        if degrees.get(node.node_id, 0) != 1:
            raise GraphError("activity without one classified_as edge: " + node.node_id)
    _require_unmappable(nodes)


def write_graph(
    graph: Graph,
    directory: Path,
    *,
    registry: Sequence[Entry],
    mode: str = "fixture",
) -> tuple[Path, Path]:
    """Write both Parquet files through a temporary sibling directory."""
    _refuse_release(registry, mode)
    validate_graph(graph.nodes, graph.edges, registry)
    if directory.exists():
        raise GraphError("graph output already exists")
    directory.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(dir=directory.parent, prefix=directory.name + ".tmp-")
    )
    try:
        _write_parquet(
            staging / NODE_FILE,
            NODE_COLUMNS,
            _NODE_TYPES,
            [tuple(node) for node in graph.nodes],
        )
        _write_parquet(
            staging / EDGE_FILE,
            EDGE_COLUMNS,
            _EDGE_TYPES,
            [tuple(edge) for edge in graph.edges],
        )
        os.replace(staging, directory)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return directory / NODE_FILE, directory / EDGE_FILE


def _check_node(node: GraphNode, registry: Sequence[Entry]) -> None:
    if node.node_type not in NODE_TYPES:
        raise GraphError("unknown node type " + node.node_type)
    if node.node_id.split(":", 1)[0] != node.node_type:
        raise GraphError("node id prefix differs from its type: " + node.node_id)
    if node.code.strip() == "":
        raise GraphError("node code is empty")
    if node.provenance not in PROVENANCES:
        raise GraphError("unknown node provenance")
    for text in (node.node_id, node.code, node.label_en, node.label_ar):
        if "SYN-" in text:
            raise GraphError("synthetic identifier in the graph: " + node.node_id)
    if node.node_type in {"release", "table"}:
        return
    if node.source_id is None or _entry_for(registry, node.source_id) is None:
        raise GraphError("node source is not in the registry: " + node.node_id)


def _check_edge(
    edge: GraphEdge,
    by_id: Mapping[str, GraphNode],
    registry: Sequence[Entry],
) -> None:
    if edge.edge_type not in EDGE_TYPES:
        raise GraphError("unknown edge type " + edge.edge_type)
    if edge.provenance not in PROVENANCES:
        raise GraphError("unknown edge provenance")
    if edge.basis not in BASES:
        raise GraphError("unknown edge basis " + edge.basis)
    for value in (edge.attr_value, edge.attr_value_2):
        if value is not None and not isinstance(value, Decimal):
            raise GraphError("edge value is not a decimal")
    for unit in (edge.attr_unit, edge.attr_unit_2):
        if unit is not None and not isinstance(unit, str):
            raise GraphError("edge unit is not text")
    for endpoint in (edge.from_node_id, edge.to_node_id):
        if endpoint not in by_id:
            raise GraphError("edge endpoint is not a node: " + endpoint)
    _check_edge_ends(edge, by_id)
    if edge.provenance == "lineage":
        if edge.edge_type not in LINEAGE_EDGE_TYPES:
            raise GraphError("lineage edge has a public edge type")
        ends = {
            by_id[edge.from_node_id].node_type,
            by_id[edge.to_node_id].node_type,
        }
        if not ends & LINEAGE_NODE_TYPES:
            raise GraphError("lineage edge has no lineage end")
        return
    if edge.edge_type in LINEAGE_EDGE_TYPES:
        raise GraphError("lineage edge type with public provenance")
    for endpoint in (edge.from_node_id, edge.to_node_id):
        if by_id[endpoint].provenance != "public":
            raise GraphError("public edge joins a lineage node")
    if edge.source_id is None or not _admitted(registry, edge.source_id):
        raise GraphError("edge source has no release-admitted licence")


def _check_edge_ends(edge: GraphEdge, by_id: Mapping[str, GraphNode]) -> None:
    """Refuse an edge whose ends or basis differ from document 03 section 10."""
    origin = by_id[edge.from_node_id]
    target = by_id[edge.to_node_id]
    if edge.edge_type == "sourced_from":
        public_or_table = origin.node_type == "table" or origin.provenance == "public"
        if target.node_type != "source" or not public_or_table:
            raise GraphError(
                "sourced_from edge does not join a public node or table to source"
            )
        if edge.basis != "lineage":
            raise GraphError("sourced_from edge basis is not lineage")
        return
    expected = _EDGE_ENDS[edge.edge_type]
    from_type, to_type, basis = expected
    if origin.node_type != from_type or target.node_type != to_type:
        raise GraphError(
            edge.edge_type + " edge does not join " + from_type + " to " + to_type
        )
    if edge.basis != basis:
        raise GraphError(edge.edge_type + " edge basis is not " + basis)


def _require_unmappable(nodes: Sequence[GraphNode]) -> None:
    """A graph that holds activities has one canonical UNMAPPABLE class node."""
    if not any(node.node_type == "activity" for node in nodes):
        return
    canonical_id = "activity_class:" + UNMAPPABLE
    buckets = [
        node
        for node in nodes
        if node.code == UNMAPPABLE or node.node_id == canonical_id
    ]
    if not buckets:
        raise GraphError("activity graph is missing the UNMAPPABLE node")
    if (
        len(buckets) != 1
        or buckets[0].node_id != canonical_id
        or buckets[0].node_type != "activity_class"
    ):
        raise GraphError("activity graph has a duplicate UNMAPPABLE node")


def _refuse_release(registry: Sequence[Entry], mode: str) -> None:
    if mode not in {"fixture", "release"}:
        raise GraphError("unknown graph mode")
    if mode != "release":
        return
    entry = _entry_for(registry, "cls_isic4")
    if entry is None:
        raise GraphError("cls_isic4 is not in the registry")
    if release_refused(entry, "title"):
        raise GraphRefused("cls_isic4 title is not released")


def _entry_for(registry: Sequence[Entry], source_id: str) -> Entry | None:
    for entry in registry:
        if entry.source_id == source_id:
            return entry
    return None


def _admitted(registry: Sequence[Entry], source_id: str) -> bool:
    return any(
        entry.source_id == source_id and entry.licence_basis != "none_stated"
        for entry in registry
    )


def _activity_sources(activity: ActivityRow) -> tuple[str, ...]:
    if any(source not in FEED_KEYS for source in activity.source_ids):
        raise GraphError("unknown activity source: " + activity.code)
    if len(set(activity.source_ids)) != len(activity.source_ids):
        raise GraphError("duplicate activity source: " + activity.code)
    known = tuple(source for source in FEED_KEYS if source in activity.source_ids)
    if known:
        return known
    return ("lic_active" if activity.active_count > 0 else "lic_cancelled",)


def _require_mapped_row(
    row: SpineRow,
    activity: ActivityRow,
    titles: Mapping[str, IsicClass],
) -> None:
    """Refuse a mapped edge that a person did not approve against the cache."""
    if len(row.code) != 7 or _DIGITS.match(row.code) is None:
        raise GraphError("mapped edge is not a seven-digit code")
    prefix = row.code[:4]
    if row.isic_class != prefix:
        raise GraphError("mapped edge class differs from the prefix")
    if prefix not in titles:
        raise GraphError("mapped edge class is not an ISIC class")
    if row.name_ar != activity.name_ar:
        raise GraphError("mapped edge name differs from the cached name")
    if row.reason != "reviewer_approved":
        raise GraphError("mapped edge without the reviewer_approved reason")
    if row.reviewed_by_role.strip() == "":
        raise GraphError("mapped edge without a reviewer role")
    if _ISO_DATE.match(row.reviewed_on) is None:
        raise GraphError("mapped edge without an ISO review date")
    try:
        date.fromisoformat(row.reviewed_on)
    except ValueError as error:
        raise GraphError("mapped edge with a malformed date") from error


def _class_node(title: IsicClass) -> GraphNode:
    return GraphNode(
        node_id="activity_class:" + title.code,
        node_type="activity_class",
        code=title.code,
        label_en=title.label_en,
        label_ar=title.label_ar,
        provenance="public",
        source_id="cls_isic4",
    )


def _add_node(nodes: dict[str, GraphNode], node: GraphNode) -> None:
    held = nodes.get(node.node_id)
    if held is not None and held != node:
        raise GraphError("conflicting node " + node.node_id)
    nodes[node.node_id] = node


def _add_edge(edges: dict[str, GraphEdge], edge: GraphEdge) -> None:
    held = edges.get(edge.edge_id)
    if held is not None and held != edge:
        raise GraphError("conflicting edge " + edge.edge_id)
    edges[edge.edge_id] = edge


def _require_sign_off(row: AllowlistRow) -> None:
    if row.reviewed_by_role.strip() == "" or row.reviewed_on == "":
        raise GraphError("allow-list row without sign-off")
    try:
        date.fromisoformat(row.reviewed_on)
    except ValueError as error:
        raise GraphError("allow-list row with a malformed date") from error


def _allowlist_row(row: Mapping[str, object]) -> AllowlistRow:
    isic_class = row.get("isic_class")
    if not isinstance(isic_class, str) or _DIGITS.match(isic_class) is None:
        raise GraphError("allow-list class is not a digit string")
    if len(isic_class) != 4:
        raise GraphError("allow-list class is not four digits")
    category = row.get("category")
    if not isinstance(category, str) or category.strip() == "":
        raise GraphError("allow-list category is empty")
    role = row.get("reviewed_by_role")
    on = row.get("reviewed_on")
    if not isinstance(role, str) or not isinstance(on, str):
        raise GraphError("allow-list sign-off is not text")
    if on != "" and _ISO_DATE.match(on) is None:
        raise GraphError("allow-list date is not an ISO date")
    return AllowlistRow(
        isic_class=isic_class,
        category=category,
        reviewed_by_role=role,
        reviewed_on=on,
    )


_NODE_TYPES = (
    ("node_id", "VARCHAR"),
    ("node_type", "VARCHAR"),
    ("code", "VARCHAR"),
    ("label_en", "VARCHAR"),
    ("label_ar", "VARCHAR"),
    ("provenance", "VARCHAR"),
    ("source_id", "VARCHAR"),
)
_EDGE_TYPES = (
    ("edge_id", "VARCHAR"),
    ("edge_type", "VARCHAR"),
    ("from_node_id", "VARCHAR"),
    ("to_node_id", "VARCHAR"),
    ("provenance", "VARCHAR"),
    ("basis", "VARCHAR"),
    ("period", "VARCHAR"),
    ("attr_value", "DECIMAL(18,4)"),
    ("attr_unit", "VARCHAR"),
    ("attr_value_2", "DECIMAL(18,4)"),
    ("attr_unit_2", "VARCHAR"),
    ("source_id", "VARCHAR"),
)


def _sql_path(path: Path) -> str:
    return path.as_posix().replace("'", "''")


def _write_parquet(
    path: Path,
    columns: Sequence[str],
    types: Sequence[tuple[str, str]],
    rows: Sequence[tuple[object, ...]],
) -> None:
    import duckdb

    connection = duckdb.connect()
    try:
        connection.execute("SET threads=1")
        connection.execute("SET preserve_insertion_order=true")
        declared = ", ".join(f'"{name}" {kind}' for name, kind in types)
        connection.execute(f"CREATE TABLE rows ({declared})")
        marks = ", ".join("?" for _ in columns)
        connection.executemany(f"INSERT INTO rows VALUES ({marks})", list(rows))
        connection.execute(
            f'COPY (SELECT * FROM rows ORDER BY "{columns[0]}") TO '
            f"'{_sql_path(path)}' (FORMAT parquet, COMPRESSION zstd, "
            "ROW_GROUP_SIZE 122880)"
        )
    finally:
        connection.close()


__all__ = [
    "EDGE_COLUMNS",
    "EDGE_FILE",
    "NODE_COLUMNS",
    "NODE_FILE",
    "UNMAPPABLE",
    "AllowlistRow",
    "Graph",
    "GraphEdge",
    "GraphError",
    "GraphNode",
    "GraphRefused",
    "build_cached_graph",
    "build_graph",
    "parse_place_categories",
    "read_allowlist",
    "validate_graph",
    "write_graph",
]
