"""Assemble pub_place, verification, display points and the flagship check."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import cast

from shapely.geometry import Point
from shapely.geometry.base import BaseGeometry

from eii_custodian.publicdata.frame.grid import ownership_index, point_cell
from eii_custodian.publicdata.places import PlacesError
from eii_custodian.publicdata.places.areas import (
    AreaCutoff,
    AreaError,
    AreaMode,
    AreaProvider,
    ReviewedPoint,
)
from eii_custodian.publicdata.places.display import (
    CAVEAT_KEY,
    Caveat,
    DuplicateOutcome,
    PubPlace,
    census_figure,
    frame_box_of,
    hidden_count,
    inventory_names,
    open_listings_caveat,
    place_stand_ins,
    resolve_duplicates,
)
from eii_custodian.publicdata.places.flagship import (
    CandidateInput,
    CheckRecord,
    CountedPlace,
    evaluate_candidates,
)
from eii_custodian.publicdata.places.read import (
    SOURCE_RELEASE,
    FileReceipt,
    ReadBuilding,
    ReadPlace,
    decode_wkb,
    geometry_bounds,
    load_boundary_buildings,
    require_receipt,
    write_place_points,
)
from eii_custodian.publicdata.places.read import (
    iter_place_file as read_place_file,
)
from eii_custodian.publicdata.places.review import (
    Verification,
    accept_verification,
    latest_status,
    load_attribution,
    load_categories,
    load_verified_places,
    refuse_same_date,
)
from eii_custodian.publicdata.places_fsq.parse import ParsedRow
from eii_custodian.publicdata.places_fsq.policy import duplicate_links, is_eligible

_OSM = frozenset({"openstreetmap", "osm"})
_PLACES_SOURCE = "places_ovt"
_BUILDINGS_SOURCE = "bldg_ovt"


@dataclass(frozen=True)
class FsqShown:
    """One further-source point that is shown, with the release date carried."""

    fsq_place_id: str
    name: str
    lon: Decimal
    lat: Decimal
    licence: str
    source_release: str
    source_id: str
    caveat_key: str


@dataclass(frozen=True)
class PlacesResult:
    """The places build. complete is false while showcase areas are pending."""

    places: tuple[PubPlace, ...]
    verifications: tuple[Verification, ...]
    shown_ids: frozenset[str]
    fsq_shown: tuple[FsqShown, ...]
    excluded: Mapping[str, int]
    report: tuple[str, ...]
    complete: bool
    caveat: Caveat
    unresolved: tuple[tuple[str, str], ...]
    hidden: int
    flagship: CheckRecord | None
    names: tuple[str, ...]
    receipts: tuple[FileReceipt, ...]
    required_verification_by_area: Mapping[str, int] = field(default_factory=dict)
    required_verification_total: int = 0


def build_places(
    places_path: Path,
    *,
    arabic_tag: str,
    boundary: BaseGeometry,
    grid: Sequence[Mapping[str, object]],
    attribution: Sequence[tuple[str, str]] = (),
    attribution_path: Path | None = None,
    attribution_cache: Path | None = None,
    categories: Sequence[tuple[str, str]] = (),
    categories_path: Path | None = None,
    categories_cache: Path | None = None,
    verified: Sequence[Verification] = (),
    verified_path: Path | None = None,
    verified_cache: Path | None = None,
    buildings_paths: Sequence[Path] = (),
    buildings_receipts: Sequence[FileReceipt] = (),
    places_receipt: FileReceipt | None = None,
    zones: Mapping[str, BaseGeometry] | None = None,
    area_provider: AreaProvider | None = None,
    showcase_areas: Sequence[Mapping[str, object]] = (),
    candidates: Sequence[Mapping[str, object]] = (),
    fsq_rows: Sequence[ParsedRow] | None = None,
    fsq_release: str = "",
    fsq_licence: str = "",
    output_dir: Path | None = None,
    build_date: date | None = None,
    census: object = None,
) -> PlacesResult:
    """Build pub_place from one local file. A row missing its source fields is left out."""
    if not isinstance(arabic_tag, str) or arabic_tag.strip() == "":
        raise PlacesError("arabic_tag")
    licences = _table(
        attribution, attribution_path, attribution_cache, load_attribution
    )
    classes = dict(
        _table(categories, categories_path, categories_cache, load_categories)
    )
    stored = ownership_index(
        [{str(key): value for key, value in row.items()} for row in grid]
    )
    excluded: dict[str, int] = {}
    report: list[str] = []
    figure = census_figure(census)
    if figure is None:
        report.append("census_comparison_pending")
    box = geometry_bounds(boundary)
    place_receipt = require_receipt(places_path, places_receipt)
    kept: list[PubPlace] = []
    omitted: list[int] = []
    for index, raw in enumerate(
        read_place_file(places_path, arabic_tag, frame_box=box, outside=omitted)
    ):
        if omitted[index]:
            excluded["outside_boundary"] = (
                excluded.get("outside_boundary", 0) + omitted[index]
            )
        place = _keep(raw, boundary, stored, licences, classes, excluded, report)
        if place is not None:
            _require_fields(place)
            kept.append(place)
    if omitted[-1]:
        excluded["outside_boundary"] = excluded.get("outside_boundary", 0) + omitted[-1]
    buildings, building_receipts, outside_buildings = load_boundary_buildings(
        buildings_paths, buildings_receipts, boundary
    )
    if outside_buildings:
        excluded["building_outside_boundary"] = outside_buildings
    verifications = _verifications(
        verified, verified_path, verified_cache, kept, build_date
    )
    status = {key: row.status for key, row in latest_status(verifications).items()}
    area_members: dict[str, frozenset[str]] = {
        str(row["place_key"]): frozenset() for row in showcase_areas
    }
    inside, area_notes, stand_in, area_blocked = _inside(
        showcase_areas, kept, area_provider, boundary, area_members=area_members
    )
    report.extend(area_notes)
    outcome = resolve_duplicates(kept, inside, status)
    shown_places = outcome.places
    hidden = hidden_count(shown_places, outcome.shown)
    fsq_shown, fsq_notes = _fsq(
        fsq_rows, shown_places, inside, boundary, fsq_release, fsq_licence
    )
    report.extend(fsq_notes)
    flagship = _flagship(
        candidates, buildings, shown_places, status, zones or {}, area_provider
    )
    if area_provider is None:
        report.append("showcase_areas_pending")
    if output_dir is not None:
        write_place_points(
            output_dir,
            tuple(
                (_PLACES_SOURCE, place.place_id, str(place.lon), str(place.lat))
                for place in shown_places
            ),
            tuple(
                (
                    _BUILDINGS_SOURCE,
                    building.building_id,
                    str(building.lon),
                    str(building.lat),
                )
                for building in buildings
            ),
        )
    complete = _complete(
        area_provider,
        showcase_areas,
        stand_in,
        area_blocked,
        fsq_rows,
        fsq_release,
        outcome,
    )
    return PlacesResult(
        places=shown_places,
        verifications=verifications,
        shown_ids=outcome.shown,
        fsq_shown=fsq_shown,
        excluded=excluded,
        report=tuple(report),
        complete=complete,
        caveat=open_listings_caveat(figure),
        unresolved=outcome.unresolved,
        hidden=hidden,
        flagship=flagship,
        names=inventory_names(shown_places),
        receipts=(place_receipt, *building_receipts),
        required_verification_by_area={
            key: len(required_verification(kept, members, classes, story_ids=()))
            for key, members in sorted(area_members.items())
        },
        required_verification_total=len(
            required_verification(
                kept, frozenset().union(*area_members.values()), classes, story_ids=()
            )
        ),
    )


def required_verification(
    places: Sequence[PubPlace],
    inside: frozenset[str],
    classes: Mapping[str, str],
    story_ids: Sequence[str],
) -> tuple[str, ...]:
    """Sorted kept food ids in showcase walks, plus explicitly supplied story ids."""
    return tuple(
        sorted(
            set(story_ids)
            | {
                place.place_id
                for place in places
                if place.place_id in inside
                and classes.get(place.category, place.category_class)
                in {"restaurant", "italian_restaurant", "food_service"}
            }
        )
    )


def _table(
    rows: Sequence[tuple[str, str]],
    path: Path | None,
    cache: Path | None,
    loader: object,
) -> tuple[tuple[str, str], ...]:
    if path is None:
        return tuple(rows)
    if not callable(loader):
        raise PlacesError("loader")
    loaded = loader(path, cache)
    if not isinstance(loaded, tuple) or len(loaded) != 2:
        raise PlacesError("loader")
    table = loaded[1]
    if not isinstance(table, tuple):
        raise PlacesError("loader")
    return cast(tuple[tuple[str, str], ...], table)


def _keep(
    raw: ReadPlace,
    boundary: BaseGeometry,
    stored: frozenset[int],
    licences: Sequence[tuple[str, str]],
    classes: Mapping[str, str],
    excluded: dict[str, int],
    report: list[str],
) -> PubPlace | None:
    if not boundary.covers(Point(float(raw.lon), float(raw.lat))):
        _bump(excluded, "outside_boundary")
        return None
    if raw.source.reason == "absent":
        _bump(excluded, "record_level_absent")
        return None
    if raw.source.reason == "not_unique":
        _bump(excluded, "record_level_not_unique")
        return None
    if raw.confidence_kind == "range":
        _bump(excluded, "confidence_range")
        return None
    if raw.confidence is None:
        _bump(excluded, "null_confidence")
        return None
    if raw.name.strip() == "":
        _bump(excluded, "name_missing")
        return None
    if raw.category.strip() == "":
        _bump(excluded, "category_missing")
        return None
    token = _dataset(raw.source.entry)
    if token is None:
        _bump(excluded, "source_provider_missing")
        return None
    if token.casefold() in _OSM:
        _bump(excluded, "osm_not_merged")
        return None
    licence = dict(licences).get(token)
    if licence is None:
        _bump(excluded, "attribution_missing")
        report.append(f"attribution token missing: {token}")
        return None
    cell = point_cell(float(raw.lon), float(raw.lat), stored)
    if cell is None:
        _bump(excluded, "no_cell")
        return None
    return PubPlace(
        raw.place_id,
        raw.name,
        raw.name_ar,
        raw.category,
        classes.get(raw.category, ""),
        raw.lon,
        raw.lat,
        cell,
        SOURCE_RELEASE,
        token,
        licence,
        raw.confidence,
        "",
    )


def _dataset(entry: Mapping[str, object] | None) -> str | None:
    if entry is None or "dataset" not in entry:
        return None
    value = entry["dataset"]
    if not isinstance(value, str) or value == "":
        return None
    return value


def _require_fields(place: PubPlace) -> None:
    if (
        place.source_provider == ""
        or place.licence == ""
        or not isinstance(place.confidence, Decimal)
    ):
        raise PlacesError("pub_place_field")


def _verifications(
    verified: Sequence[Verification],
    path: Path | None,
    cache: Path | None,
    places: Sequence[PubPlace],
    build_date: date | None,
) -> tuple[Verification, ...]:
    known = frozenset(place.place_id for place in places)
    if path is None:
        if not verified:
            return ()
        if build_date is None:
            raise PlacesError("bad_check_date")
        rows = tuple(accept_verification(row, known, build_date) for row in verified)
        refuse_same_date(rows)
        return rows
    if build_date is None:
        raise PlacesError("bad_check_date")
    _origin, loaded = load_verified_places(path, cache, known, build_date)
    return loaded


def _inside(
    specs: Sequence[Mapping[str, object]],
    places: Sequence[PubPlace],
    provider: AreaProvider | None,
    boundary: BaseGeometry,
    *,
    area_members: dict[str, frozenset[str]] | None = None,
) -> tuple[frozenset[str], tuple[str, ...], bool, bool]:
    del boundary
    if provider is None or not specs:
        return frozenset(), (), False, False
    by_id = {place.place_id: place for place in places}
    members_by_area = area_members if area_members is not None else {}
    notes: list[str] = []
    stand_in = False
    blocked = False
    for spec in specs:
        record = spec.get("record_key")
        if not isinstance(record, str) or record not in by_id:
            notes.append("showcase landmark missing")
            blocked = True
            continue
        place = by_id[record]
        try:
            area = provider.area(
                str(spec.get("place_key")),
                ReviewedPoint(float(place.lon), float(place.lat)),
                AreaMode.WALK,
                AreaCutoff.MINUTES_10,
            )
        except AreaError as exc:
            notes.append(f"showcase area error: {exc.reason}")
            blocked = True
            continue
        if area.stand_in:
            stand_in = True
        polygon = decode_wkb(area.wkb)
        members_by_area[str(spec.get("place_key"))] = frozenset(
            place.place_id
            for place in places
            if polygon.covers(Point(float(place.lon), float(place.lat)))
        )
    if blocked:
        return (
            frozenset(place.place_id for place in places),
            tuple(notes),
            stand_in,
            True,
        )
    inside = frozenset().union(*members_by_area.values())
    return inside, tuple(notes), stand_in, False


def _fsq(
    rows: Sequence[ParsedRow] | None,
    places: Sequence[PubPlace],
    inside: frozenset[str],
    boundary: BaseGeometry,
    release: str,
    licence: str,
) -> tuple[tuple[FsqShown, ...], tuple[str, ...]]:
    if rows is None:
        return (), ("fsq_pending",)
    if release == "":
        return (), ("fsq_release_missing",)
    if licence.strip() == "":
        raise PlacesError("fsq_licence_missing")
    box = frame_box_of(geometry_bounds(boundary))
    links = duplicate_links(rows, place_stand_ins(places, inside))
    shown: list[FsqShown] = []
    for row in rows:
        if not is_eligible(row, box, links):
            continue
        if not boundary.covers(Point(float(row.lon), float(row.lat))):
            continue
        shown.append(
            FsqShown(
                row.fsq_place_id,
                row.name,
                row.lon,
                row.lat,
                licence,
                release,
                "places_fsq",
                CAVEAT_KEY,
            )
        )
    note = f"fsq_duplicate_not_shown: {len(links)}"
    return tuple(shown), (note,)


def _flagship(
    candidates: Sequence[Mapping[str, object]],
    buildings: Sequence[ReadBuilding],
    places: Sequence[PubPlace],
    status: Mapping[str, str],
    zones: Mapping[str, BaseGeometry],
    provider: AreaProvider | None,
) -> CheckRecord | None:
    if not candidates:
        return None
    by_id = {building.building_id: building for building in buildings}
    prepared: list[CandidateInput] = []
    for spec in candidates:
        record = spec.get("record_key")
        if not isinstance(record, str) or record not in by_id:
            raise PlacesError("footprint_missing")
        building = by_id[record]
        use = spec.get("use")
        prepared.append(
            CandidateInput(
                str(spec.get("place_key")),
                building.footprint_wkb,
                use if isinstance(use, str) else "",
                float(building.lon),
                float(building.lat),
            )
        )
    counted = tuple(
        CountedPlace(
            place.place_id,
            float(place.lon),
            float(place.lat),
            place.category_class,
            status.get(place.place_id, ""),
        )
        for place in places
    )
    return evaluate_candidates(prepared, counted, zones, provider)


def _complete(
    provider: AreaProvider | None,
    specs: Sequence[Mapping[str, object]],
    stand_in: bool,
    area_blocked: bool,
    fsq_rows: Sequence[ParsedRow] | None,
    fsq_release: str,
    outcome: DuplicateOutcome,
) -> bool:
    if area_blocked or provider is None or not specs or stand_in:
        return False
    if fsq_rows is None or fsq_release == "":
        return False
    return not outcome.unresolved


def _bump(excluded: dict[str, int], reason: str) -> None:
    excluded[reason] = excluded.get(reason, 0) + 1
