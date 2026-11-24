"""Manifest checks on plain values. No release table is written here."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol
from unittest.mock import Mock

import pytest

from eii_core.manifest import FORBIDDEN_PUBLIC_ONLY, canonical_json, release_hash
from eii_core.source_chain import SOURCE_KEYS
from eii_product.store.release_check import (
    ReleaseRefusal,
    check_release,
    refuse_document,
    require_count,
    require_hash,
)


def test_release_missing() -> None:
    with pytest.raises(ReleaseRefusal) as caught:
        check_release(Path("invented-missing-release"))
    assert caught.value.reason == "release_missing"
    assert caught.value.exit_code == 4


def test_release_kind_unsupported() -> None:
    document = _document()
    document["release_kind"] = "protected_window"
    with pytest.raises(ReleaseRefusal) as caught:
        refuse_document(document)
    assert caught.value.reason == "release_kind_unsupported"
    assert caught.value.exit_code == 1


def test_forbidden_manifest_field() -> None:
    assert len(FORBIDDEN_PUBLIC_ONLY) == 8
    for field in sorted(FORBIDDEN_PUBLIC_ONLY):
        document = _document()
        document[field] = "invented"
        with pytest.raises(ReleaseRefusal) as caught:
            refuse_document(document)
        assert caught.value.reason == "forbidden_manifest_field"
        assert caught.value.exit_code == 4


def test_empty_table_list() -> None:
    document = _document()
    document["tables"] = []
    with pytest.raises(ReleaseRefusal) as caught:
        refuse_document(document)
    assert caught.value.reason == "empty_table_list"
    assert caught.value.exit_code == 4


def test_unknown_table() -> None:
    for name in ("release_manifest", "not_a_table"):
        document = _document()
        document["tables"] = [{"name": name, "provenance_class": "public"}]
        with pytest.raises(ReleaseRefusal) as caught:
            refuse_document(document)
        assert caught.value.reason == "unknown_table"
        assert caught.value.exit_code == 4


def test_forbidden_table_class() -> None:
    document = _document()
    document["tables"] = [{"name": "resident_pay", "provenance_class": "protected"}]
    with pytest.raises(ReleaseRefusal) as caught:
        refuse_document(document)
    assert caught.value.reason == "forbidden_table_class"
    assert caught.value.exit_code == 4


def test_table_class_invalid() -> None:
    document = _document()
    document["tables"][0]["provenance_class"] = "Public (split)"
    with pytest.raises(ReleaseRefusal) as caught:
        refuse_document(document)
    assert caught.value.reason == "table_class_invalid"
    assert caught.value.exit_code == 4


def test_receipt_listed_as_artefact() -> None:
    document = _document()
    document["artefacts"] = [{"path": "load_receipt.json", "sha256": "ab" * 32}]
    with pytest.raises(ReleaseRefusal) as caught:
        refuse_document(document)
    assert caught.value.reason == "receipt_listed_as_artefact"
    assert caught.value.exit_code == 4


def test_release_incomplete(tmp_path: Path) -> None:
    document = _document()
    document["release_id"] = release_hash(document)
    (tmp_path / "manifest.json").write_text(_json(document), encoding="utf-8")
    (tmp_path / "tables").mkdir()
    with pytest.raises(ReleaseRefusal) as caught:
        check_release(tmp_path)
    assert caught.value.reason == "release_incomplete"
    assert caught.value.exit_code == 4


def test_unlisted_table(tmp_path: Path) -> None:
    """An extra parquet name is refused. The file is not a release table."""
    document = _document()
    document["release_id"] = release_hash(document)
    (tmp_path / "manifest.json").write_text(_json(document), encoding="utf-8")
    (tmp_path / "tables").mkdir()
    (tmp_path / "tables" / "extra_table.parquet").write_bytes(b"invented")
    with pytest.raises(ReleaseRefusal) as caught:
        check_release(tmp_path)
    assert caught.value.reason == "unlisted_table"
    assert caught.value.detail == "extra_table"
    assert caught.value.exit_code == 4


def test_one_check_uses_one_duckdb_connection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Every count, schema read and source-chain read of one check shares one connection."""
    import duckdb

    _parquet_release(tmp_path)
    calls = 0
    connect = duckdb.connect

    def counting(*args: object, **kwargs: object) -> object:
        nonlocal calls
        calls += 1
        return connect(*args, **kwargs)

    monkeypatch.setattr(duckdb, "connect", counting)
    checked = check_release(tmp_path)
    assert calls == 1
    assert [entry["row_count"] for entry in checked.document["tables"]] == [1, 1, 1]


def test_successful_check_closes_its_duckdb_connection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A successful check closes its one connection while the wrapper is still held."""
    _parquet_release(tmp_path)
    retained = _retain_check_connection(monkeypatch)
    checked = check_release(tmp_path)
    assert len(retained) == 1
    assert retained[0].close_calls == 1
    assert [entry["row_count"] for entry in checked.document["tables"]] == [1, 1, 1]


def test_digest_mismatch_after_open_closes_its_duckdb_connection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A count refusal after the connection opened still closes that connection once."""
    document, _rows = _parquet_release(tmp_path)
    document["tables"][-1]["row_count"] = 2
    document["release_id"] = release_hash(document)
    (tmp_path / "manifest.json").write_text(canonical_json(document), encoding="utf-8")
    retained = _retain_check_connection(monkeypatch)
    with pytest.raises(ReleaseRefusal) as caught:
        check_release(tmp_path)
    assert caught.value.reason == "digest_mismatch"
    assert caught.value.exit_code == 4
    assert len(retained) == 1
    assert retained[0].close_calls == 1


@pytest.mark.parametrize("read", ["count", "schema", "source_chain"])
def test_injected_query_exception_closes_its_duckdb_connection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, read: str
) -> None:
    """A planted read failure still closes the connection and leaves the checker."""
    _parquet_release(tmp_path)
    retained = _retain_check_connection(monkeypatch, fail_read=read)
    with pytest.raises(_InjectedQueryError) as caught:
        check_release(tmp_path)
    assert caught.value.read == read
    assert len(retained) == 1
    assert retained[0].close_calls == 1


def test_planted_row_count_on_the_last_table_is_refused(tmp_path: Path) -> None:
    """A shared connection must still count every table, including the last."""
    document, _rows = _parquet_release(tmp_path)
    document["tables"][-1]["row_count"] = 2
    (tmp_path / "manifest.json").write_text(_json(document), encoding="utf-8")
    with pytest.raises(ReleaseRefusal) as caught:
        check_release(tmp_path)
    assert caught.value.reason == "digest_mismatch"
    assert caught.value.exit_code == 4


def test_planted_schema_hash_on_the_middle_table_is_refused(tmp_path: Path) -> None:
    """A shared connection must still refuse a schema that does not match the file."""
    document, _rows = _parquet_release(tmp_path)
    recorded = str(document["tables"][1]["schema_sha256"])
    document["tables"][1]["schema_sha256"] = "b" + recorded[1:]
    (tmp_path / "manifest.json").write_text(_json(document), encoding="utf-8")
    with pytest.raises(ReleaseRefusal) as caught:
        check_release(tmp_path)
    assert caught.value.reason == "digest_mismatch"
    assert caught.value.exit_code == 4


def test_count_one_higher_and_one_lower() -> None:
    with pytest.raises(ReleaseRefusal) as higher:
        require_count(2, 1)
    with pytest.raises(ReleaseRefusal) as lower:
        require_count(1, 2)
    assert higher.value.reason == "digest_mismatch"
    assert lower.value.reason == "digest_mismatch"
    require_count(2, 2)


def test_each_hash_refuses_one_changed_character() -> None:
    recorded = "ab" * 32
    for label in ("release", "file", "schema"):
        flipped = "b" + recorded[1:]
        with pytest.raises(ReleaseRefusal) as caught:
            require_hash(flipped, recorded)
        assert caught.value.reason == "digest_mismatch", label
        assert caught.value.exit_code == 4
    require_hash(recorded, recorded)


@pytest.mark.parametrize(
    ("table", "field", "value"),
    [
        ("source_registry", "kind", "synthetic_feed"),
        ("source_registry", "kind", "simulation_output"),
        ("source_registry", "origin", "synthetic"),
        ("source_registry", "origin", "simulated"),
        ("fact_lineage", "input_class", "synthetic"),
        ("fact_lineage", "input_class", "simulated"),
    ],
)
def test_serving_and_load_refuse_rehashed_generated_parquet(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, table: str, field: str, value: str
) -> None:
    """Real bytes, rebound hashes and the unmocked serving guard precede both stores."""
    from eii_product.store import loader

    document, rows = _parquet_release(tmp_path)
    assert check_release(tmp_path).document == document
    rows[table][0][field] = value
    _write_chain_parquet(tmp_path, document, rows)
    with pytest.raises(ReleaseRefusal) as caught:
        check_release(tmp_path)
    assert caught.value.reason == "source_link_mismatch"
    assert caught.value.exit_code == 4

    connect, postgres, embedded = Mock(), Mock(), Mock()
    monkeypatch.setattr(loader, "_stage_postgres", postgres)
    monkeypatch.setattr(loader, "_stage_embedded", embedded)
    assert (
        loader.run_load(
            tmp_path, host="127.0.0.1", port=1, database="INVENTED", connect=connect
        )
        == 4
    )
    connect.assert_not_called()
    postgres.assert_not_called()
    embedded.assert_not_called()
    assert not (tmp_path / loader.READER_NAME).exists()
    assert not (tmp_path / loader.PARTIAL_READER).exists()
    assert not (tmp_path / "load_receipt.json").exists()


class _InnerConnection(Protocol):
    """The execute and close calls one release check makes."""

    def execute(self, query: str) -> object: ...

    def close(self) -> None: ...


class _InjectedQueryError(Exception):
    """A planted query failure. The checker must close and let it propagate."""

    def __init__(self, read: str) -> None:
        super().__init__(read)
        self.read = read


class _RetainedConnection:
    """Forwards execute and close, and counts each explicit close call."""

    def __init__(self, inner: _InnerConnection, fail_read: str | None) -> None:
        self._inner = inner
        self._fail_read = fail_read
        self.close_calls = 0

    def execute(self, query: str) -> object:
        """Run the real query, or raise the planted failure for one read kind."""
        if self._fail_read is not None and _query_read(query) == self._fail_read:
            raise _InjectedQueryError(self._fail_read)
        return self._inner.execute(query)

    def close(self) -> None:
        """Count the explicit close, then close the real connection."""
        self.close_calls += 1
        self._inner.close()


def _query_read(query: str) -> str:
    """Classify one checker query as count, schema or source_chain."""
    if query.startswith("SELECT count(*) FROM read_parquet("):
        return "count"
    if query.startswith("SELECT value FROM parquet_kv_metadata("):
        return "schema"
    if " FROM read_parquet(" in query:
        return "source_chain"
    return ""


def _retain_check_connection(
    monkeypatch: pytest.MonkeyPatch, *, fail_read: str | None = None
) -> list[_RetainedConnection]:
    """Patch connect after the invented release is already on disk."""
    import duckdb

    connect = duckdb.connect
    retained: list[_RetainedConnection] = []

    def counting(*args: object, **kwargs: object) -> _RetainedConnection:
        wrapper = _RetainedConnection(connect(*args, **kwargs), fail_read=fail_read)
        retained.append(wrapper)
        return wrapper

    monkeypatch.setattr(duckdb, "connect", counting)
    return retained


def _parquet_release(folder: Path) -> tuple[dict, dict]:
    source = dict(
        source_id="INVENTED-source",
        publisher="INVENTED-publisher",
        title="INVENTED-dataset",
        url="https://invented.invalid/dataset",
        licence="INVENTED-licence",
        licence_basis="dataset",
        retrieved_on="2026-11-20",
        sha256="bc" * 32,
    )
    rows = {
        "source_registry": [dict(source, kind="public_dataset", origin="public")],
        "fact_lineage": [
            dict(
                lineage_id="INVENTED-lineage",
                source_id=source["source_id"],
                table_name="pub_census_national",
                transform="invented.hold@v1",
                input_class="public",
            )
        ],
        "pub_census_national": [dict(source_id=source["source_id"])],
    }
    assert set(source) == set(SOURCE_KEYS)
    document = _document()
    document["sources"] = [source]
    document["tables"] = []
    _write_chain_parquet(folder, document, rows)
    return document, rows


def _write_chain_parquet(folder: Path, document: dict, rows: dict) -> None:
    """Rebuild each file, logical-schema hash and release hash after every plant."""
    import hashlib

    import duckdb

    (folder / "tables").mkdir(exist_ok=True)
    entries = []
    connection = duckdb.connect()
    try:
        for name, records in rows.items():
            columns = list(records[0])
            schema = canonical_json(
                [
                    dict(name=key, logical_type="string", nullable=False)
                    for key in columns
                ]
            )
            target = folder / "tables" / (name + ".parquet")
            connection.execute(
                "CREATE OR REPLACE TABLE invented ("
                + ", ".join('"' + key + '" VARCHAR' for key in columns)
                + ")"
            )
            connection.executemany(
                "INSERT INTO invented VALUES (" + ", ".join("?" for _ in columns) + ")",
                [[record[key] for key in columns] for record in records],
            )
            connection.execute(
                "COPY invented TO '" + str(target).replace("'", "''") + "' "
                "(FORMAT PARQUET, KV_METADATA {eii_logical_schema: '"
                + schema.replace("'", "''")
                + "'})"
            )
            entries.append(
                dict(
                    name=name,
                    file="tables/" + target.name,
                    grain="INVENTED",
                    provenance_class="public"
                    if name == "pub_census_national"
                    else "lineage",
                    row_count=len(records),
                    sha256=hashlib.sha256(target.read_bytes()).hexdigest(),
                    schema_sha256=hashlib.sha256(schema.encode()).hexdigest(),
                )
            )
    finally:
        connection.close()
    document["tables"] = entries
    document["release_id"] = release_hash(document)
    (folder / "manifest.json").write_text(canonical_json(document), encoding="utf-8")


def _document() -> dict:
    return {
        "artefacts": [],
        "build_id": "build-invented",
        "built_at": "2026-01-02T00:00:00Z",
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
                "file": "tables/pub_census_national.parquet",
                "grain": "invented",
                "name": "pub_census_national",
                "provenance_class": "public",
                "row_count": 1,
                "schema_sha256": "cd" * 32,
                "sha256": "ab" * 32,
            }
        ],
    }


def _json(document: dict) -> str:
    import json

    return json.dumps(document)
