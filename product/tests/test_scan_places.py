"""Public-only envelope behaviour, invented places only."""

import pytest
from product.tests.scan_places_support import fixture

from eii_product.tools import scan_places as boundary
from eii_product.tools.scan_places import scan_places


def test_only_public_places_appear():
    store, context, request, routes = fixture()
    result = scan_places(store, request, context)
    assert result.status == "OK"
    assert result.payload.places[0].place_id == "SYN-place"
    assert result.payload.places[0].distance.fact_id in {
        f.fact_id for f in result.facts
    }
    assert all(f.provenance == "public" for f in result.facts)
    assert routes


@pytest.mark.parametrize(
    "change",
    [
        {"rating": 3},
        {"limit": True},
        {"limit": "1"},
        {"include_neighbours": 1},
        {"categories": "SYN-food"},
    ],
)
def test_request_is_closed(change):
    store, context, request, routes = fixture()
    result = scan_places(store, dict(request, **change), context)
    assert result.status == "INVALID_ARGUMENT"
    assert not store.calls and not routes


@pytest.mark.parametrize(
    "status", ["OK", "NO_DATA", "OUT_OF_SCOPE", "INVALID_ARGUMENT", "INTERNAL"]
)
def test_no_receipt_in_any_status(status):
    from eii_product.tools.scan_places import ScanPlacesResult

    store, context, request, _ = fixture()
    original = scan_places(store, request, context).model_dump()
    original["status"] = status
    assert "privacy_receipt" not in original
    for value in (None, {}, {"invented": "receipt"}):
        with pytest.raises(ValueError):
            ScanPlacesResult.model_validate(dict(original, privacy_receipt=value))


def test_no_synthetic_property_on_a_real_place():
    from eii_product.tools.scan_places import ScanPlacesResult

    store, context, request, _ = fixture()
    original = scan_places(store, request, context).model_dump()
    for provenance in ("synthetic", "simulated"):
        data = scan_places(store, request, context).model_dump()
        data["facts"][0].update(provenance=provenance, input_classes=[provenance])
        with pytest.raises(ValueError):
            ScanPlacesResult.model_validate(data)
    original["payload"]["places"][0]["rating"] = 5
    with pytest.raises(ValueError):
        ScanPlacesResult.model_validate(original)


@pytest.mark.parametrize(
    "status", ["OK", "NO_DATA", "OUT_OF_SCOPE", "INVALID_ARGUMENT", "INTERNAL"]
)
def test_incompleteness_always_present(status):
    from eii_product.tools.scan_places import ScanPlacesResult

    store, context, request, _ = fixture()
    data = scan_places(store, request, context).model_dump()
    data.update(status=status, caveat_keys=[])
    with pytest.raises(ValueError):
        ScanPlacesResult.model_validate(data)


def test_statuses_and_missing_slots():
    store, context, request, routes = fixture()
    result = scan_places(
        store, dict(request, categories=["place_category:SYN-absent"]), context
    )
    assert result.status == "OUT_OF_SCOPE" and not routes
    store.fetch = lambda *args: (_ for _ in ()).throw(RuntimeError("SYN-engine-secret"))
    result = scan_places(store, request, context)
    assert result.status == "INTERNAL"
    assert "SYN-engine-secret" not in result.model_dump_json()


def test_limit_does_not_emit_orphan_distance_facts():
    from product.tests.scan_places_support import records, replace_rows

    store, context, request, _ = fixture()
    row = records(store, "places")[0]
    replace_rows(store, "places", [row, dict(row, place_id="SYN-other")])
    result = scan_places(store, dict(request, limit=1), context)
    assert len([f for f in result.facts if f.unit == "metres"]) == 1


@pytest.mark.parametrize(
    "field,value",
    [
        ("count", 2),
        ("confidence", 0.8),
        ("rank", 1),
        ("date", "2025-01-01"),
        ("licence", "SYN-licence"),
        ("verification_link", "https://example.invalid/SYN"),
    ],
)
def test_payload_rejects_display_values(field, value):
    from eii_product.tools.scan_places import ScanPlacesResult

    store, context, request, _ = fixture()
    data = scan_places(store, request, context).model_dump()
    data["payload"][field] = value
    with pytest.raises(ValueError):
        ScanPlacesResult.model_validate(data)


@pytest.mark.parametrize(
    "plant",
    [
        "suppressed",
        "missing_reference",
        "wrong_distance_unit",
        "orphan_fact",
        "visit_reference",
    ],
)
def test_result_fact_bindings_are_closed(plant):
    from eii_product.tools.scan_places import ScanPlacesResult

    store, context, request, _ = fixture()
    data = scan_places(store, request, context).model_dump()
    if plant == "suppressed":
        data["status"] = "SUPPRESSED"
    elif plant == "missing_reference":
        data["payload"]["places"][0]["distance"]["fact_id"] = "f_" + "b" * 32
    elif plant == "wrong_distance_unit":
        data["facts"][0]["unit"] = "ratio"
    elif plant == "orphan_fact":
        data["facts"].append(dict(data["facts"][0], fact_id="f_" + "b" * 32))
    else:
        data["payload"]["place_visits"] = [
            dict(
                place_id="SYN-place",
                indicator="visitors",
                value=dict(status="OK", fact_id="f_" + "b" * 32),
            )
        ]
    with pytest.raises(ValueError):
        ScanPlacesResult.model_validate(data)


@pytest.mark.parametrize(
    "plant", ["digit_label", "visit_unit", "visit_place", "slot_status"]
)
def test_individual_binding_guards(plant):
    from eii_product.tools.scan_places import ScanPlacesResult

    store, context, request, _ = fixture()
    data = scan_places(store, request, context).model_dump()
    if plant == "digit_label":
        data["payload"]["places"][0]["name"] = "SYN Cafe 7"
    elif plant == "slot_status":
        data["payload"]["places"][0]["distance"]["status"] = "NO_DATA"
    else:
        data["payload"]["place_visits"] = [
            dict(
                place_id="SYN-other" if plant == "visit_place" else "SYN-place",
                indicator="visitors",
                value=dict(status="NO_DATA")
                if plant == "visit_place"
                else data["payload"]["places"][0]["distance"],
            )
        ]
    with pytest.raises(ValueError):
        ScanPlacesResult.model_validate(data)


@pytest.mark.parametrize(
    "field,value",
    [
        ("area_id", 7),
        ("area_id", None),
        ("area_id", True),
        ("categories", ("place_category:SYN-food",)),
        ("categories", [7]),
        ("categories", []),
        ("categories", ["SYN-food"]),
        ("limit", 1.5),
        ("limit", None),
        ("limit", True),
        ("limit", "1"),
        ("include_neighbours", "false"),
        ("include_neighbours", 0),
        ("include_neighbours", None),
    ],
)
def test_each_request_type_guard(field, value):
    from eii_product.tools.scan_places import Request

    _, _, request, _ = fixture()
    with pytest.raises(ValueError):
        Request.model_validate(dict(request, **{field: value}))


@pytest.mark.parametrize("index", [0, 1, 2])
def test_each_fact_requires_own_caveat(index):
    from eii_product.tools.scan_places import ScanPlacesResult

    store, context, request, _ = fixture()
    data = scan_places(store, request, context).model_dump()
    assert len(data["facts"]) == 3
    data["facts"][index]["caveat_keys"] = []
    with pytest.raises(ValueError, match="public_fact_required"):
        ScanPlacesResult.model_validate(data)


def test_public_input_class_operand():
    from eii_product.tools.scan_places import ScanPlacesResult

    store, context, request, _ = fixture()
    data = scan_places(store, request, context).model_dump()
    data["facts"][0].update(
        input_classes=["public", "user_input"], evidence_status="inferred"
    )
    with pytest.raises(ValueError, match="public_fact_required"):
        ScanPlacesResult.model_validate(data)


@pytest.mark.parametrize(
    "query",
    ["categories", "lineage", "sources", "places", "verification", "fsq", "visits"],
)
def test_every_store_failure_is_closed(query):
    store, context, request, _ = fixture()
    fetch = store.fetch

    def fail(token, params):
        if token.name == "scan_places_" + query:
            raise RuntimeError("SYN-private-engine-detail")
        return fetch(token, params)

    store.fetch = fail
    result = scan_places(store, request, context)
    assert result.status == "INTERNAL"
    assert "SYN-private-engine-detail" not in result.model_dump_json()
    assert result.facts == []


# Each member is exercised independently with the rest of its model valid.

BOUNDARY_MODELS = (
    boundary.Request,
    boundary.Slot,
    boundary.Place,
    boundary.Visit,
    boundary.CircleOutline,
    boundary.PolygonOutline,
    boundary.Payload,
    boundary.Blocks,
    boundary.ScanPlacesResult,
)


@pytest.mark.parametrize(
    "model,field",
    [(model, field) for model in BOUNDARY_MODELS for field in model.model_fields],
    ids=[
        model.__name__ + "." + field
        for model in BOUNDARY_MODELS
        for field in model.model_fields
    ],
)
def test_every_closed_property_type(model, field):
    store, context, request, _ = fixture()
    result = scan_places(store, request, context)

    def fields(value):
        return {key: getattr(value, key) for key in type(value).model_fields}

    samples = {
        "Request": request,
        "Slot": dict(status="OK", fact_id="f_" + "a" * 32),
        "Place": fields(result.payload.places[0]),
        "Visit": dict(
            place_id="SYN-place", indicator="visitors", value=dict(status="NO_DATA")
        ),
        "CircleOutline": fields(result.payload.outline),
        "PolygonOutline": dict(type="Polygon", coordinates=[]),
        "Payload": fields(result.payload),
        "Blocks": fields(result.blocks),
        "ScanPlacesResult": fields(result),
    }
    data = dict(samples[model.__name__])
    model.model_validate(data)
    data[field] = object()
    with pytest.raises(ValueError):
        try:
            model.model_validate(data)
        except (TypeError, AttributeError) as error:
            pytest.fail("type guard leaked " + type(error).__name__)
