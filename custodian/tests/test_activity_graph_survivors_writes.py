"""Kills of the cached graph build and of the Parquet writer."""

from __future__ import annotations

import importlib.util
import os
import shutil
import stat
import tempfile
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from eii_custodian.publicdata.fetch.registry import load_registry
from eii_custodian.publicdata.review import graph as graph_module
from eii_custodian.publicdata.review.activity import SpineError, SupplierMembership
from eii_custodian.publicdata.review.cache_fixture import read_parquet
from eii_custodian.publicdata.review.graph import (
    NODE_FILE,
    Graph,
    GraphEdge,
    GraphError,
    GraphNode,
    build_cached_graph,
    write_graph,
)

_NAME = "اسم مخترع"
_NO_SUPPLIERS = SupplierMembership(codes=(), complete=True)
_LONG_NAME = "n" * 240
_LONGER_NAME = "n" * 243
_STAGING_LOCKED = stat.S_IRUSR | stat.S_IXUSR
_STAGING_OPEN = stat.S_IRWXU
_PLANTED_WRITE_FAILURE = "planted write failure"


def _as_any(value: Any) -> Any:
    """Return the argument unchanged."""
    return value


def _refuses(call: object, message: str, kind: type[GraphError] = GraphError) -> None:
    """The call raises exactly this type and this full text."""
    assert callable(call)
    with pytest.raises(kind) as caught:
        call()
    found = caught.value
    assert str(found) == message
    assert found.detail == message


def _load_fixtures() -> Any:
    """Load the invented cache builders from the existing graph tests."""
    path = Path(__file__).with_name("test_activity_graph.py")
    spec = importlib.util.spec_from_file_location("graph_fixture_builders", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_FIXTURES = _load_fixtures()


def _node(code: str) -> GraphNode:
    """An activity node whose identifier sorts with its code."""
    return GraphNode(
        "activity:" + code,
        "activity",
        code,
        "",
        _NAME,
        "public",
        "lic_active",
    )


def _class_node() -> GraphNode:
    """The single UNMAPPABLE class node."""
    return GraphNode(
        "activity_class:UNMAPPABLE",
        "activity_class",
        "UNMAPPABLE",
        "UNMAPPABLE",
        "",
        "public",
        "cls_isic4",
    )


def _edge(code: str) -> GraphEdge:
    """The one classified_as edge of an activity."""
    target = "activity_class:UNMAPPABLE"
    return GraphEdge(
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


def _writeable() -> Graph:
    """Two activities inserted out of identifier order, plus UNMAPPABLE."""
    later = "5610002"
    earlier = "5610001"
    return Graph(
        nodes=(_node(later), _node(earlier), _class_node()),
        edges=(_edge(later), _edge(earlier)),
    )


def test_cached_build_uses_the_registry_it_was_given(tmp_path: Path) -> None:
    """A registry without the active feed is the one the cached build reads."""
    fixtures = _FIXTURES
    fixtures._write_cached_feeds(tmp_path)
    review = fixtures._review_csv(tmp_path)
    fixtures._binding_beside(review, titles=(("5610", fixtures._RESTAURANT, ""),))
    registry = tuple(entry for entry in load_registry() if entry.key != "lic_active")
    _refuses(
        lambda: build_cached_graph(
            tmp_path,
            review,
            fixtures._allowlist_csv(tmp_path),
            (),
            supplier_membership=_NO_SUPPLIERS,
            registry=registry,
        ),
        "registry key missing: lic_active",
        _as_any(SpineError),
    )


def test_cached_release_honours_an_admitted_class_title(tmp_path: Path) -> None:
    """Release mode builds when the given registry admits the class title."""
    fixtures = _FIXTURES
    fixtures._write_cached_feeds(tmp_path)
    review = fixtures._review_csv(tmp_path)
    fixtures._binding_beside(review, titles=(("5610", fixtures._RESTAURANT, ""),))
    registry = tuple(
        replace(entry, licence_basis="dataset")
        if entry.source_id == "cls_isic4"
        else entry
        for entry in load_registry()
    )
    graph = build_cached_graph(
        tmp_path,
        review,
        fixtures._allowlist_csv(tmp_path),
        (),
        supplier_membership=_NO_SUPPLIERS,
        registry=registry,
        mode="release",
    )
    assert any(node.node_type == "activity" for node in graph.nodes)


def test_parquet_rows_follow_node_id_order(tmp_path: Path) -> None:
    """Rows are stored by node id, not by the order they were inserted."""
    graph = _writeable()
    node_path, _edge_path = write_graph(
        graph, tmp_path / "graph", registry=load_registry()
    )
    stored = [row["node_id"] for row in read_parquet(node_path.read_bytes())]
    assert stored == [
        "activity:5610001",
        "activity:5610002",
        "activity_class:UNMAPPABLE",
    ]


def test_graph_output_that_already_exists_is_named(tmp_path: Path) -> None:
    """A second write to the same directory is refused by name."""
    graph = _writeable()
    write_graph(graph, tmp_path / "graph", registry=load_registry())
    _refuses(
        lambda: write_graph(graph, tmp_path / "graph", registry=load_registry()),
        "graph output already exists",
    )


def test_write_creates_a_missing_parent(tmp_path: Path) -> None:
    """The parent of the output directory is created when it is absent."""
    target = tmp_path / "absent" / "deeper" / "graph"
    node_path, edge_path = write_graph(_writeable(), target, registry=load_registry())
    assert node_path == target / NODE_FILE
    assert node_path.is_file()
    assert edge_path.is_file()


def test_write_keeps_the_staging_directory_on_the_output_device(
    tmp_path: Path,
) -> None:
    """Staging is created beside the output, even when process temp is elsewhere."""
    previous = tempfile.tempdir
    tempfile.tempdir = "/dev/shm"
    try:
        target = tmp_path / "graph"
        node_path, _edge_path = write_graph(
            _writeable(), target, registry=load_registry()
        )
        assert node_path.is_file()
        assert os.stat(node_path).st_dev == os.stat(tmp_path).st_dev
    finally:
        tempfile.tempdir = previous


def test_staging_prefix_fits_a_long_output_name(tmp_path: Path) -> None:
    """An output name of 240 letters still leaves room for the staging prefix."""
    target = tmp_path / _LONG_NAME
    node_path, _edge_path = write_graph(_writeable(), target, registry=load_registry())
    assert node_path.is_file()
    assert node_path.parent.name == _LONG_NAME


def test_staging_prefix_of_a_longer_name_is_refused(tmp_path: Path) -> None:
    """An output name of 243 letters makes the staging prefix too long."""
    target = tmp_path / _LONGER_NAME
    with pytest.raises(OSError, match="File name too long"):
        write_graph(_writeable(), target, registry=load_registry())


def test_failed_write_keeps_its_error_when_staging_cannot_be_removed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The write's own error leaves when removing its staging folder also fails."""
    real = graph_module._write_parquet
    calls = {"count": 0}
    staging: list[Path] = []

    def failing(path: Path, columns: Any, types: Any, rows: Any) -> None:
        calls["count"] += 1
        if calls["count"] == 2:
            staging.append(path.parent)
            path.parent.chmod(_STAGING_LOCKED)
            raise OSError(_PLANTED_WRITE_FAILURE)
        real(path, columns, types, rows)

    monkeypatch.setattr(graph_module, "_write_parquet", failing)
    try:
        with pytest.raises(OSError) as caught:
            write_graph(_writeable(), tmp_path / "graph", registry=load_registry())
        assert str(caught.value) == _PLANTED_WRITE_FAILURE
    finally:
        if staging and staging[0].exists():
            staging[0].chmod(_STAGING_OPEN)
            shutil.rmtree(staging[0])
