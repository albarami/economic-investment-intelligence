"""Reviewed wholly-outside boundary parts and the required STAC part set.

Invented boundaries and fixtures only; no fetched file or network.
"""

import json
from dataclasses import replace

import pytest
from custodian.tests.building_fixture import COLLECTION, PARTS, manifest, world
from hypothesis import given, settings
from hypothesis import strategies as st
from shapely.geometry import MultiPolygon, Polygon, box
from shapely.ops import unary_union

from eii_custodian.publicdata import building_inputs
from eii_custodian.publicdata.building_inputs import (
    OUTSIDE_REVIEW,
    BuildingError,
    boundary_parts,
    dump,
    national_guard,
    outside_review,
    outside_review_document,
    part_hash,
    pinned,
)
from eii_custodian.publicdata.fetch.receipts import sha256_hex
from eii_custodian.publicdata.review.cache_fixture import write_cached

MAIN = box(51, 25, 51.4, 25.5)
ISLET = box(51.1, 26.3, 51.2, 26.4)
STRADDLE = box(51.5, 26.1, 51.6, 26.3)
TOUCH = box(51.5, 26.2, 51.6, 26.3)


def bnd_sha256(prepared):
    return pinned(prepared.cache, prepared.entries, prepared.selected, "bnd_hdx").sha256


def review_path(prepared):
    return prepared.cache.parent.parent / OUTSIDE_REVIEW


def write_review(prepared, listed, **changes):
    document = {
        "version": 1,
        "bnd_hdx_sha256": bnd_sha256(prepared),
        "outside_part_sha256": listed,
        **changes,
    }
    path = review_path(prepared)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(dump(document))
    return path


def refused(prepared, boundary, name, detail=None):
    with pytest.raises(BuildingError) as error:
        prepared.produce(boundary=boundary)
    assert error.value.name == name
    if detail is not None:
        assert error.value.detail == detail
    assert not (prepared.output / "manifest.buildings.json").exists()


def test_listed_outside_part_builds_and_the_manifest_counts_it(tmp_path):
    prepared = world(tmp_path)
    path = write_review(prepared, [part_hash(ISLET)])
    boundary = unary_union([MAIN, ISLET])
    prepared.produce(boundary=boundary)
    block = manifest(prepared)
    assert block["national_completeness"] is True
    assert block["boundary_bounds"] == [51.0, 25.0, 51.4, 26.4]
    scope = block["boundary_scope"]
    assert scope["in_box_bounds"] == [51.0, 25.0, 51.4, 25.5]
    assert scope["outside_parts"] == 1
    assert scope["outside_part_sha256"] == [part_hash(ISLET)]
    assert scope["outside_review_sha256"] == sha256_hex(path.read_bytes())
    assert "in_box_bounds" in scope["rule"]


def test_no_outside_part_and_no_file_records_none(tmp_path):
    prepared = world(tmp_path)
    prepared.produce()
    scope = manifest(prepared)["boundary_scope"]
    assert (scope["outside_parts"], scope["outside_review_sha256"]) == (0, None)


# Refusal rows 1-9 of plan 2 section 5; each changes one input of the valid world.


def test_row1_unlisted_outside_part_refuses(tmp_path):
    prepared = world(tmp_path)
    write_review(prepared, [])
    refused(
        prepared,
        unary_union([MAIN, ISLET]),
        "national_boundary_outside_frame_box",
        "unlisted",
    )


@pytest.mark.parametrize("part", [STRADDLE, TOUCH], ids=["straddles", "touches"])
def test_rows2_3_a_listed_part_meeting_the_edge_refuses(tmp_path, part):
    prepared = world(tmp_path)
    write_review(prepared, [part_hash(part)])
    refused(
        prepared,
        unary_union([MAIN, part]),
        "national_boundary_outside_frame_box",
        "straddling",
    )


@pytest.mark.parametrize(
    "extra", [part_hash(box(52, 27, 52.1, 27.1)), part_hash(MAIN)], ids=["none", "in"]
)
def test_rows4_5_a_listed_hash_of_no_outside_part_is_stale(tmp_path, extra):
    prepared = world(tmp_path)
    write_review(prepared, [part_hash(ISLET), extra])
    refused(prepared, unary_union([MAIN, ISLET]), "national_boundary_review_stale")


def test_row6_review_bound_to_another_boundary_snapshot_is_stale(tmp_path):
    prepared = world(tmp_path)
    write_review(prepared, [part_hash(ISLET)], bnd_hdx_sha256="0" * 64)
    refused(prepared, unary_union([MAIN, ISLET]), "national_boundary_review_stale")


@pytest.mark.parametrize(
    "body",
    [
        b"SYN not json",
        b"[]",
        {"SYN-extra": 1},
        {"version": True},
        {"version": 2},
        {"bnd_hdx_sha256": 7},
        {"outside_part_sha256": "SYN"},
        {"outside_part_sha256": [7]},
        "duplicate",
    ],
)
def test_row7_malformed_review_or_a_hash_listed_twice_refuses(tmp_path, body):
    prepared = world(tmp_path)
    if isinstance(body, bytes):
        path = write_review(prepared, [part_hash(ISLET)])
        path.write_bytes(body)
    elif body == "duplicate":
        write_review(prepared, [part_hash(ISLET)] * 2)
    else:
        write_review(prepared, [part_hash(ISLET)], **body)
    refused(prepared, unary_union([MAIN, ISLET]), "national_boundary_review")


def test_row8_outside_part_without_a_review_file_refuses(tmp_path):
    prepared = world(tmp_path)
    refused(
        prepared,
        unary_union([MAIN, ISLET]),
        "national_boundary_outside_frame_box",
        "unreviewed",
    )


@pytest.mark.parametrize(
    "boundary,detail",
    [
        (Polygon(), "boundary"),
        (Polygon([(51, 25), (51.1, 25.1), (51, 25.1), (51.1, 25)]), "boundary"),
        (ISLET, "no_inside_part"),
    ],
    ids=["empty", "invalid", "no-inside"],
)
def test_row9_empty_invalid_or_no_inside_part_refuses(tmp_path, boundary, detail):
    prepared = world(tmp_path)
    write_review(prepared, [part_hash(ISLET)])
    refused(prepared, boundary, "national_boundary_outside_frame_box", detail)


# The required part set is the items whose bbox meets in_box_bounds.


def guard(prepared, boundary=MAIN):
    return national_guard(prepared.cache, prepared.entries, prepared.selected, boundary)


@pytest.mark.parametrize("missing", PARTS)
def test_pinned_set_missing_a_required_part_refuses(tmp_path, monkeypatch, missing):
    prepared = world(tmp_path)
    guard(prepared)
    kept = tuple(part for part in PARTS if part != missing)
    monkeypatch.setattr(building_inputs, "BUILDING_PARTS", kept)
    with pytest.raises(BuildingError) as error:
        guard(prepared)
    assert error.value.name == "bldg_ovt_part_set_incomplete"


def add_item(prepared, number, bbox):
    """Register and link one more STAC item whose asset is no fixed part."""
    key = f"bldg_ovt/stac-part-{number}"
    row = replace(
        next(row for row in prepared.entries if row.key == COLLECTION),
        key=key,
        url=f"https://syn.invalid/{key}",
    )
    prepared.entries = (*prepared.entries, row)
    document = {
        "type": "Feature",
        "id": key,
        "bbox": bbox,
        "assets": {"data": {"href": f"https://syn.invalid/bldg_ovt/part-{number}"}},
        "links": [],
    }
    prepared.selected[key] = write_cached(
        prepared.cache, row, json.dumps(document).encode()
    ).stem
    collection = next(row for row in prepared.entries if row.key == COLLECTION)
    links = [
        {"rel": "item", "href": entry.url}
        for entry in prepared.entries
        if entry.key.startswith("bldg_ovt/stac-part-")
    ]
    body = {"type": "Collection", "id": "SYN-building", "links": links}
    prepared.selected[COLLECTION] = write_cached(
        prepared.cache, collection, json.dumps(body).encode()
    ).stem


def test_item_meeting_only_an_islet_or_south_of_the_boundary_is_not_required(
    tmp_path,
):
    prepared = world(tmp_path)
    write_review(prepared, [part_hash(ISLET)])
    add_item(prepared, "90001", [51.05, 26.25, 51.25, 26.45])
    add_item(prepared, "90002", [50.7, 24.4, 51.7, 24.9])
    scope, chain = guard(prepared, unary_union([MAIN, ISLET]))
    assert scope["in_box_bounds"] == [51.0, 25.0, 51.4, 25.5]
    assert {"bldg_ovt/stac-part-90001", "bldg_ovt/stac-part-90002"} <= set(chain)


def test_fixed_part_whose_item_misses_in_box_bounds_refuses(tmp_path):
    prepared = world(tmp_path)
    row = next(row for row in prepared.entries if row.key.endswith("stac-part-00385"))
    document = {
        "type": "Feature",
        "id": row.key,
        "bbox": [50.7, 24.4, 51.7, 24.9],
        "assets": {"data": {"href": f"https://syn.invalid/{PARTS[1]}"}},
        "links": [],
    }
    prepared.selected[row.key] = write_cached(
        prepared.cache, row, json.dumps(document).encode()
    ).stem
    with pytest.raises(BuildingError) as error:
        guard(prepared)
    assert error.value.name == "bldg_ovt_part_set_incomplete"


def test_item_meeting_in_box_bounds_with_a_foreign_asset_refuses(tmp_path):
    prepared = world(tmp_path)
    add_item(prepared, "90003", [51.3, 25.4, 51.5, 25.6])
    with pytest.raises(BuildingError) as error:
        guard(prepared)
    assert error.value.name == "bldg_ovt_part_set_incomplete"


# Edge classes over generated part sets (Hypothesis).

INSIDE_CELLS = [box(51.0 + 0.1 * i, 25.0, 51.05 + 0.1 * i, 25.05) for i in range(6)]
OUTSIDE_CELLS = [box(51.0 + 0.1 * i, 26.3, 51.05 + 0.1 * i, 26.35) for i in range(6)]
EDGE_INSIDE = box(51.0, 26.15, 51.05, 26.2)


def parts_strategy():
    return st.tuples(
        st.lists(st.sampled_from([*INSIDE_CELLS, EDGE_INSIDE]), unique=True),
        st.lists(st.sampled_from(OUTSIDE_CELLS), unique=True),
        st.randoms(use_true_random=False),
    )


@settings(max_examples=60, deadline=None)
@given(parts_strategy())
def test_split_hash_and_review_hold_over_generated_part_sets(drawn):
    inside, outside, rng = drawn
    parts = [*inside, *outside]
    rng.shuffle(parts)
    if not parts:
        return
    boundary = MultiPolygon(parts)
    if not inside:
        with pytest.raises(BuildingError) as error:
            boundary_parts(boundary)
        assert error.value.detail == "no_inside_part"
        return
    found_inside, found_outside = boundary_parts(boundary)
    assert len(found_inside) == len(inside)
    assert set(found_outside) == {part_hash(part) for part in outside}
    document = outside_review_document(boundary, "a" * 64)
    reversed_boundary = MultiPolygon(list(reversed(parts)))
    assert dump(document) == dump(outside_review_document(reversed_boundary, "a" * 64))
    assert document["outside_part_sha256"] == sorted(found_outside)


@settings(max_examples=40, deadline=None)
@given(parts_strategy(), st.booleans())
def test_review_admits_exactly_the_outside_parts(tmp_path_factory, drawn, longer):
    inside, outside, _rng = drawn
    if not inside:
        return
    boundary = MultiPolygon([*inside, *outside])
    path = tmp_path_factory.mktemp("review") / "review.json"
    document = outside_review_document(boundary, "a" * 64)
    if longer:
        document["outside_part_sha256"].append(part_hash(box(52, 27, 52.1, 27.1)))
    path.write_bytes(dump(document))
    _found_inside, found_outside = boundary_parts(boundary)
    if longer:
        with pytest.raises(BuildingError) as error:
            outside_review(path, found_outside, "a" * 64)
        assert error.value.name == "national_boundary_review_stale"
    else:
        assert outside_review(path, found_outside, "a" * 64) == sha256_hex(
            path.read_bytes()
        )


def test_part_touching_the_edge_from_inside_is_inside_and_from_outside_refuses():
    inside, outside = boundary_parts(MultiPolygon([MAIN, EDGE_INSIDE]))
    assert (len(inside), outside) == (2, {})
    with pytest.raises(BuildingError) as error:
        boundary_parts(MultiPolygon([MAIN, TOUCH]))
    assert error.value.detail == "straddling"


def test_the_existing_box_reaching_east_still_refuses():
    with pytest.raises(BuildingError) as error:
        boundary_parts(box(51, 25, 51.8, 25.5))
    assert (error.value.name, error.value.detail) == (
        "national_boundary_outside_frame_box",
        "straddling",
    )


def test_part_hash_ignores_ring_orientation_and_start_vertex():
    turned = Polygon([(51.2, 26.4), (51.2, 26.3), (51.1, 26.3), (51.1, 26.4)])
    assert part_hash(turned) == part_hash(ISLET)
    assert part_hash(ISLET) != part_hash(box(51.1, 26.3, 51.2, 26.41))


def test_fixed_parts_are_the_measured_required_set():
    assert building_inputs.BUILDING_PARTS == (
        "bldg_ovt/part-00384",
        "bldg_ovt/part-00385",
    )
