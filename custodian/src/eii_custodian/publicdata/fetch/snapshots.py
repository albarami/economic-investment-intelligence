"""Immutable dated cache objects, indexed receipts and append-only check events.

The caller supplies a documented cache directory and a reviewed identity. There
is no latest selection, transport, backup destination or credential handling.
"""

from __future__ import annotations

import hashlib
import json
import re
import tempfile
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import NoReturn

from eii_custodian.publicdata.fetch.bounded import file_hash, publish_complete

_HASH = re.compile(r"[a-f0-9]{64}")
_EXT = re.compile(r"[a-z][a-z0-9.]*")


class SnapshotError(ValueError):
    """A fixed cache refusal; upstream diagnostics are never included."""


def _refuse(reason: str) -> NoReturn:
    raise SnapshotError(reason) from None


def utc(value: object) -> datetime:
    """Require a timezone-aware UTC timestamp, not a date or local time."""
    if not isinstance(value, str):
        _refuse("snapshot_date_missing")
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        _refuse("snapshot_date_missing")
    if result.tzinfo is None or result.utcoffset() != timedelta(0):
        _refuse("snapshot_date_missing")
    return result


def _dump(value: dict[str, object]) -> bytes:
    return (json.dumps(value, sort_keys=True, ensure_ascii=True) + "\n").encode()


def _object(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_bytes())
    except (OSError, ValueError):
        _refuse("snapshot_index_invalid")
    if not isinstance(value, dict):
        _refuse("snapshot_index_invalid")
    return value


def _publish(directory: Path, target: Path, body: bytes) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".snapshot-", dir=directory) as folder:
        staged = Path(folder) / "bytes"
        staged.write_bytes(body)
        publish_complete(staged, target, _refuse)


@dataclass(frozen=True)
class Snapshot:
    receipt_path: Path
    path: Path
    sha256: str
    sidecar: dict[str, object]

    @property
    def body(self) -> bytes:
        """Recheck content even when a caller holds this reference across writes."""
        body = self.path.read_bytes()
        if hashlib.sha256(body).hexdigest() != self.sha256:
            _refuse("snapshot_hash_mismatch")
        return body


def read_snapshot(directory: Path, identity: str) -> Snapshot:
    """Verify the named index, immutable receipt and body before returning bytes."""
    if _HASH.fullmatch(identity) is None:
        _refuse("snapshot_path_invalid")
    row = _object(directory / "index" / f"{identity}.json")
    stamp = utc(row.get("retrieved_utc"))
    digest = row.get("sha256")
    extension = row.get("extension")
    if not isinstance(digest, str) or _HASH.fullmatch(digest) is None:
        _refuse("snapshot_index_invalid")
    if not isinstance(extension, str) or _EXT.fullmatch(extension) is None:
        _refuse("snapshot_index_invalid")
    body_day = (
        utc(str(row.get("body_date", stamp.date().isoformat())) + "T00:00:00Z")
        .date()
        .isoformat()
    )
    relative = f"{body_day}/{digest}.{extension}"
    if row.get("path") != relative or row.get("identity") != identity:
        _refuse("snapshot_path_invalid")
    path = directory / relative
    receipt = directory / str(row.get("receipt"))
    expected_receipt = f"{stamp.date().isoformat()}/{identity}.meta.json"
    if row.get("receipt") != expected_receipt:
        _refuse("snapshot_path_invalid")
    if not path.resolve().is_relative_to(
        directory.resolve()
    ) or not receipt.resolve().is_relative_to(directory.resolve()):
        _refuse("snapshot_path_invalid")
    try:
        if file_hash(receipt) != row.get("receipt_sha256"):
            _refuse("snapshot_hash_mismatch")
        side = _object(receipt)
        actual = file_hash(path)
        size = path.stat().st_size
    except OSError:
        _refuse("snapshot_missing")
    if actual != digest:
        _refuse("snapshot_hash_mismatch")
    if type(row.get("bytes")) is not int or row["bytes"] != size:
        _refuse("snapshot_hash_mismatch")
    for key in (
        "source_id",
        "key",
        "retrieved_utc",
        "source_modified",
        "sha256",
        "bytes",
    ):
        if side.get(key) != row.get(key):
            _refuse("snapshot_index_invalid")
    return Snapshot(receipt_path=receipt, path=path, sha256=digest, sidecar=side)


def publish_snapshot(
    directory: Path,
    extension: str,
    body: bytes,
    sidecar: dict[str, object],
    *,
    identity: str | None = None,
    compatibility: bool = False,
) -> Snapshot:
    """Publish once; equal bytes retain their receipt and append a check event."""
    try:
        directory.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=".snapshot-", dir=directory) as folder:
            staged = Path(folder) / "bytes"
            staged.write_bytes(body)
            return publish_file(
                directory,
                extension,
                staged,
                sidecar,
                identity=identity,
                compatibility=compatibility,
            )
    except OSError:
        raise SnapshotError(
            str(sidecar.get("source_id", "snapshot")) + ": snapshot_write_failed"
        ) from None


def publish_file(
    directory: Path,
    extension: str,
    staged: Path,
    sidecar: dict[str, object],
    *,
    identity: str | None = None,
    compatibility: bool = False,
) -> Snapshot:
    """Publish a staged file with fixed source-scoped write diagnostics."""
    try:
        return _publish_file(
            directory,
            extension,
            staged,
            sidecar,
            identity=identity,
            compatibility=compatibility,
        )
    except OSError:
        raise SnapshotError(
            str(sidecar.get("source_id", "snapshot")) + ": snapshot_write_failed"
        ) from None


def _publish_file(
    directory: Path,
    extension: str,
    staged: Path,
    sidecar: dict[str, object],
    *,
    identity: str | None = None,
    compatibility: bool = False,
) -> Snapshot:
    """Stream-hash a staged file and publish without loading an archive in memory."""
    stamp = utc(sidecar.get("retrieved_utc"))
    digest = file_hash(staged)
    size = staged.stat().st_size
    selected = digest if identity is None else identity
    if _HASH.fullmatch(selected) is None or _EXT.fullmatch(extension) is None:
        _refuse("snapshot_path_invalid")
    for key in ("source_id", "key"):
        if not isinstance(sidecar.get(key), str) or not sidecar[key]:
            _refuse("snapshot_index_invalid")
    if sidecar.get("sha256", digest) != digest or sidecar.get("bytes", size) != size:
        _refuse("snapshot_hash_mismatch")
    directory.mkdir(parents=True, exist_ok=True)
    index = directory / "index" / f"{selected}.json"
    try:
        if index.exists():
            snapshot = read_snapshot(directory, selected)
            if snapshot.sha256 != digest:
                _refuse("snapshot_conflict")
            for key in ("source_id", "key"):
                if snapshot.sidecar[key] != sidecar[key]:
                    _refuse("snapshot_conflict")
        else:
            day = stamp.date().isoformat()
            bodies = sorted(directory.glob(f"????-??-??/{digest}.{extension}"))
            body_day = bodies[0].parent.name if bodies else day
            relative = f"{body_day}/{digest}.{extension}"
            receipt = f"{day}/{selected}.meta.json"
            side = dict(sidecar, sha256=digest, bytes=size)
            receipt_body = _dump(side)
            row = dict(
                side,
                identity=selected,
                extension=extension,
                path=relative,
                receipt=receipt,
                receipt_sha256=hashlib.sha256(receipt_body).hexdigest(),
            )
            if body_day != day:
                row["body_date"] = body_day
            (directory / day).mkdir(parents=True, exist_ok=True)
            publish_complete(staged, directory / relative, _refuse)
            _publish(directory, directory / receipt, receipt_body)
            _publish(directory, index, _dump(row))
            snapshot = read_snapshot(directory, selected)
        if compatibility:
            publish_complete(
                snapshot.path, directory / f"{selected}.{extension}", _refuse
            )
            publish_complete(
                directory
                / utc(snapshot.sidecar["retrieved_utc"]).date().isoformat()
                / f"{selected}.meta.json",
                directory / f"{selected}.meta.json",
                _refuse,
            )
        check = _dump(dict(sidecar, identity=selected, sha256=digest, bytes=size))
        check_hash = hashlib.sha256(check).hexdigest()
        _publish(directory, directory / "checks" / f"{check_hash}.json", check)
        return snapshot
    except OSError:
        _refuse("snapshot_write_failed")


def reviewed_selections(cache: Path) -> dict[str, str]:
    """Read the lead's explicit key-to-hash review file, never directory history."""
    path = cache / "snapshot_pins.json"
    if not path.exists():
        return {}
    row = _object(path)
    if any(
        not isinstance(value, str) or _HASH.fullmatch(value) is None
        for value in row.values()
    ):
        _refuse("snapshot_selection_invalid")
    return {key: str(value) for key, value in row.items()}


def checked_times(directory: Path) -> tuple[str, ...]:
    """Verify immutable check events and their referenced bytes before scheduling."""
    times: list[str] = []
    for path in sorted((directory / "checks").glob("*.json")):
        if file_hash(path) != path.stem:
            _refuse("snapshot_hash_mismatch")
        check = _object(path)
        identity = check.get("identity")
        if not isinstance(identity, str):
            _refuse("snapshot_index_invalid")
        snapshot = read_snapshot(directory, identity)
        for key in ("source_id", "key", "sha256", "bytes"):
            if check.get(key) != snapshot.sidecar.get(key):
                _refuse("snapshot_index_invalid")
        stamp = check.get("retrieved_utc")
        utc(stamp)
        times.append(str(stamp))
    return tuple(times)
