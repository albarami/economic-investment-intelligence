"""Places producer and stage inside the public build. No new command."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date
from pathlib import Path

import yaml
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

from eii_custodian.publicdata.assembly_log import _BUILD_LINES as _BUILD_LINES
from eii_custodian.publicdata.assembly_log import build_lines as build_lines
from eii_custodian.publicdata.assembly_log import observe
from eii_custodian.publicdata.building_inputs import BuildingError, invalidate_buildings
from eii_custodian.publicdata.fetch.registry import Entry, load_registry
from eii_custodian.publicdata.fetch.snapshots import (
    SnapshotError,
    read_snapshot,
    reviewed_selections,
)
from eii_custodian.publicdata.places import PlacesError
from eii_custodian.publicdata.places.area_files import (
    manifest_agrees,
    open_pinned_engine,
    produce_areas,
    road_receipt,
)
from eii_custodian.publicdata.places.area_requests import area_requests
from eii_custodian.publicdata.places.areas import AreaError
from eii_custodian.publicdata.places.fetch import FILE_KEYS
from eii_custodian.publicdata.places.read import (
    FileReceipt,
    read_building_file,
    read_place_file,
)
from eii_custodian.publicdata.places.stage import StageConfig, run_places_stage
from eii_custodian.publicdata.places_fsq.select import FRAME_BOX

_NOTHING = "areas: nothing to do"
_REVIEW_UNREADABLE = "REFUSED review_unreadable"
_TAG_FILE = "arabic_tag.txt"
_PLACES_SOURCE = "places_ovt"
_BUILDINGS_SOURCE = "bldg_ovt"
_FRAME = (FRAME_BOX.west, FRAME_BOX.south, FRAME_BOX.east, FRAME_BOX.north)
_READER_ERRORS = (yaml.YAMLError, OSError, UnicodeError, ValueError, TypeError)


def frame_when_ready(
    cache: Path,
    entries: Sequence[Entry],
    lines: list[str] | None = None,
    *,
    build_date: date | None = None,
    selections: Mapping[str, str] | None = None,
) -> None:
    """Build the frame only when its boundary source is already in the cache."""
    from eii_custodian.publicdata.frame.municipality_output import (
        MUNICIPALITY_OUTPUT,
    )

    (cache / MUNICIPALITY_OUTPUT).unlink(missing_ok=True)
    invalidate_buildings(cache)
    hdx = next(
        (
            item
            for item in entries
            if item.source_id == "bnd_hdx" and item.skip_reason == ""
        ),
        None,
    )
    if hdx is None or not any((cache / hdx.key).glob("*.meta.json")):
        return
    review = cache.parent.parent / "custodian" / "publicdata" / "review"
    if not (review / "showcase_gazetteer.yaml").is_file():
        return
    from eii_custodian.publicdata.frame.build import build_public_frame
    from eii_custodian.publicdata.frame.checks import FrameError
    from eii_custodian.publicdata.frame.municipality_output import (
        write_municipality_output,
    )

    log = lines if lines is not None else []
    with build_lines(log):
        try:
            result = build_public_frame(
                cache,
                tuple(entries),
                review,
                None,
                build_date=build_date,
                selections=selections,
            )
        except BuildingError as exc:
            log.append(f"FAIL buildings check={exc.name}")
            raise
        except FrameError:
            _note(log, "frame", "frame_refused")
        else:
            if result is not None:
                write_municipality_output(
                    cache, result.tables["municipality"], result.sources
                )


def areas_before_stage(
    cache: Path, lines: list[str], review: Path | None = None
) -> None:
    """Produce areas after the road receipt. A matching manifest does nothing."""
    try:
        road_sha = road_receipt(cache)
    except AreaError as exc:
        _observe(exc)
        return
    chosen = review if review is not None else _review_directory(cache)
    if chosen is None:
        return
    try:
        requests = area_requests(chosen, _cache_points(cache, chosen))
    except AreaError as exc:
        _area_refusal(lines, exc)
        return
    except PlacesError as exc:
        _area_refusal(lines, exc)
        return
    except _READER_ERRORS as exc:
        lines.append(_REVIEW_UNREADABLE)
        _observe(exc)
        return
    if not requests or manifest_agrees(cache, requests, road_sha):
        lines.append(_NOTHING)
        return
    try:
        engine = open_pinned_engine()
        produce_areas(engine, requests, cache=cache, frame_box=_FRAME)
    except AreaError as exc:
        _area_refusal(lines, exc)


def run_places_before_gazetteer(
    cache: Path,
    review: Path,
    registry: Sequence[Entry],
    boundaries: Sequence[BaseGeometry],
    grid: Sequence[Mapping[str, object]],
    zones: Mapping[str, BaseGeometry],
    lines: list[str] | None = None,
    *,
    build_date: date | None = None,
) -> None:
    """Run the stage where the frame can hand over boundary, grid and zones."""
    log = lines if lines is not None else _BUILD_LINES.get()
    tag = _tag(review)
    if tag == "":
        _note(log, "places", "arabic_tag_missing")
        return
    located = _place_from_registry(cache, registry)
    if located is None:
        _note(log, "places", "places_file_unreceipted")
        return
    boundary = _boundary(boundaries)
    if boundary is None:
        _note(log, "places", "frame_boundary_missing")
        return
    path, receipt = located
    building_paths, building_receipts = _buildings_from_registry(cache, registry)
    try:
        run_places_stage(
            StageConfig(
                cache=cache,
                review=review,
                build_date=build_date,
                arabic_tag=tag,
                boundary=boundary,
                grid=grid,
                zones=zones,
                places_path=path,
                places_receipt=receipt,
                buildings_paths=building_paths,
                buildings_receipts=building_receipts,
            )
        )
    except PlacesError as exc:
        _refuse_stage(cache, log, exc.reason)


def _review_directory(cache: Path) -> Path | None:
    candidate = cache.parent.parent / "custodian" / "publicdata" / "review"
    if (candidate / "showcase_gazetteer.yaml").is_file():
        return candidate
    return None


def _tag(review: Path) -> str:
    path = review / _TAG_FILE
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8").strip()


def _cache_points(
    cache: Path, review: Path
) -> dict[tuple[str, str], tuple[float, float]]:
    found: dict[tuple[str, str], tuple[float, float]] = {}
    tag = _tag(review)
    for key in (key for key in FILE_KEYS if key.startswith(_PLACES_SOURCE)):
        located = _opened_place(cache, key)
        if located is None:
            continue
        path, _receipt = located
        try:
            if tag == "":
                continue
            for row in read_place_file(path, tag):
                found[(_PLACES_SOURCE, row.place_id)] = (float(row.lon), float(row.lat))
        except PlacesError as exc:
            _observe(exc)
            continue
    for key in (key for key in FILE_KEYS if key.startswith(_BUILDINGS_SOURCE + "/")):
        _opened_place(cache, key)
    registry = load_registry()
    selections = reviewed_selections(cache)
    for entry in _building_entries(registry):
        if entry.key in selections and _receipt_of(cache, entry) is None:
            raise AreaError("places_file_digest")
    building_paths, _receipts = _buildings_from_registry(cache, registry)
    for path in building_paths:
        try:
            for building in read_building_file(path, frame_box=_FRAME):
                found[(_BUILDINGS_SOURCE, building.building_id)] = (
                    float(building.lon),
                    float(building.lat),
                )
        except PlacesError as exc:
            _observe(exc)
            continue
    return found


def _opened_place(cache: Path, key: str) -> tuple[Path, FileReceipt] | None:
    """Return one body only after its receipt matches. A bare file is refused."""
    if key not in reviewed_selections(cache):
        if (cache / key).is_dir():
            raise AreaError("places_file_unreceipted")
        return None
    entry = next((item for item in load_registry() if item.key == key), None)
    if entry is None:
        raise AreaError("places_file_unreceipted")
    located = _receipt_of(cache, entry)
    if located is None:
        raise AreaError("places_file_digest")
    return located


def _place_from_registry(
    cache: Path, registry: Sequence[Entry]
) -> tuple[Path, FileReceipt] | None:
    for entry in registry:
        if (
            entry.source_id == _PLACES_SOURCE
            and entry.skip_reason == ""
            and entry.extension == "parquet"
        ):
            located = _receipt_of(cache, entry)
            if located is not None:
                return located
    return None


def _building_entries(registry: Sequence[Entry]) -> tuple[Entry, ...]:
    """Active building Parquet inputs; STAC metadata is not a stage input."""
    return tuple(
        entry
        for entry in registry
        if entry.source_id == _BUILDINGS_SOURCE
        and entry.skip_reason == ""
        and entry.extension == "parquet"
    )


def _buildings_from_registry(
    cache: Path, registry: Sequence[Entry]
) -> tuple[tuple[Path, ...], tuple[FileReceipt, ...]]:
    paths: list[Path] = []
    receipts: list[FileReceipt] = []
    for entry in _building_entries(registry):
        located = _receipt_of(cache, entry)
        if located is None:
            continue
        paths.append(located[0])
        receipts.append(located[1])
    return tuple(paths), tuple(receipts)


def _receipt_of(cache: Path, entry: Entry) -> tuple[Path, FileReceipt] | None:
    selected = reviewed_selections(cache).get(entry.key)
    if selected is None:
        return None
    try:
        snapshot = read_snapshot(cache / entry.key, selected)
        loaded = snapshot.sidecar
        if loaded.get("key") != entry.key or loaded.get("source_id") != entry.source_id:
            return None
        retrieved, publisher = loaded.get("retrieved_utc"), loaded.get("publisher")
        if not isinstance(retrieved, str) or not isinstance(publisher, str):
            return None
        return snapshot.path, FileReceipt(
            entry.key, snapshot.sha256, retrieved, publisher
        )
    except SnapshotError as exc:
        _observe(exc)
        return None


def _refuse_stage(cache: Path, lines: list[str] | None, reason: str) -> None:
    """Drop a points file from an earlier run and name this refusal."""
    (cache / "places_s2_t06" / "place_points.json").unlink(missing_ok=True)
    _note(lines, "places", reason)


def _observe(error: Exception) -> None:
    observe("frame", error)


def _area_refusal(lines: list[str], error: AreaError | PlacesError) -> None:
    if not observe("frame", error, lines=lines):
        lines.append(f"REFUSED {error.reason}")


def _note(lines: list[str] | None, stage: str, reason: str) -> None:
    if lines is None or stage not in {"frame", "places"}:
        return
    if observe("frame", PlacesError(reason), lines=lines):
        return
    if _closed(reason):
        lines.append(f"stage {stage} {reason}")


def _closed(value: str) -> bool:
    return value != "" and all(
        char.islower() or char.isdigit() or char == "_" for char in value
    )


def _boundary(boundaries: Sequence[BaseGeometry]) -> BaseGeometry | None:
    parts = tuple(boundaries)
    if not parts:
        return None
    if len(parts) == 1:
        return parts[0]
    merged = unary_union(list(parts))
    if not isinstance(merged, BaseGeometry):
        return None
    return merged
