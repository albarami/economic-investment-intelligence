"""Plants for review N1/N3: interrupted switching and reused process IDs."""

import errno
import os
import signal
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock, patch

import test_s3_t28_promotion as promotion
from s3_t28_support import APPLICATION, IDENTITY, WorkspaceCase

from operations import activation, process
from operations.common import Refusal, atomic_json, read_json


class ConfirmationFixes(WorkspaceCase):
    def test_p1_short_authorisation_write_preserves_previous_route(self) -> None:
        self.check_short_append("promotions.jsonl")

    def test_p1_short_outcome_write_preserves_previous_route(self) -> None:
        self.check_short_append("outcomes.jsonl")

    def test_p1_partial_authorisation_write_is_refused_and_restored(self) -> None:
        self.check_short_append("promotions.jsonl", raises=False)

    def test_p1_partial_outcome_write_is_refused_and_restored(self) -> None:
        self.check_short_append("outcomes.jsonl", raises=False)

    def test_p1_authorisation_sync_failure_restores_previous_log(self) -> None:
        self.check_failed_sync("promotions.jsonl")

    def test_p1_outcome_sync_failure_restores_previous_log(self) -> None:
        self.check_failed_sync("outcomes.jsonl")

    def check_failed_sync(self, name: str) -> None:
        fixture, first = self.candidate()
        path = fixture.state / name
        before = path.read_bytes()
        fsync = os.fsync
        failed = False

        def fail_sync(descriptor: int) -> None:
            nonlocal failed
            if not failed and os.fstat(descriptor).st_ino == path.stat().st_ino:
                failed = True
                raise OSError(errno.EIO, "INVENTED-log-sync-failed")
            fsync(descriptor)

        with (
            patch("operations.activation.os.fsync", side_effect=fail_sync),
            self.assertRaisesRegex(Refusal, "promotion_log_unwritable"),
        ):
            fixture.execute()
        self.assertTrue(failed)
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(activation.active_route(fixture.state), first)
        following = fixture.execute()
        self.assertEqual(activation.active_route(fixture.state), following)

    def check_short_append(self, name: str, *, raises: bool = True) -> None:
        fixture, first = self.candidate()
        path = fixture.state / name
        before = path.read_bytes()
        route_before = (fixture.state / "route.json").read_bytes()
        original_open = Path.open

        def open_stream(target: Path, *args: Any, **kwargs: Any) -> Any:
            stream = original_open(target, *args, **kwargs)
            if target == path and args and args[0] == "ab":
                write = stream.write

                def short_write(payload: bytes) -> int:
                    count: int = write(payload[: len(payload) // 2])
                    stream.flush()
                    if raises:
                        raise OSError(errno.ENOSPC, "INVENTED-short-log-write")
                    return count

                stream.write = short_write
            return stream

        with (
            patch("pathlib.Path.open", new=open_stream),
            self.assertRaisesRegex(Refusal, "promotion_log_unwritable"),
        ):
            fixture.execute()
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual((fixture.state / "route.json").read_bytes(), route_before)
        self.assertEqual(activation.active_route(fixture.state), first)
        following = fixture.execute()
        self.assertEqual(activation.active_route(fixture.state), following)
        self.assertEqual(following["predecessor"], first)

    def candidate(self) -> tuple[promotion.Promotion, dict[str, object]]:
        fixture = promotion.Promotion()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        first = fixture.execute()
        fixture.raw.update(
            operation="promote",
            previous_release_id=IDENTITY,
            release_id="bb" * 32,
            backend_port=18089,
        )
        fixture.bind()
        return fixture, first

    def test_n1_outcome_failure_preserves_route_stops_child_and_allows_promote(
        self,
    ) -> None:
        fixture, first = self.candidate()
        before = (fixture.state / "route.json").read_bytes()
        child = object()
        stop = Mock()
        with (
            patch(
                "operations.activation.append_outcome",
                side_effect=Refusal("promotion_log_unwritable"),
            ),
            self.assertRaisesRegex(Refusal, "promotion_log_unwritable"),
        ):
            fixture.execute(start=Mock(return_value=(child, True)), stop=stop)
        self.assertEqual(activation.active_route(fixture.state), first)
        self.assertEqual((fixture.state / "route.json").read_bytes(), before)
        stop.assert_called_once_with(child)
        self.assertNotIn("retire", fixture.calls)
        following = fixture.execute()
        self.assertEqual(activation.active_route(fixture.state), following)
        self.assertEqual(following["predecessor"], first)
        self.assertEqual(following["release_id"], "bb" * 32)

    def test_n1_crash_after_outcome_leaves_previous_route_serving(self) -> None:
        fixture, first = self.candidate()
        before = (fixture.state / "route.json").read_bytes()
        stop = Mock()
        child = object()
        visited = []

        def crash(point: str) -> None:
            if point == "after_outcome":
                visited.append(point)
                # A complete new outcome is durable while the old route serves.
                self.assertEqual(activation.active_route(fixture.state), first)
                self.assertIn(
                    ("bb" * 32).encode(),
                    (fixture.state / "outcomes.jsonl").read_bytes(),
                )
                raise RuntimeError("INVENTED-after-outcome-crash")

        with self.assertRaisesRegex(RuntimeError, "INVENTED-after-outcome-crash"):
            fixture.execute(
                start=Mock(return_value=(child, True)), stop=stop, boundary=crash
            )
        self.assertEqual(visited, ["after_outcome"])
        self.assertEqual(activation.active_route(fixture.state), first)
        self.assertEqual((fixture.state / "route.json").read_bytes(), before)
        stop.assert_called_once_with(child)
        self.assertNotIn("retire", fixture.calls)

    def test_n3_reused_pid_is_retired_reported_and_never_signalled(self) -> None:
        self.check_foreign_record(reused=True)

    def test_n3_matching_ticks_wrong_nonce_is_refused_without_retiring(self) -> None:
        self.check_foreign_record(reused=False)

    def test_n6_other_user_pid_is_retired_reported_and_never_signalled(self) -> None:
        self.check_foreign_record(reused=False, other_user=True)

    def test_n6_unreadable_pid_owner_is_refused_without_retiring(self) -> None:
        self.check_foreign_record(reused=False, stat_failure=True)

    def check_foreign_record(
        self, *, reused: bool, other_user: bool = False, stat_failure: bool = False
    ) -> None:
        state = self.root / "live/state"
        state.mkdir(parents=True)
        foreign = subprocess.Popen(
            (
                sys.executable,
                "-I",
                "-B",
                "-c",
                "import signal; signal.pause()",
                "--nonce",
                "INVENTED-actual",
                "--environment",
                "live",
                "--port",
                "18088",
            ),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            ticks, command = process.identity(foreign.pid)
            record = dict(
                pid=foreign.pid,
                start_ticks="ticks:INVENTED-stale" if reused else ticks,
                cmdline_sha256=command,
                boot_id=process.boot_id(),
                nonce="INVENTED-wrong-nonce",
                environment="live",
                port=18088,
                release_id=IDENTITY,
                application_sha256=APPLICATION,
            )
            path = process.process_record(state, 18088)
            atomic_json(path, record)
            before = path.read_bytes()
            original_stat = Path.stat
            proc_path = Path(f"/proc/{foreign.pid}")

            def stat(target: Path, *args: Any, **kwargs: Any) -> Any:
                if stat_failure and target == proc_path:
                    raise OSError(errno.EACCES, "INVENTED-owner-unreadable")
                result = original_stat(target, *args, **kwargs)
                if other_user and target == proc_path:
                    return SimpleNamespace(st_uid=result.st_uid + 1)
                return result

            with (
                patch("pathlib.Path.stat", new=stat),
                patch(
                    "operations.process.signal.pidfd_send_signal",
                    wraps=signal.pidfd_send_signal,
                ) as send,
            ):
                with self.assertRaisesRegex(Refusal, "process_identity_mismatch"):
                    process.down(state, "live")
                send.assert_not_called()
                self.assertIsNone(foreign.poll())
                if reused or other_user:
                    self.assertEqual(
                        read_json(path, "process_identity_mismatch"),
                        dict(record, stopped=True),
                    )
                    # Recovery is a normal next down, without another refusal.
                    process.down(state, "live")
                    send.assert_not_called()
                else:
                    self.assertEqual(path.read_bytes(), before)
                    with self.assertRaisesRegex(Refusal, "process_identity_mismatch"):
                        process.down(state, "live")
                    self.assertEqual(path.read_bytes(), before)
                    send.assert_not_called()
        finally:
            foreign.terminate()
            foreign.wait(timeout=process.READY_SECONDS)
