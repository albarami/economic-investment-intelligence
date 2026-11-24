"""Closed health, direct startup policy and independent exposure plants."""

from __future__ import annotations

import asyncio
import json
import threading
import time
from typing import Any
from unittest.mock import Mock, patch

from fastapi.routing import APIRoute
from pydantic import ValidationError
from s3_t28_support import COMMIT, IDENTITY, WorkspaceCase
from test_s3_t28_promotion import request

from eii_product.api.app import create_app
from eii_product.api.health import Health, HealthSource, build_router, local_assets
from eii_product.api.startup import ServingPolicy
from eii_product.config import ConfigError
from eii_product.store.protocol import StoreHealth
from eii_product.store.startup import StartupRefusal
from operations.common import Refusal, encoded, sha
from operations.evidence import exposure


class Startup(WorkspaceCase):
    def test_http_health_status_for_each_independent_degradation(self) -> None:
        store = self.store()
        verify = Mock()
        assets = Mock(return_value=("ok", "ok", "ok"))
        source = HealthSource(store, verify, lambda: 2, assets)
        route = build_router(source).routes[0]
        assert isinstance(route, APIRoute)
        endpoint = route.endpoint
        self.assertEqual(asyncio.run(endpoint()).status_code, 200)
        for mode in ("postgres", "receipt", "parity", "tiles", "fonts", "replays"):
            store.ping.side_effect = None
            verify.side_effect = None
            assets.return_value = ("ok", "ok", "ok")
            if mode == "postgres":
                store.ping.side_effect = OSError("INVENTED-offline")
            elif mode in {"receipt", "parity"}:
                verify.side_effect = StartupRefusal(
                    "receipt_not_complete"
                    if mode == "receipt"
                    else "startup_parity_failed"
                )
            else:
                values = ["ok", "ok", "ok"]
                values[("tiles", "fonts", "replays").index(mode)] = "missing"
                assets.return_value = tuple(values)
            with self.subTest(mode=mode):
                response = asyncio.run(endpoint())
                self.assertEqual(response.status_code, 503)
                self.assertEqual(json.loads(response.body)["store"], "postgres")

    def test_local_assets_reflect_present_and_missing_inputs(self) -> None:
        release, web = self.root / "release", self.root / "web"
        (release / "tiles").mkdir(parents=True)
        (release / "fonts").mkdir()
        (web / "assets").mkdir(parents=True)
        (release / "tiles/basemap.pmtiles").write_bytes(b"INVENTED-tile")
        (web / "assets/font.woff2").write_bytes(b"INVENTED-font")
        self.assertEqual(local_assets(release, web), ("ok", "ok", "ok"))
        (release / "tiles/basemap.pmtiles").unlink()
        self.assertEqual(local_assets(release, web), ("missing", "ok", "ok"))
        (web / "assets/font.woff2").unlink()
        self.assertEqual(local_assets(release, web), ("missing", "missing", "ok"))

    def test_failed_new_entry_readiness_stops_only_that_owned_child(self) -> None:
        from operations.config import Environment
        from operations.deploy import up

        env = Environment(
            "live",
            self.root / "live/releases" / IDENTITY,
            self.root / "live/state",
            8088,
            ("127.0.0.1", 5432, "INVENTED_live"),
        )
        env.state.mkdir(parents=True)
        raw = request()
        child = dict(pid=17, release_id=IDENTITY)
        with (
            patch("operations.deploy.read_environment", return_value=env),
            patch("operations.deploy.verify_peers"),
            patch("operations.deploy.request_for", return_value=raw),
            patch(
                "operations.deploy.installed",
                return_value=(self.root, dict(features=[])),
            ),
            patch("operations.deploy.check_stores"),
            patch("operations.deploy.activate", return_value=raw),
            patch("operations.deploy.process.launch", return_value=child),
            patch(
                "operations.deploy.process.wait_ready",
                side_effect=Refusal("startup_not_ready"),
            ),
            patch("operations.deploy.process.terminate") as stop,
        ):
            with self.assertRaisesRegex(Refusal, "startup_not_ready"):
                up({})
            stop.assert_called_once_with(child, "live")

    def store(self) -> Any:
        store = Mock()
        store.engine = "postgres"
        store.release_id = IDENTITY
        store.ping.return_value = StoreHealth(ok=True)
        return store

    def test_health_exact_keys_types_enums_and_secret_absence(self) -> None:
        store = self.store()
        verify = Mock()
        source = HealthSource(store, verify, lambda: 3, lambda: ("ok", "ok", "ok"))
        value = source.read().model_dump()
        self.assertEqual(
            set(value),
            {
                "status",
                "store",
                "postgres",
                "release_id",
                "release_hash",
                "parity",
                "ledger",
                "local_ledger_rows",
                "model",
                "traffic",
                "tiles",
                "fonts",
                "replays",
            },
        )
        self.assertEqual(value["status"], "ok")
        self.assertEqual(value["local_ledger_rows"], 3)
        store.ping.side_effect = RuntimeError("SYN-secret-health-marker")
        down = source.read().model_dump()
        self.assertEqual(
            (down["status"], down["postgres"], down["store"]),
            ("degraded", "down", "postgres"),
        )
        self.assertNotIn("SYN-secret-health-marker", json.dumps(down))
        store.ping.side_effect = None
        verify.side_effect = ValueError("SYN-secret-health-marker")
        self.assertEqual(source.read().parity, "failed")
        for changed in (
            dict(value, extra="SYN-secret-health-marker"),
            dict(value, traffic="unknown"),
        ):
            with self.subTest(changed=set(changed)), self.assertRaises(ValidationError):
                Health.model_validate(changed)

    def test_direct_factory_requires_verified_policy(self) -> None:
        for folder in (None, self.root):
            with (
                self.subTest(release=folder is not None),
                self.assertRaisesRegex(ConfigError, "startup_policy_required"),
            ):
                create_app(
                    self.root,
                    store=self.store(),
                    ledger=Mock(),
                    release_dir=folder,
                    web_dir=self.root,
                    count_path=self.root / "count.log",
                    key_reader=lambda: None,
                    offline_reader=lambda: True,
                    fc_setting_reader=lambda: None,
                )
        with self.assertRaisesRegex(ConfigError, "release_dir_required"):
            create_app(
                self.root,
                store=self.store(),
                ledger=Mock(),
                web_dir=self.root,
                count_path=self.root / "count.log",
                key_reader=lambda: None,
                offline_reader=lambda: True,
                fc_setting_reader=lambda: None,
                startup_policy=ServingPolicy("live", IDENTITY, lambda: None),
            )

    def test_hung_postgres_degrades_within_five_seconds_without_switch(self) -> None:
        release = threading.Event()
        store = self.store()
        store.ping.side_effect = lambda _: release.wait() and StoreHealth(ok=True)
        source = HealthSource(
            store, lambda: None, lambda: 0, lambda: ("ok", "ok", "ok")
        )
        started = time.monotonic()
        try:
            result = source.read()
            self.assertLess(time.monotonic() - started, 5.0)
            self.assertEqual(
                (result.status, result.postgres, result.store),
                ("degraded", "down", "postgres"),
            )
            thread = source._probe.thread
            source.read()
            self.assertIs(source._probe.thread, thread)
        finally:
            release.set()

    def test_direct_policy_runs_shared_verifier_and_rejects_traffic(self) -> None:
        verify = Mock()
        policy = ServingPolicy("live", IDENTITY, verify)
        policy.require(self.store(), self.root)
        verify.assert_called_once()
        bad: Any = "live"
        with self.assertRaisesRegex(StartupRefusal, "traffic_mode_refused"):
            ServingPolicy("live", IDENTITY, verify, traffic=bad).require(
                self.store(), self.root
            )
        verify.side_effect = StartupRefusal("startup_parity_failed")
        with self.assertRaisesRegex(StartupRefusal, "startup_parity_failed"):
            policy.require(self.store(), self.root)

    def test_loopback_needs_no_gate(self) -> None:
        exposure(self.root, request())

    def test_each_public_gate_failure_and_lead_handover(self) -> None:
        raw = request()
        raw.update(operation="expose_public", exposure="public_entry")
        callback = Mock()
        for mode in ("missing", "failed", "commit", "release"):
            gate = dict(
                gate="S3",
                verdict="APPROVED",
                **{
                    key: raw[key]
                    for key in ("code_version", "release_id", "application_sha256")
                },
            )
            if mode == "failed":
                gate["verdict"] = "REJECTED"
            elif mode == "commit":
                gate["code_version"] = "ba" * 20
            elif mode == "release":
                gate["release_id"] = "ac" * 32
            path = self.root / "gate.json"
            path.write_bytes(encoded(gate))
            raw["gate_approval"] = (
                None if mode == "missing" else dict(file=path.name, sha256=sha(path))
            )
            with (
                self.subTest(mode=mode),
                self.assertRaisesRegex(Refusal, "public_gate_approval_required"),
            ):
                exposure(self.root, raw, callback)
            callback.assert_not_called()
        gate.update(code_version=COMMIT, release_id=IDENTITY)
        path.write_bytes(encoded(gate))
        raw["gate_approval"] = dict(file=path.name, sha256=sha(path))
        exposure(self.root, raw, callback)
        callback.assert_not_called()  # Validation does not open an entry.
        raw["actor"] = "operator"
        with self.assertRaisesRegex(Refusal, "public_handover_lead_required"):
            exposure(self.root, raw, callback)
        raw["actor"] = "lead"
        with self.assertRaisesRegex(Refusal, "public_entry_requires_s3_t20"):
            exposure(self.root, raw)
