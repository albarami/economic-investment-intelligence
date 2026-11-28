"""Local assembly envelopes; reject escaping paths and unsupported values."""

from __future__ import annotations

import json
import os
import secrets
import stat
from collections.abc import Iterator, Mapping
from dataclasses import asdict, dataclass, is_dataclass
from datetime import date
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
from typing import Any

from shapely.geometry.base import BaseGeometry

from .assembly import AssemblyError, _output_path
from .fetch.bounded import file_hash
from .grids.population import PopulationRows, PopulationTable


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


class _RowList(list[dict[str, Any]]):
    """List protocol for the stdlib's incremental encoder, without row copies."""

    def __init__(self, rows: PopulationRows | PopulationTable) -> None:
        self.rows = rows

    def __len__(self) -> int:
        return len(self.rows)

    def __iter__(self) -> Iterator[dict[str, Any]]:
        return iter(self.rows)


class _RecordEncoder(json.JSONEncoder):
    def iterencode(self, o: Any, _one_shot: bool = False) -> Iterator[str]:
        # The C encoder inspects the underlying list storage of _RowList.
        # Always use the stdlib's streaming list protocol, including encode().
        return super().iterencode(o, _one_shot=False)


def json_value(value: object) -> object:
    if isinstance(value, (PopulationRows, PopulationTable)):
        return _RowList(value)
    if is_dataclass(value) and not isinstance(value, type):
        return asdict(value)
    if isinstance(value, (Decimal, date)):
        return str(value)
    if isinstance(value, bytes):
        return {"wkb_hex": value.hex()}
    if isinstance(value, BaseGeometry):
        return {"wkb_hex": value.wkb.hex()}
    raise AssemblyError("assembly_value_invalid")


def record_encoder() -> json.JSONEncoder:
    return _RecordEncoder(
        default=json_value, sort_keys=True, ensure_ascii=False, allow_nan=False
    )


@dataclass
class HeldRecord:
    """Same-run row references, with frozen metadata and the written file hash."""

    data: dict[str, Any]
    sha256: str

    @classmethod
    def capture(cls, value: dict[str, Any], digest: str) -> HeldRecord:
        # Freeze metadata that later phases may extend (notably source_tables).
        # Only the table mapping is copied; its rows remain the producer's rows.
        metadata = {key: item for key, item in value.items() if key != "tables"}
        data = json.loads(record_encoder().encode(metadata))
        data["tables"] = dict(value["tables"])
        return cls(data, digest)

    def verify(self) -> dict[str, Any]:
        # Reconstruct the exact write_record bytes incrementally, never a second
        # phase-sized text or parsed object. The stored file is bound separately.
        digest = sha256()
        for chunk in record_encoder().iterencode(self.data):
            digest.update(chunk.encode("utf-8"))
        digest.update(b"\n")
        if digest.hexdigest() != self.sha256:
            raise AssemblyError("assembly_draw_held_rows_changed")
        return self.data


_PARTIAL_CREATE_ATTEMPTS = 8


def write_record(cache: Path, name: str, value: object) -> dict[str, str]:
    path = local(cache, name)
    digest = sha256()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        descriptor: int | None = None
        collision: FileExistsError | None = None
        for _attempt in range(_PARTIAL_CREATE_ATTEMPTS):
            partial = path.parent / (
                "." + path.name + "." + secrets.token_hex(8) + ".partial"
            )
            try:
                descriptor = os.open(
                    partial, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o666
                )
            except FileExistsError as error:
                collision = error
                continue
            temporary = partial
            break
        if temporary is None or descriptor is None:
            if collision is None:
                raise FileExistsError(path)
            raise collision
        with os.fdopen(descriptor, "wb") as stream:
            pending: list[str] = []
            characters = 0
            for chunk in record_encoder().iterencode(value):
                pending.append(chunk)
                characters += len(chunk)
                if characters >= 16384:
                    body = "".join(pending).encode("utf-8")
                    stream.write(body)
                    digest.update(body)
                    pending.clear()
                    characters = 0
            body = "".join(pending).encode("utf-8")
            stream.write(body)
            digest.update(body)
            stream.write(b"\n")
            digest.update(b"\n")
            stream.flush()
            os.fsync(stream.fileno())
        reread = file_hash(temporary)
        if reread != digest.hexdigest():
            raise AssemblyError("assembly_output_invalid")
        try:
            os.chmod(temporary, stat.S_IMODE(os.stat(path).st_mode))
        except FileNotFoundError:
            pass
        os.replace(temporary, path)
        return {name: reread}
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


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
