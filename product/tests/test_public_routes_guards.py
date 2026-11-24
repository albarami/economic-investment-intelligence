"""Structural guards for pass-1 API and exact-outline boundaries."""

import ast
from pathlib import Path

import pytest

API = Path(__file__).parents[1] / "src/eii_product/api"
OUTLINE = API.parent / "tools/area_outline.py"


def violations(text, name):
    tree = ast.parse(text)
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            modules = (
                [alias.name for alias in node.names]
                if isinstance(node, ast.Import)
                else [node.module or ""]
            )
            if any(module.startswith("eii_custodian") for module in modules):
                found.add("custodian")
            if name == "area_context.py" and any(
                module.split(".")[0]
                in {"socket", "urllib", "httpx", "httpx2", "requests"}
                for module in modules
            ):
                found.add("routing_network")
            if name == "area_outline.py" and any(
                module.startswith("shapely") for module in modules
            ):
                found.add("approximate_outline")
        if isinstance(node, ast.Call):
            if (
                isinstance(node.func, ast.Name)
                and node.func.id == "MakeAreaContext"
                and name != "area_context.py"
            ):
                found.add("context_constructor")
            if isinstance(node.func, ast.Attribute):
                if (
                    isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "logging"
                    and node.func.attr == "exception"
                ):
                    found.add("exception_log")
                if name == "area_outline.py" and node.func.attr in {
                    "buffer",
                    "bounds",
                    "envelope",
                }:
                    found.add("approximate_outline")
        if (
            isinstance(node, ast.Attribute)
            and name == "area_context.py"
            and node.attr == "environ"
        ):
            found.add("routing_environment")
        if name == "public_layers.py":
            if isinstance(node, ast.Constant) and (
                node.value == 1_000_000 or node.value == "1000000"
            ):
                found.add("route_floor")
            if isinstance(node, ast.Compare) and any(
                isinstance(value, ast.Constant) and type(value.value) in (int, float)
                for value in (node.left, *node.comparators)
            ):
                found.add("route_floor")
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if (
                node.value.lstrip()
                .upper()
                .startswith(("SELECT ", "INSERT ", "UPDATE ", "DELETE "))
            ):
                found.add("inline_sql")
            if name in {"public_layers.py", "tools.py"} and node.value.startswith(
                "band_"
            ):
                found.add("route_class")
    return found


def test_api_and_outline_sources():
    for path in [*API.glob("*.py"), OUTLINE]:
        assert violations(path.read_text(), path.name) == set(), path.name


@pytest.mark.parametrize(
    "name,text,code",
    [
        ("tools.py", "import eii_custodian", "custodian"),
        ("public_layers.py", "floor = 1_000_000", "route_floor"),
        ("public_layers.py", "baseline > 500", "route_floor"),
        ("tools.py", 'sql = "SELECT secret FROM hidden"', "inline_sql"),
        ("tools.py", 'key = "band_low"', "route_class"),
        ("tools.py", 'logging.exception("hidden")', "exception_log"),
        ("tools.py", "MakeAreaContext()", "context_constructor"),
        ("area_context.py", "import socket", "routing_network"),
        ("area_context.py", "from urllib import request", "routing_network"),
        ("area_context.py", "import os\nx = os.environ", "routing_environment"),
        (
            "area_outline.py",
            "from shapely.geometry import Point",
            "approximate_outline",
        ),
        ("area_outline.py", "shape.buffer(500)", "approximate_outline"),
    ],
)
def test_source_guard_plants(name, text, code):
    assert code in violations(text, name)
