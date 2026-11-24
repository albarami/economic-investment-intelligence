"""Invented manifest inventory and closed artefact projection, no source reads."""

import runpy
from copy import deepcopy
from functools import partial
from pathlib import Path

import public_release_fixture
import pytest
from product.tests import test_mounted_release_http

from eii_core.facts import Fact, validate_artefact_chain, validate_chain
from eii_product.api.release import Binding, MountedRelease
from eii_product.store.embedded import EmbeddedStore
from eii_product.store.registry import PACKAGED

# Reuse the existing core constructors by an explicit repository path, including
# under the root runner's -P isolation; no alternate fact fixture is copied.
_core_fixtures = runpy.run_path(
    str(Path(__file__).resolve().parents[2] / "core/tests/test_facts_model.py")
)
candidate = _core_fixtures["candidate"]
chain_rows = _core_fixtures["chain_rows"]

PATH = "artefacts/SYN-height.json"
DIGEST = "ab" * 32


def chain(release_id):
    _, sources = chain_rows()
    return [
        dict(
            lineage_id="lin_syn_height",
            release_id=release_id,
            artefact_path=PATH,
            artefact_sha256=DIGEST,
            method="invented.height",
            method_version="v1",
            input_class="public",
            source_id=sources[0]["source_id"],
        )
    ], sources


def test_artefact_validator_control():
    lines, sources = chain("a" * 64)
    assert (
        validate_artefact_chain(
            "lin_syn_height",
            lines,
            sources,
            [{"path": PATH, "sha256": DIGEST}],
            "a" * 64,
        )
        is None
    )


@pytest.mark.parametrize(
    "field,value,reason",
    [
        ("artefact_path", "artefacts/SYN-missing.json", "artefact_missing"),
        ("artefact_sha256", "cd" * 32, "artefact_hash_mismatch"),
        ("release_id", "b" * 64, "artefact_release_mismatch"),
        ("method", "", "artefact_method_missing"),
        ("method_version", "", "artefact_method_version_missing"),
        ("input_class", "synthetic", "lineage_class_invalid"),
        ("source_id", "SYN-absent", "source_missing"),
        ("table_name", "invented_table", "artefact_link_invalid"),
    ],
)
def test_artefact_validator_refusals(field, value, reason):
    lines, sources = chain("a" * 64)
    lines[0][field] = value
    assert (
        validate_artefact_chain(
            "lin_syn_height",
            lines,
            sources,
            [{"path": PATH, "sha256": DIGEST}],
            "a" * 64,
        )
        == reason
    )


def test_artefact_validator_empty():
    _, sources = chain("a" * 64)
    assert (
        validate_artefact_chain("lin_syn_height", [], sources, [], "a" * 64)
        == "lineage_missing"
    )


@pytest.fixture(scope="module")
def artefact_mount(tmp_path_factory):
    # Reuse the complete existing build/load fixture rather than copy its loader.
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(
            test_mounted_release_http,
            "build_fixture",
            partial(
                public_release_fixture.build_fixture,
                artefacts=({"path": PATH, "sha256": DIGEST},),
            ),
        )
        fixture = test_mounted_release_http.loaded.__wrapped__(tmp_path_factory)
        folder, identity, _ = next(fixture)
    store = EmbeddedStore(folder / "release.duckdb", identity, PACKAGED)
    try:
        yield MountedRelease(store, folder), folder
    finally:
        store.close()
        with pytest.raises(StopIteration):
            next(fixture)


def test_inventory_is_projected_from_verified_manifest(artefact_mount):
    mount, _ = artefact_mount
    assert mount.summary()["artefacts"] == [
        {"releaseId": mount.store.release_id, "path": PATH, "sha256": DIGEST}
    ]


def projection(mount):
    sources = mount.rows["source_registry"]
    lines, _ = chain(mount.store.release_id)
    lines[0]["source_id"] = sources[0]["source_id"]
    fact = Fact.model_validate(
        candidate(lineage_ref="lin_syn_height", release_id=mount.store.release_id)
    )
    mount.artefact_lineages[fact.lineage_ref] = lines
    return fact, Binding(metricKey="active_count", qualifiers={})


def test_mounted_artefact_projection(artefact_mount):
    mount, _ = artefact_mount
    fact, binding = projection(mount)
    body = mount.project(fact, binding)
    assert body["lineage"]["link"] == "artefact"
    assert body["lineage"]["artefactPath"] == PATH
    assert body["lineage"]["artefactSha256"] == DIGEST
    assert "tableName" not in body["lineage"]


@pytest.mark.parametrize(
    "field,value,reason",
    [
        ("artefact_path", "artefacts/SYN-missing.json", "artefact_missing"),
        ("method_version", "", "artefact_method_version_missing"),
        ("source_id", "SYN-absent", "source_missing"),
    ],
)
def test_mounted_artefact_refusals(artefact_mount, field, value, reason):
    mount, _ = artefact_mount
    fact, binding = projection(mount)
    original = deepcopy(mount.artefact_lineages)
    try:
        mount.artefact_lineages[fact.lineage_ref][0][field] = value
        with pytest.raises(ValueError, match="^" + reason + "$"):
            mount.project(fact, binding)
    finally:
        mount.artefact_lineages = original


@pytest.mark.parametrize(
    "field,value,reason",
    [
        ("publisher", "", "source_publisher_missing"),
        ("title", "", "source_title_missing"),
        ("licence", "", "source_licence_missing"),
        ("url", "", "source_url_missing"),
        ("sha256", "", "source_hash_missing"),
        ("retrieved_on", "2025-01-01", "source_retrieval_missing"),
    ],
)
@pytest.mark.parametrize("link", ["table", "artefact"])
def test_source_refusals(field, value, reason, link):
    lines, sources = chain_rows() if link == "table" else chain("a" * 64)
    sources[0][field] = value
    if link == "table":
        result = validate_chain("lin_pub_licence_active", lines, sources)
    else:
        result = validate_artefact_chain(
            "lin_syn_height",
            lines,
            sources,
            [{"path": PATH, "sha256": DIGEST}],
            "a" * 64,
        )
    assert result == reason


def test_artefact_chain_conflicting_method():
    lines, sources = chain("a" * 64)
    lines.append({**lines[0], "method": "invented.other"})
    assert (
        validate_artefact_chain(
            "lin_syn_height",
            lines,
            sources,
            [{"path": PATH, "sha256": DIGEST}],
            "a" * 64,
        )
        == "artefact_chain_conflict"
    )


@pytest.mark.parametrize("inventory", [[], [{"path": PATH, "sha256": DIGEST}] * 2])
def test_inventory_absence_and_duplicates(inventory):
    lines, sources = chain("a" * 64)
    assert (
        validate_artefact_chain("lin_syn_height", lines, sources, inventory, "a" * 64)
        == "artefact_missing"
    )


def test_duplicate_source_refused():
    lines, sources = chain("a" * 64)
    assert (
        validate_artefact_chain(
            "lin_syn_height",
            lines,
            sources * 2,
            [{"path": PATH, "sha256": DIGEST}],
            "a" * 64,
        )
        == "source_missing"
    )


def test_mounted_empty_artefact_inventory(tmp_path_factory):
    fixture = test_mounted_release_http.loaded.__wrapped__(tmp_path_factory)
    folder, identity, _ = next(fixture)
    store = EmbeddedStore(folder / "release.duckdb", identity, PACKAGED)
    try:
        assert MountedRelease(store, folder).summary()["artefacts"] == []
    finally:
        store.close()
        with pytest.raises(StopIteration):
            next(fixture)


def test_projection_selects_only_validated_lineage_rows(artefact_mount):
    mount, _ = artefact_mount
    fact, binding = projection(mount)
    unrelated = {
        **mount.artefact_lineages[fact.lineage_ref][0],
        "lineage_id": "lin_syn_unrelated",
        "method": "invented.unrelated",
    }
    mount.artefact_lineages[fact.lineage_ref].insert(0, unrelated)
    body = mount.project(fact, binding)
    assert body["lineage"]["method"] == "invented.height"


@pytest.mark.parametrize(
    "plant,reason",
    [("table", "extra_forbidden"), ("link", "missing"), ("unknown", "literal_error")],
)
def test_artefact_wire_model(plant, reason):
    from pydantic import ValidationError

    from eii_product.api.release import ArtefactLineage

    row = dict(
        link="artefact",
        lineageId="lin_syn_height",
        releaseId="a" * 64,
        artefactPath=PATH,
        artefactSha256=DIGEST,
        method="invented.height",
        methodVersion="v1",
        sourceIds=["SYN-source"],
        inputClasses=["public"],
    )
    ArtefactLineage.model_validate(row)
    if plant == "table":
        row["tableName"] = "invented_table"
    elif plant == "link":
        del row["link"]
    else:
        row["link"] = "unknown"
    with pytest.raises(ValidationError) as error:
        ArtefactLineage.model_validate(row)
    assert error.value.errors()[0]["type"] == reason
