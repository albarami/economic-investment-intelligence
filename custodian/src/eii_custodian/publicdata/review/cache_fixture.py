"""Cache bodies for tests, and the cache reader the build uses.

``write_cached`` is test support: it writes an invented body and its sidecar
through the S2-T01 commit contract. ``read_cached`` is production code: it
finds the content-addressed body of one registry key, checks it against its
sidecar and refuses a missing, ambiguous or stale pair.
"""

from __future__ import annotations

import csv
import io
import json
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

from eii_custodian.publicdata.fetch.receipts import (
    cache_directory,
    commit_pair,
    sha256_hex,
    sidecar_for,
)
from eii_custodian.publicdata.fetch.registry import Entry

RETRIEVED_UTC = "2026-11-01T00:00:00Z"
PARQUET_BATCH = 1024
_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_REL_NS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"


class CacheError(Exception):
    """A cached pair is missing, ambiguous or stale."""

    def __init__(self, detail: str) -> None:
        self.detail = detail
        super().__init__(detail)


@dataclass(frozen=True)
class CachedBody:
    """One verified cache body with its sidecar."""

    path: Path
    body: bytes
    sidecar: dict[str, object]


def write_cached(
    cache: Path,
    entry: Entry,
    body: bytes,
    *,
    extension: str | None = None,
    switched_off: bool = False,
    digest: str | None = None,
    nbytes: int | None = None,
    row_count: int | None = None,
) -> Path:
    """Write an invented body and its sidecar, and return the body path."""
    suffix = extension if extension is not None else entry.extension
    sha = digest if digest is not None else sha256_hex(body)
    size = nbytes if nbytes is not None else len(body)
    sidecar = sidecar_for(
        entry,
        digest=sha,
        nbytes=size,
        fetch_url=entry.url,
        fetch_host=entry.fetch_host,
        retrieved_utc=RETRIEVED_UTC,
        publisher=entry.publisher,
        source_modified="",
        row_count=row_count,
        terms_sha256="",
        switched_off=switched_off,
    )
    commit_pair(cache_directory(cache, entry.key), sha, suffix, body, sidecar)
    return cache_directory(cache, entry.key) / f"{sha}.{suffix}"


def read_cached(
    cache: Path, entry: Entry, *, extension: str | None = None
) -> CachedBody:
    """Return the one verified body of a key, or refuse the pair."""
    directory = cache_directory(cache, entry.key)
    if not directory.is_dir():
        raise CacheError("cache directory missing for " + entry.key)
    suffix = "." + (extension if extension is not None else entry.extension)
    bodies = sorted(
        path
        for path in directory.iterdir()
        if path.is_file()
        and path.name.endswith(suffix)
        and not path.name.endswith(".meta.json")
    )
    if not bodies:
        raise CacheError("cache body missing for " + entry.key)
    if len(bodies) > 1:
        raise CacheError("cache body ambiguous for " + entry.key)
    body_path = bodies[0]
    side_path = directory / f"{body_path.stem}.meta.json"
    if not side_path.is_file():
        raise CacheError("cache sidecar missing for " + entry.key)
    body = body_path.read_bytes()
    sidecar = _sidecar(side_path)
    if sidecar.get("sha256") != body_path.stem:
        raise CacheError("cache sidecar names another digest")
    if sidecar.get("sha256") != sha256_hex(body):
        raise CacheError("cache body digest differs from its sidecar")
    if sidecar.get("bytes") != len(body):
        raise CacheError("cache body size differs from its sidecar")
    if sidecar.get("key") != entry.key:
        raise CacheError("cache sidecar names another key")
    if sidecar.get("source_id") != entry.source_id:
        raise CacheError("cache sidecar names another source")
    if sidecar.get("switched_off") is not False:
        raise CacheError("cache body is switched off")
    return CachedBody(path=body_path, body=body, sidecar=sidecar)


def read_rows(cached: CachedBody) -> tuple[dict[str, Any], ...]:
    """Decode one verified body into row maps by its own suffix."""
    suffix = cached.path.suffix.lower()
    if suffix == ".json":
        return _json_rows(cached.body)
    if suffix == ".csv":
        return read_csv(cached.body)
    if suffix == ".xlsx":
        return read_xlsx(cached.body)
    if suffix == ".parquet":
        return read_parquet(cached.body)
    raise CacheError("cache body has no row reader for " + suffix)


def read_json(body: bytes) -> object:
    """Parse a JSON cache body."""
    return json.loads(body.decode("utf-8"))


def read_csv(body: bytes) -> tuple[dict[str, str], ...]:
    """Parse a CSV cache body with its header row."""
    text = body.decode("utf-8")
    return tuple(dict(row) for row in csv.DictReader(io.StringIO(text)))


def read_xlsx(body: bytes) -> tuple[dict[str, str], ...]:
    """Parse the first sheet of an XLSX body with the standard library."""
    with zipfile.ZipFile(io.BytesIO(body)) as archive:
        shared = _shared_strings(archive)
        sheet = _first_sheet(archive)
        rows = _sheet_rows(archive.read(sheet), shared)
    if not rows:
        return ()
    header = rows[0]
    return tuple(
        {
            name: (row[index] if index < len(row) else "")
            for index, name in enumerate(header)
        }
        for row in rows[1:]
    )


def read_parquet(body: bytes) -> tuple[dict[str, Any], ...]:
    """Read a Parquet body through DuckDB in bounded batches, imported only here."""
    import duckdb

    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "body.parquet"
        path.write_bytes(body)
        connection = duckdb.connect()
        try:
            cursor = connection.execute(
                f"SELECT * FROM read_parquet('{_sql_path(path)}')"
            )
            names = [item[0] for item in cursor.description]
            rows: list[dict[str, Any]] = []
            while True:
                batch = cursor.fetchmany(PARQUET_BATCH)
                if not batch:
                    break
                rows.extend(dict(zip(names, row, strict=True)) for row in batch)
            return tuple(rows)
        finally:
            connection.close()


def _json_rows(body: bytes) -> tuple[dict[str, Any], ...]:
    loaded = read_json(body)
    if not isinstance(loaded, list):
        raise CacheError("cache json body is not a list of rows")
    rows: list[dict[str, Any]] = []
    for item in loaded:
        if not isinstance(item, dict):
            raise CacheError("cache json row is not a map")
        rows.append({str(key): value for key, value in item.items()})
    return tuple(rows)


def _sql_path(path: Path) -> str:
    return path.as_posix().replace("'", "''")


def _sidecar(path: Path) -> dict[str, object]:
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, ValueError) as error:
        raise CacheError("cache sidecar is not JSON") from error
    if not isinstance(loaded, dict):
        raise CacheError("cache sidecar is not a map")
    return {str(key): value for key, value in loaded.items()}


def _shared_strings(archive: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []
    root = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
    return [
        "".join(node.text or "" for node in item.iter(_NS + "t"))
        for item in root.iter(_NS + "si")
    ]


def _first_sheet(archive: zipfile.ZipFile) -> str:
    names = set(archive.namelist())
    if "xl/workbook.xml" in names and "xl/_rels/workbook.xml.rels" in names:
        book = ElementTree.fromstring(archive.read("xl/workbook.xml"))
        sheet = next(book.iter(_NS + "sheet"), None)
        if sheet is not None:
            rels = ElementTree.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
            target = {
                node.get("Id"): node.get("Target", "")
                for node in rels.iter(
                    "{http://schemas.openxmlformats.org/package/2006/relationships}Relationship"
                )
            }.get(sheet.get(_REL_NS + "id"))
            if target:
                name = target.lstrip("/")
                if not name.startswith("xl/"):
                    name = "xl/" + name
                if name in names:
                    return name
    return "xl/worksheets/sheet1.xml"


def _sheet_rows(body: bytes, shared: list[str]) -> list[list[str]]:
    root = ElementTree.fromstring(body)
    rows: list[list[str]] = []
    for row in root.iter(_NS + "row"):
        cells: dict[int, str] = {}
        for index, cell in enumerate(row.iter(_NS + "c")):
            cells[_column(cell.get("r"), index)] = _cell_text(cell, shared)
        width = max(cells) + 1 if cells else 0
        rows.append([cells.get(index, "") for index in range(width)])
    return rows


def _column(reference: str | None, fallback: int) -> int:
    if not reference:
        return fallback
    letters = "".join(char for char in reference if char.isalpha())
    value = 0
    for char in letters:
        value = value * 26 + (ord(char.upper()) - ord("A") + 1)
    return value - 1


def _cell_text(cell: ElementTree.Element, shared: list[str]) -> str:
    kind = cell.get("t")
    if kind == "inlineStr":
        return "".join(node.text or "" for node in cell.iter(_NS + "t"))
    value = cell.find(_NS + "v")
    text = "" if value is None or value.text is None else value.text
    if kind == "s" and text.isdigit():
        index = int(text)
        return shared[index] if index < len(shared) else ""
    return text
