"""Launcher of the generator sandbox (ARC-09 to ARC-14, SYN-01).

``run_in_sandbox`` is the one entry point that ``build-world`` and
``build-release`` use. Every mount source is opened once, checked on its open
descriptor and handed to bubblewrap by descriptor, so the object that was
checked is the object that is mounted. The extension folder is an in-memory
mount of its own: its files are opened and hashed through descriptors
(``extension_tree``) and bound one by one into it, and the mount is then made
read-only, so nothing else of the host folder is visible. The proofs are in
``sandbox_check``.
"""

from __future__ import annotations

import contextlib
import os
import signal
import stat
import subprocess
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

import extension_tree
import sandbox_profiles as tables

ROOT = Path(__file__).resolve().parents[1]
BWRAP_PREFIX = "bwrap: "
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


def _start(
    profile: tables.Profile, argv: list[str], passed: tuple[int, ...], timeout: float
) -> SandboxResult:
    """Start bubblewrap with the mount descriptors and wait for it."""
    process = subprocess.Popen(
        argv,
        env={},
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        close_fds=True,
        pass_fds=passed,
        start_new_session=True,
    )
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        # The child can end after the time limit and be reaped (SIGCHLD ignored)
        # before the signal: only a group that is gone is ignored. Any other
        # error is raised, and a group that cannot be signalled is not waited for.
        with contextlib.suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGKILL)
        process.communicate()
        raise SandboxTimeout(
            f"sandbox {profile.name} timed out after {timeout:g} s; the process group was killed"
        ) from None
    for line in stderr.splitlines():
        if process.returncode == 1 and line.startswith(BWRAP_PREFIX):
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
        timeout: Seconds before the process group is killed.
        venv: The environment to use; the running one when None.

    Returns:
        The exit status and the output of the command.

    Raises:
        SandboxError: Bubblewrap is missing, or the layout does not fit.
        SandboxSetupError: Bubblewrap failed to build the sandbox.
        SandboxTimeout: The command ran longer than ``timeout``.
        OSError: The signal that ends the group failed for a reason other than a
            group that is already gone; the child is not waited for.

    Known limit: a sandboxed program that prints a line starting ``bwrap: `` to
    standard error and exits with status 1 is raised as ``SandboxSetupError``,
    because bubblewrap's own lines cannot be told from the program's (no status
    descriptor is used).
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
