"""S3-T20 boxes B7 and B8: `down --previous-boot` and the boot script.

Every command the script runs is a stub in an invented folder; the one real
part is the `down` logic, reached through the real dispatcher on invented
state. No database, product or tunnel is started.
"""

from __future__ import annotations

import contextlib
import io
import os
import subprocess
import sys
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

from s3_t28_support import APPLICATION, IDENTITY, ROOT, WorkspaceCase
from test_s3_t28_controls import without_call

from commands import down_cmd
from operations import deploy, process
from operations.common import Refusal, atomic_json, read_json

SCRIPT = ROOT / "scripts/boot/start-on-boot.sh"
STEPS = ("down --previous-boot", "db-up", "preflight", "up")
STATEMENTS = (
    "set -euo pipefail",
    "unset EII_REMOTE_HOST",
    'cd "$(dirname "$0")/../.."',
    *("./eii " + step for step in STEPS),
)
# The stub records its arguments and whether the remote host name reached it,
# fails one chosen step, and hands `down` to the real dispatcher when asked.
STUB = """#!/bin/sh
printf '%s|%s\\n' "$*" "${EII_REMOTE_HOST-unset}" >> "$BOOT_LOG"
if [ "$*" = "${BOOT_FAIL-}" ]; then
  exit "$BOOT_EXIT"
fi
if [ "$1" = down ] && [ -n "${BOOT_MAIN-}" ]; then
  exec "$BOOT_PYTHON" -I "$BOOT_MAIN" "$@"
fi
"""
PREVIOUS = "INVENTED-previous-boot"
MISMATCH = "process_identity_mismatch"


def statements(text: str) -> tuple[str, ...]:
    lines = text.splitlines()[1:]
    return tuple(line for line in lines if line and not line.startswith("#"))


def without_line(text: str, line: str) -> str:
    if text.count(line + "\n") != 1:
        raise AssertionError("a plant must remove exactly one line")
    return text.replace(line + "\n", "")


class BootCase(WorkspaceCase):
    def boot(self, text: str, **settings: str) -> tuple[int, list[str], str]:
        """Run one copy of the script beside the stub launcher."""
        script = self.root / "scripts/boot/start-on-boot.sh"
        script.parent.mkdir(parents=True, exist_ok=True)
        script.write_text(text)
        script.chmod(0o755)
        launcher = self.root / "eii"
        launcher.write_text(STUB)
        launcher.chmod(0o755)
        log = self.root / "calls.log"
        log.write_text("")
        elsewhere = self.root / "elsewhere"
        elsewhere.mkdir(exist_ok=True)
        done = subprocess.run(
            [str(script)],
            cwd=elsewhere,
            env=dict(
                PATH=os.environ["PATH"],
                BOOT_LOG=str(log),
                EII_REMOTE_HOST="invented-host.invalid",
                **settings,
            ),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=60,
            check=False,
        )
        return done.returncode, log.read_text().splitlines(), done.stdout

    def problems(self, text: str) -> list[str]:
        """The scenarios a copy of the script fails: order, stop and exit code."""
        wanted = [step + "|unset" for step in STEPS]
        failed = []
        if self.boot(text) != (0, wanted, ""):
            failed.append("all pass")
        for index, step in enumerate(STEPS):
            code, calls, _ = self.boot(text, BOOT_FAIL=step, BOOT_EXIT=str(index + 3))
            if (code, calls) != (index + 3, wanted[: index + 1]):
                failed.append(step + " fails")
        return failed


class BootScript(BootCase):
    def test_runs_the_four_commands_in_order_and_stops_at_the_first_failure(
        self,
    ) -> None:
        self.assertEqual(self.problems(SCRIPT.read_text()), [])
        self.assertTrue(os.access(SCRIPT, os.X_OK))

    def test_each_failing_command_stops_the_script_with_its_exit_code(self) -> None:
        text = SCRIPT.read_text()
        for index, step in enumerate(STEPS):
            with self.subTest(step=step):
                code, calls, _ = self.boot(text, BOOT_FAIL=step, BOOT_EXIT="7")
                self.assertEqual(code, 7)
                self.assertEqual(
                    calls, [name + "|unset" for name in STEPS[: index + 1]]
                )

    def test_plant_without_stop_on_failure_is_red(self) -> None:
        planted = without_line(SCRIPT.read_text(), "set -euo pipefail")
        self.assertEqual(
            self.problems(planted),
            ["down --previous-boot fails", "db-up fails", "preflight fails"],
        )

    def test_plant_with_reordered_steps_is_red(self) -> None:
        text = SCRIPT.read_text()
        planted = (
            text.replace("./eii db-up\n", "./eii STEP\n")
            .replace("./eii preflight\n", "./eii db-up\n")
            .replace("./eii STEP\n", "./eii preflight\n")
        )
        self.assertNotEqual(planted, text)
        self.assertEqual(
            self.problems(planted),
            ["all pass", "db-up fails", "preflight fails", "up fails"],
        )

    def test_plant_that_keeps_the_remote_host_is_red(self) -> None:
        planted = without_line(SCRIPT.read_text(), "unset EII_REMOTE_HOST")
        self.assertEqual(
            self.problems(planted), ["all pass", *(step + " fails" for step in STEPS)]
        )

    def test_script_holds_only_its_closed_statements(self) -> None:
        """No settings file is read: nothing but the seven statements exists."""
        text = SCRIPT.read_text()
        self.assertEqual(text.splitlines()[0], "#!/usr/bin/env bash")
        self.assertEqual(statements(text), STATEMENTS)
        planted = text.replace("./eii db-up\n", ". ./.env\n./eii db-up\n")
        self.assertNotEqual(statements(planted), STATEMENTS)


class BootDown(BootCase):
    """The script's first step through the real dispatcher and `down` logic."""

    def setUp(self) -> None:
        super().setUp()
        self.state = self.root / "home/live/state"
        self.state.mkdir(parents=True)
        release = self.root / "home/live/releases" / IDENTITY
        release.mkdir(parents=True)
        self.settings = dict(
            EII_ENVIRONMENT="live",
            EII_RELEASE_DIR=str(release),
            EII_STATE_DIR=str(self.state),
            EII_DATABASE_URL="postgresql://localhost:5432/invented_live",
        )
        self.real = dict(
            self.settings,
            BOOT_MAIN=str(ROOT / "scripts/commands/main.py"),
            BOOT_PYTHON=sys.executable,
        )

    def record(self, port: int) -> Path:
        return process.process_record(self.state, port)

    def previous(self, port: int) -> dict[str, Any]:
        record = dict(pid=17, environment="live", port=port, boot_id=PREVIOUS)
        atomic_json(self.record(port), record)
        return record

    def stored(self, port: int) -> dict[str, Any]:
        return read_json(self.record(port), MISMATCH)

    def foreign(self, port: int) -> subprocess.Popen[bytes]:
        """A process of this boot that the product did not start."""
        child = subprocess.Popen(
            (sys.executable, "-I", "-B", "-c", "import signal; signal.pause()"),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self.addCleanup(child.wait, process.READY_SECONDS)
        self.addCleanup(child.terminate)
        ticks, command = process.identity(child.pid)
        atomic_json(
            self.record(port),
            dict(
                pid=child.pid,
                start_ticks=ticks,
                cmdline_sha256=command,
                environment="live",
                nonce="INVENTED-foreign",
                port=port,
                boot_id=process.boot_id(),
            ),
        )
        return child

    def owned(self, port: int) -> dict[str, Any]:
        """A process of this boot started by the product's own launcher."""
        application = self.root / "application"
        script = application / "scripts/operations/entry.py"
        script.parent.mkdir(parents=True)
        script.write_text("import signal\nsignal.pause()\n")
        name = str(script.relative_to(application))
        tail = ("--nonce", "INVENTED-entry", "--environment", "live")
        record = process.launch(
            application,
            self.record(port),
            (sys.executable, "-I", "-B", "-S", name, *tail, "--port", str(port)),
            dict(EII_STATE_DIR=str(self.state), EII_ENVIRONMENT="live"),
            environment="live",
            nonce="INVENTED-entry",
            port=port,
            release_id=IDENTITY,
            application_sha256=APPLICATION,
        )
        self.addCleanup(process.terminate, record, "live")
        return record

    def test_previous_boot_backend_and_entry_records_are_retired(self) -> None:
        backend, entry = self.previous(18088), self.previous(8088)
        code, calls, output = self.boot(SCRIPT.read_text(), **self.real)
        self.assertEqual(
            output,
            "PASS down: previous-boot process records retired; data retained\n",
        )
        self.assertEqual((code, calls), (0, [step + "|unset" for step in STEPS]))
        self.assertEqual(self.stored(18088), dict(backend, stopped=True))
        self.assertEqual(self.stored(8088), dict(entry, stopped=True))

    def test_same_boot_foreign_record_refuses_and_no_later_step_runs(self) -> None:
        entry = self.previous(8088)
        child = self.foreign(18088)
        kept = self.stored(18088)
        code, calls, output = self.boot(SCRIPT.read_text(), **self.real)
        self.assertEqual(output.splitlines()[0], "FAIL down: " + MISMATCH)
        self.assertEqual((code, calls), (4, ["down --previous-boot|unset"]))
        self.assertIsNone(child.poll())
        self.assertEqual(self.stored(18088), kept)
        # The refusal does not stop the retirement of the other record.
        self.assertEqual(self.stored(8088), dict(entry, stopped=True))

    def test_nothing_is_signalled_for_a_previous_boot(self) -> None:
        self.previous(18088)
        self.previous(8088)
        with (
            patch("operations.process.terminate") as terminate,
            patch("operations.process.signal.pidfd_send_signal") as send,
        ):
            deploy.down(self.settings, previous_boot=True)
        terminate.assert_not_called()
        send.assert_not_called()
        self.assertTrue(self.stored(18088)["stopped"] and self.stored(8088)["stopped"])

    def test_same_boot_owned_process_keeps_running_and_keeps_its_record(self) -> None:
        record = self.owned(8088)
        with patch("operations.process.signal.pidfd_send_signal") as send:
            deploy.down(self.settings, previous_boot=True)
        send.assert_not_called()
        os.kill(record["pid"], 0)
        self.assertEqual(self.stored(8088), record)
        # The plain form still stops it: only the flag changes the outcome.
        deploy.down(self.settings)
        self.assertTrue(self.stored(8088)["stopped"])
        with self.assertRaises(ProcessLookupError):
            os.kill(record["pid"], 0)

    def test_same_boot_record_of_an_ended_process_refuses_until_plain_down(
        self,
    ) -> None:
        child = self.foreign(18088)
        child.terminate()
        child.wait(timeout=process.READY_SECONDS)
        kept = self.stored(18088)
        with self.assertRaisesRegex(Refusal, f"^{MISMATCH}$"):
            deploy.down(self.settings, previous_boot=True)
        self.assertEqual(self.stored(18088), kept)
        deploy.down(self.settings)
        self.assertEqual(self.stored(18088), dict(kept, stopped=True))

    def test_guard_deletion_admits_the_foreign_record(self) -> None:
        self.foreign(18088)
        with self.assertRaisesRegex(Refusal, f"^{MISMATCH}$"):
            process.down(self.state, "live", previous_boot=True)
        unguarded = without_call(process.down, "require_owned")
        # Red proof: without the ownership check the foreign record is admitted.
        unguarded(self.state, "live", previous_boot=True)
        with self.assertRaises(AssertionError):
            with self.assertRaisesRegex(Refusal, f"^{MISMATCH}$"):
                unguarded(self.state, "live", previous_boot=True)


class DownArguments(unittest.TestCase):
    def run_down(self, *args: str) -> tuple[int, list[Any], str]:
        errors = io.StringIO()
        with (
            patch("commands.down_cmd.down") as down,
            contextlib.redirect_stderr(errors),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            code = down_cmd.run({}, args)
        return code, down.call_args_list, errors.getvalue()

    def test_the_flag_selects_the_previous_boot_form(self) -> None:
        code, calls, _ = self.run_down("--previous-boot")
        self.assertEqual(code, 0)
        self.assertEqual([call.kwargs for call in calls], [dict(previous_boot=True)])
        code, calls, _ = self.run_down()
        self.assertEqual(code, 0)
        self.assertEqual([call.kwargs for call in calls], [dict(previous_boot=False)])

    def test_any_other_argument_is_a_usage_error(self) -> None:
        for args in (
            ("--previous-boot", "--previous-boot"),
            ("--previous-boot", "x"),
            ("--previous-boot=1",),
            ("--Previous-Boot",),
            ("previous-boot",),
            ("",),
        ):
            with self.subTest(args=args):
                code, calls, errors = self.run_down(*args)
                self.assertEqual((code, calls), (2, []))
                self.assertIn("eii: usage error", errors)


if __name__ == "__main__":
    unittest.main()
