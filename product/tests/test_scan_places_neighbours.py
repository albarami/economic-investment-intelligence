"""Released visits and neighbours, never inferred from listing names."""

import pytest
from product.tests.scan_places_support import fixture, replace_rows

from eii_product.tools.scan_places import scan_places


def test_every_visit_period_is_a_public_fact():
    store, context, request, _ = fixture()
    base = dict(
        venue_key="SYN-venue",
        place_id="SYN-place",
        venue_kind="museum_or_exhibition",
        name_en="SYN Orchard",
        name_ar=None,
        region=None,
        indicator="visitors",
        value=12,
        unit="visits",
    )
    replace_rows(
        store, "visits", [dict(base, period="2024-01"), dict(base, period="2025-01")]
    )
    result = scan_places(store, request, context)
    assert len(result.payload.place_visits) == 2
    ids = {item.value.fact_id for item in result.payload.place_visits}
    assert {f.period for f in result.facts if f.fact_id in ids} == {
        "2024-01",
        "2025-01",
    }
    assert all(
        f.unit == "count" and f.provenance == "public"
        for f in result.facts
        if f.fact_id in ids
    )


def test_neighbour_flag_and_caveats():
    store, context, request, _ = fixture()
    assert scan_places(store, request, context).payload.found_near is None
    result = scan_places(store, dict(request, include_neighbours=True), context)
    assert result.payload.found_near is None
    assert result.blocks.found_near is None
    assert result.blocks.found_near_reason == "neighbours_geography_unreleased"
    assert "scan_places_neighbours" not in store.calls
    assert "found_near" not in result.model_dump()["payload"]
    assert "found_near" not in result.model_dump()["blocks"]


def test_neighbour_reason_survives_empty_and_out_of_scope():
    store, context, request, _ = fixture()
    for categories in (["place_category:SYN-food"], ["place_category:SYN-absent"]):
        replace_rows(store, "places", [])
        result = scan_places(
            store,
            dict(request, categories=categories, include_neighbours=True),
            context,
        )
        assert result.status in {"NO_DATA", "OUT_OF_SCOPE"}
        assert result.blocks.found_near_reason == "neighbours_geography_unreleased"


@pytest.mark.parametrize(
    "field,value",
    [
        ("found_near", [{"category": "SYN-food", "quotient": 2}]),
        ("quotient", 2),
        ("p_value", 0.1),
        ("places_incomplete", True),
    ],
)
def test_unreleased_neighbours_cannot_enter_payload(field, value):
    from eii_product.tools.scan_places import ScanPlacesResult

    store, context, request, _ = fixture()
    data = scan_places(store, request, context).model_dump()
    data["payload"][field] = value
    with pytest.raises(ValueError):
        ScanPlacesResult.model_validate(data)


@pytest.mark.parametrize(
    "field,value",
    [("indicator", "people_present"), ("busyness", 5), ("hidden_count", 2)],
)
def test_visits_cannot_be_relabelled_as_presence(field, value):
    from eii_product.tools.scan_places import Visit

    data = dict(
        place_id="SYN-place", indicator="visitors", value=dict(status="NO_DATA")
    )
    data[field] = value
    with pytest.raises(ValueError):
        Visit.model_validate(data)


def test_visits_do_not_join_by_name_or_across_tables():
    store, context, request, _ = fixture()
    replace_rows(
        store,
        "visits",
        [
            dict(
                venue_key="SYN-venue",
                place_id="SYN-other",
                venue_kind="museum_or_exhibition",
                name_en="SYN Orchard",
                name_ar=None,
                region=None,
                period="2025",
                indicator="visitors",
                value=12,
                unit="visits",
            )
        ],
    )
    result = scan_places(store, request, context)
    assert result.status == "OK"
    assert not result.payload.place_visits


def test_all_visit_indicators_and_periods_survive():
    store, context, request, _ = fixture()
    base = dict(
        venue_key="SYN-venue",
        place_id="SYN-place",
        venue_kind="museum_or_exhibition",
        name_en="SYN Orchard",
        name_ar=None,
        region=None,
        value=12,
        unit="visits",
    )
    rows = [
        dict(base, period=period, indicator=indicator)
        for period in ("2024", "2025")
        for indicator in ("visitors", "patient_visits")
    ]
    replace_rows(store, "visits", rows)
    result = scan_places(store, request, context)
    assert result.status == "OK"
    by_id = {fact.fact_id: fact for fact in result.facts}
    assert {
        (visit.indicator, by_id[visit.value.fact_id].period)
        for visit in result.payload.place_visits
    } == {
        ("visitors", "2024"),
        ("visitors", "2025"),
        ("patient_visits", "2024"),
        ("patient_visits", "2025"),
    }


@pytest.mark.parametrize(
    "scenario",
    [
        "OK",
        "NO_DATA",
        "OUT_OF_SCOPE",
        "INVALID_ARGUMENT",
        "INTERNAL",
        "release_mismatch",
    ],
)
@pytest.mark.parametrize("include", [False, True])
def test_neighbour_reason_and_serialization_every_branch(scenario, include):
    import json
    from dataclasses import replace

    store, context, request, _ = fixture()
    request = dict(request, include_neighbours=include)
    expected_status = scenario
    if scenario == "NO_DATA":
        replace_rows(store, "places", [])
    elif scenario == "OUT_OF_SCOPE":
        request["categories"] = ["place_category:SYN-absent"]
    elif scenario == "INVALID_ARGUMENT":
        request["area_id"] = "invalid"
    elif scenario == "INTERNAL":
        store.fetch = lambda *args: (_ for _ in ()).throw(RuntimeError("SYN-failure"))
    elif scenario == "release_mismatch":
        context = replace(context, area=replace(context.area, release_id="b" * 64))
        expected_status = "INVALID_ARGUMENT"
    result = scan_places(store, request, context)
    assert result.status == expected_status
    for data in (result.model_dump(), json.loads(result.model_dump_json())):
        assert "found_near" not in data["payload"]
        assert "found_near" not in data["blocks"]
        assert data["blocks"]["found_near_reason"] == (
            "neighbours_geography_unreleased" if include else None
        )
        assert data["caveat_keys"] == ["open_listings_incomplete"]


@pytest.mark.parametrize(
    "field,value",
    [
        ("places_fsq_reason", "invented"),
        ("found_near_reason", "invented"),
        ("found_near", [dict(category="SYN-food")]),
    ],
)
def test_block_reasons_are_closed(field, value):
    from eii_product.tools.scan_places import Blocks

    with pytest.raises(ValueError):
        Blocks.model_validate({field: value})


def test_backend_outputs_document_neighbour_deferral():
    from pathlib import Path

    text = (Path(__file__).parents[2] / "docs/08_BACKEND.md").read_text()
    section = text.split("`scan_places`\n", 1)[1].split("`compare_areas`", 1)[0]
    output = next(
        line for line in section.splitlines() if line.startswith("| Outputs |")
    )
    assert "neighbours_geography_unreleased" in output
    assert 'at most six "found near"' not in output
    assert "C6" in output
