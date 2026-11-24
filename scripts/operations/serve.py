"""Installed application entry; isolated Python never loads checkout packages."""

from __future__ import annotations

import importlib.metadata
import json
import os
import sys
from pathlib import Path

# This bootstrap also runs with -S, so no editable-package .pth is evaluated.
APPLICATION_ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [
    str(APPLICATION_ROOT / name)
    for name in ("runtime/site-packages", "core/src", "product/src", "scripts")
]


def verify_runtime() -> None:
    from operations.common import Refusal, read_json

    manifest = read_json(
        APPLICATION_ROOT / "application.json", "application_verification_failed"
    )
    if manifest["python_version"] != ".".join(map(str, sys.version_info[:3])):
        raise Refusal("offline_python_mismatch")
    dependencies = read_json(
        APPLICATION_ROOT / "runtime/dependencies.json", "offline_dependency_missing"
    )
    for name, version in dependencies["packages"].items():
        if importlib.metadata.version(name) != version:
            raise Refusal("offline_dependency_missing")
    # Import all serving dependencies before any socket is bound.
    __import__("eii_product.api.app")
    __import__("duckdb")
    __import__("psycopg")
    __import__("uvicorn")
    __import__("shapely")


def main() -> int:
    if sys.argv[1:] == ["--verify-runtime"]:
        verify_runtime()
        return 0
    from eii_product.api.app import create_app
    from eii_product.api.health import HealthSource, local_assets
    from eii_product.api.startup import ServingPolicy
    from eii_product.ledger.local import LocalLedger
    from eii_product.store.embedded import EmbeddedStore
    from eii_product.store.postgres import PostgresStore
    from eii_product.store.receipt import read_receipt
    from eii_product.store.registry import PACKAGED
    from eii_product.store.startup import postgres_snapshot, verify_startup
    from operations.activation import entries
    from operations.common import Refusal
    from operations.config import persistent_paths, read_environment
    from operations.deploy import request_for, staging_probe
    from operations.evidence import exposure, verify_evidence
    from operations.runtime import app_connection, installed

    verify_runtime()
    clean = {key: value for key, value in os.environ.items() if key != "EII_STORE"}
    env = read_environment(clean)
    request = request_for(env, clean)
    exposure(env.home, request)
    if (
        sys.argv[sys.argv.index("--release-id") + 1] != request["release_id"]
        or sys.argv[sys.argv.index("--application-sha256") + 1]
        != request["application_sha256"]
        or int(sys.argv[sys.argv.index("--port") + 1]) != request["backend_port"]
    ):
        raise Refusal("activation_target_mismatch")
    application, manifest = installed(env, request)
    if application.resolve() != APPLICATION_ROOT:
        raise Refusal("mutable_application_refused")
    log = entries(env.state)
    # The command and direct installed entry share the durable authorisation.
    authorization = next((entry for entry in log if entry["request"] == request), None)
    if authorization is None:
        raise Refusal("promotion_log_mismatch")
    if env.name == "live":
        reports = verify_evidence(
            env.home,
            request,
            features=manifest["features"],
            staging_probe=lambda report: staging_probe(env, report),
        )
        if authorization["results"] != {
            item: dict(result="passed", report=report)
            for item, report in reports.items()
        }:
            raise Refusal("promotion_log_mismatch")
    embedded = os.environ.get("EII_STORE") == "embedded"
    if env.name in {"live", "staging"} and embedded:
        raise Refusal("embedded_environment_refused")
    connection = None if embedded else app_connection(os.environ)

    def verify() -> None:
        verify_startup(
            env.release,
            environment=env.name,
            embedded=embedded,
            postgres_reader=None
            if connection is None
            else lambda checked: postgres_snapshot(checked, connection),
        )

    verify()
    identity = request["release_id"]
    standby = EmbeddedStore(env.release / "release.duckdb", identity, PACKAGED)
    store = standby if embedded else PostgresStore(connection, identity, PACKAGED)
    ledger_path, count_path = persistent_paths(env)
    ledger = LocalLedger(ledger_path)
    policy = ServingPolicy(env.name, identity, verify)  # type: ignore[arg-type]

    def receipt_valid() -> None:
        read_receipt(env.release, identity)
        # A health check retains the store and verifies active identity, while
        # full data parity was checked immediately before serving.
        from eii_product.store.release_check import check_release, manifest_rows
        from eii_product.tools.public_context_tools import read

        expected = manifest_rows(check_release(env.release).document)
        if read(store, "public_release_manifest") != sorted(
            expected, key=lambda row: str(row["table_name"])
        ):
            raise Refusal("startup_identity_mismatch")

    health = HealthSource(
        store,
        receipt_valid,
        ledger.row_count,
        lambda: local_assets(env.release, application / "web/dist"),
    )
    app = create_app(
        env.release / "tiles",
        store=store,
        ledger=ledger,
        count_path=count_path,
        web_dir=application / "web/dist",
        release_dir=env.release,
        font_dir=env.release / "fonts",
        basemap_name="basemap.pmtiles",
        startup_policy=policy,
        health_source=health,
        key_reader=lambda: None,
        fc_setting_reader=lambda: None,
    )
    import uvicorn

    try:
        uvicorn.run(
            app,
            host="127.0.0.1",
            port=int(sys.argv[sys.argv.index("--port") + 1]),
            access_log=False,
            log_config=None,
        )
    finally:
        ledger.close()
        standby.close()
        if connection is not None:
            connection.close()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        from eii_core.reasons import reason

        # Never render driver text, credentials, request text or private paths.
        print(
            json.dumps({"status": "startup_refused", "error_code": reason(error)}),
            file=sys.stderr,
        )
        raise SystemExit(4) from None
