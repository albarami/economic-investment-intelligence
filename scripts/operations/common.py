"""Closed operational failures and durable local records."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any


class Refusal(ValueError):
    """A diagnostic identifier only, never upstream text or configuration."""

    def __init__(self, reason: str, code: int = 4):
        self.reason = reason
        self.code = code
        super().__init__(reason)


def encoded(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()


def sha(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read_json(path: Path, reason: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_bytes())
    except (OSError, ValueError):
        raise Refusal(reason) from None
    if type(value) is not dict:
        raise Refusal(reason)
    return value


def atomic_json(path: Path, value: object) -> None:
    """Replace and sync both file and directory; callers hold their operation lock."""
    partial = path.with_name(path.name + ".partial")
    created = False
    try:
        with partial.open("xb") as stream:
            created = True
            stream.write(encoded(value) + b"\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(partial, path)
        descriptor = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    finally:
        if created:
            partial.unlink(missing_ok=True)
