"""Independent parity inputs and lossless registry adapter contracts."""

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock, patch

from eii_product.store.normalise import Fact, ToolResult
from eii_product.store.parity import ParityCase
from eii_product.store.protocol import ReleaseStore
from eii_product.tools import registry
from eii_product.tools.make_area import (
    MakeAreaContext,
    MakeAreaResult,
    validate_request,
)
from eii_product.tools.sector_facts import Inputs


def test_area_cases_preserve_closed_arguments() -> None:
    cases = registry.parity_cases("a" * 64)
    assert cases == (
        ParityCase(
            "make_area",
            (("place_key", "SYN-pin"), ("mode", "walk"), ("cutoff", 5)),
        ),
        ParityCase(
            "make_area",
            (("place_key", "SYN-pin"), ("mode", "drive"), ("cutoff", 10)),
        ),
        ParityCase("make_area", (("shape_id", "a" * 64),)),
    )
    for case in cases:
        validate_request(dict(case.inputs), None)


def test_area_descriptor_preserves_result_envelope() -> None:
    store = Mock(spec=ReleaseStore, engine="embedded", release_id="SYN-release-area")
    context = Mock(spec=MakeAreaContext)
    payloads: list[bytes] = []
    result = MakeAreaResult("make_area", "OK", None, "SYN-release-area", None)
    inputs = {"shape_id": "a" * 64}
    with patch.object(registry, "make_area", return_value=result) as run:
        descriptor = registry.descriptor(context, payloads)
        actual = descriptor.run(store, inputs)
    run.assert_called_once_with(store, {"shape_id": "a" * 64}, context)
    assert descriptor.key == "make_area"
    assert descriptor.queries == (
        "make_area_grid_cells",
        "make_area_municipalities",
        "make_area_gazetteer_point",
    )
    assert actual == ToolResult(
        "embedded", "make_area", 0, "make_area", "OK", "SYN-release-area", ()
    )
    assert payloads == [b'{"payload":null,"reason":null,"status":"OK"}']


def test_sector_descriptor_preserves_result_and_fact_values() -> None:
    store = Mock(spec=ReleaseStore, engine="postgres", release_id="SYN-release-sector")
    # These are adapter doubles, not release facts or a provenance validation fixture.
    result = {
        "call_id": "SYN-call-sector",
        "status": "OK",
        "facts": [
            SimpleNamespace(fact_id="SYN-fact-count", unit="count", value=7),
            SimpleNamespace(
                fact_id="SYN-fact-share", unit="percent", value=Decimal("12.5")
            ),
            SimpleNamespace(
                fact_id="SYN-fact-label", unit="published_text", value="SYN-label"
            ),
        ],
    }
    inputs = {"activity": "561", "topic": "unit_economics", "geography": "national"}
    with patch.object(registry, "sector_facts", return_value=result) as run:
        descriptor = registry.sector_facts_descriptor()
        actual = descriptor.run(store, inputs)
    run.assert_called_once_with(
        store,
        {"activity": "561", "topic": "unit_economics", "geography": "national"},
    )
    assert descriptor.key == "sector_facts"
    assert set(descriptor.queries) == {
        "sector_facts_account_components",
        "sector_facts_account_employees",
        "sector_facts_accounts",
        "sector_facts_bulk_months",
        "sector_facts_census",
        "sector_facts_churn_dated_total",
        "sector_facts_churn_local",
        "sector_facts_churn_national",
        "sector_facts_churn_total",
        "sector_facts_employer_scale",
        "sector_facts_hotels",
        "sector_facts_licence_activity",
        "sector_facts_licence_local",
        "sector_facts_licence_municipality",
        "sector_facts_licence_national",
        "sector_facts_lineage",
        "sector_facts_market_context",
        "sector_facts_residents",
        "sector_facts_sources",
        "sector_facts_utility",
        "sector_facts_utility_national",
        "sector_facts_visitors",
        "sector_facts_wages",
    }
    assert actual == ToolResult(
        "postgres",
        "SYN-call-sector",
        0,
        "sector_facts",
        "OK",
        "SYN-release-sector",
        (
            Fact("SYN-fact-count", "count", 7),
            Fact("SYN-fact-share", "percent", Decimal("12.5")),
            Fact("SYN-fact-label", "published_text", "SYN-label"),
        ),
    )


def test_sector_cases_preserve_every_topic_argument() -> None:
    cases = registry.sector_facts_parity_cases()
    assert tuple((case.tool, dict(case.inputs)) for case in cases) == (
        (
            "sector_facts",
            {"activity": "561", "topic": "unit_economics", "geography": "national"},
        ),
        (
            "sector_facts",
            {
                "activity": "SYN-restaurant",
                "topic": "licences",
                "geography": "municipality:SYN-local",
            },
        ),
        (
            "sector_facts",
            {
                "activity": "SYN-restaurant",
                "topic": "churn",
                "geography": "municipality:SYN-local",
            },
        ),
        (
            "sector_facts",
            {
                "activity": "SYN-restaurant",
                "topic": "zone_momentum",
                "geography": "national",
            },
        ),
        (
            "sector_facts",
            {
                "activity": "SYN-restaurant",
                "topic": "pay_decomposition",
                "geography": "national",
            },
        ),
        (
            "sector_facts",
            {
                "activity": "SYN-restaurant",
                "topic": "employer_scale",
                "geography": "municipality:SYN-local",
            },
        ),
        (
            "sector_facts",
            {
                "activity": "SYN-restaurant",
                "topic": "market_context",
                "geography": "national",
            },
        ),
        (
            "sector_facts",
            {
                "activity": "SYN-restaurant",
                "topic": "visitor_markets",
                "geography": "municipality:SYN-local",
            },
        ),
        (
            "sector_facts",
            {
                "activity": "SYN-restaurant",
                "topic": "trade",
                "geography": "national",
                "trade": {"flow": "SYN-M", "product_scope": "TOTAL"},
            },
        ),
    )
    for case in cases:
        Inputs.model_validate(dict(case.inputs))
