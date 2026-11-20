"""Launcher of the generator sandbox (ARC-09 to ARC-14, SYN-01).

``run_in_sandbox`` is the one entry point that ``build-world`` and
``build-release`` use. Every mount source is opened once, checked on its open
descriptor and handed to bubblewrap by descriptor, so the object that was
checked is the object that is mounted. The extension folder is an in-memory
mount of its own: its files are opened and hashed through descriptors
(``extension_tree``) and bound one by one into it, and the mount is then made
read-only, so nothing else of the host folder is visible. Bubblewrap is
started under ``sandbox_supervisor``, which ends every process of the run when
the launcher ends, also during bubblewrap's start-up (OI-129). The proofs are
in ``sandbox_check``.
"""

from __future__ import annotations

import os
import select
import signal
import stat
import subprocess
import sys
import time
from collections import deque
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

import extension_tree
import sandbox_profiles as tables

ROOT = Path(__file__).resolve().parents[1]
BWRAP_PREFIX = "bwrap: "
# The supervisor that starts bubblewrap and ends the run with the launcher; its
# refusals start with SUPERVISOR_PREFIX and exit with status 1, as bubblewrap's
# own setup failures do.
SUPERVISOR = Path(__file__).resolve().with_name("sandbox_supervisor.py")
SUPERVISOR_PREFIX = "sandbox supervisor: "
SETUP_PREFIXES = (BWRAP_PREFIX, SUPERVISOR_PREFIX)
# At the time limit the launcher closes the control pipe and waits at most
# CLEANUP_SECONDS for the supervisor's own cleanup. If that does not finish,
# the launcher kills the supervisor, its process group and every descendant
# itself, waits at most KILL_SECONDS for them to end and DRAIN_SECONDS for the
# output to close (F1 of the part F review). With a 1 s limit the sum stays
# within the 10 s that the time-out tests allow.
CLEANUP_SECONDS = 4.0
KILL_SECONDS = 2.0
DRAIN_SECONDS = 1.0
# The walk for descendants may use at most this part of KILL_SECONDS; the rest
# is kept for the kills and the reaping (F2 of the third part F review).
WALK_SECONDS = KILL_SECONDS / 2
# At most this many descendants are taken (pinned and stopped), so the kills
# and closes still to be done are bounded before another process is stopped:
# each taken process holds one kill slot, and the supervisor's group has its
# own. A walk that finds more stops taking, still kills what it took and the
# group, and leaves the end unconfirmed (F2 of the fourth part F review).
TARGET_SLOTS = 512
# The waits for the kills end this part of KILL_SECONDS before the deadline;
# it is kept for closing the descriptor of every taken process, at most
# TARGET_SLOTS closes that never block, so that they too end within the
# deadline (F2 of the fifth part F review).
CLOSE_SECONDS = KILL_SECONDS / 16
# os.open flags of a mount source: a path descriptor that does not follow a
# symbolic link in the last part and is closed in every started program.
OPEN_FLAGS = os.O_PATH | os.O_NOFOLLOW | os.O_CLOEXEC
FIRST_FREE_DESCRIPTOR = 3
DESCRIPTOR_LINK = "/proc/self/fd/{}"


class SandboxError(Exception):
    """The sandbox cannot be started, or the request is not allowed."""


class SandboxSetupError(SandboxError):
    """Bubblewrap itself failed before or while it built the sandbox."""


class SandboxTimeout(SandboxError):
    """The sandboxed command did not finish in time and was killed."""


@dataclass(frozen=True)
class Layout:
    """The host folders that a profile mounts.

    Attributes:
        code_root: Folder holding ``core/src``, ``custodian/src`` and ``scripts``.
        cache: The public cache, mounted read-only.
        vault: The build's vault folder, mounted writable.
        extensions: The engine-extension folder; its checked files are bound read-only.
        staging: Release staging folder, writable (``build-release`` only).
        scenario: The decrypted scenario file, read-only (``build-world`` only).
    """

    code_root: Path
    cache: Path
    vault: Path
    extensions: Path
    staging: Path | None = None
    scenario: Path | None = None


@dataclass(frozen=True)
class Interpreter:
    """The interpreter folders a sandbox must hold.

    Attributes:
        venv: The virtual environment, mounted read-only.
        real: The folder of the uv-managed interpreter, mounted read-only.
        alias: The minor-version link the environment points at, or None.
    """

    venv: Path
    real: Path
    alias: Path | None


@dataclass(frozen=True)
class SandboxResult:
    """What a sandboxed command did."""

    returncode: int
    stdout: str
    stderr: str


def current_venv() -> Path:
    """Return the running virtual environment.

    Raises:
        SandboxError: The interpreter is not running in a virtual environment.
    """
    if sys.prefix == sys.base_prefix:
        raise SandboxError(
            "not running in the project environment: use 'uv run --locked' after "
            "'uv sync --managed-python --all-packages --locked --group engine'"
        )
    # The descriptor check compares paths as the kernel prints them, so ".."
    # and "." parts are removed here; links are judged on the descriptor.
    return Path(os.path.abspath(sys.prefix))


def interpreter_for(venv: Path) -> Interpreter:
    """Work out the interpreter folders of a uv-managed virtual environment.

    Args:
        venv: The virtual environment folder.

    Returns:
        The folders to mount.

    Raises:
        SandboxError: The environment's interpreter is not a uv-managed one.
    """
    python = venv / "bin" / "python"
    try:
        target = Path(os.readlink(python))
    except OSError:
        raise SandboxError(
            f"{python} is not a link to a uv-managed interpreter"
        ) from None
    if not target.is_absolute() or target.parent.name != "bin":
        raise SandboxError(f"{python} does not link to an absolute .../bin/ path")
    alias = target.parent.parent
    real = Path(os.path.realpath(alias))
    if real.is_relative_to("/usr"):
        raise SandboxError(
            f"the interpreter {real} is not uv-managed: create the environment "
            "with 'uv sync --managed-python --all-packages --locked --group engine'"
        )
    return Interpreter(venv, real, None if alias == real else alias)


def check_profile(profile: tables.Profile, layout: Layout) -> None:
    """Refuse a staging folder or scenario file that the profile does not declare.

    Raises:
        SandboxError: A declared element is missing or an undeclared one is given.
    """
    if profile.staging != (layout.staging is not None):
        raise SandboxError(
            f"profile {profile.name} needs a staging folder"
            if profile.staging
            else f"profile {profile.name} takes no staging folder"
        )
    if profile.scenario != (layout.scenario is not None):
        raise SandboxError(
            f"profile {profile.name} needs a scenario file"
            if profile.scenario
            else f"profile {profile.name} takes no scenario file"
        )


def mount_sources(
    profile: tables.Profile, layout: Layout, interpreter: Interpreter
) -> list[tuple[Path, bool]]:
    """List every host path that becomes a mount source, in mount order.

    Returns:
        ``(path, is_folder)`` pairs; only the scenario is a file.
    """
    found = [(Path(folder), True) for folder in tables.SYSTEM_READ_ONLY]
    found += [(interpreter.real, True), (interpreter.venv, True)]
    found += [(layout.code_root / folder, True) for folder in tables.CODE_FOLDERS]
    found += [(layout.cache, True), (layout.extensions, True)]
    if profile.scenario and layout.scenario is not None:
        found.append((layout.scenario, False))
    found.append((layout.vault, True))
    if profile.staging and layout.staging is not None:
        found.append((layout.staging, True))
    return found


def _descriptor_problem(path: Path, descriptor: int, is_folder: bool) -> str | None:
    """Judge an opened mount source on its descriptor; never look the path up."""
    if descriptor < FIRST_FREE_DESCRIPTOR:
        return (
            f"mount source {path} was opened as descriptor {descriptor}, a standard "
            "stream: start the launcher with standard input, output and error open"
        )
    try:
        status = os.fstat(descriptor)
        seen = os.readlink(DESCRIPTOR_LINK.format(descriptor))
    except OSError as error:
        return f"mount source cannot be checked: {path} ({type(error).__name__})"
    mode = status.st_mode
    if stat.S_ISLNK(mode) or seen != str(path):
        return f"mount source is or lies below a symbolic link: {path}"
    if not (stat.S_ISDIR(mode) if is_folder else stat.S_ISREG(mode)):
        return f"mount source is missing or of the wrong kind: {path}"
    # A second name of a mounted file could lie in a writable mount.
    if not is_folder and status.st_nlink != 1:
        return f"mount source has {status.st_nlink} hard links, expected 1: {path}"
    return None


def _open_one(path: Path, is_folder: bool) -> int:
    """Open one mount source and check it on the descriptor."""
    try:
        descriptor = os.open(path, OPEN_FLAGS)
    except FileNotFoundError:
        raise SandboxError(
            f"mount source is missing or of the wrong kind: {path}"
        ) from None
    except OSError as error:
        raise SandboxError(
            f"mount source cannot be opened: {path} ({type(error).__name__})"
        ) from None
    problem = _descriptor_problem(path, descriptor, is_folder)
    if problem is not None:
        os.close(descriptor)
        raise SandboxError(problem)
    return descriptor


def close_all(descriptors: Mapping[Path, int]) -> None:
    """Close the descriptors of ``open_sources``."""
    for descriptor in descriptors.values():
        os.close(descriptor)


def extension_files(layout: Layout) -> list[Path]:
    """Return the host paths of the extension files of the pinned engine."""
    return [
        layout.extensions / relative
        for relative in extension_tree.relative_files(extension_tree.ENGINE)
    ]


def bound_paths(
    profile: tables.Profile, layout: Layout, interpreter: Interpreter
) -> list[Path]:
    """List the keys of ``open_sources`` for a fetched extension folder, in order.

    Returns:
        The mount sources in mount order, with the extension folder replaced by
        its extension files.
    """
    found: list[Path] = []
    for path, _ in mount_sources(profile, layout, interpreter):
        found += extension_files(layout) if path == layout.extensions else [path]
    return found


def _open_extensions(folder: Path, root: int) -> dict[Path, int]:
    """Open and check the extension files below the open extension folder.

    Raises:
        SandboxError: A part of the folder is not as pinned; nothing stays open.
    """
    files, problems = extension_tree.open_tree(root, extension_tree.ENGINE)
    if problems:
        raise SandboxError(f"extension folder {folder}: " + "; ".join(problems))
    return {folder / item.relative: item.descriptor for item in files or []}


def open_sources(
    profile: tables.Profile, layout: Layout, interpreter: Interpreter
) -> dict[Path, int]:
    """Check a layout against a profile and open every mount source once.

    The paths are judged before any is opened (absolute, no two equal or
    nested); each is then opened without following a symbolic link in its last
    part and judged on the descriptor: its kind, the path the kernel gives for
    the descriptor, which must equal the given path (a link in a parent makes
    them differ), and for the scenario file one name only. Nothing looks a
    source up by path afterwards. The extension folder is opened the same way;
    its files are then opened through it (``extension_tree.open_tree``) and
    take its place, and its own descriptor is closed.

    Args:
        profile: The profile.
        layout: The host folders.
        interpreter: The interpreter folders.

    Returns:
        Each bound path with its open descriptor, in mount order (the keys of
        ``bound_paths``, without the extension files when the extension folder
        is empty). The caller closes them with ``close_all``.

    Raises:
        SandboxError: The layout does not fit the profile, or a source is
            relative, missing, a link or below one, of the wrong kind, a file
            with a second name, overlapping another, or cannot be opened, or
            the extension folder is not as pinned; nothing stays open then.
    """
    check_profile(profile, layout)
    sources = mount_sources(profile, layout, interpreter)
    for path, _ in sources:
        if not path.is_absolute():
            raise SandboxError(f"mount source is not absolute: {path}")
    for index, (first, _) in enumerate(sources):
        for second, _ in sources[index + 1 :]:
            if first == second or first in second.parents or second in first.parents:
                raise SandboxError(f"mount sources overlap: {first} and {second}")
    opened: dict[Path, int] = {}
    complete = False
    try:
        for path, is_folder in sources:
            descriptor = _open_one(path, is_folder)
            if path != layout.extensions:
                opened[path] = descriptor
                continue
            try:
                opened.update(_open_extensions(path, descriptor))
            finally:
                os.close(descriptor)
        complete = True
    finally:
        if not complete:
            close_all(opened)
    return opened


def build_argv(
    profile: tables.Profile,
    layout: Layout,
    interpreter: Interpreter,
    command: Sequence[str],
    descriptors: Mapping[Path, int],
) -> list[str]:
    """Build the bubblewrap command line (pure; touches no file).

    Args:
        profile: The profile.
        layout: The host folders.
        interpreter: The interpreter folders.
        command: The program and arguments to run; the program is an absolute path.
        descriptors: The open descriptor of every mount source (``open_sources``).

    Returns:
        The full argument list, program first.

    Raises:
        SandboxError: The command is empty or its program is not an absolute
            path, the layout does not fit the profile, or only some of the
            extension files have a descriptor.
    """
    if not command or not command[0].startswith("/"):
        raise SandboxError("the sandboxed program must be an absolute path")
    check_profile(profile, layout)

    def bind(option: str, source: Path, destination: str) -> list[str]:
        return [option, str(descriptors[source]), destination]

    argv = [tables.BWRAP, *tables.ISOLATION]
    for name, value in (
        *tables.FIXED_ENVIRONMENT,
        ("PATH", str(interpreter.venv / "bin")),
        (tables.PROFILE_VARIABLE, profile.name),
    ):
        argv += ["--setenv", name, value]
    argv += ["--dev", tables.DEVICES, "--tmpfs", tables.SCRATCH]
    for folder in tables.SYSTEM_READ_ONLY:
        argv += bind(tables.READ_ONLY_BIND, Path(folder), folder)
    argv += ["--symlink", *tables.LOADER_LINK]
    argv += bind(tables.READ_ONLY_BIND, interpreter.real, str(interpreter.real))
    if interpreter.alias is not None:
        argv += ["--symlink", interpreter.real.name, str(interpreter.alias)]
    argv += bind(tables.READ_ONLY_BIND, interpreter.venv, str(interpreter.venv))
    for folder in tables.CODE_FOLDERS:
        code = layout.code_root / folder
        argv += bind(tables.READ_ONLY_BIND, code, str(code))
    argv += bind(tables.READ_ONLY_BIND, layout.cache, str(layout.cache))
    files = extension_files(layout)
    given = [path for path in files if path in descriptors]
    argv += ["--tmpfs", str(layout.extensions)]
    if given and given != files:
        shown = ", ".join(str(path) for path in given)
        raise SandboxError(f"only some extension files have a descriptor: {shown}")
    if given:
        for part in (files[0].parent.parent, files[0].parent):
            argv += [tables.MAKE_FOLDER, str(part)]
        for path in files:
            argv += bind(tables.READ_ONLY_BIND, path, str(path))
    argv += ["--remount-ro", str(layout.extensions)]
    if profile.scenario and layout.scenario is not None:
        argv += bind(tables.READ_ONLY_BIND, layout.scenario, tables.SCENARIO_INSIDE)
    argv += bind(tables.WRITABLE_BIND, layout.vault, str(layout.vault))
    if profile.staging and layout.staging is not None:
        argv += bind(tables.WRITABLE_BIND, layout.staging, str(layout.staging))
    argv += ["--chdir", tables.SCRATCH, "--remount-ro", "/"]
    return [*argv, *command]


def python_command(*arguments: str, venv: Path | None = None) -> list[str]:
    """Return a command that runs the environment's interpreter in isolated mode."""
    folder = venv if venv is not None else current_venv()
    return [str(folder / "bin" / "python"), "-I", "-B", *arguments]


def profile_named(name: str) -> tables.Profile:
    """Find a profile by name.

    Raises:
        SandboxError: There is no such profile.
    """
    for profile in tables.PROFILES:
        if profile.name == name:
            return profile
    raise SandboxError(f"unknown profile: {name}")


def supervisor_command(
    control: int, passed: tuple[int, ...], argv: Sequence[str]
) -> list[str]:
    """Return the command that runs bubblewrap's ``argv`` under the supervisor.

    Args:
        control: The read end of the control pipe, kept open in the supervisor.
        passed: The mount descriptors, which bubblewrap receives.
        argv: The bubblewrap command line (``build_argv``).

    Raises:
        SandboxError: The launcher's interpreter is not known.
    """
    if not sys.executable:
        raise SandboxError(
            "the interpreter of the launcher is not known: the sandbox supervisor cannot start"
        )
    return [
        sys.executable,
        "-I",
        "-B",
        str(SUPERVISOR),
        str(os.getpid()),
        str(control),
        ",".join(str(number) for number in passed),
        "--",
        *argv,
    ]


class _Unread(Exception):
    """A process exists, but its metadata cannot be read or is not valid."""


@dataclass(frozen=True)
class _Stat:
    """What the walk reads of a process in ``/proc/<pid>/stat``.

    Attributes:
        state: The state letter (field 3).
        parent: The parent's process id (field 4).
        start: The start time in clock ticks after boot (field 22); with the
            process id it names one process, as a reused id has a later start.
    """

    state: str
    parent: int
    start: int


# The fields after the command name: the state is field 3, so field N is at
# index N - 3.
STATE_INDEX, PARENT_INDEX, START_INDEX = 0, 1, 19


def _stat_of(pid: int) -> _Stat | None:
    """Read the state, parent and start time of ``pid``.

    Returns:
        The metadata, or None only when the process is gone (ENOENT, ESRCH).

    Raises:
        _Unread: The process may exist, but its metadata cannot be read (for
            example EACCES) or is not valid; it is never taken as gone (F3 of
            the third part F review).
    """
    try:
        text = Path(f"/proc/{pid}/stat").read_text(encoding="ascii", errors="replace")
    except (FileNotFoundError, ProcessLookupError):
        return None
    except OSError as error:
        raise _Unread(f"{pid}: {type(error).__name__}") from None
    # The command name in brackets can hold spaces; the fields follow the last
    # closing bracket.
    fields = text.rpartition(")")[2].split()
    if (
        len(fields) <= START_INDEX
        or not fields[PARENT_INDEX].isdigit()
        or not fields[START_INDEX].isdigit()
    ):
        raise _Unread(f"{pid}: not valid")
    return _Stat(
        fields[STATE_INDEX], int(fields[PARENT_INDEX]), int(fields[START_INDEX])
    )


@dataclass
class _Table:
    """One read of ``/proc``.

    Attributes:
        stats: The metadata by process id.
        below: The process ids read with each parent id, built as each process
            is read, so no work on the table is left after the deadline.
        complete: False when ``/proc`` cannot be listed, the deadline passed
            before every process was read, or the metadata of a process could
            not be read. A process that is gone is left out.
    """

    stats: dict[int, _Stat]
    below: dict[int, list[int]]
    complete: bool


def _process_table(deadline: float) -> _Table:
    """Read and index every process of ``/proc``, stopping at ``deadline``.

    The deadline is checked before each entry is read; each process read is
    placed under its parent at once (F2 of the fourth part F review).
    """
    table = _Table({}, {}, True)
    try:
        for entry in Path("/proc").iterdir():
            if time.monotonic() >= deadline:
                table.complete = False
                return table
            if not entry.name.isdigit():
                continue
            pid = int(entry.name)
            try:
                found = _stat_of(pid)
            except _Unread:
                table.complete = False
                continue
            if found is not None:
                table.stats[pid] = found
                table.below.setdefault(found.parent, []).append(pid)
    except OSError:
        table.complete = False
    return table


def _exited(handle: int) -> bool:
    """Return whether the process pinned by ``handle`` has ended."""
    watch = select.poll()
    watch.register(handle, select.POLLIN)
    return bool(watch.poll(0))


@dataclass(frozen=True)
class _Ancestor:
    """A process whose place in the run is established.

    Attributes:
        pid: Its process id.
        start: Its start time.
        handle: Its process descriptor, or None for the unreaped supervisor,
            whose id cannot be reused before the launcher reaps it.
    """

    pid: int
    start: int
    handle: int | None


PINNED, GONE, STALE, UNKNOWN = "pinned", "gone", "stale", "unknown"


def _pin(pid: int, seen: _Stat, parent: _Ancestor) -> tuple[str, int]:
    """Pin ``pid`` and check that it is the process the walk saw below ``parent``.

    The process is pinned by a process descriptor first, then read again. The
    read is that process's own when the process has not ended after it. The
    pinned process is the one the walk saw when its start time is the same,
    and it is a child of ``parent`` when its live parent is ``parent``'s id
    while ``parent``, pinned or unreaped, has not ended after the read: an id
    that a live process holds cannot belong to another.

    Returns:
        ``(PINNED, handle)`` when every check holds; ``(GONE, -1)`` when the
        process is gone; ``(STALE, -1)`` when it is another process or has
        another parent; ``(UNKNOWN, -1)`` when its identity or its parent's
        cannot be established. Only a pinned descriptor stays open.
    """
    if seen.start < parent.start:
        return STALE, -1
    try:
        handle = os.pidfd_open(pid)
    except ProcessLookupError:
        return GONE, -1
    except OSError:
        return UNKNOWN, -1
    try:
        live = _stat_of(pid)
    except _Unread:
        os.close(handle)
        return UNKNOWN, -1
    if live is None or _exited(handle):
        os.close(handle)
        return GONE, -1
    if live.start != seen.start or live.parent != parent.pid:
        os.close(handle)
        return STALE, -1
    if parent.handle is not None and _exited(parent.handle):
        os.close(handle)
        return UNKNOWN, -1
    return PINNED, handle


@dataclass(frozen=True)
class _Round:
    """What one walk round found.

    Attributes:
        settled: It read every process, found the root alive and found
            nothing new, stale or not established.
        sent: Every stop signal was sent.
        full: Every target slot is taken, so the walk must stop.
    """

    settled: bool
    sent: bool
    full: bool = False


def _walk_round(
    root: int, pinned: dict[tuple[int, int], int], deadline: float
) -> _Round:
    """Pin and stop every new descendant of ``root`` that one walk can establish.

    The walk reads ``/proc`` once and goes down from ``root`` through
    established processes only: a process is visited only below a parent that
    is the unreaped root or a process this or an earlier round pinned; a
    candidate that is gone, stale or not established is neither signalled nor
    gone below (F1 of the third part F review). Each new process is stopped
    as soon as it is pinned, so it starts no other unseen.

    The deadline is checked before each process is read, before each frontier
    entry is taken and before each candidate, and nothing is sorted; a new
    process is taken only while a target slot is free (F2 of the fourth part
    F review).
    """
    table = _process_table(deadline)
    settled = table.complete
    sent = True
    found = table.stats.get(root)
    if found is None or found.state == "Z":
        # The root has ended, its children having gone to another parent, or
        # the read stopped before the root.
        return _Round(False, sent)
    frontier = deque([_Ancestor(root, found.start, None)])
    while frontier:
        if time.monotonic() >= deadline:
            return _Round(False, sent)
        parent = frontier.popleft()
        for pid in table.below.get(parent.pid, ()):
            if time.monotonic() >= deadline:
                return _Round(False, sent)
            seen = table.stats[pid]
            key = (pid, seen.start)
            if key in pinned:
                frontier.append(_Ancestor(pid, seen.start, pinned[key]))
                continue
            if len(pinned) >= TARGET_SLOTS:
                return _Round(False, sent, full=True)
            outcome, handle = _pin(pid, seen, parent)
            if outcome == PINNED:
                pinned[key] = handle
                sent &= _signalled(handle, signal.SIGSTOP, group=False)
                frontier.append(_Ancestor(pid, seen.start, handle))
                settled = False
            elif outcome != GONE or pid in table.below:
                # A gone process with children in the table has passed them
                # to another parent, which the next round reads.
                settled = False
    return _Round(settled, sent)


def _ended(handles: Sequence[int], deadline: float) -> bool:
    """Return whether every pinned process ended before ``deadline``."""
    for handle in handles:
        watch = select.poll()
        watch.register(handle, select.POLLIN)
        left = max(deadline - time.monotonic(), 0.0)
        if not watch.poll(int(left * 1000)):
            return False
    return True


def _signalled(target: int, signum: int, *, group: bool) -> bool:
    """Send ``signum`` to a process group or a pinned process.

    Returns:
        True when it was sent or the target is already gone; False on any other
        error, such as a refused permission.
    """
    try:
        if group:
            os.killpg(target, signum)
        else:
            signal.pidfd_send_signal(target, signum)
    except ProcessLookupError:
        return True
    except OSError:
        return False
    return True


def end_stalled(process: subprocess.Popen[str]) -> bool:
    """Kill a supervisor whose cleanup did not finish, and every process below it.

    The supervisor started a session of its own, so its process group is the
    supervisor's id; bubblewrap's inner layer runs in yet another session, so
    the group alone can miss it. The group is stopped first; then rounds of a
    walk of ``/proc`` (``_walk_round``) pin each descendant by a process
    descriptor, check its identity and ancestry and stop it, until a round
    settles, so that none can start another unseen. Each pinned process and
    the group are then killed. The supervisor is not reaped before its group is
    signalled, so its id cannot have been reused; a supervisor already reaped
    is not walked from or signalled at all.

    One absolute deadline, ``KILL_SECONDS`` from the call, bounds everything:
    the walk stops at ``WALK_SECONDS`` (checked before each process is read
    and indexed, each frontier entry and each candidate), and the rest is kept
    for the kills and closes, which are always sent and done, one each per
    taken process, and for the waits, which end ``CLOSE_SECONDS`` before the
    deadline so that the closes after them still end within it. The
    kill-and-close work is bounded before a process is taken: at most
    ``TARGET_SLOTS`` are taken, and the group's kill has its own slot. A walk
    that did not settle in time or ran out of slots leaves the end
    unconfirmed (F2 of the fourth part F review).

    Returns:
        True only when the walk settled, every signal was sent, the kills were
        sent before the deadline, the supervisor was reaped, every pinned
        process ended before the waits' end and the closes were done by the
        deadline; False when that is not confirmed.
    """
    started = time.monotonic()
    walk_deadline = started + WALK_SECONDS
    deadline = started + KILL_SECONDS
    waits_end = deadline - CLOSE_SECONDS
    pinned: dict[tuple[int, int], int] = {}
    sent = True
    settled = False
    confirmed = False
    try:
        if process.returncode is not None:
            # Reaped: its id may name another process now; nothing is walked.
            return False
        sent &= _signalled(process.pid, signal.SIGSTOP, group=True)
        while not settled and time.monotonic() < walk_deadline:
            found = _walk_round(process.pid, pinned, walk_deadline)
            settled = found.settled
            sent &= found.sent
            if found.full:
                break
        for handle in pinned.values():
            sent &= _signalled(handle, signal.SIGKILL, group=False)
        sent &= _signalled(process.pid, signal.SIGKILL, group=True)
        on_time = time.monotonic() < waits_end
        try:
            process.wait(timeout=max(waits_end - time.monotonic(), 0.0))
        except subprocess.TimeoutExpired:
            return False
        confirmed = (
            sent and settled and on_time and _ended(list(pinned.values()), waits_end)
        )
    finally:
        for handle in pinned.values():
            os.close(handle)
    return confirmed and time.monotonic() <= deadline


def _drain(process: subprocess.Popen[str]) -> None:
    """Read the rest of the output for at most DRAIN_SECONDS, then close it."""
    try:
        process.communicate(timeout=DRAIN_SECONDS)
    except subprocess.TimeoutExpired:
        for stream in (process.stdout, process.stderr):
            if stream is not None:
                stream.close()


def _start(
    profile: tables.Profile, argv: list[str], passed: tuple[int, ...], timeout: float
) -> SandboxResult:
    """Start bubblewrap under the supervisor with the mount descriptors and wait.

    The launcher keeps the write end of a control pipe and never writes to it;
    the supervisor holds the read end. When the launcher ends in any way, or
    closes the write end at the time limit, the supervisor kills bubblewrap and
    every process that bubblewrap leaves behind (``sandbox_supervisor``). If
    that cleanup does not finish within ``CLEANUP_SECONDS``, the launcher kills
    them itself (``end_stalled``) and says so in the time-out.
    """
    # Both ends are closed in every started program unless passed by number.
    control, keep = os.pipe()
    try:
        try:
            command = supervisor_command(control, passed, argv)
            process = subprocess.Popen(
                command,
                env={},
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                close_fds=True,
                pass_fds=tuple(sorted((*passed, control))),
                start_new_session=True,
            )
        finally:
            os.close(control)
        try:
            stdout, stderr = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            # Closing the write end makes the supervisor kill and reap every
            # process of the run; then it ends and is waited for, for a bounded
            # time only.
            os.close(keep)
            keep = -1
            stopped = f"sandbox {profile.name} timed out after {timeout:g} s; "
            try:
                process.communicate(timeout=CLEANUP_SECONDS)
            except subprocess.TimeoutExpired:
                ended = end_stalled(process)
                _drain(process)
                raise SandboxTimeout(
                    stopped
                    + "the supervisor's cleanup did not finish and its processes "
                    + (
                        "were killed by the launcher"
                        if ended
                        else "were sent a kill by the launcher, but their end is not confirmed"
                    )
                ) from None
            raise SandboxTimeout(
                f"sandbox {profile.name} timed out after {timeout:g} s; "
                "every process of the sandbox was killed"
            ) from None
    finally:
        if keep >= 0:
            os.close(keep)
    for line in stderr.splitlines():
        if process.returncode == 1 and line.startswith(SETUP_PREFIXES):
            raise SandboxSetupError(
                f"could not enter the sandbox {profile.name}: {line}"
            )
    return SandboxResult(process.returncode, stdout, stderr)


def run_in_sandbox(
    profile_name: str,
    layout: Layout,
    command: Sequence[str],
    *,
    timeout: float = tables.TIMEOUT_SECONDS,
    venv: Path | None = None,
) -> SandboxResult:
    """Run a command inside a profile and return what it did.

    The mount descriptors are passed to bubblewrap only; bubblewrap closes each
    one after its mount, so the command sees no descriptor above standard error.
    The launcher closes its own copies when the run ends, also on an error.

    Args:
        profile_name: ``build-world`` or ``build-release``.
        layout: The host folders to mount.
        command: The program (absolute path) and its arguments.
        timeout: Seconds before supervisor cleanup is requested.
        venv: The environment to use; the running one when None.

    Returns:
        The exit status and the output of the command.

    Raises:
        SandboxError: Bubblewrap is missing, or the layout does not fit.
        SandboxSetupError: Bubblewrap failed to build the sandbox.
        SandboxTimeout: The command ran longer than ``timeout``; the
            supervisor killed every process of the run, or, when its cleanup
            did not finish in time, the launcher killed them (its text says
            which, and says when their end is not confirmed).

    Every process of the run ends when the launcher ends, however it ends and
    at any moment, bubblewrap's start-up included: bubblewrap runs under
    ``sandbox_supervisor``, which refuses the run when it cannot guarantee
    that (OI-129).

    Known limit: a sandboxed program that prints a line starting ``bwrap: `` or
    ``sandbox supervisor: `` to standard error and exits with status 1 is
    raised as ``SandboxSetupError``, because bubblewrap's and the supervisor's
    own lines cannot be told from the program's (no status descriptor is used).
    """
    profile = profile_named(profile_name)
    if not os.access(tables.BWRAP, os.X_OK):
        raise SandboxError(
            f"bubblewrap is not installed at {tables.BWRAP}: install the distribution package bubblewrap"
        )
    interpreter = interpreter_for(venv if venv is not None else current_venv())
    descriptors = open_sources(profile, layout, interpreter)
    try:
        argv = build_argv(profile, layout, interpreter, command, descriptors)
        return _start(profile, argv, tuple(sorted(descriptors.values())), timeout)
    finally:
        close_all(descriptors)
