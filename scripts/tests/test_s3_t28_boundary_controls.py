"""Independent boundary plants complement the round-one native interfaces."""

from __future__ import annotations

import ast
import builtins
import contextlib
import io
import sys
import unittest
from collections.abc import Iterator
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock, patch

import test_s3_t28_controls as controls_fixture
import test_s3_t28_runbook as runbook_fixture
from s3_t28_support import COMMIT, IDENTITY, WorkspaceCase, snapshots
from test_s3_t28_install import archive_fixture
from test_s3_t28_promotion import request

import sandbox_launch
import sandbox_profiles
from eii_product.store import loader, receipt
from operations import activation, build, config, deploy, install, runtime
from operations.common import Refusal, encoded, sha


class BoundaryControls(WorkspaceCase):
    sensitive = controls_fixture.Controls.sensitive

    def env(self, name: str = "live") -> config.Environment:
        home = self.root / name
        return config.Environment(
            name,
            home / "releases" / IDENTITY,
            home / "state",
            config.DEFAULT_PORTS[name],
            ("127.0.0.1", 5432, "INVENTED_" + name),
        )

    def require_red(self, assertion: Any) -> None:
        result = unittest.TestResult()
        unittest.FunctionTestCase(assertion).run(result)
        self.assertEqual(
            result.errors, [], "setup failures are not planted red evidence"
        )
        self.assertEqual(len(result.failures), 1)

    def test_ac6_each_actual_staging_http_and_health_response(self) -> None:
        raw = request()
        route = dict(raw, backend_port=8089)
        report = dict(raw, port=8089)

        def response(port: int, path: str) -> tuple[int, bytes]:
            return 200, encoded(dict(release_id=IDENTITY))

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
                return_value=dict(status="ok", release_id=IDENTITY),
            ) as health,
            patch("operations.deploy.get", side_effect=response) as get,
        ):
            deploy.staging_probe(self.env(), report)
            for path in ("/", "/api/release", "/api/layers/parcels"):
                get.side_effect = lambda port, candidate, path=path: (
                    (503, b"{}") if candidate == path else response(port, candidate)
                )
                with self.subTest(path=path):
                    self.sensitive(
                        deploy.staging_probe,
                        (self.env(), report),
                        "promotion_evidence_staging",
                    )
            get.side_effect = lambda port, path: (
                (200, encoded(dict(release_id="bc" * 32)))
                if path == "/api/release"
                else response(port, path)
            )
            self.sensitive(
                deploy.staging_probe, (self.env(), report), "promotion_evidence_staging"
            )
            get.side_effect = response
            for value in (
                None,
                dict(status="degraded", release_id=IDENTITY),
                dict(status="ok", release_id="bc" * 32),
            ):
                health.return_value = value
                with self.subTest(health=value):
                    self.sensitive(
                        deploy.staging_probe,
                        (self.env(), report),
                        "promotion_evidence_staging",
                    )

    def test_ac6_retained_self_folder_and_archive_independently(self) -> None:
        archive = archive_fixture(self.root)
        env = self.env()
        with patch("operations.install.verify_runtime"):
            application, digest = install.install_application(archive, env, COMMIT)
        env.release.mkdir(parents=True)
        (env.release / "manifest.json").write_bytes(
            encoded(
                dict(
                    release_kind="public_only", release_id=IDENTITY, code_version=COMMIT
                )
            )
        )
        raw = dict(request(), application_sha256=digest)
        with patch(
            "eii_product.store.release_check.check_release",
            return_value=SimpleNamespace(
                document=dict(release_id=IDENTITY, code_version=COMMIT)
            ),
        ):
            deploy.require_retained(env, raw)
            held = env.release.with_name("INVENTED-retained-away")
            env.release.rename(held)
            with self.assertRaises(Refusal) as caught:
                deploy.require_retained(env, raw)
            self.assertEqual(caught.exception.reason, "release_missing")
            self.sensitive(deploy.require_retained, (env, raw), "release_missing")
            held.rename(env.release)
            saved = application.parent / (digest + ".zip")
            original = saved.read_bytes()
            saved.write_bytes(original + b"INVENTED-corrupt-archive")
            with self.assertRaises(Refusal) as caught:
                deploy.require_retained(env, raw)
            self.assertEqual(caught.exception.reason, "application_checksum_mismatch")
            self.sensitive(
                deploy.require_retained, (env, raw), "application_checksum_mismatch"
            )
            saved.write_bytes(original)
            deploy.require_retained(env, raw)

    def test_ac3_matching_complete_receipt_each_semantic_refusal(self) -> None:
        path = self.root / "load_receipt.json"
        good = dict(state="complete", release_id=IDENTITY)
        path.write_bytes(encoded(good))
        self.assertEqual(receipt.read_receipt(self.root, IDENTITY), good)
        for field, value, reason in (
            ("state", "pending", "receipt_not_complete"),
            ("release_id", "bc" * 32, "receipt_release_mismatch"),
        ):
            path.write_bytes(encoded(dict(good, **{field: value})))
            with self.subTest(field=field):
                self.sensitive(
                    receipt.read_receipt,
                    (self.root, IDENTITY),
                    reason,
                    kind=receipt.ReceiptRefusal,
                )

    def test_ac3_loader_owner_role_and_superuser_flag(self) -> None:
        loader.require_owner("eii_owner", False)
        for role in (
            ("eii_app", False),
            ("eii_owner", True),
            ("INVENTED-other", False),
        ):
            with self.subTest(role=role):
                self.sensitive(
                    loader.require_owner,
                    role,
                    "owner_role_unavailable",
                    kind=loader.LoadRefusal,
                )

    def test_ac8_missing_bubblewrap_guard_with_valid_remaining_interfaces(self) -> None:
        # No process launches: everything after the deciding executable check
        # has a valid, observed interface, so an unrelated setup error cannot
        # masquerade as the controls-off failure.
        with (
            patch("sandbox_launch.os.access", return_value=False),
            patch("sandbox_launch.interpreter_for", return_value=Mock()),
            patch("sandbox_launch.current_venv", return_value=self.root),
            patch("sandbox_launch.open_sources", return_value={}),
            patch("sandbox_launch.build_argv", return_value=["INVENTED-sandbox"]),
            patch(
                "sandbox_launch._start", return_value=SimpleNamespace(returncode=0)
            ) as start,
        ):
            layout = sandbox_launch.Layout(
                self.root,
                self.root / "INVENTED-input",
                self.root / "INVENTED-private-build",
                self.root / "INVENTED-extensions",
                staging=self.root / "INVENTED-stage",
            )
            reason = f"bubblewrap is not installed at {sandbox_profiles.BWRAP}: install the distribution package bubblewrap"
            self.sensitive(
                sandbox_launch.run_in_sandbox,
                ("build-release", layout, (sys.executable,)),
                reason,
                kind=sandbox_launch.SandboxError,
            )
            start.assert_called_once()

    def sandbox(self, profile: str, layout: Any, command: Any) -> Any:
        (layout.staging / "manifest.json").write_bytes(
            encoded(dict(release_kind="public_only", release_id=IDENTITY))
        )
        (layout.vault / "INVENTED-only").write_bytes(b"INVENTED-owned")
        return SimpleNamespace(returncode=0)

    def test_ac8_cleanup_refusal_disabled_alone_admits_leftover_and_delete_error(
        self,
    ) -> None:
        for mode in ("leftover", "error"):
            root = self.root / mode
            root.mkdir()
            cleanup = (
                (lambda _: None)
                if mode == "leftover"
                else Mock(side_effect=OSError("INVENTED-delete-error"))
            )
            with self.subTest(mode=mode):
                self.sensitive(
                    build.build_release,
                    (root,),
                    "vault_cleanup_failed",
                    kwargs=dict(
                        sandbox=self.sandbox, cleanup=cleanup, validate=lambda _: None
                    ),
                )
            self.assertTrue(
                (root / "data/releases" / IDENTITY / "manifest.json").is_file()
            )

    def test_ac8_cross_database_target_at_both_lower_level_store_boundaries(
        self,
    ) -> None:
        env = self.env("staging")
        settings = dict(
            EII_DATABASE_URL="postgres://eii_app" + "@" + "127.0.0.1:5432/INVENTED_live"
        )
        checked, _, _, _ = snapshots(self.root)
        connection = Mock()
        with (
            patch("eii_product.store.startup.verify_startup", return_value=checked),
            patch("operations.runtime.app_connection", return_value=connection),
            patch(
                "eii_product.store.loader._execute",
                return_value=[("eii_app", False, False)],
            ),
            patch("eii_product.store.loader._schema_present", return_value=True),
        ):
            self.sensitive(
                runtime.check_stores,
                (env, settings),
                "cross_environment_write",
                kwargs=dict(connect=lambda _: connection),
            )
            self.sensitive(
                runtime.inspect_schema, (env, settings), "cross_environment_write"
            )

    def test_ac7_log_history_witness_and_truncation_each(self) -> None:
        from test_s3_t28_promotion import Promotion

        for mode in ("empty", "truncated", "witness"):
            fixture = Promotion()
            fixture.setUp()
            self.addCleanup(fixture.doCleanups)
            fixture.execute()
            path = fixture.state / "promotions.jsonl"
            if mode == "empty":
                path.write_bytes(b"")
            elif mode == "truncated":
                path.write_bytes(path.read_bytes().rstrip(b"\n"))
            else:
                (fixture.state / "history.json").write_bytes(
                    encoded(dict(sequence=1, sha256="bc" * 32))
                )
            with self.subTest(mode=mode):
                self.sensitive(
                    activation.entries, (fixture.state,), "promotion_log_mismatch"
                )

    def test_ac8_down_preserves_each_release_ledger_journal_and_volume(self) -> None:
        env = self.env()
        env.state.mkdir(parents=True)
        settings = dict(
            EII_ENVIRONMENT="live",
            EII_RELEASE_DIR=str(env.release),
            EII_STATE_DIR=str(env.state),
            EII_DATABASE_URL="postgres://eii_app"
            + "@"
            + "127.0.0.1:5432/INVENTED_live",
        )
        record = env.state / "process-18088.json"
        targets = (
            env.release / "INVENTED-table",
            env.state / "local-ledger.sqlite",
            env.count_path,
            env.home / "INVENTED-database-volume",
        )
        for target in targets:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"INVENTED-persistent-bytes")
        before = {path: path.read_bytes() for path in targets}

        def down() -> None:
            record.write_bytes(encoded(dict(pid=17, environment="live")))
            deploy.down(settings)
            after = {
                path: path.read_bytes() if path.exists() else None for path in targets
            }
            self.assertEqual(after, before, "down deleted persistent data")

        with patch("operations.process.terminate"):
            down()
        for target in targets:
            with self.subTest(target=target.name):
                with patch(
                    "operations.process.terminate",
                    side_effect=lambda *_, path=target: path.unlink(),
                ):
                    self.require_red(down)
                target.write_bytes(before[target])

    def test_ac8_preflight_probes_only_each_release_state_and_store_write(self) -> None:
        import preflight
        import preflight_rows
        import preflight_store

        env = self.env("staging")
        settings = dict(
            EII_ENVIRONMENT="staging",
            EII_RELEASE_DIR=str(env.release),
            EII_STATE_DIR=str(env.state),
            EII_DATABASE_URL="postgres://eii_app"
            + "@"
            + "127.0.0.1:5432/INVENTED_staging",
        )
        line = preflight_store.Line
        tools = preflight_rows.ToolChecks(
            *(lambda: line("PASS", "INVENTED-tool", "checked") for _ in range(4))
        )
        release = {
            name: line("PASS", name, "checked")
            for name in (*preflight_rows.RELEASE_ROWS, preflight_rows.REPLAY_ROW)
        }
        targets = (
            env.release / "INVENTED-table",
            env.state / "route.json",
            env.home / "INVENTED-store",
        )
        for target in targets:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"INVENTED-before")
        before = {path: path.read_bytes() for path in targets}

        def probe() -> None:
            result = preflight.run_preflight(self.root, settings, tools=tools)
            self.assertEqual(result.status, 0)
            self.assertEqual(
                {path: path.read_bytes() for path in targets},
                before,
                "preflight wrote persistent data",
            )

        with (
            patch(
                "preflight.database.check_postgres",
                return_value=preflight_store.Selection(
                    line("PASS", "postgresql", "checked"), "postgres"
                ),
            ),
            patch(
                "preflight.rows.locked_dependencies_row",
                return_value=line("PASS", "locked-dependencies", "checked"),
            ),
            patch("preflight.rows.release_rows", return_value=release),
            patch(
                "preflight.rows.api_port_row",
                return_value=line("PASS", "api-port", "free"),
            ),
            patch(
                "preflight.rows.env_tracked_row",
                return_value=line("PASS", "env-not-tracked", "checked"),
            ),
            patch(
                "preflight.rows.wsl_row",
                return_value=line("WARN", "wsl-interop", "not applicable"),
            ),
            patch(
                "operations.deploy.request_for", return_value=dict(backend_port=8089)
            ),
            patch("operations.runtime.verify_peers"),
            patch(
                "operations.runtime.installed", return_value=(self.root, {})
            ) as installed,
            patch("operations.runtime.check_stores"),
            patch(
                "eii_product.api.health.local_assets", return_value=("ok", "ok", "ok")
            ),
        ):
            probe()
            for target in targets:

                def write(*_: Any, path: Any = target) -> Any:
                    path.write_bytes(b"INVENTED-unauthorised-write")
                    return self.root, {}

                installed.side_effect = write
                with self.subTest(target=target.name):
                    self.require_red(probe)
                target.write_bytes(before[target])

    def test_ac2_spend_journal_missing_and_truncated_fail_without_reset(self) -> None:
        import io

        from eii_product.photoreal_tiles.limit import Budget, BudgetFailure

        env = self.env()
        env.state.mkdir(parents=True)
        budget = Budget(env.count_path)
        self.sensitive(Budget.count, (budget,), "count_unavailable", kind=BudgetFailure)
        self.assertFalse(env.count_path.exists())
        env.count_path.write_text("ready:0\npending:0\nready:1\n")
        self.assertEqual(budget.count(), 1)
        # Lose a whole valid record after it was seen: removing the prefix
        # guard alone admits the stale lower count without another parse error.
        truncated = io.StringIO("ready:0\n")
        self.sensitive(
            Budget._read,
            (budget, truncated),
            "count_unavailable",
            kind=BudgetFailure,
            reset_fixture=lambda: truncated.seek(0),
        )
        fresh = Budget(env.count_path)
        partial = io.StringIO("ready:0")
        self.sensitive(
            Budget._read,
            (fresh, partial),
            "count_unavailable",
            kind=BudgetFailure,
            reset_fixture=lambda: partial.seek(0),
        )
        self.assertEqual(env.count_path.read_text(), "ready:0\npending:0\nready:1\n")

    def test_ac8_health_extra_property_and_each_enum_control(self) -> None:
        from pydantic import ConfigDict, ValidationError, create_model

        from eii_product.api.health import Health

        value = dict(
            status="ok",
            store="postgres",
            postgres="up",
            release_id=IDENTITY,
            release_hash=IDENTITY,
            parity="identical",
            ledger="local",
            local_ledger_rows=0,
            model="template",
            traffic="simulated",
            tiles="ok",
            fonts="ok",
            replays="ok",
        )
        Health.model_validate(value)
        extra = dict(value, extra="INVENTED-extra")
        with self.assertRaises(ValidationError):
            Health.model_validate(extra)

        class ExtraDisabled(Health):
            model_config = ConfigDict(extra="allow")

        def accept_extra() -> None:
            with self.assertRaises(ValidationError):
                ExtraDisabled.model_validate(extra)

        self.require_red(accept_extra)
        for field in (
            "status",
            "store",
            "postgres",
            "parity",
            "ledger",
            "model",
            "traffic",
            "tiles",
            "fonts",
            "replays",
        ):
            changed = dict(value, **{field: "INVENTED-wrong-enum"})
            with self.subTest(field=field):
                with self.assertRaises(ValidationError):
                    Health.model_validate(changed)
                definitions: dict[str, Any] = {field: (str, ...)}
                loosened = create_model(
                    "INVENTEDEnumDisabled", __base__=Health, **definitions
                )

                def accept_enum(model: Any = loosened, plant: Any = changed) -> None:
                    with self.assertRaises(ValidationError):
                        model.model_validate(plant)

                self.require_red(accept_enum)

    def test_ac8_each_static_and_dynamic_import_form_has_individual_guard_proof(
        self,
    ) -> None:
        import import_boundary_judge

        for source in (
            "import eii_custodian",
            "from eii_custodian import release",
            "import importlib; importlib.import_module('eii_custodian.release')",
            "__import__('eii_custodian.release')",
        ):
            tree = ast.parse(source)

            def assertion(parsed: ast.AST = tree) -> None:
                found = import_boundary_judge.judge_tree(
                    parsed, "eii_product", ("eii_product",), ("eii_custodian",)
                )
                self.assertEqual(len(found), 1, "custodian import admitted")
                self.assertEqual(found[0].kind, "forbidden-import")

            assertion()
            with (
                self.subTest(source=source),
                patch(
                    "import_boundary_judge._forbidden_first_component",
                    return_value=None,
                ),
            ):
                self.require_red(assertion)

    def test_ac8_complete_product_dispatch_has_no_custodian_import_or_private_open(
        self,
    ) -> None:
        from pathlib import Path
        from types import ModuleType

        private = self.root / "INVENTED-custodian-only"
        private.mkdir()
        record = private / "INVENTED-record"
        record.write_bytes(b"INVENTED-only")
        attempts: list[str] = []
        original_import, original_open, original_io_open = (
            builtins.__import__,
            builtins.open,
            io.open,
        )

        def import_guard(name: str, *args: Any, **kwargs: Any) -> Any:
            if name.split(".")[0] == "eii_custodian":
                attempts.append("custodian-import")
                raise Refusal("product_plane_import_refused")
            return original_import(name, *args, **kwargs)

        def open_guard(original: Any, name: Any, *args: Any, **kwargs: Any) -> Any:
            if not isinstance(name, int) and Path(name).resolve().is_relative_to(
                private
            ):
                attempts.append("custodian-open")
                raise Refusal("product_plane_open_refused")
            return original(name, *args, **kwargs)

        @contextlib.contextmanager
        def scope(command: str) -> Iterator[None]:
            if command == "build-release":
                yield
                return
            with (
                patch("builtins.__import__", side_effect=import_guard),
                patch(
                    "builtins.open",
                    side_effect=lambda *a, **k: open_guard(original_open, *a, **k),
                ),
                patch(
                    "io.open",
                    side_effect=lambda *a, **k: open_guard(original_io_open, *a, **k),
                ),
            ):
                yield

        case = runbook_fixture.Runbook(
            "test_dispatch_build_stage_promote_rollback_handover_and_down"
        )
        case.command_scope = scope
        result = unittest.TestResult()
        case.run(result)
        self.assertTrue(result.wasSuccessful(), result.errors + result.failures)
        self.assertEqual(attempts, [])
        # Test each tripwire itself with its sole refusal disabled. The opened
        # path is an invented stand-in, never the repository's real vault.
        with patch.dict(sys.modules, {"eii_custodian": ModuleType("eii_custodian")}):
            self.sensitive(
                import_guard, ("eii_custodian",), "product_plane_import_refused"
            )
        self.sensitive(
            open_guard, (original_open, record, "rb"), "product_plane_open_refused"
        )

    def test_ac1_direct_factory_cannot_omit_its_shared_policy_call(self) -> None:
        from eii_product.api import app
        from eii_product.api.startup import ServingPolicy
        from eii_product.store.startup import StartupRefusal

        store = Mock(engine="postgres", release_id=IDENTITY)
        verify = Mock(side_effect=StartupRefusal("startup_parity_failed"))
        options: dict[str, Any] = dict(
            store=store,
            ledger=Mock(),
            release_dir=self.root,
            web_dir=self.root,
            count_path=self.root / "count.log",
            key_reader=lambda: None,
            offline_reader=lambda: True,
            fc_setting_reader=lambda: None,
            startup_policy=ServingPolicy("live", IDENTITY, verify),
        )
        with patch("eii_product.api.app.MountedRelease"):
            with self.assertRaisesRegex(StartupRefusal, "startup_parity_failed"):
                app.create_app(self.root, **options)
            mutant = controls_fixture.without_call(
                app.create_app, "startup_policy.require"
            )

            def assertion() -> None:
                with self.assertRaisesRegex(StartupRefusal, "startup_parity_failed"):
                    served = mutant(self.root, **options)
                    self.assertIsNotNone(served.state.release_mount)

            self.require_red(assertion)

    def test_ac8_public_install_and_start_do_not_require_frozen_only_evidence(
        self,
    ) -> None:
        env = self.env()
        source = self.root / "INVENTED-export" / IDENTITY
        source.mkdir(parents=True)
        document = dict(
            release_kind="public_only",
            release_id=IDENTITY,
            code_version=COMMIT,
            tables=[dict(file="table.parquet")],
        )
        (source / "manifest.json").write_bytes(encoded(document))
        (source / "table.parquet").write_bytes(b"INVENTED-public-table")
        archive = archive_fixture(self.root)
        with patch("operations.install.verify_runtime"):
            application, digest = install.install_application(archive, env, COMMIT)
        raw = dict(request(), application_sha256=digest)
        with patch(
            "eii_product.store.release_check.check_release",
            return_value=SimpleNamespace(document=document, folder=source),
        ):
            install.install_release(source, env, application)
            runtime.installed(env, raw)
            for boundary in (
                lambda: install.install_release(source, env, application),
                lambda: runtime.installed(env, raw),
            ):

                def assertion(call: Any = boundary) -> None:
                    try:
                        call()
                    except Refusal as error:
                        self.assertEqual(error.reason, "INVENTED-frozen-only-refusal")
                        self.fail("valid unfrozen Public operation refused")

                with (
                    patch(
                        "operations.install.public_kind",
                        side_effect=Refusal("INVENTED-frozen-only-refusal"),
                    ),
                    patch(
                        "operations.runtime.public_kind",
                        side_effect=Refusal("INVENTED-frozen-only-refusal"),
                    ),
                ):
                    self.require_red(assertion)

    def test_ac2_every_documented_inventory_member_has_controls_off_proof(self) -> None:
        import test_operations_parity as parity

        text = parity.DOCUMENT.read_text()
        for kind in ("example", "tree", "secrets", "preflight"):
            complete = parity.documented(text, kind)
            parity.assert_parity(text, kind, complete)
            for name in sorted(complete):
                actual = complete - {name}
                try:
                    parity.assert_parity(text, kind, actual)
                except AssertionError as error:
                    reason = str(error)
                else:
                    self.fail("missing inventory member was admitted")
                with self.subTest(kind=kind, name=name):
                    self.sensitive(
                        parity.assert_parity,
                        (text, kind, actual),
                        reason,
                        kind=AssertionError,
                    )

    def test_ac8_mismatched_existing_schema_never_reloads_or_starts(self) -> None:
        import preflight
        from commands import up_cmd
        from preflight_store import Line

        env = self.env()
        env.state.mkdir(parents=True)
        physical_schema = env.state / "INVENTED-schema"
        # Correct prefix, different full identity. All role/receipt/config
        # interfaces are valid; only the selected manifest identity is wrong.
        before = encoded(dict(release_id="ab" * 8 + "bc" * 24))
        physical_schema.write_bytes(before)
        settings = dict(
            EII_ENVIRONMENT="live",
            EII_RELEASE_DIR=str(env.release),
            EII_STATE_DIR=str(env.state),
            EII_DATABASE_URL="postgres://eii_app"
            + "@"
            + "127.0.0.1:5432/INVENTED_live",
        )
        report = preflight.Report(
            (Line("FAIL", "release", "startup_identity_mismatch"),), "postgres", 1
        )
        with (
            patch("commands.up_cmd.preflight.run_preflight", return_value=report),
            patch("operations.deploy.verify_peers"),
            patch("operations.deploy.request_for", return_value=request()),
            patch("operations.deploy.installed"),
            patch("operations.deploy.inspect_schema", return_value=True),
            patch("operations.deploy.check_stores"),
            patch(
                "eii_product.store.loader.perform",
                side_effect=lambda *a, **k: physical_schema.write_bytes(
                    b"INVENTED-reloaded"
                ),
            ) as load,
            patch("operations.deploy.up") as start,
            contextlib.redirect_stdout(io.StringIO()),
        ):

            def assertion() -> None:
                self.assertEqual(
                    up_cmd.run(self.root, settings, ()), 4, "mismatched schema admitted"
                )
                self.assertEqual(physical_schema.read_bytes(), before)
                load.assert_not_called()
                start.assert_not_called()

            assertion()
            mutant = controls_fixture.without_return(deploy.ensure_schema, "False")
            with patch("operations.deploy.ensure_schema", side_effect=mutant):
                self.require_red(assertion)
            load.assert_called_once()
            start.assert_called_once()
            self.assertEqual(physical_schema.read_bytes(), b"INVENTED-reloaded")

    def test_ac3_loader_existing_schema_and_each_data_parity_control(self) -> None:
        self.sensitive(
            loader.refuse_existing_schema,
            (True,),
            "schema_exists",
            kind=loader.LoadRefusal,
        )
        checked, _, left, right = snapshots(self.root)
        loader.verify_staged(left.rows, right.rows, checked)
        for mode in ("value", "count"):
            bad: dict[str, Any] = {
                name: [dict(row) for row in rows] for name, rows in right.rows.items()
            }
            if mode == "value":
                bad["source_registry"][0]["source_id"] = "INVENTED-other"
            else:
                bad["source_registry"] = []
            with self.subTest(mode=mode):
                # Equal but wrong counts isolate the declared-count control;
                # a one-sided deletion is also rejected by the digest defence.
                self.sensitive(
                    loader.verify_staged,
                    (bad if mode == "count" else left.rows, bad, checked),
                    "store_verification_failed",
                    kind=loader.LoadRefusal,
                )

    def test_ac4_freeze_and_supported_protected_kind_have_dedicated_controls(
        self,
    ) -> None:
        document = dict(release_kind="public_only")
        self.assertEqual(
            receipt.refuse_public_only_freeze(document), receipt.FREEZE_REASON
        )
        mutant = controls_fixture.without_return(
            receipt.refuse_public_only_freeze, "FREEZE_REASON"
        )
        self.require_red(
            lambda: self.assertEqual(
                mutant(document), receipt.FREEZE_REASON, "Public freeze admitted"
            )
        )
        from operations import evidence

        for environment in ("live", "staging"):
            raw = dict(request(), release_kind="protected", environment=environment)
            if environment == "staging":
                raw.update(
                    operation="start_staging", entry_port=8089, backend_port=8089
                )
            with self.subTest(environment=environment):
                self.sensitive(
                    evidence.operation, (raw,), "protected_release_requires_s11_t09"
                )

    def test_ac4_each_public_build_parameter_request_is_independently_refused(
        self,
    ) -> None:
        for parameter in ("A", "B"):
            root = self.root / parameter
            root.mkdir()
            with self.subTest(parameter=parameter):
                self.sensitive(
                    build.build_release,
                    (root,),
                    "public_only_parameter_selection",
                    kwargs=dict(
                        parameter_set=parameter,
                        sandbox=self.sandbox,
                        validate=lambda _: None,
                    ),
                )
            self.assertTrue(
                (root / "data/releases" / IDENTITY / "manifest.json").is_file()
            )

    def test_ac3_each_existing_release_byte_and_folder_identity(self) -> None:
        env = self.env()
        source = self.root / "INVENTED-source" / IDENTITY
        source.mkdir(parents=True)
        (source / "table.parquet").write_bytes(b"INVENTED-original-table")
        (source / "tiles").mkdir()
        (source / "tiles/INVENTED-tile").write_bytes(b"INVENTED-original-tile")
        document = dict(
            release_kind="public_only",
            release_id=IDENTITY,
            build_id="INVENTED-build",
            tables=[dict(file="table.parquet")],
            artefacts=[
                dict(
                    path="tiles/INVENTED-tile",
                    sha256=sha(source / "tiles/INVENTED-tile"),
                )
            ],
        )
        (source / "manifest.json").write_bytes(encoded(document))
        application = self.root / "INVENTED-application"
        checked = SimpleNamespace(document=document, folder=source)
        with patch(
            "eii_product.store.release_check.check_release", return_value=checked
        ):
            install.install_release(source, env, application)
            for name in ("manifest.json", "table.parquet", "tiles/INVENTED-tile"):
                path = env.release / name
                original = path.read_bytes()
                if name == "manifest.json":
                    path.write_bytes(
                        encoded(dict(document, build_id="INVENTED-rewritten"))
                    )
                else:
                    path.write_bytes(original + b"INVENTED-mutation")
                with self.subTest(file=name):
                    self.sensitive(
                        install.install_release,
                        (source, env, application),
                        "install_byte_mismatch",
                    )
                path.write_bytes(original)
            renamed = source.with_name("INVENTED-wrong-folder")
            source.rename(renamed)
            checked.folder = renamed
            self.sensitive(
                install.install_release,
                (renamed, env, application),
                "release_folder_identity_mismatch",
            )
        from eii_product.store import release_check

        for label in ("release", "file", "schema"):
            with self.subTest(hash=label):
                self.sensitive(
                    release_check._require_hash,
                    ("bc" * 32, "ab" * 32),
                    "digest_mismatch",
                    kind=release_check.ReleaseRefusal,
                )

    def test_ac7_single_entry_reuse_has_an_independent_admission_plant(self) -> None:
        import inspect
        import textwrap

        @contextlib.contextmanager
        def scope(command: str) -> Iterator[None]:
            if command != "up":
                yield
                return
            # Compile after the runbook installs its invented IO interfaces.
            # Only the existing-entry reuse condition is disabled.
            function = deploy.up
            tree = ast.parse(textwrap.dedent(inspect.getsource(function)))
            changed = 0
            for node in ast.walk(tree):
                if isinstance(node, ast.If) and ast.unparse(node.test).startswith(
                    "path.exists() and read_json("
                ):
                    node.test = ast.Constant(False)
                    changed += 1
            self.assertEqual(changed, 1)
            namespace = dict(function.__globals__)
            exec(
                compile(
                    ast.fix_missing_locations(tree),
                    "<invented-entry-reuse-off>",
                    "exec",
                ),
                namespace,
            )
            with patch("operations.deploy.up", namespace[function.__name__]):
                yield

        case = runbook_fixture.Runbook(
            "test_dispatch_build_stage_promote_rollback_handover_and_down"
        )
        case.command_scope = scope
        result = unittest.TestResult()
        case.run(result)
        self.assertEqual(result.errors, [])
        self.assertEqual(len(result.failures), 1)
        self.assertIn("second exposed entry admitted", result.failures[0][1])

    def test_ac2_configured_occupied_port_refuses_with_default_free_and_inverse(
        self,
    ) -> None:
        import errno

        import preflight
        import preflight_rows
        import preflight_store

        env = self.env("staging")
        configured = 19091
        settings = dict(
            EII_ENVIRONMENT="staging",
            EII_RELEASE_DIR=str(env.release),
            EII_STATE_DIR=str(env.state),
            EII_API_PORT=str(configured),
            EII_DATABASE_URL="postgres://eii_app"
            + "@"
            + "127.0.0.1:5432/INVENTED_staging",
        )
        line = preflight_store.Line
        tools = preflight_rows.ToolChecks(
            *(
                lambda name=name: line("PASS", name, "checked")
                for name in (
                    "python",
                    "node-npm",
                    "duckdb-extensions",
                    "bubblewrap-sandbox",
                )
            )
        )
        release = {
            name: line("PASS", name, "checked")
            for name in (*preflight_rows.RELEASE_ROWS, preflight_rows.REPLAY_ROW)
        }
        occupied = {configured}
        probed: list[int] = []

        def socket_factory(*_: Any) -> Any:
            instance = Mock()

            def bind(endpoint: Any) -> None:
                self.assertEqual(endpoint[0], "127.0.0.1")
                probed.append(endpoint[1])
                if endpoint[1] in occupied:
                    raise OSError(errno.EADDRINUSE, "INVENTED-occupied")

            instance.bind.side_effect = bind
            return instance

        with (
            patch(
                "preflight.database.check_postgres",
                return_value=preflight_store.Selection(
                    line("PASS", "postgresql", "checked"), "postgres"
                ),
            ),
            patch(
                "preflight.rows.locked_dependencies_row",
                return_value=line("PASS", "locked-dependencies", "checked"),
            ),
            patch("preflight.rows.release_rows", return_value=release),
            patch(
                "preflight.rows.env_tracked_row",
                return_value=line("PASS", "env-not-tracked", "checked"),
            ),
            patch(
                "preflight.rows.wsl_row",
                return_value=line("WARN", "wsl-interop", "not applicable"),
            ),
            patch(
                "operations.deploy.request_for",
                return_value=dict(backend_port=configured),
            ),
            patch("operations.runtime.verify_peers"),
            patch("operations.runtime.installed", return_value=(self.root, {})),
            patch("operations.runtime.check_stores"),
            patch(
                "eii_product.api.health.local_assets", return_value=("ok", "ok", "ok")
            ),
            patch("preflight.rows.socket.socket", side_effect=socket_factory),
        ):

            def decision() -> int:
                return preflight.up_decision(
                    settings, preflight.run_preflight(self.root, settings, tools=tools)
                )[0]

            self.assertEqual(decision(), 5)
            self.assertEqual(probed, [configured])
            real_row = preflight_rows.api_port_row
            # Admit the occupied configured port by probing the unrelated
            # default instead. Every other report row remains healthy.
            with patch(
                "preflight.rows.api_port_row", side_effect=lambda _: real_row(8000)
            ):
                self.require_red(
                    lambda: self.assertEqual(
                        decision(), 5, "occupied configured port admitted"
                    )
                )
            occupied.clear()
            occupied.add(8000)
            probed.clear()
            self.assertEqual(decision(), 0)
            self.assertEqual(probed, [configured])
