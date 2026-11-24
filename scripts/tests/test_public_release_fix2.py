"""Load-time plants. Each refusal names its reason and opens neither store."""

from __future__ import annotations

import json
import tempfile
import unittest
from collections.abc import Callable
from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path
from typing import Any

import public_release_fixture as fixture

from eii_core.manifest import CATALOGUE, canonical_json, release_hash
from eii_product.store.loader import PARTIAL_READER, READER_NAME, run_load
from eii_product.store.receipt import RECEIPT_NAME


def _boom(**_kwargs: object) -> object:
    message = "connection was opened"
    raise AssertionError(message)


class LoadRefusals(unittest.TestCase):
    def test_duplicate_key_at_either_depth(self) -> None:
        """A repeated manifest key, including a nested one, is refused by name."""
        texts = (
            '{"release_kind":"public_only","release_kind":"public_only"}',
            '{"sources":[{"source_id":"src-invented","source_id":"src-other"}]}',
        )
        for text in texts:
            with self.subTest(text=text):
                with self._empty() as folder:
                    (folder / "manifest.json").write_text(text, encoding="utf-8")
                    self._expect(folder, "duplicate_key")

    def test_unknown_manifest_key_is_refused(self) -> None:
        """An unknown manifest key is refused before either store opens."""
        with self._release() as folder:
            self._mutate(folder, lambda document: document.__setitem__("notes", "x"))
            self._expect(folder, "unknown_manifest_key")

    def test_manifest_key_in_another_case_is_refused(self) -> None:
        """WINDOW_KEY and Window_Key are not the privacy key and are refused."""
        for key in ("WINDOW_KEY", "Window_Key"):
            with self.subTest(key=key):
                with self._release() as folder:
                    self._mutate(
                        folder,
                        lambda document, name=key: document.__setitem__(name, "x"),
                    )
                    self._expect(folder, "manifest_key_case")

    def test_wrong_manifest_types_are_refused(self) -> None:
        """A number, a string and a boolean in the wrong place are refused."""
        plants = (
            ("sources", 17),
            ("tables", "pub_census_national"),
        )
        for key, value in plants:
            with self.subTest(key=key):
                with self._release() as folder:
                    self._mutate(
                        folder,
                        lambda document, name=key, planted=value: document.__setitem__(
                            name, planted
                        ),
                    )
                    self._expect(folder, "manifest_type_invalid")
        with self._release() as folder:
            self._mutate(
                folder,
                lambda document: document["tables"][0].__setitem__("row_count", True),
            )
            self._expect(folder, "manifest_type_invalid")

    def test_duplicate_table_is_refused(self) -> None:
        """The same table listed twice is refused before either store opens."""
        with self._release() as folder:
            self._mutate(
                folder,
                lambda document: document["tables"].append(dict(document["tables"][0])),
            )
            self._expect(folder, "duplicate_table")

    def test_absolute_table_path_is_refused(self) -> None:
        """An absolute table path is refused before the file is read."""
        with self._release() as folder:
            name = "pub_census_national"
            outside = folder.parent / f"{name}.parquet"
            self._retarget(folder, name, str(outside.resolve()))
            self._expect(folder, "absolute_path")

    def test_traversal_is_refused(self) -> None:
        """A table path with a .. component is refused before the file is read."""
        with self._release() as folder:
            name = "pub_census_national"
            self._retarget(folder, name, f"../{name}.parquet")
            self._expect(folder, "path_traversal")

    def test_symbolic_link_inside_the_release_is_refused(self) -> None:
        """A symlink whose target stays in the release is refused by name."""
        with self._release() as folder:
            name = "pub_census_national"
            path = folder / "tables" / f"{name}.parquet"
            held = folder / "held.parquet"
            path.rename(held)
            path.symlink_to(held)
            self._expect(folder, "symbolic_link")

    def test_resolved_path_outside_the_release_is_refused(self) -> None:
        """A symlink that resolves outside the release is refused by name."""
        with self._release() as folder:
            name = "pub_census_national"
            path = folder / "tables" / f"{name}.parquet"
            held = folder.parent / "outside.parquet"
            path.rename(held)
            path.symlink_to(held)
            self._expect(folder, "path_outside_release")

    def test_each_privacy_written_table_is_refused(self) -> None:
        """Every privacy-written table that is not Protected or Simulated is refused."""
        names = [
            row.name
            for row in CATALOGUE
            if row.writer == "privacy"
            and row.manifest_class not in {"protected", "simulated"}
        ]
        self.assertEqual(
            names,
            [
                "release_unit",
                "unit_member",
                "rules_version",
                "suppression_reason",
                "survival_report",
            ],
        )
        for name in names:
            with self.subTest(name=name):
                with self._release() as folder:
                    if name == "rules_version":
                        self._write_parameter_set(folder)
                    catalogue = next(row for row in CATALOGUE if row.name == name)
                    self._mutate(
                        folder,
                        lambda document, table=name, kind=catalogue.manifest_class: (
                            document["tables"].append(
                                {
                                    "file": f"tables/{table}.parquet",
                                    "name": table,
                                    "provenance_class": kind,
                                }
                            )
                        ),
                    )
                    self._expect(folder, "privacy_written_table")

    def test_missing_lineage_table_is_refused(self) -> None:
        """A release without fact_lineage is refused before either store opens."""
        with self._release() as folder:
            self._drop_table(folder, "fact_lineage")
            self._expect(folder, "source_link_missing")

    def test_incomplete_source_is_refused(self) -> None:
        """A manifest source without its publisher is incomplete."""
        with self._release() as folder:
            self._mutate(
                folder, lambda document: document["sources"][0].__delitem__("publisher")
            )
            self._expect(folder, "source_link_incomplete")

    def test_unknown_source_is_refused(self) -> None:
        """A manifest source_id that is not registered is unknown."""
        with self._release() as folder:
            self._mutate(
                folder,
                lambda document: document["sources"][0].__setitem__(
                    "source_id", "src-missing"
                ),
            )
            self._expect(folder, "source_link_unknown")

    def test_mismatched_source_is_refused(self) -> None:
        """A manifest publisher that differs from the registry is a mismatch."""
        with self._release() as folder:
            self._mutate(
                folder,
                lambda document: document["sources"][0].__setitem__(
                    "publisher", "INVENTED-other"
                ),
            )
            self._expect(folder, "source_link_mismatch")

    def _expect(self, folder: Path, reason: str) -> None:
        code, err = self._run(folder)
        self.assertEqual(code, 4, err)
        self.assertIn(reason, err)
        self.assertNotIn("connection was opened", err)
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

    def _empty(self) -> _Held:
        return _Held(tempfile.TemporaryDirectory())

    def _mutate(self, folder: Path, change: Callable[..., None]) -> None:
        path = folder / "manifest.json"
        document = json.loads(path.read_text(encoding="utf-8"))
        change(document)
        document["release_id"] = release_hash(document)
        path.write_bytes(canonical_json(document).encode("utf-8"))

    def _retarget(self, folder: Path, name: str, file_name: str) -> None:
        def change(document: dict[str, Any]) -> None:
            for entry in document["tables"]:
                if entry["name"] == name:
                    entry["file"] = file_name

        self._mutate(folder, change)

    def _drop_table(self, folder: Path, name: str) -> None:
        (folder / "tables" / f"{name}.parquet").unlink()

        def change(document: dict[str, Any]) -> None:
            document["tables"] = [
                entry for entry in document["tables"] if entry["name"] != name
            ]

        self._mutate(folder, change)

    def _write_parameter_set(self, folder: Path) -> None:
        import duckdb

        path = folder / "tables" / "rules_version.parquet"
        connection = duckdb.connect()
        try:
            connection.execute(
                "CREATE TABLE rules_version ("
                "rules_version_id VARCHAR, parameter_set VARCHAR, rule_code VARCHAR)"
            )
            connection.execute(
                "INSERT INTO rules_version VALUES ('invented-rules', 'A', 'invented_rule')"
            )
            connection.execute(f"COPY rules_version TO {_sql(path)} (FORMAT PARQUET)")
            columns = connection.execute(
                "SELECT name FROM parquet_schema("
                + _sql(path)
                + ") WHERE name != 'schema'"
            ).fetchall()
        finally:
            connection.close()
        self.assertIn(("parameter_set",), columns)

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


def _sql(path: Path) -> str:
    return "'" + str(path).replace("'", "''") + "'"
