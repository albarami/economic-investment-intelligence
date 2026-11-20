"""Supervisor of one generator-sandbox run (ARC-09, OI-129).

``sandbox_launch`` starts this program, never bubblewrap itself; this program
starts bubblewrap as its child and ends every process of the run when the
launcher ends, at any moment of the run, bubblewrap's start-up included.

Why it is needed: bubblewrap's ``--die-with-parent`` arms a parent-death
signal in each of its layers, but the inner layer (the init process of the new
pid namespace) arms its own only during its start-up. A launcher killed before
that kills the outer layer, and the inner one is re-parented to the system's
init and runs the sandboxed command on.

How it closes that window:

1. Before it starts anything, it makes itself a child subreaper
   (``PR_SET_CHILD_SUBREAPER``) and checks that the flag is set; it refuses to
   start otherwise. A descendant whose parent dies is then re-parented to this
   process, never to the system's init.
2. It learns that the launcher has ended in two independent ways: the end of
   file on a pipe whose only writer is the launcher (any exit, crash or kill
   of the launcher closes it, and the launcher closes it at its time limit),
   and a parent-death signal, armed and then checked against the launcher's
   process id, so a launcher that ended before the signal was armed is seen.
   It checks both before it starts bubblewrap and refuses if either fired.
3. When either fires, it kills bubblewrap and every process that is or becomes
   its child, and reaps them until it has no child left. A subreaper with no
   child has no descendant: an orphan is re-parented before its parent can be
   reaped. Killing the inner layer, the pid namespace's init, kills every
   process of the namespace.

There is no path that runs the command without this supervision: a step that
fails, or raises an error, refuses the run before bubblewrap starts. The
supervisor itself being killed by another process (``SIGKILL``) is outside
this; the launcher's process is the one whose end it covers. When this
process's cleanup does not finish in time, the launcher kills it, its process
group and every descendant itself (``sandbox_launch``).

Usage::

    python -I -B sandbox_supervisor.py LAUNCHER_PID CONTROL_FD FDS -- PROGRAM [ARG ...]

``FDS`` is the comma-separated list of descriptors that the program receives
(it may be empty); every other descriptor is closed in it. The exit status is
the program's own (a signal that ended it ends this process too); a refusal
writes one line starting ``sandbox supervisor: `` to standard error and exits
with status 1.
"""

from __future__ import annotations

import contextlib
import ctypes
import os
import select
import signal
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path
from types import FrameType
from typing import NoReturn

PREFIX = "sandbox supervisor: "
PR_SET_PDEATHSIG = 1
PR_SET_CHILD_SUBREAPER = 36
PR_GET_CHILD_SUBREAPER = 37
# The signals that end a run: the parent-death signal is the first.
ENDING_SIGNALS = (signal.SIGTERM, signal.SIGHUP, signal.SIGINT)
REFUSED = 1


def refuse(reason: str) -> NoReturn:
    """Write the refusal line and exit with status 1; no process of the run is left."""
    sys.stderr.write(PREFIX + reason + "\n")
    sys.stderr.flush()
    os._exit(REFUSED)


def parse(argv: Sequence[str]) -> tuple[int, int, tuple[int, ...], list[str]]:
    """Read ``LAUNCHER_PID CONTROL_FD FDS -- PROGRAM [ARG ...]``.

    Raises:
        ValueError: The arguments do not have that form.
    """
    if len(argv) < 5 or argv[3] != "--" or not argv[4].startswith("/"):
        raise ValueError("usage: LAUNCHER_PID CONTROL_FD FDS -- /PROGRAM [ARG ...]")
    launcher, control = int(argv[0]), int(argv[1])
    fds = tuple(int(item) for item in argv[2].split(",")) if argv[2] else ()
    if launcher <= 1 or control < 3 or any(fd < 3 or fd == control for fd in fds):
        raise ValueError("a process id or descriptor is out of range")
    return launcher, control, fds, list(argv[4:])


def _prctl(option: int, value: object) -> int:
    libc = ctypes.CDLL(None, use_errno=True)
    result: int = libc.prctl(option, value, 0, 0, 0)
    return result


def become_subreaper() -> str | None:
    """Mark this process a child subreaper; return a problem, or None."""
    if _prctl(PR_SET_CHILD_SUBREAPER, 1) != 0:
        return f"cannot become a child subreaper (errno {ctypes.get_errno()})"
    flag = ctypes.c_int(0)
    if _prctl(PR_GET_CHILD_SUBREAPER, ctypes.byref(flag)) != 0 or flag.value != 1:
        return "the child subreaper flag is not set"
    return None


def _noted(signum: int, frame: FrameType | None) -> None:
    """Handle an ending signal: the wake-up descriptor already carries it.

    Nothing is raised from a signal handler, so a signal can never interrupt
    the ending of the run half-way.
    """


def catch_ending_signals() -> int:
    """Route the ending signals to a wake-up pipe; return its read end."""
    wake, woken = os.pipe2(os.O_NONBLOCK | os.O_CLOEXEC)
    signal.set_wakeup_fd(woken, warn_on_full_buffer=False)
    for signum in ENDING_SIGNALS:
        signal.signal(signum, _noted)
    return wake


def arm_parent_death(launcher: int) -> str | None:
    """Arm the parent-death signal and check that the launcher is the parent."""
    if _prctl(PR_SET_PDEATHSIG, ENDING_SIGNALS[0]) != 0:
        return f"cannot arm the parent-death signal (errno {ctypes.get_errno()})"
    # Checked after arming: a launcher that ended before is seen here, one
    # that ends after sends the signal.
    if os.getppid() != launcher:
        return "the launcher ended before the sandbox started"
    return None


def ending(watched: Sequence[int], timeout: int | None) -> set[int]:
    """Return the descriptors of ``watched`` that have an event.

    On the control pipe an event means that its writer, the launcher, is gone
    (it never writes); on the wake-up pipe, that an ending signal arrived.
    """
    watch = select.poll()
    for fd in watched:
        watch.register(fd, select.POLLIN)
    return {fd for fd, _ in watch.poll(timeout)}


def children() -> list[int]:
    """Return the process ids whose parent is this process."""
    me = str(os.getpid())
    found = []
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            text = (entry / "stat").read_text(encoding="ascii", errors="replace")
        except OSError:
            continue
        # The command name in brackets can hold spaces; the parent follows
        # the state after the last closing bracket.
        fields = text.rpartition(")")[2].split()
        if len(fields) > 1 and fields[1] == me:
            found.append(int(entry.name))
    return found


def end_all() -> None:
    """Kill every child, present or re-parented, and reap them until none is left.

    Only children found in the process table are signalled: a child keeps its
    process id until it is reaped here, so no id that is signalled can belong
    to another process.
    """
    while True:
        for pid in children():
            with contextlib.suppress(ProcessLookupError):
                os.kill(pid, signal.SIGKILL)
        try:
            os.waitpid(-1, 0)
        except ChildProcessError:
            return


def exit_like(code: int) -> NoReturn:
    """Exit with the program's status; a signal that ended it ends this process."""
    if code < 0:
        signum = -code
        with contextlib.suppress(OSError, ValueError):
            signal.signal(signum, signal.SIG_DFL)
        os.kill(os.getpid(), signum)
        code = 128 + signum
    os._exit(code)


def supervise(
    launcher: int, control: int, fds: tuple[int, ...], program: list[str]
) -> NoReturn:
    """Start the program under supervision and end its run with the launcher."""
    try:
        os.set_inheritable(control, False)
        wake = catch_ending_signals()
        problem = become_subreaper() or arm_parent_death(launcher)
        if problem is None and ending((control, wake), 0):
            problem = "the launcher ended before the sandbox started"
    except Exception as error:
        # Nothing has started yet: an error here is a refusal like the others.
        problem = (
            f"the run was refused after an error in its set-up ({type(error).__name__})"
        )
    if problem is not None:
        refuse(problem)
    try:
        started = subprocess.Popen(program, env={}, close_fds=True, pass_fds=fds)
        done = os.pidfd_open(started.pid)
        ready: set[int] = set()
        while not ready:
            ready = ending((control, wake, done), None)
        code = None if ready & {control, wake} else started.wait()
    except Exception as error:
        end_all()
        refuse(f"the run was ended after an error ({type(error).__name__})")
    end_all()
    if code is None:
        # The launcher is gone or the run was asked to end: nobody reads this.
        os._exit(REFUSED)
    exit_like(code)


def main(argv: Sequence[str]) -> NoReturn:
    try:
        launcher, control, fds, program = parse(argv)
    except ValueError as error:
        refuse(str(error))
    supervise(launcher, control, fds, program)


if __name__ == "__main__":
    main(sys.argv[1:])
