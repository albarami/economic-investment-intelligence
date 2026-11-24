"""Place one regular file under the cache's ``artefacts/`` (decision 0096).

``place_artefact`` copies a single regular file atomically to an ARC-119 path
and records its path and SHA-256 in the phase record ``assembly/artefacts.json``,
so the release spec's ``artefacts`` list is checked against computed hashes and
never typed by hand. A folder artefact does not exist under decision 0096.
"""

from __future__ import annotations

import hashlib
import os
import stat
import unicodedata
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path, PurePosixPath
from typing import Any, BinaryIO

from eii_core.manifest import canonical_json
from eii_custodian.release import pinned
from eii_custodian.release.producer import _HASH, _decode, _path

RECORD = "assembly/artefacts.json"
_METHOD = dict(method="public-assembly.artefacts", method_version="1", tables={})
_PART_BYTES = 255
_PATH_BYTES = 1024


def _relative(relative: object) -> str:
    """ARC-119: a normalised relative path of one file under ``artefacts/``.

    A path that POSIX normalisation changes, and ``..``, ``.private``, ``.env``
    and symlinked parts, are refused by the producer's own ``_path``, which
    every caller applies next.
    """
    if (
        not isinstance(relative, str)
        or unicodedata.normalize("NFC", relative) != relative
        or any(
            unicodedata.category(character) == "Cc" or character == "\\"
            for character in relative
        )
        or len(relative.encode()) > _PATH_BYTES
    ):
        raise ValueError("artefact_path_refused")
    parts = PurePosixPath(relative).parts
    if (
        len(parts) < 2
        or parts[0] != "artefacts"
        or any(len(part.encode()) > _PART_BYTES for part in parts)
    ):
        raise ValueError("artefact_path_refused")
    return relative


def recorded(data: Any) -> list[dict[str, str]]:
    """The record's ``artefacts`` list, sorted and unique by path, or refuse.

    ``data`` is an object already: ``_decode`` refuses any other JSON value.
    """
    if (
        set(data) != {*_METHOD, "artefacts"}
        or any(data[key] != value for key, value in _METHOD.items())
        or not isinstance(data["artefacts"], list)
        or any(
            not isinstance(item, dict)
            or set(item) != {"path", "sha256"}
            or not isinstance(item["path"], str)
            or not isinstance(item["sha256"], str)
            or _HASH.fullmatch(item["sha256"]) is None
            for item in data["artefacts"]
        )
        or [item["path"] for item in data["artefacts"]]
        != sorted({item["path"] for item in data["artefacts"]})
    ):
        raise ValueError("producer_schema_refused")
    return list(data["artefacts"])


@contextmanager
def _source(source_file: Path) -> Iterator[BinaryIO]:
    """Open one regular source before creating anything in the cache."""
    try:
        descriptor = os.open(
            source_file, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC
        )
    except OSError:
        raise ValueError("artefact_not_regular") from None
    if not stat.S_ISREG(os.fstat(descriptor).st_mode):
        os.close(descriptor)
        raise ValueError("artefact_not_regular")
    with os.fdopen(descriptor, "rb") as stream:
        yield stream


def _copy(stream: BinaryIO, output: BinaryIO) -> str:
    """Hash exactly the bytes copied from the pinned source descriptor."""
    digest = hashlib.sha256()
    while chunk := stream.read(1 << 20):
        digest.update(chunk)
        output.write(chunk)
    return digest.hexdigest()


def place_artefact(cache: Path, relative: str, source_file: Path) -> dict[str, str]:
    """Place ``source_file`` at ``cache/relative`` and record ``{path, sha256}``."""
    try:
        with pinned.root(cache, "artefact_path_refused") as root:
            try:
                _path(cache, _relative(relative))
                _path(cache, RECORD)
            except ValueError:
                raise ValueError("artefact_path_refused") from None
            with _source(Path(source_file)) as stream:
                with (
                    pinned.target(root, relative) as target,
                    pinned.target(root, RECORD) as phase,
                ):
                    body = pinned.read(phase)
                    entries = [] if body is None else recorded(_decode(body))
                    with pinned.publish(target, phase.check) as output:
                        placed = dict(path=relative, sha256=_copy(stream, output))
                    entries = sorted(
                        [item for item in entries if item["path"] != relative]
                        + [placed],
                        key=lambda item: item["path"],
                    )
                    with pinned.publish(phase, target.check) as output:
                        output.write(
                            canonical_json(dict(_METHOD, artefacts=entries)).encode()
                        )
    except OSError:
        raise ValueError("artefact_path_refused") from None
    return placed


__all__ = ["RECORD", "place_artefact", "recorded"]
