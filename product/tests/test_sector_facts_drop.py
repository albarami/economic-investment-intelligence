"""DAT-90/94 final assembly plants, reached through the complete tool."""

from decimal import Decimal

import pytest
from product.tests.sector_fixture import release_store, with_lineage

from eii_product.tools import sector_facts as module


@pytest.mark.parametrize(
    "plant",
    [
        "fraction",
        "null",
        "unresolved",
        "hash",
        "mixed",
        "size",
        "month_range",
        "month_width",
    ],
)
def test_whole_response_drops_invalid_fact_and_keeps_siblings(monkeypatch, plant):
    data = with_lineage(
        {
            "pub_trade_wr": [
                dict(
                    trade_type="SYN-a",
                    period="2025",
                    indicator=indicator,
                    value=value,
                    unit="count",
                    source_id="SYN-pub_trade_wr",
                )
                for indicator, value in (("purchases", 2), ("sales", 3))
            ]
        }
    )
    original = module.Context.block
    kept = []
    rejected = []

    def plant_at_assembly(self, name, values, status="NO_DATA", reason=None):
        if name != "market_context":
            return original(self, name, values, status, reason)
        bad, sibling = values
        assert bad is not None and sibling is not None
        kept.append(sibling)
        updates = {
            "fraction": {"value": Decimal("2.5")},
            "null": {"value": None},
            "mixed": {"geography": {"kind": "national", "public_code": "zone:SYN-a"}},
            "size": {"unit": "size_band", "value": "SYN-unknown"},
            "month_range": {"unit": "calendar_month", "value": "2024-13"},
            "month_width": {"unit": "calendar_month", "value": "2024-9"},
        }
        if plant in {"unresolved", "hash"}:
            ref = "lin_pub_trade_wr_broken"
            lines, sources = self.chains[bad.lineage_ref]
            lines = [dict(line, lineage_id=ref) for line in lines]
            sources = (
                [] if plant == "unresolved" else [dict(s, sha256="") for s in sources]
            )
            self.chains[ref] = (lines, sources)
            update = {"lineage_ref": ref}
        else:
            update = updates[plant]
        bad = bad.model_copy(update=update)
        rejected.append(bad.fact_id)
        original(self, name, [bad, sibling], status, reason)
        original(self, "SYN-invalid-only", [bad], reason="too_few_licences")

    monkeypatch.setattr(module.Context, "block", plant_at_assembly)
    with release_store(data) as store:
        result = module.sector_facts(
            store, dict(activity="SYN-a", topic="market_context", geography="national")
        )
    assert result["facts"] == kept
    assert result["status"] == "OK"
    assert result["blocks"] == [
        dict(
            block="market_context",
            status="OK",
            fact_ids=[kept[0].fact_id],
            reason_key={
                "unresolved": "source_missing",
                "hash": "source_hash_missing",
            }.get(plant, "fact_invalid"),
        ),
        dict(
            block="SYN-invalid-only",
            status="NO_DATA",
            fact_ids=[],
            reason_key={
                "unresolved": "source_missing",
                "hash": "source_hash_missing",
            }.get(plant, "fact_invalid"),
        ),
    ]
    assert all(fact_id not in repr(result) for fact_id in rejected)


@pytest.mark.parametrize("bad_month", ["2024-13", "2024-9"])
@pytest.mark.parametrize("sibling", [True, False])
def test_invalid_flagged_month_is_dropped_without_repair(
    monkeypatch, bad_month, sibling
):
    months = (bad_month, "2024-09") if sibling else (bad_month,)
    data = with_lineage(
        {
            "pub_licence_cancelled": [
                dict(
                    municipality_code="SYN-local",
                    activity_code="SYN-a",
                    period=month,
                    cancelled_count=1,
                    bulk_month=True,
                    source_id="SYN-pub_licence_cancelled",
                )
                for month in months
            ]
        }
    )
    monkeypatch.setattr(module, "bulk_months", lambda totals: months)
    with release_store(data) as store:
        result = module.sector_facts(
            store,
            dict(activity="SYN-a", topic="churn", geography="municipality:SYN-local"),
        )
    assert [f.value for f in result["facts"]] == (["2024-09"] if sibling else [])
    assert bad_month not in repr(result)
    block = next(b for b in result["blocks"] if b["block"] == "bulk_months")
    assert block == dict(
        block="bulk_months",
        status="OK" if sibling else "NO_DATA",
        fact_ids=[f.fact_id for f in result["facts"]],
    )
