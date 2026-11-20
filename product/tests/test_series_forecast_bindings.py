"""Closed catalogue declarations; no new renderer or canonical emitter."""

from copy import deepcopy
from pathlib import Path

import pytest
import yaml

from eii_product.assistant.catalogue.entries import _components
from eii_product.assistant.catalogue.schema import Refusal

CATALOGUE = Path(__file__).resolve().parents[1] / "assistant/catalogue/components.yaml"
FACTS = ("value", "low", "high", "error", "points", "inside", "tested")


def definitions():
    return yaml.safe_load(CATALOGUE.read_text())["components"]


@pytest.mark.parametrize("component", ["series_forecast_card", "series_forecast_chart"])
@pytest.mark.parametrize("missing", [*FACTS, "low_clamped", "high_clamped"])
def test_each_forecast_companion_and_clamp_required_at_catalogue_load(
    component, missing
):
    rows = definitions()
    row = next((row for row in rows if row["component_key"] == component), None)
    assert row is not None, "forecast declaration missing"
    row["props"] = [p for p in row["props"] if p["name"] != missing]
    result = _components(rows)
    assert isinstance(result, Refusal)
    assert result.rule_code == "FORECAST_COMPONENT"


def test_forecast_declarations_reject_raw_values_duplicates_and_extra_slots():
    rows = definitions()
    row = next((r for r in rows if r["component_key"] == "series_forecast_card"), None)
    assert row is not None, "forecast declaration missing"
    for props in (
        [*row["props"], {"name": "free_text", "kind": "fact_id"}],
        [*row["props"], row["props"][0]],
        [
            {"name": p["name"], "kind": "boolean"} if p["name"] == "value" else p
            for p in row["props"]
        ],
    ):
        changed = deepcopy(rows)
        next(r for r in changed if r["component_key"] == row["component_key"])[
            "props"
        ] = props
        result = _components(changed)
        assert isinstance(result, Refusal)
        assert result.rule_code == "FORECAST_COMPONENT"


def test_no_claim_or_http_route_impersonates_missing_release_reader(tmp_path):
    from eii_product.api.app import create_app
    from eii_product.assistant.catalogue import load_catalogue

    catalogue = load_catalogue(CATALOGUE.parent)
    assert not isinstance(catalogue, Refusal)
    assert not any("forecast" in claim.key for claim in catalogue.claims)
    app = create_app(tmp_path)
    paths = app.openapi()["paths"]
    assert "/tiles" in paths
    assert not any("forecast" in path for path in paths)


def layout_fixture():
    from eii_product.assistant.catalogue import load_catalogue
    from eii_product.assistant.catalogue.schema import ReturnedFact
    from eii_product.assistant.templates.series_forecast import FACT_BINDINGS

    facts = {}
    props = {"low_clamped": False, "high_clamped": False}
    for index, (name, metric) in enumerate(FACT_BINDINGS):
        # Keep every invented identity distinct, including the last companion.
        identity = "f_" + format(index, "032x")
        unit = (
            "count"
            if name in ("points", "inside", "tested")
            else "ratio"
            if name == "error"
            else "qar"
        )
        facts[identity] = ReturnedFact(
            identity,
            metric,
            unit,
            "2025",
            "public",
            "public",
            "inferred",
            "lin_fixture",
        )
        props[name] = identity
    return load_catalogue(CATALOGUE.parent), props, facts


@pytest.mark.parametrize(
    "field,wrong",
    [
        ("metric_key", "forecast_low"),
        ("period", "2024"),
        ("lineage_ref", "lin_other"),
        ("evidence_status", "observed"),
        ("provenance", "synthetic"),
        ("unit", "index"),
    ],
)
def test_forecast_layout_rejects_swapped_metric_or_foreign_companion(field, wrong):
    from dataclasses import replace

    from eii_product.assistant.catalogue.brief import _layout

    catalogue, props, facts = layout_fixture()
    layout = [{"component": "series_forecast_card", "props": props}]
    assert _layout(catalogue, layout, facts) is None
    changed = dict(facts)
    changed[props["value"]] = replace(changed[props["value"]], **{field: wrong})
    refusal = _layout(catalogue, layout, changed)
    assert isinstance(refusal, Refusal)
    assert refusal.rule_code == "FORECAST_BINDING"
