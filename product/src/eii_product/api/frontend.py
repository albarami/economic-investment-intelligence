"""Closed same-origin paths for the built bundle; no SPA or proxy fallback."""

import re
from pathlib import Path

from fastapi import APIRouter
from starlette.responses import FileResponse, Response

from eii_product.api.playbooks import refusal

ASSET_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*\.(js|css|woff2|svg|png|json)\Z")
FONT_STACKS = ("Noto Sans Medium",)
FONT_SPAN = re.compile(r"(0|[1-9][0-9]*)-(0|[1-9][0-9]*)\.pbf\Z")
FONT_TYPE = "application/x-protobuf"
ASSET_TYPES = {
    ".js": "text/javascript",
    ".css": "text/css",
    ".woff2": "font/woff2",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".json": "application/json",
}


def _inside(base: Path, name: str) -> Path | None:
    try:
        resolved = (base / name).resolve()
        resolved.relative_to(base.resolve())
        return resolved if resolved.is_file() else None
    except (OSError, ValueError, RuntimeError):
        return None


def _font_path(font_dir: Path, stack: str, span: str) -> Path | None:
    if stack not in FONT_STACKS:
        return None
    match = FONT_SPAN.fullmatch(span)
    if match is None:
        return None
    start, end = int(match[1]), int(match[2])
    if start % 256 or end != start + 255 or start > 0xFF00:
        return None
    expected = font_dir.resolve() / stack
    base = (font_dir / stack).resolve()
    if base != expected:
        return None
    return _inside(base, span)


def build_router(web_dir: Path | None, font_dir: Path | None = None) -> APIRouter:
    router = APIRouter()

    @router.get("/", response_model=None)
    async def index() -> Response:
        path = None if web_dir is None else _inside(web_dir, "index.html")
        if path is None:
            return refusal(404, "NOT_FOUND")
        return FileResponse(
            path, media_type="text/html", headers={"X-Content-Type-Options": "nosniff"}
        )

    @router.get("/assets/{name:path}", response_model=None)
    async def asset(name: str) -> Response:
        if web_dir is None or ASSET_NAME.fullmatch(name) is None:
            return refusal(404, "NOT_FOUND")
        path = _inside(web_dir / "assets", name)
        if path is None:
            return refusal(404, "NOT_FOUND")
        return FileResponse(
            path,
            media_type=ASSET_TYPES[Path(name).suffix],
            headers={"X-Content-Type-Options": "nosniff"},
        )

    @router.get("/fonts/{stack}/{span}", response_model=None)
    async def glyph(stack: str, span: str) -> Response:
        path = None if font_dir is None else _font_path(font_dir, stack, span)
        if path is None:
            return refusal(404, "NOT_FOUND")
        return FileResponse(
            path,
            media_type=FONT_TYPE,
            headers={"X-Content-Type-Options": "nosniff"},
        )

    return router
