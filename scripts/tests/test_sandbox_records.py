"""Fetch, record and verify. No sandbox and no network."""

from __future__ import annotations

import hashlib
import importlib
import io
import json
import os
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import sandbox_support as support

import engine_extensions
import extension_tree

ROOT = support.ROOT


def _pins() -> dict[tuple[str, str], dict[str, tuple[int, str]]]:
    row = {
        name: (len(data), hashlib.sha256(data).hexdigest())
        for name, data in support.FAKE_EXTENSION_BYTES.items()
    }
    return {(extension_tree.ENGINE, extension_tree.PLATFORM): row}


class RecordRules(unittest.TestCase):
    def test_pinned_table_is_well_formed(self) -> None:
        self.assertEqual(extension_tree.ENGINE, "v2.0.0")
        self.assertEqual(
            set(extension_tree.PINNED),
            {(extension_tree.ENGINE, extension_tree.PLATFORM)},
        )
        row = extension_tree.PINNED[(extension_tree.ENGINE, extension_tree.PLATFORM)]
        self.assertEqual(set(row), {"h3", "spatial"})
        for size, digest in row.values():
            self.assertIsInstance(size, int)
            self.assertGreater(size, 0)
            self.assertEqual(len(digest), 64)
            self.assertEqual(digest, digest.lower())
            self.assertTrue(
                all(character in "0123456789abcdef" for character in digest)
            )
        self.assertEqual(
            extension_tree.relative_files("v2.0.0"),
            [
                "v2.0.0/linux_amd64/h3.duckdb_extension",
                "v2.0.0/linux_amd64/h3.duckdb_extension.info",
                "v2.0.0/linux_amd64/spatial.duckdb_extension",
                "v2.0.0/linux_amd64/spatial.duckdb_extension.info",
            ],
        )
        self.assertEqual(engine_extensions.SOURCES["h3"][2], "Apache-2.0")
        self.assertEqual(engine_extensions.SOURCES["spatial"][2], "MIT")
        self.assertEqual(set(engine_extensions.SOURCES), {"h3", "spatial"})
        self.assertEqual(
            engine_extensions.STATEMENTS,
            ("INSTALL spatial", "INSTALL h3 FROM community"),
        )
        self.assertEqual(
            extension_tree.FETCH_COMMAND,
            "uv run --locked python scripts/engine_extensions.py fetch",
        )
        self.assertEqual(
            engine_extensions.SYNC_COMMAND,
            "uv sync --managed-python --all-packages --locked --group engine",
        )

    def test_fetch_configuration_and_statements(self) -> None:
        fake, _status, _out = self._fetch()
        self.assertEqual(
            fake.configs[0],
            {
                "autoinstall_known_extensions": False,
                "autoload_known_extensions": False,
                "extension_directories": [
                    str(self.root / "data" / "engine_extensions")
                ],
            },
        )
        self.assertNotIn("allow_unsigned_extensions", fake.configs[0])
        self.assertNotIn("enable_external_access", fake.configs[0])
        self.assertNotIn("extension_directory", fake.configs[0])
        self.assertEqual(
            fake.statements,
            [
                "select version()",
                "INSTALL spatial",
                "INSTALL h3 FROM community",
                engine_extensions.LISTING_SQL,
            ],
        )
        self.assertEqual(list(self.home.iterdir()), [])

    def test_fetch_record_and_output(self) -> None:
        _fake, _status, out = self._fetch()
        pins = _pins()[(extension_tree.ENGINE, extension_tree.PLATFORM)]
        h3_size, h3_hash = pins["h3"]
        spatial_size, spatial_hash = pins["spatial"]
        self.assertEqual(
            out.splitlines(),
            [
                "engine duckdb v2.0.0 linux_amd64",
                f"file v2.0.0/linux_amd64/h3.duckdb_extension {h3_size} bytes sha256 {h3_hash}",
                f"file v2.0.0/linux_amd64/spatial.duckdb_extension {spatial_size} bytes sha256 {spatial_hash}",
                "record written: data/engine_extensions/EXTENSIONS.json",
                "engine extensions: OK",
            ],
        )
        raw = (self.root / "data" / "engine_extensions" / "EXTENSIONS.json").read_text(
            encoding="utf-8"
        )
        self.assertTrue(raw.endswith("\n"))
        self.assertFalse(raw.endswith("\n\n"))
        record = json.loads(raw)
        self.assertEqual(record["schema"], 1)
        self.assertEqual(record["engine"], "duckdb")
        self.assertEqual(record["engine_version"], "v2.0.0")
        self.assertEqual(record["platform"], "linux_amd64")
        self.assertEqual(record["retrieved_on"], "2026-01-02")
        self.assertEqual(
            [item["name"] for item in record["extensions"]], ["h3", "spatial"]
        )
        keys = {
            "name",
            "repository",
            "host",
            "licence",
            "extension_version",
            "file",
            "size",
            "sha256",
            "info_file",
            "info_size",
        }
        for item in record["extensions"]:
            self.assertEqual(set(item), keys)
            self.assertEqual(item["info_size"], 4)
            self.assertNotIn("info_sha256", item)

    def test_fetch_and_main_failures(self) -> None:
        labels = []
        labels.append("a")
        fake = support.FakeDuckdb()
        fake.fail_on.append(
            ("INSTALL h3", support.FakeError("Failed to download x\nsecond line"))
        )
        status, out, root = self._run(["fetch"], fake)
        self.assertEqual(status, 1)
        self.assertEqual(out, "FAIL fetch: FakeError: Failed to download x\n")
        self.assertFalse(
            (root / "data" / "engine_extensions" / "EXTENSIONS.json").exists()
        )
        labels.append("b")
        wrong = _pins()
        size, _digest = wrong[(extension_tree.ENGINE, extension_tree.PLATFORM)]["h3"]
        wrong[(extension_tree.ENGINE, extension_tree.PLATFORM)]["h3"] = (size, "a" * 64)
        status, out, root = self._run(["fetch"], support.FakeDuckdb(), pinned=wrong)
        self.assertEqual(status, 1)
        self.assertIn(
            "FAIL v2.0.0/linux_amd64/h3.duckdb_extension has a SHA-256 that differs from the pinned "
            + "a" * 64,
            out,
        )
        self.assertTrue(out.endswith("engine extensions: FAILED\n"))
        self.assertFalse(
            (root / "data" / "engine_extensions" / "EXTENSIONS.json").exists()
        )
        labels.append("c")
        fake = support.FakeDuckdb()
        fake.version = "v9.9.9"
        status, out, _root = self._run(["fetch"], fake)
        self.assertEqual(
            out,
            "engine duckdb v9.9.9 linux_amd64\n"
            "FAIL no pinned hashes for engine v9.9.9 on linux_amd64: review the files and record them in scripts/extension_tree.py\n"
            "engine extensions: FAILED\n",
        )
        self.assertEqual(status, 1)
        labels.append("d")
        err = io.StringIO()
        for argv in ([], ["x"], ["fetch", "x"]):
            status = engine_extensions.main(
                argv, root=root, duckdb=support.FakeDuckdb(), out=io.StringIO(), err=err
            )
            self.assertEqual(status, 2)
        self.assertEqual(
            err.getvalue(), "engine_extensions: usage: fetch | verify\n" * 3
        )
        labels.append("e")
        with patch.object(
            support.exposed(engine_extensions, "importlib"),
            "import_module",
            side_effect=ImportError,
        ):
            status, out, _root = self._run(["fetch"], None)
        self.assertEqual(status, 1)
        self.assertEqual(
            out,
            "FAIL duckdb is not installed: run uv sync --managed-python --all-packages --locked --group engine\n",
        )
        labels.append("f")
        with patch.object(
            support.exposed(engine_extensions, "sys"), "platform", "darwin"
        ):
            status, out, _root = self._run(["fetch"], support.FakeDuckdb())
        self.assertEqual(status, 1)
        self.assertEqual(out, "FAIL this task supports only linux_amd64\n")
        labels.append("g")
        _fake, status, out = self._fetch()
        err = io.StringIO()
        verify_out = io.StringIO()
        with patch.object(extension_tree, "PINNED", _pins()):
            status = engine_extensions.verify(
                self.root, support.FakeDuckdb(), verify_out
            )
        self.assertEqual(status, 0)
        self.assertEqual(
            verify_out.getvalue(),
            "engine duckdb v2.0.0 linux_amd64\nengine extensions: OK\n",
        )
        self.assertEqual(labels, list("abcdefg"))

    def test_real_extension_folder_is_populated(self) -> None:
        try:
            duckdb = importlib.import_module("duckdb")
        except ImportError:
            self.fail(
                "duckdb is not installed: run uv sync --managed-python --all-packages --locked --group engine"
            )
        version = str(duckdb.connect().execute("select version()").fetchone()[0])
        problems = extension_tree.check_folder(
            ROOT / "data" / "engine_extensions", version
        )
        self.assertEqual(
            problems,
            [],
            "engine extensions are not fetched or differ from the pin; "
            "run: uv run --locked python scripts/engine_extensions.py fetch",
        )

    def _fetch(self) -> tuple[support.FakeDuckdb, int, str]:
        self.holder = tempfile.TemporaryDirectory()
        self.addCleanup(self.holder.cleanup)
        self.root = Path(self.holder.name).resolve()
        self.home = self.root / "home"
        self.home.mkdir()
        fake = support.FakeDuckdb()
        out = io.StringIO()
        with (
            patch.object(extension_tree, "PINNED", _pins()),
            patch.dict(os.environ, {"HOME": str(self.home)}),
        ):
            status = engine_extensions.main(
                ["fetch"],
                root=self.root,
                duckdb=fake,
                today=lambda: date(2026, 1, 2),
                out=out,
                err=io.StringIO(),
            )
        self.assertEqual(status, 0)
        return fake, status, out.getvalue()

    def _run(
        self,
        argv: list[str],
        duckdb: support.FakeDuckdb | None,
        pinned: dict[tuple[str, str], dict[str, tuple[int, str]]] | None = None,
    ) -> tuple[int, str, Path]:
        holder = tempfile.TemporaryDirectory()
        self.addCleanup(holder.cleanup)
        root = Path(holder.name).resolve()
        out = io.StringIO()
        with patch.object(
            extension_tree, "PINNED", _pins() if pinned is None else pinned
        ):
            status = engine_extensions.main(
                argv,
                root=root,
                duckdb=duckdb,
                today=lambda: date(2026, 1, 2),
                out=out,
                err=io.StringIO(),
            )
        return status, out.getvalue(), root
