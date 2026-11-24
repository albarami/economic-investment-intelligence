"""Invented Public place facts: narrow application vocabulary (L1, L8)."""

from decimal import Decimal

import pytest

from eii_core.facts import Fact, fact_id


def candidate(**changes):
    row = dict(
        fact_id="f_" + "a" * 32,
        value=Decimal("2"),
        unit="metres",
        period="2025",
        geography={"kind": "public", "public_code": "place:SYN-a"},
        provenance="public",
        input_classes=["public"],
        evidence_status="observed",
        reliability="not_applicable",
        coverage_keys=[],
        caveat_keys=["open_listings_incomplete"],
        label_en="Distance",
        label_ar="المسافة",
        lineage_ref="lin_road_link_scan_places_distance",
        release_id="a" * 64,
    )
    row.update(changes)
    return row


@pytest.mark.parametrize(
    "unit,value", [("metres", Decimal("2")), ("calendar_date", "2024-02-29")]
)
def test_place_units(unit, value):
    assert Fact.model_validate(candidate(unit=unit, value=value)).value == value


@pytest.mark.parametrize(
    "value", ["2025-02-29", "2025-04-31", "2025-3-14", "2025-03", True, None]
)
def test_invalid_calendar_date(value):
    with pytest.raises(ValueError):
        Fact.model_validate(candidate(unit="calendar_date", value=value))


@pytest.mark.parametrize(
    "change",
    [
        {"evidence_status": "inferred"},
        {"reliability": "standard"},
        {"provenance": "synthetic", "input_classes": ["synthetic"]},
    ],
)
def test_calendar_date_public_only(change):
    with pytest.raises(ValueError):
        Fact.model_validate(
            candidate(unit="calendar_date", value="2024-02-29", **change)
        )


@pytest.mark.parametrize(
    "metric",
    [
        "place_distance_metres",
        "place_confidence",
        "venue_visits",
        "found_near_quotient",
        "place_source_release",
        "place_check_date",
        "place_name",
        "place_licence",
        "place_source_attribution",
    ],
)
@pytest.mark.parametrize(
    "qualifier",
    [
        "source_table",
        "origin",
        "routing_method",
        "routing_graph",
        "category",
        "language",
    ],
)
def test_place_semantic_vocabulary(metric, qualifier):
    assert fact_id(
        release_id="a" * 64,
        metric_key=metric,
        geography={"kind": "national"},
        period="2025",
        qualifiers={qualifier: "SYN-fixture"},
    ).startswith("f_")


@pytest.mark.parametrize("change", [{"unit": "invented"}, {"rating": 5}])
def test_unknown_fact_fields_and_units(change):
    with pytest.raises(ValueError):
        Fact.model_validate(candidate(**change))


def test_unknown_semantics():
    args = dict(
        release_id="a" * 64,
        metric_key="place_confidence",
        geography={"kind": "national"},
        period="2025",
        qualifiers={},
    )
    with pytest.raises(ValueError):
        fact_id(**dict(args, metric_key="invented"))
    with pytest.raises(ValueError):
        fact_id(**dict(args, qualifiers={"invented": "SYN-value"}))


@pytest.mark.parametrize(
    "field",
    ["table_name", "transform", "retrieved_on", "title", "sha256", "licence", "url"],
)
@pytest.mark.parametrize("table", ["road_link", "pub_place"])
def test_distance_facts_have_source_chains(field, table):
    from product.tests.scan_places_support import fixture, records, replace_rows

    from eii_product.tools.scan_places import scan_places

    store, context, request, _ = fixture()
    target = "lineage" if field in {"table_name", "transform"} else "sources"
    rows = records(store, target)
    for row in rows:
        if target == "sources" or row["table_name"] == table:
            row[field] = ""
    replace_rows(store, target, rows)
    result = scan_places(store, request, context)
    assert result.status != "INTERNAL"
    if table == "road_link" or target == "sources":
        assert result.status == "NO_DATA"
        assert not result.payload.places
    else:
        assert result.payload.places[0].confidence.status == "NO_DATA"


@pytest.mark.parametrize(
    "value",
    [
        "SYN Cafe 7",
        "SYN Cafe \u0667",
        " SYN Cafe 7",
        "SYN Cafe " + "1" * 8,
        "SYN Cafe " + "1" * 11,
    ],
)
def test_digit_name_is_published_text_fact(value):
    from product.tests.scan_places_support import fixture, records, replace_rows

    from eii_product.tools.scan_places import scan_places

    store, context, request, _ = fixture()
    replace_rows(store, "places", [dict(records(store, "places")[0], name=value)])
    result = scan_places(store, request, context)
    place = result.payload.places[0]
    assert place.name is None
    if value == "SYN Cafe 7":
        assert not place.name_unshowable
        fact = next(f for f in result.facts if f.fact_id == place.name_fact.fact_id)
        assert fact.unit == "published_text" and fact.value == value
    else:
        assert place.name_unshowable
        assert place.name_fact.status == "NO_DATA"


def test_plain_name_is_label():
    from product.tests.scan_places_support import fixture

    from eii_product.tools.scan_places import scan_places

    store, context, request, _ = fixture()
    place = scan_places(store, request, context).payload.places[0]
    assert place.name == "SYN Orchard" and place.name_ar is None
    assert place.name_fact.status == "NO_DATA"


@pytest.mark.parametrize("table", ["road_link", "pub_place"])
def test_missing_lineage_drops_slot(table):
    from product.tests.scan_places_support import fixture, records, replace_rows

    from eii_product.tools.scan_places import scan_places

    store, context, request, _ = fixture()
    replace_rows(
        store,
        "lineage",
        [r for r in records(store, "lineage") if r["table_name"] != table],
    )
    result = scan_places(store, request, context)
    if table == "road_link":
        assert result.status == "NO_DATA" and not result.payload.places
    else:
        assert result.status == "OK"
        assert result.payload.places[0].confidence.status == "NO_DATA"


def test_incomplete_inputs_are_not_filled():
    from dataclasses import replace

    from product.tests.scan_places_support import fixture

    from eii_product.tools.scan_places import scan_places

    store, context, request, _ = fixture()
    key = "lin_road_link_scan_places_distance"
    chain = context.chains[key][0]
    context = replace(
        context,
        chains={**context.chains, key: (chain, replace(chain, dataset="SYN-absent"))},
    )
    result = scan_places(store, request, context)
    assert result.status == "NO_DATA" and not result.facts


def test_every_fact_chain_and_drop():
    from product.tests.scan_places_support import fixture, records

    from eii_core.facts import validate_chain
    from eii_product.tools.scan_places import scan_places

    store, context, request, _ = fixture()
    result = scan_places(store, request, context)
    assert result.facts
    for fact in result.facts:
        assert (
            validate_chain(
                fact.lineage_ref,
                records(store, "lineage"),
                records(store, "sources"),
                required_sources=context.chains[fact.lineage_ref],
            )
            is None
        )


def test_semantic_fact_identity():
    from dataclasses import replace

    from product.tests.scan_places_support import fixture

    from eii_product.tools.make_area import make_area
    from eii_product.tools.scan_places import scan_places

    store, context, request, _ = fixture()

    def distance_id(req, ctx):
        return scan_places(store, req, ctx).payload.places[0].distance.fact_id

    original = distance_id(request, context)
    for longitude, cutoff, same in [
        (Decimal(0), 500, True),
        (Decimal("0.001"), 250, False),
    ]:
        area = make_area(
            store,
            dict(
                latitude=Decimal(0), longitude=longitude, mode="distance", cutoff=cutoff
            ),
            context.area,
        )
        changed = distance_id(dict(request, area_id=area.payload["area_id"]), context)
        assert (original == changed) is same
    changed = scan_places(store, request, replace(context, graph="SYN-other-graph"))
    assert changed.status == "NO_DATA"
    assert not changed.payload.places
    assert not changed.facts


@pytest.mark.parametrize(
    "value",
    [
        "SYN 7 ",
        "SYN\n7",
        "SYN\u202e7",
        "SYN\u20287",
        "SYN\u20297",
        "7" + "a" * 200,
        "SYN \u0667",
    ],
)
def test_unshowable_digit_name_is_omitted_with_flag(value):
    from product.tests.scan_places_support import fixture, records, replace_rows

    from eii_product.tools.scan_places import scan_places

    store, context, request, _ = fixture()
    replace_rows(store, "places", [dict(records(store, "places")[0], name=value)])
    result = scan_places(store, request, context)
    assert result.status == "OK"
    place = result.payload.places[0]
    assert place.name is None and place.name_unshowable
    assert place.name_fact.status == "NO_DATA"
    assert all(f.value != value for f in result.facts)


def test_source_release_and_check_date_are_facts():
    from datetime import date

    from product.tests.scan_places_support import fixture, replace_rows

    from eii_product.tools.scan_places import scan_places

    store, context, request, _ = fixture()
    replace_rows(
        store,
        "verification",
        [
            dict(
                place_id="SYN-place",
                check_date=date(2024, 2, 29),
                reviewer_role="SYN-reviewer",
                verification_link="https://example.invalid/SYN",
                status="verified_open",
                source_id="roads_osm",
            )
        ],
    )
    result = scan_places(store, request, context)
    place = result.payload.places[0]
    assert place.check_date.status == "OK"
    fact = next(f for f in result.facts if f.fact_id == place.check_date.fact_id)
    assert fact.value == "2024-02-29" and fact.unit == "calendar_date"
    assert "verification_link" not in place.model_dump()


def credit_fixture(table, licence="SYN-licence", attribution="SYN attribution"):
    from dataclasses import replace

    from product.tests.scan_places_support import fixture, records, replace_rows

    store, context, request, _ = fixture()
    base = dict(records(store, "places")[0], licence=licence, name="SYN Name 7")
    replace_rows(store, "places", [base])
    if table == "pub_place_fsq":
        replace_rows(store, "places", [dict(base, licence="SYN other licence")])
        row = {
            key: base[key]
            for key in ("name", "name_ar", "lon", "lat", "cell", "licence")
        }
        row.update(
            fsq_place_id="SYN-place",
            category_ids="SYN-source-category",
            category_labels="SYN Food",
            source_release="2025-01-10",
        )
        replace_rows(store, "fsq", [row])
        # Distinct registry metadata prevents attribution borrowed from roads
        # or from the first registry row from satisfying the test.
        sources = records(store, "sources")
        sources.append(
            dict(
                sources[0],
                source_id="SYN-fsq-source",
                publisher="SYN FSQ publisher",
                title="SYN FSQ dataset",
                attribution=attribution,
            )
        )
        replace_rows(store, "sources", sources)
        lines = records(store, "lineage")
        for line in lines:
            if line["table_name"] == table:
                line["source_id"] = "SYN-fsq-source"
        replace_rows(store, "lineage", lines)
        key = "lin_pub_place_fsq"
        chain = replace(
            context.chains[key][0],
            publisher="SYN FSQ publisher",
            dataset="SYN FSQ dataset",
        )
        context = replace(context, chains={**context.chains, key: (chain,)})
    return store, context, request


def credit_place(result, table):
    assert result.status == "OK"
    return (
        result.payload.places[0]
        if table == "pub_place"
        else result.payload.places_fsq[0]
    )


@pytest.mark.parametrize("table", ["pub_place", "pub_place_fsq"])
@pytest.mark.parametrize("licence", ["SYN-licence", "SYN licence 2.0"])
def test_place_licence_label_or_own_fact(table, licence):
    from eii_product.tools.scan_places import scan_places

    store, context, request = credit_fixture(table, licence)
    result = scan_places(store, request, context)
    place = credit_place(result, table)
    if licence == "SYN-licence":
        assert place.licence == licence
    else:
        assert place.licence.status == "OK"
        fact = next(f for f in result.facts if f.fact_id == place.licence.fact_id)
        assert fact.value == licence and fact.unit == "published_text"
        assert fact.lineage_ref == "lin_" + table
        assert fact.geography["public_code"] == "place:SYN-place"
        assert fact.fact_id == fact_id(
            release_id=result.release_id,
            metric_key="place_licence",
            geography={"kind": "public", "public_code": "place:SYN-place"},
            period="2025-01-10" if table == "pub_place_fsq" else "2025-01-01",
            qualifiers={"source_table": table},
        )
        assert fact.fact_id != place.name_fact.fact_id


@pytest.mark.parametrize("attribution", ["SYN attribution", "SYN attribution 2.0"])
def test_fsq_attribution_uses_matched_registry_chain(attribution):
    from eii_product.tools.scan_places import scan_places

    store, context, request = credit_fixture("pub_place_fsq", attribution=attribution)
    result = scan_places(store, request, context)
    place = credit_place(result, "pub_place_fsq")
    assert result.payload.places[0].source_attribution is None
    if attribution == "SYN attribution":
        assert place.source_attribution == attribution
    else:
        assert place.source_attribution.status == "OK"
        fact = next(
            f for f in result.facts if f.fact_id == place.source_attribution.fact_id
        )
        assert fact.value == attribution and fact.unit == "published_text"
        assert fact.lineage_ref == "lin_pub_place_fsq"
        assert fact.fact_id == fact_id(
            release_id=result.release_id,
            metric_key="place_source_attribution",
            geography={"kind": "public", "public_code": "place:SYN-place"},
            period="2025-01-10",
            qualifiers={"source_table": "pub_place_fsq"},
        )
        assert fact.fact_id != place.name_fact.fact_id


@pytest.mark.parametrize("table", ["pub_place", "pub_place_fsq"])
@pytest.mark.parametrize("value", ["SYN licence", "SYN licence 2.0"])
@pytest.mark.parametrize("broken", ["expected", "lineage", "registry"])
def test_place_credits_require_their_own_chain(table, value, broken):
    from dataclasses import replace

    from product.tests.scan_places_support import records, replace_rows

    from eii_product.tools.scan_places import scan_places

    store, context, request = credit_fixture(table, value, value)
    lineage = "lin_" + table
    if broken == "expected":
        context = replace(
            context, chains={k: v for k, v in context.chains.items() if k != lineage}
        )
    else:
        lines = records(store, "lineage")
        for line in lines:
            if line["lineage_id"] == lineage:
                line["source_id"] = (
                    "SYN-absent" if broken == "registry" else "roads_osm"
                )
                if broken == "lineage":
                    line["table_name"] = "road_link"
        replace_rows(store, "lineage", lines)
    result = scan_places(store, request, context)
    place = credit_place(result, table)
    assert place.licence.status == "NO_DATA"
    if table == "pub_place_fsq":
        assert place.source_attribution.status == "NO_DATA"
    assert value not in result.model_dump_json()


@pytest.mark.parametrize("value", ["SYN 7 ", "SYN \u0667", "SYN\n7"])
def test_invalid_place_credits_never_become_labels(value):
    from eii_product.tools.scan_places import scan_places

    store, context, request = credit_fixture("pub_place_fsq", value, value)
    result = scan_places(store, request, context)
    place = credit_place(result, "pub_place_fsq")
    assert place.licence.status == place.source_attribution.status == "NO_DATA"
    assert all(f.value != value for f in result.facts)


@pytest.mark.parametrize("field", ["licence", "source_attribution"])
@pytest.mark.parametrize("plant", ["digit_label", "missing_fact"])
def test_credit_boundary_rejects_invalid_slot(field, plant):
    from eii_product.tools.scan_places import Place, ScanPlacesResult, Slot, scan_places

    store, context, request = credit_fixture("pub_place_fsq")
    result = scan_places(store, request, context)
    data = result.payload.places_fsq[0].model_dump()
    if plant == "digit_label":
        data[field] = "SYN 7"
        with pytest.raises(ValueError, match="label_digit"):
            Place.model_validate(data)
    else:
        data[field] = Slot(status="OK", fact_id="f_" + "b" * 32)
        replacement = Place.model_validate(data)
        payload = result.payload.model_copy(update={"places_fsq": [replacement]})
        body = {key: getattr(result, key) for key in ScanPlacesResult.model_fields}
        with pytest.raises(ValueError, match="fact_reference_missing"):
            ScanPlacesResult.model_validate(dict(body, payload=payload))


def test_attribution_is_not_an_invented_primary_place_field():
    from eii_product.tools.scan_places import Place, scan_places

    store, context, request = credit_fixture("pub_place")
    data = scan_places(store, request, context).payload.places[0].model_dump()
    data["source_attribution"] = "SYN attribution"
    with pytest.raises(ValueError, match="attribution_unavailable"):
        Place.model_validate(data)


@pytest.mark.parametrize("plant", ["empty", "ambiguous"])
def test_fsq_attribution_is_not_filled_from_another_source(plant):
    from product.tests.scan_places_support import records, replace_rows

    from eii_product.tools.scan_places import scan_places

    store, context, request = credit_fixture("pub_place_fsq", attribution="")
    if plant == "ambiguous":
        sources = records(store, "sources")
        sources[-1]["attribution"] = "SYN attribution"
        sources.append(
            dict(sources[-1], source_id="SYN-other-source", attribution="SYN other")
        )
        replace_rows(store, "sources", sources)
        lines = records(store, "lineage")
        fsq_line = next(r for r in lines if r["table_name"] == "pub_place_fsq")
        replace_rows(
            store, "lineage", [*lines, dict(fsq_line, source_id="SYN-other-source")]
        )
    place = credit_place(scan_places(store, request, context), "pub_place_fsq")
    assert place.source_attribution.status == "NO_DATA"


@pytest.mark.parametrize(
    "release", ["2024-02-29", "2025-02-29", "2025-01", "2025-1-01"]
)
def test_fsq_source_date_is_verbatim_or_no_data(release):
    from product.tests.scan_places_support import fixture, records, replace_rows

    from eii_product.tools.scan_places import scan_places

    store, context, request, _ = fixture()
    base = records(store, "places")[0]
    row = {
        key: base[key] for key in ("name", "name_ar", "lon", "lat", "cell", "licence")
    }
    row.update(
        fsq_place_id="SYN-fsq",
        category_ids="SYN-source-category",
        category_labels="SYN Food",
        source_release=release,
    )
    replace_rows(store, "fsq", [row])
    result = scan_places(store, request, context)
    assert result.status == "OK"
    place = result.payload.places_fsq[0]
    if release == "2024-02-29":
        assert place.source_release.status == "OK"
        fact = next(
            f for f in result.facts if f.fact_id == place.source_release.fact_id
        )
        assert fact.value == release and fact.unit == "calendar_date"
    else:
        assert place.source_release.status == "NO_DATA"
        assert all(f.value != release for f in result.facts)


def test_wrong_road_source_drops_distance():
    from product.tests.scan_places_support import fixture, records, replace_rows

    from eii_product.tools.scan_places import scan_places

    store, context, request, _ = fixture()
    # A valid alternate source row reaches the road-specific guard, rather than
    # failing generic missing-source validation first.
    sources = records(store, "sources")
    sources.append(dict(sources[0], source_id="SYN-unrelated"))
    replace_rows(store, "sources", sources)
    lines = records(store, "lineage")
    for row in lines:
        if row["table_name"] == "road_link":
            row["source_id"] = "SYN-unrelated"
    replace_rows(store, "lineage", lines)
    result = scan_places(store, request, context)
    assert result.status == "NO_DATA" and not result.payload.places


@pytest.mark.parametrize("table", ["road_link", "pub_place"])
def test_transform_must_match_release_context(table):
    from product.tests.scan_places_support import fixture, records, replace_rows

    from eii_product.tools.scan_places import scan_places

    store, context, request, _ = fixture()
    lines = records(store, "lineage")
    for row in lines:
        if row["table_name"] == table:
            row["transform"] = "invented.other_method@v1"
    replace_rows(store, "lineage", lines)
    result = scan_places(store, request, context)
    if table == "road_link":
        assert result.status == "NO_DATA" and not result.payload.places
    else:
        assert result.status == "OK"
        assert result.payload.places[0].confidence.status == "NO_DATA"


@pytest.mark.parametrize(
    "field,value", [("table", "pub_place"), ("lineage_ref", "lin_wrong")]
)
def test_expected_chain_is_bound_to_distance(field, value):
    from dataclasses import replace

    from product.tests.scan_places_support import fixture

    from eii_product.tools.scan_places import scan_places

    store, context, request, _ = fixture()
    lineage = "lin_road_link_scan_places_distance"
    chain = replace(context.chains[lineage][0], **{field: value})
    context = replace(context, chains={**context.chains, lineage: (chain,)})
    result = scan_places(store, request, context)
    assert result.status == "NO_DATA" and not result.payload.places


@pytest.mark.parametrize("table", ["road_link", "pub_place"])
@pytest.mark.parametrize(
    "field",
    [
        "publisher",
        "title",
        "licence",
        "url",
        "sha256",
        "retrieved_on",
        "table_name",
        "transform",
        "missing_lineage",
    ],
)
def test_chain_field_reaches_own_slot(table, field):
    from product.tests.scan_places_support import fixture, records, replace_rows

    from eii_core.facts import validate_chain
    from eii_product.tools.scan_places import _Facts

    store, context, _, _ = fixture()
    lineage = "lin_" + table + ("_scan_places_distance" if table == "road_link" else "")
    target = (
        "lineage"
        if field in {"table_name", "transform", "missing_lineage"}
        else "sources"
    )
    rows = records(store, target)
    if field == "missing_lineage":
        rows = [row for row in rows if row["lineage_id"] != lineage]
    else:
        for row in rows:
            if target == "sources" or row["lineage_id"] == lineage:
                row[field] = ""
    replace_rows(store, target, rows)
    reasons = {
        "table_name": "lineage_table_missing",
        "transform": "lineage_transform_missing",
        "missing_lineage": "lineage_missing",
        "sha256": "source_hash_missing",
        "retrieved_on": "source_retrieval_missing",
    }
    assert validate_chain(
        lineage,
        records(store, "lineage"),
        records(store, "sources"),
        required_sources=context.chains[lineage],
        numerator_table=table,
    ) == reasons.get(field, "source_" + field + "_missing")
    facts = _Facts(store, context)
    slot = facts.add(
        Decimal("0.8"),
        "metres" if table == "road_link" else "ratio",
        "place_distance_metres" if table == "road_link" else "place_confidence",
        table,
        "SYN-place",
        "2025",
        lineage=lineage,
    )
    assert slot.status == "NO_DATA"
    assert not facts.facts


def test_all_emitted_fact_kinds_have_chains_together():
    from datetime import date

    from product.tests.scan_places_support import fixture, records, replace_rows

    from eii_core.facts import validate_chain
    from eii_product.tools.scan_places import scan_places

    store, context, request, _ = fixture()
    row = records(store, "places")[0]
    replace_rows(store, "places", [dict(row, name="SYN Orchard 7")])
    fsq = {key: row[key] for key in ("lon", "lat", "cell", "licence", "name_ar")}
    fsq.update(
        fsq_place_id="SYN-place",
        name="SYN Orchard 8",
        category_ids="SYN-source-category",
        category_labels="SYN Food",
        source_release="2025-01-10",
    )
    replace_rows(store, "fsq", [fsq])
    replace_rows(
        store,
        "verification",
        [
            dict(
                place_id="SYN-place",
                check_date=date(2025, 1, 1),
                reviewer_role="SYN-reviewer",
                verification_link="https://example.invalid/SYN",
                status="verified_open",
                source_id="roads_osm",
            )
        ],
    )
    replace_rows(
        store,
        "visits",
        [
            dict(
                venue_key="SYN-venue",
                place_id="SYN-place",
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
    assert {fact.unit for fact in result.facts} == {
        "metres",
        "ratio",
        "calendar_date",
        "published_text",
        "count",
    }
    assert (
        result.payload.places[0].distance.fact_id
        != result.payload.places_fsq[0].distance.fact_id
    )
    for fact in result.facts:
        assert (
            validate_chain(
                fact.lineage_ref,
                records(store, "lineage"),
                records(store, "sources"),
                required_sources=context.chains[fact.lineage_ref],
            )
            is None
        )


def test_source_date_cannot_be_a_place_label():
    from product.tests.scan_places_support import fixture

    from eii_product.tools.scan_places import Place, scan_places

    store, context, request, _ = fixture()
    data = scan_places(store, request, context).payload.places[0].model_dump()
    data["name"] = "2025-01-10"
    with pytest.raises(ValueError, match="label_digit"):
        Place.model_validate(data)
