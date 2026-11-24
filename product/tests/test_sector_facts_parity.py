"""Declared tool/query parity coverage and embedded leg."""

import pytest
from product.tests.sector_fixture import (
    IDENTITY,
    SECTOR_INVENTORY,
    churn_rows,
    fixed_rows,
    licence_rows,
    licence_store,
    norm_rows,
    pay_rows,
    release_store,
    utility_rows,
    with_lineage,
)

from eii_product.store import QueryResult, StoreRefusal
from eii_product.store.parity import TracingStore, cover, run_parity
from eii_product.store.registry import PACKAGED
from eii_product.tools.registry import (
    sector_facts_descriptor,
    sector_facts_parity_cases,
)


def all_topic_rows():
    data = {}
    for part in (
        licence_rows(),
        pay_rows(),
        utility_rows(),
        norm_rows("561"),
        fixed_rows(),
    ):
        data.update(part)
    data["pub_licence_cancelled"] = churn_rows()["pub_licence_cancelled"]
    return with_lineage(data)


@pytest.mark.parametrize(
    "case", sector_facts_parity_cases(), ids=lambda c: dict(c.inputs)["topic"]
)
def test_individual_parity_case_runs_nonempty_on_embedded(case):
    descriptor = sector_facts_descriptor()
    seen = []
    with release_store(all_topic_rows()) as store:
        result = descriptor.run(TracingStore(store, seen), dict(case.inputs))
    assert result.status == "OK"
    assert result.facts
    assert result.tool == case.tool == "sector_facts"
    assert result.release_id == IDENTITY
    assert set(seen) <= set(descriptor.queries)
    assert len({f.name for f in result.facts}) == len(result.facts)
    assert all(f.name.startswith("f_") for f in result.facts)


class SecondEngineStandIn:
    """A delegation double for ownership guards, never PostgreSQL evidence."""

    engine = "postgres"

    def __init__(self, store):
        self.store = store
        self.release_id = store.release_id

    def fetch(self, query, params):
        return self.store.fetch(query, params)


def parity_guard(descriptor, cases):
    from eii_core.facts import UNITS

    with release_store(all_topic_rows()) as store:
        return run_parity(
            (store, SecondEngineStandIn(store)),
            (descriptor,),
            cases,
            SECTOR_INVENTORY,
            unit_precision=dict.fromkeys(UNITS, 0),
            round_fact=lambda value, places: value,
        )


def test_all_cases_execute_exact_owned_query_union():
    descriptor = sector_facts_descriptor()
    cases = sector_facts_parity_cases()
    result = parity_guard(descriptor, cases)
    assert result.coverage.passed
    for names in result.traces.values():
        assert (
            set(names)
            == set(descriptor.queries)
            == {q.name for q in SECTOR_INVENTORY.queries}
        )
    assert {dict(c.inputs)["topic"] for c in cases} == {
        "unit_economics",
        "licences",
        "churn",
        "pay_decomposition",
        "zone_momentum",
        "employer_scale",
        "market_context",
        "visitor_markets",
    }
    norms = next(c for c in cases if dict(c.inputs)["topic"] == "unit_economics")
    assert dict(norms.inputs) == dict(
        activity="561", topic="unit_economics", geography="national"
    )


@pytest.mark.parametrize("removed", range(8))
def test_removing_each_individual_case_loses_query_coverage(removed):
    cases = sector_facts_parity_cases()
    with pytest.raises(StoreRefusal, match="query not executed"):
        parity_guard(sector_facts_descriptor(), cases[:removed] + cases[removed + 1 :])


def test_ownership_and_missing_cases_are_refused():
    from dataclasses import replace

    descriptor = sector_facts_descriptor()
    with pytest.raises(StoreRefusal, match="tool case missing"):
        parity_guard(descriptor, ())
    with pytest.raises(StoreRefusal, match="query not owned"):
        parity_guard(replace(descriptor, queries=()), sector_facts_parity_cases())


def test_parity_declared_and_every_query_reachable():
    from eii_product.tools.registry import (
        sector_facts_descriptor,
        sector_facts_parity_cases,
    )

    DESCRIPTOR = sector_facts_descriptor()
    CASES = sector_facts_parity_cases()

    seen = set()

    class Recorder:
        release_id = IDENTITY
        engine = "embedded"

        def fetch(self, query, params):
            seen.add(query.name)
            if query.name == "sector_facts_licence_local":
                return QueryResult(
                    ("municipality_code", "activity_code", "period", "active_count"),
                    (("SYN-a", "SYN-a", "2025-05", 10),),
                )
            return QueryResult((), ())

    for case in CASES:
        DESCRIPTOR.run(Recorder(), dict(case.inputs))
    # Empty releases still fetch lineage for fixed reads; calculation queries may
    # need fixture rows to reach their source lookups, so exercise embedded too.
    with licence_store() as store:
        for case in CASES:
            DESCRIPTOR.run(store, dict(case.inputs))
    assert set(DESCRIPTOR.queries) == {
        q.name for q in PACKAGED.queries if q.name.startswith("sector_facts_")
    }
    assert seen == set(DESCRIPTOR.queries)
    with pytest.raises(StoreRefusal, match="tool case missing"):
        cover(
            tools=[DESCRIPTOR],
            cases=[],
            traces={"embedded": [], "postgres": []},
            identities={"embedded": IDENTITY, "postgres": IDENTITY},
            query_names=DESCRIPTOR.queries,
        )
