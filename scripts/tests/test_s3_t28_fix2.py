"""F5 plants: the parsed database namespace separates unrelated deployment roots."""

from dataclasses import replace
from unittest.mock import Mock, patch

from s3_t28_support import IDENTITY, WorkspaceCase

import preflight
import preflight_database
import preflight_rows
import preflight_store
from commands import load_release
from operations import config, deploy, runtime
from operations.common import Refusal, atomic_json


class DatabaseNamespace(WorkspaceCase):
    def test_n5_empty_environment_probes_development(self) -> None:
        settings = self.settings("development", "INVENTED_development")
        settings["EII_ENVIRONMENT"] = ""
        with patch(
            "preflight_database.probe_postgres",
            return_value=preflight_store.PgOutcome("ok", "INVENTED-probe"),
        ) as probe:
            selection = preflight_database.check_postgres(
                settings, self.root, 5.0, docker=False
            )
            self.assertEqual(selection.store, "postgres")
            probe.assert_called_once()

    def test_n5_empty_environment_loads_development(self) -> None:
        settings = self.settings("development", "INVENTED_development")
        settings["EII_ENVIRONMENT"] = ""
        with patch("commands.load_release.run_load", return_value=0) as load:
            self.assertEqual(load_release.run(settings, []), 0)
            load.assert_called_once()
            self.assertEqual(load.call_args.kwargs["database"], "INVENTED_development")

    def test_n5_empty_environment_config_defaults_to_development(self) -> None:
        settings = self.settings("development", "INVENTED_development")
        settings["EII_ENVIRONMENT"] = ""
        self.assertEqual(config.read_environment(settings).name, "development")

    def test_n5_empty_environment_still_refuses_reserved_database_names(self) -> None:
        for database in ("INVENTED_live", "INVENTED_STAGING"):
            settings = self.settings("development", database)
            settings["EII_ENVIRONMENT"] = ""
            with self.subTest(database=database, path="config"):
                with self.assertRaisesRegex(Refusal, "^environment_database_conflict$"):
                    config.read_environment(settings)
            with self.subTest(database=database, path="preflight"):
                with patch("preflight_database.probe_postgres") as probe:
                    selection = preflight_database.check_postgres(
                        settings, self.root, 5.0, docker=False
                    )
                    self.assertEqual(selection.store, "none")
                    assert selection.line is not None
                    self.assertEqual(
                        selection.line.reason, "environment_database_conflict"
                    )
                    probe.assert_not_called()
            with self.subTest(database=database, path="loader"):
                with patch("commands.load_release.run_load") as load:
                    self.assertEqual(load_release.run(settings, []), 4)
                    load.assert_not_called()

    def settings(
        self, name: str, database: str, parent: str = "deployment"
    ) -> dict[str, str]:
        home = self.root / parent / name
        return dict(
            EII_ENVIRONMENT=name,
            EII_STATE_DIR=str(home / "state"),
            EII_RELEASE_DIR=str(home / "releases" / IDENTITY),
            EII_DATABASE_URL="postgresql://eii_app"
            + "@"
            + "127.0.0.1:5432/"
            + database,
        )

    def test_disjoint_parents_cannot_share_one_database(self) -> None:
        for database, valid_name, refused_name in (
            ("INVENTED_staging", "staging", "live"),
            ("INVENTED_live", "live", "staging"),
        ):
            with self.subTest(database=database):
                valid = config.read_environment(
                    self.settings(valid_name, database, "left")
                )
                runtime.verify_peers(valid)
                with self.assertRaisesRegex(Refusal, "^environment_database_conflict$"):
                    config.read_environment(
                        self.settings(refused_name, database, "right")
                    )
        self.assertFalse((self.root / "left").exists())
        self.assertFalse((self.root / "right").exists())

    def test_each_wrong_namespace_refuses_before_loader_or_store(self) -> None:
        for name, database in (
            ("staging", "INVENTED_live"),
            ("live", "INVENTED_staging"),
            ("staging", "INVENTED_shared"),
            ("live", "INVENTED_shared"),
            ("development", "INVENTED_live"),
            ("development", "INVENTED_staging"),
        ):
            with self.subTest(name=name, database=database):
                settings = self.settings(name, database)
                with self.assertRaisesRegex(Refusal, "^environment_database_conflict$"):
                    config.read_environment(settings)
                if name == "development":
                    continue
                with (
                    patch("eii_product.store.loader.run_load") as load,
                    patch("operations.deploy.install_application") as install,
                    patch("operations.deploy.check_stores") as stores,
                ):
                    with self.assertRaisesRegex(
                        Refusal, "^environment_database_conflict$"
                    ):
                        deploy.load(self.root, settings)
                    load.assert_not_called()
                    install.assert_not_called()
                    stores.assert_not_called()
                self.assertFalse((self.root / "deployment" / name).exists())

    def test_parsed_database_case_and_escaped_suffix(self) -> None:
        for name, database in (
            ("staging", "INVENTED_LIVE"),
            ("live", "INVENTED_StAgInG"),
            ("development", "INVENTED_LiVe"),
            ("development", "INVENTED_STAGING"),
            ("development", "INVENTED%5flive"),
        ):
            with self.subTest(name=name, database=database):
                with self.assertRaisesRegex(Refusal, "^environment_database_conflict$"):
                    config.read_environment(self.settings(name, database))
        for name, database, expected in (
            ("staging", "INVENTED_StAgInG", "INVENTED_StAgInG"),
            ("staging", "INVENTED%5fstaging", "INVENTED_staging"),
            ("live", "INVENTED_LIVE", "INVENTED_LIVE"),
            ("live", "INVENTED%5flive", "INVENTED_live"),
            ("development", "INVENTED_development", "INVENTED_development"),
        ):
            with self.subTest(name=name, database=database):
                env = config.read_environment(self.settings(name, database))
                self.assertEqual(env.database, ("127.0.0.1", 5432, expected))

    def test_query_parameter_alias_cannot_select_another_database(self) -> None:
        for name, database in (
            ("staging", "INVENTED_staging?dbname=INVENTED_live"),
            ("live", "INVENTED_live?dbname=INVENTED_staging"),
            ("development", "INVENTED_development?dbname=INVENTED_live"),
        ):
            with self.subTest(name=name):
                with self.assertRaisesRegex(Refusal, "^database_url_invalid$"):
                    config.read_environment(self.settings(name, database))

    def test_direct_environment_construction_and_replace_cannot_bypass(self) -> None:
        for name, database in (
            ("live", "INVENTED_staging"),
            ("staging", "INVENTED_live"),
            ("development", "INVENTED_LIVE"),
        ):
            home = self.root / name
            with self.subTest(name=name):
                with self.assertRaisesRegex(Refusal, "^environment_database_conflict$"):
                    config.Environment(
                        name,
                        home / "releases" / IDENTITY,
                        home / "state",
                        config.DEFAULT_PORTS[name],
                        ("127.0.0.1", 5432, database),
                    )
        live = config.read_environment(self.settings("live", "INVENTED_live"))
        with self.assertRaisesRegex(Refusal, "^environment_database_conflict$"):
            replace(live, name="staging")

    def test_persisted_peer_identity_cannot_bypass(self) -> None:
        live = config.read_environment(self.settings("live", "INVENTED_live"))
        (live.home.parent / "staging/state").mkdir(parents=True)
        atomic_json(
            live.home.parent / "staging/state/environment.json",
            dict(
                environment="staging",
                release_id=IDENTITY,
                port=8089,
                database=["127.0.0.1", 5432, "INVENTED_shared"],
            ),
        )
        with self.assertRaisesRegex(Refusal, "^environment_database_conflict$"):
            runtime.verify_peers(live)

    def test_valid_names_under_disjoint_parents_remain_usable(self) -> None:
        environments = [
            config.read_environment(self.settings(name, "INVENTED_" + name, parent))
            for name, parent in (("live", "left"), ("staging", "right"))
        ]
        config.isolated(environments)
        for env in environments:
            runtime.verify_peers(env)
        self.assertFalse((self.root / "left").exists())
        self.assertFalse((self.root / "right").exists())

    def test_staging_smoke_uses_its_reserved_database_identity(self) -> None:
        from test_s3_t28_promotion import request

        live = config.read_environment(self.settings("live", "INVENTED_live"))
        state = live.home.parent / "staging/state"
        state.mkdir(parents=True)
        identity = state / "environment.json"
        database = ["127.0.0.1", 5432, "INVENTED_staging"]
        atomic_json(identity, dict(database=database))
        atomic_json(state / "process-8089.json", dict())
        route = dict(request(), backend_port=8089)
        report = dict(request(), port=8089)
        with (
            patch("operations.deploy.active_route", return_value=route),
            patch("operations.deploy.installed") as installed,
            patch("operations.deploy.process.require_owned"),
            patch(
                "operations.deploy.health_probe",
                return_value=dict(status="ok", release_id=IDENTITY),
            ),
            patch(
                "operations.deploy.get",
                return_value=(200, b'{"release_id":"' + IDENTITY.encode() + b'"}'),
            ),
        ):
            deploy.staging_probe(live, report)
            staged = installed.call_args.args[0]
            self.assertEqual(staged.database, tuple(database))
            self.assertNotEqual(staged.database, live.database)
            installed.reset_mock()
            atomic_json(identity, dict(database=list(live.database or ())))
            with self.assertRaisesRegex(Refusal, "^environment_database_conflict$"):
                deploy.staging_probe(live, report)
            installed.assert_not_called()

    def test_embedded_development_does_not_ignore_a_reserved_url(self) -> None:
        for database in ("INVENTED_live", "INVENTED_STAGING"):
            with self.subTest(database=database):
                with self.assertRaisesRegex(Refusal, "^environment_database_conflict$"):
                    config.read_environment(
                        self.settings("development", database), embedded=True
                    )
        env = self.settings("development", "INVENTED_development")
        self.assertIsNone(config.read_environment(env, embedded=True).database)
        del env["EII_DATABASE_URL"]
        self.assertIsNone(config.read_environment(env, embedded=True).database)

    def test_legacy_development_loader_refuses_before_connecting(self) -> None:
        connect = Mock(side_effect=AssertionError("store touched"))
        with patch("commands.load_release.run_load", return_value=0) as load:
            for database in ("INVENTED_live", "INVENTED_STAGING"):
                with self.subTest(database=database):
                    self.assertEqual(
                        load_release.run(
                            self.settings("development", database), [], connect=connect
                        ),
                        4,
                    )
            load.assert_not_called()
        connect.assert_not_called()

    def test_preflight_refuses_namespace_before_database_probe(self) -> None:
        for name, database in (
            ("staging", "INVENTED_live"),
            ("live", "INVENTED_staging"),
            ("development", "INVENTED_LIVE"),
        ):
            with (
                self.subTest(name=name),
                patch(
                    "preflight_database.probe_postgres",
                    return_value=preflight_store.PgOutcome("ok", "INVENTED-probe"),
                ) as probe,
            ):
                selection = preflight_database.check_postgres(
                    self.settings(name, database), self.root, 5.0, docker=False
                )
                self.assertEqual(selection.store, "none")
                assert selection.line is not None
                self.assertEqual(selection.line.reason, "environment_database_conflict")
                probe.assert_not_called()

    def test_preflight_report_preserves_conflict_without_touching_stores(self) -> None:
        line = preflight_store.Line
        tools = preflight_rows.ToolChecks(
            *(lambda: line("PASS", "INVENTED-tool", "checked") for _ in range(4))
        )
        release = {
            name: line("PASS", name, "checked")
            for name in (*preflight_rows.RELEASE_ROWS, preflight_rows.REPLAY_ROW)
        }
        with (
            patch(
                "preflight.rows.locked_dependencies_row",
                return_value=line("PASS", "locked-dependencies", "checked"),
            ),
            patch("preflight.rows.release_rows", return_value=release) as release_read,
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
                "preflight_database.probe_postgres",
                return_value=preflight_store.PgOutcome("ok", "INVENTED-probe"),
            ) as probe,
            patch("operations.runtime.installed") as installed,
            patch("operations.runtime.check_stores") as stores,
        ):
            report = preflight.run_preflight(
                self.root, self.settings("staging", "INVENTED_live"), tools=tools
            )
            self.assertEqual(report.status, 1)
            self.assertEqual(report.store, "none")
            self.assertEqual(
                [row.reason for row in report.lines if row.check == "postgresql"],
                ["environment_database_conflict"],
            )
            probe.assert_not_called()
            release_read.assert_not_called()
            installed.assert_not_called()
            stores.assert_not_called()
