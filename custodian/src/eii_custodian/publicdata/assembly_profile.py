"""Local awards profile measurements, without inferring semantic column mappings."""

from __future__ import annotations

import csv
import io
import re
from pathlib import Path
from typing import Any

from .assembly import AssemblyError
from .fetch.awards import _xlsx
from .fetch.bounded import CHUNK_BYTES
from .fetch.receipts import sha256_hex

_INTEGER = re.compile(r"-?(?:0|[1-9][0-9]*)", re.ASCII)
_NUMBER = re.compile(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?", re.ASCII)


def bounded_input(path: Path, ceiling: int, digest: object) -> bytes:
    chunks = []
    total = 0
    with path.open("rb") as stream:
        while chunk := stream.read(CHUNK_BYTES):
            total += len(chunk)
            if total > ceiling:
                raise AssemblyError("assembly_intake_bound")
            chunks.append(chunk)
    body = b"".join(chunks)
    if sha256_hex(body) != digest:
        raise AssemblyError("assembly_intake_invalid")
    return body


def observe_profile(body: bytes, format: str, sheet: str) -> dict[str, Any]:
    try:
        raw = (
            list(csv.reader(io.StringIO(body.decode("utf-8-sig"))))
            if format == "csv"
            else _xlsx(body, sheet)
            if format == "xlsx" and sheet
            else []
        )
    except (UnicodeError, csv.Error):
        raise AssemblyError("assembly_intake_invalid") from None
    if (
        not raw
        or not raw[0]
        or len(set(raw[0])) != len(raw[0])
        or any(not value for value in raw[0])
    ):
        raise AssemblyError("assembly_intake_invalid")
    columns = raw[0]
    rows = raw[1:]
    if format == "xlsx":
        rows = [row + [""] * (len(columns) - len(row)) for row in rows]
    if any(len(row) != len(columns) for row in rows):
        raise AssemblyError("assembly_intake_invalid")
    types = []
    for index in range(len(columns)):
        values = [row[index].strip() for row in rows if row[index].strip()]
        kind = "string"
        if values and all(_INTEGER.fullmatch(value) for value in values):
            kind = "integer"
        elif values and all(_NUMBER.fullmatch(value) for value in values):
            kind = "number"
        types.append(kind)
    return {
        "format": format,
        "sheet": sheet,
        "original_columns": columns,
        "inferred_types": types,
        "row_count": len(rows),
        "type_method": "lexical-columns.v1",
    }
