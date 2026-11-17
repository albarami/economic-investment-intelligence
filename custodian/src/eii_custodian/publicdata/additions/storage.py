"""Stage typed Parquet tables and publish them only as a complete set."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from collections.abc import Mapping, Sequence
from pathlib import Path

import duckdb

from eii_custodian.publicdata.additions.common import AdditionError

_NAME = re.compile(r"^[a-z][a-z0-9_]*$")


def write_parquet(
    path: Path,
    columns: Sequence[tuple[str, str]],
    rows: Sequence[Sequence[object]],
) -> str:
    """Write one Parquet file and return its SHA-256. An empty row set is valid."""
    path.parent.mkdir(parents=True, exist_ok=True)
    definitions = ", ".join(_definition(name, kind) for name, kind in columns)
    connection = duckdb.connect()
    try:
        connection.execute(f"CREATE TABLE staged ({definitions})")
        if rows:
            placeholders = ", ".join(["?"] * len(columns))
            connection.executemany(
                f"INSERT INTO staged VALUES ({placeholders})",
                [tuple(row) for row in rows],
            )
        target = path.as_posix().replace("'", "''")
        connection.execute(f"COPY staged TO '{target}' (FORMAT PARQUET)")
    finally:
        connection.close()
    return hashlib.sha256(path.read_bytes()).hexdigest()


def publish(
    output: Path,
    tables: Sequence[tuple[str, Sequence[tuple[str, str]], Sequence[Sequence[object]]]],
    manifest: Mapping[str, object],
    report: Mapping[str, object],
) -> Path:
    """Publish every table, the manifest and the report, or leave the previous set."""
    staging = output / ".staging"
    destination = output / "current"
    previous = output / ".previous"
    if staging.exists():
        shutil.rmtree(staging)
    (staging / "tables").mkdir(parents=True)
    moved = False
    try:
        files: list[dict[str, object]] = []
        for name, columns, rows in tables:
            if _NAME.fullmatch(name) is None:
                raise AdditionError("table_name")
            digest = write_parquet(
                staging / "tables" / f"{name}.parquet", columns, rows
            )
            files.append({"name": name, "rows": len(rows), "sha256": digest})
        body = dict(manifest)
        body["tables"] = files
        _write_json(staging / "manifest.json", body)
        _write_json(staging / "build_report.json", report)
        if previous.exists():
            shutil.rmtree(previous)
        if destination.exists():
            destination.rename(previous)
            moved = True
        staging.rename(destination)
        moved = False
        if previous.exists():
            shutil.rmtree(previous)
    except Exception:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)
        if moved and previous.exists() and not destination.exists():
            previous.rename(destination)
        raise
    return destination


def _definition(name: str, kind: str) -> str:
    if _NAME.fullmatch(name) is None:
        raise AdditionError("column_name")
    return f'"{name}" {kind}'


def _write_json(path: Path, body: Mapping[str, object]) -> None:
    path.write_text(
        json.dumps(body, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8"
    )
