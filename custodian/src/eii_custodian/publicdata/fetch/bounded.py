"""One bounded metadata read, archive stream and immutable publication."""

from __future__ import annotations

import hashlib
import os
from collections.abc import Callable
from pathlib import Path
from typing import NoReturn

from eii_custodian.publicdata.fetch.allowlist import host_of
from eii_custodian.publicdata.fetch.transport import (
    ATTEMPT_LIMIT,
    BACKOFF_S,
    MAX_RETRIES,
    StreamTransport,
    Transport,
    TransportFault,
    TransportReadError,
)

CHUNK_BYTES = 65536
ACCESS_MARKERS = (
    b"registration required",
    b"sign in",
    b"robot check",
    b"paid tier",
)
Refuse = Callable[[str], NoReturn]
Review = Callable[[str], None]


def file_hash(path: Path) -> str:
    """SHA-256 of a file, read in fixed chunks."""
    result = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(CHUNK_BYTES):
            result.update(chunk)
    return result.hexdigest()


def within(value: int, span: tuple[int, int]) -> bool:
    """Inclusive on both ends."""
    return span[0] <= value <= span[1]


def publish_complete(path: Path, destination: Path, refuse: Refuse) -> None:
    """Link content-addressed bytes. A different occupant of the name is refused."""
    if destination.exists():
        if file_hash(destination) != file_hash(path):
            refuse("cache_integrity")
        return
    os.link(path, destination)


def read_metadata(
    url: str,
    transport: Transport,
    *,
    review: Review,
    max_bytes: int,
    sleep: Callable[[float], None],
    refuse: Refuse,
) -> bytes:
    """Read one reviewed metadata body. Access markers stop the fetch."""
    review(url)
    for attempt in range(ATTEMPT_LIMIT):
        try:
            response = transport(url)
            for address in (*response.hops, response.final_url):
                review(address)
            if len(response.body) > max_bytes:
                refuse("metadata_bytes")
            folded = response.body.lower()
            for marker in ACCESS_MARKERS:
                if marker in folded:
                    refuse("access_obstacle")
            return response.body
        except (RuntimeError, TypeError, AttributeError, ValueError):
            refuse("transport_metadata_invalid")
        except (TransportFault, OSError, TransportReadError) as exc:
            if isinstance(exc, TransportFault) and exc.kind == "blocked_host":
                refuse("blocked_host")
            if attempt < MAX_RETRIES:
                sleep(BACKOFF_S[attempt])
    refuse("network_exhausted")


def stream_download(
    url: str,
    transport: StreamTransport,
    target: Path,
    *,
    review: Review,
    byte_bounds: tuple[int, int],
    sleep: Callable[[float], None],
    refuse: Refuse,
) -> str:
    """Stream one reviewed archive into target. No partial file is reused."""
    for attempt in range(ATTEMPT_LIMIT):
        try:
            with transport(url) as response:
                for address in (*response.hops, response.final_url):
                    review(address)
                length = response.declared_length
                if length is not None and type(length) is not int:
                    refuse("declared_length")
                if length is not None and not within(length, byte_bounds):
                    refuse("archive_bytes")
                count = 0
                with target.open("wb") as output:
                    for chunk in response.chunks:
                        if type(chunk) is not bytes or len(chunk) > CHUNK_BYTES:
                            refuse("stream_chunk")
                        count += len(chunk)
                        if count > byte_bounds[1]:
                            refuse("archive_bytes")
                        output.write(chunk)
                if not within(count, byte_bounds):
                    refuse("archive_bytes")
                if length is not None and length != count:
                    refuse("length_mismatch")
                return host_of(response.final_url)
        except (TransportFault, OSError, TransportReadError) as exc:
            if isinstance(exc, TransportFault) and exc.kind == "blocked_host":
                refuse("blocked_host")
            target.unlink(missing_ok=True)
            if attempt < MAX_RETRIES:
                sleep(BACKOFF_S[attempt])
    refuse("network_exhausted")
