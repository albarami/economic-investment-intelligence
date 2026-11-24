"""Full-store startup plants, independent of drivers and real deployments."""

from __future__ import annotations

import copy
from dataclasses import replace
from typing import Any
from unittest.mock import Mock, patch

from s3_t28_support import WorkspaceCase, fixture_reads, snapshots

from eii_product.store.startup import StartupRefusal, verify_snapshots, verify_startup
from operations.common import Refusal, encoded
from operations.config import read_environment


class ReleaseStartup(WorkspaceCase):
    def test_actual_staging_smoke_each_response_and_wrong_health_identity(self) -> None:
        import json

        from test_s3_t28_promotion import request

        from operations.config import Environment
        from operations.deploy import staging_probe

        raw = request()
        route = dict(raw, backend_port=8089)
        report = dict(raw, port=8089)
        env = Environment(
            "live",
            self.root / "live/releases" / raw["release_id"],
            self.root / "live/state",
            8088,
            ("127.0.0.1", 5432, "INVENTED_live"),
        )

        def response(port: int, path: str) -> tuple[int, bytes]:
            return 200, json.dumps(dict(release_id=raw["release_id"])).encode()

        with (
            patch("operations.deploy.active_route", return_value=route),
            patch("operations.deploy.installed"),
            patch(
                "operations.deploy.read_json",
                return_value=dict(database=["127.0.0.1", 5432, "INVENTED_staging"]),
            ),
            patch("operations.deploy.process.require_owned"),
            patch(
                "operations.deploy.health_probe",
                return_value=dict(status="ok", release_id=raw["release_id"]),
            ) as health,
            patch("operations.deploy.get", side_effect=response) as get,
        ):
            staging_probe(env, report)
            for target in ("/", "/api/release", "/api/layers/parcels"):
                get.side_effect = lambda port, path, target=target: (
                    (503, b"{}") if path == target else response(port, path)
                )
                with (
                    self.subTest(target=target),
                    self.assertRaisesRegex(Refusal, "promotion_evidence_staging"),
                ):
                    staging_probe(env, report)
            get.side_effect = response
            health.return_value = dict(status="ok", release_id="cd" * 32)
            with self.assertRaisesRegex(Refusal, "promotion_evidence_staging"):
                staging_probe(env, report)

    def settings(self) -> dict[str, str]:
        from test_s3_t28_promotion import request

        home = self.root / "live"
        home.mkdir()
        record = home / "operation.json"
        record.write_bytes(encoded(request()))
        return dict(
            EII_ENVIRONMENT="live",
            EII_RELEASE_DIR=str(home / "releases" / request()["release_id"]),
            EII_STATE_DIR=str(home / "state"),
            EII_DATABASE_URL="postgres://eii_app"
            + "@"
            + "127.0.0.1:5432/INVENTED_live",
            EII_OPERATION_RECORD=str(record),
        )

    def test_schema_role_flags_precede_namespace_read(self) -> None:
        from operations.runtime import inspect_schema

        settings = self.settings()
        env = read_environment(settings)
        for role in (
            ("eii_owner", False, False),
            ("other", False, False),
            ("eii_app", True, False),
            ("eii_app", False, True),
        ):
            connection = Mock()
            with (
                self.subTest(role=role),
                patch("eii_product.store.loader._execute", return_value=[role]),
                patch("eii_product.store.loader._schema_present") as namespace,
            ):
                with self.assertRaisesRegex(Refusal, "startup_role_refused"):
                    inspect_schema(env, settings, connect=Mock(return_value=connection))
                namespace.assert_not_called()
                connection.close.assert_called_once()

    def test_absent_schema_uses_owner_loader_existing_schema_never_reloads(
        self,
    ) -> None:
        from commands.load_release import _connect
        from operations.deploy import ensure_schema

        settings = self.settings()
        with (
            patch("operations.deploy.installed"),
            patch("operations.deploy.inspect_schema", return_value=False) as present,
            patch("eii_product.store.loader.perform") as load,
            patch("operations.deploy.check_stores") as verify,
        ):
            self.assertTrue(ensure_schema(settings))
            self.assertIs(load.call_args.kwargs["connect"], _connect)
            verify.assert_called_once()
            load.reset_mock()
            verify.reset_mock()
            present.return_value = True
            self.assertFalse(ensure_schema(settings))
            load.assert_not_called()
            verify.assert_not_called()

    def test_up_loads_absent_schema_without_repeating_probes(self) -> None:
        import preflight
        from commands.up_cmd import run
        from preflight_store import Line

        settings = self.settings()
        report = preflight.Report(
            (Line("FAIL", "release", "absent schema"),), "postgres", 1
        )
        with (
            patch(
                "commands.up_cmd.preflight.run_preflight", return_value=report
            ) as probe,
            patch("operations.deploy.ensure_schema", return_value=True) as ensure,
            patch("operations.deploy.up") as start,
        ):
            self.assertEqual(run(self.root, settings, ()), 0)
            probe.assert_called_once()
            start.assert_called_once()
            probe.reset_mock()
            start.reset_mock()
            ensure.return_value = False
            self.assertEqual(run(self.root, settings, ()), 4)
            probe.assert_called_once()
            start.assert_not_called()

    def test_matching_complete_stores(self) -> None:
        checked, receipt, left, right = snapshots(self.root)
        with fixture_reads(checked, receipt, left):
            verify_snapshots(checked, receipt, left, right)
            self.assertIs(
                verify_startup(
                    self.root,
                    environment="live",
                    embedded_reader=lambda _: left,
                    postgres_reader=lambda _: right,
                ),
                checked,
            )

    def test_each_physical_inventory(self) -> None:
        checked, receipt, left, right = snapshots(self.root)
        for side in ("embedded", "postgres"):
            bad = replace(
                left if side == "embedded" else right,
                names=left.names | {"INVENTED_extra"},
            )
            with (
                self.subTest(side=side),
                fixture_reads(checked, receipt, left),
                self.assertRaisesRegex(StartupRefusal, "startup_inventory_mismatch"),
            ):
                verify_snapshots(
                    checked,
                    receipt,
                    bad if side == "embedded" else left,
                    bad if side == "postgres" else right,
                )

    def test_each_full_identity(self) -> None:
        checked, receipt, left, right = snapshots(self.root)
        for side in ("embedded", "postgres"):
            rows: dict[str, Any] = copy.deepcopy(dict(left.rows))
            rows["release_manifest"][0]["release_id"] = "ab" * 8 + "dd" * 24
            bad = replace(left, rows=rows)
            with (
                self.subTest(side=side),
                fixture_reads(checked, receipt, left),
                self.assertRaisesRegex(StartupRefusal, "startup_identity_mismatch"),
            ):
                verify_snapshots(
                    checked,
                    receipt,
                    bad if side == "embedded" else left,
                    bad if side == "postgres" else right,
                )

    def test_actual_non_lineage_value_and_count(self) -> None:
        checked, receipt, left, right = snapshots(self.root)
        for side in ("embedded", "postgres"):
            for change in ("row", "count"):
                rows: dict[str, Any] = copy.deepcopy(dict(left.rows))
                if change == "row":
                    rows["source_registry"][0]["source_id"] = "INVENTED-tampered"
                else:
                    rows["source_registry"] = []
                bad = replace(left, rows=rows)
                with (
                    self.subTest(side=side, change=change),
                    fixture_reads(checked, receipt, left),
                    self.assertRaisesRegex(StartupRefusal, "startup_parity_failed"),
                ):
                    verify_snapshots(
                        checked,
                        receipt,
                        bad if side == "embedded" else left,
                        bad if side == "postgres" else right,
                    )

    def test_each_application_role_flag(self) -> None:
        checked, receipt, left, right = snapshots(self.root)
        for role in (
            ("eii_owner", False, False),
            ("INVENTED-other", False, False),
            ("eii_app", True, False),
            ("eii_app", False, True),
        ):
            with (
                self.subTest(role=role),
                fixture_reads(checked, receipt, left),
                self.assertRaisesRegex(StartupRefusal, "startup_role_refused"),
            ):
                verify_snapshots(checked, receipt, left, replace(right, role=role))

    def test_actual_markers_with_complete_receipt(self) -> None:
        checked, receipt, left, right = snapshots(self.root)
        for marker in ("release.duckdb.partial", ".load_receipt.json.partial"):
            path = self.root / marker
            path.write_text("INVENTED-interruption")
            with (
                self.subTest(marker=marker),
                fixture_reads(checked, receipt, left),
                self.assertRaisesRegex(StartupRefusal, "interrupted_load_refused"),
            ):
                verify_startup(
                    self.root,
                    environment="live",
                    embedded_reader=lambda _: left,
                    postgres_reader=lambda _: right,
                )
            path.unlink()
        with (
            fixture_reads(checked, receipt, left),
            self.assertRaisesRegex(StartupRefusal, "interrupted_load_refused"),
        ):
            verify_snapshots(checked, receipt, left, replace(right, interrupted=True))

    def test_no_fallback_and_developer_explicit_embedded(self) -> None:
        checked, receipt, left, _right = snapshots(self.root)
        for env in ("live", "staging"):
            with self.subTest(env=env), fixture_reads(checked, receipt, left):
                with self.assertRaisesRegex(
                    StartupRefusal, "embedded_environment_refused"
                ):
                    verify_startup(self.root, environment=env, embedded=True)
                with self.assertRaisesRegex(StartupRefusal, "postgres_required"):
                    verify_startup(
                        self.root, environment=env, embedded_reader=lambda _: left
                    )
        with fixture_reads(checked, receipt, left):
            verify_startup(
                self.root,
                environment="development",
                embedded=True,
                embedded_reader=lambda _: left,
            )

    def test_application_connector_pins_address_and_disables_password_file_lookup(
        self,
    ) -> None:
        import os
        import sys
        from types import SimpleNamespace

        from operations.runtime import app_connection

        connector = Mock()
        settings = self.settings()
        with patch.dict(sys.modules, {"psycopg": SimpleNamespace(connect=connector)}):
            self.assertIs(app_connection(settings), connector.return_value)
            self.assertIs(
                app_connection(dict(settings, EII_STORE="postgres")),
                connector.return_value,
            )
        self.assertEqual(connector.call_args.kwargs.get("hostaddr"), "127.0.0.1")
        self.assertEqual(connector.call_args.kwargs.get("passfile"), os.devnull)
