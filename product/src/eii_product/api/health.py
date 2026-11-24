"""The closed OPS-30 health projection; failure never selects another store."""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Literal, cast

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field
from starlette.responses import JSONResponse

from eii_core.reasons import closed_code, reason
from eii_product.api.frontend import _font_path
from eii_product.api.map_assets import basemap_entry, font_entries
from eii_product.api.tiles import tile_status
from eii_product.config import ConfigError
from eii_product.store.protocol import ReleaseStore
from eii_product.store.release_check import CheckedRelease

AssetStatus = Literal["ok", "missing", "invalid"]


def asset_reason(assets: tuple[AssetStatus, AssetStatus, AssetStatus]) -> str:
    """Preserve every failed slot, in the fixed health order, as one closed code."""
    failed = [
        name + "_" + status
        for name, status in zip(("basemap", "fonts", "replays"), assets, strict=True)
        if status != "ok"
    ]
    return closed_code(
        "_".join(failed) or "installed_local_assets", "local_assets_invalid"
    )


def _font_assets(checked: CheckedRelease, web: Path) -> AssetStatus:
    try:
        entries = font_entries(checked)
    except ConfigError:
        return "missing"
    if not any((web / "assets").glob("*.woff2")):
        return "missing"
    root = checked.folder / "artefacts/fonts"
    for entry in entries:
        parts = PurePosixPath(entry).parts
        if _font_path(root, parts[2], parts[3]) is None:
            return "invalid"
    return "ok"


def local_assets(
    checked: CheckedRelease, web: Path
) -> tuple[AssetStatus, AssetStatus, AssetStatus]:
    """Observe map artefacts selected by the checked manifest."""
    try:
        basemap_entry(checked)
        tiles = cast(
            AssetStatus,
            tile_status(checked.folder / "artefacts/tiles", "basemap.pmtiles"),
        )
    except ConfigError:
        tiles = "missing"
    return tiles, _font_assets(checked, web), "ok"


class _Probe:
    """One bounded in-flight observation, never an accumulating pool of retries."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.thread: threading.Thread | None = None
        self.started = 0.0
        self.result: list[tuple[bool, bool]] = []

    def read(
        self, store: ReleaseStore, verify: Callable[[], None]
    ) -> tuple[bool, bool]:
        with self.lock:
            if self.thread is None or not self.thread.is_alive():
                result: list[tuple[bool, bool]] = []

                def observe() -> None:
                    up, identical = False, False
                    try:
                        up = store.ping(4.0).ok
                        if up:
                            verify()
                            identical = True
                    except Exception as error:
                        logging.getLogger(__name__).warning(
                            "health_probe_refused", extra={"error_code": reason(error)}
                        )
                    result.append((up, identical))

                self.result = result
                self.started = time.monotonic()
                self.thread = threading.Thread(target=observe, daemon=True)
                self.thread.start()
            thread, started, result = self.thread, self.started, self.result
        thread.join(max(0.0, 4.0 - (time.monotonic() - started)))
        if thread.is_alive() or not result:
            return False, False
        return result[0]


class Health(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    status: Literal["ok", "degraded"]
    store: Literal["postgres", "embedded"]
    postgres: Literal["up", "down", "not_used"]
    release_id: str
    release_hash: str
    parity: Literal["identical", "failed"]
    ledger: Literal["postgres", "local"]
    local_ledger_rows: int = Field(ge=0)
    model: Literal["live", "replay", "template"]
    traffic: Literal["live", "simulated"]
    tiles: AssetStatus
    fonts: AssetStatus
    replays: AssetStatus


@dataclass(frozen=True)
class HealthSource:
    store: ReleaseStore
    verify: Callable[[], None]
    local_rows: Callable[[], int]
    assets: Callable[[], tuple[AssetStatus, AssetStatus, AssetStatus]]
    _probe: _Probe = field(default_factory=_Probe, init=False, repr=False)

    def read(self) -> Health:
        postgres: Literal["up", "down", "not_used"] = (
            "not_used" if self.store.engine == "embedded" else "up"
        )
        parity: Literal["identical", "failed"] = "identical"
        up, identical = self._probe.read(self.store, self.verify)
        if not up and self.store.engine == "postgres":
            postgres = "down"
        if not identical:
            parity = "failed"
        rows = self.local_rows()
        tiles, fonts, replays = self.assets()
        ok = (
            postgres != "down"
            and parity == "identical"
            and (tiles, fonts, replays) == ("ok", "ok", "ok")
        )
        return Health(
            status="ok" if ok else "degraded",
            store=self.store.engine,
            postgres=postgres,
            release_id=self.store.release_id,
            release_hash=self.store.release_id,
            parity=parity,
            ledger="local",
            local_ledger_rows=rows,
            model="template",
            traffic="simulated",
            tiles=tiles,
            fonts=fonts,
            replays=replays,
        )


def build_router(source: HealthSource | None) -> APIRouter:
    router = APIRouter()

    @router.get("/health")
    async def health() -> JSONResponse:
        if source is None:
            return JSONResponse({"error": "STORE_UNAVAILABLE"}, status_code=503)
        result = source.read()
        return JSONResponse(
            result.model_dump(), status_code=200 if result.status == "ok" else 503
        )

    return router
