"""Eligibility, the duplicate rule and the reviewed category mapping."""

from __future__ import annotations

import csv
import math
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from eii_custodian.publicdata.places_fsq.constants import (
    ATTRIBUTION,
    DUPLICATE_WITHIN_M,
    EARTH_RADIUS_M,
    RELEASE_POLICY,
    TERMS_CHECKED,
)
from eii_custodian.publicdata.places_fsq.errors import PlacesFsqError
from eii_custodian.publicdata.places_fsq.parse import ParsedRow
from eii_custodian.publicdata.places_fsq.select import FRAME_BOX, FrameBox

MAPPING_COLUMNS = (
    "source_category_id",
    "place_category_key",
    "mapping_version",
    "review_status",
    "reviewer_role",
    "review_date",
    "rationale",
)
_APPROVED = "approved"


@dataclass(frozen=True)
class PlaceStandIn:
    """One invented row of the main places table's contract shape."""

    place_id: str
    name: str
    name_ar: str | None
    lon: float
    lat: float
    in_showcase: bool


@dataclass(frozen=True)
class DuplicateLink:
    """A copy row that matches a main-places row and is not shown."""

    fsq_place_id: str
    place_id: str
    distance_m: float
    in_showcase: bool


@dataclass(frozen=True)
class CategoryMapping:
    """One reviewed row. The source category text is not rewritten."""

    source_category_id: str
    place_category_key: str
    mapping_version: str
    review_status: str
    reviewer_role: str
    review_date: str
    rationale: str


def normalise_duplicate_name(value: str) -> str:
    """Trim, collapse inner white space and case-fold. PUB-51 names either language."""
    return " ".join(value.split()).casefold()


def distance_m(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """Great-circle distance in metres."""
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    chord = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lon / 2) ** 2
    )
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(chord))


def move_north(lon: float, lat: float, metres: float) -> tuple[float, float]:
    """Return the point due north of (lon, lat) by metres, on the same sphere."""
    return lon, lat + math.degrees(metres / EARTH_RADIUS_M)


def duplicate_links(
    rows: Sequence[ParsedRow], places: Sequence[PlaceStandIn]
) -> tuple[DuplicateLink, ...]:
    """Link a copy row to a main-places row when PUB-51's candidate rule matches."""
    found: list[DuplicateLink] = []
    for row in rows:
        link = _first_link(row, places)
        if link is not None:
            found.append(link)
    return tuple(found)


def is_eligible(
    row: ParsedRow, frame: FrameBox, links: Sequence[DuplicateLink]
) -> bool:
    """A place is shown when it has a name, a point in the frame and no closing date."""
    if row.name.strip() == "":
        return False
    if row.date_closed is not None:
        return False
    lon = float(row.lon)
    lat = float(row.lat)
    if not (frame.west <= lon <= frame.east and frame.south <= lat <= frame.north):
        return False
    return all(link.fsq_place_id != row.fsq_place_id for link in links)


def load_mapping(path: Path, known_keys: frozenset[str]) -> tuple[CategoryMapping, ...]:
    """Load a reviewed mapping. A bad row refuses the file's use."""
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(line for line in handle if not line.startswith("#"))
        if reader.fieldnames is None or tuple(reader.fieldnames) != MAPPING_COLUMNS:
            raise PlacesFsqError("mapping_header")
        rows = [
            _mapping_row(item, known_keys)
            for item in reader
            if any((value or "").strip() for value in item.values())
        ]
    seen: dict[str, str] = {}
    for row in rows:
        prior = seen.get(row.source_category_id)
        if prior is not None and prior != row.place_category_key:
            raise PlacesFsqError("mapping_conflict")
        if prior is not None:
            raise PlacesFsqError("mapping_conflict")
        seen[row.source_category_id] = row.place_category_key
    return tuple(rows)


def product_categories(
    category_ids: str, mapping: Sequence[CategoryMapping]
) -> str | None:
    """Return reviewed keys only when every source identifier has a mapping."""
    if category_ids == "":
        return None
    by_id = {row.source_category_id: row.place_category_key for row in mapping}
    identifiers = category_ids.split(";")
    if any(item not in by_id for item in identifiers):
        raise PlacesFsqError("category_unmapped")
    return ";".join(by_id[item] for item in identifiers)


def _first_link(row: ParsedRow, places: Sequence[PlaceStandIn]) -> DuplicateLink | None:
    source = normalise_duplicate_name(row.name)
    if source == "":
        return None
    lon = float(row.lon)
    lat = float(row.lat)
    for place in places:
        if not _same_name(source, place):
            continue
        metres = distance_m(lon, lat, place.lon, place.lat)
        if metres <= DUPLICATE_WITHIN_M:
            return DuplicateLink(
                row.fsq_place_id, place.place_id, metres, place.in_showcase
            )
    return None


def assert_policy(path: Path) -> None:
    """Refuse a reviewed policy file that disagrees with the enforced rules."""
    import yaml

    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise PlacesFsqError("policy_disagrees")
    expected: dict[str, object] = {
        "release": RELEASE_POLICY,
        "release_field": "folder_name",
        "metadata_file": "<release>/places/_metadata",
        "selection": "row_group_coordinate_statistics",
        "ignored_bounds": "file_geographic_metadata",
        "country": "QA",
        "display": "name_and_point_in_frame_and_no_closing_date",
        "name_normalisation": "trim_collapse_whitespace_casefold",
        "name_languages": "source_name_against_either_main_places_name",
        "distance_source": "PUB-51",
        "attribution": ATTRIBUTION,
        "host_terms": f"terms to be read; checked {TERMS_CHECKED}",
        "name_ar": "always_null",
        "categories": "category_ids_and_category_labels",
        "category_mapping": "every_nonempty_identifier_reviewed",
        "snapshots": "every_dated_release_retained",
    }
    for key, value in expected.items():
        if loaded.get(key) != value:
            raise PlacesFsqError("policy_disagrees")
    raw_distance = loaded.get("distance_m")
    if isinstance(raw_distance, bool) or not isinstance(raw_distance, (int, float)):
        raise PlacesFsqError("policy_disagrees")
    if float(raw_distance) != DUPLICATE_WITHIN_M:
        raise PlacesFsqError("policy_disagrees")
    box = loaded.get("frame_box")
    wanted = {
        "west": FRAME_BOX.west,
        "south": FRAME_BOX.south,
        "east": FRAME_BOX.east,
        "north": FRAME_BOX.north,
    }
    if not isinstance(box, dict):
        raise PlacesFsqError("policy_disagrees")
    try:
        got = {key: float(box[key]) for key in wanted}
    except (KeyError, TypeError, ValueError) as exc:
        raise PlacesFsqError("policy_disagrees") from exc
    if got != wanted:
        raise PlacesFsqError("policy_disagrees")


def _same_name(source: str, place: PlaceStandIn) -> bool:
    if normalise_duplicate_name(place.name) == source:
        return True
    if place.name_ar is None:
        return False
    return normalise_duplicate_name(place.name_ar) == source


def _mapping_row(
    item: dict[str, str | None], known_keys: frozenset[str]
) -> CategoryMapping:
    values = {key: (item.get(key) or "").strip() for key in MAPPING_COLUMNS}
    if any(value == "" for value in values.values()):
        raise PlacesFsqError("mapping_unsigned")
    if values["review_status"] != _APPROVED:
        raise PlacesFsqError("mapping_unsigned")
    if values["place_category_key"] not in known_keys:
        raise PlacesFsqError("mapping_unknown_target")
    return CategoryMapping(
        source_category_id=values["source_category_id"],
        place_category_key=values["place_category_key"],
        mapping_version=values["mapping_version"],
        review_status=values["review_status"],
        reviewer_role=values["reviewer_role"],
        review_date=values["review_date"],
        rationale=values["rationale"],
    )
