"""A public release is refused before either store is opened."""

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from collections.abc import Callable
from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path
from typing import Any

import public_release_fixture as fixture

from eii_core.manifest import (
    CATALOGUE,
    FORBIDDEN_PUBLIC_ONLY,
    canonical_json,
    release_hash,
)
from eii_product.store.loader import PARTIAL_READER, READER_NAME, run_load
from eii_product.store.receipt import RECEIPT_NAME


def _boom(**_kwargs: object) -> object:
    message = "connection was opened"
    raise AssertionError(message)


class PublicReleaseRefusals(unittest.TestCase):
    def test_unlisted_table_loads_nowhere(self) -> None:
        """An extra parquet is refused by name and nothing is written."""
        with self._release() as folder:
            (folder / "tables" / "extra_table.parquet").write_bytes(b"invented")
            code, err = self._run(folder)
            self.assertEqual(code, 4)
            self.assertIn("unlisted_table extra_table", err)
            self._assert_unwritten(folder)

    def test_changed_file_is_digest_mismatch(self) -> None:
        """One changed byte of a listed file fails the file hash."""
        with self._release() as folder:
            path = next((folder / "tables").glob("*.parquet"))
            path.write_bytes(path.read_bytes() + b"x")
            code, err = self._run(folder)
            self.assertEqual(code, 4)
            self.assertIn("digest_mismatch", err)
            self._assert_unwritten(folder)

    def test_reordered_schema_is_digest_mismatch(self) -> None:
        """A reordered logical schema fails the schema hash."""
        with self._release() as folder:
            self._rewrite_schema(folder, _swap_columns, name="pub_census_national")
            code, err = self._run(folder)
            self.assertEqual(code, 4)
            self.assertIn("digest_mismatch", err)
            self._assert_unwritten(folder)

    def test_geometry_with_another_srid_is_digest_mismatch(self) -> None:
        """A geometry SRID other than 4326 fails the schema hash."""
        with self._release() as folder:
            self._rewrite_schema(folder, _zero_srid, name="district")
            code, err = self._run(folder)
            self.assertEqual(code, 4)
            self.assertIn("digest_mismatch", err)
            self._assert_unwritten(folder)

    def test_each_forbidden_field_and_table_is_refused(self) -> None:
        """The eight fields and every protected or simulated table are refused."""
        protected = [row.name for row in CATALOGUE if row.manifest_class == "protected"]
        simulated = [row.name for row in CATALOGUE if row.manifest_class == "simulated"]
        self.assertEqual(len(FORBIDDEN_PUBLIC_ONLY), 8)
        self.assertEqual(len(protected), 7)
        self.assertEqual(len(simulated), 6)
        with self._release() as folder:
            original = (folder / "manifest.json").read_bytes()
            for field in sorted(FORBIDDEN_PUBLIC_ONLY):
                self._write(folder, original, _add_field(field))
                code, err = self._run(folder)
                self.assertEqual(code, 4, field)
                self.assertIn("forbidden_manifest_field", err)
                self._assert_unwritten(folder)
            for name in (*protected, *simulated):
                self._write(folder, original, _add_table(name))
                code, err = self._run(folder)
                self.assertEqual(code, 4, name)
                self.assertIn("forbidden_table_class", err)
                self._assert_unwritten(folder)

    def test_release_manifest_parquet_is_refused(self) -> None:
        """release_manifest is not a catalogue table."""
        with self._release() as folder:
            original = (folder / "manifest.json").read_bytes()
            self._write(
                folder,
                original,
                lambda document: document["tables"].append(
                    {"name": "release_manifest", "provenance_class": "lineage"}
                ),
            )
            code, err = self._run(folder)
            self.assertEqual(code, 4)
            self.assertIn("unknown_table", err)
            self._assert_unwritten(folder)

    def test_empty_table_list_is_refused(self) -> None:
        """A manifest with no tables is refused."""
        with self._release() as folder:
            original = (folder / "manifest.json").read_bytes()
            self._write(
                folder, original, lambda document: document.__setitem__("tables", [])
            )
            code, err = self._run(folder)
            self.assertEqual(code, 4)
            self.assertIn("empty_table_list", err)
            self._assert_unwritten(folder)

    def test_public_split_label_as_class_is_refused(self) -> None:
        """The label Public (split) is not a manifest class."""
        with self._release() as folder:
            original = (folder / "manifest.json").read_bytes()
            self._write(folder, original, _split_label)
            code, err = self._run(folder)
            self.assertEqual(code, 4)
            self.assertIn("table_class_invalid", err)
            self._assert_unwritten(folder)

    def test_receipt_named_as_artefact_is_refused(self) -> None:
        """The receipt is not a manifest artefact."""
        with self._release() as folder:
            original = (folder / "manifest.json").read_bytes()
            self._write(
                folder,
                original,
                lambda document: document.__setitem__(
                    "artefacts",
                    [{"path": "load_receipt.json", "sha256": "ab" * 32}],
                ),
            )
            code, err = self._run(folder)
            self.assertEqual(code, 4)
            self.assertIn("receipt_listed_as_artefact", err)
            self._assert_unwritten(folder)

    def _run(self, folder: Path) -> tuple[int, str]:
        err = StringIO()
        with redirect_stderr(err):
            code = run_load(
                folder,
                host="127.0.0.1",
                port=1,
                database="invented",
                connect=_boom,
            )
        return code, err.getvalue()

    def _release(self) -> _Held:
        hold = tempfile.TemporaryDirectory()
        fixture.build_fixture(Path(hold.name))
        return _Held(hold)

    def _write(
        self, folder: Path, original: bytes, change: Callable[[dict[str, Any]], None]
    ) -> None:
        document = json.loads(original)
        change(document)
        document["release_id"] = release_hash(document)
        (folder / "manifest.json").write_bytes(canonical_json(document).encode("utf-8"))

    def _rewrite_schema(
        self,
        folder: Path,
        change: Callable[[list[Any]], None],
        name: str | None = None,
    ) -> None:
        import duckdb

        path = (
            folder / "tables" / f"{name}.parquet"
            if name
            else next((folder / "tables").glob("*.parquet"))
        )
        literal = "'" + str(path).replace("'", "''") + "'"
        connection = duckdb.connect()
        try:
            raw = connection.execute(
                f"SELECT value FROM parquet_kv_metadata({literal}) "
                "WHERE key = 'eii_logical_schema'"
            ).fetchone()
            self.assertIsNotNone(raw)
            assert raw is not None
            schema = json.loads(raw[0].decode("utf-8"))
            change(schema)
            text = canonical_json(schema).replace("'", "''")
            dest = path.with_suffix(".next.parquet")
            dest_literal = "'" + str(dest).replace("'", "''") + "'"
            connection.execute(
                f"COPY (SELECT * FROM read_parquet({literal})) TO {dest_literal} "
                f"(FORMAT PARQUET, KV_METADATA {{eii_logical_schema: '{text}'}})"
            )
        finally:
            connection.close()
        dest.replace(path)
        document = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
        for entry in document["tables"]:
            if entry["name"] == path.stem:
                entry["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        document["release_id"] = release_hash(document)
        (folder / "manifest.json").write_bytes(canonical_json(document).encode("utf-8"))

    def _assert_unwritten(self, folder: Path) -> None:
        self.assertFalse((folder / RECEIPT_NAME).exists())
        self.assertFalse((folder / READER_NAME).exists())
        self.assertFalse((folder / PARTIAL_READER).exists())


class _Held:
    def __init__(self, hold: tempfile.TemporaryDirectory[str]) -> None:
        self._hold = hold

    def __enter__(self) -> Path:
        return Path(self._hold.name)

    def __exit__(self, *_exc: object) -> None:
        self._hold.cleanup()


def _add_field(field: str) -> Callable[[dict[str, Any]], None]:
    def change(document: dict[str, Any]) -> None:
        document[field] = "x"

    return change


def _add_table(name: str) -> Callable[[dict[str, Any]], None]:
    def change(document: dict[str, Any]) -> None:
        tables = document["tables"]
        if isinstance(tables, list):
            tables.append(
                {
                    "file": f"tables/{name}.parquet",
                    "name": name,
                    "provenance_class": "protected",
                }
            )

    return change


def _swap_columns(schema: list[Any]) -> None:
    schema[0], schema[1] = schema[1], schema[0]


def _zero_srid(schema: list[Any]) -> None:
    for column in schema:
        if column.get("logical_type") == "geometry":
            column["srid"] = 0


def _split_label(document: dict[str, Any]) -> None:
    document["tables"][0]["provenance_class"] = "Public (split)"
