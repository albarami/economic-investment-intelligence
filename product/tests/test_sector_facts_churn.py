"""C2 through the actual named reads, with invented release rows."""

from decimal import Decimal

import pytest
from product.tests.sector_fixture import churn_rows, release_store, with_lineage

from eii_core import calc
from eii_core.calc.public_series import C2_CALENDAR, complete_years
from eii_product.store.parity import TracingStore
from eii_product.tools import sector_facts as module


def run_churn(data, area="SYN-local"):
    with release_store(with_lineage(data)) as store:
        return module.sector_facts(
            store,
            dict(
                activity="SYN-restaurant",
                topic="churn",
                geography="municipality:" + area,
            ),
        )


@pytest.mark.parametrize(
    "area,expected", [("SYN-local", "15.1"), ("SYN-second", "13.6")]
)
def test_churn_reproduces_card_c2_through_store(area, expected):
    result = run_churn(churn_rows(), area)
    block = next(b for b in result["blocks"] if b["block"] == "churn_2024")
    facts = {f.label_en: f for f in result["facts"] if f.fact_id in block["fact_ids"]}
    assert block["status"] == "OK"
    assert facts["Churn including flagged months"].value == Decimal(expected)
    assert facts["Churn excluding flagged months"].value == Decimal("0.0")
    assert facts["Churn including flagged months"].period == "2024"
    assert facts["Churn including flagged months"].geography == {
        "kind": "public",
        "public_code": "municipality:" + area,
    }
    assert (
        next(f.value for f in result["facts"] if f.label_en == "Undated cancellations")
        == 7386
    )
    for fact in result["facts"]:
        if fact.label_en in {"Undated cancellations", "Flagged cancellation share"}:
            assert fact.geography == {"kind": "national"}


def test_churn_blocks_cover_each_complete_year_and_distinct_intervals():
    result = run_churn(churn_rows())
    blocks = [
        b for b in result["blocks"] if b["block"].removeprefix("churn_").isdigit()
    ]
    assert [b["block"] for b in blocks] == [
        "churn_" + year for year, _ in complete_years()
    ]
    assert all(b["status"] == "OK" for b in blocks)
    ids = {f.fact_id for f in result["facts"]}
    assert all(set(b["fact_ids"]) <= ids for b in result["blocks"])
    block = next(b for b in blocks if b["block"] == "churn_2024")
    lows = [
        f
        for f in result["facts"]
        if f.fact_id in block["fact_ids"] and f.label_en == "Churn lower bound"
    ]
    assert len(lows) == 2
    assert lows[0].fact_id != lows[1].fact_id
    assert lows[0].value != lows[1].value


def test_churn_adapter_selects_one_year(monkeypatch):
    data = churn_rows()
    other = dict(data["pub_licence_cancelled"][0], period="2023-01", cancelled_count=7)
    data["pub_licence_cancelled"].append(other)
    calls = []
    original = calc.licence_churn

    def spy(active, local, national, calendar, all_rows, dated_rows):
        calls.append((tuple(local), calendar, all_rows.value, dated_rows.value))
        return original(active, local, national, calendar, all_rows, dated_rows)

    monkeypatch.setattr(calc, "licence_churn", spy)
    result = run_churn(data)
    assert len(calls) == len(complete_years())
    for (_, months), (local, calendar, all_count, dated_count) in zip(
        complete_years(), calls, strict=True
    ):
        assert set(local) <= set(months)
        assert "UNDATED" not in local
        assert calendar is C2_CALENDAR
        assert all_count - dated_count == 7386
    assert next(
        f.value
        for f in result["facts"]
        if f.period == "2024" and f.label_en == "Churn including flagged months"
    ) == Decimal("15.1")


def test_churn_reads_both_national_sums():
    seen = []
    with release_store(with_lineage(churn_rows())) as store:
        module.sector_facts(
            TracingStore(store, seen),
            dict(
                activity="SYN-restaurant",
                topic="churn",
                geography="municipality:SYN-local",
            ),
        )
    assert {"sector_facts_churn_total", "sector_facts_churn_dated_total"} <= set(seen)


@pytest.mark.parametrize(
    "plant",
    [
        "no_active",
        "two_active",
        "zero_active",
        "negative",
        "out_of_calendar",
        "missing_source",
        "null",
    ],
)
def test_churn_refuses_invalid_inputs(plant):
    data = churn_rows()
    if plant == "no_active":
        data["pub_licence_active"] = []
    elif plant == "two_active":
        data["pub_licence_active"].append(
            dict(data["pub_licence_active"][0], period="2025-04")
        )
    elif plant == "zero_active":
        data["pub_licence_active"][0]["active_count"] = 0
    elif plant == "negative":
        data["pub_licence_cancelled"][4]["cancelled_count"] = -1
    elif plant == "out_of_calendar":
        data["pub_licence_cancelled"][0]["period"] = "2026-01"
    elif plant == "null":
        data["pub_licence_cancelled"][4]["cancelled_count"] = None
    else:
        data["pub_licence_active"][0]["source_id"] = "SYN-missing"
    result = run_churn(data)
    blocks = [
        b for b in result["blocks"] if b["block"].removeprefix("churn_").isdigit()
    ]
    assert blocks
    assert all(b["status"] == "NO_DATA" and not b["fact_ids"] for b in blocks)


def test_churn_flow_above_stock_keeps_rates_without_intervals():
    data = churn_rows()
    data["pub_licence_active"][0]["active_count"] = 1
    result = run_churn(data)
    assert next(
        f.value
        for f in result["facts"]
        if f.period == "2024" and f.label_en == "Churn including flagged months"
    ) == Decimal("31800.0")
    assert any(b.get("reason_key") == "not_coverable" for b in result["blocks"])


def test_churn_zero_dated_count_retains_no_denominator_reason():
    data = churn_rows()
    for row in data["pub_licence_cancelled"]:
        row["cancelled_count"] = 0
        row["bulk_month"] = False
    result = run_churn(data)
    assert (
        dict(
            block="bulk_share",
            status="NO_DATA",
            fact_ids=[],
            reason_key="no_denominator",
        )
        in result["blocks"]
    )
    assert (
        next(f.value for f in result["facts"] if f.label_en == "Undated cancellations")
        == 0
    )


def test_required_published_bulk_months_are_served():
    result = run_churn(churn_rows())
    flags = {f.value for f in result["facts"] if f.unit == "calendar_month"}
    assert {"2020-07", "2022-06", "2024-09"} <= flags


@pytest.mark.parametrize("count,expected", [(29, "low_count"), (30, "standard")])
def test_churn_reliability_uses_active_stock(count, expected):
    data = churn_rows()
    data["pub_licence_active"][0]["active_count"] = count
    result = run_churn(data)
    local = [f for f in result["facts"] if f.geography["kind"] == "public"]
    assert local
    assert {f.reliability for f in local} == {expected}
