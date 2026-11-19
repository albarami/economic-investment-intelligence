"""C30 exact application wording and the Part A component contract."""

import re
from copy import deepcopy
from pathlib import Path
from string import Formatter

import pytest
import yaml

from eii_product.assistant.catalogue import load_catalogue
from eii_product.assistant.catalogue.schema import Refusal

ROOT = Path(__file__).resolve().parents[1]
CATALOGUE = ROOT / "assistant/catalogue"
TEMPLATE = ROOT / "src/eii_product/assistant/templates/series_forecast.py"
PUBLIC = "Forecast of {series} for {period}: {value}, range {low} to {high}. In the backtest {x} of {y} past values fell inside the range that the other past errors gave; its error was {error}."
SYNTHETIC = "Forecast of this area's released {series} for {month}: {value}, range {low} to {high}. In the backtest {x} of {y} past values fell inside the range that the other past errors gave; its error was {error}. These released periods show the format, not Qatar."


def assert_sentence(text):
    assert text in (PUBLIC, SYNTHETIC)
    assert not re.search(
        r"\b(probability|confidence|likely|certain|will|chance|odds|coverage)\b", text
    )
    assert not any(c.isnumeric() for c in text)
    assert "rose between months" not in text
    assert "fell from the previous month" not in text


def test_exact_templates_and_placeholders():
    assert TEMPLATE.is_file(), "C30 application template is missing"
    from eii_product.assistant.templates import series_forecast as templates

    assert templates.PUBLIC_SENTENCE == PUBLIC
    assert templates.SYNTHETIC_SENTENCE == SYNTHETIC
    assert (
        templates.METHOD_LINE
        == "Method: {candidate}, chosen in code by backtest; source: {source}."
    )
    assert templates.NOT_ENOUGH_HISTORY == "not enough history"
    for text in (templates.PUBLIC_SENTENCE, templates.SYNTHETIC_SENTENCE):
        assert_sentence(text)
    assert {field for _, field, _, _ in Formatter().parse(PUBLIC) if field} == {
        "series",
        "period",
        "value",
        "low",
        "high",
        "x",
        "y",
        "error",
    }
    assert {field for _, field, _, _ in Formatter().parse(SYNTHETIC) if field} == {
        "series",
        "month",
        "value",
        "low",
        "high",
        "x",
        "y",
        "error",
    }
    assert templates.CAPTION_BINDINGS == (("x", "inside"), ("y", "tested"))


def component_contract(rows):
    by_key = {row["component_key"]: row for row in rows}
    for name, facts in (
        (
            "series_forecast_card",
            ("value", "low", "high", "error", "points", "inside", "tested"),
        ),
        (
            "series_forecast_chart",
            ("value", "low", "high", "error", "points", "inside", "tested"),
        ),
    ):
        assert name in by_key
        row = by_key[name]
        assert row["max_count"] == 1
        expected = {key: "fact_id" for key in facts} | {
            "low_clamped": "boolean",
            "high_clamped": "boolean",
        }
        assert {prop["name"]: prop["kind"] for prop in row["props"]} == expected
        assert len(row["props"]) == len(expected)


def test_components_load_and_match_contract():
    rows = yaml.safe_load((CATALOGUE / "components.yaml").read_text())["components"]
    component_contract(rows)
    loaded = load_catalogue(CATALOGUE)
    assert not isinstance(loaded, Refusal)
    for key in ("series_forecast_card", "series_forecast_chart"):
        component = loaded.find_component(key)
        assert component is not None
        assert component.max_count == 1
        assert all(prop.kind in ("fact_id", "boolean") for prop in component.props)


@pytest.mark.parametrize(
    "component,prop,change",
    [
        ("series_forecast_card", "points", "remove"),
        ("series_forecast_card", "low_clamped", "combined"),
        ("series_forecast_chart", "value", "remove"),
        ("series_forecast_chart", "low_clamped", "remove"),
        ("series_forecast_chart", "high_clamped", "remove"),
        ("series_forecast_card", "value", "raw"),
    ],
)
def test_component_plants(component, prop, change):
    rows = deepcopy(
        yaml.safe_load((CATALOGUE / "components.yaml").read_text())["components"]
    )
    assert any(row["component_key"] == component for row in rows)
    row = next(row for row in rows if row["component_key"] == component)
    item = next(item for item in row["props"] if item["name"] == prop)
    if change == "remove":
        row["props"].remove(item)
    elif change == "combined":
        item["name"] = "clamped"
    else:
        item["kind"] = "number"
    with pytest.raises(AssertionError):
        component_contract(rows)


@pytest.mark.parametrize(
    "text",
    [
        "probability",
        "confidence",
        "likely",
        "certain",
        "will",
        "chance",
        "odds",
        "rose between months",
        "fell from the previous month",
        "coverage",
        "1",
    ],
)
def test_wording_plants(text):
    with pytest.raises(AssertionError):
        assert_sentence(PUBLIC + " " + text)
    assert_sentence(PUBLIC)
