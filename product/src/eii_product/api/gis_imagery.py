"""Read credited pictures only from immutable released artifacts, same origin."""

from __future__ import annotations

import hashlib
import json
import os
import re
import threading
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Response

_HASH = re.compile(r"[a-f0-9]{64}")
_DATE = re.compile(r"[0-9]{4}-[0-9]{2}")


class ReleasedImagery:
    def __init__(self, directory: Path, manifest_sha256: str) -> None:
        self.directory = directory
        self._verified: set[tuple[str, int, int, int, int, int]] = set()
        self._hash_lock = threading.Lock()
        if _HASH.fullmatch(manifest_sha256) is None:
            raise ValueError("imagery_manifest_integrity")
        try:
            body = self._path(manifest_sha256 + ".json").read_bytes()
            if hashlib.sha256(body).hexdigest() != manifest_sha256:
                raise ValueError("imagery_manifest_integrity")
            data = json.loads(body)
            if (
                data["version"] != "gis-snapshot-v1"
                or data["numerical_evidence"] is not False
                or not data["sources"]
            ):
                raise ValueError("imagery_manifest_integrity")
            self.tiles: dict[str, Any] = data["tiles"]
            self.sources: tuple[dict[str, Any], ...] = tuple(data["sources"])
            self.credit = self.sources[0]
            self.coverage: dict[str, Any] = data["coverage"]
        except (OSError, KeyError, TypeError, json.JSONDecodeError):
            raise ValueError("imagery_manifest_integrity") from None

    def _path(self, relative: str) -> Path:
        candidate = self.directory / relative
        if (
            self.directory.resolve() != self.directory
            or candidate.resolve() != candidate
            or not candidate.is_relative_to(self.directory)
        ):
            raise ValueError("imagery_path_integrity")
        return candidate

    def tile(self, date: str, level: int, row: int, column: int) -> bytes | None:
        if type(level) is not int or not 0 <= level <= 10:
            raise ValueError(
                "level_11_deferred"
                if type(level) is int and level == 11
                else "imagery_level_refused"
            )
        if _DATE.fullmatch(date) is None or any(
            type(n) is not int or n < 0 for n in (row, column)
        ):
            raise ValueError("imagery_tile_key")
        tile = self.tiles.get(f"{date}/{level}/{row}/{column}")
        if tile is None:
            return None
        try:
            sha = tile["object_sha256"]
            if not isinstance(sha, str) or _HASH.fullmatch(sha) is None:
                raise ValueError("imagery_integrity")
            offset, size = tile["offset"], tile["bytes"]
            if (
                type(offset) is not int
                or type(size) is not int
                or offset < 0
                or not 6 <= size <= 4 * 1024 * 1024
            ):
                raise ValueError("imagery_integrity")
            path = self._path("objects/" + sha + ".tar")
            with path.open("rb") as stream:
                with self._hash_lock:
                    status = os.fstat(stream.fileno())
                    token = (
                        sha,
                        status.st_dev,
                        status.st_ino,
                        status.st_size,
                        status.st_mtime_ns,
                        status.st_ctime_ns,
                    )
                    if token not in self._verified:
                        actual_hash = hashlib.file_digest(stream, "sha256").hexdigest()
                        after = os.fstat(stream.fileno())
                        if (
                            actual_hash != sha
                            or (
                                after.st_dev,
                                after.st_ino,
                                after.st_size,
                                after.st_mtime_ns,
                                after.st_ctime_ns,
                            )
                            != token[1:]
                        ):
                            raise ValueError("imagery_integrity")
                        self._verified.add(token)
                stream.seek(offset)
                body = stream.read(size)
            if (
                hashlib.sha256(body).hexdigest() != tile["member_sha256"]
                or not body.startswith(b"\xff\xd8\xff")
                or not body.endswith(b"\xff\xd9")
            ):
                raise ValueError("imagery_integrity")
            return body
        except (OSError, KeyError, TypeError):
            raise ValueError("imagery_integrity") from None


def imagery_router(imagery: ReleasedImagery | None) -> APIRouter:
    router = APIRouter()

    @router.get("/api/gis-imagery/{date}/{level}/{row}/{column}")
    def tile(date: str, level: int, row: int, column: int) -> Response:
        if imagery is None:
            raise HTTPException(status_code=404, detail="missing-source")
        try:
            body = imagery.tile(date, level, row, column)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from None
        if body is None:
            raise HTTPException(status_code=404, detail="missing-coverage")
        return Response(
            body,
            media_type="image/jpeg",
            headers={"Cache-Control": "public, immutable"},
        )

    @router.get("/api/gis-imagery/credit")
    def credit() -> dict[str, object]:
        return (
            {"status": "missing-source"}
            if imagery is None
            else {
                "sources": imagery.sources,
                "coverage": imagery.coverage,
                "numerical_evidence": False,
            }
        )

    return router
