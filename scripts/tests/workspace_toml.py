"""TOML load and dump helpers for workspace metadata tests."""

from __future__ import annotations

import json
import tomllib
from pathlib import Path
from typing import Any


def load_toml(path: Path) -> dict[str, Any] | None:
    """Parse a TOML file when it exists and is valid."""
    if not path.is_file():
        return None
    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError:
        return None


def _dump_scalar(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    if isinstance(value, str):
        return json.dumps(value)
    raise TypeError(type(value))


def _dump_inline(value: object) -> str:
    if isinstance(value, dict):
        parts = [f"{json.dumps(str(k))} = {_dump_inline(v)}" for k, v in value.items()]
        return "{ " + ", ".join(parts) + " }"
    if isinstance(value, list):
        return "[ " + ", ".join(_dump_inline(v) for v in value) + " ]"
    return _dump_scalar(value)


def dump_toml(data: dict[str, Any]) -> str:
    """Write a subset of TOML used by the metadata tests."""
    lines: list[str] = []
    nested: list[tuple[str, dict[str, Any]]] = []

    def emit_table(table: dict[str, Any], prefix: str) -> None:
        scalars: list[str] = []
        for key, value in table.items():
            if isinstance(value, dict):
                nested.append((f"{prefix}.{key}" if prefix else key, value))
            elif isinstance(value, list):
                inline = _dump_inline(value)
                scalars.append(f"{key} = {inline}")
            else:
                scalars.append(f"{key} = {_dump_scalar(value)}")
        for line in scalars:
            lines.append(line)

    emit_table(data, "")
    while nested:
        path, table = nested.pop(0)
        lines.append(f"[{path}]")
        emit_table(table, path)
    return "\n".join(lines) + "\n"
