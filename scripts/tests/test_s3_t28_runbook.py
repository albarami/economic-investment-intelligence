"""Real dispatcher with invented IO interfaces and a complete local transcript."""

from __future__ import annotations

import contextlib
import copy
import io
import json
from collections.abc import Callable
from contextlib import AbstractContextManager
from pathlib import Path
from typing import Any
from unittest.mock import patch

import test_s3_t28_promotion as promotion_fixture
from s3_t28_support import COMMIT, IDENTITY, WorkspaceCase
from test_s3_t28_install import archive_fixture

import preflight
from commands.main import main
from operations.activation import active_route
from operations.common import Refusal, atomic_json, encoded, sha
from operations.runbook import STEPS, verify_transcript


class Runbook(WorkspaceCase):
    command_scope: Callable[[str], AbstractContextManager[None]]
    operation_hook: Callable[[str], None]

    def test_each_missing_step_and_falsified_result(self) -> None:
        transcript: list[dict[str, Any]] = []
        for step, command, environment in STEPS:
            candidate = step.startswith("candidate_") or step == "promotion"
            identity = "bb" * 32 if candidate else IDENTITY
            result = dict(
                release_id=identity,
                release_sha256=("cc" if candidate else "aa") * 32,
                application_sha256=None if environment == "custodian" else "ef" * 32,
                backend_port=None
                if environment == "custodian"
                else 8089
                if environment == "staging"
                else 18089
                if candidate
                else 18088,
            )
            transcript.append(
                dict(
                    step=step,
                    command=command,
                    environment=environment,
                    exit_code=0,
                    verified_result=result,
                )
            )
        verify_transcript(transcript)
        for index, (step, _, _) in enumerate(STEPS):
            with (
                self.subTest(step=step),
                self.assertRaisesRegex(Refusal, "runbook_step_missing"),
            ):
                verify_transcript(transcript[:index] + transcript[index + 1 :])
            changed = [dict(row) for row in transcript]
            changed[index]["exit_code"] = 4
            with (
                self.subTest(step=step),
                self.assertRaisesRegex(Refusal, "runbook_result_invalid"),
            ):
                verify_transcript(changed)
            changed = copy.deepcopy(transcript)
            changed[index]["verified_result"]["release_sha256"] = "dd" * 32
            with (
                self.subTest(step=step, plant="wrong-returned-checksum"),
                self.assertRaisesRegex(Refusal, "runbook_result_invalid"),
            ):
                verify_transcript(changed)

    def test_dispatch_build_stage_promote_rollback_handover_and_down(self) -> None:
        from types import SimpleNamespace

        from eii_product.api.health import Health
        from operations.install import file_inventory

        archive = archive_fixture(self.root)
        application_hash = sha(archive)
        candidate = "bb" * 32
        building = [IDENTITY]
        builds: list[str] = []
        events: list[tuple[str, str, int]] = []
        transcript: list[dict[str, Any]] = []
        reports = promotion_fixture.Promotion()
        reports.setUp()
        self.addCleanup(reports.doCleanups)

        def sandbox(profile: str, layout: Any, argv: Any) -> Any:
            self.assertEqual(profile, "build-release")
            identity = building[0]
            (layout.staging / "manifest.json").write_bytes(
                encoded(
                    dict(
                        release_kind="public_only",
                        release_id=identity,
                        code_version=COMMIT,
                        tables=[dict(file="table.parquet")],
                    )
                )
            )
            (layout.staging / "table.parquet").write_bytes(
                ("INVENTED-" + identity).encode()
            )
            builds.append(identity)
            return SimpleNamespace(returncode=0)

        def checked(folder: Path) -> Any:
            return SimpleNamespace(
                document=json.loads((folder / "manifest.json").read_bytes()),
                folder=folder,
            )

        def loader(folder: Path, **kwargs: Any) -> int:
            (folder / "release.duckdb").write_bytes(b"INVENTED-reader")
            (folder / "load_receipt.json").write_bytes(
                encoded(dict(state="complete", release_id=folder.name))
            )
            events.append(("load", folder.parent.parent.name, 0))
            return 0

        def launch(
            application: Path, path: Path, argv: Any, environ: Any, **values: Any
        ) -> dict[str, Any]:
            record = dict(pid=17, start_ticks="123", cmdline_sha256="ab" * 32, **values)
            atomic_json(path, record)
            events.append(("start", values["environment"], values["port"]))
            return record

        def get(port: int, path: str, timeout: float = 4.0) -> tuple[int, bytes]:
            home = self.root / ("staging" if port == 8089 else "live")
            if port == 8088:
                route = active_route(home / "state")
                assert route is not None
                identity = route["release_id"]
            else:
                identity = json.loads(
                    (home / "state" / ("process-" + str(port) + ".json")).read_bytes()
                )["release_id"]
            if path == "/":
                return 200, b"INVENTED-page"
            if path == "/health":
                return 200, encoded(
                    Health(
                        status="ok",
                        store="postgres",
                        postgres="up",
                        release_id=identity,
                        release_hash=identity,
                        parity="identical",
                        ledger="local",
                        local_ledger_rows=0,
                        model="template",
                        traffic="simulated",
                        tiles="ok",
                        fonts="ok",
                        replays="ok",
                    ).model_dump()
                )
            return 200, encoded(
                dict(
                    status="OK", release_id=identity, facts=[dict(release_id=identity)]
                )
            )

        def owned(record: Any, environment: str) -> None:
            self.assertEqual(record["environment"], environment)

        def settings(
            environment: str,
            identity: str,
            op: str,
            predecessor: str | None,
            backend: int,
        ) -> dict[str, str]:
            home = self.root / environment
            folder = home / "evidence"
            folder.mkdir(parents=True, exist_ok=True)
            raw = promotion_fixture.request()
            raw.update(
                environment=environment,
                operation=op,
                release_id=identity,
                previous_release_id=predecessor,
                application_sha256=application_hash,
                backend_port=backend,
                entry_port=8089 if environment == "staging" else 8088,
            )
            if environment == "live":
                for item, content in reports.reports.items():
                    content.update(
                        code_version=COMMIT,
                        release_id=identity,
                        application_sha256=application_hash,
                    )
                    if item == "staging":
                        content["installation_verified"] = application_hash
                    if item == "retention":
                        content["retained_release_id"] = predecessor or identity
                    path = folder / (item + ".json")
                    path.write_bytes(encoded(content))
                    raw["evidence"][item] = dict(
                        file="evidence/" + path.name, sha256=sha(path)
                    )
            if op == "expose_public":
                raw["exposure"] = "public_entry"
                path = folder / "gate.json"
                path.write_bytes(
                    encoded(
                        dict(
                            gate="S3",
                            verdict="APPROVED",
                            release_id=identity,
                            application_sha256=application_hash,
                            code_version=COMMIT,
                        )
                    )
                )
                raw["gate_approval"] = dict(file="evidence/gate.json", sha256=sha(path))
            request_path = folder / "request.json"
            request_path.write_bytes(encoded(raw))
            return dict(
                EII_ENVIRONMENT=environment,
                EII_STATE_DIR=str(home / "state"),
                EII_RELEASE_DIR=str(home / "releases" / identity),
                EII_DATABASE_URL="postgresql://eii_app"
                + "@"
                + "127.0.0.1:5432/INVENTED_"
                + environment,
                EII_OPERATION_RECORD=str(request_path),
            )

        def run(
            step: str,
            command: str,
            environment: str,
            env: dict[str, str],
            identity: str,
        ) -> None:
            settings_for_command = env
            if command == "load-release":
                settings_for_command = dict(
                    env,
                    EII_SOURCE_RELEASE_DIR=str(self.root / "data/releases" / identity),
                    EII_APPLICATION_ARCHIVE=str(archive),
                )
            before = (
                file_inventory(self.root / environment)
                if command == "preflight"
                else None
            )
            with (
                getattr(self, "command_scope", lambda _: contextlib.nullcontext())(
                    command
                ),
                contextlib.redirect_stdout(io.StringIO()),
                contextlib.redirect_stderr(io.StringIO()) as errors,
            ):
                code = main([command], settings_for_command, self.root)
            # The syscall-tripwire companion can plant an attempt at an exact
            # command boundary without replacing production dispatch itself.
            getattr(self, "operation_hook", lambda _: None)(step)
            self.assertEqual(code, 0, (step, errors.getvalue()))
            if command == "preflight":
                self.assertEqual(file_inventory(self.root / environment), before)
            if command == "up":
                route = active_route(self.root / environment / "state")
                assert route is not None
                self.assertEqual(route["release_id"], identity)
                response = get(
                    8089 if environment == "staging" else 8088, "/api/release"
                )
                self.assertEqual(json.loads(response[1])["release_id"], identity)
            export = (
                self.root / "data/releases" / identity
                if environment == "custodian"
                else self.root / environment / "releases" / identity
            )
            manifest = json.loads((export / "manifest.json").read_bytes())
            if environment == "custodian":
                backend = None
                app_hash = None
            else:
                requested = json.loads(Path(env["EII_OPERATION_RECORD"]).read_bytes())
                backend = requested["backend_port"]
                app_hash = requested["application_sha256"]
            transcript.append(
                dict(
                    step=step,
                    command=command,
                    environment=environment,
                    exit_code=code,
                    verified_result=dict(
                        release_id=manifest["release_id"],
                        release_sha256=sha(export / "manifest.json"),
                        application_sha256=app_hash,
                        backend_port=backend,
                    ),
                )
            )

        with contextlib.ExitStack() as stack:
            for target, replacement in (
                ("operations.install.verify_runtime", lambda _: None),
                ("eii_product.store.release_check.check_release", checked),
                ("eii_product.store.loader.run_load", loader),
                ("sandbox_launch.run_in_sandbox", sandbox),
                ("operations.deploy.check_stores", lambda *a, **k: None),
                (
                    "preflight.run_preflight",
                    lambda *a, **k: preflight.Report((), "postgres", 0),
                ),
                ("operations.process.launch", launch),
                ("operations.process.require_owned", owned),
                (
                    "operations.process.terminate",
                    lambda record, env: events.append(("stop", env, record["port"])),
                ),
                ("operations.deploy.get", get),
            ):
                stack.enter_context(patch(target, side_effect=replacement))
            run("build", "build-release", "custodian", {}, IDENTITY)
            stage = settings("staging", IDENTITY, "start_staging", None, 8089)
            for step, command in (
                ("stage_load", "load-release"),
                ("stage_probe", "preflight"),
                ("stage_start", "up"),
            ):
                run(step, command, "staging", stage, IDENTITY)
            live = settings("live", IDENTITY, "initial_live_activation", None, 18088)
            for step, command in (
                ("live_load", "load-release"),
                ("live_probe", "preflight"),
                ("live_start", "up"),
            ):
                run(step, command, "live", live, IDENTITY)
            building[0] = candidate
            run("candidate_build", "build-release", "custodian", {}, candidate)
            stage = settings("staging", candidate, "start_staging", None, 8089)
            for step, command in (
                ("candidate_stage_load", "load-release"),
                ("candidate_stage_probe", "preflight"),
                ("candidate_stage_start", "up"),
            ):
                run(step, command, "staging", stage, candidate)
            live = settings("live", candidate, "promote", IDENTITY, 18089)
            for step, command in (
                ("candidate_live_load", "load-release"),
                ("candidate_live_probe", "preflight"),
                ("promotion", "up"),
            ):
                run(step, command, "live", live, candidate)
            active = active_route(self.root / "live/state")
            assert active is not None
            self.assertEqual(active["backend_port"], 18089)
            stage = settings("staging", IDENTITY, "start_staging", None, 8089)
            run("rollback_stage_probe", "preflight", "staging", stage, IDENTITY)
            run("rollback_stage_start", "up", "staging", stage, IDENTITY)
            live = settings("live", IDENTITY, "rollback", candidate, 18088)
            run("rollback_live_probe", "preflight", "live", live, IDENTITY)
            run("rollback", "up", "live", live, IDENTITY)
            active = active_route(self.root / "live/state")
            assert active is not None
            self.assertEqual(active["backend_port"], 18088)
            live = settings("live", IDENTITY, "expose_public", IDENTITY, 18088)
            run("handover_probe", "preflight", "live", live, IDENTITY)
            # S3-T20: the real handover runs on the patched process seams.
            exposed = dict(live, EII_REMOTE_HOST="entry.s3-t20.invalid")
            run("handover", "up", "live", exposed, IDENTITY)
            preserved = {
                environment: file_inventory(self.root / environment / "releases")
                for environment in ("staging", "live")
            }
            run("stage_stop", "down", "staging", stage, IDENTITY)
            run("live_stop", "down", "live", live, IDENTITY)
            for environment, inventory in preserved.items():
                self.assertEqual(
                    file_inventory(self.root / environment / "releases"), inventory
                )
        verify_transcript(transcript)
        self.assertEqual(builds, [IDENTITY, candidate])
        entry_events = [
            kind
            for kind, environment, port in events
            if (environment, port) == ("live", 8088) and kind in {"start", "stop"}
        ]
        unstopped = [
            entry_events[: index + 1].count("start")
            - entry_events[: index + 1].count("stop")
            for index in range(len(entry_events))
        ]
        self.assertLessEqual(max(unstopped), 1, "second exposed entry admitted")
        # Initial start; the handover's stop and start; the final down.
        self.assertEqual(entry_events, ["start", "stop", "start", "stop"])
