"""FastAPI application factory for the tile spike (no settings surface)."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI

from eii_product.api.address_search import AddressIndex, Search, address_router
from eii_product.api.gis_imagery import ReleasedImagery, imagery_router
from eii_product.api.tiles import build_router


def create_app(
    tile_dir: Path,
    *,
    addresses: Search | None = None,
    imagery: ReleasedImagery | None = None,
) -> FastAPI:
    """Build an application that serves one tile folder on loopback tests."""
    app = FastAPI(title="eii tile spike", docs_url=None, redoc_url=None)
    app.include_router(build_router(tile_dir))
    app.include_router(
        address_router(AddressIndex(None) if addresses is None else addresses)
    )
    app.include_router(imagery_router(imagery))
    return app
