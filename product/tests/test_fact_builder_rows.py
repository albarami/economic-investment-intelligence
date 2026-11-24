"""Survivor regressions for release identity and calculation provenance."""

from dataclasses import replace
from decimal import Decimal

import pytest
from product.tests.sector_fixture import IDENTITY, licence_rows, with_lineage

from eii_core.calc.facts import CalculationFact, SourceChain
from eii_product.tools import fact_builder as module
from eii_product.tools.fact_builder import build_calculated, build_published


def builder_inputs():
    data = with_lineage(licence_rows())
    line = data["fact_lineage"][0]
    source = data["source_registry"][0]
    link = SourceChain(
        line["lineage_id"],
        line["table_name"],
        "eii_core.calc.fixture",
        "v1",
        source["publisher"],
        source["title"],
        source["url"],
        source["licence"],
        str(source["retrieved_on"]),
        source["sha256"],
    )
    result = CalculationFact(
        Decimal(12),
        "count",
        "active_count",
        IDENTITY,
        "national",
        "2025",
        ("public",),
        (link,),
        geography_kind="national",
    )
    kwargs = dict(
        release_id=IDENTITY,
        lineage_ref=line["lineage_id"],
        lineage_rows=[line],
        source_rows=[source],
        qualifiers={},
    )
    return result, kwargs


def test_published_identity_includes_release(monkeypatch):
    original = module.fact_id
    seen = []

    def record(**arguments):
        seen.append(arguments)
        return original(**arguments)

    monkeypatch.setattr(module, "fact_id", record)
    _, kwargs = builder_inputs()
    fact = build_published(
        value=12,
        unit="count",
        metric_key="active_count",
        period="2025",
        geography={"kind": "national"},
        **kwargs,
    )
    assert fact is not None
    assert seen == [
        dict(
            release_id=IDENTITY,
            metric_key="active_count",
            geography={"kind": "national"},
            period="2025",
            qualifiers={},
        )
    ]


@pytest.mark.parametrize(
    "changes", [dict(evidence_status="inferred"), dict(input_classes=("synthetic",))]
)
def test_only_observed_public_calculations(changes):
    result, kwargs = builder_inputs()
    assert build_calculated(replace(result, **changes), **kwargs) is None


def test_numerator_table_must_match_even_with_same_source():
    result, kwargs = builder_inputs()
    kwargs["lineage_ref"] = "lin_pub_population_municipality"
    kwargs["lineage_rows"] = [
        dict(
            kwargs["lineage_rows"][0],
            lineage_id="lin_pub_population_municipality",
            table_name="pub_population_municipality",
        )
    ]
    assert build_calculated(result, **kwargs) is None


@pytest.mark.parametrize(
    "key,text",
    [
        ("base_period", "2020"),
        ("base_geography", "national"),
        ("base_geography_kind", "national"),
    ],
)
def test_matching_base_qualifier_is_retained(monkeypatch, key, text):
    original = module.build_published
    seen = []

    def record(**arguments):
        seen.append(arguments["qualifiers"])
        return original(**arguments)

    monkeypatch.setattr(module, "build_published", record)
    result, kwargs = builder_inputs()
    result = replace(result, **{key: text})
    kwargs["qualifiers"] = {key: text}
    fact = build_calculated(result, **kwargs)
    assert fact is not None
    assert seen == [{key: text}]
