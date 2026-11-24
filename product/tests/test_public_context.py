"""Fixed readers select centres; no live source or cache participates."""

from dataclasses import asdict, replace
from datetime import date
from decimal import Decimal as D

import pytest

from eii_core.calc.facts import NoData, SourceChain
from eii_core.facts import fact_id
from eii_core.shapes import canonical_ring
from eii_product.assistant.catalogue.brief import _layout
from eii_product.assistant.catalogue.entries import _claim, _claims
from eii_product.assistant.catalogue.load import catalogue_directory, load_catalogue
from eii_product.assistant.catalogue.schema import (
    Component,
    FieldSpec,
    Refusal,
    ReturnedFact,
)
from eii_product.tools.area_outline import CircleOutline, PolygonOutline
from eii_product.tools.public_context import (
    read_night_lights,
    read_population_age_sex,
    read_venue_busyness,
)


def square(x0, y0, x1, y1):
    return PolygonOutline(
        canonical_ring(((y0, x0), (y0, x1), (y1, x1), (y1, x0), (y0, x0)))
    )


def slot_row(slot):
    return {**asdict(slot), "allowed_provenance": list(slot.allowed_provenance)}


RELEASE = "a" * 64
AREA = "ma1/" + "a" * 16 + "/polygon/" + "b" * 64


def chain(table):
    return SourceChain(
        "lin_" + table,
        table,
        "fixture",
        "v1",
        "Fixture publisher",
        "Invented source",
        "https://example.test/source",
        "Fixture terms",
        "2026-01-02",
        "a" * 64,
    )


def context(table):
    src = chain(table)
    return dict(
        source=src,
        release_id=RELEASE,
        lineage_rows=[
            dict(
                lineage_id=src.lineage_ref,
                table_name=table,
                transform="fixture.read@v1",
                input_class="public",
                source_id="fixture",
            )
        ],
        source_rows=[
            dict(
                source_id="fixture",
                publisher=src.publisher,
                title=src.dataset,
                licence=src.licence,
                url=src.url,
                sha256=src.sha256,
                retrieved_on=date.fromisoformat(src.retrieved),
            )
        ],
    )


def test_night_reader_centre_not_overlap():
    rows = [
        dict(cell=1, radiance=D(4), period="2024-01", source_id="ntl_blackmarble"),
        dict(cell=2, radiance=D(10), period="2024-01", source_id="ntl_blackmarble"),
        dict(cell=3, radiance=D(99), period="2024-01", source_id="ntl_blackmarble"),
    ]
    centres = {1: (0, 0), 2: (1, 1), 3: (3, 3)}
    result = read_night_lights(
        rows,
        centres=centres,
        area=square(0, 0, 1, 1),
        area_id=AREA,
        period="2024-01",
        **context("pub_night_lights"),
    )
    assert result.value == D(7)
    assert result.geography == {"kind": "area_shape", "area_id": AREA}
    assert (result.provenance, result.evidence_status) == ("public", "observed")
    assert read_night_lights(
        rows,
        centres=centres,
        area=square(5, 5, 6, 6),
        area_id=AREA,
        period="2024-01",
        **context("pub_night_lights"),
    ) == NoData("missing_input")


def pop_rows():
    return [
        dict(
            grid_key=key,
            lon=D(x),
            lat=D(y),
            age_band="20",
            sex=sex,
            people=D(value),
            period="2025",
            source_id="worldpop_qat_agesex",
        )
        for key, x, y, female, male in [
            ("g1", 0, 0, "10.4", "11.2"),
            ("g2", 1, 1, "12.3", "13.1"),
            ("g3", 2, 2, "30.0", "25.0"),
        ]
        for sex, value in [("female", female), ("male", male)]
    ]


def test_population_whole_cells_boundary_and_round_once():
    for sex, expected in [("female", D(23)), ("male", D(24)), (None, D(47))]:
        result = read_population_age_sex(
            pop_rows(),
            area=square(0, 0, 1, 1),
            area_id=AREA,
            period="2025",
            sex=sex,
            age_band="20",
            **context("pub_pop_agesex_grid"),
        )
        fact = result.fact
        assert fact.value == expected
        assert fact.evidence_status == "observed"
        assert fact.caveat_keys == ["calculated", "grid_cells_summed"]
    assert read_population_age_sex(
        pop_rows(),
        area=square(4, 4, 5, 5),
        area_id=AREA,
        period="2025",
        **context("pub_pop_agesex_grid"),
    ) == NoData("missing_input")


def test_planted_overlap_weight_and_broken_lineage():
    rows = pop_rows()
    rows[0]["overlap_weight"] = D("0.5")
    with pytest.raises(ValueError):
        read_population_age_sex(
            rows,
            area=square(0, 0, 1, 1),
            area_id=AREA,
            period="2025",
            **context("pub_pop_agesex_grid"),
        )
    kwargs = context("pub_pop_agesex_grid")
    kwargs["source_rows"] = []
    assert read_population_age_sex(
        pop_rows(), area=square(0, 0, 1, 1), area_id=AREA, period="2025", **kwargs
    ) == NoData("missing_input")


def test_busyness_row_dates_no_fallback():
    row = dict(
        place_id="fixture_venue",
        day_of_week="monday",
        hour=9,
        busyness_index=40,
        retrieved_on="2026-01-01",
        provider_updated_on=None,
        source_id="busy_besttime",
    )
    kwargs = context("pub_venue_busyness")
    result = read_venue_busyness(
        [row], place_id="fixture_venue", day="monday", hour=9, **kwargs
    )
    assert result.fact.value == D(40)
    assert result.fact.label_en == "BestTime relative busyness"
    assert result.fact.geography == {
        "kind": "public",
        "public_code": "place:fixture_venue",
    }
    assert (
        result.retrieved_on == "2026-01-01"
    )  # deliberately differs from registry date
    assert result.lineage.retrieved_on == "2026-01-01"
    assert result.lineage.lineage_ref == result.fact.lineage_ref
    assert result.lineage.source.retrieved == "2026-01-02"
    assert result.provider_updated_on is None
    assert result.hour == 9
    absent = read_venue_busyness(
        [],
        place_id="fixture_venue",
        day="monday",
        hour=9,
        coverage_reasons={"fixture_venue": "no_forecast"},
        **kwargs,
    )
    assert absent.reason == "no_forecast"
    assert absent.fact == NoData("missing_input")
    for place, hour in [("fixture_other", 9), ("fixture_venue", 10)]:
        missing = read_venue_busyness(
            [row], place_id=place, day="monday", hour=hour, **kwargs
        )
        assert missing.fact == NoData("missing_input")
    row["retrieved_on"] = None
    assert read_venue_busyness(
        [row], place_id="fixture_venue", day="monday", hour=9, **kwargs
    ).fact == NoData("missing_input")


def test_catalogue_families_and_plants():
    catalogue = load_catalogue(catalogue_directory())
    assert not isinstance(catalogue, Refusal)
    for family, caveat in [
        ("night_lights", "night_lights_not_activity"),
        ("venue_busyness", "relative_busyness_not_people"),
        ("population_age_sex", "grid_cells_summed"),
    ]:
        claim = catalogue.find_claim(family)
        assert claim is not None
        assert claim.section == "observed"
        assert caveat in claim.required_caveat_keys
        assert catalogue.find_component(family) is not None
        assert catalogue.find_fragment(caveat) is not None
        assert set(dict(claim.fields)) == {"template_en", "template_ar"}
    # A context claim cannot acquire another slot or become a rank criterion.
    claim = catalogue.find_claim("population_age_sex")
    row = dict(
        claim_key=claim.key,
        section=claim.section,
        subject=claim.subject,
        slots=[slot_row(slot) for slot in claim.slots],
        required_caveat_keys=list(claim.required_caveat_keys),
        required_companions=[],
        strengths_allowed=list(claim.strengths_allowed),
        **dict(claim.fields),
    )
    assert not isinstance(_claim(row, "claims[0]", claim.key), Refusal)
    row["slots"].append(
        {
            **row["slots"][0],
            "name": "rank",
            "metric_key": "sites_hold_runs",
            "breakdown": "none",
        }
    )
    assert isinstance(_claim(row, "claims[0]", claim.key), Refusal)
    slot = replace(
        claim.slots[0],
        metric_key="venue_busyness_index",
        unit="relative_index",
        breakdown="none",
    )
    row["slots"] = [slot_row(slot)]
    assert isinstance(_claim(row, "claims[0]", claim.key), Refusal)


def test_planted_violation_busyness_shared_and_population_chart():
    catalogue = load_catalogue(catalogue_directory())
    assert not isinstance(catalogue, Refusal)
    for family, metric, unit in [
        ("venue_busyness", "venue_busyness_index", "relative_index"),
        ("population_age_sex", "population_grid_people", "count"),
    ]:
        fact = ReturnedFact(
            "f_" + "a" * 32,
            metric,
            unit,
            "2025",
            "area_shape",
            "public",
            "observed",
            "lin_fixture",
        )
        mixed = Component("fixture_chart", 1, (FieldSpec("value", "fact_id"),))
        planted = replace(catalogue, components=(*catalogue.components, mixed))
        assert (
            _layout(
                planted,
                [{"component": "fixture_chart", "props": {"value": fact.fact_id}}],
                {fact.fact_id: fact},
            )
            is not None
        )
        claim = catalogue.find_claim(family)
        rows = [
            dict(
                claim_key=family,
                section="observed",
                subject=claim.subject,
                slots=[slot_row(s) for s in claim.slots],
                required_caveat_keys=list(claim.required_caveat_keys),
                required_companions=[],
                strengths_allowed=list(claim.strengths_allowed),
                **dict(claim.fields),
            )
        ]
        assert not isinstance(_claims(rows), Refusal)
        rows[0]["slots"].append(
            dict(
                name="people",
                metric_key="present_by_pay_band",
                unit="count",
                geography_role="area_shape",
                period_rule="calendar_year",
                allowed_provenance=["simulated"],
                breakdown="none",
            )
        )
        assert isinstance(_claims(rows), Refusal)


def test_population_is_not_a_ranking_question_input():
    from eii_product.assistant.catalogue.entries import _questions

    catalogue = load_catalogue(catalogue_directory())
    claim = catalogue.find_claim("population_age_sex")
    row = dict(
        question_key="fixture_rank",
        playbook="rank_areas",
        personas=["local"],
        slots=[slot_row(replace(claim.slots[0], breakdown="none"))],
        template_en="Compare {value}",
        template_ar="قارن {value}",
    )
    assert isinstance(_questions([row]), Refusal)


def test_busyness_binding_serializes_reader_qualifiers_unchanged():
    result = read_venue_busyness(
        [
            dict(
                place_id="fixture_venue",
                day_of_week="monday",
                hour=9,
                busyness_index=40,
                retrieved_on="2026-01-01",
                provider_updated_on=None,
                source_id="busy_besttime",
            )
        ],
        place_id="fixture_venue",
        day="monday",
        hour=9,
        **context("pub_venue_busyness"),
    )
    wire = result.binding.wire()
    assert wire["qualifiers"] == {"day_of_week": "monday", "hour": "9"}
    assert result.fact.fact_id == fact_id(
        release_id=RELEASE,
        metric_key="venue_busyness_index",
        geography=result.fact.geography,
        period=result.fact.period,
        qualifiers=wire["qualifiers"],
    )
    assert wire["fact"] == result.fact.model_dump(mode="json")
    assert wire["metricKey"] == "venue_busyness_index"
    assert wire["presentation"] == "ordinary"


@pytest.mark.parametrize(
    "sex,age_band", [("female", "20"), (None, None), (None, "20"), ("male", None)]
)
def test_population_binding_serializes_reader_qualifiers_unchanged(sex, age_band):
    result = read_population_age_sex(
        pop_rows(),
        area=square(0, 0, 1, 1),
        area_id=AREA,
        period="2025",
        sex=sex,
        age_band=age_band,
        **context("pub_pop_agesex_grid"),
    )
    wire = result.wire()
    assert wire["qualifiers"] == {"age_band": age_band or "all", "sex": sex or "none"}
    assert result.fact.fact_id == fact_id(
        release_id=RELEASE,
        metric_key="population_grid_people",
        geography=result.fact.geography,
        period=result.fact.period,
        qualifiers=wire["qualifiers"],
    )
    assert wire["fact"] == result.fact.model_dump(mode="json")
    assert wire["metricKey"] == "population_grid_people"
    assert wire["presentation"] == "ordinary"


def test_circle_reader_cases():
    rows = [
        dict(cell=1, radiance=D(4), period="2024-01", source_id="ntl_blackmarble"),
        dict(cell=2, radiance=D(10), period="2024-01", source_id="ntl_blackmarble"),
    ]
    area = CircleOutline(D(0), D(0), 500)
    result = read_night_lights(
        rows,
        centres={1: (0, 0), 2: (1, 1)},
        area=area,
        area_id=AREA,
        period="2024-01",
        **context("pub_night_lights"),
    )
    assert result.value == D(4)
    pop = read_population_age_sex(
        pop_rows(),
        area=area,
        area_id=AREA,
        period="2025",
        **context("pub_pop_agesex_grid"),
    )
    assert pop.fact.value == D(22)
    empty = CircleOutline(D(5), D(5), 500)
    assert read_night_lights(
        rows,
        centres={1: (0, 0), 2: (1, 1)},
        area=empty,
        area_id=AREA,
        period="2024-01",
        **context("pub_night_lights"),
    ) == NoData("missing_input")
    assert read_population_age_sex(
        pop_rows(),
        area=empty,
        area_id=AREA,
        period="2025",
        **context("pub_pop_agesex_grid"),
    ) == NoData("missing_input")
