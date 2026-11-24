"""Independent configuration plants; no engines or deployment directories."""

from __future__ import annotations

import socket
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import s3_t28_support as support

from operations.common import Refusal
from operations.config import (
    RESTRICTED,
    Environment,
    api_port,
    database_identity,
    isolated,
    read_environment,
    runtime_environment,
    write_target,
)

ROOT = support.ROOT


class Isolation(unittest.TestCase):
    def test_public_operational_preflight_uses_installed_assets_not_freeze_tree(
        self,
    ) -> None:
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
                "preflight.rows.tiles_row",
                return_value=line(
                    "FAIL", "tiles-glyphs-fonts", "unrelated frozen release"
                ),
            ) as old_tiles,
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
            patch("operations.runtime.installed", return_value=(self.root, {})),
            patch("operations.runtime.check_stores"),
            patch("eii_product.store.release_check.check_release"),
            patch(
                "eii_product.api.health.local_assets", return_value=("ok", "ok", "ok")
            ),
        ):
            report = preflight.run_preflight(self.root, settings, tools=tools)
            self.assertEqual(report.status, 0)
            old_tiles.assert_not_called()
        self.assertFalse(env.home.exists())

    def test_preflight_gate_rejects_live_traffic_without_a_key(self) -> None:
        import preflight
        import preflight_rows
        import preflight_store

        line = preflight_store.Line
        tools = preflight_rows.ToolChecks(
            *(lambda: line("PASS", "INVENTED-tool", "checked") for _ in range(4))
        )
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
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
            patch(
                "preflight.rows.env_tracked_row",
                return_value=line("PASS", "env-not-tracked", "checked"),
            ),
            patch(
                "preflight.rows.wsl_row",
                return_value=line("WARN", "wsl-interop", "not applicable"),
            ),
        ):
            positive = preflight.run_preflight(
                self.root, {}, tools=tools, api_port=port
            )
            self.assertEqual(positive.status, 0)
            planted = preflight.run_preflight(
                self.root,
                {"EII_TRAFFIC_PROVIDER": "tomtom"},
                tools=tools,
                api_port=port,
            )
            self.assertEqual(planted.status, 1)
            failures = [item for item in planted.lines if item.severity == "FAIL"]
            self.assertEqual(
                [(item.check, item.reason) for item in failures],
                [("traffic-provider-key", "traffic_mode_refused")],
            )

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(dir=ROOT / ".overnight/tmp")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def env(self, name: str) -> Environment:
        home = self.root / name
        return Environment(
            name,
            home / "releases" / ("ab" * 32),
            home / "state",
            {"live": 8088, "staging": 8089}[name],
            ("127.0.0.1", 5432, "INVENTED_" + name),
        )

    def test_valid_isolated_and_closed_child(self) -> None:
        isolated((self.env("live"), self.env("staging")))
        child = runtime_environment({"PATH": "synthetic", "UNRELATED": "marker"})
        self.assertEqual(child["PATH"], "synthetic")
        self.assertNotIn("UNRELATED", child)
        self.assertEqual(
            database_identity(
                "postgres://eii_app" + "@" + "LOCALHOST:5432/INVENTED_live"
            ),
            database_identity("postgresql://eii_app" + "@" + "127.0.0.1/INVENTED_live"),
        )

    def test_each_unwanted_setting(self) -> None:
        for key in sorted(
            RESTRICTED
            | {
                "EII_UNKNOWN",
                "EII_REGISTER_FILE",
                "EII_BESTTIME_RUN_CREDIT_LIMIT",
                "EII_STORE",
                "EII_SOURCE_RELEASE_DIR",
                "PGHOSTADDR",
                "PGSERVICE",
                "PGPASSFILE",
                "PGSSLROOTCERT",
            }
        ):
            with (
                self.subTest(key=key),
                self.assertRaisesRegex(Refusal, "unwanted_runtime_setting"),
            ):
                runtime_environment({key: "SYN-dummy-marker"})

    def test_modes_have_separate_branches(self) -> None:
        for key, value, reason in (
            ("EII_DECISION_PROVIDER", "jev", "decision_mode_refused"),
            ("EII_PRESENTER", "1", "presenter_mode_refused"),
            ("EII_TRAFFIC_PROVIDER", "tomtom", "traffic_mode_refused"),
        ):
            with self.subTest(key=key), self.assertRaisesRegex(Refusal, reason):
                runtime_environment({key: value})

    def test_each_path_database_and_port_collision(self) -> None:
        live, staging = self.env("live"), self.env("staging")
        with self.assertRaisesRegex(Refusal, "environment_database_conflict"):
            replace(staging, database=live.database)
        # Bypass only construction to keep the independent pair guard deciding.
        with patch("operations.config.require_database_environment"):
            database_collision = replace(staging, database=live.database)
        for changed, reason in (
            (replace(staging, release=live.release), "environment_path_conflict"),
            (replace(staging, state=live.state), "environment_path_conflict"),
            (database_collision, "environment_database_conflict"),
            (replace(staging, port=live.port), "environment_port_conflict"),
            (replace(staging, port=18088), "environment_port_conflict"),
        ):
            with self.subTest(reason=reason), self.assertRaisesRegex(Refusal, reason):
                isolated((live, changed))

    def test_symlink_alias(self) -> None:
        live, staging = self.env("live"), self.env("staging")
        live.release.parent.mkdir(parents=True)
        staging.home.mkdir()
        staging.release.parent.symlink_to(live.release.parent)
        with self.assertRaisesRegex(Refusal, "environment_path_conflict"):
            isolated((live, staging))

    def test_leaf_release_symlink_cannot_share_an_environment_copy(self) -> None:
        live, staging = self.env("live"), self.env("staging")
        live.release.mkdir(parents=True)
        staging.release.parent.mkdir(parents=True)
        staging.release.symlink_to(live.release, target_is_directory=True)
        with self.assertRaisesRegex(Refusal, "environment_path_conflict"):
            isolated((live, staging))

    def test_cross_write_has_no_effect(self) -> None:
        live, staging = self.env("live"), self.env("staging")
        for path in (
            live.release,
            live.state / "ledger",
            live.state / "log",
            live.applications,
        ):
            with (
                self.subTest(path=path.name),
                self.assertRaisesRegex(Refusal, "cross_environment_write"),
            ):
                write_target(staging, path)
        self.assertFalse(live.home.exists())

    def test_ports_and_host(self) -> None:
        for value in ("-1", "0", "65536", "x", "٨", "1.2"):
            with (
                self.subTest(value=value),
                self.assertRaisesRegex(Refusal, "api_port_invalid"),
            ):
                api_port(value)
        self.assertEqual(api_port("8089"), 8089)
        with self.assertRaisesRegex(Refusal, "host_not_loopback"):
            read_environment({"EII_LISTEN_HOST": "0.0.0.0"})

    def test_count_journal_does_not_move_with_release(self) -> None:
        live = self.env("live")
        self.assertEqual(
            live.count_path,
            replace(live, release=live.release.with_name("cd" * 32)).count_path,
        )
        self.assertNotEqual(live.count_path, self.env("staging").count_path)
        self.assertFalse(live.count_path.exists())

    def test_relative_deployment_paths_cannot_change_meaning_in_child_cwd(self) -> None:
        with self.assertRaisesRegex(Refusal, "environment_path_conflict"):
            read_environment(
                dict(
                    EII_ENVIRONMENT="staging",
                    EII_RELEASE_DIR="staging/releases/" + "ab" * 32,
                    EII_STATE_DIR="staging/state",
                    EII_DATABASE_URL="postgres://eii_app"
                    + "@"
                    + "127.0.0.1:5432/INVENTED_staging",
                )
            )

    def test_late_ledger_and_count_aliases_cannot_redirect_scoped_writes(self) -> None:
        from operations.config import persistent_paths

        live, stage = self.env("live"), self.env("staging")
        live.state.mkdir(parents=True)
        stage.state.mkdir(parents=True)
        isolated((live, stage))
        ledger, count = persistent_paths(stage)
        self.assertEqual((ledger.parent, count.parent), (stage.state, stage.state))
        for name in ("local-ledger.sqlite", "photoreal-count.log"):
            target = live.state / name
            target.write_bytes(b"INVENTED-retained")
            alias = stage.state / name
            alias.symlink_to(target)
            with (
                self.subTest(name=name),
                self.assertRaisesRegex(Refusal, "cross_environment_write"),
            ):
                persistent_paths(stage)
            self.assertEqual(target.read_bytes(), b"INVENTED-retained")
            alias.unlink()
