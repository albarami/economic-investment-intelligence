"""Propose reviewed place keys from the receipted cache; lead-shell only, offline.

``review_place_keys.py CACHE REVIEW_DIR [--check]`` fills a null ``record_key``
of ``flagship_candidates.yaml`` (a building id, ``bldg_ovt``) and of
``showcase_gazetteer.yaml`` (a place id, ``places_ovt``) only when exactly one
receipted open place carries one of the row's names after
``trim_collapse_whitespace_casefold``; a building also needs that point in
exactly one footprint, inside the boundary set the build uses. The matched
place must also survive the build's own ``_keep`` exclusions, read with the
reviewed attribution table (so ``attribution_missing`` withholds the key; H2
and the reviewer's table come first), and ``resolve_duplicates``. A repeated
``place_key`` and a selected building part that does not verify are refused.
Every other row stays null with a closed reason. It prints counts and booleans
per place_key, never a name, id or coordinate; an expected failure prints one
closed reason and no text of the failure. ``--check`` re-derives every filled
key and fails one whose place the build excludes.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import tempfile
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

import yaml
from shapely.geometry import Point
from shapely.geometry.base import BaseGeometry

import h3
from eii_custodian.publicdata.fetch.registry import Entry, load_registry
from eii_custodian.publicdata.fetch.snapshots import SnapshotError, reviewed_selections
from eii_custodian.publicdata.frame.build import read_cached
from eii_custodian.publicdata.frame.checks import FrameError
from eii_custodian.publicdata.frame.raw import read_archive
from eii_custodian.publicdata.places import PlacesError
from eii_custodian.publicdata.places.build import _keep
from eii_custodian.publicdata.places.display import resolve_duplicates
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
    load_attribution,
    load_flagship_candidates,
    load_showcase_gazetteer,
)
from eii_custodian.publicdata.places_fsq.policy import normalise_duplicate_name

PLACES = "places_ovt"
BUILDINGS = "bldg_ovt"
ATTRIBUTION = "places_ovt_attribution.csv"
Loader = Callable[[Path, Path | None], tuple[str, tuple[Mapping[str, object], ...]]]
FILES: tuple[tuple[str, str, Loader], ...] = (
    ("flagship_candidates.yaml", BUILDINGS, load_flagship_candidates),
    ("showcase_gazetteer.yaml", PLACES, load_showcase_gazetteer),
)
UNPARSABLE = (yaml.YAMLError, UnicodeError, csv.Error)


class ReviewError(Exception):
    """A refusal with a closed reason; nothing is written."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


@dataclass(frozen=True)
class Inputs:
    """The receipted places, every receipted footprint and the inside ids.

    fates holds each place's outcome under the build's own filters ("ok" or a
    closed reason).
    """

    places: tuple[ReadPlace, ...]
    buildings: tuple[ReadBuilding, ...]
    inside: frozenset[str]
    fates: Mapping[str, str]


@dataclass(frozen=True)
class Proposal:
    """One row's outcome. key is None unless every rule holds."""

    place_key: str
    matches: int
    kept: bool | None
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
        return Proposal(place_key, len(matches), None, None, None, None, reason)
    place = matches[0]
    fate = inputs.fates[place.place_id]
    if fate != "ok":
        return Proposal(place_key, 1, False, None, None, None, fate)
    if source_id == PLACES:
        return Proposal(place_key, 1, True, None, None, place.place_id, "ok")
    point = Point(float(place.lon), float(place.lat))
    holding = [
        row for row in inputs.buildings if decode_wkb(row.footprint_wkb).covers(point)
    ]
    if len(holding) != 1:
        reason = "footprint_0" if not holding else "footprint_n"
        return Proposal(place_key, 1, True, len(holding), None, None, reason)
    building = holding[0].building_id
    if building not in inputs.inside:
        return Proposal(place_key, 1, True, 1, False, None, "outside_boundary")
    return Proposal(place_key, 1, True, 1, True, building, "ok")


def place_fates(
    places: Sequence[ReadPlace],
    boundary: BaseGeometry,
    licences: Sequence[tuple[str, str]],
) -> dict[str, str]:
    """Each place's outcome under the build's own ``_keep`` and duplicate rule.

    ``licences`` is the reviewed attribution table, so a token without a row
    is ``attribution_missing``. The frame's grid is not rebuilt here: each
    place's own fine cell stands in, so ``no_cell`` is not evaluated. No
    showcase area exists yet, so ``inside`` is empty.
    """
    stored = frozenset(
        h3.str_to_int(h3.latlng_to_cell(float(raw.lat), float(raw.lon), 9))
        for raw in places
    )
    fates: dict[str, str] = {}
    kept = []
    for raw in places:
        excluded: dict[str, int] = {}
        place = _keep(raw, boundary, stored, licences, {}, excluded, [])
        if place is None:
            fates[raw.place_id] = f"excluded_by_keep_{next(iter(excluded))}"
            continue
        kept.append(place)
        fates[raw.place_id] = "ok"
    outcome = resolve_duplicates(kept, frozenset(), {})
    for survivor in outcome.places:
        for dropped in survivor.merged_ids.split(";"):
            if dropped:
                fates[dropped] = "duplicate_dropped"
    return fates


def apply(
    rows: Sequence[Mapping[str, object]],
    proposals: Sequence[Proposal | None],
    source_id: str,
) -> list[dict[str, object]]:
    """Fill each row from its own proposal; a row already set is refused."""
    result = []
    for row, item in zip(rows, proposals, strict=True):
        updated = dict(row)
        key = None if item is None else item.key
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
    cache: Path,
    registry: Sequence[Entry],
    boundary: BaseGeometry,
    tag: str,
    licences: Sequence[tuple[str, str]],
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
    verified = {receipt.source_key for receipt in receipts}
    for entry in registry:
        part = entry.source_id == BUILDINGS and entry.key != BUILDINGS
        if part and entry.extension == "parquet" and not entry.skip_reason:
            if (cache / entry.key).is_dir() and entry.key not in selected:
                raise ReviewError("buildings_file_unreceipted")
            if entry.key in selected and entry.key not in verified:
                raise ReviewError("buildings_file_unverified")
    inside, _receipts, _outside = load_boundary_buildings(paths, receipts, boundary)
    every = tuple(row for item in paths for row in read_building_file(item))
    places = read_place_file(path, tag)
    fates = place_fates(places, boundary, licences)
    return Inputs(places, every, frozenset(row.building_id for row in inside), fates)


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


def review_rows(path: Path, loader: Loader) -> tuple[Mapping[str, object], ...]:
    """Load one review file through the build's reader; a repeated key refuses."""
    rows = loader(path, None)[1]
    keys = [str(row.get("place_key")) for row in rows]
    if len(set(keys)) != len(keys):
        raise ReviewError("duplicate_place_key")
    return rows


def fill(review: Path, inputs: Inputs) -> list[str]:
    """Propose keys for null rows and write each file; return the summary lines."""
    lines = []
    for name, source_id, loader in FILES:
        path = review / name
        rows = review_rows(path, loader)
        proposals = [
            propose(row, source_id, inputs) if row.get("record_key") is None else None
            for row in rows
        ]
        if any(item is not None and item.key is not None for item in proposals):
            write_reviewed(path, apply(rows, proposals, source_id), loader)
        for item in proposals:
            if item is None:
                continue
            lines.append(
                f"{item.place_key} matches={_bucket(item.matches)} "
                f"kept={_flag(item.kept)} "
                f"footprints={_bucket(item.footprints)} inside={_flag(item.inside)} "
                f"written={_flag(item.key is not None)} reason={item.reason}"
            )
    return lines


def check(review: Path, inputs: Inputs) -> tuple[list[str], bool]:
    """Re-derive every filled key; True when every one agrees."""
    lines = []
    agrees = True
    for name, source_id, loader in FILES:
        for row in review_rows(review / name, loader):
            if row.get("record_key") is None:
                continue
            item = propose(row, source_id, inputs)
            same = (
                item.key == row.get("record_key") and row.get("source_id") == source_id
            )
            agrees = agrees and same
            lines.append(
                f"{item.place_key} check={_flag(same)} kept={_flag(item.kept)}"
            )
    return lines, agrees


def refusal(exc: Exception) -> str:
    """The closed reason of an expected failure; never the failure's own text."""
    if isinstance(exc, (ReviewError, PlacesError)):
        return exc.reason
    if isinstance(exc, FrameError):
        return "frame_boundary_unreadable"
    if isinstance(exc, SnapshotError):
        return "snapshot_refused"
    if isinstance(exc, FileExistsError):
        return "output_exists"
    if isinstance(exc, OSError):
        return "filesystem_refused"
    return "review_file_unparsable"


EXPECTED = (ReviewError, PlacesError, FrameError, SnapshotError, OSError, *UNPARSABLE)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cache", type=Path)
    parser.add_argument("review", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    registry = load_registry()
    try:
        boundary = frame_boundary(args.cache, registry)
        licences = load_attribution(args.review / ATTRIBUTION, None)[1]
        inputs = load_inputs(
            args.cache, registry, boundary, _tag(args.review), licences
        )
        if args.check:
            lines, agrees = check(args.review, inputs)
        else:
            lines, agrees = fill(args.review, inputs), True
    except EXPECTED as exc:
        print(f"REFUSED {refusal(exc)}")
        return 2
    for line in lines:
        print(line)
    return 0 if agrees else 1


if __name__ == "__main__":
    sys.exit(main())
