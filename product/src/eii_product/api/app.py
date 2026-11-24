"""FastAPI factory for tiles, address search and optional loaded Public playbooks."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any, Literal
from urllib.request import urlopen

from fastapi import FastAPI

from eii_product.api.address_search import (
    AddressIndex,
    Search,
    TransportFactory,
    address_router,
    build_router,
    offline_unset,
)
from eii_product.api.answers import Gate, default_gate
from eii_product.api.area_context import AreaContextFactory, RoutingSource
from eii_product.api.frontend import build_router as build_frontend_router
from eii_product.api.gis_imagery import ReleasedImagery, imagery_router
from eii_product.api.health import HealthSource
from eii_product.api.health import build_router as build_health_router
from eii_product.api.layers import build_layer_router
from eii_product.api.map_modes import build_router as build_map_router
from eii_product.api.playbooks import build_router as build_playbook_router
from eii_product.api.public_layers import (
    PUBLIC_LAYER_KEYS,
    public_point_snapshot,
    read_layer,
)
from eii_product.api.release import MountedRelease, build_release_router
from eii_product.api.session_store import SESSION_CAP, SessionStore
from eii_product.api.shapes import build_router as build_shapes_router
from eii_product.api.startup import ServingPolicy
from eii_product.api.tiles import build_router as build_tile_router
from eii_product.api.tools import build_tools_router
from eii_product.assistant.catalogue.load import catalogue_directory, load_catalogue
from eii_product.assistant.catalogue.schema import Catalogue
from eii_product.config import ConfigError, read_esri_api_key, read_fc_register_file
from eii_product.imagery_provider.address import live_transport
from eii_product.ledger.local import LocalLedger
from eii_product.photoreal_tiles.limit import COUNT_PATH
from eii_product.photoreal_tiles.proxy import tile_opener
from eii_product.register_file import (
    RegisterBundle,
    RegisterRefusal,
    read_fc_register_rows,
)
from eii_product.store.protocol import ReleaseStore


def create_app(
    tile_dir: Path,
    *,
    addresses: Search | None = None,
    imagery: ReleasedImagery | None = None,
    store: ReleaseStore | None = None,
    ledger: LocalLedger | None = None,
    gate: Gate = default_gate,
    key_reader: Callable[[], str | None] = read_esri_api_key,
    offline_reader: Callable[[], bool] = offline_unset,
    transport_factory: TransportFactory = live_transport,
    opener: Callable[..., object] = urlopen,
    fc_setting_reader: Callable[[], str | None] = read_fc_register_file,
    fc_rows_reader: Callable[..., RegisterBundle | None] = read_fc_register_rows,
    count_path: Path = COUNT_PATH,
    web_dir: Path | None = None,
    release_dir: Path | None = None,
    font_dir: Path | None = None,
    basemap_name: Literal["basemap.pmtiles"] | None = None,
    session_cap: int = SESSION_CAP,
    routing: RoutingSource | None = None,
    startup_policy: ServingPolicy | None = None,
    health_source: HealthSource | None = None,
) -> FastAPI:
    """Build an application that serves tiles, address search and layers.

    A ledger is required when a store is supplied. Existing callers pass only
    the tile folder. The address route defaults to the config reader, offline
    unset and the live transport. The financial centre register is read once
    here; an invalid value stops the start.
    """
    if store is not None and (release_dir is not None or web_dir is not None):
        if startup_policy is None:
            raise ConfigError("startup_policy_required")
        if release_dir is None:
            raise ConfigError("release_dir_required")
        startup_policy.require(store, release_dir)
    if basemap_name not in (None, "basemap.pmtiles"):
        raise ConfigError("basemap_name")
    if routing is not None and not isinstance(routing, RoutingSource):
        raise ConfigError("routing_tiles")
    fc_setting = fc_setting_reader()
    if fc_setting is not None:
        try:
            fc_rows_reader(fc_setting)
        except RegisterRefusal as exc:
            if exc.reason == "read_refused":
                raise ConfigError("EII_FC_REGISTER_FILE") from None
            raise
    sessions = SessionStore(session_cap)
    app = FastAPI(title="eii tile spike", docs_url=None, redoc_url=None)
    app.state.sessions = sessions
    mount = (
        MountedRelease(store, release_dir, basemap_name=basemap_name)
        if store is not None and release_dir is not None
        else None
    )
    app.state.release_mount = mount
    app.include_router(build_health_router(health_source))
    app.include_router(build_release_router(mount))
    # Catalogue-only construction probes have no serving-store identity.
    app.state.area_contexts = (
        AreaContextFactory(
            store.release_id,
            routing,
            point_snapshot=lambda: public_point_snapshot(store),
        )
        if store is not None and hasattr(store, "release_id")
        else None
    )
    app.include_router(build_shapes_router(store, sessions))
    app.include_router(build_tile_router(tile_dir))
    app.include_router(
        address_router(AddressIndex(None) if addresses is None else addresses)
    )
    app.include_router(imagery_router(imagery))
    app.include_router(
        build_router(key_reader, offline_reader, transport_factory, opener)
    )
    if store is not None:
        catalogue = load_catalogue(catalogue_directory())
        if not isinstance(catalogue, Catalogue):
            raise ValueError("catalogue_invalid")
        app.include_router(
            build_playbook_router(
                store,
                ledger,
                catalogue,
                gate=gate,
                area_contexts=app.state.area_contexts,
                mount=mount,
            )
        )
        if app.state.area_contexts is not None and ledger is not None:
            app.include_router(
                build_tools_router(
                    store, ledger, sessions, app.state.area_contexts, mount=mount
                )
            )
    readers = None
    if store is not None and app.state.area_contexts is not None:
        from functools import partial

        def mounted_layer(key: str, month: str | None) -> dict[str, Any]:
            body = read_layer(store, key, month)
            return mount.layer(body) if mount is not None else body

        readers = {key: partial(mounted_layer, key) for key in PUBLIC_LAYER_KEYS}
    app.include_router(
        build_layer_router(fc_setting, fc_rows_reader, public_readers=readers)
    )
    app.include_router(
        build_map_router(
            key_reader,
            offline_reader,
            tile_opener if opener is urlopen else opener,
            count_path,
        )
    )
    app.include_router(build_frontend_router(web_dir, font_dir))
    return app
