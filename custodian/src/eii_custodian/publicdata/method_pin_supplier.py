"""C5's same-run producer: reviewed basket selection, calculator, receipt pins."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from decimal import Decimal
from typing import TYPE_CHECKING, Any, cast

from eii_core.calc.facts import CalculationFact, Measure, NoData, SourceChain
from eii_core.calc.public_methods import TradeRow, supplier_metrics

from .assembly import AssemblyError
from .method_card_validation import _mapping
from .method_pin_rows import source_lineage, table_keys
from .series.baskets import ACTIVITIES, reviewed_inputs, tariff_digits

if TYPE_CHECKING:
    from .assembly_adapters import Production


def _trade_row(row: Mapping[str, Any], product: str, chain: SourceChain) -> TradeRow:
    value, weight = Decimal(str(row["value_qar"])), Decimal(str(row["weight_kg"]))
    period = str(row["period"])

    def measure(amount: Decimal, unit: str) -> Measure:
        return Measure(amount, unit, period, "national", "national", "public", (chain,))

    return TradeRow(
        product,
        str(row["origin_iso3"] or "not attributed to a country"),
        period,
        value,
        weight,
        "kg",
        measure(value, "qar"),
        measure(weight, "kg"),
    )


def _source_chain(build: Production, key: str) -> SourceChain:
    receipt = build.receipts[key]
    entry = next(entry for entry in build.entries if entry.key == key)
    return SourceChain(
        key,
        "pub_customs_import",
        "C5.supplier_metrics",
        "1",
        str(receipt["publisher"]),
        entry.slug,
        str(receipt["fetch_url"]),
        str(receipt["licence_id"]),
        str(receipt["retrieved_utc"])[:10],
        str(receipt["sha256"]),
    )


def _basket(build: Production) -> dict[str, dict[str, object]]:
    document = json.loads((build.review / "baskets.yaml").read_bytes())
    selected = [
        (activity + ":" + str(item["name"]), item)
        for activity in sorted(ACTIVITIES)
        for item in reviewed_inputs(document, activity)
    ]
    inputs = dict(selected)
    if len(inputs) != len(selected):
        raise AssemblyError("pin_c5_basket_duplicate")
    if not inputs:
        raise AssemblyError("pin_c5_basket_empty")
    return inputs


def _window_rows(
    build: Production, months: Sequence[str], source: str
) -> tuple[list[dict[str, Any]], SourceChain, tuple[str, ...]]:
    keys = table_keys(build, "pub_customs_import", source)
    if len(keys) != 1:
        raise AssemblyError("pin_customs_window_missing")
    source_lineage(build, keys, "C5.supplier_metrics@v1")
    width = 8 if source == "cus_imp_2019" else 12
    rows = [
        row
        for row in build.tables.get("pub_customs_import", [])
        if row["period"] in months
        and row["tariff_code"] is not None
        and len(row["tariff_code"]) == width
    ]
    if {row["period"] for row in rows} != set(months):
        raise AssemblyError("pin_customs_window_missing")
    return rows, _source_chain(build, keys[0]), keys


def _line_values(
    line: str,
    item: Mapping[str, object],
    settings: Mapping[str, object],
    old: Sequence[Mapping[str, Any]],
    new: Sequence[Mapping[str, Any]],
    old_chain: SourceChain,
    new_chain: SourceChain,
) -> dict[str, str]:
    included = {
        tariff_digits(row["code"]) for row in cast(list[dict[str, str]], item["lines"])
    }
    excluded = {
        tariff_digits(row["code"])[:8]
        for row in cast(list[dict[str, str]], item["excluded_lines"])
    }
    parents = {code[:8] for code in included}
    review = _mapping(_mapping(settings["lines"])[line])
    contaminated = bool(parents & excluded)
    if review.get("parent_contains_excluded") is not contaminated or review.get(
        "parent_treatment"
    ) not in (("includes excluded lines", "withheld") if contaminated else ("clean",)):
        raise AssemblyError("pin_c5_parent_review_mismatch")
    months, prior = (
        cast(list[str], settings["latest_months"]),
        cast(list[str], settings["prior_months"]),
    )
    result = supplier_metrics(
        [
            _trade_row(row, line, new_chain)
            for row in new
            if row["tariff_code"].startswith(tuple(included))
        ],
        (line,),
        months,
        (*prior, *months),
        reviewed=True,
        prior_rows=[
            _trade_row(row, line, old_chain)
            for row in old
            if row["tariff_code"] in parents
        ],
        prior_months=prior,
    )
    if isinstance(result, NoData):
        values = dict.fromkeys(
            ("hhi", "prior12", "latest12", "trend"), "NO_DATA:" + result.reason
        )
    else:
        values = _calculated_values(result)
    for pin in ("prior12", "trend"):
        if review["parent_treatment"] == "withheld":
            values[pin] = "NO_DATA:includes excluded lines"
        elif contaminated:
            values[pin] += ";caveat=includes excluded lines"
    return values


def _calculated_values(result: Mapping[str, object]) -> dict[str, str]:
    """Serialize exact calculator outputs; never round or recompute them."""
    hhi = cast(CalculationFact | NoData, result["hhi"])
    return {
        "hhi": "NO_DATA:" + hhi.reason
        if isinstance(hhi, NoData)
        else str(hhi.exact_unrounded),
        "prior12": str(result["prior_total_value_unrounded"]),
        "latest12": str(result["total_value_unrounded"]),
        "trend": str(result["trend_unrounded"])
        if result["trend_unrounded"] is not None
        else "NO_DATA:no_denominator",
    }


def c5_pin_rows(
    build: Production, settings_by_pin: Mapping[str, object]
) -> list[dict[str, object]]:
    settings = _mapping(settings_by_pin["c5.hhi"])
    basket = _basket(build)
    if set(_mapping(settings["lines"])) != set(basket) or any(
        settings_by_pin["c5." + pin] != settings
        for pin in ("prior12", "latest12", "trend")
    ):
        raise AssemblyError("pin_c5_settings_mismatch")
    old, old_chain, old_keys = _window_rows(
        build, cast(list[str], settings["prior_months"]), "cus_imp_2019"
    )
    new, new_chain, new_keys = _window_rows(
        build, cast(list[str], settings["latest_months"]), "cus_imp_2025"
    )
    values = {
        line: _line_values(line, item, settings, old, new, old_chain, new_chain)
        for line, item in basket.items()
    }
    return [
        {
            "pin_id": "c5." + pin,
            "values": {line: cells[pin] for line, cells in values.items()},
            "source_lineage": source_lineage(
                build,
                old_keys
                if pin == "prior12"
                else new_keys
                if pin in ("hhi", "latest12")
                else (*old_keys, *new_keys),
                "C5.supplier_metrics@v1",
            ),
        }
        for pin in ("hhi", "prior12", "latest12", "trend")
    ]
