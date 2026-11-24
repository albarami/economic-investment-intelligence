"""Consume a reviewed, hash-bound Public assembly envelope inside the sandbox.

The envelope is an explicit input contract. Missing schemas, review, files or
lineage refuse the build; this module never invents a table or source record.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from eii_core.manifest import ColumnSpec, canonical_json
from eii_core.reasons import reason
from eii_custodian.release.approval import approval_reason
from eii_custodian.release.public_only import TableWrite, write_public_only


def read_assembly(cache: Path) -> dict[str, Any]:
    try:
        value = json.loads((cache / "assembly/release.json").read_bytes())
        review = json.loads((cache / "assembly/release_review.json").read_bytes())
        if (
            type(value) is not dict
            or set(value) - {"listed_inputs"}
            != {"version", "scalars", "sources", "tables", "artefacts", "files"}
            or value["version"] != 1
            or not isinstance(value["files"], dict)
            or "assembly/final_audit.json" not in value["files"]
        ):
            raise ValueError("assembly_input_refused")
        refusal = approval_reason(
            review,
            value["scalars"]["code_version"],
            hashlib.sha256(canonical_json(value).encode()).hexdigest(),
        )
        if refusal is not None:
            raise ValueError(refusal)
        for name, digest in value["files"].items():
            path = cache / name
            if (
                Path(name).is_absolute()
                or ".." in Path(name).parts
                or path.is_symlink()
                or not path.resolve().is_relative_to(cache.resolve())
            ):
                raise ValueError("assembly_path_refused")
            if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
                raise ValueError("assembly_file_hash_mismatch")
        from eii_custodian.publicdata.assembly_reports import require_complete

        require_complete(json.loads((cache / "assembly/final_audit.json").read_bytes()))
        return value
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise ValueError(reason(error, "assembly_input_refused")) from None


def decode(value: object, column: ColumnSpec) -> object:
    if value is None:
        return None
    if column.logical_type.startswith("decimal("):
        return Decimal(str(value))
    if column.logical_type == "date":
        return date.fromisoformat(str(value))
    if column.logical_type == "timestamp":
        return datetime.fromisoformat(str(value))
    if column.logical_type == "geometry":
        if not isinstance(value, dict) or set(value) != {"wkb_hex"}:
            raise ValueError("assembly_input_refused")
        return bytes.fromhex(value["wkb_hex"])
    return value


def build(cache: Path, destination: Path) -> str:
    document = read_assembly(cache)
    tables = []
    try:
        for item in document["tables"]:
            if set(item) != {"name", "columns", "rows"}:
                raise ValueError
            columns = tuple(ColumnSpec(**column) for column in item["columns"])
            rows = tuple(
                {column.name: decode(row[column.name], column) for column in columns}
                for row in item["rows"]
            )
            if any(
                set(row) != {column.name for column in columns} for row in item["rows"]
            ):
                raise ValueError
            tables.append(TableWrite(item["name"], columns, rows))
    except (ValueError, KeyError, TypeError) as error:
        raise ValueError(reason(error, "assembly_input_refused")) from None
    identity = write_public_only(
        destination,
        document["scalars"],
        document["sources"],
        tables,
        artefacts=document["artefacts"],
        listed_inputs=document.get("listed_inputs", ()),
    )
    # Artefacts are copied only from the reviewed, bound inventory.
    for item in document["artefacts"]:
        name = item["path"]
        if name not in document["files"] or item["sha256"] != document["files"][name]:
            raise ValueError("assembly_input_refused")
        path = destination / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes((cache / name).read_bytes())
    return identity
