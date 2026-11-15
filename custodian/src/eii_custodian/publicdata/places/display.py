"""Display threshold, duplicate rule, caveat and the further-source seam."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal

from eii_custodian.publicdata.places_fsq.constants import DUPLICATE_WITHIN_M
from eii_custodian.publicdata.places_fsq.policy import (
    PlaceStandIn,
    distance_m,
    normalise_duplicate_name,
)
from eii_custodian.publicdata.places_fsq.select import FrameBox

# PUB-49. 0.7000 is shown. 0.6999 is not.
CONFIDENCE_MIN = Decimal("0.7000")
# PUB-50.
CAVEAT_KEY = "open_listings_incomplete"
CAVEAT_EN = "Open listings are incomplete"
CAVEAT_AR = "القوائم المفتوحة غير مكتملة"
ARABIC_REVIEW = "pending native review"
CENSUS_SOURCE = "est_census"
ABSENT_CATEGORY = "not found in public places data"
_OPEN = "verified_open"


@dataclass(frozen=True)
class CensusFigure:
    """The census comparison, with the lineage of the frame's census output."""

    source_key: str
    table: str
    indicator: str
    retrieval_date: str
    digest: str
    value: int


@dataclass(frozen=True)
class Caveat:
    """The incomplete-listing note. An absent census input carries no figure."""

    key: str
    text_en: str
    text_ar: str
    arabic_review: str
    census_source: str
    census_table: str
    census_indicator: str
    census_retrieval_date: str
    census_digest: str
    census_establishments: int | None


@dataclass(frozen=True)
class PubPlace:
    """One pub_place row. source_provider, licence and confidence are required."""

    place_id: str
    name: str
    name_ar: str | None
    category: str
    category_class: str
    lon: Decimal
    lat: Decimal
    cell: int
    source_release: str
    source_provider: str
    licence: str
    confidence: Decimal
    merged_ids: str


@dataclass(frozen=True)
class DuplicateOutcome:
    """Kept rows, the pairs a reviewer has not settled, and who is shown."""

    places: tuple[PubPlace, ...]
    unresolved: tuple[tuple[str, str], ...]
    shown: frozenset[str]


@dataclass(frozen=True)
class CategoryResult:
    """A category count, or the absent-category sentence. An absence is not zero."""

    found: bool
    shown: int | None
    text: str


def census_figure(value: object) -> CensusFigure | None:
    """Accept a lineage-bearing census figure. A bare number is refused."""
    from eii_custodian.publicdata.places import PlacesError

    if value is None:
        return None
    if not isinstance(value, CensusFigure):
        raise PlacesError("census_lineage")
    if (
        value.source_key != CENSUS_SOURCE
        or value.table == ""
        or value.indicator == ""
        or value.retrieval_date == ""
        or value.digest == ""
    ):
        raise PlacesError("census_lineage")
    return value


def open_listings_caveat(census: CensusFigure | None = None) -> Caveat:
    """Return the standing note. The Arabic line is pending native review."""
    if census is None:
        return Caveat(
            CAVEAT_KEY,
            CAVEAT_EN,
            CAVEAT_AR,
            ARABIC_REVIEW,
            "",
            "",
            "",
            "",
            "",
            None,
        )
    return Caveat(
        CAVEAT_KEY,
        CAVEAT_EN,
        CAVEAT_AR,
        ARABIC_REVIEW,
        census.source_key,
        census.table,
        census.indicator,
        census.retrieval_date,
        census.digest,
        census.value,
    )


def resolve_duplicates(
    places: Sequence[PubPlace],
    inside: frozenset[str],
    status: Mapping[str, str],
) -> DuplicateOutcome:
    """Apply the one name-and-distance rule. Inside, only a reviewed duplicate merges."""
    ordered = tuple(sorted(places, key=lambda place: place.place_id))
    pairs = _pairs(ordered)
    absorbed: dict[str, str] = {}
    _absorb_outside(ordered, pairs, inside, absorbed)
    _absorb_inside(ordered, pairs, inside, status, absorbed)
    merged = _with_merged_ids(ordered, absorbed)
    unresolved = _unresolved(ordered, pairs, inside, status, absorbed)
    shown = frozenset(
        place.place_id for place in merged if _shown(place, inside, status, absorbed)
    )
    return DuplicateOutcome(merged, unresolved, shown)


def hidden_count(places: Sequence[PubPlace], shown: frozenset[str]) -> int:
    """Count rows that the display rule hides. The count is this function's."""
    return sum(1 for place in places if place.place_id not in shown)


def category_result(
    places: Sequence[PubPlace], category: str, shown: frozenset[str]
) -> CategoryResult:
    """Return the shown count, or the absent-category sentence when none exist."""
    present = [place for place in places if place.category == category]
    if not present:
        return CategoryResult(False, None, ABSENT_CATEGORY)
    count = sum(1 for place in present if place.place_id in shown)
    return CategoryResult(True, count, "")


def place_stand_ins(
    places: Sequence[PubPlace], inside: frozenset[str]
) -> tuple[PlaceStandIn, ...]:
    """Return the further source's stand-in rows, including showcase membership."""
    return tuple(
        PlaceStandIn(
            place.place_id,
            place.name,
            place.name_ar,
            float(place.lon),
            float(place.lat),
            place.place_id in inside,
        )
        for place in places
    )


def inventory_names(places: Sequence[PubPlace]) -> tuple[str, ...]:
    """Return every name and Arabic name for the real-name inventory."""
    found: list[str] = []
    for place in places:
        found.append(place.name)
        if place.name_ar:
            found.append(place.name_ar)
    return tuple(found)


def frame_box_of(boundary_bounds: tuple[float, float, float, float]) -> FrameBox:
    """Build the further source's box from a boundary's bounds."""
    west, south, east, north = boundary_bounds
    return FrameBox(west=west, south=south, east=east, north=north)


def _pairs(places: Sequence[PubPlace]) -> tuple[tuple[str, str], ...]:
    found: list[tuple[str, str]] = []
    for index, left in enumerate(places):
        for right in places[index + 1 :]:
            if _same_name(left, right) and _within(left, right):
                found.append((left.place_id, right.place_id))
    return tuple(found)


def _same_name(left: PubPlace, right: PubPlace) -> bool:
    return bool(_labels(left) & _labels(right))


def _labels(place: PubPlace) -> set[str]:
    found = {_folded_name(place.name)}
    if place.name_ar:
        found.add(_folded_name(place.name_ar))
    found.discard("")
    return found


def _folded_name(value: str) -> str:
    return normalise_duplicate_name(value)


def _within(left: PubPlace, right: PubPlace) -> bool:
    metres = distance_m(
        float(left.lon), float(left.lat), float(right.lon), float(right.lat)
    )
    return metres <= DUPLICATE_WITHIN_M


def _absorb_outside(
    places: Sequence[PubPlace],
    pairs: Sequence[tuple[str, str]],
    inside: frozenset[str],
    absorbed: dict[str, str],
) -> None:
    by_id = {place.place_id: place for place in places}
    pair_set = set(pairs)
    order = sorted(
        places,
        key=lambda place: (-place.confidence, place.place_id),
    )
    for keeper in order:
        if keeper.place_id in absorbed or keeper.place_id in inside:
            continue
        for other in places:
            if other.place_id == keeper.place_id or other.place_id in absorbed:
                continue
            if other.place_id in inside or keeper.place_id in inside:
                continue
            key = _pair_key(keeper.place_id, other.place_id)
            if key not in pair_set:
                continue
            if other.confidence < keeper.confidence:
                absorbed[other.place_id] = keeper.place_id
            elif by_id[other.place_id].confidence < keeper.confidence:
                absorbed[other.place_id] = keeper.place_id


def _absorb_inside(
    places: Sequence[PubPlace],
    pairs: Sequence[tuple[str, str]],
    inside: frozenset[str],
    status: Mapping[str, str],
    absorbed: dict[str, str],
) -> None:
    pair_set = set(pairs)
    for left_id, right_id in pair_set:
        if left_id not in inside and right_id not in inside:
            continue
        left_duplicate = status.get(left_id) == "duplicate"
        right_duplicate = status.get(right_id) == "duplicate"
        if left_duplicate == right_duplicate:
            continue
        drop = left_id if left_duplicate else right_id
        keep = right_id if left_duplicate else left_id
        if drop in absorbed:
            continue
        absorbed[drop] = keep
    del places


def _with_merged_ids(
    places: Sequence[PubPlace], absorbed: Mapping[str, str]
) -> tuple[PubPlace, ...]:
    extras: dict[str, list[str]] = {}
    for dropped, keeper in absorbed.items():
        extras.setdefault(keeper, []).append(dropped)
    rewritten: list[PubPlace] = []
    for place in places:
        added = extras.get(place.place_id, [])
        if not added and place.merged_ids == "":
            rewritten.append(place)
            continue
        current = [part for part in place.merged_ids.split(";") if part]
        merged = ";".join(sorted(set(current + added)))
        rewritten.append(
            PubPlace(
                place.place_id,
                place.name,
                place.name_ar,
                place.category,
                place.category_class,
                place.lon,
                place.lat,
                place.cell,
                place.source_release,
                place.source_provider,
                place.licence,
                place.confidence,
                merged,
            )
        )
    return tuple(rewritten)


def _unresolved(
    places: Sequence[PubPlace],
    pairs: Sequence[tuple[str, str]],
    inside: frozenset[str],
    status: Mapping[str, str],
    absorbed: Mapping[str, str],
) -> tuple[tuple[str, str], ...]:
    del places
    found: list[tuple[str, str]] = []
    for left, right in pairs:
        if left in absorbed or right in absorbed:
            continue
        outside = left not in inside and right not in inside
        if outside:
            found.append((left, right))
            continue
        left_duplicate = status.get(left) == "duplicate"
        right_duplicate = status.get(right) == "duplicate"
        if left_duplicate == right_duplicate:
            found.append((left, right))
    return tuple(sorted(found))


def _shown(
    place: PubPlace,
    inside: frozenset[str],
    status: Mapping[str, str],
    absorbed: Mapping[str, str],
) -> bool:
    if place.place_id in absorbed:
        return False
    if place.place_id in inside:
        return status.get(place.place_id) == _OPEN
    return place.confidence >= CONFIDENCE_MIN


def _pair_key(left: str, right: str) -> tuple[str, str]:
    if left < right:
        return left, right
    return right, left
