"""Serve the built bundle, invented tiles and invented glyphs on one origin."""

from __future__ import annotations

import argparse
import sys
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import cast

import uvicorn

from eii_product.api.app import create_app
from eii_product.api.startup import developer_policy


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tile-dir", type=Path, required=True)
    parser.add_argument("--font-dir", type=Path, required=True)
    parser.add_argument("--web-dir", type=Path, required=True)
    parser.add_argument("--port", type=int, required=True)
    args = parser.parse_args()
    # Same disposable, loaded invented release as the mounted-browser proof.
    # The recording connection is fixture plumbing, never live parity evidence.
    root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(root / "scripts" / "tests"))
    from public_release_fixture import (
        SOURCE_ID,
        _cards_tables,
        _manifest_sources,
        _scalars,
    )
    from test_live_public_release_load import _RecordingPostgres

    from eii_custodian.release.public_only import write_public_only
    from eii_product.ledger.local import LocalLedger
    from eii_product.store.embedded import EmbeddedStore
    from eii_product.store.loader import _parquet_rows, run_load
    from eii_product.store.registry import PACKAGED
    from eii_product.store.release_check import check_release, manifest_rows

    # Both asset servers of one map proof use the same loaded fixture.
    # Each mount still verifies it; each server has its own ledger.
    folder = args.tile_dir.parent / "mounted-public"
    if not folder.exists():
        # This proof needs the opening layer and its source chain, not the
        # unrelated card/layer inventory of the full statistics fixture.
        tables = []
        for table in _cards_tables():
            if table.name not in {
                "zone",
                "pub_zone_utility",
                "source_registry",
                "fact_lineage",
            }:
                continue
            if table.name == "fact_lineage":
                table = replace(
                    table,
                    rows=tuple(
                        row
                        for row in table.rows
                        if row["table_name"] == "pub_zone_utility"
                    ),
                )
            elif table.name == "source_registry":
                table = replace(
                    table,
                    rows=tuple(
                        row for row in table.rows if row["source_id"] == SOURCE_ID
                    ),
                )
            tables.append(table)
        identity = write_public_only(folder, _scalars(), _manifest_sources(), tables)
        checked = check_release(folder)
        rows = {
            entry["name"]: _parquet_rows(
                folder / entry["file"], checked.schemas[entry["name"]]
            )
            for entry in cast(list[dict[str, str]], checked.document["tables"])
        }
        rows["release_manifest"] = manifest_rows(checked.document)
        connection = _RecordingPostgres(
            rows, names=tuple(rows), columns=checked.schemas
        )
        if (
            run_load(
                folder,
                host="invented.invalid",
                port=1,
                database="INVENTED",
                connect=lambda **kw: connection,
            )
            != 0
        ):
            raise RuntimeError("invented_release_load_refused")
    checked = check_release(folder)
    identity = cast(str, checked.document["release_id"])
    with TemporaryDirectory(prefix="eii-map-ledger-") as temporary:
        store = EmbeddedStore(folder / "release.duckdb", identity, PACKAGED)
        ledger = LocalLedger(Path(temporary) / "map-ledger.sqlite")
        try:
            app = create_app(
                args.tile_dir,
                store=store,
                ledger=ledger,
                release_dir=folder,
                startup_policy=developer_policy(folder),
                web_dir=args.web_dir,
                font_dir=args.font_dir,
                basemap_name="basemap.pmtiles",
                fc_setting_reader=lambda: None,
                key_reader=lambda: None,
            )
            uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="error")
        finally:
            ledger.close()
            store.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
