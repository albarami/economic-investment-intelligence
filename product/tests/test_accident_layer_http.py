"""S3-T12 / decision 0047: the accident read's absence matrix and refusals.

Invented rows only (the cards fixture); no cache and no network.
"""

import json

import pytest
from hypothesis import given
from hypothesis import strategies as st
from product.tests.test_tools_http import CardStore
from product.tests.test_tools_http import service as service

from eii_core.facts import Fact

NO_DATA_KEYS = {"status", "reason", "facts", "coverage_report", "payload"}


def body(client):
    response = client.get("/api/layers/accidents")
    assert response.status_code == 200
    return response.json()


def test_counted_rows_are_outlines_on_their_own_zone_and_latest_year(service):
    client, ledger, _store, _calls = service
    got = body(client)
    assert got["status"] == "ok" and "reason" not in got
    layer = got["payload"]["layers"][0]
    assert [
        (f["source_zone"], f["year"], f["geography_code"]) for f in layer["features"]
    ] == [
        ("51", "2024", "zone:INVENTED-zone-a"),
        ("52", "2024", "zone:INVENTED-zone-b"),
    ]
    assert {f["geometry_kind"] for f in layer["features"]} == {"outline"}
    facts = {
        f["fact_id"]: Fact.model_validate_json(json.dumps(f)) for f in got["facts"]
    }
    assert [facts[f["fact_id"]].value for f in layer["features"]] == [5, 0]
    for feature in layer["features"]:
        fact = facts[feature["fact_id"]]
        assert (fact.unit, fact.evidence_status, fact.provenance) == (
            "count",
            "inferred",
            "public",
        )
        assert fact.caveat_keys == ["accidents_recorded_not_risk"]
        # RV1 finding 2: the zone reference is a fact of the count's own row.
        zone = facts[feature["source_zone_fact_id"]]
        assert (zone.value, zone.unit, zone.evidence_status) == (
            feature["source_zone"],
            "published_text",
            "observed",
        )
        assert (zone.period, zone.geography, zone.lineage_ref) == (
            fact.period,
            fact.geography,
            fact.lineage_ref,
        )
    assert len(facts) == 2 * len(layer["features"])
    # The unmatched source zone is counted as missing, never as zero.
    assert got["coverage_report"] == {"counts": {"counted": 2, "geography_missing": 1}}
    assert ledger.rows() == []


def without_manifest_table(store):
    store.tables["release_manifest"] = [
        r
        for r in store.tables["release_manifest"]
        if r["table_name"] != "pub_accident_zone"
    ]


def no_data(got, reason, counts):
    assert set(got) == NO_DATA_KEYS
    assert (got["status"], got["reason"], got["facts"]) == ("NO_DATA", reason, [])
    assert got["payload"]["layers"][0]["key"] == "accidents"
    assert got["payload"]["layers"][0]["features"] == []
    assert got["coverage_report"] == {"counts": counts}


def test_pending_source_is_no_data_before_any_table_query(service):
    client, _ledger, store, _calls = service
    without_manifest_table(store)
    del store.tables["pub_accident_zone"]  # a query would raise KeyError
    no_data(body(client), "accident_source_missing", {})


def test_unconfirmed_measure_is_no_data(service):
    client, _ledger, store, _calls = service
    unconfirmed(store)
    no_data(body(client), "accident_measure_unconfirmed", {"measure_unconfirmed": 3})


def test_confirmed_measure_without_geometry_is_no_data_and_web_fixture(service):
    client, _ledger, store, _calls = service
    without_geometry(store)
    got = body(client)
    no_data(got, "accident_geography_missing", {"counted": 0, "geography_missing": 3})


def test_removing_the_matched_zone_polygon_withholds_only_that_feature(service):
    client, _ledger, store, _calls = service
    store.tables["zone"] = [
        z for z in store.tables["zone"] if z["zone_code"] != "INVENTED-zone-b"
    ]
    got = body(client)
    assert [f["source_zone"] for f in got["payload"]["layers"][0]["features"]] == ["51"]
    assert got["coverage_report"] == {"counts": {"counted": 1, "geography_missing": 2}}
    assert len(got["facts"]) == 2  # the one count and its zone reference


def refused(client, store, reason):
    """A hard failure: the route answers a closed 500 and the reader names it."""
    from eii_product.api.public_layers import read_layer

    response = client.get("/api/layers/accidents")
    assert response.status_code == 500
    assert reason not in json.dumps(response.json())
    with pytest.raises(ValueError, match="^" + reason + "$"):
        read_layer(store, "accidents")


def test_broken_lineage_is_a_hard_failure(service):
    client, _ledger, store, _calls = service
    without_lineage(store)
    refused(client, store, "accident_lineage_broken")


def unconfirmed(store):
    store.tables["pub_accident_zone"] = [
        {**r, "coverage_key": "measure_unconfirmed", "accident_count": None}
        for r in store.tables["pub_accident_zone"]
    ]


def without_geometry(store):
    store.tables["zone"] = [
        z
        for z in store.tables["zone"]
        if z["zone_code"] not in {"INVENTED-zone-a", "INVENTED-zone-b"}
    ]


def without_lineage(store):
    store.tables["fact_lineage"] = [
        r
        for r in store.tables["fact_lineage"]
        if r["table_name"] != "pub_accident_zone"
    ]


def foreign_source(store):
    rows = store.tables["pub_accident_zone"] = list(store.tables["pub_accident_zone"])
    rows[0] = {**rows[0], "source_id": "src-invented-elsewhere"}


# RV1 finding 3: a present table's lineage and every row's source membership
# are checked before either absence outcome; each case changes one input of
# an otherwise valid absence case.
@pytest.mark.parametrize("absence", [unconfirmed, without_geometry])
@pytest.mark.parametrize("break_chain", [without_lineage, foreign_source])
def test_broken_lineage_is_never_ordinary_absence(service, absence, break_chain):
    client, _ledger, store, _calls = service
    absence(store)
    break_chain(store)
    refused(client, store, "accident_lineage_broken")


OUTCOME = {
    None: ("ok", None),
    unconfirmed: ("NO_DATA", "accident_measure_unconfirmed"),
    without_geometry: ("NO_DATA", "accident_geography_missing"),
}


# Edge classes (L-1389): every outcome of a present table against every set of
# rows moved to a source outside the chain, with or without the lineage row.
@given(
    absence=st.sampled_from(list(OUTCOME)),
    moved=st.sets(st.integers(0, 3)),
    source=st.text(min_size=1).filter(lambda s: s != "src-invented"),
    lineage=st.booleans(),
)
def test_lineage_is_checked_before_every_outcome(absence, moved, source, lineage):
    from eii_product.api.public_layers import read_layer

    store = CardStore()
    if absence is not None:
        absence(store)
    rows = store.tables["pub_accident_zone"] = list(store.tables["pub_accident_zone"])
    assert len(rows) == 4  # every row of the invented table can move
    for index in moved:
        rows[index] = {**rows[index], "source_id": source}
    if not lineage:
        without_lineage(store)
    if moved or not lineage:
        with pytest.raises(ValueError, match=r"^accident_lineage_broken$"):
            read_layer(store, "accidents")
        return
    got = read_layer(store, "accidents")
    assert (got["status"], got.get("reason")) == OUTCOME[absence]


ROW = {
    "source_zone": "51",
    "period": "2024",
    "zone_code": "INVENTED-zone-a",
    "accident_count": 5,
    "coverage_key": "counted",
}


# One input changed per case; every other row and field stays valid (L-1409).
@pytest.mark.parametrize(
    ("change", "reason"),
    [
        ({"coverage_key": "risk_high"}, "accident_coverage_invalid"),
        ({"accident_count": None}, "accident_coverage_invalid"),
        ({"zone_code": None}, "accident_coverage_invalid"),
        ({"accident_count": -1}, "accident_count_invalid"),
        ({"accident_count": True}, "accident_count_invalid"),
        ({"period": "2024-03"}, "accident_period_invalid"),
        ({"source_zone": "51a"}, "accident_zone_invalid"),
        ({"source_zone": "52"}, "accident_row_duplicate"),
        ({"zone_code": "INVENTED-zone-b"}, "accident_geography_allocation"),
        (
            {"coverage_key": "measure_unconfirmed", "accident_count": None},
            "accident_coverage_invalid",
        ),
    ],
)
def test_each_corrupt_row_has_its_own_closed_reason(service, change, reason):
    client, _ledger, store, _calls = service
    rows = store.tables["pub_accident_zone"] = list(store.tables["pub_accident_zone"])
    index = next(
        i
        for i, r in enumerate(rows)
        if (r["source_zone"], r["period"]) == ("51", "2024")
    )
    rows[index] = {**rows[index], **change}
    refused(client, store, reason)


# Edge classes (L-1389): the text-shape count check against the integer oracle,
# over every integer (zero, one, negatives, huge) and the two booleans.
@given(count=st.one_of(st.integers(), st.booleans()))
def test_count_shape_check_matches_the_integer_oracle(count):
    from eii_product.api.public_layers import accident_rows

    row = {**ROW, "accident_count": count}
    if type(count) is int and count >= 0:
        assert accident_rows([row]) == [row]
    else:
        with pytest.raises(ValueError, match=r"^accident_count_invalid$"):
            accident_rows([row])


def test_geography_missing_row_with_a_zone_is_corrupt(service):
    client, _ledger, store, _calls = service
    rows = store.tables["pub_accident_zone"] = list(store.tables["pub_accident_zone"])
    index = next(i for i, r in enumerate(rows) if r["source_zone"] == "53")
    rows[index] = {**rows[index], "zone_code": "INVENTED-zone-c"}
    refused(client, store, "accident_coverage_invalid")


def test_unknown_coverage_on_a_null_row_is_corrupt(service):
    # Null count and zone pass the consistency check; only the closed list refuses.
    client, _ledger, store, _calls = service
    rows = store.tables["pub_accident_zone"] = list(store.tables["pub_accident_zone"])
    index = next(i for i, r in enumerate(rows) if r["source_zone"] == "53")
    rows[index] = {**rows[index], "coverage_key": "risk_high"}
    refused(client, store, "accident_coverage_invalid")


def test_present_empty_table_is_a_hard_failure(service):
    client, _ledger, store, _calls = service
    store.tables["pub_accident_zone"] = []
    refused(client, store, "accident_table_empty")


def test_envelope_refuses_an_unknown_reason(service):
    from eii_product.api.public_layers import LayerRead, accident_no_data

    _client, _ledger, store, _calls = service
    with pytest.raises(ValueError, match=r"^accident_reason_unknown$"):
        accident_no_data(LayerRead(store, "accidents"), "risk_low", {})
