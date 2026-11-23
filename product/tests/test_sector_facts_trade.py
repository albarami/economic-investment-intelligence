"""S3-T06 part A: the Comtrade reporter-row binding on a fixture-only inventory.

Every row is invented. The inventory under ``fixtures/comtrade_inventory`` is a
fixture, not the production contract: its decimal(20,4) bound and the unit map
below are invented, and the production read stays gated on S2-T23 box 1.
"""

import re
from datetime import date
from decimal import Decimal
from hashlib import sha256
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from product.tests.sector_fixture import IDENTITY

from eii_core.facts import QUALIFIER_KEYS, fact_id, validate_chain
from eii_product.store.normalise import normalise
from eii_product.store.protocol import StoreRefusal
from eii_product.store.registry import PACKAGED, checked_result, load_inventory
from eii_product.tools import sector_facts as sf

FIXTURE = load_inventory(Path(__file__).parent / "fixtures" / "comtrade_inventory")
# Fixture only: an invented measure in an invented QAR unit, mapped to qar.
FIXTURE_UNITS = {("SYN-value", "SYN-qar"): "qar"}
TABLE = "pub_comtrade_trade"
REQUEST = dict(flow="SYN-M", product_scope="TOTAL")


def row(**change):
    base = dict(
        source_id="SYN-comtrade",
        series_role="reporter",
        reporter_code="QAT",
        partner_code="SYN-world",
        partner2_code="",
        frequency="annual",
        period="2024",
        flow_code="SYN-M",
        classification="SYN-HS",
        classification_revision="SYN-rev",
        product_code="TOTAL",
        aggregation_level=0,
        customs_code="SYN-customs",
        transport_mode_code="SYN-mode",
        valuation_basis="SYN-basis",
        measure="SYN-value",
        unit="SYN-qar",
        value=Decimal("1000.5000"),
    )
    base.update(change)
    return base


def lineage(**change):
    line = dict(
        lineage_id="lin_" + TABLE,
        table_name=TABLE,
        source_id="SYN-comtrade",
        input_class="public",
        transform="eii_product.tools.sector_facts.comtrade_reporter@v1",
    )
    line.update(change)
    return line


def source(**change):
    item = dict(
        source_id="SYN-comtrade",
        kind="public",
        publisher="SYN-publisher",
        title="SYN-comtrade",
        url="https://example.invalid/SYN-comtrade",
        licence="SYN-provider-terms",
        retrieved_on=date(2025, 1, 1),
        sha256=sha256(b"SYN-comtrade").hexdigest(),
    )
    item.update(change)
    return item


class SpyStore:
    """Serves invented rows by query name; checks them against the header."""

    engine = "embedded"
    release_id = IDENTITY

    def __init__(self, rows=(), lines=None, sources=None):
        self.data = {
            "sector_facts_comtrade": list(rows),
            "sector_facts_lineage": [lineage()] if lines is None else lines,
            "sector_facts_sources": [source()] if sources is None else sources,
        }
        self.reads = []

    def fetch(self, query, params):
        self.reads.append((query.name, dict(params)))
        spec = FIXTURE.get(query.name) or PACKAGED.get(query.name)
        names = tuple(r.name for r in spec.returns)
        rows = [tuple(r.get(n) for n in names) for r in self.data[query.name]]
        return checked_result(spec, names, rows)


def run(store, request=REQUEST, units=FIXTURE_UNITS, inventory=FIXTURE):
    inputs = sf.Inputs(
        activity="SYN-a", topic="trade", geography="national", trade=request
    )
    ctx = sf.Context(store, inputs)
    sf.trade_reporter(ctx, inventory, units)
    return ctx


def facts_of(ctx):
    return list(ctx.facts.values())


def test_reporter_cell_returns_its_stored_decimal_exactly():
    ctx = run(SpyStore([row()]))
    (fact,) = facts_of(ctx)
    # The value is the store's normalised Decimal, passed through unchanged.
    assert type(fact.value) is Decimal and str(fact.value) == "1000.500000"
    assert fact.value == normalise(row()["value"])
    assert fact.unit == "qar" and fact.period == "2024"
    assert fact.geography == {"kind": "national"}
    assert fact.label_en and fact.lineage_ref == "lin_" + TABLE
    assert ctx.blocks == [
        dict(block="trade_reporter", status="OK", fact_ids=[fact.fact_id])
    ]


def test_request_parameters_are_bound_verbatim():
    store = SpyStore([row(partner_code="SYN-p")])
    run(store, dict(flow="SYN-M", product_scope="TOTAL", partner="SYN-p"))
    assert store.reads[0] == (
        "sector_facts_comtrade",
        dict(flow="SYN-M", product_code="TOTAL", partner="SYN-p"),
    )
    store = SpyStore([row()])
    run(store)
    assert store.reads[0][1] == dict(flow="SYN-M", product_code="TOTAL", partner="")


def test_gated_production_read_returns_no_data_and_reads_nothing():
    store = SpyStore([row()])
    ctx = run(store, inventory=PACKAGED, units=sf.TRADE_UNITS)
    assert store.reads == [] and ctx.facts == {}
    assert ctx.blocks == [dict(block="trade_reporter", status="NO_DATA", fact_ids=[])]
    assert sf.TRADE_UNITS == {}
    assert PACKAGED.get(sf.COMTRADE_QUERY) is None


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        (dict(series_role="mirror"), "trade_series_role"),
        (dict(reporter_code="SYN-other"), "trade_reporter_invalid"),
        (dict(source_id="SYN-elsewhere"), "source_missing"),
        (dict(value=None), "trade_coverage_gap"),
        (dict(unit="SYN-usd"), "trade_unit_unmapped"),
        (dict(measure="SYN-quantity"), "trade_unit_unmapped"),
        (dict(aggregation_level="0"), "trade_qualifier_invalid"),
        (dict(customs_code=7), "trade_qualifier_invalid"),
    ],
)
def test_row_refusals_name_their_reason_and_emit_no_fact(change, reason):
    planted = row(**change)
    assert sf.comtrade_refusal(planted, {"SYN-comtrade"}, FIXTURE_UNITS) == reason
    assert sf.comtrade_refusal(row(), {"SYN-comtrade"}, FIXTURE_UNITS) is None
    ctx = run(SpyStore([]))
    assert sf.comtrade_fact(ctx, planted, FIXTURE_UNITS) is None
    assert sf.comtrade_fact(ctx, row(), FIXTURE_UNITS) is not None


@pytest.mark.parametrize(
    "value", [1000.5, True, "1000.5"], ids=["float", "bool", "text"]
)
def test_non_decimal_value_is_refused(value):
    planted = dict(row(), value=value)
    assert sf.comtrade_refusal(planted, {"SYN-comtrade"}, FIXTURE_UNITS) == (
        "number_required"
    )


def test_null_value_gives_coverage_gap_never_zero():
    ctx = run(SpyStore([row(value=None)]))
    assert ctx.facts == {}
    assert ctx.blocks == [
        dict(
            block="trade_reporter",
            status="NO_DATA",
            fact_ids=[],
            reason_key="trade_coverage_gap",
        )
    ]


def test_absent_cell_gives_coverage_gap_and_no_sum_of_chapters():
    store = SpyStore([])
    ctx = run(store)
    assert ctx.facts == {}
    assert ctx.blocks[0]["reason_key"] == "trade_coverage_gap"
    # A chapter row returned for a total request is outside the request.
    with pytest.raises(ValueError, match=r"^trade_row_outside_request$"):
        run(SpyStore([row(product_code="01", aggregation_level=2)]))


@pytest.mark.parametrize(
    "change",
    [dict(flow_code="SYN-X"), dict(product_code="02"), dict(partner_code="SYN-q")],
)
def test_row_outside_request_is_refused(change):
    request = dict(flow="SYN-M", product_scope="TOTAL", partner="SYN-world")
    with pytest.raises(ValueError, match=r"^trade_row_outside_request$"):
        run(SpyStore([row(**change)]), request)


def test_duplicate_full_key_refuses_the_block():
    ctx = run(SpyStore([row(), row(value=Decimal("2.0000"))]))
    assert ctx.facts == {}
    assert ctx.blocks == [
        dict(
            block="trade_reporter",
            status="NO_DATA",
            fact_ids=[],
            reason_key="duplicate_row_key",
        )
    ]


@pytest.mark.parametrize(
    ("lines", "sources", "reason"),
    [
        ([], None, "lineage_missing"),
        ([lineage(table_name="pub_trade_wr")], None, "lineage_table_mismatch"),
        (None, [source(url="")], "source_url_missing"),
        (None, [source(licence="")], "source_licence_missing"),
        (None, [source(sha256="SYN-bad")], "source_hash_missing"),
    ],
)
def test_broken_source_chain_is_never_repaired(lines, sources, reason):
    store = SpyStore([row()], lines, sources)
    ctx = run(store)
    ref, found_lines, found_sources = ctx.chain(TABLE)
    assert validate_chain(ref, found_lines, found_sources) == reason
    assert ctx.facts == {}


def test_trade_unit_map_refuses_the_fdi_locked_unit():
    planted = {("SYN-value", "SYN-qar"): "usd_million"}
    assert sf.comtrade_refusal(row(), {"SYN-comtrade"}, planted) == "trade_unit_locked"
    ctx = run(SpyStore([row()]), units=planted)
    assert ctx.facts == {}
    # Even with the FDI caveat attached, the reviewed map is what refuses it.
    assert sf.trade_unit(row(), planted) is None
    assert sf.trade_unit(row(), {("SYN-value", "SYN-qar"): "SYN-unit"}) is None
    assert sf.trade_unit(row(), FIXTURE_UNITS) == "qar"


def test_fdi_caveat_cannot_carry_a_trade_value_in_usd_million():
    planted = {("SYN-value", "SYN-qar"): "usd_million"}
    ctx = run(SpyStore([row()]), units=planted)
    built = sf.comtrade_fact(ctx, row(), planted, caveats=("fdi_estimates",))
    assert built is None and ctx.facts == {}


def test_distinct_native_rows_keep_distinct_fact_ids():
    rows = [row()] + [
        row(**{key: "SYN-alt"})
        for key in sf.COMTRADE_QUALIFIERS
        if key
        not in {
            "series_role",
            "reporter_code",
            "flow_code",
            "product_code",
            "partner_code",
            "aggregation_level",
            "measure",
        }
    ]
    rows += [row(aggregation_level=1), row(period="2023"), row(frequency="monthly")]
    ctx = run(SpyStore(rows))
    assert len(ctx.facts) == len(rows)


def test_every_comtrade_key_column_is_a_named_qualifier_and_period_is_not():
    assert set(sf.COMTRADE_QUALIFIERS) <= QUALIFIER_KEYS
    assert "period" not in sf.COMTRADE_QUALIFIERS
    with pytest.raises(ValueError, match=r"^qualifier_unknown$"):
        fact_id(
            release_id=IDENTITY,
            metric_key="trade_reporter_measure",
            geography={"kind": "national"},
            period="2024",
            qualifiers={"syn_unknown": "x"},
        )


def test_removed_qualifier_key_refuses_the_fact(monkeypatch):
    import eii_core.facts as facts

    monkeypatch.setattr(facts, "QUALIFIER_KEYS", QUALIFIER_KEYS - {"customs_code"})
    assert run(SpyStore([row()])).facts == {}


def test_tool_routes_trade_and_refuses_bad_trade_inputs_before_a_read():
    store = SpyStore([row()])
    good = dict(
        activity="SYN-a", topic="trade", geography="national", trade=dict(REQUEST)
    )
    result = sf.sector_facts(store, good)
    assert result["status"] == "NO_DATA" and store.reads == []
    for change in [
        dict(trade=None),
        dict(trade={**REQUEST, "year": "2024"}),
        dict(trade={**REQUEST, "flow": 1}),
        dict(trade={**REQUEST, "product_scope": 1.0}),
        dict(trade={**REQUEST, "product_scope": "total "}),
        dict(trade={**REQUEST, "product_scope": "123"}),
        dict(trade={**REQUEST, "flow": "M;"}),
        dict(trade={**REQUEST, "partner": "SYN p"}),
        dict(geography="municipality:SYN-local"),
        dict(topic="licences"),
    ]:
        with pytest.raises(ValueError, match=r"^INVALID_ARGUMENT$"):
            sf.sector_facts(store, {**good, **change})
    assert store.reads == []


codes = st.sampled_from(["SYN-a", "SYN-b", "SYN-c"])
rows_strategy = st.lists(
    st.fixed_dictionaries(
        dict(
            partner_code=codes,
            customs_code=codes,
            period=st.sampled_from(["2023", "2024", "2024-01"]),
            aggregation_level=st.integers(0, 6),
            value=st.one_of(
                st.none(),
                st.decimals(
                    min_value=-(10**15),
                    max_value=10**15,
                    places=4,
                    allow_nan=False,
                    allow_infinity=False,
                ),
            ),
            series_role=st.sampled_from(["reporter", "mirror"]),
        )
    ),
    max_size=12,
)


@settings(max_examples=150, deadline=None)
@given(rows_strategy, st.randoms(use_true_random=False))
def test_property_values_pass_byte_for_byte_and_ids_ignore_order(changes, rng):
    rows = [row(**change) for change in changes]
    keys = [tuple(r[k] for k in (*sf.COMTRADE_QUALIFIERS, "period")) for r in rows]
    ctx = run(SpyStore(rows))
    shuffled = list(rows)
    rng.shuffle(shuffled)
    again = run(SpyStore(shuffled))
    assert set(ctx.facts) == set(again.facts)
    if len(keys) != len(set(keys)):
        assert ctx.facts == {} and ctx.blocks[0]["reason_key"] == "duplicate_row_key"
        return
    kept = [
        r for r in rows if r["series_role"] == "reporter" and r["value"] is not None
    ]
    assert len(ctx.facts) == len(kept)
    stored = sorted(repr(normalise(r["value"])) for r in kept)
    assert sorted(repr(f.value) for f in ctx.facts.values()) == stored
    if any(r["value"] is None for r in rows):
        assert ctx.blocks[0].get("reason_key") == "trade_coverage_gap"


def test_tool_input_admits_the_trade_object_and_store_params_stay_scalar():
    from typing import get_args

    from eii_product.store.protocol import Param, ToolInput
    from eii_product.store.registry import bind

    assert dict[str, str] in get_args(ToolInput.__value__)
    assert all(
        getattr(item, "__origin__", item) is not dict
        for item in get_args(Param.__value__)
    )
    spec = FIXTURE.get(sf.COMTRADE_QUERY)
    with pytest.raises(StoreRefusal, match=r"^parameter types invalid$"):
        bind(spec, dict(flow={"x": "y"}, product_code="TOTAL", partner=""), "embedded")


json_leaf = st.one_of(
    st.none(),
    st.booleans(),
    st.integers(),
    st.floats(),
    st.text(max_size=6),
    st.sampled_from(["SYN-M", "TOTAL", "01", "99", "SYN-world"]),
)
trade_objects = st.dictionaries(
    st.sampled_from(["flow", "product_scope", "partner", "year", "period"]),
    json_leaf,
    max_size=4,
)


@settings(max_examples=300, deadline=None)
@given(trade_objects, st.sampled_from(["national", "municipality:SYN-a"]))
def test_property_trade_input_is_refused_unread_or_valid(trade, geography):
    store = SpyStore([row()])
    raw = dict(activity="SYN-a", topic="trade", geography=geography, trade=trade)
    valid = (
        geography == "national"
        and set(trade) <= {"flow", "product_scope", "partner"}
        and {"flow", "product_scope"} <= set(trade)
        and type(trade["flow"]) is str
        and re.fullmatch(r"[A-Za-z0-9_-]+", trade["flow"]) is not None
        and type(trade["product_scope"]) is str
        and re.fullmatch(r"TOTAL|[0-9]{2}", trade["product_scope"]) is not None
        and (
            trade.get("partner") is None
            or (
                type(trade["partner"]) is str
                and re.fullmatch(r"[A-Za-z0-9_-]+", trade["partner"]) is not None
            )
        )
    )
    if valid:
        assert sf.sector_facts(store, raw)["status"] == "NO_DATA"
    else:
        with pytest.raises(ValueError, match=r"^INVALID_ARGUMENT$"):
            sf.sector_facts(store, raw)
    assert store.reads == []
