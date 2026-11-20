"""The sandbox supervisor on its own (OI-129). No sandbox is started."""

from __future__ import annotations

import contextlib
import errno
import os
import select
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from collections.abc import Callable, Iterator
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
# An unrelated parent and child, outside any run, both sleeping; the parent
# prints the child's process id. Each carries the marker given after it.
PAIR = """
import os
import time

child = os.fork()
if child == 0:
    time.sleep(60)
    os._exit(0)
print(child, flush=True)
time.sleep(60)
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

    def _stalled_run(
        self, folder: Path, marker: str
    ) -> tuple[subprocess.Popen[str], list[int]]:
        """Start the stalled stand-in; return it and its four process ids."""
        standin = folder / "stalled.py"
        standin.write_text(support.STALLED_SUPERVISOR, encoding="utf-8")
        tree = standin.with_name("tree.pids")
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
        self.assertEqual(sorted(pids), sorted(support.marker_processes(marker)))
        return process, pids

    def _finish(self, process: subprocess.Popen[str], marker: str) -> None:
        """End what is left of a stalled run (processes this test started)."""
        _end(marker)
        process.wait(timeout=5)
        process.communicate(timeout=5)

    def test_a_stale_tree_never_signals_an_unrelated_process(self) -> None:
        # F1 of the third part F review: the walk sees root -> A -> B -> C,
        # where A is the stand-in's child in a session of its own and B and C
        # are an unrelated parent and child that this test started. The walk's
        # read of B names A as its parent (a stale view); every later read is
        # live. C's parent really is B's number, so a check of the parent's
        # number alone accepts C. Neither B nor C may be signalled.
        marker = "eii-stale-" + os.urandom(4).hex()
        unrelated = "eii-unrelated-" + os.urandom(4).hex()
        self.addCleanup(_end, marker)
        self.addCleanup(_end, unrelated)
        with tempfile.TemporaryDirectory() as tmp:
            process, pids = self._stalled_run(Path(tmp), marker)
            leader = pids[2]
            pair = subprocess.Popen(
                [sys.executable, "-I", "-B", "-c", PAIR, unrelated],
                env={},
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                text=True,
            )
            assert pair.stdout is not None
            first, second = pair.pid, int(pair.stdout.readline())
            self.assertEqual(_parent(second), first)
            self.assertNotEqual(_parent(first), leader)
            real_read = Path.read_text
            stale = [first]

            def walk_view(path: Path, *args: object, **kwargs: object) -> str:
                text = real_read(path, *args, **kwargs)  # type: ignore[arg-type]
                if stale and str(path) == f"/proc/{first}/stat":
                    stale.clear()
                    head, _, tail = text.rpartition(")")
                    fields = tail.split()
                    fields[1] = str(leader)
                    text = head + ") " + " ".join(fields) + "\n"
                return text

            signalled: list[int] = []
            real_send = signal.pidfd_send_signal

            def spy(handle: int, signum: int, *args: object) -> None:
                signalled.append(_pid_of_handle(handle))
                real_send(handle, signum, *args)  # type: ignore[arg-type]

            with (
                patch.object(Path, "read_text", walk_view),
                patch.object(signal, "pidfd_send_signal", spy),
            ):
                ended = launch.end_stalled(process)
            self.assertEqual(stale, [], "the stale view was not read")
            self.assertNotIn(first, signalled)
            self.assertNotIn(second, signalled)
            self.assertIn(leader, signalled)
            for pid in (first, second):
                self.assertIn(_state(pid), ("R", "S"))
            self.assertTrue(ended)
            self.assertEqual(support.marker_processes(marker), [])
            self._finish(process, marker)
            _end(unrelated)
            pair.wait(timeout=5)
            pair.stdout.close()

    def test_the_walk_stops_at_its_deadline(self) -> None:
        # F2 of the third part F review: the clock passes the whole kill bound
        # while the walk enumerates /proc. No process is read after that; the
        # group's kill is still sent; the end is not confirmed.
        marker = "eii-clock-" + os.urandom(4).hex()
        self.addCleanup(_end, marker)
        with tempfile.TemporaryDirectory() as tmp:
            process, _pids = self._stalled_run(Path(tmp), marker)
            real_read = Path.read_text
            real_clock = time.monotonic
            reads: list[str] = []
            late: list[str] = []
            offset = [0.0]

            def counted(path: Path, *args: object, **kwargs: object) -> str:
                name = str(path)
                if name.startswith("/proc/") and name.endswith("/stat"):
                    if offset[0]:
                        late.append(name)
                    reads.append(name)
                    if len(reads) == 3:
                        offset[0] = launch.KILL_SECONDS + 1
                return real_read(path, *args, **kwargs)  # type: ignore[arg-type]

            def clock() -> float:
                return real_clock() + offset[0]

            started = real_clock()
            with (
                patch.object(Path, "read_text", counted),
                patch.object(time, "monotonic", clock),
            ):
                ended = launch.end_stalled(process)
            elapsed = real_clock() - started
            self.assertGreaterEqual(len(reads), 3)
            self.assertEqual(late, [], "a process was read after the deadline")
            self.assertFalse(ended)
            self.assertLess(elapsed, launch.KILL_SECONDS)
            process.wait(timeout=5)
            self.assertEqual(process.returncode, -signal.SIGKILL)
            self._finish(process, marker)

    def test_an_unreadable_process_is_never_confirmed(self) -> None:
        # F3 of the third part F review: the stat of the stand-in's child in a
        # session of its own cannot be read (EACCES), so the walk cannot know
        # what lies below it. The end must not be confirmed, so the launcher
        # cannot say "killed".
        marker = "eii-unread-" + os.urandom(4).hex()
        self.addCleanup(_end, marker)
        with tempfile.TemporaryDirectory() as tmp:
            process, pids = self._stalled_run(Path(tmp), marker)
            leader = pids[2]
            real_read = Path.read_text

            def unreadable(path: Path, *args: object, **kwargs: object) -> str:
                if str(path) == f"/proc/{leader}/stat":
                    raise PermissionError(errno.EACCES, "planted", str(path))
                return real_read(path, *args, **kwargs)  # type: ignore[arg-type]

            started = time.monotonic()
            with patch.object(Path, "read_text", unreadable):
                ended = launch.end_stalled(process)
            elapsed = time.monotonic() - started
            self.assertFalse(ended)
            self.assertLess(elapsed, launch.KILL_SECONDS + 1)
            # What was not read was not reached: the unconfirmed end is true.
            self.assertIn(leader, support.marker_processes(marker))
            process.wait(timeout=5)
            self.assertEqual(process.returncode, -signal.SIGKILL)
            self._finish(process, marker)

    def test_the_index_is_not_built_after_the_deadline(self) -> None:
        # F2 of the fourth part F review, indexing: the clock passes the whole
        # kill bound as the third process read is placed under its parent. No
        # process may be placed after that; the group's kill is still sent.
        marker = "eii-index-" + os.urandom(4).hex()
        self.addCleanup(_end, marker)
        with tempfile.TemporaryDirectory() as tmp:
            process, _pids = self._stalled_run(Path(tmp), marker)
            clock = _Clock()
            placed: list[int] = []
            late: list[int] = []
            real_stat = launch._stat_of

            def watched(pid: int) -> launch._Stat | None:
                found = real_stat(pid)
                if found is None:
                    return None

                def placing() -> None:
                    if clock.offset:
                        late.append(pid)
                    placed.append(pid)
                    if len(placed) == 3:
                        clock.offset = launch.KILL_SECONDS + 1

                return _WatchedStat(found, placing)

            with (
                patch.object(launch, "_stat_of", watched),
                patch.object(time, "monotonic", clock),
            ):
                ended = launch.end_stalled(process)
            self.assertGreaterEqual(len(placed), 3)
            self.assertEqual(late, [], "a process was indexed after the deadline")
            self.assertFalse(ended)
            process.wait(timeout=5)
            self.assertEqual(process.returncode, -signal.SIGKILL)
            self._finish(process, marker)

    def test_the_frontier_stops_at_the_deadline(self) -> None:
        # F2 of the fourth part F review, leaf-frontier processing: the clock
        # passes the whole kill bound as the last process of the run is
        # stopped, while the frontier still holds it. No frontier entry may be
        # processed after that; every process already pinned is still killed.
        marker = "eii-frontier-" + os.urandom(4).hex()
        self.addCleanup(_end, marker)
        with tempfile.TemporaryDirectory() as tmp:
            process, pids = self._stalled_run(Path(tmp), marker)
            last = pids[3]
            clock = _Clock()
            late: list[int] = []
            spy = _SignalSpy()

            def expire(pid: int, signum: int) -> None:
                if pid == last and signum == signal.SIGSTOP:
                    clock.offset = launch.KILL_SECONDS + 1

            spy.after = expire
            real_ancestor = launch._Ancestor

            class Watched(real_ancestor):  # type: ignore[valid-type,misc]
                def __getattribute__(self, name: str) -> object:
                    if name == "pid" and clock.offset:
                        late.append(object.__getattribute__(self, "pid"))
                    return object.__getattribute__(self, name)

            with (
                patch.object(launch, "_Ancestor", Watched),
                patch.object(time, "monotonic", clock),
                spy.installed(),
            ):
                ended = launch.end_stalled(process)
            self.assertTrue(clock.offset, "the last process was not stopped")
            self.assertEqual(
                late, [], "a frontier entry was processed after the deadline"
            )
            self.assertFalse(ended)
            stopped = spy.pids(signal.SIGSTOP)
            self.assertEqual(sorted(stopped), sorted(pids[1:]))
            self.assertEqual(sorted(spy.pids(signal.SIGKILL)), sorted(stopped))
            self.assertIn((process.pid, signal.SIGKILL), spy.groups)
            process.wait(timeout=5)
            self.assertEqual(process.returncode, -signal.SIGKILL)
            self._finish(process, marker)

    def test_the_kill_work_is_bounded_before_a_process_is_taken(self) -> None:
        # F2 of the fourth part F review, finalization: the kill-and-close work
        # is bounded before another process is stopped. With two target slots,
        # the walk takes the stand-in's two children and stops before the
        # third process; the clock then passes the whole kill bound during the
        # kills. Every taken process and the group are still killed, no wait
        # waits past the deadline, and the end is not confirmed.
        marker = "eii-slots-" + os.urandom(4).hex()
        self.addCleanup(_end, marker)
        with tempfile.TemporaryDirectory() as tmp:
            process, pids = self._stalled_run(Path(tmp), marker)
            clock = _Clock()
            spy = _SignalSpy()

            def expire(_pid: int, signum: int) -> None:
                if signum == signal.SIGKILL:
                    clock.offset = launch.KILL_SECONDS + 1

            spy.after = expire
            waits: list[float | None] = []
            real_wait = process.wait

            def wait(timeout: float | None = None) -> int:
                waits.append(timeout)
                return real_wait(timeout=timeout)

            closed: list[int] = []
            real_close = os.close

            def close(handle: int) -> None:
                closed.append(handle)
                real_close(handle)

            with (
                patch.object(launch, "TARGET_SLOTS", 2, create=True),
                patch.object(time, "monotonic", clock),
                patch.object(process, "wait", wait),
                patch.object(os, "close", close),
                spy.installed(),
            ):
                try:
                    ended = launch.end_stalled(process)
                except subprocess.TimeoutExpired:
                    ended = False
            stopped = spy.pids(signal.SIGSTOP)
            self.assertEqual(sorted(stopped), sorted(pids[1:3]))
            self.assertEqual(sorted(spy.pids(signal.SIGKILL)), sorted(stopped))
            self.assertIn((process.pid, signal.SIGKILL), spy.groups)
            self.assertEqual(len(closed), 2)
            self.assertTrue(waits)
            self.assertTrue(all(left == 0 for left in waits), waits)
            self.assertFalse(ended)
            # What was not taken was not reached: the unconfirmed end is true.
            self.assertIn(pids[3], support.marker_processes(marker))
            process.wait(timeout=5)
            self.assertEqual(process.returncode, -signal.SIGKILL)
            self._finish(process, marker)

    def test_the_cleanup_time_is_bounded(self) -> None:
        # F2 of the fourth and fifth part F reviews: the clock never moves by
        # itself; it moves only by the cost of each read, descriptor, signal,
        # close and blocking wait of the cleanup, a blocking wait costing its
        # whole time-out. With
        # a run that settles and one that never settles (an unreadable process),
        # the cleanup ends within KILL_SECONDS of that clock and still kills
        # every taken process and the group.
        for unreadable in (False, True):
            with self.subTest(unreadable=unreadable):
                self._bounded_cleanup(unreadable)

    def _bounded_cleanup(self, unreadable: bool) -> None:
        """One case of ``test_the_cleanup_time_is_bounded``."""
        marker = "eii-bound-" + os.urandom(4).hex()
        self.addCleanup(_end, marker)
        with tempfile.TemporaryDirectory() as tmp:
            process, pids = self._stalled_run(Path(tmp), marker)
            hidden = f"/proc/{pids[2]}/stat" if unreadable else ""
            clock = _VirtualClock()
            spy = _SignalSpy()
            spy.after = lambda _pid, _signum: clock.spend()
            real_read = Path.read_text
            real_open = os.pidfd_open
            real_wait = process.wait

            def read(path: Path, *args: object, **kwargs: object) -> str:
                name = str(path)
                if name.startswith("/proc/") and name.endswith("/stat"):
                    clock.spend()
                    if name == hidden:
                        raise PermissionError(errno.EACCES, "planted", name)
                return real_read(path, *args, **kwargs)  # type: ignore[arg-type]

            def pidfd_open(pid: int, flags: int = 0) -> int:
                clock.spend()
                return real_open(pid, flags)

            def wait(timeout: float | None = None) -> int:
                assert timeout is not None, "an unbounded wait"
                clock.now += timeout
                return real_wait(timeout=5)

            real_close = os.close
            closed: list[int] = []

            def close(handle: int) -> None:
                # Each close of a taken process costs a step too, after a wait
                # that used its whole allowance (F2 of the fifth part F review).
                clock.spend()
                closed.append(handle)
                real_close(handle)

            with (
                patch.object(time, "monotonic", clock),
                patch.object(Path, "read_text", read),
                patch.object(os, "pidfd_open", pidfd_open),
                patch.object(os, "close", close),
                patch.object(process, "wait", wait),
                patch.object(select, "poll", clock.poll),
                spy.installed(),
            ):
                started = clock.now
                ended = launch.end_stalled(process)
                elapsed = clock.now - started
            self.assertLessEqual(elapsed, launch.KILL_SECONDS)
            self.assertTrue(closed, "no taken process was closed")
            if unreadable:
                self.assertFalse(ended)
            self.assertEqual(
                sorted(spy.pids(signal.SIGKILL)), sorted(spy.pids(signal.SIGSTOP))
            )
            self.assertIn((process.pid, signal.SIGKILL), spy.groups)
            process.wait(timeout=5)
            self.assertEqual(process.returncode, -signal.SIGKILL)
            self._finish(process, marker)

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


class _Clock:
    """The real monotonic clock, moved forward by ``offset`` seconds."""

    def __init__(self) -> None:
        self.real = time.monotonic
        self.offset = 0.0

    def __call__(self) -> float:
        return self.real() + self.offset


class _VirtualClock:
    """A clock that never moves by itself; only ``spend`` and waits move it.

    Every value is a multiple of a power of two, so sums are exact.
    """

    STEP = 2.0**-10

    def __init__(self) -> None:
        self.now = 1024.0

    def __call__(self) -> float:
        return self.now

    def spend(self) -> None:
        self.now += self.STEP

    def poll(self) -> _VirtualPoll:
        return _VirtualPoll(self)


REAL_POLL = select.poll


class _VirtualPoll:
    """``select.poll`` whose blocking wait costs its whole time-out."""

    def __init__(self, clock: _VirtualClock) -> None:
        self.clock = clock
        self.real = REAL_POLL()

    def register(self, handle: int, mask: int) -> None:
        self.real.register(handle, mask)

    def poll(self, timeout: int | None = None) -> list[tuple[int, int]]:
        assert timeout is not None, "an unbounded poll"
        ready = self.real.poll(0)
        if not ready:
            self.clock.now += timeout / 1000
        return ready


class _SignalSpy:
    """Record each signal the launcher sends, and call ``after`` once it is sent."""

    def __init__(self) -> None:
        self.sent: list[tuple[int, int]] = []
        self.groups: list[tuple[int, int]] = []
        self.after: Callable[[int, int], None] = lambda _pid, _signum: None

    def pids(self, signum: int) -> list[int]:
        return [pid for pid, number in self.sent if number == signum]

    @contextlib.contextmanager
    def installed(self) -> Iterator[None]:
        real_send = signal.pidfd_send_signal
        real_killpg = os.killpg

        def send(handle: int, signum: int, *args: object) -> None:
            pid = _pid_of_handle(handle)
            self.sent.append((pid, signum))
            real_send(handle, signum, *args)  # type: ignore[arg-type]
            self.after(pid, signum)

        def killpg(group: int, signum: int) -> None:
            self.groups.append((group, signum))
            real_killpg(group, signum)
            self.after(group, signum)

        with (
            patch.object(signal, "pidfd_send_signal", send),
            patch.object(os, "killpg", killpg),
        ):
            yield


class _WatchedStat(launch._Stat):
    """A process's metadata that calls a hook when its parent is read."""

    def __getattribute__(self, name: str) -> object:
        if name == "parent":
            object.__getattribute__(self, "hook")()
        return object.__getattribute__(self, name)

    def __new__(cls, found: launch._Stat, hook: Callable[[], None]) -> _WatchedStat:
        made = object.__new__(cls)
        object.__setattr__(made, "state", found.state)
        object.__setattr__(made, "parent", found.parent)
        object.__setattr__(made, "start", found.start)
        object.__setattr__(made, "hook", hook)
        return made

    def __init__(self, found: launch._Stat, hook: Callable[[], None]) -> None:
        """Every field is set by ``__new__``."""


def _end(marker: str) -> None:
    for pid in support.marker_processes(marker):
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


def _fields(pid: int) -> list[str]:
    """Return the fields of ``/proc/PID/stat`` after the command name."""
    with open(f"/proc/{pid}/stat", encoding="ascii", errors="replace") as handle:
        return handle.read().rpartition(")")[2].split()


def _parent(pid: int) -> int:
    return int(_fields(pid)[1])


def _state(pid: int) -> str | None:
    """Return the state letter of ``pid``, or None when it is gone."""
    try:
        return _fields(pid)[0]
    except (FileNotFoundError, ProcessLookupError):
        return None


def _pid_of_handle(handle: int) -> int:
    """Return the process id that a process descriptor of this process pins."""
    with open(f"/proc/self/fdinfo/{handle}", encoding="ascii") as info:
        for line in info:
            if line.startswith("Pid:"):
                return int(line.split()[1])
    return -1


if __name__ == "__main__":
    unittest.main()
