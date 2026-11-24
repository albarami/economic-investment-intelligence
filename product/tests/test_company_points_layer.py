"""S3-T12 box 12: the commerce register's establishment points (`company_points`).

Invented register rows only (the cards fixture); no register file is read.
The plants put a wage, a labour or residence detail, a Simulated figure and a
Synthetic figure other than `employee_count` on a point, a label or a card;
each is refused before emission.
"""

import json
from copy import deepcopy

import pytest
from hypothesis import example, given
from hypothesis import strategies as st
from product.tests.test_mounted_release_http import loaded as loaded
from product.tests.test_mounted_release_http import mounted as mounted
from product.tests.test_tools_http import CardStore
from product.tests.test_tools_http import service as service

from eii_core.facts import Fact, validate_chain
from eii_product.api.public_layers import (
    COMPANY_ABSENT_REASON,
    METRICS,
    TABLES,
    CompanyPointRefusal,
    LayerRead,
    read_layer,
    seal_company_points,
)
from eii_product.api.results import wire_fact
from eii_product.tools.registry import public_layer_descriptors


def _body(store=None):
    return read_layer(store or CardStore(), "company_points")


def _seal(body, store=None):
    return seal_company_points(body, store or CardStore())


def test_company_points_served_from_registered_cell(service):
    import h3

    client, ledger, store, _calls = service
    response = client.get("/api/layers/company_points")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    layer = body["payload"]["layers"][0]
    assert layer["key"] == "company_points"
    held = [
        r
        for r in store.tables["pub_register_company"]
        if r["registered_cell"] is not None
    ]
    assert len(layer["features"]) == len(held) == 1
    feature = layer["features"][0]
    lat, lon = h3.cell_to_latlng(h3.int_to_str(held[0]["registered_cell"]))
    assert feature["position"] == [lon, lat]
    assert feature["geometry_kind"] == "point"
    assert feature["subject"] == "business"
    assert feature["provenance"] == "public"
    assert feature["metric_key"] == "register_company_point"
    assert "words" not in feature and "label_key" not in feature
    # The register's own key never reaches the wire of the points layer.
    text = json.dumps(body)
    for row in store.tables["pub_register_company"]:
        assert row["registration_number"] not in text
    for item in body["facts"]:
        fact = Fact.model_validate_json(json.dumps(item))
        assert fact.provenance == "public" and fact.input_classes == ["public"]
        assert (
            validate_chain(
                fact.lineage_ref,
                store.tables["fact_lineage"],
                store.tables["source_registry"],
                numerator_table="pub_register_company",
            )
            is None
        )
    assert ledger.rows() == []


def test_card_shows_published_fields_and_absent_employee_count(service):
    client, *_ = service
    body = client.get("/api/layers/company_points").json()
    feature = body["payload"]["layers"][0]["features"][0]
    cards = body["payload"]["company_cards"]
    assert [card["feature_id"] for card in cards] == [feature["feature_id"]]
    card = cards[0]
    assert set(card) == {"feature_id", "row_id", "fields", "employee_count"}
    assert [field["key"] for field in card["fields"]] == ["establishment_nationality"]
    # public_only holds no register_company_list: the count is absent, with its
    # reason, never a zero and never a figure.
    assert card["employee_count"] == {
        "state": "absent",
        "reason_key": COMPANY_ABSENT_REASON,
    }


def test_unresolved_cell_is_not_drawn(service):
    client, _ledger, store, _calls = service
    for row in store.tables["pub_register_company"]:
        row["registered_cell"] = None
    body = client.get("/api/layers/company_points").json()
    assert body["status"] == "NO_DATA"
    assert body["payload"]["layers"][0]["features"] == []
    assert body["payload"]["company_cards"] == []


def test_broken_chain_draws_no_point(service):
    client, _ledger, store, _calls = service
    store.tables["fact_lineage"] = [
        r
        for r in store.tables["fact_lineage"]
        if r["table_name"] != "pub_register_company"
    ]
    body = client.get("/api/layers/company_points").json()
    assert body["facts"] == [] and body["payload"]["layers"][0]["features"] == []


def test_success_chain_through_production_fact_chain_route(mounted):
    """Builder-audit item: an invented loaded register, a successful chain read."""
    client, store, rows = mounted
    assert any(r["registered_cell"] is not None for r in rows["pub_register_company"])
    body = client.get("/api/layers/company_points").json()
    assert body["status"] == "ok" and body["facts"]
    fact = body["facts"][0]
    response = client.get("/api/facts/" + fact["fact_id"] + "/lineage")
    assert response.status_code == 200
    chain = response.json()
    assert chain["lineage"]["tableName"] == "pub_register_company"
    assert chain["binding"]["metricKey"] == "register_company_point"
    assert chain["release_id"] == store.release_id
    assert chain["sources"] and all(
        source["inputClass"] == "public" for source in chain["sources"]
    )


# Plants. Each one is refused by the seal that every response passes through.
def _plant_card_field(body, key):
    body["payload"]["company_cards"][0]["fields"].append(
        {"key": key, "segments": [{"kind": "plain", "text": "INVENTED"}]}
    )


def _plant_feature_words(body, key):
    body["payload"]["layers"][0]["features"][0]["words"] = {key: "INVENTED"}


def _plant_fact_provenance(body, provenance, metric):
    fact = deepcopy(body["facts"][0])
    fact["provenance"] = provenance
    fact["input_classes"] = [provenance]
    fact["fact_id"] = "f_" + "c" * 32
    body["facts"].append(fact)
    body["payload"]["layers"][0]["features"][0]["metric_key"] = metric
    body["payload"]["layers"][0]["features"][0]["fact_id"] = fact["fact_id"]


PLANTS = {
    "wage_on_card": lambda b: _plant_card_field(b, "wage"),
    "wage_bill_on_point": lambda b: _plant_feature_words(b, "wage_bill"),
    "occupation_on_card": lambda b: _plant_card_field(b, "occupation"),
    "residence_on_label": lambda b: b["payload"]["layers"][0]["features"][0].update(
        label_key="residence"
    ),
    "home_municipality_on_point": lambda b: _plant_feature_words(
        b, "home_municipality"
    ),
    "simulated_figure": lambda b: _plant_fact_provenance(
        b, "simulated", "register_company_point"
    ),
    "synthetic_other_than_employee_count": lambda b: _plant_fact_provenance(
        b, "synthetic", "employees"
    ),
    "synthetic_feature_provenance": lambda b: b["payload"]["layers"][0]["features"][
        0
    ].update(provenance="synthetic"),
    "released_count_in_public_only": lambda b: b["payload"]["company_cards"][0].update(
        employee_count={"state": "released", "value": 7}
    ),
    "zero_for_absent_count": lambda b: b["payload"]["company_cards"][0].update(
        employee_count={
            "state": "absent",
            "reason_key": COMPANY_ABSENT_REASON,
            "value": 0,
        }
    ),
}


def test_seal_passes_the_clean_body():
    body = _body()
    assert _seal(deepcopy(body)) == body


@pytest.mark.parametrize("plant", sorted(PLANTS))
def test_planted_violation_is_refused(plant):
    body = _body()
    PLANTS[plant](body)
    with pytest.raises(CompanyPointRefusal):
        _seal(body)


def test_descriptor_declares_every_query_the_reader_runs():
    descriptor = next(
        d for d in public_layer_descriptors() if d.key == "layer:company_points"
    )
    assert descriptor.queries == (
        "layer_company_points",
        "public_lineage_for_table",
        "sector_facts_sources",
    )


def test_parity_inventory_holds_exactly_the_traced_reads():
    """An omitted query in the parity inventory is refused (traced, not declared)."""
    from live_public_playbook import public_query_names

    from eii_product.store.parity import TracingStore

    found: list[str] = []
    read_layer(TracingStore(CardStore(), found), "company_points")
    descriptor = next(
        d for d in public_layer_descriptors() if d.key == "layer:company_points"
    )
    assert set(found) == set(descriptor.queries)
    assert set(found) <= set(public_query_names())


# Review round 2. F1: the card is closed at every nesting level. F2: a card
# reference binds a fact the response carries. F3: the production read seals.
def _card(body):
    return body["payload"]["company_cards"][0]


def _field(body):
    return _card(body)["fields"][0]


def _segment(body):
    return _field(body)["segments"][0]


def _reference(record, value="INVENTED 7", kind="published_text"):
    return {
        "kind": "reference",
        "referenceKind": kind,
        "value": value,
        "recordId": record,
    }


NESTED_PLANTS = {
    "nested_wage_key_in_field": lambda b: _field(b).update(wage="INVENTED"),
    "nested_unknown_key_in_field": lambda b: _field(b).update(note="INVENTED"),
    "nested_wage_key_in_segment": lambda b: _segment(b).update(wage="INVENTED"),
    "nested_unknown_key_in_segment": lambda b: _segment(b).update(note="INVENTED"),
    "nested_object_as_segment_text": lambda b: _segment(b).update(
        text={"wage": "INVENTED"}
    ),
    "nested_object_as_row_id": lambda b: _card(b).update(row_id={"wage": "INVENTED"}),
    "nested_object_as_feature_id": lambda b: _card(b).update(
        feature_id={"wage": "INVENTED"}
    ),
    "text_beside_segments": lambda b: _field(b).update(text="INVENTED"),
    "segments_not_a_list": lambda b: _field(b).update(segments={"wage": "INVENTED"}),
    "field_without_segments": lambda b: _field(b).update(segments=[]),
    "fields_not_a_list": lambda b: _card(b).update(
        fields={"key": "establishment_nationality", "wage": "INVENTED"}
    ),
    "unknown_segment_kind": lambda b: _segment(b).update(kind="wage"),
    "nested_object_as_segment_kind": lambda b: _segment(b).update(
        kind={"wage": "INVENTED"}
    ),
    "numeral_in_plain_segment": lambda b: _segment(b).update(text="INVENTED 7"),
    "reference_with_absent_fact": lambda b: _field(b).update(
        segments=[_reference("f_" + "d" * 32)]
    ),
    "reference_to_the_feature_not_a_fact": lambda b: _field(b).update(
        segments=[_reference(_card(b)["feature_id"])]
    ),
    "reference_value_differs_from_its_fact": lambda b: _field(b).update(
        segments=[
            _reference(b["facts"][0]["fact_id"], "1999-01-01", b["facts"][0]["unit"])
        ]
    ),
    "reference_kind_differs_from_its_fact": lambda b: _field(b).update(
        segments=[_reference(b["facts"][0]["fact_id"], str(b["facts"][0]["value"]))]
    ),
    "reference_with_nested_wage_key": lambda b: _field(b).update(
        segments=[
            dict(
                _reference(
                    b["facts"][0]["fact_id"],
                    str(b["facts"][0]["value"]),
                    b["facts"][0]["unit"],
                ),
                wage="INVENTED",
            )
        ]
    ),
}


def _point(body):
    return body["payload"]["layers"][0]["features"][0]


@pytest.mark.parametrize(
    "position",
    [
        [],
        [1.0],
        [1.0, 2.0, 3.0],
        None,
        (1.0, 2.0),
        "ab",
        {"a": 1.0, "b": 2.0},
        [True, 2.0],
        [1, 2.0],
        [1.0, {"wage": "INVENTED"}],
    ],
)
def test_malformed_point_position_has_specific_refusal(position):
    body = _body()
    _point(body)["position"] = position
    with pytest.raises(CompanyPointRefusal, match=r"^detail_on_point$"):
        _seal(body)


@given(
    st.one_of(
        st.recursive(
            st.none() | st.booleans() | st.integers() | st.floats() | st.text(),
            lambda child: st.lists(child) | st.dictionaries(st.text(), child),
        ),
        st.tuples(st.floats(), st.floats()),
        st.lists(st.floats()),
    )
)
@example([0.0, 0.0])
@example([float("inf"), float("nan")])
@example([-0.0, 1.0])
def test_position_contract_over_json_values(position):
    body = _body()
    _point(body)["position"] = position
    valid = (
        isinstance(position, list)
        and len(position) == 2
        and all(type(value) is float for value in position)
    )
    if valid:
        assert _seal(body) is body
    else:
        with pytest.raises(CompanyPointRefusal, match=r"^detail_on_point$"):
            _seal(body)


# The same closure on the point: every value is a string, the position a pair.
NESTED_PLANTS.update(
    {
        "nested_object_as_point_source": lambda b: _point(b).update(
            source_id={"wage": "INVENTED"}
        ),
        "nested_object_as_point_fact": lambda b: _point(b).update(
            fact_id={"wage": "INVENTED"}
        ),
        "nested_object_in_point_position": lambda b: _point(b).update(
            position=[*_point(b)["position"], {"wage": "INVENTED"}]
        ),
        "nested_object_as_point_position": lambda b: _point(b).update(
            position={"wage": "INVENTED"}
        ),
    }
)


@pytest.mark.parametrize("plant", sorted(NESTED_PLANTS))
def test_nested_plant_is_refused(plant):
    body = _body()
    NESTED_PLANTS[plant](body)
    with pytest.raises(CompanyPointRefusal):
        _seal(body)


def test_seal_passes_a_reference_bound_to_a_carried_fact():
    """The refusals above are of the unbound reference, not of every reference."""
    body = _body()
    fact = body["facts"][0]
    _field(body).update(
        segments=[_reference(fact["fact_id"], str(fact["value"]), fact["unit"])]
    )
    assert _seal(deepcopy(body)) == body


# Review round 3 (F2, server tier). A wire fact names no table and no metric:
# its table is its lineage and its metric key is held by its identifier. A
# reference binds only a fact of the `company_points` entry's table and metric.
def _carried(body, table, metric, code):
    """Another Public fact in the response, of the first fact's unit and value."""
    first = body["facts"][0]
    fact = LayerRead(CardStore(), "company_points").fact(
        table, metric, first["value"], first["unit"], first["period"], code
    )
    assert fact is not None and fact.fact_id != first["fact_id"]
    carried = wire_fact(fact)
    assert (carried["unit"], carried["value"]) == (first["unit"], first["value"])
    assert carried["provenance"] == "public" and carried["input_classes"] == ["public"]
    body["facts"].append(carried)
    return carried, first


def _carry(body, table, metric, code):
    """The same further fact, named by a card reference."""
    carried, first = _carried(body, table, metric, code)
    _field(body).update(
        segments=[
            _reference(carried["fact_id"], str(carried["value"]), carried["unit"])
        ]
    )
    return carried, first


def test_reference_to_a_public_fact_of_another_table_is_refused():
    body = _body()
    # The entry's own metric on an invented further point: only the table differs.
    carried, first = _carry(
        body, "pub_place", METRICS["company_points"], "feature:company-invented"
    )
    assert TABLES["company_points"] != "pub_place"
    assert carried["lineage_ref"] != first["lineage_ref"]
    with pytest.raises(CompanyPointRefusal) as refusal:
        _seal(body)
    assert refusal.value.reason == "card_reference_unbound"


def test_reference_to_a_public_fact_of_another_metric_is_refused():
    body = _body()
    # The entry's own table, period and point: only the metric differs.
    carried, first = _carry(
        body,
        TABLES["company_points"],
        "landmark_name",
        body["facts"][0]["geography"]["public_code"],
    )
    assert METRICS["company_points"] != "landmark_name"
    assert carried["lineage_ref"] == first["lineage_ref"]
    assert carried["geography"] == first["geography"]
    with pytest.raises(CompanyPointRefusal) as refusal:
        _seal(body)
    assert refusal.value.reason == "card_reference_unbound"


def test_reference_is_refused_when_the_register_chain_is_broken():
    """Without the register's lineage no fact is of the entry's table."""
    body = _body()
    fact = body["facts"][0]
    _field(body).update(
        segments=[_reference(fact["fact_id"], str(fact["value"]), fact["unit"])]
    )
    store = CardStore()
    store.tables["fact_lineage"] = [
        r
        for r in store.tables["fact_lineage"]
        if r["table_name"] != TABLES["company_points"]
    ]
    with pytest.raises(CompanyPointRefusal) as refusal:
        _seal(body, store)
    assert refusal.value.reason == "card_reference_unbound"


def _planted_builder(monkeypatch):
    import eii_product.api.public_layers as module

    clean = module.company_points

    def planted(ctx):
        body = clean(ctx)
        _plant_card_field(body, "wage")
        return body

    monkeypatch.setattr(module, "company_points", planted)


def test_production_read_seals_the_builders_body(monkeypatch):
    """F3: the read every production caller uses refuses what the seal refuses."""
    _planted_builder(monkeypatch)
    with pytest.raises(CompanyPointRefusal):
        read_layer(CardStore(), "company_points")


def test_route_refuses_an_unsealed_body(service, monkeypatch):
    client, *_ = service
    assert client.get("/api/layers/company_points").status_code == 200
    _planted_builder(monkeypatch)
    response = client.get("/api/layers/company_points")
    assert response.status_code == 500
    assert "wage" not in response.text and "INVENTED" not in response.text


def test_layer_descriptor_refuses_an_unsealed_body(monkeypatch):
    _planted_builder(monkeypatch)
    descriptor = next(
        d for d in public_layer_descriptors() if d.key == "layer:company_points"
    )
    with pytest.raises(CompanyPointRefusal):
        descriptor.run(CardStore(), {})


def test_digit_bearing_card_field_is_refused_by_the_production_read(service):
    """No field fact exists for a card field: a numeral has no fact to bind."""
    client, _ledger, store, _calls = service
    for row in store.tables["pub_register_company"]:
        row["establishment_nationality"] = "INVENTED 7 nationality"
    with pytest.raises(CompanyPointRefusal) as refusal:
        read_layer(store, "company_points")
    assert refusal.value.reason == "card_reference_unbound"
    response = client.get("/api/layers/company_points")
    assert response.status_code == 500
    assert "INVENTED 7" not in response.text


# Review round 4 (server tier, rules 7 and 19). A point's `fact_id` is held to
# the same binding as a card reference: a carried fact of the entry's own table
# and metric. Each case leaves the point's own metric key and provenance clean.
def test_point_whose_fact_is_not_carried_is_refused():
    body = _body()
    carried = {fact["fact_id"] for fact in body["facts"]}
    _point(body).update(fact_id="fact:invented-not-carried")
    assert _point(body)["fact_id"] not in carried
    with pytest.raises(CompanyPointRefusal) as refusal:
        _seal(body)
    assert refusal.value.reason == "point_fact_unbound"


def test_point_that_names_no_fact_is_refused():
    body = _body()
    del _point(body)["fact_id"]
    with pytest.raises(CompanyPointRefusal) as refusal:
        _seal(body)
    assert refusal.value.reason == "point_fact_unbound"


def test_point_naming_a_public_fact_of_another_table_is_refused():
    body = _body()
    carried, first = _carried(
        body, "pub_place", METRICS["company_points"], "feature:company-invented"
    )
    assert TABLES["company_points"] != "pub_place"
    assert carried["lineage_ref"] != first["lineage_ref"]
    _point(body).update(fact_id=carried["fact_id"])
    with pytest.raises(CompanyPointRefusal) as refusal:
        _seal(body)
    assert refusal.value.reason == "point_fact_unbound"


def test_point_naming_a_public_fact_of_another_metric_is_refused():
    body = _body()
    carried, first = _carried(
        body,
        TABLES["company_points"],
        "landmark_name",
        body["facts"][0]["geography"]["public_code"],
    )
    assert METRICS["company_points"] != "landmark_name"
    assert carried["lineage_ref"] == first["lineage_ref"]
    _point(body).update(fact_id=carried["fact_id"])
    with pytest.raises(CompanyPointRefusal) as refusal:
        _seal(body)
    assert refusal.value.reason == "point_fact_unbound"


def test_point_is_refused_when_the_register_chain_is_broken():
    """Without the register's lineage no point's fact is of the entry's table."""
    store = CardStore()
    store.tables["fact_lineage"] = [
        r
        for r in store.tables["fact_lineage"]
        if r["table_name"] != TABLES["company_points"]
    ]
    with pytest.raises(CompanyPointRefusal) as refusal:
        _seal(_body(), store)
    assert refusal.value.reason == "point_fact_unbound"


def test_seal_passes_a_further_carried_fact_no_point_names():
    """The refusals above are of the point's binding, not of the carried fact."""
    body = _body()
    _carried(body, "pub_place", METRICS["company_points"], "feature:company-invented")
    assert _seal(deepcopy(body)) == body
