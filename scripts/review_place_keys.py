"""Propose reviewed place keys from the receipted cache; lead-shell only, offline.

``review_place_keys.py CACHE REVIEW_DIR [--check]`` fills a null ``record_ref``
of ``flagship_candidates.yaml`` (a building id, ``bldg_ovt``) and of
``showcase_gazetteer.yaml`` (a place id, ``places_ovt``). Names compare after
``trim_collapse_whitespace_casefold`` (N0). Each row records its basis:

- ``building_name`` (building rows, tried first): exactly one verified
  footprint carries one of the row's names among its own names (primary,
  common values and rules values), and it is inside the boundary set. Two or
  more such footprints refuse with ``building_name_n``; more than one once
  combining marks and tatweel are also dropped (N1) refuses with
  ``building_name_folded_n``; a place-point footprint (below) that differs
  refuses with ``basis_conflict``. No named footprint falls back to
  ``place_point``. No nearest-footprint rule exists.
- ``place_point`` (building rows): exactly one place that the build keeps
  carries one of the row's names, and its point lies in exactly one footprint,
  inside the boundary set.
- ``place_name`` (gazetteer rows): exactly one place that the build keeps
  carries one of the row's names, and its category is in the closed area list
  ``LANDMARK_CATEGORIES``; any other category refuses with
  ``landmark_category_refused``.

Only places that survive the build's own ``_keep`` exclusions, read with the
reviewed attribution table (so ``attribution_missing`` withholds the key; H2
and the reviewer's table come first), and ``resolve_duplicates`` are counted
for ``match_0`` and ``match_n``; the excluded count is printed beside them,
and a row whose one match is excluded keeps that match's own reason. A
repeated ``place_key`` and a selected building part that does not verify are
refused. Every other row stays null with a closed reason. It prints counts and
booleans per place_key, never a name, id or coordinate; an expected failure
prints one closed reason and no text of the failure. ``--check`` re-derives
every filled key with the same rules, the area list included, and fails one
whose place the build excludes.

The writing contract. At each filesystem call of ``write_reviewed`` and its
helpers (each write, copy, ``copymode``, reload, ``os.replace``, restore,
unlink and close), the only fault raises ``OSError`` or ``KeyboardInterrupt``.
The outcome is then exactly one of:

(a) both files unchanged, with ``REFUSED filesystem_refused`` and exit 2, or
    the interrupt passing through after a full restore;
(b) ``FAILED rollback_failed`` and exit 3, with every unrestored original kept
    beside its file and no path printed;
(c) success: both files replaced.

Cleanup only follows an outcome already decided, so a fault in it, an
interrupt included, never replaces that outcome; it only leaves its own
temporary file. Once a restore has failed, nothing later replaces (b); once
both files are replaced, nothing later replaces (c).
"""

from __future__ import annotations

import argparse
import contextlib
import csv
import json
import os
import shutil
import sys
import tempfile
import unicodedata
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
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
    _column_names,
    connect_parquet,
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
    review_file_row,
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
ROLLBACK_FAILED = "rollback_failed"
BUILDING_NAME = "building_name"
PLACE_POINT = "place_point"
PLACE_NAME = "place_name"
# The closed list of area categories a gazetteer row may resolve to. The
# tokens are those the lead's diagnosis of the live L4 run names; they are
# not checked against the source's published taxonomy (open item proposed).
LANDMARK_CATEGORIES = frozenset({"district", "neighbourhood", "island"})
TATWEEL = "ـ"
NAME_FIELDS = frozenset({"primary", "common", "rules"})


class ReviewError(Exception):
    """A refusal with a closed reason; nothing is written."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


@dataclass(frozen=True)
class Inputs:
    """The receipted places, every receipted footprint and the inside ids.

    fates holds each place's outcome under the build's own filters ("ok" or a
    closed reason). named holds each named footprint's own names, as stored.
    """

    places: tuple[ReadPlace, ...]
    buildings: tuple[ReadBuilding, ...]
    inside: frozenset[str]
    fates: Mapping[str, str]
    named: Mapping[str, frozenset[str]]


@dataclass(frozen=True)
class Proposal:
    """One row's outcome. key is None unless every rule holds.

    matches counts kept places only and excluded the other name matches;
    footprint is the one footprint the row's basis reached, inside or not.
    """

    place_key: str
    matches: int | None
    kept: bool | None
    footprints: int | None
    inside: bool | None
    key: str | None
    reason: str
    basis: str
    excluded: int | None = None
    footprint: str | None = None


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


def folded_name(value: str) -> str:
    """N1: the N0 name with combining marks and tatweel also dropped."""
    decomposed = unicodedata.normalize("NFKD", normalise_duplicate_name(value))
    kept = (
        item
        for item in decomposed
        if unicodedata.category(item) != "Mn" and item != TATWEEL
    )
    return normalise_duplicate_name(unicodedata.normalize("NFC", "".join(kept)))


def named_footprints(
    names: frozenset[str],
    named: Mapping[str, frozenset[str]],
    compare: Callable[[str], str],
) -> list[str]:
    """Footprints one of whose own names equals one of names under compare."""
    wanted = {compare(name) for name in names} - {""}
    return [
        building
        for building, own in named.items()
        if wanted & {compare(name) for name in own}
    ]


def propose(spec: Mapping[str, object], source_id: str, inputs: Inputs) -> Proposal:
    """Derive one row's key, or the closed reason it stays null."""
    place_key = str(spec.get("place_key"))
    names = candidate_names(spec)
    if source_id == BUILDINGS:
        found = by_building_name(place_key, names, inputs)
        if found is not None:
            return found
    return by_place(place_key, names, source_id, inputs)


def by_building_name(
    place_key: str, names: frozenset[str], inputs: Inputs
) -> Proposal | None:
    """The footprint that carries the row's name itself; None when none does."""
    exact = named_footprints(names, inputs.named, normalise_duplicate_name)
    folded = named_footprints(names, inputs.named, folded_name)
    base = Proposal(place_key, None, None, len(exact), None, None, "", BUILDING_NAME)
    if len(exact) > 1:
        return replace(base, reason="building_name_n")
    if len(folded) > 1:
        return replace(base, reason="building_name_folded_n")
    if not exact:
        return None
    building = exact[0]
    base = replace(base, footprint=building, inside=building in inputs.inside)
    if not base.inside:
        return replace(base, reason="outside_boundary")
    point = by_place(place_key, names, BUILDINGS, inputs).footprint
    if point is not None and point != building:
        return replace(base, reason="basis_conflict")
    return replace(base, key=building, reason="ok")


def by_place(
    place_key: str, names: frozenset[str], source_id: str, inputs: Inputs
) -> Proposal:
    """The one kept place that carries the row's name, then its point's footprint."""
    found = matching_places(names, inputs.places)
    kept = [place for place in found if inputs.fates[place.place_id] == "ok"]
    basis = PLACE_NAME if source_id == PLACES else PLACE_POINT
    base = Proposal(
        place_key, len(kept), None, None, None, None, "", basis, len(found) - len(kept)
    )
    if len(found) == 1 and not kept:
        return replace(base, kept=False, reason=inputs.fates[found[0].place_id])
    if len(kept) != 1:
        return replace(base, reason="match_0" if not kept else "match_n")
    place = kept[0]
    if source_id == PLACES:
        if place.category not in LANDMARK_CATEGORIES:
            return replace(base, kept=True, reason="landmark_category_refused")
        return replace(base, kept=True, key=place.place_id, reason="ok")
    point = Point(float(place.lon), float(place.lat))
    holding = [
        row for row in inputs.buildings if decode_wkb(row.footprint_wkb).covers(point)
    ]
    if len(holding) != 1:
        reason = "footprint_0" if not holding else "footprint_n"
        return replace(base, kept=True, footprints=len(holding), reason=reason)
    building = holding[0].building_id
    base = replace(base, kept=True, footprints=1, footprint=building)
    if building not in inputs.inside:
        return replace(base, inside=False, reason="outside_boundary")
    return replace(base, inside=True, key=building, reason="ok")


def footprint_names(value: object) -> frozenset[str]:
    """A footprint's primary, common and rules names as stored; a wrong form refuses.

    ``names`` is null or a struct with the fields ``primary`` (null or text),
    ``common`` (null or a map of null or text) and ``rules`` (null or a list of
    structs, each with a ``value`` field of null or text). Empty names are
    dropped.
    """
    if value is None:
        return frozenset()
    if not isinstance(value, dict) or not NAME_FIELDS <= value.keys():
        raise ReviewError("building_names_form")
    found = [value.get("primary")]
    common, rules = value.get("common"), value.get("rules")
    if common is not None:
        if not isinstance(common, dict):
            raise ReviewError("building_names_form")
        found.extend(common.values())
    if rules is not None:
        if not isinstance(rules, list) or not all(
            isinstance(rule, dict) and "value" in rule for rule in rules
        ):
            raise ReviewError("building_names_form")
        found.extend(rule.get("value") for rule in rules)
    if any(item is not None and not isinstance(item, str) for item in found):
        raise ReviewError("building_names_form")
    return frozenset(item for item in found if isinstance(item, str) and item.strip())


def building_names(paths: Sequence[Path]) -> dict[str, frozenset[str]]:
    """Each named footprint's own names, from the verified parts only."""
    named: dict[str, frozenset[str]] = {}
    for path in paths:
        connection = connect_parquet()
        try:
            if "names" not in _column_names(connection, path):
                raise ReviewError("building_names_missing")
            rows = connection.execute(
                "SELECT id, names FROM read_parquet(?) WHERE names IS NOT NULL",
                [str(path)],
            ).fetchall()
        finally:
            connection.close()
        for building, value in rows:
            own = footprint_names(value)
            if own:
                named[str(building)] = own
    return named


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
        updated = review_file_row(row)
        key = None if item is None else item.key
        if key is not None:
            if row.get("record_key") is not None or row.get("source_id") is not None:
                raise ReviewError("overwrite_refused")
            updated["source_id"] = source_id
            updated["record_ref"] = key
        result.append(updated)
    return result


def write_beside(path: Path, data: bytes) -> Path:
    """Write data to a new temporary file beside path, with path's mode.

    The file is removed on a failure.
    """
    handle, name = tempfile.mkstemp(prefix=".review-", dir=path.parent)
    written = Path(name)
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(data)
        shutil.copymode(path, written)
    except BaseException:
        discard([written])
        raise
    return written


def discard(paths: Sequence[Path]) -> None:
    """Remove each path, each in its own try; a failure leaves only that path.

    A failure, an interrupt included, neither stops the removal of the rest
    nor escapes: cleanup never replaces the outcome it follows.
    """
    for path in paths:
        with contextlib.suppress(BaseException):
            path.unlink(missing_ok=True)


def stage(path: Path, rows: Sequence[Mapping[str, object]], loader: Loader) -> Path:
    """Write a temporary file beside path and load it with the build's reader.

    The staged path is returned; on any failure it is removed first.
    """
    text = json.dumps(list(rows), ensure_ascii=False, indent=2) + "\n"
    staged = write_beside(path, text.encode("utf-8"))
    try:
        reloaded = [review_file_row(row) for row in loader(staged, None)[1]]
        if reloaded != json.loads(text):
            raise ReviewError("reload_mismatch")
    except BaseException:
        discard([staged])
        raise
    return staged


def restore(replaced: Sequence[tuple[Path, Path]]) -> list[Path]:
    """Move each kept original back over its target; return those not restored.

    Any exception, an interrupt included, counts as a failed restore.
    """
    unrestored = []
    for original, path in replaced:
        try:
            os.replace(original, path)
        except BaseException:
            unrestored.append(original)
    return unrestored


def write_reviewed(
    planned: Sequence[tuple[Path, Sequence[Mapping[str, object]], Loader]],
) -> None:
    """Stage, reload and keep each original, then replace the targets.

    A refusal or a failed replacement leaves neither target changed and no
    temporary file. A failed restore raises ``rollback_failed`` and leaves each
    unrestored original beside its target. A cleanup failure replaces no
    outcome (see the module's writing contract). An original is at risk
    from just before its target's replacement, unless that replacement raises
    ``OSError``; an interrupt unwinds like any failure, and an at-risk original
    is unlinked only by its own restore.
    """
    staged: list[tuple[Path, Path]] = []
    originals: list[tuple[Path, Path]] = []
    at_risk: list[tuple[Path, Path]] = []

    def temporaries(keep: Sequence[Path] = ()) -> list[Path]:
        return [
            temporary for temporary, _ in (*staged, *originals) if temporary not in keep
        ]

    try:
        for path, rows, loader in planned:
            staged.append((stage(path, rows, loader), path))
        for _temporary, path in staged:
            originals.append((write_beside(path, path.read_bytes()), path))
        for (temporary, path), original in zip(staged, originals, strict=True):
            at_risk.append(original)
            try:
                os.replace(temporary, path)
            except OSError:
                at_risk.pop()
                raise
    except BaseException:
        unrestored = restore(at_risk)
        discard(temporaries(unrestored))
        if unrestored:
            raise ReviewError(ROLLBACK_FAILED) from None
        raise
    discard(temporaries())


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
    named = building_names(paths)
    places = read_place_file(path, tag)
    fates = place_fates(places, boundary, licences)
    ids = frozenset(row.building_id for row in inside)
    return Inputs(places, every, ids, fates, named)


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
    """Propose keys for null rows of both files, then write them together.

    Every refusal is found before either file is replaced.
    """
    lines = []
    planned = []
    for name, source_id, loader in FILES:
        path = review / name
        rows = review_rows(path, loader)
        proposals = [
            propose(row, source_id, inputs) if row.get("record_key") is None else None
            for row in rows
        ]
        if any(item is not None and item.key is not None for item in proposals):
            planned.append((path, apply(rows, proposals, source_id), loader))
        for item in proposals:
            if item is None:
                continue
            lines.append(
                f"{item.place_key} matches={_bucket(item.matches)} "
                f"kept={_flag(item.kept)} "
                f"footprints={_bucket(item.footprints)} inside={_flag(item.inside)} "
                f"written={_flag(item.key is not None)} reason={item.reason} "
                f"basis={item.basis} excluded={_bucket(item.excluded)}"
            )
    write_reviewed(planned)
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
        reason = refusal(exc)
        if reason == ROLLBACK_FAILED:
            print(f"FAILED {reason}")
            return 3
        print(f"REFUSED {reason}")
        return 2
    for line in lines:
        print(line)
    return 0 if agrees else 1


if __name__ == "__main__":
    sys.exit(main())
