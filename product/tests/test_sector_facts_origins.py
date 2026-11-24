"""MTH-01 fixed tested Public reads, exact fields rather than derived values."""

from decimal import Decimal

import pytest
from product.tests.sector_fixture import fixed_rows, release_store, with_lineage

from eii_product.tools.sector_facts import sector_facts


@pytest.mark.parametrize(
    "topic,expected",
    [
        (
            "employer_scale",
            {
                ("2022", "Employees"): 37,
                ("2022", "Size class"): "s01_09",
                ("2015", "Establishments"): 53,
            },
        ),
        (
            "market_context",
            {
                ("2025", "Purchases"): Decimal("17.35"),
                ("2025", "Sales"): Decimal("41.73"),
            },
        ),
        (
            "visitor_markets",
            {
                ("2025", "Facilities"): 71,
                ("2025", "Arrivals"): 89,
                ("2025", "Guests"): 97,
            },
        ),
    ],
)
def test_every_fixed_number_comes_from_a_fixed_tested_read(topic, expected):
    with release_store(with_lineage(fixed_rows())) as store:
        result = sector_facts(
            store,
            dict(
                activity="SYN-restaurant",
                topic=topic,
                geography="municipality:SYN-local",
            ),
        )
    assert {(f.period, f.label_en): f.value for f in result["facts"]} == expected
    assert all("calculated" not in f.caveat_keys for f in result["facts"])
    for fact in result["facts"]:
        if fact.label_en in {"Facilities", "Establishments"}:
            assert fact.geography == {
                "kind": "public",
                "public_code": "municipality:SYN-local",
            }
        else:
            assert fact.geography == {"kind": "national"}
        if fact.period == "2015":
            assert "dated_census" in fact.caveat_keys
