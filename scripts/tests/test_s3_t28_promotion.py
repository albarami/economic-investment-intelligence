"""Candidate-bound evidence, write-ahead service and explicit reverse transitions."""

from __future__ import annotations

import copy
import hashlib
from typing import Any
from unittest.mock import patch

from s3_t28_support import APPLICATION, COMMIT, IDENTITY, WorkspaceCase

from operations.activation import activate, active_route, entries, operation_lock
from operations.common import Refusal, encoded, sha
from operations.config import Environment
from operations.evidence import CHECKS, ITEMS, operation


def request() -> dict[str, Any]:
    return dict(
        operation="initial_live_activation",
        environment="live",
        exposure="loopback",
        release_kind="public_only",
        code_version=COMMIT,
        release_id=IDENTITY,
        application_sha256=APPLICATION,
        previous_release_id=None,
        entry_port=8088,
        backend_port=18088,
        evidence={},
        gate_approval=None,
        actor="lead",
    )


class Promotion(WorkspaceCase):
    def test_real_fsync_failure_cannot_start_service(self) -> None:
        with (
            patch(
                "operations.activation.os.fsync",
                side_effect=OSError("INVENTED-sync-failure"),
            ),
            self.assertRaisesRegex(Refusal, "promotion_log_unwritable"),
        ):
            self.execute()
        self.assertNotIn("start", self.calls)
        self.assertFalse((self.state / "route.json").exists())

    def test_each_logged_result_semantics_after_rehash(self) -> None:
        self.execute()
        original = entries(self.state)[0]
        for item in sorted(ITEMS):
            for mode in ("missing", "failed"):
                entry = copy.deepcopy(original)
                if mode == "missing":
                    del entry["results"][item]
                else:
                    entry["results"][item]["result"] = "failed"
                entry["sha256"] = hashlib.sha256(
                    encoded(
                        {key: value for key, value in entry.items() if key != "sha256"}
                    )
                ).hexdigest()
                (self.state / "promotions.jsonl").write_bytes(encoded(entry) + b"\n")
                (self.state / "history.json").write_bytes(
                    encoded(dict(sequence=1, sha256=entry["sha256"]))
                )
                with (
                    self.subTest(item=item, mode=mode),
                    self.assertRaisesRegex(Refusal, "promotion_log_mismatch"),
                ):
                    entries(self.state)

    def test_cross_environment_scope_blocks_every_write_before_lock(self) -> None:
        scope = Environment(
            "staging",
            self.root / "staging/releases" / IDENTITY,
            self.root / "staging/state",
            8089,
            ("127.0.0.1", 5432, "INVENTED_staging"),
        )
        with self.assertRaisesRegex(Refusal, "cross_environment_write"):
            self.execute(scope=scope)
        self.assertEqual(self.calls, [])
        self.assertFalse(self.state.exists())

    def test_failed_readiness_stops_candidate_and_preserves_route(self) -> None:
        first = self.execute()
        self.raw.update(
            operation="promote",
            previous_release_id=IDENTITY,
            release_id="bb" * 32,
            backend_port=18089,
        )
        self.bind()

        def fail(*args: Any) -> None:
            raise Refusal("startup_not_ready")

        with self.assertRaisesRegex(Refusal, "startup_not_ready"):
            self.execute(ready=fail)
        self.assertEqual(active_route(self.state), first)
        self.assertEqual(self.calls[-1], "stop")
        self.assertNotIn("retire", self.calls)

    def setUp(self) -> None:
        super().setUp()
        self.state = self.root / "state"
        self.calls: list[str] = []
        self.raw = request()
        self.reports: dict[str, dict[str, Any]] = {
            "merged": dict(
                branch="main",
                main_commit=COMMIT,
                ancestors=[COMMIT],
                checks={
                    name: dict(
                        commit=COMMIT, conclusion="success", run_id="INVENTED-run"
                    )
                    for name in CHECKS
                },
            ),
            "review": dict(
                verdict="APPROVED",
                builder="OpenAI",
                reviewer="Anthropic",
                findings_report="INVENTED-reviewed-record",
            ),
            "whole_test": dict(
                exit_code=0,
                passed=12,
                failed=0,
                seed="INVENTED-seed",
                command="./eii test",
            ),
            "staging": dict(
                environment="staging", port=8089, installation_verified=APPLICATION
            ),
            "retention": dict(
                retained_release_id=IDENTITY, installation="INVENTED-retained"
            ),
            "features": dict(
                enabled=["INVENTED-finished"],
                completed=["INVENTED-finished"],
                review_record="INVENTED-feature-review",
            ),
            "gates": dict(
                required=["S3-T02"],
                results={"S3-T02": dict(verdict="APPROVED", commit=COMMIT)},
            ),
        }
        self.bind()

    def bind(self) -> None:
        for item, report in self.reports.items():
            for key in ("code_version", "release_id", "application_sha256"):
                report[key] = self.raw[key]
            path = self.root / (item + ".json")
            path.write_bytes(encoded(report))
            self.raw["evidence"][item] = {"file": path.name, "sha256": sha(path)}

    def execute(self, **overrides: Any) -> dict[str, Any]:
        def start(raw: Any, entry: Any) -> tuple[object, bool]:
            self.assertEqual(entries(self.state)[-1]["sha256"], entry["sha256"])
            self.calls.append("start")
            return object(), True

        options: dict[str, Any] = dict(
            scope=Environment(
                self.raw["environment"],
                self.state.parent / "releases" / self.raw["release_id"],
                self.state,
                self.raw["entry_port"],
                ("127.0.0.1", 5432, "INVENTED_" + self.raw["environment"]),
            ),
            evidence_root=self.root,
            features=["INVENTED-finished"],
            verify_installation=lambda _: self.calls.append("verify"),
            staging_probe=lambda _: self.calls.append("probe"),
            retain=lambda _: self.calls.append("retain"),
            start=start,
            ready=lambda *_: self.calls.append("ready"),
            stop=lambda _: self.calls.append("stop"),
            retire=lambda _: self.calls.append("retire"),
        )
        options.update(overrides)
        return activate(self.state, self.raw, **options)

    def test_initial_promote_and_rollback_restore_identity_and_port(self) -> None:
        first = self.execute()
        self.assertEqual(
            (first["release_id"], first["backend_port"]), (IDENTITY, 18088)
        )
        self.assertIsNone(first["predecessor"])
        self.raw.update(
            operation="promote",
            previous_release_id=IDENTITY,
            release_id="bb" * 32,
            backend_port=18089,
        )
        self.bind()
        second = self.execute()
        self.assertEqual(second["predecessor"]["release_id"], IDENTITY)
        self.assertEqual(
            (second["release_id"], second["backend_port"]), ("bb" * 32, 18089)
        )
        self.raw.update(
            operation="rollback",
            previous_release_id="bb" * 32,
            release_id=IDENTITY,
            backend_port=18088,
        )
        self.reports["retention"]["retained_release_id"] = "bb" * 32
        self.bind()
        back = self.execute()
        self.assertEqual((back["release_id"], back["backend_port"]), (IDENTITY, 18088))
        self.assertEqual(len(entries(self.state)), 3)
        self.assertEqual(self.calls.count("retire"), 2)

    def test_each_missing_failed_stale_or_boolean_evidence(self) -> None:
        for item in sorted(ITEMS):
            original = copy.deepcopy(self.reports[item])
            ref = copy.deepcopy(self.raw["evidence"][item])
            for mode in ("missing", "failed", "stale", "boolean"):
                self.reports[item] = copy.deepcopy(original)
                self.bind()
                if mode == "missing":
                    (self.root / ref["file"]).unlink()
                elif mode == "stale":
                    self.reports[item]["release_id"] = "aa" * 32
                elif mode == "boolean":
                    self.reports[item] = {
                        key: self.raw[key]
                        for key in ("code_version", "release_id", "application_sha256")
                    }
                    self.reports[item]["green"] = True
                else:
                    failed = dict(
                        merged="checks",
                        review="verdict",
                        whole_test="exit_code",
                        staging="installation_verified",
                        retention="retained_release_id",
                        features="completed",
                        gates="results",
                    )[item]
                    self.reports[item][failed] = None
                if mode != "missing":
                    path = self.root / ref["file"]
                    path.write_bytes(encoded(self.reports[item]))
                    self.raw["evidence"][item]["sha256"] = sha(path)
                reason = (
                    "gate_evidence_required"
                    if item == "gates"
                    else "promotion_evidence_" + item
                )
                with (
                    self.subTest(item=item, mode=mode),
                    self.assertRaisesRegex(Refusal, reason),
                ):
                    self.execute()
                self.assertNotIn("start", self.calls)
                self.assertFalse((self.state / "route.json").exists())
            self.reports[item] = original
            self.bind()

    def test_each_hosted_check_missing_or_failed(self) -> None:
        original = copy.deepcopy(self.reports["merged"]["checks"])
        for name in sorted(CHECKS):
            for mode in ("missing", "failed", "stale"):
                checks = copy.deepcopy(original)
                if mode == "missing":
                    del checks[name]
                else:
                    checks[name]["conclusion" if mode == "failed" else "commit"] = (
                        "failure" if mode == "failed" else "ab" * 20
                    )
                self.reports["merged"]["checks"] = checks
                self.bind()
                with (
                    self.subTest(name=name, mode=mode),
                    self.assertRaisesRegex(Refusal, "promotion_evidence_merged"),
                ):
                    self.execute()
        self.assertNotIn("start", self.calls)

    def test_unmerged_same_maker_unfinished_each_refuses(self) -> None:
        for index, (item, key, value) in enumerate(
            (
                ("merged", "ancestors", []),
                ("review", "reviewer", "OpenAI"),
                ("review", "reviewer", " openai "),
                ("review", "builder", ""),
                ("review", "reviewer", " "),
                ("features", "enabled", ["INVENTED-unfinished"]),
            )
        ):
            self.state = self.root / ("case-" + str(index)) / "state"
            original = copy.deepcopy(self.reports[item])
            self.reports[item][key] = value
            self.bind()
            with (
                self.subTest(item=item),
                self.assertRaisesRegex(Refusal, "promotion_evidence_" + item),
            ):
                self.execute()
            self.reports[item] = original
            self.bind()

    def test_bootstrap_reuse_and_first_rollback(self) -> None:
        self.execute()
        with self.assertRaisesRegex(Refusal, "bootstrap_reused"):
            self.execute()
        self.raw.update(operation="rollback", previous_release_id=IDENTITY)
        with self.assertRaisesRegex(Refusal, "no_previous_release_for_rollback"):
            self.execute()
        active = active_route(self.state)
        assert active is not None
        self.assertEqual(active["release_id"], IDENTITY)

    def test_missing_or_truncated_history_never_bootstraps(self) -> None:
        self.execute()
        path = self.state / "promotions.jsonl"
        content = path.read_bytes()
        for mode in ("missing", "empty", "truncated"):
            path.write_bytes(content)
            if mode == "missing":
                path.unlink()
            else:
                path.write_bytes(b"" if mode == "empty" else content[:-1])
            with (
                self.subTest(mode=mode),
                self.assertRaisesRegex(Refusal, "promotion_log_mismatch"),
            ):
                self.execute()

    def test_log_failure_precedes_service(self) -> None:
        with (
            patch(
                "operations.activation.append_authorisation",
                side_effect=Refusal("promotion_log_unwritable"),
            ),
            self.assertRaisesRegex(Refusal, "promotion_log_unwritable"),
        ):
            self.execute()
        self.assertNotIn("start", self.calls)

    def test_lock_serializes_valid_requests(self) -> None:
        with (
            operation_lock(self.state),
            self.assertRaisesRegex(Refusal, "operation_in_progress"),
        ):
            self.execute()

    def test_explicit_restart_can_resume_a_durable_first_authorisation(self) -> None:
        def crash(point: str) -> None:
            if point == "after_authorisation":
                raise RuntimeError("INVENTED-crash")

        with self.assertRaisesRegex(RuntimeError, "INVENTED-crash"):
            self.execute(boundary=crash)
        self.assertIsNone(active_route(self.state))
        self.raw.update(operation="restart", previous_release_id=IDENTITY)
        route = self.execute()
        self.assertEqual(
            (route["release_id"], route["backend_port"]), (IDENTITY, 18088)
        )
        self.assertIsNone(route["predecessor"])

    def test_operator_cannot_promote(self) -> None:
        self.raw["actor"] = "operator"
        with self.assertRaisesRegex(Refusal, "activation_lead_required"):
            self.execute()
        self.assertFalse(self.state.exists())

    def test_crash_boundaries_preserve_durable_authorisation(self) -> None:
        def crash(boundary: str) -> None:
            if boundary == self.crash_at:
                raise RuntimeError("INVENTED-crash")

        for point in ("before_authorisation", "after_authorisation", "after_switch"):
            self.state = self.root / point
            self.crash_at = point
            with (
                self.subTest(point=point),
                self.assertRaisesRegex(RuntimeError, "INVENTED-crash"),
            ):
                self.execute(boundary=crash)
            current = active_route(self.state)
            if point == "after_switch":
                self.assertIsNotNone(current)
                assert current is not None
                self.assertEqual(
                    current["authorization"], entries(self.state)[-1]["sha256"]
                )
            else:
                self.assertIsNone(current)

    def test_schema_and_port_target(self) -> None:
        for key, value in (
            ("extra", True),
            ("operation", "invented"),
            ("exposure", "internet"),
            ("code_version", "short"),
            ("release_id", 1),
            ("entry_port", True),
            ("operation", {}),
            ("evidence", {"INVENTED-unknown": {}}),
            ("gate_approval", True),
            ("gate_approval", {"file": "INVENTED", "sha256": []}),
        ):
            changed = dict(self.raw, **{key: value})
            with (
                self.subTest(key=key),
                self.assertRaisesRegex(Refusal, "operation_schema_invalid"),
            ):
                operation(changed)
        self.raw["backend_port"] = 8088
        with self.assertRaisesRegex(Refusal, "activation_target_mismatch"):
            self.execute()
