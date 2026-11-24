"""S3-T10 loopback-only built-app fixture. No live store or provider."""

from __future__ import annotations

import argparse
from decimal import Decimal
from importlib import import_module
from pathlib import Path
from typing import NoReturn, cast

import uvicorn
from fastapi import FastAPI
from public_release_fixture import build_fixture
from test_live_public_release_load import _RecordingPostgres

from eii_product.api.app import create_app
from eii_product.api.area_context import RoutingSource
from eii_product.api.startup import developer_policy
from eii_product.ledger.local import LocalLedger
from eii_product.store.embedded import EmbeddedStore
from eii_product.store.loader import _parquet_rows, run_load
from eii_product.store.registry import PACKAGED
from eii_product.store.release_check import check_release, manifest_rows

HOST = "127.0.0.1"


def build_fixture_app(
    work: Path, web: Path
) -> tuple[FastAPI, EmbeddedStore, LocalLedger]:
    """Load the complete invented resolver/cards fixture through the real loader."""
    folder = work / "release"
    identity = build_fixture(folder, resolver=True)
    checked = check_release(folder)
    rows = {
        entry["name"]: _parquet_rows(
            folder / entry["file"], checked.schemas[entry["name"]]
        )
        for entry in cast(list[dict[str, str]], checked.document["tables"])
    }
    rows["release_manifest"] = manifest_rows(checked.document)
    connection = _RecordingPostgres(rows, names=tuple(rows), columns=checked.schemas)
    code = run_load(
        folder,
        host="invented.invalid",
        port=1,
        database="INVENTED",
        connect=lambda **_kw: connection,
    )
    if code != 0:
        raise RuntimeError("invented_load_refused")
    store = EmbeddedStore(folder / "release.duckdb", identity, PACKAGED)
    ledger = LocalLedger(work / "ledger.sqlite")
    import_module("product.tests.map_assets").write_assets(
        work / "tiles", work / "fonts"
    )

    def denied(*_args: object, **_kwargs: object) -> NoReturn:
        # Records even an attempted/caught call; no provider is ever contacted.
        with (work / "egress-attempts.txt").open("a") as output:
            output.write("provider_attempt\n")
        raise AssertionError("provider_attempt")

    def route(
        mode: str, _minutes: int, lat: Decimal, lon: Decimal
    ) -> tuple[tuple[object, object], ...]:
        # Documented fixture geometry, not a real routing input or tolerance.
        # A drive box is larger than a walk box, so a story's wider drive ring
        # never coincides with its chosen walk outline (S3-T26 A5).
        delta = Decimal(".02") if mode == "drive" else Decimal(".01")
        return (
            (lat - delta, lon - delta),
            (lat - delta, lon + delta),
            (lat + delta, lon + delta),
            (lat + delta, lon - delta),
            (lat - delta, lon - delta),
        )

    app = create_app(
        work / "tiles",
        store=store,
        ledger=ledger,
        release_dir=folder,
        startup_policy=developer_policy(folder),
        web_dir=web,
        font_dir=work / "fonts",
        basemap_name="basemap.pmtiles",
        routing=RoutingSource.from_call(route),
        key_reader=lambda: None,
        offline_reader=lambda: True,
        transport_factory=denied,
        opener=denied,
        count_path=work / "photoreal-count.log",
        fc_setting_reader=lambda: None,
    )
    return app, store, ledger


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--web", type=Path, required=True)
    args = parser.parse_args()
    app, store, ledger = build_fixture_app(args.work, args.web)
    try:
        uvicorn.run(app, host=HOST, port=args.port, log_level="error", access_log=False)
    finally:
        ledger.close()
        store.close()


if __name__ == "__main__":
    main()
