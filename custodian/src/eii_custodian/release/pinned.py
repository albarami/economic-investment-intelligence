"""Read and publish one file beneath a pinned cache (decision 0096).

Every traversal, read, creation, replacement and cleanup goes through
directory descriptors opened with ``O_DIRECTORY|O_NOFOLLOW``, with ``dir_fd``
on every call, so a root, parent or leaf substituted by name is refused rather
than followed. Replacement is conditional and atomic: ``renameat2`` with
``RENAME_NOREPLACE`` for a destination that was absent and ``RENAME_EXCHANGE``,
with a check of the displaced leaf and a rollback, for one that existed. A
displaced file is never unlinked on an exceptional exit: when the rollback
cannot complete it is kept under its temporary name and the refusal is
``publication_rollback_incomplete``. A
system without ``renameat2`` refuses as ``publication_rename_unsupported``;
there is no fallback to a plain rename. Standard library only, so both writers
of the release package may use it.
"""

from __future__ import annotations

import ctypes
import errno
import os
import stat
import uuid
from collections.abc import Callable, Iterator
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import BinaryIO, NoReturn

UNSUPPORTED = "publication_rename_unsupported"
ROLLBACK_INCOMPLETE = "publication_rollback_incomplete"
RENAME_NOREPLACE = 1
RENAME_EXCHANGE = 2
_DIRECTORY_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
_LIBC = ctypes.CDLL(None, use_errno=True)

Identity = tuple[int, int, int]


def _renameat2(parent: int, source: str, destination: str, flags: int) -> None:
    """Rename within one pinned directory, or refuse; never a plain rename."""
    function = getattr(_LIBC, "renameat2", None)
    if function is None:
        raise ValueError(UNSUPPORTED)
    function.argtypes = [
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_uint,
    ]
    function.restype = ctypes.c_int
    if function(parent, os.fsencode(source), parent, os.fsencode(destination), flags):
        code = ctypes.get_errno()
        if code in (errno.ENOSYS, errno.EINVAL):
            raise ValueError(UNSUPPORTED)
        raise OSError(code, os.strerror(code))


def _identity(parent: int, name: str) -> Identity | None:
    """Read an entry's identity without following a link; absence is distinct."""
    try:
        info = os.stat(name, dir_fd=parent, follow_symlinks=False)
    except FileNotFoundError:
        return None
    return info.st_dev, info.st_ino, info.st_mode


@dataclass
class Target:
    parent: int
    name: str
    directories: list[tuple[int, str, int]]
    identity: Identity | None
    reason: str

    def refuse(self) -> NoReturn:
        raise ValueError(self.reason)

    def check(self) -> None:
        """Every pinned directory and the destination must still have its name."""
        for parent, name, descriptor in self.directories:
            info = os.fstat(descriptor)
            if _identity(parent, name) != (info.st_dev, info.st_ino, info.st_mode):
                self.refuse()
        if _identity(self.parent, self.name) != self.identity:
            self.refuse()


def _pin(
    parent: int, name: str, directories: list[tuple[int, str, int]], stack: ExitStack
) -> int:
    """Retain one no-follow directory descriptor and its parent/name binding."""
    descriptor = os.open(name, _DIRECTORY_FLAGS, dir_fd=parent)
    stack.callback(os.close, descriptor)
    directories.append((parent, name, descriptor))
    return descriptor


@contextmanager
def root(cache: Path, reason: str) -> Iterator[Target]:
    """Pin the cache and its ancestry; ``reason`` names every identity refusal."""
    with ExitStack() as stack:
        parent = os.open("/", _DIRECTORY_FLAGS)
        stack.callback(os.close, parent)
        directories: list[tuple[int, str, int]] = []
        for name in cache.absolute().parts[1:]:
            parent = _pin(parent, name, directories, stack)
        pinned = Target(parent, ".", directories, _identity(parent, "."), reason)
        pinned.check()
        yield pinned


@contextmanager
def target(root: Target, relative: str, create: bool = True) -> Iterator[Target]:
    """Pin a destination's folders beneath the pinned cache, creating them only
    when ``create``; a missing folder of a read raises ``FileNotFoundError``."""
    parts = PurePosixPath(relative).parts
    if (
        str(PurePosixPath(relative)) != relative
        or not parts
        or parts[0] == "/"
        or ".." in parts
    ):
        root.refuse()
    root.check()
    with ExitStack() as stack:
        parent = root.parent
        directories = list(root.directories)
        for name in parts[:-1]:
            try:
                if create:
                    os.mkdir(name, dir_fd=parent)
            except FileExistsError:
                pass
            parent = _pin(parent, name, directories, stack)
        identity = _identity(parent, parts[-1])
        if identity is not None and not stat.S_ISREG(identity[2]):
            root.refuse()
        leaf = Target(parent, parts[-1], directories, identity, root.reason)
        leaf.check()
        yield leaf


def read(leaf: Target) -> bytes | None:
    """The pinned leaf's bytes, opened without following a link, or None if absent.

    Only a leaf absent when pinned is absent; one that disappears afterwards
    is refused."""
    if leaf.identity is None:
        return None
    try:
        descriptor = os.open(
            leaf.name,
            os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC,
            dir_fd=leaf.parent,
        )
    except FileNotFoundError:
        leaf.refuse()
    with os.fdopen(descriptor, "rb") as stream:
        info = os.fstat(stream.fileno())
        if (info.st_dev, info.st_ino, info.st_mode) != leaf.identity:
            leaf.refuse()
        body = stream.read()
    leaf.check()
    return body


def _unlink_owned(parent: int, name: str, owned: Identity) -> bool:
    """Remove ``name`` only while it still holds the owned identity; an entry
    gone at the check or at the unlink is absent and not owned."""
    if _identity(parent, name) != owned:
        return False
    try:
        os.unlink(name, dir_fd=parent)
    except FileNotFoundError:
        return False
    return True


def _roll_back(leaf: Target, temporary: str, owned: Identity) -> str | None:
    """Undo an exchange on an exceptional exit; a reason when it cannot complete.

    Nothing but the owned file is ever unlinked here. The exchange back runs
    only while the target is still the owned one and must leave the owned file
    under the temporary name; otherwise, or if it fails, whatever the
    temporary name holds (the displaced file) stays there for recovery and the
    owned target is withdrawn only while it is still the owned one."""
    if _identity(leaf.parent, leaf.name) == owned:
        try:
            _renameat2(leaf.parent, temporary, leaf.name, RENAME_EXCHANGE)
        except (OSError, ValueError):
            pass
        else:
            if _unlink_owned(leaf.parent, temporary, owned):
                return None
    _unlink_owned(leaf.parent, leaf.name, owned)
    return ROLLBACK_INCOMPLETE


@contextmanager
def publish(
    leaf: Target, check: Callable[[], None] = lambda: None, replace: bool = True
) -> Iterator[BinaryIO]:
    """Write a temporary file and conditionally, atomically put it in place.

    Without ``replace`` the rename is always ``RENAME_NOREPLACE``, whatever
    the leaf held when pinned, so a leaf that exists raises
    ``FileExistsError`` and is left untouched. On an exceptional exit only
    the owned file is ever removed; an exchange is rolled back, or refused as
    ``publication_rollback_incomplete`` with the displaced file kept."""
    temporary = "." + uuid.uuid4().hex + ".partial"
    handle = os.open(
        temporary,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
        0o600,
        dir_fd=leaf.parent,
    )
    with os.fdopen(handle, "wb") as output:
        info = os.fstat(output.fileno())
        owned: Identity = info.st_dev, info.st_ino, info.st_mode
        displaced = leaf.identity
        # The displaced identity once the exchange has run, else None.
        exchanged: Identity | None = None
        try:
            yield output
            output.flush()
            os.fsync(output.fileno())
            leaf.check()
            check()
            if _identity(leaf.parent, temporary) != owned:
                leaf.refuse()
            if displaced is None or not replace:
                _renameat2(leaf.parent, temporary, leaf.name, RENAME_NOREPLACE)
            else:
                _renameat2(leaf.parent, temporary, leaf.name, RENAME_EXCHANGE)
                exchanged = displaced
                if _identity(leaf.parent, temporary) != displaced:
                    leaf.refuse()
            leaf.identity = owned
            leaf.check()
            check()
        except BaseException as error:
            leaf.identity = displaced
            if exchanged is None:
                _unlink_owned(leaf.parent, temporary, owned)
                _unlink_owned(leaf.parent, leaf.name, owned)
            elif reason := _roll_back(leaf, temporary, owned):
                raise ValueError(reason) from error
            raise
    if exchanged is not None:
        _unlink_owned(leaf.parent, temporary, exchanged)


__all__ = [
    "ROLLBACK_INCOMPLETE",
    "UNSUPPORTED",
    "Target",
    "publish",
    "read",
    "root",
    "target",
]
