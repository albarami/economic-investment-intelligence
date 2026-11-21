"""Bounded immutable shards using section 3.1 snapshot publication, never latest."""

from __future__ import annotations

import hashlib
import io
import json
import re
import tarfile
import tempfile
from collections.abc import Callable, Iterable, Iterator, Mapping
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from typing import Any

from eii_custodian.publicdata.fetch.bounded import file_hash
from eii_custodian.publicdata.fetch.snapshots import (
    Snapshot,
    SnapshotError,
    publish_file,
    read_snapshot,
    utc,
)

from .snapshot_policy import (
    GENERATOR,
    MAX_TILE_BYTES,
    SHARD_TILES,
    SnapshotRefusal,
    level_allowed,
    safe_child,
    service_url,
)
from .snapshot_receipt import public_chain, publish_public, validate_receipt


def canonical(row: object) -> bytes:
    return (
        json.dumps(row, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n"
    ).encode()


def digest(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def read_checked(directory: Path, identity: str) -> Snapshot:
    """Do not read an index/receipt/body through an escaped or symbolic path."""
    if re.fullmatch(r"[a-f0-9]{64}", identity) is None:
        raise SnapshotRefusal("archive_integrity")
    try:
        index = safe_child(directory, "index/" + identity + ".json")
        row = json.loads(index.read_bytes())
        for key in ("path", "receipt"):
            if not isinstance(row.get(key), str):
                raise SnapshotRefusal("archive_integrity")
            safe_child(directory, row[key])
        return read_snapshot(directory, identity)
    except (OSError, ValueError, KeyError, TypeError, SnapshotError):
        raise SnapshotRefusal("archive_integrity") from None


def _immutable(path: Path, body: bytes) -> None:
    """Link-publish once; an interrupted staging file is never a completed object."""
    from eii_custodian.publicdata.fetch.snapshots import _publish

    try:
        if path.exists() and path.read_bytes() != body:
            raise SnapshotRefusal("enumeration_identity_changed")
        _publish(path.parent, path, body)
    except (OSError, SnapshotError):
        raise SnapshotRefusal("archive_integrity") from None


def jpeg(body: bytes) -> None:
    """Bound size/dimensions before fully decoding with the pinned JPEG driver."""
    memory_file = import_module("rasterio.io").MemoryFile
    decode_error = import_module("rasterio.errors").RasterioIOError
    gdal_env = import_module("rasterio").Env

    if (
        not 21 <= len(body) <= MAX_TILE_BYTES
        or not body.startswith(b"\xff\xd8\xff")
        or not body.endswith(b"\xff\xd9")
    ):
        raise SnapshotRefusal("tile_format_or_gap")
    cursor = 2
    while cursor + 4 <= len(body):
        if body[cursor] != 255:
            break
        while cursor + 1 < len(body) and body[cursor + 1] == 255:
            cursor += 1
        marker = body[cursor + 1]
        size = int.from_bytes(body[cursor + 2 : cursor + 4], "big")
        if size < 2 or cursor + 2 + size > len(body):
            break
        if marker in {
            0xC0,
            0xC1,
            0xC2,
            0xC3,
            0xC5,
            0xC6,
            0xC7,
            0xC9,
            0xCA,
            0xCB,
            0xCD,
            0xCE,
            0xCF,
        }:
            if size < 8:
                break
            height = int.from_bytes(body[cursor + 5 : cursor + 7], "big")
            width = int.from_bytes(body[cursor + 7 : cursor + 9], "big")
            if width != 512 or height != 512:
                raise SnapshotRefusal("tile_dimensions_refused")
            try:
                with gdal_env(GDAL_ERROR_ON_LIBJPEG_WARNING="TRUE"):
                    with memory_file(body, filename="tile.jpg") as memory:
                        with memory.open(driver="JPEG") as dataset:
                            dataset.read()
            except decode_error:
                raise SnapshotRefusal("tile_format_or_gap") from None
            return
        if marker in {0xDA, 0xD9}:
            break
        cursor += 2 + size
    raise SnapshotRefusal("tile_format_or_gap")


def unpack(snapshot: Snapshot) -> Iterator[tuple[int, int, int, bytes]]:
    try:
        members = snapshot.sidecar["members"]
        if not isinstance(members, list) or not 0 <= len(members) <= SHARD_TILES:
            raise SnapshotRefusal("archive_integrity")
        if file_hash(snapshot.path) != snapshot.sha256:
            raise SnapshotRefusal("archive_integrity")
        with tarfile.open(snapshot.path, mode="r:") as archive:
            served = archive.getmembers()
            if len(served) != len(members):
                raise SnapshotRefusal("archive_integrity")
            seen: set[str] = set()
            for item, proof in zip(served, members, strict=True):
                if (
                    not isinstance(proof, dict)
                    or item.name in seen
                    or not re.fullmatch(r"[0-9]+/[0-9]+/[0-9]+\.jpg", item.name)
                    or not item.isfile()
                    or item.size > MAX_TILE_BYTES
                ):
                    raise SnapshotRefusal("archive_integrity")
                seen.add(item.name)
                stream = archive.extractfile(item)
                if stream is None:
                    raise SnapshotRefusal("archive_integrity")
                body = stream.read(MAX_TILE_BYTES + 1)
                if proof != {
                    "name": item.name,
                    "sha256": digest(body),
                    "bytes": len(body),
                }:
                    raise SnapshotRefusal("archive_integrity")
                jpeg(body)
                level, row, column = (
                    int(part) for part in item.name.removesuffix(".jpg").split("/")
                )
                level_allowed(level)
                yield level, row, column, body
    except (SnapshotError, OSError, tarfile.TarError, KeyError, TypeError, ValueError):
        raise SnapshotRefusal("archive_integrity") from None


def checked_gap(gap: Any) -> list[int]:
    """Validate gap eligibility before publication and on every verified read."""
    if not isinstance(gap, dict) or set(gap) != {
        "key",
        "http_status",
        "reason",
        "attempts",
        "retrieved_utc",
    }:
        raise SnapshotRefusal("archive_integrity")
    key = gap["key"]
    status, attempts = gap["http_status"], gap["attempts"]
    if gap["reason"] not in {
        "request_failed",
        "response_bytes_or_gap",
        "tile_format_or_gap",
        "tile_dimensions_refused",
        "outside_extent",
    }:
        raise SnapshotRefusal("gap_reason_integrity")
    if (
        gap["reason"] == "request_failed"
        and (status not in {404, 410} or attempts != 1)
    ) or (
        gap["reason"]
        in {
            "response_bytes_or_gap",
            "tile_format_or_gap",
            "tile_dimensions_refused",
        }
        and (status != 200 or attempts != 1)
    ):
        raise SnapshotRefusal("gap_reason_integrity")
    if (
        not isinstance(key, list)
        or len(key) != 3
        or any(type(n) is not int or n < 0 for n in key)
        or type(attempts) is not int
        or not 0 <= attempts <= 4
        or (
            status is not None and (type(status) is not int or not 100 <= status <= 599)
        )
        or (gap["reason"] == "outside_extent" and (attempts != 0 or status is not None))
        or (gap["reason"] != "outside_extent" and attempts == 0)
    ):
        raise SnapshotRefusal("archive_integrity")
    level_allowed(key[0])
    utc(gap["retrieved_utc"])
    return key


def checked_gaps(snapshot: Snapshot, expected: list[list[int]]) -> list[dict[str, Any]]:
    """Every enumerated key occurs once, as either a JPEG member or a fixed gap."""
    actual = [[level, row, column] for level, row, column, _ in unpack(snapshot)]
    gaps = snapshot.sidecar.get("gaps")
    if not isinstance(gaps, list) or not expected:
        raise SnapshotRefusal("archive_integrity")
    keys = [checked_gap(gap) for gap in gaps]
    combined = actual + keys
    if (
        len(combined) > SHARD_TILES
        or sorted(combined) != expected
        or len({tuple(key) for key in combined}) != len(combined)
    ):
        raise SnapshotRefusal("gap_enumeration_integrity")
    return gaps


def shard_lineage(
    side: Mapping[str, Any], enumeration: Mapping[str, Any], shard: int
) -> None:
    if (
        side.get("metadata_sha256") != enumeration["metadata_sha256"]
        or side.get("boundary_sha256") != enumeration["boundary_sha256"]
        or side.get("enumeration_sha256") != digest(canonical(enumeration))
        or side.get("shard") != shard
    ):
        raise SnapshotRefusal("shard_lineage_integrity")


class Archive:
    def __init__(self, root: Path, enumeration: dict[str, Any]) -> None:
        self.root = root
        self.enumeration = enumeration
        level_allowed(enumeration["level"])
        service_url(enumeration["date"])
        for key in ("boundary_sha256", "metadata_sha256"):
            if not re.fullmatch(r"[a-f0-9]{64}", enumeration[key]):
                raise SnapshotRefusal("enumeration_identity_invalid")
        root.mkdir(parents=True, exist_ok=True)
        _immutable(safe_child(root, "enumeration.json"), canonical(enumeration))
        self.identity = digest(canonical(enumeration))

    def _folder(self, shard: int) -> Path:
        if type(shard) is not int or shard < 0:
            raise SnapshotRefusal("shard_key")
        return safe_child(self.root, f"shards/{shard:06d}")

    def expected(self, shard: int) -> list[list[int]]:
        return list(
            self.enumeration["tiles"][shard * SHARD_TILES : (shard + 1) * SHARD_TILES]
        )

    def read_shard(self, shard: int) -> Snapshot:
        folder = self._folder(shard)
        try:
            identity = json.loads(safe_child(folder, "selection.json").read_bytes())[
                "identity"
            ]
            snap = read_checked(folder, identity)
            side = snap.sidecar
            validate_receipt(snap, "shard", self.enumeration["date"])
            shard_lineage(side, self.enumeration, shard)
            checked_gaps(snap, self.expected(shard))
            return snap
        except SnapshotRefusal:
            raise
        except (OSError, ValueError, KeyError, TypeError, SnapshotError):
            raise SnapshotRefusal("archive_integrity") from None

    def has_shard(self, shard: int) -> bool:
        folder = self._folder(shard)
        if (folder / "selection.json").exists():
            self.read_shard(shard)
            return True
        # A completed object without its pointer is an interruption, never skipped.
        return False

    def write_shard(
        self,
        shard: int,
        tiles: Mapping[tuple[int, int, int], bytes],
        retrieved_utc: str,
    ) -> str:
        return self.write_shard_stream(shard, sorted(tiles.items()), retrieved_utc)

    def write_shard_stream(
        self,
        shard: int,
        tiles: Iterable[tuple[tuple[int, int, int], bytes]],
        retrieved_utc: str | Callable[[], str],
        *,
        gaps: list[dict[str, Any]] | None = None,
    ) -> str:
        folder = self._folder(shard)
        folder.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=".staging-", dir=folder) as directory:
            staged = Path(directory) / "shard.tar"
            members: list[dict[str, object]] = []
            actual: list[list[int]] = []
            with tarfile.open(staged, "w") as archive:
                for (level, row, column), body in tiles:
                    if len(actual) >= SHARD_TILES:
                        raise SnapshotRefusal("shard_bound")
                    level_allowed(level)
                    if any(type(n) is not int or n < 0 for n in (row, column)):
                        raise SnapshotRefusal("tile_key_refused")
                    jpeg(body)
                    name = f"{level}/{row}/{column}.jpg"
                    member = tarfile.TarInfo(name)
                    member.size = len(body)
                    archive.addfile(member, io.BytesIO(body))
                    members.append(
                        {"name": name, "sha256": digest(body), "bytes": len(body)}
                    )
                    actual.append([level, row, column])
            missing = [] if gaps is None else gaps
            gap_keys = [checked_gap(gap) for gap in missing]
            if not self.expected(shard) or sorted(actual + gap_keys) != self.expected(
                shard
            ):
                raise SnapshotRefusal("enumeration_identity_mismatch")
            identity = digest(
                canonical(
                    {
                        "enumeration": self.identity,
                        "shard": shard,
                        "sha256": file_hash(staged),
                        "gaps": missing,
                    }
                )
            )
            stamp = retrieved_utc() if callable(retrieved_utc) else retrieved_utc
            return self._publish_shard(
                shard, folder, staged, members, missing, stamp, identity
            )

    def _publish_shard(
        self,
        shard: int,
        folder: Path,
        staged: Path,
        members: list[dict[str, object]],
        gaps: list[dict[str, Any]],
        retrieved_utc: str,
        identity: str,
    ) -> str:
        side: dict[str, object] = {
            **public_chain("shard", self.enumeration["date"], retrieved_utc),
            "metadata_sha256": self.enumeration["metadata_sha256"],
            "boundary_sha256": self.enumeration["boundary_sha256"],
            "enumeration_sha256": self.identity,
            "members": members,
            "gaps": gaps,
            "shard": shard,
        }
        try:
            snap = publish_file(folder, "tar", staged, side, identity=identity)
            _immutable(
                safe_child(folder, "selection.json"), canonical({"identity": identity})
            )
            self.read_shard(shard)
            return snap.sha256
        except SnapshotError:
            raise SnapshotRefusal("archive_integrity") from None

    def complete(self, shards: list[int], retrieved_utc: str) -> str:
        count = (len(self.enumeration["tiles"]) + SHARD_TILES - 1) // SHARD_TILES
        if not count or shards != list(range(count)):
            raise SnapshotRefusal("completion_gaps")
        records = []
        gaps = []
        for shard in shards:
            snap = self.read_shard(shard)
            gaps.extend(checked_gaps(snap, self.expected(shard)))
            records.append(
                {
                    "shard": shard,
                    "identity": snap.sidecar.get(
                        "identity",
                        json.loads(
                            (self._folder(shard) / "selection.json").read_bytes()
                        )["identity"],
                    ),
                    "sha256": snap.sha256,
                }
            )
        body = canonical(
            {
                "version": GENERATOR,
                "enumeration": self.enumeration,
                "shards": records,
                "gaps": gaps,
                "gap_count": len(gaps),
                "uncovered": self.enumeration.get("uncovered"),
                "complete": True,
            }
        )
        identity = digest(body)
        side = public_chain("completion", self.enumeration["date"], retrieved_utc)
        try:
            publish_public(safe_child(self.root, "completion"), body, side, identity)
        except SnapshotError:
            raise SnapshotRefusal("completion_integrity") from None
        return identity


@dataclass(frozen=True)
class Selection:
    files: tuple[tuple[Path, str], ...]
    date: str
    shards: tuple[Snapshot, ...]
    gaps: tuple[dict[str, Any], ...] = ()
    uncovered: dict[str, Any] | None = None

    def iter_tiles(self) -> Iterator[tuple[str, int, int, int, bytes]]:
        for shard in self.shards:
            for level, row, column, body in unpack(shard):
                yield self.date, level, row, column, body


def verify_selection(root: Path, manifest: str) -> Selection:
    """Explicit complete manifest only; never glob for a latest acquisition."""
    try:
        completion = read_checked(safe_child(root, "completion"), manifest)
        data = json.loads(completion.body)
        if data.get("complete") is not True or data.get("version") != GENERATOR:
            raise SnapshotRefusal("completion_incomplete")
        archive = Archive.__new__(Archive)
        archive.root, archive.enumeration = root, data["enumeration"]
        validate_receipt(completion, "completion", archive.enumeration["date"])
        archive.identity = digest(canonical(archive.enumeration))
        if safe_child(root, "enumeration.json").read_bytes() != canonical(
            archive.enumeration
        ):
            raise SnapshotRefusal("completion_integrity")
        expected_count = (
            len(archive.enumeration["tiles"]) + SHARD_TILES - 1
        ) // SHARD_TILES
        if not expected_count or [s["shard"] for s in data["shards"]] != list(
            range(expected_count)
        ):
            raise SnapshotRefusal("completion_gaps")
        files = [
            (completion.path, completion.sha256),
            (completion.receipt_path, digest(completion.receipt_path.read_bytes())),
        ]
        snapshots = []
        gaps = []
        for row in data["shards"]:
            snap = read_checked(archive._folder(row["shard"]), row["identity"])
            validate_receipt(snap, "shard", archive.enumeration["date"])
            shard_lineage(snap.sidecar, archive.enumeration, row["shard"])
            if snap.sha256 != row["sha256"]:
                raise SnapshotRefusal("completion_integrity")
            gaps.extend(checked_gaps(snap, archive.expected(row["shard"])))
            snapshots.append(snap)
            files.extend(
                (
                    (snap.path, snap.sha256),
                    (snap.receipt_path, digest(snap.receipt_path.read_bytes())),
                )
            )
        if (
            data.get("gaps") != gaps
            or data.get("gap_count") != len(gaps)
            or data.get("uncovered") != archive.enumeration.get("uncovered")
        ):
            raise SnapshotRefusal("completion_coverage_integrity")
        for name, identity in archive.enumeration.get("inputs", {}).items():
            if name not in {"metadata", "boundary"}:
                raise SnapshotRefusal("completion_integrity")
            item = read_checked(safe_child(root, "inputs/" + name), identity)
            validate_receipt(item, name, archive.enumeration["date"])
            if (
                name == "boundary"
                and item.sidecar["upstream_sha256"]
                != archive.enumeration["boundary_sha256"]
            ):
                raise SnapshotRefusal("boundary_upstream_integrity")
            if item.sha256 != identity:
                raise SnapshotRefusal("completion_integrity")
            if (
                name == "metadata"
                and identity != archive.enumeration["metadata_sha256"]
            ):
                raise SnapshotRefusal("completion_integrity")
            files.extend(
                (
                    (item.path, item.sha256),
                    (item.receipt_path, digest(item.receipt_path.read_bytes())),
                )
            )
        for path, _ in files:
            safe_child(root, str(path.relative_to(root)))
        return Selection(
            tuple(files),
            archive.enumeration["date"],
            tuple(snapshots),
            tuple(gaps),
            data.get("uncovered"),
        )
    except SnapshotRefusal:
        raise
    except (OSError, ValueError, KeyError, TypeError, SnapshotError):
        raise SnapshotRefusal("completion_integrity_or_incomplete") from None
