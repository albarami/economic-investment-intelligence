"""Exact-name and geometric ties; pages and points are visibly invented."""

from dataclasses import replace

import pytest
from custodian.tests.test_landmark_select import candidate
from custodian.tests.test_landmark_snapshots import BODY, STAMP, citation_setup
from hypothesis import given
from hypothesis import strategies as st
from shapely.geometry import Point, box

from eii_custodian.publicdata.fetch.build import run_build
from eii_custodian.publicdata.fetch.transport import Response
from eii_custodian.publicdata.heights.landmark_select import select_landmarks
from eii_custodian.publicdata.heights.landmark_tie import LandmarkPoint, tie_landmarks
from eii_custodian.publicdata.heights.model import Building


def selections(count=1):
    return select_landmarks(
        [
            candidate(landmark_id=f"SYN-LM-{i}", name_en=f"SYN Tower {i}")
            for i in range(count)
        ]
    ).admitted


def building(ident="SYN-B-A", geometry=None):
    return Building(
        ident, box(0, 0, 2, 2) if geometry is None else geometry, None, None, "SYN-FOOT"
    )


def fetched_selection(tmp_path, monkeypatch):
    from eii_custodian.publicdata.heights import landmarks
    from eii_custodian.publicdata.review.cache_fixture import select_fixture

    row, _ = citation_setup(monkeypatch)
    result = run_build(
        (row,),
        lambda u: Response(u, BODY, (), status=200),
        tmp_path,
        lambda: STAMP,
        lambda _: None,
        _fetch_only=True,
    )
    assert result.failure is None
    select_fixture(tmp_path, row.key, result.manifests[row.key])
    monkeypatch.setattr(landmarks, "_registry_by_url", lambda: {row.url: row})
    selected = select_landmarks(
        [candidate(page_url=row.url, retrieved_on="2026-11-20")]
    ).admitted
    point = LandmarkPoint("SYN-P-A", "SYN Example Tower", Point(0, 1))
    return selected, point


def test_tied_emits_snapshot_tokens_and_receipt_fields(tmp_path, monkeypatch):
    selected, point = fetched_selection(tmp_path, monkeypatch)
    result = tie_landmarks(selected, [point], [building()], tmp_path)
    assert result.outcomes == (("SYN-LM-A", "tied"),)
    emitted = result.document["entries"][0]
    assert emitted["height_m"] == "123.40"
    assert emitted["height_kind"] == "roof"
    assert emitted["citation"]["height_excerpt"] == "Roof: 123.40 m"
    assert emitted["citation"]["retrieved_on"] == STAMP[:10]
    assert len(emitted["citation"]["page_sha256"]) == 64
    assert "pending" not in result.document


@pytest.mark.parametrize(
    "plant,reason",
    [
        ("name", "no_point"),
        ("two_points", "several_points"),
        ("outside", "point_in_no_building"),
        ("two_buildings", "point_in_several_buildings"),
        ("shared_point", "point_claimed_twice"),
        ("shared_building", "building_claimed_twice"),
    ],
)
def test_each_tie_refusal_changes_one_input(tmp_path, plant, reason):
    selected = selections(2)
    points = [
        LandmarkPoint("SYN-P-A", "SYN Tower 0", Point(1, 1)),
        LandmarkPoint("SYN-P-B", "SYN Tower 1", Point(5, 1)),
    ]
    buildings = [building(), building("SYN-B-B", box(4, 0, 6, 2))]
    aliases = {}
    if plant == "name":
        points[0] = replace(points[0], name="SYN Tower zero")
    elif plant == "two_points":
        points.append(replace(points[0], point_id="SYN-P-C"))
    elif plant == "outside":
        points[0] = replace(points[0], geometry=Point(3, 1))
    elif plant == "two_buildings":
        buildings.append(building("SYN-B-C"))
    elif plant == "shared_point":
        selected = (selected[0], replace(selected[1], name_en=selected[0].name_en))
    elif plant == "shared_building":
        points[1] = replace(points[1], geometry=points[0].geometry)
    # Inspect ties without emitting the other valid row (no page I/O for refusal proof).
    from eii_custodian.publicdata.heights.landmark_tie import tie_outcomes

    outcomes = tie_outcomes(selected, points, buildings, aliases)
    assert outcomes[0][1] == reason


@given(st.integers(min_value=-4, max_value=4), st.integers(min_value=-4, max_value=4))
def test_point_cover_matches_exact_integer_oracle(x, y):
    from eii_custodian.publicdata.heights.landmark_tie import tie_outcomes

    point = LandmarkPoint("SYN-P", "syn, TOWER 0", Point(x, y))
    reason = "tied" if 0 <= x <= 2 and 0 <= y <= 2 else "point_in_no_building"
    assert tie_outcomes(selections(), [point], [building()], {}) == (
        ("SYN-LM-0", reason, "SYN-B-A" if reason == "tied" else None),
    )


def test_no_ties_keeps_closed_pending_reason(tmp_path):
    result = tie_landmarks(selections(), [], [], tmp_path)
    assert result.document == {
        "version": 1,
        "pending": "landmark_list_empty",
        "entries": [],
    }


def test_cache_writer_loads_and_verifies_before_publication(tmp_path, monkeypatch):
    from custodian.tests.test_publicdata_heights import _cited_page

    from eii_custodian.publicdata.heights import landmarks
    from eii_custodian.publicdata.heights.landmark_tie import (
        Ties,
        write_landmark_heights,
    )

    cache, _, _, rows, _ = _cited_page(tmp_path, monkeypatch)
    document = {"version": 1, "entries": [landmarks.landmark_record(rows[0])]}
    result = Ties(document, ((rows[0].landmark_id, "tied"),))
    target = write_landmark_heights(cache, result)
    assert target == cache / "review/landmark_heights.yaml"
    assert landmarks.load_landmark_heights(target) == rows
    # A changed height with the same present excerpt cannot replace the reviewed record.
    before = target.read_bytes()
    document["entries"][0]["height_m"] = "201.00"
    with pytest.raises(landmarks.HeightError) as error:
        write_landmark_heights(cache, result)
    assert error.value.detail == "height_excerpt_mismatch"
    assert target.read_bytes() == before


@given(
    st.floats(min_value=-180, max_value=180, allow_nan=False, allow_infinity=False),
    st.floats(min_value=-90, max_value=90, allow_nan=False, allow_infinity=False),
)
def test_crs84_point_domain_against_box_oracle(x, y):
    from eii_custodian.publicdata.heights.landmark_tie import tie_outcomes

    reason = "tied" if 0 <= x <= 2 and 0 <= y <= 2 else "point_in_no_building"
    assert (
        tie_outcomes(
            selections(),
            [LandmarkPoint("SYN-P", "SYN Tower 0", Point(x, y))],
            [building()],
            {},
        )[0][1]
        == reason
    )


def test_duplicate_claim_outcomes_are_independent_of_input_order():
    from eii_custodian.publicdata.heights.landmark_tie import tie_outcomes

    selected = selections(2)
    points = [
        LandmarkPoint("SYN-P-A", "SYN Tower 0", Point(1, 1)),
        LandmarkPoint("SYN-P-B", "SYN Tower 1", Point(1, 1)),
    ]
    original = tie_outcomes(selected, points, [building()], {})
    reversed_result = tie_outcomes(
        tuple(reversed(selected)), list(reversed(points)), [building()], {}
    )
    assert sorted(original) == sorted(reversed_result)
    assert [r[1] for r in original] == [
        "building_claimed_twice",
        "building_claimed_twice",
    ]


def test_aliases_use_exact_normalized_equality_only():
    from eii_custodian.publicdata.heights.landmark_tie import tie_outcomes

    point = LandmarkPoint("SYN-P", "\uff33\uff39\uff2e Alias, Tower", Point(1, 1))
    selected = selections()
    assert (
        tie_outcomes(
            selected, [point], [building()], {"SYN-LM-0": ("syn alias tower",)}
        )[0][1]
        == "tied"
    )
    assert (
        tie_outcomes(selected, [point], [building()], {"SYN-LM-0": ("syn alias",)})[0][
            1
        ]
        == "no_point"
    )


@pytest.mark.parametrize(
    "plant,detail",
    [
        ("registry", "registry_row"),
        ("height", "height_excerpt_mismatch"),
        ("selection", "page_snapshot"),
    ],
)
def test_tie_emission_refusals_have_valid_snapshots(
    tmp_path, monkeypatch, plant, detail
):
    from eii_custodian.publicdata.heights import landmarks

    selected, point = fetched_selection(tmp_path, monkeypatch)
    if plant == "registry":
        monkeypatch.setattr(landmarks, "_registry_by_url", lambda: {})
    elif plant == "selection":
        (tmp_path / "snapshot_pins.json").unlink()
    else:
        selected[0].page["height_m"] = "124.40"
    with pytest.raises(landmarks.HeightError) as error:
        tie_landmarks(selected, [point], [building()], tmp_path)
    assert (error.value.name, error.value.detail) == (
        "landmark_heights_citation",
        detail,
    )


@pytest.mark.parametrize("body", [b"\xff", b'{"inputs": []}'])
def test_malformed_citation_envelope_has_closed_refusal(tmp_path, monkeypatch, body):
    from eii_custodian.publicdata.fetch.page_records import selected_page
    from eii_custodian.publicdata.fetch.receipts import sha256_hex
    from eii_custodian.publicdata.fetch.snapshots import (
        publish_snapshot,
        read_snapshot,
        reviewed_selections,
    )
    from eii_custodian.publicdata.heights import landmark_tie, landmarks
    from eii_custodian.publicdata.review.cache_fixture import select_fixture

    selected, point = fetched_selection(tmp_path, monkeypatch)
    row = landmarks._registry_by_url()[selected[0].page["page_url"]]
    envelope = selected_page(tmp_path, row)
    sidecar = dict(envelope.sidecar, sha256=sha256_hex(body), bytes=len(body))
    malformed = publish_snapshot(tmp_path / row.key, "json", body, sidecar)
    select_fixture(tmp_path, row.key, malformed.sha256)
    # Isolate envelope consumption from selected_page's own shape checks;
    # the selected bytes, index and receipt still pass the snapshot verifier.
    monkeypatch.setattr(
        landmark_tie,
        "selected_page",
        lambda cache, entry: read_snapshot(
            cache / entry.key, reviewed_selections(cache)[entry.key]
        ),
    )
    with pytest.raises(landmarks.HeightError) as error:
        tie_landmarks(selected, [point], [building()], tmp_path)
    assert (error.value.name, error.value.detail) == (
        "landmark_heights_citation",
        "page_snapshot",
    )
