"""Choose the data files whose row-group coordinates meet the frame.

The bounding box in a file's own geographic metadata is recorded and never
used. A point on the frame edge counts as inside.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from eii_custodian.publicdata.places_fsq.errors import PlacesFsqError
from eii_custodian.publicdata.places_fsq.footer import ChunkStat, read_summary

_RELEASE_IN_PATH = re.compile(r"(?:^|/)(\d{4}-\d{2}-\d{2})(?:/|$)")
_LONGITUDE = ("longitude",)
_LATITUDE = ("latitude",)


@dataclass(frozen=True)
class FrameBox:
    """Inclusive longitude and latitude bounds of the frame, degrees."""

    west: float
    south: float
    east: float
    north: float


# The box the lead's facts file used for this frame: section 2 of that note.
FRAME_BOX = FrameBox(west=50.7, south=24.4, east=51.7, north=26.2)


@dataclass(frozen=True)
class IgnoredGeo:
    """A geographic bbox that was present and was not used to choose a file."""

    file_path: str
    bbox: tuple[float, float, float, float]


@dataclass(frozen=True)
class Selection:
    """The files to fetch, in name order, and the bboxes that were ignored."""

    files: tuple[str, ...]
    ignored_geo: tuple[IgnoredGeo, ...]
    release: str


def select_partitions(body: bytes, release: str, frame: FrameBox) -> Selection:
    """Return the files of one release whose coordinate statistics meet the frame."""
    summary = read_summary(body)
    chosen: set[str] = set()
    ignored: dict[str, tuple[float, float, float, float]] = {}
    if summary.dataset_geo_bbox is not None:
        ignored[""] = summary.dataset_geo_bbox
    for chunks in summary.row_groups:
        file_path, bounds, geo = _group(chunks)
        _release_of(file_path, release)
        if geo is not None:
            ignored[file_path] = geo
        if _meets(bounds[0], bounds[1], bounds[2], bounds[3], frame):
            chosen.add(file_path)
    if not chosen:
        raise PlacesFsqError("no_file_for_frame")
    basenames = [path.rsplit("/", 1)[-1] for path in chosen]
    if len(set(basenames)) != len(basenames):
        raise PlacesFsqError("file_name_duplicate")
    recorded = tuple(IgnoredGeo(path, bbox) for path, bbox in sorted(ignored.items()))
    return Selection(tuple(sorted(chosen)), recorded, release)


def _group(
    chunks: tuple[ChunkStat, ...],
) -> tuple[
    str, tuple[float, float, float, float], tuple[float, float, float, float] | None
]:
    longitude = _axis(chunks, _LONGITUDE)
    latitude = _axis(chunks, _LATITUDE)
    paths = {chunk.file_path for chunk in chunks if chunk.file_path}
    if len(paths) != 1:
        raise PlacesFsqError("file_path_missing")
    file_path = next(iter(paths))
    geo = next((chunk.geo_bbox for chunk in chunks if chunk.geo_bbox is not None), None)
    return file_path, (longitude[0], longitude[1], latitude[0], latitude[1]), geo


def _axis(chunks: tuple[ChunkStat, ...], path: tuple[str, ...]) -> tuple[float, float]:
    found = [chunk for chunk in chunks if chunk.path == path]
    if len(found) != 1 or found[0].minimum is None or found[0].maximum is None:
        raise PlacesFsqError("statistics_missing")
    return found[0].minimum, found[0].maximum


def _meets(minx: float, maxx: float, miny: float, maxy: float, frame: FrameBox) -> bool:
    return (
        minx <= frame.east
        and maxx >= frame.west
        and miny <= frame.north
        and maxy >= frame.south
    )


def _release_of(file_path: str, release: str) -> None:
    match = _RELEASE_IN_PATH.search(file_path)
    if match is not None and match.group(1) != release:
        raise PlacesFsqError("release_mismatch")


def coordinate_bounds(
    body: bytes, file_path: str | None = None
) -> tuple[float, float, float, float]:
    """Aggregate all row groups of a file; None reads a data file without paths."""
    bounds = []
    for chunks in read_summary(body).row_groups:
        if file_path is not None:
            path, bound, _geo = _group(chunks)
            if path != file_path:
                continue
        else:
            longitude = _axis(chunks, _LONGITUDE)
            latitude = _axis(chunks, _LATITUDE)
            bound = (*longitude, *latitude)
        bounds.append(bound)
    if not bounds:
        raise PlacesFsqError("statistics_missing")
    return (
        min(b[0] for b in bounds),
        max(b[1] for b in bounds),
        min(b[2] for b in bounds),
        max(b[3] for b in bounds),
    )
