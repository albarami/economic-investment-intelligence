"""Lead-shell exact-name ties and code-emitted, receipt-backed cache rows."""

from __future__ import annotations

import json
import tempfile
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

import yaml
from shapely.geometry import Point

from eii_custodian.publicdata.fetch.award_checks import normalise_name
from eii_custodian.publicdata.fetch.page_records import PageError, selected_page
from eii_custodian.publicdata.fetch.snapshots import SnapshotError, read_snapshot, utc

from . import landmarks
from .landmark_select import SelectedLandmark, kind_of
from .model import Building


@dataclass(frozen=True)
class LandmarkPoint:
    point_id: str
    name: str
    geometry: Point


@dataclass(frozen=True)
class Ties:
    document: dict[str, Any]
    outcomes: tuple[tuple[str, str], ...]


def _match(
    selected: SelectedLandmark,
    points: Sequence[LandmarkPoint],
    buildings: Sequence[Building],
    aliases: Mapping[str, tuple[str, ...]],
) -> tuple[str, str | None, str | None]:
    names = {
        normalise_name(n)
        for n in (selected.name_en, *aliases.get(selected.landmark_id, ()))
    }
    matches = [point for point in points if normalise_name(point.name) in names]
    if not matches:
        return "no_point", None, None
    if len(matches) != 1:
        return "several_points", None, None
    point = matches[0]
    covers = [b for b in buildings if b.geometry.covers(point.geometry)]
    if not covers:
        return "point_in_no_building", point.point_id, None
    if len(covers) != 1:
        return "point_in_several_buildings", point.point_id, None
    return "tied", point.point_id, covers[0].building_id


def tie_outcomes(
    selected: Sequence[SelectedLandmark],
    points: Sequence[LandmarkPoint],
    buildings: Sequence[Building],
    aliases: Mapping[str, tuple[str, ...]],
) -> tuple[tuple[str, str, str | None], ...]:
    """Reject every claimant of a shared point or building, independent of order."""
    matches = [_match(row, points, buildings, aliases) for row in selected]
    point_counts = Counter(point for reason, point, _ in matches if reason == "tied")
    building_counts = Counter(
        building for reason, _, building in matches if reason == "tied"
    )
    outcomes = []
    for row, (reason, point, building) in zip(selected, matches, strict=True):
        if reason == "tied" and point_counts[point] > 1:
            reason = "point_claimed_twice"
        elif reason == "tied" and building_counts[building] > 1:
            reason = "building_claimed_twice"
        outcomes.append(
            (row.landmark_id, reason, building if reason == "tied" else None)
        )
    return tuple(outcomes)


def _emit(
    cache: Path, selected: SelectedLandmark, building_id: str
) -> dict[str, object]:
    """Read a reviewed page selection; copy tokens and receipt metadata by code."""
    page = selected.page
    entry = landmarks._registry_by_url().get(page["page_url"])
    if entry is None:
        raise landmarks._refuse_citation("registry_row")
    try:
        envelope = selected_page(cache, entry)
        payload = json.loads(envelope.body)
        identity = payload["inputs"][0]["identity"]
        raw = read_snapshot(cache / entry.key / "inputs/input-0", identity)
    except (PageError, SnapshotError, json.JSONDecodeError, KeyError, TypeError):
        raise landmarks._refuse_citation("page_snapshot") from None
    row = landmarks.LandmarkHeight(
        selected.landmark_id,
        building_id,
        selected.name_en,
        Decimal(page["height_m"]),
        kind_of(page),
        landmarks.LandmarkCitation(
            page["page_url"],
            page["publisher"],
            utc(raw.sidecar["retrieved_utc"]).date().isoformat(),
            entry.licence_basis,
            raw.sha256,
            page["height_excerpt"],
        ),
    )
    landmarks.verify_landmark_receipts(cache, (row,))
    record = landmarks.landmark_record(row)
    record["height_m"] = page["height_m"]
    return record


def tie_landmarks(
    selected: Sequence[SelectedLandmark],
    points: Sequence[LandmarkPoint],
    buildings: Sequence[Building],
    cache: Path,
    aliases: Mapping[str, tuple[str, ...]] | None = None,
) -> Ties:
    """Emit only tied rows; the caller stores and independently reviews one YAML."""
    outcomes = tie_outcomes(selected, points, buildings, aliases or {})
    entries = [
        _emit(cache, row, building)
        for row, (_, reason, building) in zip(selected, outcomes, strict=True)
        if reason == "tied" and building is not None
    ]
    document: dict[str, Any] = {"version": 1, "entries": entries}
    if not entries:
        document["pending"] = "landmark_list_empty"
    return Ties(document, tuple((key, reason) for key, reason, _ in outcomes))


def write_landmark_heights(cache: Path, result: Ties) -> Path:
    """Publish one local YAML only after the loader and receipts both pass."""
    landmarks.landmark_heights_path(cache)
    target = cache / "review" / "landmark_heights.yaml"
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", suffix=".yaml", dir=target.parent, delete=False
    ) as handle:
        temporary = Path(handle.name)
        yaml.safe_dump(result.document, handle, sort_keys=False, allow_unicode=True)
    try:
        rows = landmarks.load_landmark_heights(temporary)
        landmarks.verify_landmark_receipts(cache, rows)
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)
    return target
