"""Local assembly envelopes; reject escaping paths and unsupported values."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import asdict, is_dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

from shapely.geometry.base import BaseGeometry

from .assembly import AssemblyError, _output_path
from .fetch.bounded import file_hash


def local(root: Path, relative: str) -> Path:
    if root.is_symlink() or any(parent.is_symlink() for parent in root.parents):
        raise AssemblyError("assembly_path_invalid")
    path = _output_path(root, relative)
    current = root
    for part in Path(relative).parts:
        current = current / part
        if current.is_symlink():
            raise AssemblyError("assembly_path_invalid")
    return path


def json_value(value: object) -> object:
    if is_dataclass(value) and not isinstance(value, type):
        return asdict(value)
    if isinstance(value, (Decimal, date)):
        return str(value)
    if isinstance(value, bytes):
        return {"wkb_hex": value.hex()}
    if isinstance(value, BaseGeometry):
        return {"wkb_hex": value.wkb.hex()}
    raise AssemblyError("assembly_value_invalid")


def write_record(cache: Path, name: str, value: object) -> dict[str, str]:
    path = local(cache, name)
    body = (
        json.dumps(
            value,
            default=json_value,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as stream:
        stream.write(body)
        stream.flush()
        os.fsync(stream.fileno())
    return {name: file_hash(path)}


def read_object(root: Path, name: str) -> dict[str, Any]:
    try:
        value = json.loads(local(root, name).read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeError):
        raise AssemblyError("assembly_input_refused") from None
    if not isinstance(value, dict):
        raise AssemblyError("assembly_input_refused")
    return value


def bound_files(root: Path, files: Mapping[str, str]) -> None:
    for name, digest in files.items():
        try:
            if file_hash(local(root, name)) != digest:
                raise AssemblyError("assembly_output_invalid")
        except OSError:
            raise AssemblyError("assembly_output_invalid") from None
