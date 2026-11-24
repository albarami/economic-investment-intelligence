"""Explicit embedded developer serving, with no PostgreSQL or control path."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from operations.common import atomic_json
from operations.config import persistent_paths, read_environment, write_target
from operations.runtime import verify_peers


def serve_embedded(
    root: Path, environ: Mapping[str, str], *, server: Callable[..., Any] | None = None
) -> None:
    from eii_product.api.app import create_app
    from eii_product.api.health import HealthSource, local_assets
    from eii_product.api.startup import developer_policy
    from eii_product.ledger.local import LocalLedger
    from eii_product.store.embedded import EmbeddedStore
    from eii_product.store.registry import PACKAGED
    from eii_product.store.startup import verify_startup

    env = read_environment(environ, embedded=True)
    verify_peers(env)
    checked = verify_startup(env.release, environment="development", embedded=True)
    identity = str(checked.document["release_id"])
    env.state.mkdir(parents=True, exist_ok=True)
    atomic_json(
        write_target(env, env.state / "environment.json"),
        dict(
            environment="development", release_id=identity, port=env.port, database=None
        ),
    )
    store = EmbeddedStore(env.release / "release.duckdb", identity, PACKAGED)
    ledger_path, count_path = persistent_paths(env)
    ledger = LocalLedger(ledger_path)
    policy = developer_policy(env.release)
    health = HealthSource(
        store,
        policy.verify,
        ledger.row_count,
        lambda: local_assets(env.release, root / "web/dist"),
    )
    try:
        app = create_app(
            env.release / "tiles",
            store=store,
            ledger=ledger,
            count_path=count_path,
            web_dir=root / "web/dist",
            release_dir=env.release,
            startup_policy=policy,
            health_source=health,
            key_reader=lambda: None,
            offline_reader=lambda: True,
            fc_setting_reader=lambda: None,
        )
        if server is None:
            import uvicorn

            server = uvicorn.run
        server(app, host="127.0.0.1", port=env.port, access_log=False, log_config=None)
    finally:
        ledger.close()
        store.close()
