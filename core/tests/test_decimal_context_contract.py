"""D1: caller and process defaults cannot alter calculation representations."""

import dataclasses
import decimal
import json
import os
import subprocess
import sys
from fractions import Fraction
from pathlib import Path

import pytest
from method_rows import energy, measure, trade

from eii_core.calc import facts as f
from eii_core.calc import public_methods as m
from eii_core.calc import public_series as s
from eii_core.calc import sector_economics as e

D = decimal.Decimal


def representation(value):
    if isinstance(value, Fraction):
        return (value.numerator, value.denominator)
    if isinstance(value, D):
        with decimal.localcontext(capitals=1):
            return (str(value), tuple(value.as_tuple()))
    if dataclasses.is_dataclass(value):
        return {
            field.name: representation(getattr(value, field.name))
            for field in dataclasses.fields(value)
        }
    if isinstance(value, dict):
        return {key: representation(cell) for key, cell in value.items()}
    if isinstance(value, (tuple, list)):
        return tuple(representation(cell) for cell in value)
    if isinstance(value, frozenset):
        return tuple(sorted(value))
    return value


def battery():
    before = {
        "invented": (measure(1, period="2020"), measure(3, "qar_per_month", "2020"))
    }
    after = {
        "invented": (measure(1, period="2021"), measure(4, "qar_per_month", "2021"))
    }
    months = tuple(f"2025-{month:02}" for month in range(1, 13))
    calendar = tuple(f"{2015 + i // 12}-{i % 12 + 1:02}" for i in range(125))

    def national(n):
        return measure(n, geography="national", kind="national")

    def emitted(value, period):
        return f.emit(
            D(value),
            unit="ratio",
            places=2,
            metric_key="invented",
            release_id="invented",
            geography="municipality:invented_muni",
            geography_kind="public",
            period=period,
            inputs=(measure(1, period=period),),
        )

    calls = {
        "finite": lambda: s.finite(D(1)),
        "count": lambda: s.count(3),
        "rounded": lambda: s.rounded(D("1.25"), 1),
        "rounded_subnormal": lambda: s.rounded(D(0), 60),
        "ratio": lambda: s.ratio(D(1), D(3)),
        "growth": lambda: s.growth(D(3), D(4)),
        "weighted_mean": lambda: s.weighted_mean({"invented": (D(3), D(7))}),
        "decomposition": lambda: s.decomposition(before, after),
        "unit_value": lambda: s.unit_value([(D(1), D(3), "kg")]),
        "bulk_months": lambda: s.bulk_months({"2020-01": D(7)}),
        "least_real": lambda: f.least_real(("public", "synthetic")),
        "weakest_evidence": lambda: f.weakest_evidence(("observed", "inferred")),
        "require_aligned": lambda: f.require_aligned((measure(1), measure(2))),
        "emit": lambda: emitted("1.25", "2020"),
        "compare_public_facts": lambda: f.compare_public_facts(
            emitted("3", "2020"), emitted("4", "2021")
        ),
        "order_changes": lambda: f.order_changes(
            (f.compare_public_facts(emitted("3", "2020"), emitted("4", "2021")),)
        ),
        "wilson": lambda: m.wilson(1, 3),
        "reliability": lambda: m.reliability(3),
        "licence_density": lambda: m.licence_density(measure(1), measure(3)),
        "location_quotient": lambda: m.location_quotient(
            measure(10), measure(30), national(10), national(90)
        ),
        "licence_churn": lambda: m.licence_churn(
            measure(3), {}, {}, calendar, national(3), national(3)
        ),
        "coverage_share": lambda: m.coverage_share(measure(1), measure(3)),
        "supplier_metrics": lambda: m.supplier_metrics(
            [trade("invented", "invented", months[0], 1, 3)],
            ["invented"],
            months,
            months,
            reviewed=True,
        ),
        "zone_momentum": lambda: m.zone_momentum(
            [energy("invented", 2021, 1000000), energy("invented", 2025, 3000000)],
            energy("national", 2021, 3000000),
            energy("national", 2025, 7000000),
        ),
        "sector_norms": lambda: e.sector_norms(
            employees=measure(3),
            productivity=measure(7, "qar"),
            compensation_thousand=measure(1, "qar_thousand"),
            surplus_thousand=measure(1, "qar_thousand"),
            goods_percent=measure("1.25", "percent"),
            services_percent=measure("2.25", "percent"),
        ),
        "share_range": lambda: e.share_range([D("1.25"), D("2.25")]),
        "output_keys": lambda: e.output_keys({"invented": 1, "invented_unrounded": 1}),
        "bad_finite": lambda: s.finite(D("NaN")),
        "bad_count": lambda: s.count(-1),
        "bad_ratio": lambda: s.ratio(D(1), D(0)),
        "empty_mean": lambda: s.weighted_mean({}),
        "bad_wilson": lambda: m.wilson(2, 1),
        "bad_alignment": lambda: f.require_aligned(
            (measure(1), measure(1, period="2020"))
        ),
        "huge_round": lambda: s.rounded(D("1E60"), 0),
    }
    result = {}
    for name, call in calls.items():
        try:
            result[name] = representation(call())
        except Exception as error:
            result[name] = (type(error).__name__, str(error))
    return result


def hostile_contexts():
    first = decimal.Context(prec=1)
    for signal in first.traps:
        first.traps[signal] = True
    return (
        first,
        decimal.Context(prec=3, rounding=decimal.ROUND_FLOOR, Emin=-5, Emax=5),
        decimal.Context(prec=60, traps=[decimal.Inexact, decimal.Rounded]),
    )


@pytest.mark.parametrize("context", hostile_contexts())
def test_every_public_function_ignores_caller_context(context):
    expected = battery()
    with decimal.localcontext(context):
        actual = battery()
    assert actual == expected


@pytest.mark.parametrize("when", ["before", "after"])
def test_every_public_function_ignores_process_defaults(when):
    script = """
import decimal, json, sys

def alter():
    c = decimal.DefaultContext
    c.prec = 3
    c.rounding = decimal.ROUND_FLOOR
    c.Emin, c.Emax = -5, 5
    c.clamp, c.capitals = 1, 0
    c.traps[decimal.Clamped] = True
    c.traps[decimal.Rounded] = True
if sys.argv[1] == "before":
    alter()
from test_decimal_context_contract import battery
if sys.argv[1] == "after":
    alter()
print(json.dumps(battery(), sort_keys=True))
"""
    core = Path(__file__).resolve().parents[1]
    env = {
        **os.environ,
        "PYTHONPATH": os.pathsep.join((str(core / "src"), str(core / "tests"))),
    }

    def run(mode):
        result = subprocess.run(
            [sys.executable, "-c", script, mode],
            env=env,
            text=True,
            capture_output=True,
            check=True,
        )
        return json.loads(result.stdout)

    assert run(when) == run("unchanged")
