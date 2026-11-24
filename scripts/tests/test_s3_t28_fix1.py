"""Planted review regressions on real activation wiring and owned state."""

import copy
import os
import signal
import socketserver
import subprocess
import sys
from contextlib import ExitStack
from typing import Any
from unittest.mock import Mock, patch

import test_s3_t28_promotion as promotion
from s3_t28_support import APPLICATION, COMMIT, IDENTITY, WorkspaceCase

from operations import activation, deploy, entry, evidence, process
from operations.common import Refusal, atomic_json, read_json, sha
from operations.config import Environment


class ReviewFixes(WorkspaceCase):
    def test_f1_native_entry_binds_without_name_service_contact(self) -> None:
        env = Environment(
            "live",
            self.root / "live/releases" / IDENTITY,
            self.root / "live/state",
            8088,
            ("127.0.0.1", 5432, "INVENTED_live"),
        )
        route = dict(environment="live", entry_port=8088, exposure="loopback")
        native_bind = socketserver.TCPServer.server_bind

        def bind(server: socketserver.TCPServer) -> None:
            self.assertEqual(server.server_address, ("127.0.0.1", 8088))
            # The production fixed port may belong to a foreign service. This
            # IO seam allocates an owned port without replacing name handling.
            server.server_address = ("127.0.0.1", 0)
            self.addCleanup(server.server_close)
            native_bind(server)

        with (
            patch("operations.config.read_environment", return_value=env),
            patch("operations.entry.active_route", return_value=route),
            patch("operations.entry.sys.argv", ["INVENTED-entry"]),
            patch("operations.entry.ThreadingHTTPServer.serve_forever"),
            patch("socketserver.TCPServer.server_bind", bind),
            patch(
                "socket.getfqdn", side_effect=AssertionError("name service contacted")
            ) as lookup,
        ):
            self.assertEqual(entry.main(), 0)
            lookup.assert_not_called()

    def fixture(self) -> promotion.Promotion:
        fixture = promotion.Promotion()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        return fixture

    def test_f3_degraded_reused_backend_preserves_process_and_route(self) -> None:
        for mode in ("restart", "expose_public", "start_staging"):
            with self.subTest(mode=mode):
                fixture = self.fixture()
                if mode == "start_staging":
                    fixture.raw.update(
                        operation=mode,
                        environment="staging",
                        entry_port=8089,
                        backend_port=8089,
                    )
                route = fixture.execute()
                fixture.raw.update(operation=mode, previous_release_id=IDENTITY)
                if mode == "expose_public":
                    fixture.raw["exposure"] = "public_entry"
                    gate = {
                        key: fixture.raw[key]
                        for key in (
                            "code_version",
                            "release_id",
                            "application_sha256",
                        )
                    }
                    gate.update(gate="S3", verdict="APPROVED")
                    path = fixture.root / "gate.json"
                    atomic_json(path, gate)
                    fixture.raw["gate_approval"] = dict(
                        file=path.name, sha256=sha(path)
                    )
                fixture.bind()
                env = Environment(
                    fixture.raw["environment"],
                    fixture.root / "releases" / IDENTITY,
                    fixture.state,
                    fixture.raw["entry_port"],
                    ("127.0.0.1", 5432, "INVENTED_" + fixture.raw["environment"]),
                )
                child = dict(
                    pid=17, release_id=IDENTITY, application_sha256=APPLICATION
                )
                path = process.process_record(
                    fixture.state, fixture.raw["backend_port"]
                )
                atomic_json(path, child)
                before = path.read_bytes()
                with ExitStack() as stack:
                    for target, kwargs in (
                        ("read_environment", dict(return_value=env)),
                        ("verify_peers", {}),
                        ("request_for", dict(return_value=fixture.raw)),
                        (
                            "installed",
                            dict(
                                return_value=(
                                    fixture.root,
                                    dict(features=["INVENTED-finished"]),
                                )
                            ),
                        ),
                        ("check_stores", {}),
                        ("require_retained", {}),
                        ("staging_probe", {}),
                        ("process.require_owned", {}),
                        (
                            "process.wait_ready",
                            dict(side_effect=Refusal("startup_not_ready")),
                        ),
                    ):
                        stack.enter_context(
                            patch("operations.deploy." + target, **kwargs)
                        )
                    stop = stack.enter_context(
                        patch("operations.deploy.process.terminate")
                    )
                    launch = stack.enter_context(
                        patch("operations.deploy.process.launch")
                    )
                    with self.assertRaisesRegex(Refusal, "startup_not_ready"):
                        deploy.up({}, handover=lambda: None)
                    stop.assert_not_called()
                    launch.assert_not_called()
                self.assertEqual(path.read_bytes(), before)
                self.assertEqual(activation.active_route(fixture.state), route)

    def test_f4_foreign_record_does_not_prevent_owned_shutdown(self) -> None:
        state = self.root / "live/state"
        state.mkdir(parents=True)
        foreign = dict(pid=17, environment="live", nonce="INVENTED-foreign")
        owned = dict(pid=19, environment="live", nonce="INVENTED-owned")
        first, last = state / "process-18088.json", state / "process-8088.json"
        atomic_json(first, foreign)
        atomic_json(last, owned)
        stopped: list[dict[str, Any]] = []

        def terminate(record: dict[str, Any], environment: str) -> None:
            self.assertEqual(environment, "live")
            if record == foreign:
                raise Refusal("process_identity_mismatch")
            self.assertEqual(record, owned)
            stopped.append(record)

        with patch("operations.process.terminate", side_effect=terminate):
            with self.assertRaisesRegex(Refusal, "process_identity_mismatch"):
                process.down(state, "live")
        self.assertEqual(stopped, [owned])
        self.assertEqual(read_json(first, "process_identity_mismatch"), foreign)
        self.assertTrue(read_json(last, "process_identity_mismatch")["stopped"])

    def test_f4_previous_boot_is_retired_without_a_signal(self) -> None:
        state = self.root / "live/state"
        state.mkdir(parents=True)
        path = state / "process-18088.json"
        atomic_json(
            path, dict(pid=17, environment="live", boot_id="INVENTED-previous-boot")
        )
        with patch("operations.process.terminate") as terminate:
            process.down(state, "live")
            terminate.assert_not_called()
        self.assertTrue(read_json(path, "process_identity_mismatch")["stopped"])

    def test_f4_native_foreign_pid_and_owned_entry_shutdown(self) -> None:
        application = self.root / "application"
        script = application / "scripts/operations/entry.py"
        script.parent.mkdir(parents=True)
        script.write_text("import signal\nsignal.pause()\n")
        state = self.root / "live/state"
        state.mkdir(parents=True)
        record = process.launch(
            application,
            process.process_record(state, 8088),
            (
                sys.executable,
                "-I",
                "-B",
                "-S",
                "scripts/operations/entry.py",
                "--nonce",
                "INVENTED-entry",
                "--environment",
                "live",
                "--port",
                "8088",
            ),
            dict(EII_STATE_DIR=str(state), EII_ENVIRONMENT="live"),
            environment="live",
            nonce="INVENTED-entry",
            port=8088,
            release_id=IDENTITY,
            application_sha256=APPLICATION,
        )
        self.addCleanup(process.terminate, record, "live")
        self.assertEqual(record["boot_id"], process.boot_id())
        foreign = subprocess.Popen(
            (sys.executable, "-I", "-B", "-c", "import signal; signal.pause()"),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            ticks, command = process.identity(foreign.pid)
            atomic_json(
                process.process_record(state, 18088),
                dict(
                    pid=foreign.pid,
                    start_ticks=ticks,
                    cmdline_sha256=command,
                    environment="live",
                    nonce="INVENTED-foreign",
                    port=18088,
                    boot_id=process.boot_id(),
                ),
            )
            with patch(
                "operations.process.signal.pidfd_send_signal",
                wraps=signal.pidfd_send_signal,
            ) as send:
                with self.assertRaisesRegex(Refusal, "process_identity_mismatch"):
                    process.down(state, "live")
                self.assertEqual(send.call_count, 1)
            self.assertIsNone(foreign.poll())
            with self.assertRaises(ProcessLookupError):
                os.kill(record["pid"], 0)
            self.assertTrue(
                read_json(
                    process.process_record(state, 8088), "process_identity_mismatch"
                )["stopped"]
            )
        finally:
            foreign.terminate()
            foreign.wait(timeout=process.READY_SECONDS)

    def test_f5_database_identity_is_reserved_before_store_loading(self) -> None:
        env = Environment(
            "staging",
            self.root / "staging/releases" / IDENTITY,
            self.root / "staging/state",
            8089,
            ("127.0.0.1", 5432, "INVENTED_staging"),
        )

        def load(*args: Any, **kwargs: Any) -> int:
            path = env.state / "environment.json"
            self.assertTrue(
                path.is_file(), "environment reservation missing before load"
            )
            record = read_json(path, "environment_path_conflict")
            self.assertEqual(record["database"], list(env.database or ()))
            self.assertEqual(record["environment"], "staging")
            return 4  # Even a refused/interrupted load must keep the reservation.

        with (
            patch("operations.deploy.read_environment", return_value=env),
            patch(
                "operations.deploy.public_kind", return_value=dict(code_version=COMMIT)
            ),
            patch("eii_product.store.release_check.check_release"),
            patch(
                "operations.deploy.install_application",
                return_value=(self.root, APPLICATION),
            ),
            patch("operations.deploy.install_release"),
            patch("eii_product.store.loader.run_load", side_effect=load) as store_load,
        ):
            self.assertEqual(
                deploy.load(
                    self.root,
                    dict(
                        EII_SOURCE_RELEASE_DIR=str(self.root / "INVENTED-source"),
                        EII_APPLICATION_ARCHIVE=str(self.root / "INVENTED-archive"),
                    ),
                ),
                4,
            )
            store_load.assert_called_once()
        self.assertTrue((env.state / "environment.json").is_file())

    def test_f6_entry_step_holds_the_operation_lock(self) -> None:
        state = self.root / "live/state"
        state.mkdir(parents=True)
        env = Environment(
            "live",
            self.root / "live/releases" / IDENTITY,
            state,
            8088,
            ("127.0.0.1", 5432, "INVENTED_live"),
        )
        path = process.process_record(state, 8088)
        atomic_json(path, dict(stopped=True, nonce="INVENTED-retained-entry"))
        before = path.read_bytes()
        with ExitStack() as stack:
            for target, kwargs in (
                ("read_environment", dict(return_value=env)),
                ("verify_peers", {}),
                ("request_for", dict(return_value=promotion.request())),
                ("installed", dict(return_value=(self.root, dict(features=[])))),
                ("check_stores", {}),
                ("activate", dict(return_value=promotion.request())),
                ("process.wait_ready", {}),
            ):
                stack.enter_context(patch("operations.deploy." + target, **kwargs))
            launch = stack.enter_context(
                patch("operations.deploy.process.launch", return_value={})
            )
            with activation.operation_lock(state):
                with self.assertRaisesRegex(Refusal, "operation_in_progress"):
                    deploy.up({})
            launch.assert_not_called()
        self.assertEqual(path.read_bytes(), before)

    def test_f7_merged_ancestors_is_a_list_of_full_commits(self) -> None:
        for ancestors in (
            "0" + COMMIT,
            {COMMIT: True},
            [COMMIT, "short"],
            [COMMIT, 1],
            None,
        ):
            with self.subTest(ancestors=ancestors):
                fixture = self.fixture()
                fixture.reports["merged"]["ancestors"] = ancestors
                fixture.bind()
                with self.assertRaisesRegex(Refusal, "promotion_evidence_merged"):
                    evidence.verify_evidence(
                        fixture.root,
                        fixture.raw,
                        features=["INVENTED-finished"],
                        staging_probe=lambda _: None,
                    )

    def test_f8_unswitched_authorisation_cannot_become_the_route(self) -> None:
        fixture = self.fixture()
        first = fixture.execute()
        fixture.raw.update(
            operation="promote",
            previous_release_id=IDENTITY,
            release_id="bb" * 32,
            backend_port=18089,
        )
        fixture.bind()
        with self.assertRaisesRegex(Refusal, "startup_not_ready"):
            fixture.execute(ready=Mock(side_effect=Refusal("startup_not_ready")))
        entry = activation.entries(fixture.state)[-1]
        forged = dict(
            first,
            sequence=entry["sequence"],
            authorization=entry["sha256"],
            release_id="bb" * 32,
            backend_port=18089,
            predecessor=first,
        )
        atomic_json(fixture.state / "route.json", forged)
        with self.assertRaisesRegex(Refusal, "promotion_log_mismatch"):
            activation.active_route(fixture.state)

    def test_f8_outcome_binds_the_complete_predecessor(self) -> None:
        fixture = self.fixture()
        fixture.execute()
        fixture.raw.update(
            operation="promote",
            previous_release_id=IDENTITY,
            release_id="bb" * 32,
            backend_port=18089,
        )
        fixture.bind()
        route = fixture.execute()
        forged = copy.deepcopy(route)
        forged["predecessor"] = None
        atomic_json(fixture.state / "route.json", forged)
        with self.assertRaisesRegex(Refusal, "promotion_log_mismatch"):
            activation.active_route(fixture.state)
