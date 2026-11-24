"""Structural arithmetic fence; aliases and comprehensions share the same walk."""

import ast
from pathlib import Path

import pytest


def require_no_number_work(source):
    forbidden = {"sorted", "sort", "sum", "min", "max", "round", "len"}
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Name) and node.id in forbidden:
            raise AssertionError("number_work")
        if isinstance(node, ast.Attribute) and node.attr in forbidden:
            raise AssertionError("number_work")
        if isinstance(
            node,
            (ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.Mult, ast.Div, ast.Sub, ast.Pow),
        ):
            raise AssertionError("number_work")
        if isinstance(node, ast.Slice) and any(
            isinstance(value, ast.Constant) and type(value.value) is int
            for value in (node.lower, node.upper, node.step)
        ):
            raise AssertionError("number_work")


def test_handler_contains_no_number_work():
    require_no_number_work(
        Path("product/src/eii_product/tools/scan_places.py").read_text()
    )


@pytest.mark.parametrize(
    "plant",
    [
        "sorted(rows, key=lambda r: r.distance)",
        "confidence >= 0.7",
        "rows[:6]",
        "alias = sorted\nalias(rows)",
        "[x for x in rows if x.confidence >= 0.7]",
    ],
)
def test_scanner_plants(plant):
    with pytest.raises(AssertionError, match="number_work"):
        require_no_number_work(plant)


def test_foundation_inventory_requires_ruling():
    def require_foundations(absent, cleared):
        if set(absent) - set(cleared):
            raise ValueError("foundation_ruling_required")

    with pytest.raises(ValueError, match="foundation_ruling_required"):
        require_foundations(["provenance", "fact_schema"], [])
    require_foundations(["provenance", "fact_schema"], ["provenance", "fact_schema"])
