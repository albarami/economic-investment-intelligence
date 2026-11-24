"""Document 08 correction preserves the prior Reads row and covers all queries."""

import re

import pytest
from product.tests.sector_fixture import repository_path

from eii_product.store.registry import PACKAGED

EARLIER = set(
    "pub_sector_accounts pub_licence_active pub_licence_cancelled pub_zone_utility pub_wage_table pub_price_index pub_establishment_size pub_census_2015_municipality pub_trade_wr pub_hotels_municipality pub_visitor_markets pub_investqa_record fact_lineage source_registry".split()
)
POPULATION = {"pub_population_municipality", "pub_census_national"}


def check_reads(row):
    tables = set(re.findall(r"`([a-z0-9_]+)`", row))
    assert EARLIER | POPULATION <= tables
    assert {
        t.name
        for q in PACKAGED.queries
        if q.name.startswith("sector_facts_")
        for t in q.tables
    } <= tables


def reads_row():
    section = (
        repository_path("docs/08_BACKEND.md", __file__)
        .read_text()
        .split("\n`sector_facts`\n", 1)[1]
        .split("\n`supplier_lens`", 1)[0]
    )
    return next(line for line in section.splitlines() if line.startswith("| Reads |"))


def test_reads_row_correction():
    check_reads(reads_row())


@pytest.mark.parametrize(
    "table", ["pub_population_municipality", "pub_census_national", "pub_price_index"]
)
def test_reads_row_cannot_lose_a_table(table):
    with pytest.raises(AssertionError):
        check_reads(reads_row().replace("`" + table + "`", ""))
