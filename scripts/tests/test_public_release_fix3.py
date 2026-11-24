"""Engine-version plants. Each refusal names its reason and opens neither store."""

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

from eii_core.manifest import canonical_json, release_hash
from eii_product.store.loader import PARTIAL_READER, READER_NAME, run_load
from eii_product.store.receipt import RECEIPT_NAME


def _boom(**_kwargs: object) -> object:
    message = "connection was opened"
    raise AssertionError(message)


def _wrong_type(value: object) -> Any:
    """Hand a value through without a suppression comment."""
    return value


def _rename(source: str, target: str) -> Callable[[dict[str, Any]], None]:
    def change(engines: dict[str, Any]) -> None:
        engines[target] = engines.pop(source)

    return change


class EngineVersionRefusals(unittest.TestCase):
    def test_missing_engine_key_is_refused(self) -> None:
        """A map without python is refused before either store opens."""
        with self._release() as folder:
            self._mutate(folder, lambda engines: engines.pop("python"))
            self._expect(folder, "manifest_type_invalid")

    def test_unknown_engine_key_is_refused(self) -> None:
        """An engine key outside duckdb, postgis_target and python is refused."""
        with self._release() as folder:
            self._mutate(
                folder,
                lambda engines: engines.__setitem__("invented_engine", "1.0.0"),
            )
            self._expect(folder, "unknown_manifest_key")

    def test_engine_key_in_another_case_is_refused(self) -> None:
        """DuckDB and PYTHON are not the engine keys."""
        plants = (
            ("duckdb", "DuckDB"),
            ("python", "PYTHON"),
        )
        for old, new in plants:
            with self.subTest(key=new):
                with self._release() as folder:
                    self._mutate(folder, _rename(old, new))
                    self._expect(folder, "manifest_key_case")

    def test_empty_engine_version_is_refused(self) -> None:
        """An empty version string is refused before either store opens."""
        with self._release() as folder:
            self._mutate(folder, lambda engines: engines.__setitem__("python", ""))
            self._expect(folder, "manifest_type_invalid")

    def test_non_string_engine_version_is_refused(self) -> None:
        """A version that is not a string is refused before either store opens."""
        with self._release() as folder:
            self._mutate(
                folder,
                lambda engines: engines.__setitem__("python", _wrong_type(3)),
            )
            self._expect(folder, "manifest_type_invalid")

    def _expect(self, folder: Path, reason: str) -> None:
        code, err = self._run(folder)
        self.assertEqual(code, 4, err)
        self.assertIn(f"FAIL load-release: {reason}", err)
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

    def _mutate(self, folder: Path, change: Callable[[dict[str, Any]], None]) -> None:
        path = folder / "manifest.json"
        document = json.loads(path.read_text(encoding="utf-8"))
        engines = document["engine_versions"]
        if type(engines) is not dict:
            message = "engine_versions missing"
            raise AssertionError(message)
        change(engines)
        document["release_id"] = release_hash(document)
        path.write_bytes(canonical_json(document).encode("utf-8"))

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
