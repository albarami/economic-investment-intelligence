"""Invented C36-C38 fixtures; no provider values or source files are read."""

from dataclasses import replace
from decimal import Decimal as D

import pytest

from eii_core.calc.facts import NoData, SourceChain, compare_public_facts
from eii_core.calc.public_context import (
    PopulationCell,
    RadianceCell,
    calc_night_lights,
    calc_population_age_sex,
    calc_venue_busyness,
)


def source(table="pub_night_lights"):
    return SourceChain(
        "lin_" + table,
        table,
        "fixture",
        "v1",
        "Fixture publisher",
        "Invented grid",
        "https://example.test/grid",
        "Fixture terms",
        "2026-01-02",
        "a" * 64,
    )


def test_night_lights_calc_mean():
    rows = [RadianceCell("c1", D(4)), RadianceCell("c2", D(10))]
    fact = calc_night_lights(rows, source(), "2024-01")
    assert fact.value == D(7)
    assert fact.unit == "radiance_nw_cm2_sr"
    assert calc_night_lights([], source(), "2024-01") == NoData("missing_input")
    assert calc_night_lights([RadianceCell("c1", None)], source(), "2024-01") == NoData(
        "missing_input"
    )
    with pytest.raises(ValueError, match="duplicate"):
        calc_night_lights([rows[0], rows[0]], source(), "2024-01")


def test_night_lights_metadata():
    fact = calc_night_lights([RadianceCell("c1", D(4))], source(), "2024-01")
    assert fact.provenance == "public"
    assert fact.evidence_status == "observed"
    assert fact.caveat_keys == ("calculated", "night_lights_not_activity")
    assert "grid_cells_summed" not in fact.caveat_keys
    assert "apportioned_from" not in fact.caveat_keys
    assert fact.sources == (source(),)


def test_busyness_format():
    src = source("pub_venue_busyness")
    for index in (D(40), D(100), D(0)):
        fact = calc_venue_busyness(index, src, "2026-01-01")
        assert fact.value == index
        assert fact.unit == "relative_index"
        assert fact.subject == "place_public"
        assert fact.retrieved_on == "2026-01-01"
        assert fact.caveat_keys == ("relative_busyness_not_people",)
        assert (fact.provenance, fact.evidence_status) == ("public", "observed")
    assert calc_venue_busyness(None, src, "2026-01-01") == NoData("missing_input")
    assert calc_venue_busyness(D(40), src, None) == NoData("missing_input")
    with pytest.raises(ValueError):
        calc_venue_busyness(D(101), src, "2026-01-01")


def population_rows():
    return [
        PopulationCell("g1", "adult", "female", D("10.4")),
        PopulationCell("g2", "adult", "female", D("12.3")),
        PopulationCell("g1", "adult", "male", D("11.2")),
        PopulationCell("g2", "adult", "male", D("13.1")),
    ]


def test_mth_111_fixture():
    rows, src = population_rows(), source("pub_pop_agesex_grid")
    assert calc_population_age_sex(rows[:2], src, "2025").value == D(23)
    assert calc_population_age_sex(rows[2:], src, "2025").value == D(24)
    fact = calc_population_age_sex(rows, src, "2025")
    assert fact.value == D(47)
    assert fact.caveat_keys == ("calculated", "grid_cells_summed")
    assert calc_population_age_sex([], src, "2025") == NoData("missing_input")
    # Rounding each cell first would produce two, rather than one.
    small = [
        PopulationCell("g1", "adult", "female", D("0.6")),
        PopulationCell("g2", "adult", "female", D("0.6")),
    ]
    assert calc_population_age_sex(small, src, "2025").value == D(1)
    with pytest.raises(ValueError, match="duplicate"):
        calc_population_age_sex([rows[0], rows[0]], src, "2025")


def test_planted_violation_population_overlap_weight():
    with pytest.raises(TypeError):
        PopulationCell("g1", "adult", "female", D(10), overlap_weight=D("0.5"))


def test_planted_violation_population_evidence_status():
    fact = calc_population_age_sex(
        population_rows(), source("pub_pop_agesex_grid"), "2025"
    )
    assert fact.evidence_status == "observed"
    with pytest.raises(TypeError):
        replace(fact, evidence_status="inferred")


def test_planted_violation_population_routing():
    fact = calc_population_age_sex(
        population_rows(), source("pub_pop_agesex_grid"), "2025"
    )
    # C38 is not a CalculationFact and is refused before generic comparison.
    with pytest.raises(TypeError):
        compare_public_facts(fact, fact)


def test_application_area_fact_cannot_admit_protected_or_simulated_data():
    from eii_core.facts import Fact

    base = dict(
        fact_id="f_" + "a" * 32,
        value=D(7),
        unit="radiance_nw_cm2_sr",
        period="2024-01",
        geography={
            "kind": "area_shape",
            "area_id": "ma1/" + "a" * 16 + "/polygon/" + "b" * 64,
        },
        provenance="public",
        input_classes=["public"],
        evidence_status="observed",
        reliability="not_applicable",
        coverage_keys=[],
        caveat_keys=["calculated", "night_lights_not_activity"],
        label_en="Night-time radiance",
        label_ar="الإشعاع الضوئي الليلي",
        lineage_ref="lin_pub_night_lights",
        release_id="a" * 64,
    )
    assert Fact(**base).value == D(7)
    for provenance in ("synthetic", "simulated"):
        with pytest.raises(ValueError):
            Fact(**{**base, "provenance": provenance, "input_classes": [provenance]})


@pytest.mark.parametrize("bad", [D("NaN"), D("-1"), D("Infinity")])
def test_invalid_values(bad):
    with pytest.raises(ValueError):
        calc_night_lights([RadianceCell("c1", bad)], source(), "2024-01")
    with pytest.raises(ValueError):
        calc_population_age_sex(
            [PopulationCell("g1", "adult", "male", bad)],
            source("pub_pop_agesex_grid"),
            "2025",
        )
