"""PUB-57 candidate checks and the provisional decision validator."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from shapely.geometry import Point
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

from eii_custodian.publicdata.places import PlacesError
from eii_custodian.publicdata.places.areas import (
    AreaCutoff,
    AreaError,
    AreaMode,
    AreaProvider,
    AreaResult,
    ReviewedPoint,
)
from eii_custodian.publicdata.places.read import decode_wkb, geometry_wkb

# PUB-57 (b).
MIN_VERIFIED_OPEN_RESTAURANTS_WALK_5 = 8
# PUB-57 (c).
MIN_VERIFIED_OPEN_ITALIAN_WALK_10 = 2
# PUB-57 (a).
FLAGSHIP_ZONE_CODES = ("69", "70")
# PUB-57 (e).
LANDMARK_USES = frozenset({"public", "commercial", "mixed"})
METHOD = "places.flagship.v1"
_OPEN = "verified_open"
_RESTAURANT = "restaurant"
_ITALIAN = "italian_restaurant"
_RESTAURANT_CLASSES = frozenset({_RESTAURANT, _ITALIAN})
_ITALIAN_CLASSES = frozenset({_ITALIAN})
_CHECK_NAMES = (
    "a_footprint_in_zones",
    "b_restaurants_walk_5",
    "c_italian_walk_10",
    "d_areas_returned",
    "e_landmark_use",
)


@dataclass(frozen=True)
class CandidateInput:
    """One footprint and the reviewed use of its landmark."""

    candidate_key: str
    footprint_wkb: bytes
    use: str
    lon: float
    lat: float


@dataclass(frozen=True)
class CountedPlace:
    """A verified place the restaurant counts read."""

    place_id: str
    lon: float
    lat: float
    category_class: str
    status: str


@dataclass(frozen=True)
class CheckRecord:
    """Every candidate, every check, the inputs and the digest of that body."""

    body: dict[str, object]
    digest: str
    passing_evidence: bool
    passed_keys: tuple[str, ...]


@dataclass(frozen=True)
class Decision:
    """A provisional choice. It names a candidate and the check digest."""

    candidate_key: str
    digest: str
    provisional: bool


def evaluate_candidates(
    candidates: Sequence[CandidateInput],
    places: Sequence[CountedPlace],
    zones: Mapping[str, BaseGeometry],
    provider: AreaProvider | None,
) -> CheckRecord:
    """Run checks (a) to (e). A stand-in area is not passing evidence."""
    zone_union = _zone_union(zones)
    listed: list[dict[str, object]] = []
    for candidate in candidates:
        areas, area_errors = _areas(candidate, provider)
        checks, counts = _checks(candidate, places, zone_union, areas, area_errors)
        listed.append(
            {
                "candidate_key": candidate.candidate_key,
                "checks": checks,
                "counts": counts,
                "passed_predicates": all(checks.values()),
                "use": candidate.use,
                "inputs": _inputs(candidate, zones, areas, area_errors, places),
            }
        )
    body: dict[str, object] = {
        "candidates": listed,
        "method": METHOD,
        "provider_given": provider is not None,
        "provisional": True,
    }
    evidence = _evidence_from(body)
    body["passing_evidence"] = evidence
    digest = digest_of(body)
    return CheckRecord(body, digest, evidence, _passed_keys(body, evidence))


def digest_of(body: Mapping[str, object]) -> str:
    """SHA-256 of the canonical JSON of the check body."""
    encoded = json.dumps(
        body, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def validate_decision(decision: Decision, record: CheckRecord) -> None:
    """Refuse a failed candidate, a stale digest, a hand edit or a stand-in area."""
    recomputed = _recompute(record.body)
    stored = _stored_checks(record.body)
    if recomputed != stored:
        raise PlacesError("hand_edited")
    if decision.digest != record.digest or digest_of(record.body) != record.digest:
        raise PlacesError("stale_digest")
    if decision.provisional is not True:
        raise PlacesError("not_provisional")
    evidence = _evidence_from(record.body)
    if (
        record.passing_evidence is not evidence
        or record.body.get("passing_evidence") is not evidence
    ):
        raise PlacesError("evidence_mismatch")
    keys = _passed_keys(record.body, evidence)
    if tuple(record.passed_keys) != keys:
        raise PlacesError("passed_keys_mismatch")
    if evidence is not True:
        if record.body.get("provider_given") is not True:
            raise PlacesError("no_provider")
        raise PlacesError("stand_in_area")
    if decision.candidate_key not in keys:
        raise PlacesError("failed_candidate")


def decision_from_mapping(payload: Mapping[str, object]) -> Decision:
    """Read a decision fixture. Extra authority fields are refused."""
    allowed = {"candidate_key", "digest", "provisional"}
    if set(payload) != allowed:
        raise PlacesError("decision_fields")
    key = payload["candidate_key"]
    digest = payload["digest"]
    provisional = payload["provisional"]
    if not isinstance(key, str) or not isinstance(digest, str):
        raise PlacesError("decision_fields")
    if not isinstance(provisional, bool):
        raise PlacesError("decision_fields")
    return Decision(key, digest, provisional)


def _zone_union(zones: Mapping[str, BaseGeometry]) -> BaseGeometry | None:
    parts = [zones[code] for code in FLAGSHIP_ZONE_CODES if code in zones]
    if not parts:
        return None
    if len(parts) == 1:
        return parts[0]
    return unary_union(parts)


def _areas(
    candidate: CandidateInput, provider: AreaProvider | None
) -> tuple[dict[str, AreaResult], dict[str, str]]:
    found: dict[str, AreaResult] = {}
    errors: dict[str, str] = {}
    if provider is None:
        return found, {"walk_5": "not_called", "drive_10": "not_called"}
    point = ReviewedPoint(candidate.lon, candidate.lat)
    requests = (
        ("walk_5", AreaMode.WALK, AreaCutoff.MINUTES_5),
        ("walk_10", AreaMode.WALK, AreaCutoff.MINUTES_10),
        ("drive_10", AreaMode.DRIVE, AreaCutoff.MINUTES_10),
    )
    for name, mode, cutoff in requests:
        try:
            result = provider.area(candidate.candidate_key, point, mode, cutoff)
        except AreaError as exc:
            errors[name] = exc.reason
            continue
        found[name] = result
    return found, errors


def _checks(
    candidate: CandidateInput,
    places: Sequence[CountedPlace],
    zone_union: BaseGeometry | None,
    areas: Mapping[str, AreaResult],
    errors: Mapping[str, str],
) -> tuple[dict[str, bool], dict[str, int]]:
    footprint = decode_wkb(candidate.footprint_wkb)
    inside_zones = zone_union is not None and zone_union.covers(footprint)
    restaurants = _count(places, areas.get("walk_5"), _RESTAURANT_CLASSES)
    italian = _count(places, areas.get("walk_10"), _ITALIAN_CLASSES)
    areas_ok = _walk_5_and_drive_10_returned(errors, areas)
    use_ok = candidate.use in LANDMARK_USES
    checks = {
        "a_footprint_in_zones": inside_zones,
        "b_restaurants_walk_5": restaurants >= MIN_VERIFIED_OPEN_RESTAURANTS_WALK_5,
        "c_italian_walk_10": italian >= MIN_VERIFIED_OPEN_ITALIAN_WALK_10,
        "d_areas_returned": areas_ok,
        "e_landmark_use": use_ok,
    }
    return checks, {"restaurants_walk_5": restaurants, "italian_walk_10": italian}


def _walk_5_and_drive_10_returned(
    errors: Mapping[str, object], areas: Mapping[str, object]
) -> bool:
    """PUB-57 (d): walk 5 and drive 10 both returned. Another area error does not."""
    return (
        "walk_5" not in errors
        and "drive_10" not in errors
        and "walk_5" in areas
        and "drive_10" in areas
    )


def _count(
    places: Sequence[CountedPlace],
    area: AreaResult | None,
    classes: frozenset[str],
) -> int:
    if area is None:
        return 0
    polygon = decode_wkb(area.wkb)
    return sum(
        1
        for place in places
        if place.category_class in classes
        and place.status == _OPEN
        and polygon.covers(Point(place.lon, place.lat))
    )


def _inputs(
    candidate: CandidateInput,
    zones: Mapping[str, BaseGeometry],
    areas: Mapping[str, AreaResult],
    errors: Mapping[str, str],
    places: Sequence[CountedPlace],
) -> dict[str, object]:
    return {
        "area_errors": dict(sorted(errors.items())),
        "areas": {
            name: {
                "engine_version": result.engine_version,
                "graph_hash": result.graph_hash,
                "inputs_hash": result.inputs_hash,
                "method_version": result.method_version,
                "stand_in": result.stand_in,
                "wkb_sha256": hashlib.sha256(result.wkb).hexdigest(),
                "wkb_hex": result.wkb.hex(),
            }
            for name, result in sorted(areas.items())
        },
        "footprint_sha256": hashlib.sha256(candidate.footprint_wkb).hexdigest(),
        "footprint_wkb_hex": candidate.footprint_wkb.hex(),
        "lon": candidate.lon,
        "lat": candidate.lat,
        "places": [
            {
                "category_class": place.category_class,
                "lat": place.lat,
                "lon": place.lon,
                "place_id": place.place_id,
                "status": place.status,
            }
            for place in places
        ],
        "use": candidate.use,
        "zones": {
            code: geometry_wkb(zones[code]).hex()
            for code in FLAGSHIP_ZONE_CODES
            if code in zones
        },
    }


def _evidence_from(body: Mapping[str, object]) -> bool:
    """Evidence is false only when no provider was given or an area is a stand-in."""
    if body.get("provider_given") is not True:
        return False
    listed = body.get("candidates")
    if not isinstance(listed, list) or not listed:
        return False
    for item in listed:
        if not isinstance(item, dict):
            return False
        inputs = item.get("inputs")
        if not isinstance(inputs, dict):
            return False
        areas = inputs.get("areas")
        if not isinstance(areas, dict):
            return False
        for area in areas.values():
            if isinstance(area, dict) and area.get("stand_in") is True:
                return False
    return True


def _passed_keys(body: Mapping[str, object], evidence: bool) -> tuple[str, ...]:
    if evidence is not True:
        return ()
    listed = body.get("candidates")
    if not isinstance(listed, list):
        return ()
    keys: list[str] = []
    for item, checks in zip(listed, _recompute(body), strict=False):
        if isinstance(item, dict) and _all_pass(checks):
            keys.append(str(item.get("candidate_key")))
    return tuple(keys)


def _all_pass(checks: object) -> bool:
    if not isinstance(checks, dict):
        return False
    return all(checks.get(name) is True for name in _CHECK_NAMES)


def _stored_checks(body: Mapping[str, object]) -> list[object]:
    candidates = body.get("candidates")
    if not isinstance(candidates, list):
        return []
    return [
        item.get("checks") if isinstance(item, dict) else None for item in candidates
    ]


def _recompute(body: Mapping[str, object]) -> list[object]:
    """Re-run the predicates from the stored inputs. A hand edit will not match."""
    candidates = body.get("candidates")
    if not isinstance(candidates, list):
        return []
    found: list[object] = []
    for item in candidates:
        if not isinstance(item, dict):
            found.append(None)
            continue
        inputs = item.get("inputs")
        if not isinstance(inputs, dict):
            found.append(None)
            continue
        found.append(_checks_from_inputs(inputs))
    return found


def _checks_from_inputs(inputs: Mapping[str, object]) -> dict[str, bool]:
    footprint_hex = inputs.get("footprint_wkb_hex")
    zones = inputs.get("zones")
    areas = inputs.get("areas")
    errors = inputs.get("area_errors")
    places = inputs.get("places")
    use = inputs.get("use")
    if not isinstance(footprint_hex, str) or not isinstance(zones, dict):
        return _blank()
    if not isinstance(areas, dict) or not isinstance(errors, dict):
        return _blank()
    if not isinstance(places, list) or not isinstance(use, str):
        return _blank()
    footprint = decode_wkb(bytes.fromhex(footprint_hex))
    parts = [
        decode_wkb(bytes.fromhex(value))
        for value in zones.values()
        if isinstance(value, str)
    ]
    zone_union = unary_union(parts) if len(parts) > 1 else (parts[0] if parts else None)
    inside = zone_union is not None and zone_union.covers(footprint)
    counted = _places_from(places)
    restaurants = _count_area(counted, areas.get("walk_5"), _RESTAURANT_CLASSES)
    italian = _count_area(counted, areas.get("walk_10"), _ITALIAN_CLASSES)
    areas_ok = _walk_5_and_drive_10_returned(errors, areas)
    return {
        "a_footprint_in_zones": inside,
        "b_restaurants_walk_5": restaurants >= MIN_VERIFIED_OPEN_RESTAURANTS_WALK_5,
        "c_italian_walk_10": italian >= MIN_VERIFIED_OPEN_ITALIAN_WALK_10,
        "d_areas_returned": areas_ok,
        "e_landmark_use": use in LANDMARK_USES,
    }


def _places_from(places: Sequence[object]) -> tuple[CountedPlace, ...]:
    found: list[CountedPlace] = []
    for item in places:
        if not isinstance(item, dict):
            continue
        found.append(
            CountedPlace(
                str(item.get("place_id")),
                float(item["lon"]),
                float(item["lat"]),
                str(item.get("category_class")),
                str(item.get("status")),
            )
        )
    return tuple(found)


def _count_area(
    places: Sequence[CountedPlace], area: object, classes: frozenset[str]
) -> int:
    if not isinstance(area, dict):
        return 0
    hex_wkb = area.get("wkb_hex")
    if not isinstance(hex_wkb, str):
        return 0
    return _count(
        places,
        AreaResult(bytes.fromhex(hex_wkb), "", "", "", "", False),
        classes,
    )


def _blank() -> dict[str, bool]:
    return {
        "a_footprint_in_zones": False,
        "b_restaurants_walk_5": False,
        "c_italian_walk_10": False,
        "d_areas_returned": False,
        "e_landmark_use": False,
    }
