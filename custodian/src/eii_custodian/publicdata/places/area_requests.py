"""The one list of area requests. The producer and the provider both use it."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from eii_custodian.publicdata.places.area_files import AreaRequest, coordinate_text
from eii_custodian.publicdata.places.areas import AreaCutoff, AreaMode
from eii_custodian.publicdata.places.review import (
    load_flagship_candidates,
    load_showcase_areas,
)

_CANDIDATE_AREAS = (
    (AreaMode.WALK, AreaCutoff.MINUTES_5),
    (AreaMode.WALK, AreaCutoff.MINUTES_10),
    (AreaMode.DRIVE, AreaCutoff.MINUTES_10),
)


def area_requests(
    review: Path,
    points: Mapping[tuple[str, str], tuple[float, float]],
) -> tuple[AreaRequest, ...]:
    """One list for the producer and the provider. Coordinates are canonical text."""
    found: dict[tuple[str, str, int], AreaRequest] = {}
    for item in load_showcase_areas(review / "showcase_areas.yaml", None)[1]:
        _remember(
            found,
            item,
            points,
            _mode(item.get("mode")),
            _cutoff(item.get("cutoff_minutes")),
        )
    for item in load_flagship_candidates(review / "flagship_candidates.yaml", None)[1]:
        for mode, cutoff in _CANDIDATE_AREAS:
            _remember(found, item, points, mode, cutoff)
    return tuple(found[key] for key in sorted(found))


def _remember(
    found: dict[tuple[str, str, int], AreaRequest],
    item: Mapping[str, object],
    points: Mapping[tuple[str, str], tuple[float, float]],
    mode: AreaMode | None,
    cutoff: AreaCutoff | None,
) -> None:
    if mode is None or cutoff is None:
        return
    source = item.get("source_id")
    record = item.get("record_key")
    place_key = item.get("place_key")
    if not isinstance(source, str) or source == "":
        return
    if not isinstance(record, str) or record == "":
        return
    if not isinstance(place_key, str) or place_key == "":
        return
    pair = points.get((source, record))
    if pair is None:
        return
    found[(place_key, mode.value, cutoff.value)] = AreaRequest(
        place_key,
        coordinate_text(pair[0]),
        coordinate_text(pair[1]),
        mode,
        cutoff,
    )


def _mode(value: object) -> AreaMode | None:
    if not isinstance(value, str):
        return None
    try:
        return AreaMode(value)
    except ValueError:
        return None


def _cutoff(value: object) -> AreaCutoff | None:
    if not isinstance(value, int):
        return None
    try:
        return AreaCutoff(value)
    except ValueError:
        return None
