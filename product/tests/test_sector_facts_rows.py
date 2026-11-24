"""Exact boundary contracts for the sector-facts campaign survivors."""

from decimal import Decimal
from typing import Any
from uuid import UUID

import pytest
from product.tests.sector_fixture import (
    IDENTITY,
    churn_rows,
    fixed_rows,
    licence_rows,
    norm_rows,
    pay_rows,
    release_store,
    repository_path,
    utility_rows,
    with_lineage,
)
from product.tests.test_fact_builder_rows import builder_inputs

from eii_product.store import QueryResult
from eii_product.tools import sector_facts as module
from eii_product.tools.fact_builder import build_calculated


def unchecked(value: Any) -> Any:
    return value


def run(topic, data, **changes):
    with release_store(with_lineage(data)) as store:
        return module.sector_facts(
            store,
            dict(
                activity="SYN-restaurant",
                topic=topic,
                geography="municipality:SYN-local",
                **changes,
            ),
        )


def empty(name, **extra):
    return dict(block=name, status="NO_DATA", fact_ids=[], **extra)


def refusal(action, expected):
    with pytest.raises(ValueError) as caught:
        action()
    assert str(caught.value) == expected


@pytest.mark.parametrize("row", [(), (1, 2)])
def test_read_requires_exact_row_width(row):
    class Store:
        def fetch(self, query, params):
            return QueryResult(("value",), (row,))

    with pytest.raises(ValueError):
        module._read(unchecked(Store()), "licence_local")


@pytest.mark.parametrize(
    "plant,message",
    [
        ("lineage", "lineage_missing"),
        ("source", "source_missing"),
        ("number", "number_required"),
    ],
)
def test_measure_refusal_messages(plant, message):
    with release_store(with_lineage(licence_rows())) as store:
        ctx = module.Context(
            store,
            module.Inputs(activity="SYN-a", topic="licences", geography="national"),
        )
        row = dict(period="2025", value=12, source_id="SYN-pub_licence_active")
        if plant == "lineage":
            ctx.chains["lin_pub_licence_active"] = ([], [])
        elif plant == "source":
            row["source_id"] = "SYN-missing"
        else:
            row["value"] = "12"
        refusal(
            lambda: ctx.measure(
                row, "pub_licence_active", "value", "count", "national"
            ),
            message,
        )


def test_block_drops_fact_without_cached_chain():
    result, kwargs = builder_inputs()
    fact = build_calculated(result, **kwargs)
    assert fact is not None
    with release_store({}) as store:
        ctx = module.Context(
            store,
            module.Inputs(activity="SYN-a", topic="licences", geography="national"),
        )
        ctx.block("SYN-block", [fact])
    assert ctx.blocks == [empty("SYN-block")]
    assert ctx.facts == {}


@pytest.mark.parametrize(
    "plant,block",
    [("missing", "licences"), ("duplicate", "licences"), ("invalid", "quotient")],
)
def test_licence_failure_blocks(plant, block):
    data = licence_rows()
    if plant == "missing":
        data["pub_licence_active"] = []
    elif plant == "duplicate":
        data["pub_licence_active"].append(
            dict(data["pub_licence_active"][0], period="2025-04")
        )
    else:
        data["pub_licence_active"][0]["active_count"] = -1
    result = run("licences", data)
    assert result["blocks"] == [empty("national_density"), empty(block)]


@pytest.mark.parametrize("count", [4, 10])
def test_licence_count_reliability_and_density_caveats(count):
    data = licence_rows()
    data["pub_licence_active"][0]["active_count"] = count
    result = run("licences", data)
    blocks = {b["block"]: b for b in result["blocks"]}
    assert blocks["national_density"] == empty("national_density")
    assert blocks["density"]["status"] == "OK"
    assert all(f.reliability == "low_count" for f in result["facts"])
    density = next(f for f in result["facts"] if f.label_en == "Licence density")
    assert density.caveat_keys == [
        "calculated",
        "licence_activity_not_firm",
        "snapshot_may_2025",
    ]
    if count == 4:
        assert blocks["quotient"] == empty("quotient", reason_key="too_few_licences")
        assert blocks["licence_count"]["status"] == "OK"
    else:
        assert blocks["quotient"]["status"] == "OK"


@pytest.mark.parametrize("plant", ["missing", "duplicate", "stock_year"])
def test_density_requires_one_resident_row_and_snapshot(plant):
    data = licence_rows()
    if plant == "missing":
        data["pub_population_municipality"] = []
    elif plant == "duplicate":
        data["pub_population_municipality"].append(
            dict(data["pub_population_municipality"][0])
        )
    else:
        for row in data["pub_licence_active"]:
            row["period"] = "2024-05"
    result = run("licences", data)
    assert empty("density") in result["blocks"]


def test_envelope_exact_fields():
    result = run("market_context", fixed_rows())
    assert set(result) == {
        "tool",
        "call_id",
        "release_id",
        "engine",
        "status",
        "blocks",
        "facts",
        "payload",
        "caveat_keys",
    }
    assert result["tool"] == "sector_facts"
    assert result["release_id"] == IDENTITY
    assert result["engine"] == "embedded"
    assert result["caveat_keys"] == []
    assert str(UUID(result["call_id"], version=4)) == result["call_id"]


@pytest.mark.parametrize(
    "change",
    [
        dict(activity="!"),
        dict(geography="!"),
        dict(
            topic="churn", scenario_inputs=dict(monthly_rent=1, seats=1, average_bill=1)
        ),
    ],
)
def test_full_invalid_argument_refusal(change):
    with release_store({}) as store:
        args = dict(activity="SYN-a", topic="licences", geography="national")
        args.update(change)
        refusal(lambda: module.sector_facts(store, args), "INVALID_ARGUMENT")


def test_repository_search_fails_loudly(tmp_path):
    with pytest.raises(FileNotFoundError):
        repository_path("SYN-missing-file", tmp_path / "tests" / "test.py")


@pytest.mark.parametrize(
    "topic,blocks",
    [
        ("employer_scale", ["employer_scale", "census"]),
        ("market_context", ["market_context"]),
        ("visitor_markets", ["hotels", "visitors"]),
    ],
)
def test_fixed_qualifiers_and_caveats(monkeypatch, topic, blocks):
    original = module.build_published
    seen = {}

    def record(**arguments):
        fact = original(**arguments)
        assert fact is not None
        seen[fact.fact_id] = (arguments["metric_key"], arguments["qualifiers"])
        return fact

    monkeypatch.setattr(module, "build_published", record)
    result = run(topic, fixed_rows())
    assert [b["block"] for b in result["blocks"]] == blocks
    specs = {
        "Employees": (
            "employees",
            {
                "table_code": "SYN-size",
                "indicator": "employees",
                "size_class": "s01_09",
            },
        ),
        "Size class": (
            "size_class",
            {
                "table_code": "SYN-size",
                "indicator": "employees",
                "size_class": "s01_09",
            },
        ),
        "Establishments": ("establishments", {"indicator": "establishments"}),
        "Purchases": (
            "purchases",
            {"indicator": "purchases", "trade_type": "SYN-restaurant"},
        ),
        "Sales": ("sales", {"indicator": "sales", "trade_type": "SYN-restaurant"}),
        "Facilities": ("facilities", {"facility_type": "SYN-hotel"}),
        "Arrivals": (
            "arrivals",
            {
                "table_code": "SYN-visitors",
                "indicator": "arrivals",
                "nationality_group": "SYN-group",
                "breakdown_key": "SYN-all",
            },
        ),
        "Guests": (
            "guests",
            {
                "table_code": "SYN-visitors",
                "indicator": "guests",
                "nationality_group": "SYN-group",
                "breakdown_key": "SYN-all",
            },
        ),
    }
    for fact in result["facts"]:
        metric, qualifiers = specs[fact.label_en]
        assert seen[fact.fact_id] == (
            metric,
            dict(qualifiers, activity="SYN-restaurant"),
        )
        assert fact.caveat_keys == (
            ["dated_census"] if fact.label_en == "Establishments" else []
        )


@pytest.mark.parametrize("plant", ["source", "unit"])
def test_fixed_invalid_row_does_not_drop_later_row(plant):
    data = fixed_rows()
    row = data["pub_trade_wr"][0]
    row["source_id" if plant == "source" else "unit"] = "SYN-unknown"
    result = run("market_context", data)
    # The second stored row is 41.73 QAR; no calculation or conversion.
    assert [(f.label_en, f.value) for f in result["facts"]] == [
        ("Sales", Decimal("41.73"))
    ]


@pytest.mark.parametrize("plant", ["outside_period", "missing_cell"])
def test_pay_failure_block(monkeypatch, plant):
    data = pay_rows()
    if plant == "missing_cell":
        data["pub_wage_table"] = [
            r for r in data["pub_wage_table"] if r["indicator"] != "paid_workers"
        ]
    else:
        original = module._read

        def read(store, name, **params):
            rows = original(store, name, **params)
            return [dict(rows[0], period="2019")] if name == "wages" else rows

        monkeypatch.setattr(module, "_read", read)
    assert run("pay_decomposition", data)["blocks"] == [empty("pay_decomposition")]


@pytest.mark.parametrize(
    "topic,builder,names,caveats,qualifiers",
    [
        (
            "pay_decomposition",
            pay_rows,
            ["pay_decomposition"],
            ["calculated", "named_table", "composition_not_wages"],
            {"table_code": "wage_occ"},
        ),
        (
            "zone_momentum",
            utility_rows,
            [
                "national_momentum",
                "zone_momentum",
                "zone_momentum",
                "zone_momentum",
                "zone_momentum",
                "zone_momentum",
            ],
            ["calculated", "activity_proxy_not_population"],
            {"utility": "electricity"},
        ),
        (
            "unit_economics",
            norm_rows,
            [
                "unit_economics",
                "unit_economics",
                "unit_economics",
                "unit_economics",
                "unit_economics",
                "scenario",
            ],
            ["calculated", "national_average", "world_cup_year"],
            {"activity": "SYN-restaurant"},
        ),
    ],
)
def test_calculation_metadata(monkeypatch, topic, builder, names, caveats, qualifiers):
    original = module.build_calculated
    seen = []

    def spy(result, **kwargs):
        assert kwargs["qualifiers"] == qualifiers
        fact = original(result, **kwargs)
        assert fact is not None
        assert fact.caveat_keys == caveats
        seen.append(fact.fact_id)
        return fact

    monkeypatch.setattr(module, "build_calculated", spy)
    result = run(topic, builder())
    assert seen
    assert [b["block"] for b in result["blocks"]] == names


def test_momentum_failure_block():
    data = utility_rows()
    data["pub_zone_utility"][0]["partial_year"] = True
    assert run("zone_momentum", data)["blocks"] == [empty("zone_momentum")]


@pytest.mark.parametrize("plant", ["employees", "unit"])
def test_norm_failure_continues_to_later_years(plant):
    data = norm_rows()
    rows = data["pub_sector_accounts"]
    if plant == "employees":
        data["pub_sector_accounts"] = [
            r
            for r in rows
            if not (r["period"] == "2018" and r["indicator"].startswith("employees:"))
        ]
    else:
        next(
            r
            for r in rows
            if r["period"] == "2018" and r["indicator"] == "compensation"
        )["unit"] = "count"
    result = run("unit_economics", data)
    assert result["blocks"][0] == empty("unit_economics")
    assert [b["block"] for b in result["blocks"]] == ["unit_economics"] * 5 + [
        "scenario"
    ]
    assert {f.period for f in result["facts"]} == {"2019", "2020", "2021", "2022"}


def test_norm_missing_component_keeps_other_components():
    data = norm_rows()
    data["pub_sector_accounts"] = [
        r
        for r in data["pub_sector_accounts"]
        if r["indicator"] != "intermediate_goods:Food%20Stuff"
    ]
    result = run("unit_economics", data)
    assert len(result["facts"]) == 30  # Five years times six retained metrics.
    assert all(b["status"] == "OK" for b in result["blocks"][:-1])
    assert not any(f.label_en == "Food share" for f in result["facts"])


def test_norm_out_of_scope_block():
    assert run("unit_economics", {})["blocks"] == [
        dict(block="unit_economics", status="OUT_OF_SCOPE", fact_ids=[]),
        empty("scenario"),
    ]


def test_churn_exact_metadata(monkeypatch):
    original = module.build_calculated
    seen = []

    def spy(result, **kwargs):
        assert kwargs["lineage_ref"] == (
            "lin_pub_licence_active_churn"
            if result.metric_key == "active_count"
            else "lin_pub_licence_cancelled_churn"
        )
        if result.metric_key in {"undated_count", "bulk_share"}:
            assert kwargs["qualifiers"] == {}
        else:
            if result.metric_key != "active_count":
                assert result.base_period == "2025-05"
                assert result.period in {
                    "2015",
                    "2016",
                    "2017",
                    "2018",
                    "2019",
                    "2020",
                    "2021",
                    "2022",
                    "2023",
                    "2024",
                }
        seen.append(result.metric_key)
        return original(result, **kwargs)

    monkeypatch.setattr(module, "build_calculated", spy)
    result = run("churn", churn_rows())
    assert seen
    assert result["blocks"][-1]["block"] == "churn_national"
    flags = [f for f in result["facts"] if f.unit == "calendar_month"]
    assert flags
    assert all(f.caveat_keys == ["calculated"] for f in flags)


def test_churn_interval_block_names():
    data = churn_rows()
    data["pub_licence_active"][0]["active_count"] = 1
    result = run("churn", data)
    assert (
        empty("churn_2024_including_interval", reason_key="not_coverable")
        in result["blocks"]
    )


def test_churn_bad_measure_continues_all_years():
    data = churn_rows()
    data["pub_licence_active"][0]["active_count"] = -1
    result = run("churn", data)
    assert [b for b in result["blocks"] if b["block"] != "bulk_months"] == [
        empty("churn_" + year)
        for year in [
            "2015",
            "2016",
            "2017",
            "2018",
            "2019",
            "2020",
            "2021",
            "2022",
            "2023",
            "2024",
        ]
    ]


def test_churn_full_refusal_message(monkeypatch):
    original = module._read

    def read(store, name, **params):
        if name == "churn_local":
            return [dict(period="UNDATED")]
        return original(store, name, **params)

    monkeypatch.setattr(module, "_read", read)
    refusal(lambda: run("churn", churn_rows()), "churn_month_outside_request")


def test_internal_unit_refusal_text():
    import sys

    from eii_core.calc.facts import MeasureMismatch

    data = norm_rows()
    for row in data["pub_sector_accounts"]:
        if row["indicator"] == "compensation":
            row["unit"] = "count"
    messages = set()

    def trace(frame, event, arg):
        if event == "exception" and isinstance(arg[1], MeasureMismatch):
            messages.add(str(arg[1]))
        return trace

    previous = sys.gettrace()
    try:
        sys.settrace(trace)
        run("unit_economics", data)
    finally:
        sys.settrace(previous)
    assert messages == {"unit mismatch"}


@pytest.mark.parametrize(
    "change,message",
    [
        (dict(activity="!"), "activity"),
        (dict(geography="!"), "geography"),
        (
            dict(scenario_inputs=dict(monthly_rent=1, seats=1, average_bill=1)),
            "scenario",
        ),
    ],
)
def test_validation_exception_context(change, message):
    with release_store({}) as store:
        args = dict(activity="SYN-a", topic="licences", geography="national")
        args.update(change)
        with pytest.raises(ValueError) as caught:
            module.sector_facts(store, args)
        assert str(caught.value) == "INVALID_ARGUMENT"
        assert str(caught.value.__context__) == message
