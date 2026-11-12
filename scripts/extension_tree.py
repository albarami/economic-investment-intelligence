"""What the project-local DuckDB extension folder must hold, checked by descriptor.

The pinned table names the files of each engine version and platform. Each
part of the folder is opened relative to the descriptor of its parent without
following a symbolic link, and each file is checked and hashed through its own
descriptor. ``open_tree`` hands the open descriptors of the checked files to
the launcher, which binds exactly these objects into the sandbox (ARC-14);
``check_folder`` is the same check by path for ``fetch`` and ``verify``.
"""

from __future__ import annotations

import errno
import hashlib
import os
import stat
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

PLATFORM = "linux_amd64"
# The engine version whose extension files are pinned below (the root group engine).
ENGINE = "v2.0.0"
FETCH_COMMAND = "uv run --locked python scripts/engine_extensions.py fetch"
BINARY = ".duckdb_extension"
INFO = ".duckdb_extension.info"
# (engine version, platform) -> name -> (size in bytes, SHA-256) of the extension file.
PINNED = {
    (ENGINE, PLATFORM): {
        "h3": (
            520_766,
            "abba3f5702e6917804a1e05be20013b51d2174e296b175f0a3fdfc2eeffd6352",
        ),
        "spatial": (
            108_189_118,
            "8ec99d875355200316c743ede176e2cb50d2b712d2fa192ccbf19cc245a8d0bc",
        ),
    },
}
Pinned = dict[tuple[str, str], dict[str, tuple[int, str]]]
# A folder is opened as a path descriptor that does not follow a symbolic link
# (a link gives a descriptor of the link itself); a file is opened for reading
# without following a link (a link fails with ELOOP), and O_NONBLOCK keeps a
# planted FIFO from blocking the open.
PART_FLAGS = os.O_PATH | os.O_NOFOLLOW | os.O_CLOEXEC
LIST_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC
FILE_FLAGS = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC
READ_BLOCK = 1 << 20
DESCRIPTOR_LINK = "/proc/self/fd/{}"


@dataclass(frozen=True)
class Verified:
    """One file of the extension folder, checked through its open descriptor.

    Attributes:
        relative: Its path below the folder, for example
            ``v2.0.0/linux_amd64/h3.duckdb_extension``.
        descriptor: The descriptor it was opened, checked and hashed through.
        size: Its size in bytes.
        sha256: Its SHA-256 for an extension binary; None for an ``.info`` file.
    """

    relative: str
    descriptor: int
    size: int
    sha256: str | None


class _Refused(Exception):
    """A part of the extension folder is not as required; the text says why."""


def required_files(
    engine: str, pinned: Pinned | None = None
) -> dict[str, tuple[int, str] | None]:
    """Name the files the platform folder must hold for an engine version.

    Args:
        engine: The engine version tag, for example ``v2.0.0``.
        pinned: The table of pinned sizes and hashes; ``PINNED`` when None.

    Returns:
        File name -> pinned (size, SHA-256) for a binary, None for an ``.info``
        file, sorted by name; empty when the version has no pinned row.
    """
    row = (PINNED if pinned is None else pinned).get((engine, PLATFORM), {})
    wanted: dict[str, tuple[int, str] | None] = {}
    for name, pin in row.items():
        wanted[name + BINARY] = pin
        wanted[name + INFO] = None
    return dict(sorted(wanted.items()))


def relative_files(engine: str, pinned: Pinned | None = None) -> list[str]:
    """Return the paths below the folder of the files of ``required_files``."""
    return [f"{engine}/{PLATFORM}/{name}" for name in required_files(engine, pinned)]


def close_files(files: Sequence[Verified]) -> None:
    """Close the descriptors of checked files."""
    for item in files:
        os.close(item.descriptor)


def _sha256(descriptor: int) -> str:
    """Hash a file through its descriptor; the name is not looked up again."""
    digest = hashlib.sha256()
    offset = 0
    while block := os.pread(descriptor, READ_BLOCK, offset):
        digest.update(block)
        offset += len(block)
    return digest.hexdigest()


def _open_folder(parent: int, name: str, label: str) -> int:
    """Open a folder below ``parent`` without following a symbolic link."""
    try:
        descriptor = os.open(name, PART_FLAGS, dir_fd=parent)
    except FileNotFoundError:
        raise _Refused(f"{label} is missing: run {FETCH_COMMAND}") from None
    except OSError as error:
        raise _Refused(f"{label} cannot be opened ({type(error).__name__})") from None
    try:
        mode = os.fstat(descriptor).st_mode
    except OSError:
        os.close(descriptor)
        raise
    if not stat.S_ISDIR(mode):
        os.close(descriptor)
        raise _Refused(
            f"{label} is a symbolic link"
            if stat.S_ISLNK(mode)
            else f"{label} is not a folder"
        )
    return descriptor


def _judge_file(descriptor: int, label: str, pin: tuple[int, str] | None) -> Verified:
    """Check an open file: kind, one name, size and, for a binary, the pin."""
    status = os.fstat(descriptor)
    if not stat.S_ISREG(status.st_mode):
        raise _Refused(f"{label} is not a regular file")
    if status.st_nlink != 1:
        raise _Refused(f"{label} has {status.st_nlink} hard links, expected 1")
    if status.st_size == 0:
        raise _Refused(f"{label} is empty")
    digest = None
    if pin is not None:
        size, pinned_digest = pin
        if status.st_size != size:
            raise _Refused(f"{label} has size {status.st_size}, pinned {size}")
        digest = _sha256(descriptor)
        if digest != pinned_digest:
            raise _Refused(
                f"{label} has a SHA-256 that differs from the pinned {pinned_digest}"
            )
    return Verified(label, descriptor, status.st_size, digest)


def _open_file(
    parent: int, name: str, label: str, pin: tuple[int, str] | None
) -> Verified:
    """Open a file below ``parent`` without following a link and check it."""
    try:
        descriptor = os.open(name, FILE_FLAGS, dir_fd=parent)
    except FileNotFoundError:
        raise _Refused(f"{label} is missing: run {FETCH_COMMAND}") from None
    except OSError as error:
        if error.errno == errno.ELOOP:
            raise _Refused(f"{label} is a symbolic link") from None
        raise _Refused(f"{label} cannot be opened ({type(error).__name__})") from None
    try:
        return _judge_file(descriptor, label, pin)
    except (OSError, _Refused):
        os.close(descriptor)
        raise


def _names(folder: int) -> list[str]:
    """List the entries of an open folder through a reading descriptor of it."""
    listing = os.open(".", LIST_FLAGS, dir_fd=folder)
    try:
        return sorted(os.listdir(listing))
    finally:
        os.close(listing)


def open_tree(
    root: int, engine: str, pinned: Pinned | None = None
) -> tuple[list[Verified] | None, list[str]]:
    """Open and check the extension files below an open extension folder.

    The version folder, the platform folder and each file are opened relative
    to the descriptor of their parent, and no symbolic link is followed in any
    of them. Each file must be a regular file with one name; a binary must have
    its pinned size and SHA-256, read through its descriptor; an ``.info`` file
    must not be empty; the platform folder holds nothing else. Other entries of
    the extension folder and of the version folder are not looked at.

    Args:
        root: An open descriptor of the extension folder.
        engine: The engine version tag, for example ``v2.0.0``.
        pinned: The table of pinned sizes and hashes; ``PINNED`` when None.

    Returns:
        ``(None, [])`` when the folder holds no entry at all; else the checked
        files, open and in the order of ``required_files``, and no problem;
        else an empty list and one problem text per difference, and nothing
        stays open.
    """
    wanted = required_files(engine, pinned)
    if not wanted:
        return [], [
            f"no pinned hashes for engine {engine} on {PLATFORM}: review the files "
            "and record them in scripts/extension_tree.py"
        ]
    files: list[Verified] = []
    problems: list[str] = []
    folders: list[int] = []
    base = f"{engine}/{PLATFORM}"
    try:
        if not _names(root):
            return None, []
        folders.append(_open_folder(root, engine, engine))
        folders.append(_open_folder(folders[0], PLATFORM, base))
        for name, pin in wanted.items():
            try:
                files.append(_open_file(folders[1], name, f"{base}/{name}", pin))
            except _Refused as refused:
                problems.append(str(refused))
        problems += [
            f"unexpected entry {base}/{name}"
            for name in _names(folders[1])
            if name not in wanted
        ]
    except _Refused as refused:
        problems.append(str(refused))
    except OSError as error:
        problems.append(f"the extension folder cannot be read ({type(error).__name__})")
    finally:
        for descriptor in folders:
            os.close(descriptor)
    if problems:
        close_files(files)
        return [], problems
    return files, []


def open_folder(
    folder: Path, engine: str, pinned: Pinned | None = None
) -> tuple[list[Verified], list[str]]:
    """Open the extension folder by its path and check its files (``open_tree``).

    Args:
        folder: The absolute path of the folder; no part of it may be a link.
        engine: The engine version tag.
        pinned: The table of pinned sizes and hashes; ``PINNED`` when None.

    Returns:
        The checked files, open (the caller closes them with ``close_files``),
        and no problem; or an empty list and the problems. An empty folder is a
        problem here: nothing was fetched.
    """
    try:
        root = os.open(folder, PART_FLAGS)
    except FileNotFoundError:
        return [], [f"the extension folder is missing: run {FETCH_COMMAND}"]
    except OSError as error:
        return [], [f"the extension folder cannot be opened ({type(error).__name__})"]
    try:
        mode = os.fstat(root).st_mode
        seen = os.readlink(DESCRIPTOR_LINK.format(root))
        if stat.S_ISLNK(mode) or seen != str(folder):
            return [], ["the extension folder is or lies below a symbolic link"]
        if not stat.S_ISDIR(mode):
            return [], ["the extension folder is not a folder"]
        files, problems = open_tree(root, engine, pinned)
    except OSError as error:
        return [], [f"the extension folder cannot be read ({type(error).__name__})"]
    finally:
        os.close(root)
    if files is None:
        return [], [f"{engine} is missing: run {FETCH_COMMAND}"]
    return files, problems


def check_folder(folder: Path, engine: str, pinned: Pinned | None = None) -> list[str]:
    """Compare the files of the extension folder with the pinned table.

    Args:
        folder: The absolute path of the project-local extension folder.
        engine: The engine version tag, for example ``v2.0.0``.
        pinned: The table of pinned sizes and hashes; ``PINNED`` when None.

    Returns:
        One problem text per difference; empty when the folder is as pinned.
    """
    files, problems = open_folder(folder, engine, pinned)
    close_files(files)
    return problems
