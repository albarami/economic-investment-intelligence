"""PUB-57 checks. Counts and the digest are computed in the test from stated inputs."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from custodian.tests.repository_root import repository_root
from shapely.geometry import Point, box

from eii_custodian.publicdata.places import PlacesError
from eii_custodian.publicdata.places.areas import (
    AreaCutoff,
    AreaError,
    AreaMode,
    AreaResult,
    ReviewedPoint,
)
from eii_custodian.publicdata.places.flagship import (
    MIN_VERIFIED_OPEN_ITALIAN_WALK_10,
    MIN_VERIFIED_OPEN_RESTAURANTS_WALK_5,
    CandidateInput,
    CheckRecord,
    CountedPlace,
    Decision,
    decision_from_mapping,
    digest_of,
    evaluate_candidates,
    validate_decision,
)

_WALK = box(51.45, 25.25, 51.55, 25.35)
_FOOT = box(51.46, 25.26, 51.54, 25.34)
_ZONE_69 = box(51.40, 25.20, 51.60, 25.40)
_ZONE_70 = box(51.90, 25.20, 52.00, 25.30)
_OUTSIDE = box(51.70, 25.20, 51.80, 25.30)
_FIXTURE = (
    repository_root(Path(__file__))
    / "custodian"
    / "tests"
    / "fixtures"
    / "places"
    / "flagship_decision.json"
)


def test_named_thresholds_match_the_pack() -> None:
    """The minimums are the numbers PUB-57 states."""
    assert MIN_VERIFIED_OPEN_RESTAURANTS_WALK_5 == 8
    assert MIN_VERIFIED_OPEN_ITALIAN_WALK_10 == 2


def test_passing_candidate_and_each_planted_failure() -> None:
    """One candidate passes every predicate. Each plant breaks exactly one."""
    zones = {"69": _ZONE_69, "70": _ZONE_70}
    places = _restaurants(6) + _italians(2)
    passed = evaluate_candidates(
        (_candidate(_FOOT.wkb, "commercial"),),
        places,
        zones,
        _Areas(stand_in=False),
    )
    assert passed.passing_evidence is True
    assert passed.passed_keys == ("SYN-CAND-1",)
    assert passed.body["candidates"][0]["counts"] == {
        "restaurants_walk_5": 8,
        "italian_walk_10": 2,
    }
    _assert_digest(passed)
    validate_decision(Decision("SYN-CAND-1", passed.digest, True), passed)

    outside = evaluate_candidates(
        (_candidate(_OUTSIDE.wkb, "commercial"),),
        places,
        zones,
        _Areas(stand_in=False),
    )
    assert outside.body["candidates"][0]["checks"]["a_footprint_in_zones"] is False

    short = evaluate_candidates(
        (_candidate(_FOOT.wkb, "commercial"),),
        _restaurants(5) + _italians(2),
        zones,
        _Areas(stand_in=False),
    )
    assert short.body["candidates"][0]["checks"]["b_restaurants_walk_5"] is False
    assert short.body["candidates"][0]["counts"]["restaurants_walk_5"] == 7

    one_italian = evaluate_candidates(
        (_candidate(_FOOT.wkb, "commercial"),),
        _restaurants(8) + _italians(1),
        zones,
        _Areas(stand_in=False),
    )
    assert one_italian.body["candidates"][0]["checks"]["c_italian_walk_10"] is False

    no_drive = evaluate_candidates(
        (_candidate(_FOOT.wkb, "commercial"),),
        places,
        zones,
        _Areas(stand_in=False, fail="drive_10"),
    )
    assert no_drive.body["candidates"][0]["checks"]["d_areas_returned"] is False

    residence = evaluate_candidates(
        (_candidate(_FOOT.wkb, "residential"),),
        places,
        zones,
        _Areas(stand_in=False),
    )
    assert residence.body["candidates"][0]["checks"]["e_landmark_use"] is False
    with pytest.raises(PlacesError, match="failed_candidate"):
        validate_decision(Decision("SYN-CAND-1", residence.digest, True), residence)


def test_a_point_on_the_polygon_edge_is_inside() -> None:
    """The eighth restaurant sits on the walk polygon's edge and is counted."""
    edge = Point(51.45, 25.30)
    assert _WALK.covers(edge)
    assert not _WALK.contains(edge)
    places = (
        *_restaurants(5),
        CountedPlace("SYN-EDGE", 51.45, 25.30, "restaurant", "verified_open"),
    )
    record = evaluate_candidates(
        (_candidate(_FOOT.wkb, "commercial"),),
        places + _italians(2),
        {"69": _ZONE_69, "70": _ZONE_70},
        _Areas(stand_in=False),
    )
    checks = record.body["candidates"][0]["checks"]
    counts = record.body["candidates"][0]["counts"]
    assert counts["restaurants_walk_5"] == 8
    assert checks["b_restaurants_walk_5"] is True


@pytest.mark.parametrize("food_service_count", [0, 1, 8, 20])
def test_food_service_never_raises_restaurant_counts(food_service_count: int) -> None:
    """Even open food-service venues inside both walks cannot meet PUB-57(b)."""
    food_service = tuple(
        CountedPlace(f"SYN-FOOD-{i}", 51.5, 25.3, "food_service", "verified_open")
        for i in range(food_service_count)
    )
    record = evaluate_candidates(
        (_candidate(_FOOT.wkb, "commercial"),),
        _restaurants(5) + _italians(2) + food_service,
        {"69": _ZONE_69, "70": _ZONE_70},
        _Areas(stand_in=False),
    )
    assert record.body["candidates"][0]["counts"] == {
        "restaurants_walk_5": 7,
        "italian_walk_10": 2,
    }
    assert record.body["candidates"][0]["checks"]["b_restaurants_walk_5"] is False
    with pytest.raises(PlacesError, match=r"^failed_candidate$"):
        validate_decision(Decision("SYN-CAND-1", record.digest, True), record)


def test_stand_in_stale_digest_and_hand_edit_are_refused() -> None:
    """A stand-in area, a stale digest and a hand-edited check do not select."""
    record = evaluate_candidates(
        (_candidate(_FOOT.wkb, "commercial"),),
        _restaurants(8) + _italians(2),
        {"69": _ZONE_69, "70": _ZONE_70},
        _Areas(stand_in=True),
    )
    assert record.body["candidates"][0]["passed_predicates"] is True
    assert record.passing_evidence is False
    assert record.passed_keys == ()
    with pytest.raises(PlacesError, match="stand_in_area"):
        validate_decision(Decision("SYN-CAND-1", record.digest, True), record)

    fresh = evaluate_candidates(
        (_candidate(_FOOT.wkb, "commercial"),),
        _restaurants(8) + _italians(2),
        {"69": _ZONE_69, "70": _ZONE_70},
        _Areas(stand_in=False),
    )
    fixture = decision_from_mapping(json.loads(_FIXTURE.read_text(encoding="utf-8")))
    assert fixture.candidate_key == "SYN-CAND-1"
    assert fixture.provisional is True
    with pytest.raises(PlacesError, match="stale_digest"):
        validate_decision(fixture, fresh)

    edited_body = json.loads(json.dumps(fresh.body))
    edited_body["candidates"][0]["checks"]["a_footprint_in_zones"] = False
    edited = CheckRecord(edited_body, digest_of(edited_body), True, ("SYN-CAND-1",))
    with pytest.raises(PlacesError, match="hand_edited"):
        validate_decision(Decision("SYN-CAND-1", edited.digest, True), edited)


def test_forged_evidence_and_passed_keys_are_refused() -> None:
    """A stand-in body marked as passing, and an extra passed key, are refused."""
    stand_in = evaluate_candidates(
        (_candidate(_FOOT.wkb, "commercial"),),
        _restaurants(6) + _italians(2),
        {"69": _ZONE_69, "70": _ZONE_70},
        _Areas(stand_in=True),
    )
    forged_body = json.loads(json.dumps(stand_in.body))
    forged_body["passing_evidence"] = True
    forged = CheckRecord(forged_body, digest_of(forged_body), True, ("SYN-CAND-1",))
    with pytest.raises(PlacesError, match="evidence_mismatch"):
        validate_decision(Decision("SYN-CAND-1", forged.digest, True), forged)
    record_only = CheckRecord(
        stand_in.body, stand_in.digest, True, stand_in.passed_keys
    )
    with pytest.raises(PlacesError, match="evidence_mismatch"):
        validate_decision(Decision("SYN-CAND-1", record_only.digest, True), record_only)
    body_only = json.loads(json.dumps(stand_in.body))
    body_only["passing_evidence"] = True
    body_forged = CheckRecord(body_only, digest_of(body_only), False, ())
    with pytest.raises(PlacesError, match="evidence_mismatch"):
        validate_decision(Decision("SYN-CAND-1", body_forged.digest, True), body_forged)

    failed = evaluate_candidates(
        (_candidate(_FOOT.wkb, "residential"),),
        _restaurants(6) + _italians(2),
        {"69": _ZONE_69, "70": _ZONE_70},
        _Areas(stand_in=False),
    )
    extra = CheckRecord(failed.body, failed.digest, True, ("SYN-CAND-1",))
    with pytest.raises(PlacesError, match="passed_keys_mismatch"):
        validate_decision(Decision("SYN-CAND-1", extra.digest, True), extra)


def test_one_area_error_fails_only_that_candidate() -> None:
    """A walk-5 error drops the second candidate and leaves the evidence true."""
    record = evaluate_candidates(
        (
            _candidate(_FOOT.wkb, "commercial", "SYN-CAND-1"),
            _candidate(_FOOT.wkb, "commercial", "SYN-CAND-2"),
        ),
        _restaurants(6) + _italians(2),
        {"69": _ZONE_69, "70": _ZONE_70},
        _FailWalk5("SYN-CAND-2"),
    )
    assert record.passing_evidence is True
    assert record.passed_keys == ("SYN-CAND-1",)
    second = record.body["candidates"][1]
    assert second["checks"]["d_areas_returned"] is False
    validate_decision(Decision("SYN-CAND-1", record.digest, True), record)
    with pytest.raises(PlacesError, match="failed_candidate"):
        validate_decision(Decision("SYN-CAND-2", record.digest, True), record)


def test_walk_10_error_fails_only_check_c_of_that_candidate() -> None:
    """A walk-10 error fails check (c) of that candidate and leaves (d) true."""
    record = evaluate_candidates(
        (
            _candidate(_FOOT.wkb, "commercial", "SYN-CAND-1"),
            _candidate(_FOOT.wkb, "commercial", "SYN-CAND-2"),
        ),
        _restaurants(8) + _italians(2),
        {"69": _ZONE_69, "70": _ZONE_70},
        _FailOneArea("SYN-CAND-2", "walk_10"),
    )
    assert record.passing_evidence is True
    assert record.passed_keys == ("SYN-CAND-1",)
    candidates = record.body["candidates"]
    assert isinstance(candidates, list)
    second = candidates[1]
    assert isinstance(second, dict)
    checks = second["checks"]
    assert isinstance(checks, dict)
    assert checks["c_italian_walk_10"] is False
    assert checks["d_areas_returned"] is True
    validate_decision(Decision("SYN-CAND-1", record.digest, True), record)
    with pytest.raises(PlacesError, match="failed_candidate"):
        validate_decision(Decision("SYN-CAND-2", record.digest, True), record)


def test_check_d_needs_walk_5_and_drive_10_and_ignores_other_errors() -> None:
    """Each operand of check (d) is required. A walk-10 error is not one of them."""
    from eii_custodian.publicdata.places.flagship import _walk_5_and_drive_10_returned

    both = {"walk_5": object(), "drive_10": object()}
    assert _walk_5_and_drive_10_returned({}, both) is True
    assert _walk_5_and_drive_10_returned({"walk_5": "engine_failed"}, both) is False
    assert _walk_5_and_drive_10_returned({"drive_10": "engine_failed"}, both) is False
    assert _walk_5_and_drive_10_returned({}, {"drive_10": object()}) is False
    assert _walk_5_and_drive_10_returned({}, {"walk_5": object()}) is False
    assert _walk_5_and_drive_10_returned({"walk_10": "engine_failed"}, both) is True


def test_a_real_flagged_decision_must_stay_provisional() -> None:
    """A passing real-area record refuses a decision that drops provisional."""
    record = evaluate_candidates(
        (_candidate(_FOOT.wkb, "commercial"),),
        _restaurants(8) + _italians(2),
        {"69": _ZONE_69, "70": _ZONE_70},
        _Areas(stand_in=False),
    )
    with pytest.raises(PlacesError, match="not_provisional"):
        validate_decision(Decision("SYN-CAND-1", record.digest, False), record)
    validate_decision(Decision("SYN-CAND-1", record.digest, True), record)


def test_no_candidates_is_not_passing_evidence() -> None:
    """An empty candidate list is not passing evidence."""
    record = evaluate_candidates(
        (),
        (),
        {"69": _ZONE_69, "70": _ZONE_70},
        _Areas(stand_in=False),
    )
    assert record.passing_evidence is False


def test_no_provider_is_not_passing_evidence() -> None:
    """Absence of a provider is its own field and its own refusal."""
    record = evaluate_candidates(
        (_candidate(_FOOT.wkb, "commercial"),),
        _restaurants(6) + _italians(2),
        {"69": _ZONE_69, "70": _ZONE_70},
        None,
    )
    assert record.passing_evidence is False
    assert record.body["provider_given"] is False
    assert record.body["candidates"][0]["inputs"]["area_errors"] == {
        "drive_10": "not_called",
        "walk_5": "not_called",
    }
    with pytest.raises(PlacesError, match="no_provider"):
        validate_decision(Decision("SYN-CAND-1", record.digest, True), record)

    named = evaluate_candidates(
        (_candidate(_FOOT.wkb, "commercial"),),
        _restaurants(6) + _italians(2),
        {"69": _ZONE_69, "70": _ZONE_70},
        _Areas(stand_in=False, fail="walk_5", reason="no_provider"),
    )
    assert named.passing_evidence is True
    assert named.body["candidates"][0]["inputs"]["area_errors"]["walk_5"] == (
        "no_provider"
    )
    with pytest.raises(PlacesError, match="failed_candidate"):
        validate_decision(Decision("SYN-CAND-1", named.digest, True), named)


def test_italian_places_count_toward_restaurants_and_status_filters() -> None:
    """(b) counts both classes. (c) counts Italian only. Closed rows are out."""
    zones = {"69": _ZONE_69, "70": _ZONE_70}
    provider = _Areas(stand_in=False)
    passing = evaluate_candidates(
        (_candidate(_FOOT.wkb, "commercial"),),
        _restaurants(6) + _italians(2),
        zones,
        provider,
    )
    assert passing.body["candidates"][0]["counts"]["restaurants_walk_5"] == 8
    assert passing.body["candidates"][0]["checks"]["b_restaurants_walk_5"] is True
    validate_decision(Decision("SYN-CAND-1", passing.digest, True), passing)

    short = evaluate_candidates(
        (_candidate(_FOOT.wkb, "commercial"),),
        _restaurants(5) + _italians(2),
        zones,
        provider,
    )
    assert short.body["candidates"][0]["counts"]["restaurants_walk_5"] == 7
    assert short.body["candidates"][0]["checks"]["b_restaurants_walk_5"] is False
    with pytest.raises(PlacesError, match="failed_candidate"):
        validate_decision(Decision("SYN-CAND-1", short.digest, True), short)

    mixed = (
        *_open_places(6, "restaurant", "SYN-RO"),
        CountedPlace("SYN-RC", 51.50, 25.30, "restaurant", "closed_or_moved"),
        *_open_places(1, "italian_restaurant", "SYN-IO"),
        CountedPlace("SYN-IN", 51.51, 25.31, "italian_restaurant", "not_found"),
    )
    filtered = evaluate_candidates(
        (_candidate(_FOOT.wkb, "commercial"),), mixed, zones, provider
    )
    counts = filtered.body["candidates"][0]["counts"]
    checks = filtered.body["candidates"][0]["checks"]
    assert counts["restaurants_walk_5"] == 7
    assert checks["b_restaurants_walk_5"] is False
    assert counts["italian_walk_10"] == 1
    assert checks["c_italian_walk_10"] is False
    with pytest.raises(PlacesError, match="failed_candidate"):
        validate_decision(Decision("SYN-CAND-1", filtered.digest, True), filtered)


def test_walk_10_italian_places_are_outside_walk_5() -> None:
    """Two Italian places between the walk polygons count for (c) only."""
    record = evaluate_candidates(
        (_candidate(_FOOT.wkb, "commercial"),),
        (
            CountedPlace(
                "SYN-I-0", 51.52, 25.32, "italian_restaurant", "verified_open"
            ),
            CountedPlace(
                "SYN-I-1", 51.53, 25.32, "italian_restaurant", "verified_open"
            ),
        ),
        {"69": _ZONE_69, "70": _ZONE_70},
        _SplitWalks(),
    )
    counts = record.body["candidates"][0]["counts"]
    assert counts["italian_walk_10"] == 2
    assert counts["restaurants_walk_5"] == 0


def test_zone_70_alone_holds_the_footprint() -> None:
    """A footprint inside zone 70, and not zone 69, passes check (a)."""
    footprint = box(51.92, 25.22, 51.96, 25.26)
    record = evaluate_candidates(
        (_candidate(footprint.wkb, "commercial"),),
        _restaurants(6) + _italians(2),
        {"69": _ZONE_69, "70": _ZONE_70},
        _Areas(stand_in=False),
    )
    assert record.body["candidates"][0]["checks"]["a_footprint_in_zones"] is True


@pytest.mark.parametrize("use", ["public", "commercial", "mixed"])
def test_landmark_use_accepts_each_listed_value(use: str) -> None:
    """Public, commercial and mixed each pass check (e)."""
    record = evaluate_candidates(
        (_candidate(_FOOT.wkb, use),),
        _restaurants(6) + _italians(2),
        {"69": _ZONE_69, "70": _ZONE_70},
        _Areas(stand_in=False),
    )
    assert record.body["candidates"][0]["checks"]["e_landmark_use"] is True
    assert record.passed_keys == ("SYN-CAND-1",)


def test_decision_mapping_refuses_an_extra_field_and_a_missing_digest() -> None:
    """The decision fixture has exactly the three allowed fields."""
    with pytest.raises(PlacesError, match="decision_fields"):
        decision_from_mapping(
            {
                "candidate_key": "SYN-CAND-1",
                "digest": "a" * 64,
                "provisional": True,
                "approved_by": "SYN reviewer",
            }
        )
    with pytest.raises(PlacesError, match="decision_fields"):
        decision_from_mapping({"candidate_key": "SYN-CAND-1", "provisional": True})


def _assert_digest(record: CheckRecord) -> None:
    encoded = json.dumps(
        record.body, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")
    assert hashlib.sha256(encoded).hexdigest() == record.digest
    assert digest_of(record.body) == record.digest


def _candidate(footprint: bytes, use: str, key: str = "SYN-CAND-1") -> CandidateInput:
    pin = Point(51.50, 25.30)
    return CandidateInput(key, footprint, use, pin.x, pin.y)


def _open_places(count: int, category: str, prefix: str) -> tuple[CountedPlace, ...]:
    return tuple(
        CountedPlace(
            f"{prefix}-{index}",
            51.46 + index * 0.01,
            25.30,
            category,
            "verified_open",
        )
        for index in range(count)
    )


def _restaurants(count: int) -> tuple[CountedPlace, ...]:
    return tuple(
        CountedPlace(
            f"SYN-R-{index}",
            51.46 + index * 0.01,
            25.30,
            "restaurant",
            "verified_open",
        )
        for index in range(count)
    )


def _italians(count: int) -> tuple[CountedPlace, ...]:
    return tuple(
        CountedPlace(
            f"SYN-I-{index}",
            51.47 + index * 0.01,
            25.31,
            "italian_restaurant",
            "verified_open",
        )
        for index in range(count)
    )


class _Areas:
    def __init__(
        self, stand_in: bool, fail: str = "", reason: str = "area_missing"
    ) -> None:
        self.stand_in = stand_in
        self.fail = fail
        self.reason = reason

    def area(
        self,
        point_key: str,
        point: ReviewedPoint,
        mode: AreaMode,
        cutoff: AreaCutoff,
    ) -> AreaResult:
        del point_key, point
        name = f"{mode.value}_{cutoff.value}"
        if name == self.fail:
            raise AreaError(self.reason)
        return AreaResult(
            _WALK.wkb,
            "stand-in.v0",
            "a" * 64,
            "b" * 64,
            "none",
            self.stand_in,
        )


class _FailWalk5:
    def __init__(self, key: str) -> None:
        self.key = key

    def area(
        self,
        point_key: str,
        point: ReviewedPoint,
        mode: AreaMode,
        cutoff: AreaCutoff,
    ) -> AreaResult:
        del point
        name = f"{mode.value}_{cutoff.value}"
        if point_key == self.key and name == "walk_5":
            raise AreaError("engine_failed")
        return AreaResult(_WALK.wkb, "stand-in.v0", "a" * 64, "b" * 64, "none", False)


class _FailOneArea:
    """Fails one named area for one candidate key. Other areas return."""

    def __init__(self, key: str, area_name: str) -> None:
        self.key = key
        self.area_name = area_name

    def area(
        self,
        point_key: str,
        point: ReviewedPoint,
        mode: AreaMode,
        cutoff: AreaCutoff,
    ) -> AreaResult:
        del point
        name = f"{mode.value}_{cutoff.value}"
        if point_key == self.key and name == self.area_name:
            raise AreaError("engine_failed")
        return AreaResult(_WALK.wkb, "stand-in.v0", "a" * 64, "b" * 64, "none", False)


class _SplitWalks:
    def area(
        self,
        point_key: str,
        point: ReviewedPoint,
        mode: AreaMode,
        cutoff: AreaCutoff,
    ) -> AreaResult:
        del point_key, point
        small = box(51.45, 25.25, 51.49, 25.29)
        wide = box(51.45, 25.25, 51.55, 25.35)
        polygon = small if cutoff is AreaCutoff.MINUTES_5 else wide
        return AreaResult(polygon.wkb, "stand-in.v0", "a" * 64, "b" * 64, "none", False)
