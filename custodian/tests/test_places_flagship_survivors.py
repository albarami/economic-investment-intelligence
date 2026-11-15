"""Mutation-killing regressions for the PUB-57 candidate and decision checks."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from copy import deepcopy
from typing import Any

import pytest
from custodian.tests.test_places_flagship import (
    _FOOT,
    _WALK,
    _ZONE_69,
    _ZONE_70,
    _Areas,
    _candidate,
    _italians,
    _restaurants,
)
from shapely.geometry import MultiPolygon, Polygon, box

from eii_custodian.publicdata.places import PlacesError, flagship
from eii_custodian.publicdata.places.areas import (
    AreaCutoff,
    AreaMode,
    AreaResult,
    ReviewedPoint,
)
from eii_custodian.publicdata.places.flagship import (
    CheckRecord,
    CountedPlace,
    Decision,
    decision_from_mapping,
    digest_of,
    evaluate_candidates,
    validate_decision,
)

_ALL_PASS = {
    "a_footprint_in_zones": True,
    "b_restaurants_walk_5": True,
    "c_italian_walk_10": True,
    "d_areas_returned": True,
    "e_landmark_use": True,
}
_BLANK = {
    "a_footprint_in_zones": False,
    "b_restaurants_walk_5": False,
    "c_italian_walk_10": False,
    "d_areas_returned": False,
    "e_landmark_use": False,
}


def _assert_refusal(call: Callable[[], object], expected: str) -> None:
    with pytest.raises(PlacesError) as caught:
        call()
    assert str(caught.value) == expected
    assert caught.value.reason == expected


def _passing_record() -> CheckRecord:
    return evaluate_candidates(
        (_candidate(_FOOT.wkb, "commercial"),),
        _restaurants(6) + _italians(2),
        {"69": _ZONE_69, "70": _ZONE_70},
        _Areas(stand_in=False),
    )


def _place_payloads() -> list[dict[str, object]]:
    return [
        {
            "place_id": place.place_id,
            "lon": place.lon,
            "lat": place.lat,
            "category_class": place.category_class,
            "status": place.status,
        }
        for place in _restaurants(6) + _italians(2)
    ]


def _valid_inputs() -> dict[str, object]:
    area = {"wkb_hex": _WALK.wkb.hex(), "stand_in": False}
    return {
        "footprint_wkb_hex": _FOOT.wkb.hex(),
        "zones": {"69": _ZONE_69.wkb.hex(), "70": _ZONE_70.wkb.hex()},
        "areas": {"walk_5": area, "walk_10": area, "drive_10": area},
        "area_errors": {},
        "places": _place_payloads(),
        "use": "commercial",
    }


def _validate_recomputed(
    inputs: dict[str, object], checks: dict[str, bool], refusal: str | None
) -> None:
    evidence = isinstance(inputs.get("areas"), dict)
    keys = ("SYN-CAND-1",) if evidence and all(checks.values()) else ()
    body: dict[str, object] = {
        "candidates": [
            {
                "candidate_key": "SYN-CAND-1",
                "checks": checks,
                "counts": {"restaurants_walk_5": 8, "italian_walk_10": 2},
                "passed_predicates": all(checks.values()),
                "use": inputs.get("use"),
                "inputs": inputs,
            }
        ],
        "method": "places.flagship.v1",
        "provider_given": True,
        "provisional": True,
        "passing_evidence": evidence,
    }
    record = CheckRecord(body, digest_of(body), evidence, keys)

    def call() -> None:
        validate_decision(Decision("SYN-CAND-1", record.digest, True), record)

    if refusal is None:
        call()
    else:
        _assert_refusal(call, refusal)


def _malformed_record(candidates: list[object]) -> CheckRecord:
    body: dict[str, object] = {
        "candidates": candidates,
        "method": "places.flagship.v1",
        "provider_given": True,
        "provisional": True,
        "passing_evidence": False,
    }
    return CheckRecord(body, digest_of(body), False, ())


def _assert_malformed_record_is_stand_in(record: CheckRecord) -> None:
    _assert_refusal(
        lambda: validate_decision(Decision("SYN-CAND-1", record.digest, True), record),
        "stand_in_area",
    )


def _decision_payload(
    key: Any = "SYN-CAND-1", digest: Any = "SYN-DIGEST", provisional: Any = True
) -> dict[str, Any]:
    return {"candidate_key": key, "digest": digest, "provisional": provisional}


def test_evaluate_body_and_input_schema_are_complete() -> None:
    record = _passing_record()
    assert set(record.body) == {
        "candidates",
        "method",
        "provider_given",
        "provisional",
        "passing_evidence",
    }
    assert record.body["method"] == "places.flagship.v1"
    assert record.body["provider_given"] is True
    assert record.body["provisional"] is True
    assert record.body["passing_evidence"] is True
    candidate = record.body["candidates"][0]
    assert set(candidate) == {
        "candidate_key",
        "checks",
        "counts",
        "passed_predicates",
        "use",
        "inputs",
    }
    assert candidate["use"] == "commercial"
    inputs = candidate["inputs"]
    assert set(inputs) == {
        "area_errors",
        "areas",
        "footprint_sha256",
        "footprint_wkb_hex",
        "lon",
        "lat",
        "places",
        "use",
        "zones",
    }
    for area in inputs["areas"].values():
        assert set(area) == {
            "engine_version",
            "graph_hash",
            "inputs_hash",
            "method_version",
            "stand_in",
            "wkb_sha256",
            "wkb_hex",
        }
    assert set(inputs["places"][0]) == {
        "category_class",
        "lat",
        "lon",
        "place_id",
        "status",
    }


def test_digest_escapes_non_ascii_before_hashing() -> None:
    expected = hashlib.sha256(b'{"label":"SYN Caf\\u00e9"}').hexdigest()
    assert digest_of({"label": "SYN Café"}) == expected


def test_every_decision_refusal_has_its_complete_reason() -> None:
    fresh = _passing_record()
    edited_body = deepcopy(fresh.body)
    edited_body["candidates"][0]["checks"]["a_footprint_in_zones"] = False
    edited = CheckRecord(edited_body, digest_of(edited_body), True, ("SYN-CAND-1",))
    _assert_refusal(
        lambda: validate_decision(Decision("SYN-CAND-1", edited.digest, True), edited),
        "hand_edited",
    )
    _assert_refusal(
        lambda: validate_decision(Decision("SYN-CAND-1", "SYN-STALE", True), fresh),
        "stale_digest",
    )
    _assert_refusal(
        lambda: validate_decision(Decision("SYN-CAND-1", fresh.digest, False), fresh),
        "not_provisional",
    )

    stand_in = evaluate_candidates(
        (_candidate(_FOOT.wkb, "commercial"),),
        _restaurants(6) + _italians(2),
        {"69": _ZONE_69, "70": _ZONE_70},
        _Areas(stand_in=True),
    )
    forged_body = deepcopy(stand_in.body)
    forged_body["passing_evidence"] = True
    forged = CheckRecord(forged_body, digest_of(forged_body), True, ("SYN-CAND-1",))
    _assert_refusal(
        lambda: validate_decision(Decision("SYN-CAND-1", forged.digest, True), forged),
        "evidence_mismatch",
    )

    failed = evaluate_candidates(
        (_candidate(_FOOT.wkb, "residential"),),
        _restaurants(6) + _italians(2),
        {"69": _ZONE_69, "70": _ZONE_70},
        _Areas(stand_in=False),
    )
    extra = CheckRecord(failed.body, failed.digest, True, ("SYN-CAND-1",))
    _assert_refusal(
        lambda: validate_decision(Decision("SYN-CAND-1", extra.digest, True), extra),
        "passed_keys_mismatch",
    )
    _assert_refusal(
        lambda: validate_decision(Decision("SYN-CAND-1", failed.digest, True), failed),
        "failed_candidate",
    )
    _assert_refusal(
        lambda: validate_decision(
            Decision("SYN-CAND-1", stand_in.digest, True), stand_in
        ),
        "stand_in_area",
    )

    without_provider = evaluate_candidates(
        (_candidate(_FOOT.wkb, "commercial"),),
        _restaurants(6) + _italians(2),
        {"69": _ZONE_69, "70": _ZONE_70},
        None,
    )
    _assert_refusal(
        lambda: validate_decision(
            Decision("SYN-CAND-1", without_provider.digest, True), without_provider
        ),
        "no_provider",
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [("candidate_key", 7), ("digest", 7), ("provisional", 1), ("provisional", None)],
)
def test_decision_mapping_rejects_each_wrong_field_type(field: str, value: Any) -> None:
    payload = _decision_payload()
    payload[field] = value
    _assert_refusal(lambda: decision_from_mapping(payload), "decision_fields")


def test_decision_mapping_rejects_field_set_changes_and_preserves_values() -> None:
    _assert_refusal(lambda: decision_from_mapping({}), "decision_fields")
    extra = _decision_payload()
    extra["approved_by"] = "SYN reviewer"
    _assert_refusal(lambda: decision_from_mapping(extra), "decision_fields")
    assert decision_from_mapping(_decision_payload()) == Decision(
        "SYN-CAND-1", "SYN-DIGEST", True
    )


class _RecordingAreas:
    def __init__(self) -> None:
        self.calls: list[tuple[str, ReviewedPoint, AreaMode, AreaCutoff]] = []

    def area(
        self,
        point_key: str,
        point: ReviewedPoint,
        mode: AreaMode,
        cutoff: AreaCutoff,
    ) -> AreaResult:
        self.calls.append((point_key, point, mode, cutoff))
        return AreaResult(
            _WALK.wkb, "syn.v1", "SYN-GRAPH", "SYN-INPUTS", "syn-engine", False
        )


def test_area_provider_receives_the_candidate_key_point_and_each_request() -> None:
    provider = _RecordingAreas()
    evaluate_candidates(
        (_candidate(_FOOT.wkb, "commercial"),), (), {"69": _ZONE_69}, provider
    )
    point = ReviewedPoint(51.5, 25.3)
    assert provider.calls == [
        ("SYN-CAND-1", point, AreaMode.WALK, AreaCutoff.MINUTES_5),
        ("SYN-CAND-1", point, AreaMode.WALK, AreaCutoff.MINUTES_10),
        ("SYN-CAND-1", point, AreaMode.DRIVE, AreaCutoff.MINUTES_10),
    ]


def test_missing_areas_and_area_payloads_count_zero() -> None:
    classes = frozenset({"restaurant"})
    assert flagship._count((), None, classes) == 0
    assert flagship._count_area((), None, classes) == 0
    assert flagship._count_area((), {"wkb_hex": None}, classes) == 0
    record = evaluate_candidates(
        (_candidate(_FOOT.wkb, "commercial"),), _restaurants(6), {"69": _ZONE_69}, None
    )
    assert record.body["candidates"][0]["counts"] == {
        "restaurants_walk_5": 0,
        "italian_walk_10": 0,
    }


def test_malformed_candidates_are_not_passing_evidence() -> None:
    _assert_malformed_record_is_stand_in(_malformed_record(["SYN-not-a-mapping"]))
    _assert_malformed_record_is_stand_in(
        _malformed_record(
            [{"candidate_key": "SYN-CAND-1", "checks": None, "inputs": None}]
        )
    )
    _assert_malformed_record_is_stand_in(
        _malformed_record(
            [
                {
                    "candidate_key": "SYN-CAND-1",
                    "checks": _BLANK,
                    "inputs": {"areas": None},
                }
            ]
        )
    )


def test_recompute_continues_past_each_malformed_candidate() -> None:
    valid = deepcopy(_passing_record().body["candidates"][0])
    _assert_malformed_record_is_stand_in(_malformed_record([None, valid]))
    invalid = deepcopy(valid)
    invalid["checks"] = None
    invalid["inputs"] = None
    _assert_malformed_record_is_stand_in(_malformed_record([invalid, valid]))


def test_all_pass_rejects_a_non_mapping() -> None:
    # Public validation refuses malformed evidence before it can call this helper.
    assert flagship._all_pass(None) is False


def test_recompute_guards_each_required_input_independently() -> None:
    missing_footprint = _valid_inputs()
    missing_footprint["footprint_wkb_hex"] = None
    _validate_recomputed(missing_footprint, _BLANK, "failed_candidate")
    missing_areas = _valid_inputs()
    missing_areas["areas"] = None
    _validate_recomputed(missing_areas, _BLANK, "stand_in_area")
    missing_places = _valid_inputs()
    missing_places["places"] = None
    _validate_recomputed(missing_places, _BLANK, "failed_candidate")


def test_recompute_unites_two_zones_for_a_footprint_in_the_second() -> None:
    inputs = _valid_inputs()
    inputs["footprint_wkb_hex"] = box(51.92, 25.22, 51.96, 25.26).wkb.hex()
    _validate_recomputed(inputs, _ALL_PASS, None)


def test_recompute_reads_one_zone_and_refuses_no_zone() -> None:
    one_zone = _valid_inputs()
    one_zone["zones"] = {"69": _ZONE_69.wkb.hex()}
    _validate_recomputed(one_zone, _ALL_PASS, None)
    no_zone = _valid_inputs()
    no_zone["zones"] = {}
    _validate_recomputed(
        no_zone, {**_ALL_PASS, "a_footprint_in_zones": False}, "failed_candidate"
    )


def test_recompute_skips_a_non_mapping_place_without_later_loss() -> None:
    inputs = _valid_inputs()
    places = inputs["places"]
    assert isinstance(places, list)
    inputs["places"] = ["SYN-not-a-mapping", *places]
    _validate_recomputed(inputs, _ALL_PASS, None)


def test_places_from_preserves_the_complete_place_id() -> None:
    parsed = flagship._places_from(
        [
            {
                "place_id": "SYN-UNIQUE",
                "lon": "51.5",
                "lat": "25.3",
                "category_class": "restaurant",
                "status": "verified_open",
            }
        ]
    )
    assert parsed == (
        CountedPlace("SYN-UNIQUE", 51.5, 25.3, "restaurant", "verified_open"),
    )


def test_blank_has_the_complete_five_check_literal() -> None:
    assert flagship._blank() == _BLANK


def _overlapping_zone() -> MultiPolygon:
    """Two squares that share a band. The shape is not a valid collection."""
    left = Polygon(((0, 0), (2, 0), (2, 2), (0, 2), (0, 0)))
    right = Polygon(((1, 0), (3, 0), (3, 2), (1, 2), (1, 0)))
    return MultiPolygon([left, right])


def test_one_overlapping_zone_covers_the_shared_part() -> None:
    """The first evaluation unites one stored zone before the footprint test."""
    footprint = box(0.5, 0.5, 2.5, 1.5)
    record = evaluate_candidates(
        (_candidate(footprint.wkb, "commercial"),),
        (),
        {"69": _overlapping_zone()},
        None,
    )
    checks = record.body["candidates"][0]["checks"]
    assert isinstance(checks, dict)
    assert checks["a_footprint_in_zones"] is True


def test_recompute_unites_one_zone_whose_parts_overlap() -> None:
    """The stored-input evaluation unites that same one zone."""
    footprint = box(0.5, 0.5, 2.5, 1.5)
    inputs = _valid_inputs()
    inputs["zones"] = {"69": _overlapping_zone().wkb.hex()}
    inputs["footprint_wkb_hex"] = footprint.wkb.hex()
    assert flagship._checks_from_inputs(inputs)["a_footprint_in_zones"] is True
