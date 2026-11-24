"""Verification overrides and separate released source blocks."""

from datetime import date
from decimal import Decimal

import pytest
from product.tests.scan_places_support import fixture, records, replace_rows

from eii_product.tools.scan_places import scan_places


@pytest.mark.parametrize(
    "status,visible",
    [
        ("verified_open", True),
        ("duplicate", True),
        ("closed_or_moved", False),
        ("not_found", False),
    ],
)
def test_latest_verification_status(status, visible):
    store, context, request, _ = fixture()
    replace_rows(
        store, "places", [dict(records(store, "places")[0], confidence=Decimal("0.1"))]
    )
    base = dict(
        place_id="SYN-place",
        reviewer_role="SYN-reviewer",
        verification_link="https://example.invalid/SYN",
        source_id="roads_osm",
    )
    older = dict(base, check_date=date(2024, 1, 1), status="closed_or_moved")
    newer = dict(base, check_date=date(2025, 1, 1), status=status)
    for rows in ([older, newer], [newer, older]):
        replace_rows(store, "verification", rows)
        result = scan_places(store, request, context)
        assert result.status == ("OK" if visible else "NO_DATA")
        assert bool(result.payload.places) is visible
        if visible:
            assert result.payload.places[0].verification_status == status


def test_separate_lists_and_missing_mapping():
    from dataclasses import replace

    store, context, request, _ = fixture()
    base = records(store, "places")[0]
    fsq = {
        key: base[key]
        for key in (
            "name",
            "name_ar",
            "lon",
            "lat",
            "cell",
            "source_release",
            "licence",
        )
    }
    fsq.update(
        fsq_place_id="SYN-place",
        category_ids="SYN-source-category",
        category_labels="SYN Food",
    )
    replace_rows(store, "fsq", [fsq])
    result = scan_places(store, dict(request, limit=1), context)
    assert len(result.payload.places) == len(result.payload.places_fsq) == 1
    assert (
        result.payload.places[0].distance.fact_id
        != result.payload.places_fsq[0].distance.fact_id
    )
    missing = scan_places(store, request, replace(context, mapping=None))
    assert missing.blocks.places_fsq == "NO_DATA" and not missing.payload.places_fsq
    assert missing.blocks.places == "OK"
    assert missing.blocks.places_fsq_reason == "mapping_missing"


@pytest.mark.parametrize("status", ["closed_or_moved", "not_found"])
def test_hidden_status_overrides_high_confidence(status):
    store, context, request, _ = fixture()
    replace_rows(
        store,
        "verification",
        [
            dict(
                place_id="SYN-place",
                check_date=date(2025, 1, 1),
                reviewer_role="SYN-reviewer",
                verification_link="https://example.invalid/SYN",
                status=status,
                source_id="roads_osm",
            )
        ],
    )
    result = scan_places(store, request, context)
    assert result.status == "NO_DATA"
    assert not result.payload.places


def test_unmapped_source_category_is_not_guessed():
    store, context, request, _ = fixture()
    base = records(store, "places")[0]
    row = {
        key: base[key]
        for key in (
            "name",
            "name_ar",
            "lon",
            "lat",
            "cell",
            "source_release",
            "licence",
        )
    }
    row.update(
        fsq_place_id="SYN-fsq", category_ids="SYN-unmapped", category_labels="SYN Food"
    )
    replace_rows(store, "fsq", [row])
    result = scan_places(store, request, context)
    assert result.status == "OK" and not result.payload.places_fsq
    row["category_ids"] = "SYN-unmapped;SYN-source-category"
    replace_rows(store, "fsq", [row])
    result = scan_places(store, request, context)
    assert result.payload.places_fsq[0].category == "place_category:SYN-food"
    assert result.payload.places_fsq[0].confidence.status == "NO_DATA"


def test_same_date_verification_is_a_release_defect():
    store, context, request, _ = fixture()
    row = dict(
        place_id="SYN-place",
        check_date=date(2025, 1, 1),
        reviewer_role="SYN-reviewer",
        verification_link="https://example.invalid/SYN",
        source_id="roads_osm",
        status="verified_open",
    )
    replace_rows(store, "verification", [row, dict(row, status="not_found")])
    assert scan_places(store, request, context).status == "INTERNAL"


def test_source_limits_do_not_count_across_or_deduplicate():
    store, context, request, _ = fixture()
    base = records(store, "places")[0]
    replace_rows(store, "places", [base, dict(base, place_id="SYN-second")])
    fsq = {
        key: base[key] for key in ("name", "name_ar", "lon", "lat", "cell", "licence")
    }
    fsq.update(
        fsq_place_id="SYN-place",
        source_release="2025-01-10",
        category_ids="SYN-source-category",
        category_labels="SYN Food",
    )
    replace_rows(store, "fsq", [fsq, dict(fsq, fsq_place_id="SYN-second")])
    for limit, expected in [(1, 1), (50, 2)]:
        result = scan_places(store, dict(request, limit=limit), context)
        assert result.status == "OK"
        assert len(result.payload.places) == expected
        assert len(result.payload.places_fsq) == expected
        assert all(p.source_table == "pub_place" for p in result.payload.places)
        assert all(p.source_table == "pub_place_fsq" for p in result.payload.places_fsq)
        assert all(p.confidence.status == "NO_DATA" for p in result.payload.places_fsq)


@pytest.mark.parametrize("provider", ["SYN-provider", "SYN-provider 7"])
def test_source_provider_output(provider):
    store, context, request, _ = fixture()
    base = dict(
        records(store, "places")[0], source_provider=provider, name="SYN Name 7"
    )
    replace_rows(store, "places", [base])
    fsq = {
        key: base[key] for key in ("name", "name_ar", "lon", "lat", "cell", "licence")
    }
    fsq.update(
        fsq_place_id="SYN-fsq",
        source_release="2025-01-10",
        category_ids="SYN-source-category",
        category_labels="SYN Food",
    )
    replace_rows(store, "fsq", [fsq])
    result = scan_places(store, request, context)
    place = result.payload.places[0]
    assert "source_provider" in place.model_dump()
    if provider == "SYN-provider":
        assert place.source_provider == provider
    else:
        assert place.source_provider.status == "OK"
        fact = next(
            f for f in result.facts if f.fact_id == place.source_provider.fact_id
        )
        assert fact.value == provider
        assert fact.unit == "published_text"
        assert fact.lineage_ref == "lin_pub_place"
        assert fact.provenance == "public" and fact.input_classes == ["public"]
        assert place.source_provider.fact_id != place.name_fact.fact_id
    assert result.payload.places_fsq[0].source_provider is None


@pytest.mark.parametrize("provider", ["SYN 7 ", "SYN \u0667"])
def test_invalid_provider_fact_is_no_data(provider):
    store, context, request, _ = fixture()
    replace_rows(
        store, "places", [dict(records(store, "places")[0], source_provider=provider)]
    )
    result = scan_places(store, request, context)
    assert result.status == "OK"
    assert result.payload.places[0].source_provider.status == "NO_DATA"


def test_provider_fact_requires_lineage():
    from dataclasses import replace

    store, context, request, _ = fixture()
    replace_rows(
        store, "places", [dict(records(store, "places")[0], source_provider="SYN 7")]
    )
    context = replace(
        context,
        chains={k: v for k, v in context.chains.items() if k != "lin_pub_place"},
    )
    result = scan_places(store, request, context)
    assert result.status == "OK"
    assert result.payload.places[0].source_provider.status == "NO_DATA"


@pytest.mark.parametrize("change", ["digit_label", "fsq_provider", "missing_fact"])
def test_provider_boundary_rejects_invalid_slot(change):
    from eii_product.tools.scan_places import Place, ScanPlacesResult, Slot

    store, context, request, _ = fixture()
    result = scan_places(store, request, context)
    place = result.payload.places[0]
    data = {key: getattr(place, key) for key in Place.model_fields}
    if change == "digit_label":
        data["source_provider"] = "SYN 7"
        with pytest.raises(ValueError, match="label_digit"):
            Place.model_validate(data)
    elif change == "fsq_provider":
        data["source_table"] = "pub_place_fsq"
        with pytest.raises(ValueError, match="provider_unavailable"):
            Place.model_validate(data)
    else:
        data["source_provider"] = Slot(status="OK", fact_id="f_" + "b" * 32)
        replacement = Place.model_validate(data)
        payload = result.payload.model_copy(update={"places": [replacement]})
        body = {key: getattr(result, key) for key in ScanPlacesResult.model_fields}
        with pytest.raises(ValueError, match="fact_reference_missing"):
            ScanPlacesResult.model_validate(dict(body, payload=payload))
