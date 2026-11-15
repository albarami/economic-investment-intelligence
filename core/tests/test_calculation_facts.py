"""Typed calculation boundary; the release owner supplies canonical fact IDs."""

import json
from dataclasses import replace
from decimal import Decimal as D
from pathlib import Path

import pytest
from result_types import fact_value

from eii_core.calc.facts import (
    NUMERIC_UNITS,
    CalculationFact,
    NoData,
    SourceChain,
    Suppressed,
    WithheldInput,
    compare_public_facts,
    least_real,
    order_changes,
)


def source():
    return SourceChain(
        "invented_lineage",
        "invented_table",
        "C20",
        "1",
        "invented_publisher",
        "invented_dataset",
        "https://example.org/invented",
        "invented_fixture",
        "2026-11-14",
        "a" * 64,
    )


def fact(value=120, period="2025-01", **kwargs):
    return CalculationFact(
        value=D(value),
        unit="count",
        metric_key="invented_metric",
        release_id="invented_release",
        geography="zone:invented_zone",
        geography_kind="public",
        period=period,
        input_classes=("public",),
        sources=(source(),),
        **kwargs,
    )


def test_invented_c20_fixture_row_is_read():
    row = json.loads(
        (Path(__file__).parent / "fixtures/methods/public_methods.json").read_text()
    )["invented"]["C20"]
    result = compare_public_facts(fact(row["before"]), fact(row["after"], "2025-02"))
    assert fact_value(result.difference) == D(30)
    assert fact_value(result.ratio) == D("1.25")
    assert fact_value(result.direction) == "higher"


def test_c20_numeric_comparisons_and_zero_baseline():
    result = compare_public_facts(fact(), fact(150, "2025-02"))
    assert result.difference.value == D(30)
    assert result.difference.unit == "count"
    assert result.ratio.value == D("1.25")
    assert result.ratio.unit == "ratio"
    assert result.direction.value == "higher"
    assert result.direction.unit == "direction"
    assert result.difference.sources == (source(),)
    zero = compare_public_facts(fact(0), fact(4, "2025-02"))
    assert zero.difference.value == D(4)
    assert zero.ratio == NoData("no_denominator")
    assert compare_public_facts(None, fact()).difference == NoData("missing_input")


@pytest.mark.parametrize("after,direction", [(100, "lower"), (120, "equal")])
def test_comparison_directions(after, direction):
    assert (
        compare_public_facts(fact(), fact(after, "2025-02")).direction.value
        == direction
    )


def test_c20_printed_order_no_ratio_last_and_ties():
    changes = [
        compare_public_facts(
            replace(fact(), metric_key=key),
            replace(fact(value, "2025-02"), metric_key=key),
        )
        for key, value in [("a", 126), ("b", 108), ("c", 150)]
    ]
    ordered = order_changes(changes)
    assert [c.ratio.value for c in ordered] == [D("1.25"), D(".90"), D("1.05")]
    zero = compare_public_facts(fact(0), fact(4, "2025-02"))
    assert order_changes([zero, *changes])[-1] == zero
    tied = [replace(changes[0], metric_key="z"), replace(changes[0], metric_key="a")]
    assert [c.metric_key for c in order_changes(tied)] == ["a", "z"]


@pytest.mark.parametrize(
    "field,value",
    [
        ("unit", "qar"),
        ("metric_key", "different"),
        ("release_id", "different"),
        ("period", "2025-03"),
        ("geography", "different"),
        ("input_classes", ("synthetic",)),
    ],
)
def test_incompatible_comparison_refused(field, value):
    with pytest.raises(ValueError):
        compare_public_facts(fact(), replace(fact(150, "2025-02"), **{field: value}))


def test_two_areas_one_month_and_inferred_status():
    result = compare_public_facts(
        replace(fact(), geography_kind="public"),
        replace(
            fact(150),
            geography="zone:invented_other",
            geography_kind="public",
            evidence_status="inferred",
        ),
    )
    assert result.difference.value == D(30)
    assert result.difference.evidence_status == "inferred"
    assert result.before_geography == "zone:invented_zone"
    assert result.after_geography == "zone:invented_other"
    assert result.difference.base_geography == "zone:invented_zone"
    assert result.difference.geography == "zone:invented_other"


def test_provenance_is_computed_and_cannot_be_supplied():
    # Literals, not the rank formula: simulated is less real than public or synthetic.
    assert least_real(("public", "synthetic", "user_input")) == "synthetic"
    assert least_real(("simulated", "public", "synthetic")) == "simulated"
    assert least_real(("public", "public")) == "public"
    assert (
        replace(fact(), input_classes=("public", "simulated")).provenance == "simulated"
    )
    with pytest.raises(TypeError):
        fact(provenance="public")
    with pytest.raises(TypeError):
        from eii_core.calc.facts import emit

        emit(
            D(1),
            unit="count",
            places=0,
            metric_key="m",
            release_id="r",
            geography="g",
            geography_kind="public",
            period="2025-01",
            inputs=(),
            provenance="public",
        )
    with pytest.raises(ValueError):
        least_real(("unknown",))
    with pytest.raises(ValueError):
        least_real(("user_input",))


@pytest.mark.parametrize(
    "field,value",
    [
        ("value", None),
        ("value", D("NaN")),
        ("value", D("1.5")),
        ("unit", "unknown"),
        ("evidence_status", "Not measured"),
        ("sources", ()),
        ("metric_key", ""),
    ],
)
def test_invalid_fact_cells(field, value):
    with pytest.raises(ValueError):
        replace(fact(), **{field: value})


@pytest.mark.parametrize(
    "field",
    [
        "lineage_ref",
        "table",
        "method",
        "version",
        "publisher",
        "dataset",
        "url",
        "licence",
        "retrieved",
        "sha256",
    ],
)
def test_missing_chain_link_refused(field):
    with pytest.raises(ValueError):
        replace(source(), **{field: ""})


def test_unknown_fact_field_and_user_input_status():
    with pytest.raises(TypeError):
        fact(unknown="bad")
    with pytest.raises(ValueError):
        replace(fact(), input_classes=("public", "user_input"))


def test_annual_adjacency_and_missing_sides():
    assert compare_public_facts(
        fact(period="2024"), fact(150, "2025")
    ).ratio.value == D("1.25")
    with pytest.raises(ValueError):
        compare_public_facts(fact(period="2023"), fact(150, "2025"))
    with pytest.raises(ValueError):
        compare_public_facts(fact(period="2024"), fact(150, "2025-01"))
    assert compare_public_facts(fact(), None).metric_key == "invented_metric"
    with pytest.raises(ValueError):
        compare_public_facts(None, None)


@pytest.mark.parametrize(
    "unit",
    [
        "count",
        "qar",
        "qar_thousand",
        "qar_million",
        "qar_per_month",
        "qar_per_kg",
        "kwh",
        "ratio",
        "percent",
        "index",
        "riders",
    ],
)
def test_supported_numeric_units(unit):
    assert replace(fact(), unit=unit).unit == unit


@pytest.mark.parametrize("status", ["observed", "inferred", "still_to_test"])
def test_closed_evidence_statuses(status):
    assert replace(fact(), evidence_status=status).evidence_status == status


def test_comparison_keeps_the_weaker_status_and_both_chains():
    before = replace(fact(), evidence_status="still_to_test")
    after = fact(150, "2025-02")
    result = compare_public_facts(before, after)
    assert result.difference.evidence_status == "still_to_test"
    inferred_first = compare_public_facts(
        replace(fact(), evidence_status="inferred"), fact(150, "2025-02")
    )
    assert inferred_first.difference.evidence_status == "inferred"
    other = source()
    other = replace(other, lineage_ref="invented_other")
    chained = compare_public_facts(
        fact(), replace(fact(150, "2025-02"), sources=(other,))
    )
    assert chained.difference.sources == (source(), other)
    assert chained.difference.base_period == "2025-01"
    assert chained.difference.period == "2025-02"


def test_no_ratio_sorts_after_a_ratio_of_one_and_areas_need_one_month():
    one = compare_public_facts(
        replace(fact(), metric_key="zz"),
        replace(fact(120, "2025-02"), metric_key="zz"),
    )
    zero = compare_public_facts(fact(0), fact(4, "2025-02"))
    assert order_changes([zero, one])[-1] == zero
    with pytest.raises(ValueError):
        compare_public_facts(
            replace(fact(period="2025"), geography_kind="public"),
            replace(fact(150, "2025"), geography="zone:other", geography_kind="public"),
        )
    with pytest.raises(ValueError):
        compare_public_facts(
            replace(fact(), geography="zone:1", geography_kind="public"),
            replace(
                fact(150), geography="municipality:3", geography_kind="municipality"
            ),
        )


def test_withheld_value_is_suppressed_and_a_band_has_direction_only():
    withheld = WithheldInput(
        "invented_metric",
        "invented_release",
        "zone:invented_zone",
        "public",
        "2025-01",
        "count",
        "carried_forward",
        (source(),),
    )
    result = compare_public_facts(withheld, fact(150, "2025-02"))
    assert result.difference == Suppressed(
        "carried_forward", reasons=("carried_forward",)
    )
    assert result.ratio == Suppressed("carried_forward", reasons=("carried_forward",))
    assert result.direction == Suppressed(
        "carried_forward", reasons=("carried_forward",)
    )
    band = compare_public_facts(
        replace(fact(), unit="wage_band", value="B01", geography_kind="public"),
        replace(
            fact(),
            unit="wage_band",
            value="B02",
            geography="zone:other",
            geography_kind="public",
        ),
    )
    assert band.direction.value == "higher"
    assert not hasattr(band, "difference")
    assert not hasattr(band, "ratio")


def test_source_hash_date_and_closed_units():
    with pytest.raises(ValueError):
        replace(source(), sha256="g" * 64)
    with pytest.raises(ValueError):
        replace(source(), retrieved="2026-13-01")
    with pytest.raises(ValueError):
        replace(source(), licence="none")
    with pytest.raises(ValueError):
        replace(source(), url="?")
    with pytest.raises(ValueError):
        replace(fact(), metric_key="   ")
    with pytest.raises(ValueError):
        replace(fact(), sources=["not-a-tuple"])
    assert NUMERIC_UNITS == (
        "count",
        "qar",
        "qar_thousand",
        "qar_million",
        "qar_per_month",
        "qar_per_kg",
        "kwh",
        "ratio",
        "percent",
        "index",
        "riders",
    )


def test_display_ratio_is_rounded_once():
    result = compare_public_facts(fact(3), fact(10, "2025-02"))
    assert result.ratio.value == D("3.33")
    assert result.ratio_unrounded != result.ratio.value
    assert len(format(result.ratio.value, "f")) < 10
