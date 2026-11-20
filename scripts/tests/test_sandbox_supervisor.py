"""The sandbox supervisor on its own (OI-129). No sandbox is started."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import sandbox_support as support

import sandbox_launch as launch
import sandbox_supervisor as supervisor

SHELL = "/bin/sh"
# A sleeper whose command line carries the marker given after it.
SLEEP = f"{sys.executable} -I -c 'import time; time.sleep(60)'"
# The supervisor with ``os.pipe2`` failing as it does when no descriptor is
# left, in its own process only: its set-up fails before anything starts.
FAILING_SETUP = """
import errno
import os
import sys

sys.path.insert(0, sys.argv[1])
import sandbox_supervisor as supervisor


def fail(*args):
    raise OSError(errno.EMFILE, os.strerror(errno.EMFILE))


supervisor.os.pipe2 = fail
supervisor.main(sys.argv[2:])
"""


class Run:
    """One supervisor process with its control pipe, as the launcher starts it."""

    def __init__(self, program: list[str], launcher: int | None = None) -> None:
        control, self.keep = os.pipe()
        try:
            command = launch.supervisor_command(control, (), program)
            if launcher is not None:
                command[4] = str(launcher)
            self.process = subprocess.Popen(
                command,
                env={},
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                close_fds=True,
                pass_fds=(control,),
                start_new_session=True,
            )
        finally:
            os.close(control)

    def close_control(self) -> None:
        if self.keep >= 0:
            os.close(self.keep)
            self.keep = -1

    def finish(self) -> tuple[int, str, str]:
        try:
            out, err = self.process.communicate(timeout=20)
        finally:
            self.close_control()
        return self.process.returncode, out, err


class SupervisorRules(unittest.TestCase):
    def test_arguments_are_checked(self) -> None:
        self.assertEqual(
            supervisor.parse(["42", "5", "3,4", "--", "/bin/true", "x"]),
            (42, 5, (3, 4), ["/bin/true", "x"]),
        )
        self.assertEqual(
            supervisor.parse(["42", "5", "", "--", "/bin/true"]),
            (42, 5, (), ["/bin/true"]),
        )
        for bad in (
            ["42", "5", "", "/bin/true"],
            ["42", "5", "", "--", "true"],
            ["1", "5", "", "--", "/bin/true"],
            ["42", "2", "", "--", "/bin/true"],
            ["42", "5", "2", "--", "/bin/true"],
            ["42", "5", "5", "--", "/bin/true"],
            ["x", "5", "", "--", "/bin/true"],
        ):
            with self.assertRaises(ValueError, msg=bad):
                supervisor.parse(bad)

    def test_subreaper_refused_is_reported(self) -> None:
        with patch.object(supervisor, "_prctl", return_value=-1):
            self.assertIsNotNone(supervisor.become_subreaper())
            self.assertIsNotNone(supervisor.arm_parent_death(os.getppid()))
        answers = iter([0, 0])
        with patch.object(supervisor, "_prctl", lambda *args: next(answers)):
            # The flag reads back as 0: not a subreaper.
            self.assertEqual(
                supervisor.become_subreaper(), "the child subreaper flag is not set"
            )

    def test_status_is_passed_through(self) -> None:
        run = Run([SHELL, "-c", "exit 7"])
        self.assertEqual(run.finish(), (7, "", ""))
        run = Run([SHELL, "-c", "printf out; printf err >&2; kill -TERM $$"])
        self.assertEqual(run.finish(), (-signal.SIGTERM, "out", "err"))

    def test_a_foreign_launcher_is_refused_and_nothing_starts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            planted = Path(tmp) / "started"
            run = Run([SHELL, "-c", f"touch {planted}"], launcher=os.getppid())
            status, out, err = run.finish()
            self.assertEqual(
                (status, out, err),
                (
                    1,
                    "",
                    "sandbox supervisor: the launcher ended before the sandbox started\n",
                ),
            )
            self.assertFalse(planted.exists())

    def test_a_closed_control_pipe_is_refused_and_nothing_starts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            planted = Path(tmp) / "started"
            control, keep = os.pipe()
            os.close(keep)
            try:
                done = subprocess.run(
                    launch.supervisor_command(
                        control, (), [SHELL, "-c", f"touch {planted}"]
                    ),
                    env={},
                    capture_output=True,
                    text=True,
                    close_fds=True,
                    pass_fds=(control,),
                    timeout=20,
                    check=False,
                )
            finally:
                os.close(control)
            self.assertEqual(
                (done.returncode, done.stderr),
                (
                    1,
                    "sandbox supervisor: the launcher ended before the sandbox started\n",
                ),
            )
            self.assertFalse(planted.exists())

    def test_a_setup_error_is_refused_and_nothing_starts(self) -> None:
        # Finding 2 of the second part F review: an error in the set-up, before
        # the run's own error handling, is refused with the supervisor's line.
        with tempfile.TemporaryDirectory() as tmp:
            planted = Path(tmp) / "started"
            control, keep = os.pipe()
            try:
                command = launch.supervisor_command(
                    control, (), [SHELL, "-c", f"touch {planted}"]
                )
                done = subprocess.run(
                    [
                        command[0],
                        "-I",
                        "-B",
                        "-c",
                        FAILING_SETUP,
                        str(launch.SUPERVISOR.parent),
                        *command[4:],
                    ],
                    env={},
                    capture_output=True,
                    text=True,
                    close_fds=True,
                    pass_fds=(control,),
                    timeout=20,
                    check=False,
                )
            finally:
                os.close(control)
                os.close(keep)
            self.assertEqual(
                (done.returncode, done.stdout, done.stderr),
                (
                    1,
                    "",
                    "sandbox supervisor: the run was refused after an error in its "
                    "set-up (OSError)\n",
                ),
            )
            self.assertFalse(planted.exists())

    def test_the_launcher_ends_a_stalled_run_itself(self) -> None:
        # F1 of the part F review, without bubblewrap: the launcher's own kill
        # reaches the process group and the session below it, and reports an
        # end it cannot confirm (a late supervisor, a refused signal) as not
        # confirmed; the kills are sent in every case.
        marker = "eii-stalled-" + os.urandom(4).hex()
        self.addCleanup(_end, marker)
        with tempfile.TemporaryDirectory() as tmp:
            standin = Path(tmp) / "stalled.py"
            standin.write_text(support.STALLED_SUPERVISOR, encoding="utf-8")
            tree = standin.with_name("tree.pids")
            real_killpg = os.killpg

            def refused(group: int, signum: int) -> None:
                if signum == signal.SIGSTOP:
                    raise PermissionError("planted")
                real_killpg(group, signum)

            for case in ("confirmed", "late", "refused"):
                with self.subTest(case=case):
                    tree.unlink(missing_ok=True)
                    process = subprocess.Popen(
                        [sys.executable, "-I", "-B", str(standin), marker],
                        env={},
                        stdin=subprocess.DEVNULL,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        start_new_session=True,
                    )
                    deadline = time.monotonic() + 10
                    while time.monotonic() < deadline and not tree.exists():
                        time.sleep(0.01)
                    self.assertTrue(tree.exists())
                    pids = [int(item) for item in tree.read_text().split()]
                    self.assertEqual(
                        sorted(pids), sorted(support.marker_processes(marker))
                    )
                    if case == "confirmed":
                        self.assertTrue(launch.end_stalled(process))
                        self.assertEqual(support.marker_processes(marker), [])
                    else:
                        if case == "late":
                            late = subprocess.TimeoutExpired("supervisor", 0)
                            planted = patch.object(process, "wait", side_effect=late)
                        else:
                            planted = patch.object(os, "killpg", side_effect=refused)
                        with planted:
                            self.assertFalse(launch.end_stalled(process))
                        process.wait(timeout=5)
                        deadline = time.monotonic() + 5
                        while time.monotonic() < deadline and support.marker_processes(
                            marker
                        ):
                            time.sleep(0.05)
                        self.assertEqual(support.marker_processes(marker), [])
                    self.assertEqual(process.returncode, -signal.SIGKILL)
                    process.communicate(timeout=5)

    def test_an_orphan_is_ended_when_the_program_ends(self) -> None:
        # The program leaves a process behind that has no parent-death signal;
        # it is re-parented to the supervisor and killed before it exits.
        marker = "eii-orphan-" + os.urandom(4).hex()
        run = Run([SHELL, "-c", f"exec 1>&- 2>&-; {SLEEP} {marker} & exit 3"])
        self.addCleanup(_end, marker)
        status, _out, _err = run.finish()
        self.assertEqual(status, 3)
        # The supervisor ends only after it has reaped every process.
        self.assertEqual(support.marker_processes(marker), [])

    def test_closing_the_control_pipe_ends_the_run(self) -> None:
        marker = "eii-closed-" + os.urandom(4).hex()
        with tempfile.TemporaryDirectory() as tmp:
            ready = Path(tmp) / "ready"
            run = Run(
                [
                    SHELL,
                    "-c",
                    f"{SLEEP} {marker} & touch {ready}; {SLEEP} {marker}",
                ]
            )
            self.addCleanup(_end, marker)
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline and not ready.exists():
                time.sleep(0.01)
            self.assertTrue(ready.exists())
            # The supervisor, the shell and the background sleeper at least.
            self.assertGreaterEqual(len(support.marker_processes(marker)), 3)
            run.close_control()
            status, out, err = run.finish()
            self.assertEqual((status, out, err), (1, "", ""))
            # The supervisor ends only after it has reaped every process.
        self.assertEqual(support.marker_processes(marker), [])

    def test_an_ending_signal_ends_the_run(self) -> None:
        marker = "eii-signal-" + os.urandom(4).hex()
        with tempfile.TemporaryDirectory() as tmp:
            ready = Path(tmp) / "ready"
            run = Run([SHELL, "-c", f"touch {ready}; {SLEEP} {marker}"])
            self.addCleanup(_end, marker)
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline and not ready.exists():
                time.sleep(0.01)
            self.assertTrue(ready.exists())
            os.kill(run.process.pid, signal.SIGTERM)
            status, _out, _err = run.finish()
            self.assertEqual(status, 1)
            # The supervisor ends only after it has reaped every process.
        self.assertEqual(support.marker_processes(marker), [])


def _end(marker: str) -> None:
    for pid in support.marker_processes(marker):
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


if __name__ == "__main__":
    unittest.main()
