"""Existing published FDI values keep units, fractional jobs and identity."""

import json
from decimal import Decimal

import pytest
from core.tests.test_facts_model import candidate

from eii_core.facts import Fact, fact_id


@pytest.mark.parametrize(
    "metric,unit,value",
    [
        ("fdi_capex", "usd_million", Decimal("12.5")),
        ("fdi_jobs", "announced_jobs", Decimal("12.5")),
        ("fdi_location", "decimal_degree", Decimal("1.25")),
        ("fdi_field", "calendar_year", "2025"),
    ],
)
def test_fdi_units_and_fields(metric, unit, value):
    identifier = fact_id(
        release_id="ab" * 32,
        metric_key=metric,
        geography={"kind": "public", "public_code": "feature:INVENTED-fdi"},
        period="2025",
        qualifiers={"field": "lat"},
    )
    fact = Fact.model_validate(
        candidate(
            fact_id=identifier, unit=unit, value=value, caveat_keys=["fdi_estimates"]
        )
    )
    assert fact.value == value and fact.unit == unit


@pytest.mark.parametrize("unit", ["usd_million", "announced_jobs", "decimal_degree"])
@pytest.mark.parametrize(
    "changes",
    [
        dict(provenance="synthetic", input_classes=["synthetic"]),
        dict(provenance="simulated", input_classes=["simulated"]),
        dict(evidence_status="inferred"),
        dict(reliability="standard"),
        dict(value=float("inf")),
        dict(value=True),
    ],
)
def test_fdi_numeric_guards(unit, changes):
    with pytest.raises(ValueError):
        Fact.model_validate(
            candidate(unit=unit, caveat_keys=["fdi_estimates"], **changes)
        )


@pytest.mark.parametrize("unit", ["usd_million", "announced_jobs"])
def test_announced_estimate_caveat_cannot_be_omitted(unit):
    with pytest.raises(ValueError, match="announced_estimate_unlabelled"):
        Fact.model_validate(candidate(unit=unit))


def test_latitude_and_longitude_have_distinct_identities():
    args = dict(
        release_id="ab" * 32,
        metric_key="fdi_location",
        geography={"kind": "public", "public_code": "feature:INVENTED-fdi"},
        period="2025",
    )
    assert fact_id(**args, qualifiers={"field": "lat"}) != fact_id(
        **args, qualifiers={"field": "lng"}
    )


@pytest.mark.parametrize(
    "unit,value",
    [("published_text", "2025"), ("calendar_year", "2025"), ("published_text", "7")],
)
def test_numeric_looking_published_string_survives_json_validation(unit, value):
    fact = Fact.model_validate_json(json.dumps(candidate(unit=unit, value=value)))
    assert type(fact.value) is str and fact.value == value
