"""Manifest model: canonical JSON, release hash, schema hash and the class map."""

from __future__ import annotations

import hashlib

import pytest

import eii_core.manifest as manifest


def _sample() -> dict[str, object]:
    return {
        "artefacts": [],
        "build_id": "build-a",
        "built_at": "2026-01-01T00:00:00Z",
        "code_version": "invented-code",
        "engine_versions": {
            "duckdb": "2.0.0",
            "postgis_target": "3.6",
            "python": "3.14",
        },
        "release_contract_version": "release.v1",
        "release_id": "ab" * 32,
        "release_kind": "public_only",
        "rules_version_id": "invented-rules",
        "sources": [],
        "tables": [
            {
                "file": "tables/district.parquet",
                "grain": "district",
                "name": "district",
                "provenance_class": "frame",
                "row_count": 1,
                "schema_sha256": "cd" * 32,
                "sha256": "ef" * 32,
            }
        ],
    }


def test_literal_canonical_bytes_and_sha256() -> None:
    """Independent literals for one release body, one schema and one row digest.

    The canonical bytes were written by hand. Their SHA-256 values were computed
    with the shell's hashlib, not with eii_core.manifest.
    """
    release_bytes = '{"release_kind":"public_only","tables":[]}'
    schema_bytes = '[{"logical_type":"string","name":"label","nullable":false}]'
    row_bytes = '[{"label":"invented"}]'
    release_sha = "c880f42f38270ff391c0078412f4d46a00fc1fbb66478d2ca7ff67048aada721"
    schema_sha = "84d0138670a68a839672e9ccc0b12e03c21e808e66d25acbf727a6539423523a"
    row_sha = "b2a3679905852fc98f9d8008ca43960a0ed76420253ead2008b0d0b4fa08e0e9"
    document = {
        "build_id": "build-a",
        "built_at": "2026-01-01T00:00:00Z",
        "release_id": "ab" * 32,
        "release_kind": "public_only",
        "tables": [],
    }
    body = {
        key: value
        for key, value in document.items()
        if key not in manifest.HASH_IGNORED
    }
    assert manifest.canonical_json(body) == release_bytes
    assert manifest.release_hash(document) == release_sha
    columns = (manifest.ColumnSpec("label", "string", False),)
    assert manifest.canonical_json(manifest.schema_document(columns)) == schema_bytes
    assert manifest.schema_hash(columns) == schema_sha
    assert manifest.canonical_json([{"label": "invented"}]) == row_bytes
    assert hashlib.sha256(row_bytes.encode("utf-8")).hexdigest() == row_sha


def test_release_hash_ignores_only_the_three_fields() -> None:
    """A change of any other field changes the hash. The three identity fields do not."""
    base = manifest.release_hash(_sample())
    for field in ("release_id", "build_id", "built_at"):
        changed = _sample()
        changed[field] = "changed-value"
        assert manifest.release_hash(changed) == base
    others = (
        "release_kind",
        "release_contract_version",
        "code_version",
        "rules_version_id",
        "engine_versions",
        "sources",
        "artefacts",
        "tables",
    )
    for field in others:
        changed = _sample()
        if field == "engine_versions":
            changed[field] = {
                "duckdb": "9.9.9",
                "postgis_target": "3.6",
                "python": "3.14",
            }
        elif field in {"sources", "artefacts"}:
            changed[field] = [{"path": "artefacts/note.json", "sha256": "aa" * 32}]
        elif field == "tables":
            tables = changed["tables"]
            assert isinstance(tables, list)
            row = dict(tables[0])
            row["row_count"] = 2
            changed[field] = [row]
        else:
            changed[field] = "changed-value"
        assert manifest.release_hash(changed) != base


def test_canonical_json_refuses_a_float() -> None:
    """A floating-point value is not a manifest value."""
    with pytest.raises(manifest.ManifestRefusal) as caught:
        manifest.canonical_json({"value": 1.5})
    assert caught.value.reason == "float_refused"
    text = manifest.canonical_json({"b": 1, "a": "ä"})
    assert text == '{"a":"ä","b":1}'


def test_schema_hash_depends_on_order_type_nullability_and_srid() -> None:
    """Each of order, logical type, nullability and geometry SRID changes the hash."""
    columns = (
        manifest.ColumnSpec("name", "string", False),
        manifest.ColumnSpec("geometry", "geometry", False, "Geometry", 4326),
    )
    base = manifest.schema_hash(columns)
    assert manifest.schema_hash(columns) == base
    reordered = (columns[1], columns[0])
    retyped = (
        manifest.ColumnSpec("name", "int", False),
        columns[1],
    )
    renull = (
        manifest.ColumnSpec("name", "string", True),
        columns[1],
    )
    resrid = (
        columns[0],
        manifest.ColumnSpec("geometry", "geometry", False, "Geometry", 0),
    )
    assert manifest.schema_hash(reordered) != base
    assert manifest.schema_hash(retyped) != base
    assert manifest.schema_hash(renull) != base
    assert manifest.schema_hash(resrid) != base


def test_class_map_is_closed() -> None:
    """A document label maps to a closed class. The label itself is not a class."""
    assert manifest.class_of_label("Public (split)") == "public"
    assert manifest.class_of_label("Frame (Public geometry)") == "frame"
    with pytest.raises(manifest.ManifestRefusal) as caught:
        manifest.require_manifest_class("Public (split)")
    assert caught.value.reason == "unknown_class"
    with pytest.raises(manifest.ManifestRefusal) as label_caught:
        manifest.class_of_label("Invented")
    assert label_caught.value.reason == "unknown_class_label"
    with pytest.raises(manifest.ManifestRefusal):
        manifest.require_logical_type("float")


def test_public_only_forbidden_fields_are_the_eight() -> None:
    """The eight protected-only fields, and no ninth name, are forbidden."""
    expected = {
        "window_key",
        "protected_sha256",
        "parameter_set",
        "world_seed",
        "scenario_sha256",
        "contracts",
        "window_period",
        "spare_seeds",
    }
    assert manifest.FORBIDDEN_PUBLIC_ONLY == frozenset(expected)
    assert "rules_version_id" not in manifest.FORBIDDEN_PUBLIC_ONLY
