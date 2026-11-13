"""Tile artefact path rules and provisional status endpoint.

``GET /tiles`` on the application is provisional until task S3-T08 serves the
full health page (OPS-30). A non-empty regular file with a resolvable name reads
as ``ok`` even when its bytes are not a valid tile archive; only presence,
emptiness and path shape are judged here.
"""

from __future__ import annotations

import re
from pathlib import Path

from fastapi import APIRouter, HTTPException
from starlette.responses import FileResponse

TILE_NAME = re.compile(r"^[a-z][a-z0-9_-]*\.tile$")

_PROBE_NAME = "spike.tile"


def tile_path(tile_dir: Path, name: str) -> Path | None:
    """Return a resolved file path when ``name`` stays inside ``tile_dir``."""
    if TILE_NAME.fullmatch(name) is None:
        return None
    base = tile_dir.resolve()
    candidate = (tile_dir / name).resolve()
    try:
        candidate.relative_to(base)
    except ValueError:
        return None
    return candidate


def tile_status(tile_dir: Path, name: str) -> str:
    """Return ``ok``, ``missing`` or ``invalid`` from the filesystem alone."""
    resolved = tile_path(tile_dir, name)
    if resolved is None or not resolved.exists():
        return "missing"
    if resolved.is_dir():
        return "invalid"
    if resolved.stat().st_size == 0:
        return "invalid"
    return "ok"


def build_router(tile_dir: Path) -> APIRouter:
    """Routes for one tile file and the provisional ``/tiles`` status."""
    router = APIRouter()

    @router.get("/tiles/{name}")
    def serve_tile(name: str) -> FileResponse:
        resolved = tile_path(tile_dir, name)
        if resolved is None or not resolved.is_file():
            raise HTTPException(status_code=404, detail="not found")
        return FileResponse(resolved, media_type="application/octet-stream")

    @router.get("/tiles")
    def tiles_field() -> dict[str, str]:
        return {"tiles": tile_status(tile_dir, _PROBE_NAME)}

    return router
