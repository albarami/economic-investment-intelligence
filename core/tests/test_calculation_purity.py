"""MTH-01: fail closed on I/O, clock/random calls and decimal-context leakage."""

import ast
import builtins
import datetime
import importlib
import io
import random
import socket
import sqlite3
import statistics
import sys
import time
from copy import deepcopy
from decimal import ROUND_DOWN, Inexact, localcontext
from decimal import Decimal as D
from pathlib import Path
from types import ModuleType

import pytest
from method_rows import energy, measure, trade

from eii_core import classification
from eii_core.calc import (
    facts,
    public_methods,
    public_series,
    sector_economics,
)

MODULES = (
    *(
        importlib.import_module("eii_core.calc." + path.stem)
        for path in sorted(Path(facts.__file__).parent.glob("*.py"))
        if path.stem != "__init__"
    ),
    classification,
)
ALLOWED_IMPORTS = {
    "__future__",
    "collections.abc",
    "dataclasses",
    "datetime",
    "decimal",
    "fractions",
    "math",
    "functools",
    "typing",
    "re",
    "statistics",
    "building_heights",
    "public_series",
    "facts",
    "public_methods",
    "sector_economics",
}
REVIEWED_IMPORTS = {
    "eii_core.calc.firms_per_tower": {"CLASS_KEYS"},
    "itertools": {"pairwise"},
}
FORBIDDEN_CALLS = {
    "open",
    "read_text",
    "read_bytes",
    "write_text",
    "write_bytes",
    "connect",
    "socket",
    "time",
    "now",
    "today",
    "utcnow",
    "random",
    "samples",
    "NormalDist",
    "getcontext",
    "setcontext",
    "__import__",
    "eval",
    "exec",
    "getattr",
    "setattr",
    "vars",
    "globals",
    "locals",
    "__builtins__",
}


def _call_names(node: ast.AST) -> set[str]:
    found: set[str] = set()
    if isinstance(node, ast.Name):
        found.add(node.id)
    elif isinstance(node, ast.Attribute):
        found.add(node.attr)
        found |= _call_names(node.value)
    elif isinstance(node, ast.Subscript):
        found |= _call_names(node.value)
        found |= _call_names(node.slice)
    elif isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        for element in node.elts:
            found |= _call_names(element)
    elif isinstance(node, ast.Call):
        found |= _call_names(node.func)
    return found


def assert_pure(source, *, allow_datetime=False):
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Name):
            assert node.id not in {
                "getattr",
                "setattr",
                "vars",
                "globals",
                "locals",
                "eval",
                "exec",
                "__import__",
                "__builtins__",
            }
        if isinstance(node, ast.Import):
            assert all(alias.name in ALLOWED_IMPORTS for alias in node.names)
        if isinstance(node, ast.ImportFrom):
            if node.module in REVIEWED_IMPORTS:
                assert all(
                    alias.name in REVIEWED_IMPORTS[node.module] for alias in node.names
                )
            else:
                assert node.module in ALLOWED_IMPORTS
            if node.module == "datetime":
                assert allow_datetime
                assert all(alias.name == "date" for alias in node.names)
        if isinstance(node, ast.Call):
            names = _call_names(node.func)
            assert not names & FORBIDDEN_CALLS


def assert_calculation_directory(folder):
    for path in sorted(folder.rglob("*.py")):
        assert_pure(
            path.read_text(),
            allow_datetime=path
            in {
                folder / "facts.py",
                folder / "public_context.py",
                folder / "scan_places.py",
            },
        )


@pytest.mark.parametrize(
    "name,source",
    [
        ("new_calculation.py", 'def helper(): return open("invented")'),
        ("nested/facts.py", "from datetime import datetime"),
        ("new_calculation.py", "from datetime import date"),
        ("nested/facts.py", "from datetime import date"),
        ("nested/public_context.py", "from datetime import date"),
        ("nested/scan_places.py", "from datetime import date"),
    ],
)
def test_unlisted_calculation_module_is_checked(tmp_path, name, source):
    path = tmp_path / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source)
    with pytest.raises(AssertionError):
        assert_calculation_directory(tmp_path)


def test_purity_guard_and_planted_io_helper():
    assert_calculation_directory(Path(facts.__file__).parent)
    assert_pure(Path(classification.__file__).read_text())
    for plant in [
        'def helper():\n return open("invented")',
        "import os",
        "from itertools import count",
        "from eii_core.calc.firms_per_tower import unreviewed_helper",
        "from datetime import datetime",
        "from datetime import date; date.today()",
        "def helper():\n return getattr(clock, 'utc' + 'now')()",
        "def helper():\n return __builtins__['open']('invented')",
        "def helper():\n return clock.now()",
        "def helper():\n return datetime.utcnow()",
        "def helper():\n return [open][0]('/dev/null')",
        "def helper():\n return random.random()",
        "def helper():\n return NormalDist().samples(1)",
    ]:
        with pytest.raises(AssertionError):
            assert_pure(plant, allow_datetime=True)


def test_calls_and_imports_need_no_io_clock_or_random(monkeypatch):
    compiled = [
        (module, compile(Path(module.__file__).read_text(), module.__file__, "exec"))
        for module in MODULES
    ]

    def refuse(*args, **kwargs):
        raise AssertionError("calculation attempted external access")

    for owner, name in [
        (builtins, "open"),
        (io, "open"),
        (Path, "read_bytes"),
        (Path, "read_text"),
        (socket, "socket"),
        (sqlite3, "connect"),
        (time, "time"),
        (random, "random"),
        (datetime, "datetime"),
        (statistics, "NormalDist"),
    ]:
        monkeypatch.setattr(owner, name, refuse)
    # A planted helper proves the runtime guard is active.
    with pytest.raises(AssertionError, match="external access"):
        builtins.open("invented")
    for module, code in compiled:
        isolated = ModuleType(module.__name__)
        isolated.__package__ = module.__package__
        monkeypatch.setitem(sys.modules, module.__name__, isolated)
        exec(code, vars(isolated))
    for module in MODULES:
        monkeypatch.setitem(sys.modules, module.__name__, module)
    common = {"period": "2022", "geography": "national", "kind": "national"}
    assert public_methods.licence_density(measure(1), measure(10000)).value == 1
    assert public_methods.location_quotient(
        measure(10),
        measure(100),
        measure(10, geography="national", kind="national"),
        measure(1000, geography="national", kind="national"),
    )["value"].value == D(10)
    assert public_series.ratio(D(4), D(2)) == 2
    assert sector_economics.sector_norms(
        employees=measure(10, unit="count", **common),
        productivity=measure(100, unit="qar", **common),
        compensation_thousand=measure(1, unit="qar_thousand", **common),
        surplus_thousand=measure(0, unit="qar_thousand", **common),
        goods_percent=measure(20, unit="percent", **common),
        services_percent=measure(30, unit="percent", **common),
    )["compensation_percent"].value == D(100)
    assert facts.least_real(("public", "synthetic")) == "synthetic"
    assert facts.weakest_evidence(("observed", "inferred")) == "inferred"
    facts.require_aligned((measure(1), measure(2)))
    first = facts.emit(
        D(120),
        unit="count",
        places=0,
        metric_key="m",
        release_id="r",
        geography="municipality:invented_muni",
        geography_kind="public",
        period="2025-01",
        inputs=(measure(120, period="2025-01"),),
    )
    last = facts.emit(
        D(150),
        unit="count",
        places=0,
        metric_key="m",
        release_id="r",
        geography="municipality:invented_muni",
        geography_kind="public",
        period="2025-02",
        inputs=(measure(150, period="2025-02"),),
    )
    comparison = facts.compare_public_facts(first, last)
    assert comparison.ratio.value == D("1.25")
    assert facts.order_changes([comparison]) == (comparison,)
    assert public_methods.coverage_share(measure(3), measure(4))["percent"].value == 75
    public_methods.licence_churn(
        measure(10),
        {},
        {},
        tuple(f"{2015 + i // 12}-{i % 12 + 1:02}" for i in range(125)),
        measure(1, geography="national", kind="national"),
        measure(1, geography="national", kind="national"),
    )
    months = tuple(f"2025-{i:02}" for i in range(1, 13))
    public_methods.supplier_metrics(
        [trade("p", "o", months[0], 10, 2)], ["p"], months, months, reviewed=True
    )
    public_methods.zone_momentum(
        [energy("z", 2021, 1000000), energy("z", 2025, 2000000)],
        energy("national", 2021, 1),
        energy("national", 2025, 2),
    )
    public_methods.wilson(6, 28)
    assert public_methods.reliability(30) == "standard"
    public_series.finite(D(1))
    public_series.count(1)
    assert public_series.rounded(D("-2.5"), 0) == "-3"
    assert public_series.growth(D(4), D(5)) == 25
    public_series.weighted_mean({"a": (D(1), D(10))})
    public_series.decomposition(_wage_groups("2020"), _wage_groups("2025"))
    public_series.unit_value([(D(10), D(2), "kg")])
    public_series.bulk_months({"2015-01": D(1)})
    assert sector_economics.share_range([D(1), D(2)]) == (D(1), D(2))
    assert sector_economics.output_keys({"value": first}) == {"value"}


def _wage_groups(period: str) -> dict[str, tuple[object, object]]:
    return {
        "invented_b": (
            measure(1, period=period, geography="national", kind="national"),
            measure(
                30,
                period=period,
                geography="national",
                kind="national",
                unit="qar_per_month",
            ),
        ),
        "invented_a": (
            measure(3, period=period, geography="national", kind="national"),
            measure(
                10,
                period=period,
                geography="national",
                kind="national",
                unit="qar_per_month",
            ),
        ),
    }


def test_context_order_and_input_immutability():
    groups = _wage_groups("2020")
    original = deepcopy(groups)
    baseline = public_series.decomposition(groups, _wage_groups("2025"))
    interval = public_methods.wilson(6, 28)
    with localcontext() as context:
        context.prec = 6
        context.rounding = ROUND_DOWN
        context.traps[Inexact] = True
        assert (
            public_series.decomposition(
                dict(reversed(tuple(groups.items()))), _wage_groups("2025")
            )
            == baseline
        )
        assert public_methods.wilson(6, 28) == interval
    assert groups == original
