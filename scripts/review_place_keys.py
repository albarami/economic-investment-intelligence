"""Propose reviewed place keys from the receipted cache; lead-shell only, offline.

``review_place_keys.py CACHE REVIEW_DIR [--check]`` fills a null ``record_key``
of ``flagship_candidates.yaml`` (a building id, ``bldg_ovt``) and of
``showcase_gazetteer.yaml`` (a place id, ``places_ovt``) only when exactly one
receipted open place carries one of the row's names after
``trim_collapse_whitespace_casefold``; a building also needs that point in
exactly one footprint, inside the boundary set the build uses. Every other row
stays null with a closed reason. It prints counts and booleans per place_key,
never a name, id or coordinate. ``--check`` re-derives every filled key.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from shapely.geometry import Point
from shapely.geometry.base import BaseGeometry

from eii_custodian.publicdata.fetch.registry import Entry, load_registry
from eii_custodian.publicdata.fetch.snapshots import reviewed_selections
from eii_custodian.publicdata.frame.build import read_cached
from eii_custodian.publicdata.frame.checks import FrameError
from eii_custodian.publicdata.frame.raw import read_archive
from eii_custodian.publicdata.places import PlacesError
from eii_custodian.publicdata.places.integrate import (
    _boundary,
    _buildings_from_registry,
    _place_from_registry,
    _tag,
)
from eii_custodian.publicdata.places.read import (
    ReadBuilding,
    ReadPlace,
    decode_wkb,
    load_boundary_buildings,
    read_building_file,
    read_place_file,
    require_receipt,
)
from eii_custodian.publicdata.places.review import (
    load_flagship_candidates,
    load_showcase_gazetteer,
)
from eii_custodian.publicdata.places_fsq.policy import normalise_duplicate_name

PLACES = "places_ovt"
BUILDINGS = "bldg_ovt"
Loader = Callable[[Path, Path | None], tuple[str, tuple[Mapping[str, object], ...]]]
FILES: tuple[tuple[str, str, Loader], ...] = (
    ("flagship_candidates.yaml", BUILDINGS, load_flagship_candidates),
    ("showcase_gazetteer.yaml", PLACES, load_showcase_gazetteer),
)


class ReviewError(Exception):
    """A refusal with a closed reason; nothing is written."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


@dataclass(frozen=True)
class Inputs:
    """The receipted places, every receipted footprint and the inside ids."""

    places: tuple[ReadPlace, ...]
    buildings: tuple[ReadBuilding, ...]
    inside: frozenset[str]


@dataclass(frozen=True)
class Proposal:
    """One row's outcome. key is None unless every rule holds."""

    place_key: str
    matches: int
    footprints: int | None
    inside: bool | None
    key: str | None
    reason: str


def candidate_names(spec: Mapping[str, object]) -> frozenset[str]:
    """The row's English, Arabic and alias names, normalised; empty names dropped."""
    aliases = spec.get("aliases")
    if aliases is None:
        aliases = []
    if not isinstance(aliases, list):
        raise ReviewError("aliases_form")
    raw = [spec.get("name_en"), spec.get("name_ar"), *aliases]
    names = {normalise_duplicate_name(item) for item in raw if isinstance(item, str)}
    return frozenset(name for name in names if name != "")


def matching_places(
    names: frozenset[str], places: Sequence[ReadPlace]
) -> list[ReadPlace]:
    """Places whose primary or Arabic-tag name equals one candidate name."""
    found = []
    for place in places:
        own = {normalise_duplicate_name(place.name)}
        if place.name_ar is not None:
            own.add(normalise_duplicate_name(place.name_ar))
        if own & names:
            found.append(place)
    return found


def propose(spec: Mapping[str, object], source_id: str, inputs: Inputs) -> Proposal:
    """Derive one row's key, or the closed reason it stays null."""
    place_key = str(spec.get("place_key"))
    matches = matching_places(candidate_names(spec), inputs.places)
    if len(matches) != 1:
        reason = "match_0" if not matches else "match_n"
        return Proposal(place_key, len(matches), None, None, None, reason)
    place = matches[0]
    if source_id == PLACES:
        return Proposal(place_key, 1, None, None, place.place_id, "ok")
    point = Point(float(place.lon), float(place.lat))
    holding = [
        row for row in inputs.buildings if decode_wkb(row.footprint_wkb).covers(point)
    ]
    if len(holding) != 1:
        reason = "footprint_0" if not holding else "footprint_n"
        return Proposal(place_key, 1, len(holding), None, None, reason)
    building = holding[0].building_id
    if building not in inputs.inside:
        return Proposal(place_key, 1, 1, False, None, "outside_boundary")
    return Proposal(place_key, 1, 1, True, building, "ok")


def apply(
    rows: Sequence[Mapping[str, object]], proposals: Sequence[Proposal], source_id: str
) -> list[dict[str, object]]:
    """Fill each proposed key; a row whose key is already set is refused."""
    chosen = {item.place_key: item.key for item in proposals if item.key is not None}
    result = []
    for row in rows:
        updated = dict(row)
        key = chosen.get(str(row.get("place_key")))
        if key is not None:
            if row.get("record_key") is not None or row.get("source_id") is not None:
                raise ReviewError("overwrite_refused")
            updated["source_id"] = source_id
            updated["record_key"] = key
        result.append(updated)
    return result


def write_reviewed(
    path: Path, rows: Sequence[Mapping[str, object]], loader: Loader
) -> None:
    """Write a temporary file, load it with the build's reader, then replace."""
    text = json.dumps(list(rows), ensure_ascii=False, indent=2) + "\n"
    handle, name = tempfile.mkstemp(prefix=".review-", dir=path.parent)
    staged = Path(name)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            stream.write(text)
        if list(loader(staged, None)[1]) != json.loads(text):
            raise ReviewError("reload_mismatch")
        os.replace(staged, path)
    finally:
        staged.unlink(missing_ok=True)


def load_inputs(
    cache: Path, registry: Sequence[Entry], boundary: BaseGeometry, tag: str
) -> Inputs:
    """Read only receipted files through the build's own readers."""
    if tag == "":
        raise ReviewError("arabic_tag_missing")
    located = _place_from_registry(cache, registry)
    if located is None:
        raise ReviewError("places_file_unreceipted")
    path, receipt = located
    require_receipt(path, receipt)
    paths, receipts = _buildings_from_registry(cache, registry)
    selected = reviewed_selections(cache)
    for entry in registry:
        part = entry.source_id == BUILDINGS and entry.key != BUILDINGS
        if part and entry.extension == "parquet" and not entry.skip_reason:
            if (cache / entry.key).is_dir() and entry.key not in selected:
                raise ReviewError("buildings_file_unreceipted")
    inside, _receipts, _outside = load_boundary_buildings(paths, receipts, boundary)
    every = tuple(row for item in paths for row in read_building_file(item))
    return Inputs(
        read_place_file(path, tag),
        every,
        frozenset(row.building_id for row in inside),
    )


def frame_boundary(cache: Path, registry: Sequence[Entry]) -> BaseGeometry:
    """The union of the receipted municipality boundaries, as the frame hands over."""
    hdx = next(
        (row for row in registry if row.source_id == "bnd_hdx" and not row.skip_reason),
        None,
    )
    if hdx is None:
        raise ReviewError("frame_boundary_missing")
    digest = reviewed_selections(cache).get(hdx.key, "")
    body, _receipt = read_cached(cache, hdx, digest=digest)
    merged = _boundary(
        tuple(row.geometry for row in read_archive(body)["municipality"])
    )
    if merged is None:
        raise ReviewError("frame_boundary_missing")
    return merged


def _bucket(value: int | None) -> str:
    if value is None:
        return "na"
    return str(value) if value < 2 else "n"


def _flag(value: bool | None) -> str:
    return "na" if value is None else str(value).lower()


def fill(review: Path, inputs: Inputs) -> list[str]:
    """Propose keys for null rows and write each file; return the summary lines."""
    lines = []
    for name, source_id, loader in FILES:
        path = review / name
        rows = loader(path, None)[1]
        proposals = [
            propose(row, source_id, inputs)
            for row in rows
            if row.get("record_key") is None
        ]
        if any(item.key is not None for item in proposals):
            write_reviewed(
                path, apply(loader(path, None)[1], proposals, source_id), loader
            )
        for item in proposals:
            lines.append(
                f"{item.place_key} matches={_bucket(item.matches)} "
                f"footprints={_bucket(item.footprints)} inside={_flag(item.inside)} "
                f"written={_flag(item.key is not None)} reason={item.reason}"
            )
    return lines


def check(review: Path, inputs: Inputs) -> tuple[list[str], bool]:
    """Re-derive every filled key; True when every one agrees."""
    lines = []
    agrees = True
    for name, source_id, loader in FILES:
        for row in loader(review / name, None)[1]:
            if row.get("record_key") is None:
                continue
            item = propose(row, source_id, inputs)
            same = (
                item.key == row.get("record_key") and row.get("source_id") == source_id
            )
            agrees = agrees and same
            lines.append(f"{item.place_key} check={_flag(same)}")
    return lines, agrees


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cache", type=Path)
    parser.add_argument("review", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    registry = load_registry()
    try:
        boundary = frame_boundary(args.cache, registry)
        inputs = load_inputs(args.cache, registry, boundary, _tag(args.review))
        if args.check:
            lines, agrees = check(args.review, inputs)
        else:
            lines, agrees = fill(args.review, inputs), True
    except (ReviewError, PlacesError) as exc:
        print(f"REFUSED {exc.reason}")
        return 2
    except FrameError:
        print("REFUSED frame_boundary_unreadable")
        return 2
    for line in lines:
        print(line)
    return 0 if agrees else 1


if __name__ == "__main__":
    sys.exit(main())
