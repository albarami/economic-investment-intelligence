"""Closed inputs and response guarantees, using invented release rows only."""

import pytest


@pytest.mark.parametrize(
    "change",
    [
        dict(topic="unknown"),
        dict(year="2025"),
        dict(geography="area:SYN-a"),
        dict(activity="SELECT * FROM secret"),
    ],
)
def test_closed_inputs(change):
    from eii_product.tools.sector_facts import sector_facts

    class Unread:
        def fetch(self, *args):
            raise AssertionError("input read before validation")

    with pytest.raises(
        ValueError,
        match="^"
        + ("INVALID_ARGUMENT" if "year" in change else next(iter(change)))
        + "$",
    ):
        sector_facts(
            Unread(),
            {
                **dict(activity="SYN-a", topic="licences", geography="national"),
                **change,
            },
        )


def test_fixed_reads_and_size_classes():
    from product.tests.sector_fixture import release_store, with_lineage

    from eii_product.tools.sector_facts import sector_facts

    data = {
        "pub_establishment_size": [
            dict(
                table_code="SYN-bulletin",
                activity_key="SYN-a",
                period="2022",
                size_class=size,
                indicator="employees",
                value=value,
                unit="persons",
                source_id="SYN-pub_establishment_size",
            )
            for size, value in [("s01_09", 12), ("SYN-class-12", 24)]
        ]
    }
    with release_store(with_lineage(data)) as store:
        result = sector_facts(
            store, dict(activity="SYN-a", geography="national", topic="employer_scale")
        )
    assert {f.value for f in result["facts"] if f.unit == "count"} == {12, 24}
    assert {f.value for f in result["facts"] if f.unit == "size_band"} == {"s01_09"}
    assert {f.value for f in result["facts"] if f.unit == "published_text"} == {
        "SYN-class-12"
    }
    assert all("calculated" not in f.caveat_keys for f in result["facts"])


def test_quotient_needs_no_residents():
    from product.tests.sector_fixture import licence_store

    from eii_product.tools.sector_facts import sector_facts

    with licence_store() as store:
        result = sector_facts(
            store,
            dict(
                activity="SYN-restaurant",
                geography="municipality:SYN-local",
                topic="licences",
            ),
        )
    blocks = {b["block"]: b for b in result["blocks"]}
    assert blocks["national_density"]["status"] == "NO_DATA"
    assert blocks["quotient"]["status"] == "OK"
    assert len(blocks["quotient"]["fact_ids"]) == 3


@pytest.mark.parametrize("plant", ["fraction", "null", "source", "hash"])
def test_invalid_fact_is_dropped_from_the_response(plant):
    from decimal import Decimal

    from product.tests.sector_fixture import release_store, with_lineage

    from eii_product.tools.sector_facts import sector_facts

    rows = [
        dict(
            trade_type="SYN-a",
            period="2025",
            indicator=indicator,
            value=value,
            unit="count",
            source_id="SYN-pub_trade_wr",
        )
        for indicator, value in [("purchases", 2), ("sales", 3)]
    ]
    data = with_lineage({"pub_trade_wr": rows})
    if plant == "fraction":
        data["pub_trade_wr"][0]["value"] = Decimal("2.5")
    elif plant == "null":
        data["pub_trade_wr"][0]["value"] = None
    elif plant == "source":
        data["source_registry"] = []
    else:
        data["source_registry"][0]["sha256"] = ""
    with release_store(data) as store:
        result = sector_facts(
            store, dict(activity="SYN-a", geography="national", topic="market_context")
        )
    if plant in {"fraction", "null"}:
        assert [f.value for f in result["facts"]] == [3]
        assert result["status"] == "OK"
    else:
        assert result["facts"] == []
        assert result["status"] == "NO_DATA"
    valid = {f.fact_id for f in result["facts"]}
    assert all(set(b["fact_ids"]) <= valid for b in result["blocks"])


def test_partial_utility_year_is_refused():
    from product.tests.sector_fixture import release_store, utility_rows, with_lineage

    from eii_product.tools.sector_facts import sector_facts

    data = utility_rows()
    data["pub_zone_utility"][0]["partial_year"] = True
    with release_store(with_lineage(data)) as store:
        result = sector_facts(
            store, dict(activity="SYN-a", topic="zone_momentum", geography="national")
        )
    assert result["status"] == "NO_DATA"
    assert result["facts"] == []


def test_scenario_block_is_no_data():
    from product.tests.sector_fixture import release_store, with_lineage

    from eii_product.tools.sector_facts import sector_facts

    with release_store(with_lineage({})) as store:
        result = sector_facts(
            store,
            dict(
                activity="SYN-a",
                topic="unit_economics",
                geography="national",
                scenario_inputs=dict(monthly_rent=40000, seats=60, average_bill=120),
            ),
        )
    block = next(b for b in result["blocks"] if b["block"] == "scenario")
    assert block == dict(block="scenario", status="NO_DATA", fact_ids=[])


def test_churn_years_come_from_the_calculation_layer(monkeypatch):
    from product.tests.sector_fixture import IDENTITY

    from eii_core.calc.public_series import complete_years
    from eii_product.store import QueryResult
    from eii_product.tools import sector_facts as module

    calls = []

    class Recorder:
        release_id = IDENTITY
        engine = "embedded"

        def fetch(self, query, params):
            calls.append((query.name, params))
            return QueryResult((), ())

    result = module.sector_facts(
        Recorder(),
        dict(activity="SYN-a", geography="municipality:SYN-a", topic="churn"),
    )
    expected = complete_years()
    assert [b["block"] for b in result["blocks"]] == [
        "churn_" + year for year, _ in expected
    ]
    assert [p["months"] for q, p in calls if q == "sector_facts_churn_local"] == [
        list(months) for _, months in expected
    ]
    assert all(b["status"] == "NO_DATA" for b in result["blocks"])
    assert result["facts"] == []


def test_churn_adapter_refuses_another_year():
    from product.tests.sector_fixture import IDENTITY

    from eii_product.store import QueryResult
    from eii_product.tools.sector_facts import sector_facts

    class BadRows:
        release_id = IDENTITY
        engine = "embedded"

        def fetch(self, query, params):
            return (
                QueryResult(("period",), (("UNDATED",),))
                if query.name == "sector_facts_churn_local"
                else QueryResult((), ())
            )

    with pytest.raises(ValueError, match="churn_month_outside_request"):
        sector_facts(
            BadRows(),
            dict(activity="SYN-a", geography="municipality:SYN-a", topic="churn"),
        )


def no_arithmetic(source):
    import ast

    tree = ast.parse(source)
    assert not any(
        isinstance(n, (ast.Div, ast.FloorDiv, ast.Mod)) for n in ast.walk(tree)
    )
    assert not any(
        isinstance(n, ast.Call)
        and isinstance(n.func, ast.Name)
        and n.func.id in {"round", "sum", "min", "max", "sorted"}
        for n in ast.walk(tree)
    )


def test_every_number_comes_from_calc_or_a_fixed_tested_read(monkeypatch):
    """MTH-01 admits fixed tested Public reads alongside calc output identities."""
    from product.tests.sector_fixture import (
        churn_rows,
        licence_rows,
        norm_rows,
        pay_rows,
        release_store,
        repository_path,
        utility_rows,
        with_lineage,
    )

    from eii_core import calc
    from eii_core.calc.facts import CalculationFact
    from eii_product.tools.sector_facts import sector_facts

    returned = []

    def record(value):
        if isinstance(value, CalculationFact):
            returned.append(value.value)
        elif isinstance(value, dict):
            for v in value.values():
                record(v)
        elif isinstance(value, tuple):
            for v in value:
                record(v)

    for name in (
        "licence_density",
        "location_quotient",
        "decomposition",
        "zone_momentum",
        "licence_churn",
        "sector_norms",
    ):
        original = getattr(calc, name)

        def spy(*args, _original=original, **kwargs):
            result = _original(*args, **kwargs)
            record(result)
            return result

        monkeypatch.setattr(calc, name, spy)
    for topic, data, geography in [
        ("licences", licence_rows(), "municipality:SYN-local"),
        ("pay_decomposition", pay_rows(), "national"),
        ("zone_momentum", utility_rows(), "national"),
        ("churn", churn_rows(), "municipality:SYN-local"),
        ("unit_economics", norm_rows(), "national"),
    ]:
        returned.clear()
        with release_store(with_lineage(data)) as store:
            result = sector_facts(
                store, dict(activity="SYN-restaurant", topic=topic, geography=geography)
            )
        assert result["facts"]
        assert all(
            any(f.value is value for value in returned)
            for f in result["facts"]
            if f.unit != "calendar_month"
        )
    for name in ("sector_facts.py", "fact_builder.py"):
        no_arithmetic(
            repository_path(
                "product/src/eii_product/tools/" + name, __file__
            ).read_text()
        )
    for source in ("x = a / b", "x = round(a)", "x = sum(rows)"):
        with pytest.raises(AssertionError):
            no_arithmetic(source)


def payload_is_pure(value):
    if isinstance(value, dict):
        for key, item in value.items():
            assert isinstance(key, str)
            payload_is_pure(item)
    elif isinstance(value, list):
        for item in value:
            payload_is_pure(item)
    else:
        assert isinstance(value, str)
        assert not any(c.isdigit() for c in value) or value.startswith(
            ("f_", "SYN-", "zone:")
        )


def test_payload_purity():
    from product.tests.sector_fixture import licence_store

    from eii_product.tools.sector_facts import TOPICS, sector_facts

    for topic in TOPICS:
        with licence_store() as store:
            trade = dict(flow="SYN-M", product_scope="TOTAL")
            result = sector_facts(
                store,
                dict(activity="SYN-a", topic=topic, geography="national")
                | (dict(trade=trade) if topic == "trade" else {}),
            )
        payload_is_pure(result["payload"])
    with pytest.raises(AssertionError):
        payload_is_pure({"count": 2})
    with pytest.raises(AssertionError):
        payload_is_pure({"label": "Count 2"})


def test_statuses_and_reasons():
    from product.tests.sector_fixture import licence_rows, release_store, with_lineage

    from eii_product.tools.sector_facts import sector_facts

    data = licence_rows()
    data["pub_licence_active"][0]["active_count"] = 9
    with release_store(with_lineage(data)) as store:
        result = sector_facts(
            store,
            dict(
                activity="SYN-restaurant",
                topic="licences",
                geography="municipality:SYN-local",
            ),
        )
        scope = sector_facts(
            store,
            dict(activity="SYN-missing", topic="unit_economics", geography="national"),
        )
        missing = sector_facts(
            store, dict(activity="SYN-missing", topic="licences", geography="national")
        )
    quotient = next(b for b in result["blocks"] if b["block"] == "quotient")
    assert quotient["status"] == "NO_DATA"
    assert quotient["reason_key"] == "too_few_licences"
    assert (
        next(f.value for f in result["facts"] if f.label_en == "Local licence count")
        == 9
    )
    assert scope["status"] == "OUT_OF_SCOPE"
    assert missing["status"] == "NO_DATA"
    assert all("reason_key" not in b for b in scope["blocks"] + missing["blocks"])


def test_mixed_geography_cannot_bypass_assembly():
    from product.tests.sector_fixture import IDENTITY
    from product.tests.test_fact_builder import fixture

    from eii_product.tools.fact_builder import build_calculated
    from eii_product.tools.sector_facts import Context, Inputs

    value, lines, sources = fixture()
    fact = build_calculated(
        value,
        release_id=IDENTITY,
        lineage_ref="lin_pub_licence_active",
        lineage_rows=lines,
        source_rows=sources,
        qualifiers={},
    )
    forged = fact.model_copy(
        update={"geography": {"kind": "national", "public_code": "zone:SYN-a"}}
    )
    ctx = Context(
        object(), Inputs(activity="SYN-a", topic="licences", geography="national")
    )
    ctx.chains[fact.lineage_ref] = (lines, sources)
    ctx.block("SYN-block", [forged, fact])
    assert list(ctx.facts.values()) == [fact]
    ctx2 = Context(object(), ctx.inputs)
    ctx2.block("SYN-empty", [forged])
    assert ctx2.blocks == [
        dict(
            block="SYN-empty", status="NO_DATA", fact_ids=[], reason_key="fact_invalid"
        )
    ]


def test_stored_bulk_flag_agrees_with_the_calculator():
    from product.tests.sector_fixture import release_store, with_lineage

    from eii_product.tools.sector_facts import sector_facts

    data = {
        "pub_licence_cancelled": [
            dict(
                municipality_code="SYN-local",
                activity_code="SYN-a",
                period="2024-09",
                cancelled_count=11232,
                bulk_month=True,
                source_id="SYN-pub_licence_cancelled",
            )
        ]
    }
    with release_store(with_lineage(data)) as store:
        result = sector_facts(
            store,
            dict(activity="SYN-a", geography="municipality:SYN-local", topic="churn"),
        )
    months = [f for f in result["facts"] if f.unit == "calendar_month"]
    assert [f.value for f in months] == ["2024-09"]
    assert all(f.geography == {"kind": "national"} for f in months)
    data["pub_licence_cancelled"][0]["bulk_month"] = False
    with release_store(with_lineage(data)) as store:
        result = sector_facts(
            store,
            dict(activity="SYN-a", geography="municipality:SYN-local", topic="churn"),
        )
    assert result["facts"] == []


def test_fixed_read_refuses_unresolved_row_source():
    from product.tests.sector_fixture import release_store, with_lineage

    from eii_product.tools.sector_facts import sector_facts

    data = with_lineage(
        {
            "pub_trade_wr": [
                dict(
                    trade_type="SYN-a",
                    period="2025",
                    indicator="sales",
                    value=7,
                    unit="count",
                    source_id="SYN-unresolved",
                )
            ]
        }
    )
    with release_store(data) as store:
        result = sector_facts(
            store, dict(activity="SYN-a", topic="market_context", geography="national")
        )
    assert result["facts"] == []


def test_scenario_extra_field_refused():
    from eii_product.tools.sector_facts import Inputs

    with pytest.raises(ValueError):
        Inputs.model_validate(
            dict(
                activity="SYN-a",
                topic="unit_economics",
                geography="national",
                scenario_inputs=dict(
                    monthly_rent=1, seats=1, average_bill=1, unknown=1
                ),
            )
        )
