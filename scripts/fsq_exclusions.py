"""Bounded, offline audit of the pinned copy's excluded file footers.

The lead supplies explicit local paths and budgets. Names from the summary
are comparison keys, never filesystem paths. No CLI, download, receipt or
production-fetch change is introduced; a result covers only these footers.
"""

from __future__ import annotations

import hashlib
import struct
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from eii_custodian.publicdata.places_fsq.constants import PINNED_RELEASE
from eii_custodian.publicdata.places_fsq.errors import PlacesFsqError
from eii_custodian.publicdata.places_fsq.footer import read_summary
from eii_custodian.publicdata.places_fsq.select import (
    FRAME_BOX,
    coordinate_bounds,
    select_partitions,
)


@dataclass(frozen=True)
class CheckedFooter:
    """An exact summary row key and digest of header, footer and trailer only."""

    name: str
    footer_sha256: str


@dataclass(frozen=True)
class ExclusionCheck:
    """Completed coverage of all exclusions named by this summary, in key order."""

    summary_footer_sha256: str
    selected: tuple[str, ...]
    checked: tuple[CheckedFooter, ...]
    method: str = "fsq_exclusions.v1"
    release: str = PINNED_RELEASE


def check_exclusions(
    summary: Path,
    excluded_files: Mapping[str, Path],
    *,
    max_files: int,
    max_footer_bytes: int,
) -> ExclusionCheck:
    """Compare every excluded footer, refusing missing/extra inputs or over-budget.

    Both budgets are explicit positive integers; max_footer_bytes includes the
    four-byte header and eight-byte trailer. Total reads are bounded by that
    budget times (max_files + 1), including the summary. A failure returns no
    coverage record. The selected-file checks remain fetch_release's job.
    """
    if (
        type(max_files) is not int
        or max_files < 1
        or type(max_footer_bytes) is not int
        or max_footer_bytes < 12
    ):
        raise PlacesFsqError("exclusion_budget_invalid")
    body = _read_footer(summary, max_footer_bytes)
    selected = select_partitions(body, PINNED_RELEASE, FRAME_BOX)
    all_names = {
        chunk.file_path
        for chunks in read_summary(body).row_groups
        for chunk in chunks
        if chunk.file_path
    }
    excluded = all_names - set(selected.files)
    if len(excluded) > max_files:
        raise PlacesFsqError("exclusion_file_limit")
    if set(excluded_files) != excluded:
        raise PlacesFsqError("exclusion_file_set")
    checked = []
    for name in sorted(excluded):
        footer = _read_footer(excluded_files[name], max_footer_bytes)
        if coordinate_bounds(footer) != coordinate_bounds(body, name):
            raise PlacesFsqError("summary_stale")
        checked.append(CheckedFooter(name, hashlib.sha256(footer).hexdigest()))
    return ExclusionCheck(
        hashlib.sha256(body).hexdigest(), selected.files, tuple(checked)
    )


def _read_footer(path: Path, limit: int) -> bytes:
    """Seek over data pages; enforce the byte budget before reading metadata.

    The envelope follows the package README's format facts N1-01 and N1-02.
    The existing footer parser checks the compact-protocol metadata itself.
    """
    try:
        with path.open("rb") as handle:
            size = handle.seek(0, 2)
            if size < 12:
                raise PlacesFsqError("metadata_unreadable")
            handle.seek(0)
            header = handle.read(4)
            handle.seek(-8, 2)
            trailer = handle.read(8)
            if header != b"PAR1" or len(trailer) != 8 or trailer[4:] != b"PAR1":
                raise PlacesFsqError("metadata_unreadable")
            length = struct.unpack("<I", trailer[:4])[0]
            if length < 1 or length > size - 12:
                raise PlacesFsqError("metadata_unreadable")
            if length + 12 > limit:
                raise PlacesFsqError("exclusion_footer_limit")
            handle.seek(size - 8 - length)
            metadata = handle.read(length)
            if len(metadata) != length:
                raise PlacesFsqError("metadata_unreadable")
            return header + metadata + trailer
    except OSError:
        raise PlacesFsqError("exclusion_file_unreadable") from None
