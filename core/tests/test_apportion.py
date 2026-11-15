"""C18 regressions and planted eligibility violations; invented fixtures only."""

from dataclasses import replace
from decimal import Decimal as D
from decimal import Inexact, Rounded, localcontext

import pytest

from eii_core.calc.apportion import (
    Lineage,
    Row,
    Weight,
    apportion,
    select_people_weight,
    validate_result,
)


def lineage(**changes):
    return replace(
        Lineage(
            "invented_source",
            "invented publisher",
            "invented page",
            "fixture-only",
            "2026-11-14",
            "a" * 64,
            "invented_method",
            "fixture-v1",
        ),
        **changes,
    )


def row(**changes):
    return replace(
        Row(
            "invented_G1",
            "official",
            "pub_building_permits",
            "building_permits",
            D(1000),
            D(100),
            D("12.5"),
            lineage(),
            lineage(source_id="invented_frame"),
        ),
        **changes,
    )


def grid(**changes):
    return replace(
        Weight(
            "worldpop_qat_2020",
            "public",
            True,
            "CC-BY-4.0",
            "dataset",
            True,
            True,
            lineage(source_id="worldpop_qat_2020"),
        ),
        **changes,
    )


def simulated(**changes):
    return row(
        table="presence_count",
        metric="presence_count",
        provenance="simulated",
        geography_kind="release_unit",
        value=D(120),
        low=D(110),
        high=D(130),
        area=D(2),
        intersection=D(1),
        **changes,
    )


def test_agesex_weight_is_refused():
    with pytest.raises(ValueError, match="weight"):
        select_people_weight(
            grid(
                source_id="worldpop_qat_agesex",
                lineage=lineage(source_id="worldpop_qat_agesex"),
            )
        )


def test_c18_area_example_and_lineage():
    rows = (
        row(),
        row(geography="invented_G2", value=D(600), area=D(20), intersection=D(5)),
    )
    result = apportion(rows, "invented_shape")
    assert (result.value, result.low, result.high) == (275, None, None)
    assert result.evidence_status == "inferred"
    assert result.provenance == "public"
    assert result.geography_kind == "area_shape"
    assert result.area_shape == "invented_shape"
    assert result.apportioned_from == ("invented_G1", "invented_G2")
    assert (result.method, result.method_version, result.caveat) == (
        "area",
        "C18-v1",
        "apportioned_estimate",
    )
    assert tuple(c.weight for c in result.contributions) == (D("0.125"), D("0.25"))
    assert tuple(c.row for c in result.contributions) == rows
    assert rows[0].value == 1000
    validate_result(result)


def test_c18_population_example():
    result = apportion(
        (
            row(
                metric="population",
                table="pub_population_municipality",
                value=D(20000),
                grid_total=D(4000),
                grid_intersection=D(1000),
            ),
        ),
        "invented_shape",
        grid(),
    )
    assert result.value == 5000
    assert result.method == "worldpop_qat_2020"
    assert result.weight_source == grid()


def test_c18_simulated_example():
    result = apportion(
        (
            simulated(),
            replace(
                simulated(),
                geography="invented_U2",
                value=D(80),
                low=D(72),
                high=D(88),
                area=D(4),
            ),
        ),
        "invented_shape",
    )
    assert (result.value, result.low, result.high) == (80, 73, 87)
    assert result.provenance == "simulated"
    assert result.apportioned_from == ("release_units",)


@pytest.mark.parametrize(
    "metric", ["population", "labour_force", "employed", "unemployed"]
)
def test_people_use_area_until_grid_confirmed(metric):
    result = apportion(
        (
            row(
                metric=metric,
                table="pub_population_municipality"
                if metric == "population"
                else "pub_labour_sex_municipality",
                split="total" if metric == "population" else "all_categories_total",
            ),
        ),
        "invented_shape",
    )
    assert result.value == 125
    assert result.method == "area"


@pytest.mark.parametrize(
    "changes",
    [
        {"licence_id": ""},
        {"licence_basis": "owner_decision"},
        {"file_confirmed": False},
        {"schema_confirmed": False},
        {"lineage": None},
        {"admitted": False},
        {"provenance": "protected"},
        {"provenance": "simulated"},
        {"source_id": "invented_other"},
    ],
)
def test_unconfirmed_or_ineligible_grid_refused(changes):
    with pytest.raises(ValueError, match="weight"):
        select_people_weight(grid(**changes))


@pytest.mark.parametrize("provenance", ["protected", "simulated"])
def test_area_weight_must_come_from_shape_or_frame(provenance):
    with pytest.raises(ValueError, match="weight"):
        select_people_weight(Weight(provenance=provenance))


@pytest.mark.parametrize(
    "changes",
    [
        {"metric": "unreviewed"},
        {"table": "employment"},
        {"table": "residence"},
        {"table": "business_register"},
        {"table": "wages"},
        {"table": "pub_pop_agesex_grid"},
        {"table": "presence_split"},
        {"table": "flow_split"},
        {"split": "sex"},
        {"split": "nationality"},
        {"split": "movement"},
        {"status": "suppressed"},
        {"status": "unreleased"},
        {"in_release": False},
        {"provenance": "protected"},
        {"provenance": "synthetic"},
        {"geography": ""},
        {"geography_kind": "area_shape"},
        {"lineage": lineage(method_version="")},
        {"lineage": lineage(source_id="")},
        {"geometry_lineage": lineage(sha256="")},
        {"geometry_origin": "protected"},
        {"geometry_origin": "simulated"},
        {"metric": "presence_count"},
    ],
)
def test_forbidden_input_refused(changes):
    result = apportion((row(**changes),), "invented_shape")
    assert result.status == "REFUSED"
    assert (result.value, result.low, result.high, result.contributions) == (
        None,
        None,
        None,
        (),
    )


@pytest.mark.parametrize(
    "field",
    [
        "source_id",
        "publisher",
        "page",
        "licence",
        "retrieved",
        "sha256",
        "method",
        "method_version",
    ],
)
def test_every_lineage_field_required(field):
    assert (
        apportion((row(lineage=lineage(**{field: ""})),), "invented_shape").status
        == "REFUSED"
    )


def test_total_over_all_public_categories_allowed():
    assert (
        apportion((row(split="all_categories_total"),), "invented_shape").value == 125
    )


@pytest.mark.parametrize(
    "metric", ["share", "rate", "mean", "median", "price", "index"]
)
def test_noncounts_preserve_values_and_extrema(metric):
    rows = (row(metric=metric, value=D("7.25")), row(metric=metric, value=D("2.75")))
    result = apportion(rows, "invented_shape")
    assert result.status == "UNBLENDED"
    assert result.originals == rows
    assert (result.low, result.high, result.value) == (D("2.75"), D("7.25"), None)
    assert result.contributions == ()
    assert result.area_shape == ""


@pytest.mark.parametrize(
    "changes", [{"area": D(0)}, {"grid_total": D(0), "grid_intersection": D(0)}]
)
def test_zero_denominator_no_data(changes):
    weight = grid() if "grid_total" in changes else Weight()
    r = row(metric="population", table="pub_population_municipality", **changes)
    assert apportion((r,), "invented_shape", weight).status == "NO_DATA"


def test_empty_input_no_data():
    assert apportion((), "invented_shape").status == "NO_DATA"


def test_incomplete_simulated_group_withholds_every_count():
    result = apportion((simulated(complete_group=False),), "invented_shape")
    assert result.status == "BELOW_PANEL_MINIMUM"
    assert (result.value, result.low, result.high, result.contributions) == (
        None,
        None,
        None,
        (),
    )


def test_half_up_rounding():
    assert (
        apportion(
            (row(value=D(5), area=D(2), intersection=D(1)),), "invented_shape"
        ).value
        == 3
    )


@pytest.mark.parametrize(
    "value,area,inside,expected", [(14, 28, 1, 1), (13, 26, 17, 9)]
)
def test_exact_ratio_half_up(value, area, inside, expected):
    r = row(value=D(value), area=D(area), intersection=D(inside))
    assert apportion((r,), "invented_shape").value == expected


def test_exact_multirow_half_up():
    rows = (
        row(value=D(3337), area=D(21), intersection=D(16)),
        row(geography="invented_G2", value=D(4615), area=D(42), intersection=D(25)),
    )
    assert apportion(rows, "invented_shape").value == 5290


def test_exact_presence_bounds_half_up():
    r = replace(simulated(), value=D(140), low=D(14), high=D(154), area=D(28))
    result = apportion((r,), "invented_shape")
    assert (result.value, result.low, result.high) == (5, 1, 6)


def test_exact_grid_half_up():
    r = row(
        metric="population",
        table="pub_population_municipality",
        value=D(14),
        grid_total=D(28),
        grid_intersection=D(1),
    )
    assert apportion((r,), "invented_shape", grid()).value == 1


def test_decimal_context_does_not_change_result():
    r = row(value=D(1234567), area=D(3), intersection=D(3))
    repeating = row(value=D(14), area=D(28), intersection=D(1))
    expected = apportion((repeating,), "invented_shape")
    with localcontext() as context:
        context.prec = 5
        context.traps[Inexact] = True
        context.traps[Rounded] = True
        assert apportion((r,), "invented_shape").value == 1234567
        assert apportion((repeating,), "invented_shape") == expected


def test_round_final_sum_only():
    r = row(value=D(1), area=D(10), intersection=D(4))
    assert (
        apportion((r, replace(r, geography="invented_G2")), "invented_shape").value == 1
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"evidence_status": "observed"},
        {"caveat": ""},
        {"method_version": ""},
        {"geography_kind": "official"},
        {"area_shape": ""},
        {"apportioned_from": ()},
        {"apportioned_from": ("wrong",)},
        {"method": ""},
        {"provenance": "simulated"},
    ],
)
def test_invalid_fact_metadata_rejected(changes):
    result = apportion((row(),), "invented_shape")
    with pytest.raises(ValueError, match="result"):
        validate_result(replace(result, **changes))


def test_simulated_provenance_cannot_be_lost():
    with pytest.raises(ValueError, match="result"):
        validate_result(
            replace(apportion((simulated(),), "invented_shape"), provenance="public")
        )


@pytest.mark.parametrize(
    "table", ["pub_register_company", "pub_unknown", "pub_licence_active"]
)
def test_count_requires_reviewed_table_mapping(table):
    assert apportion((row(table=table),), "invented_shape").status == "REFUSED"


@pytest.mark.parametrize(
    "table", ["pub_licence_active", "pub_licence_issued", "pub_licence_cancelled"]
)
def test_reviewed_licence_counts(table):
    assert (
        apportion((row(table=table, metric="licences"),), "invented_shape").value == 125
    )


def test_released_flow_count_keeps_simulated_provenance():
    r = replace(
        simulated(), table="flow_hourly", metric="flow_hourly", low=None, high=None
    )
    result = apportion((r,), "invented_shape")
    assert (result.value, result.low, result.high, result.provenance) == (
        60,
        None,
        None,
        "simulated",
    )

    assert result.apportioned_from == ("release_units",)


def test_mixed_metrics_and_provenance_refused():
    assert (
        apportion(
            (row(), row(metric="population", table="pub_population_municipality")),
            "invented_shape",
        ).status
        == "REFUSED"
    )
    assert apportion((row(), simulated()), "invented_shape").status == "REFUSED"


def test_public_labour_split_requires_all_categories_total():
    r = row(metric="population", table="pub_labour_sex_municipality")
    assert apportion((r,), "invented_shape").status == "REFUSED"
    assert (
        apportion((replace(r, split="all_categories_total"),), "invented_shape").value
        == 125
    )


@pytest.mark.parametrize("origin", ["shape", "frame", "public"])
def test_admitted_area_origins(origin):
    assert (
        apportion(
            (row(geometry_origin=origin),), "invented_shape", Weight(provenance=origin)
        ).value
        == 125
    )


@pytest.mark.parametrize("field", ["grid_total", "grid_intersection"])
def test_missing_grid_sum_refused(field):
    r = row(
        metric="population",
        table="pub_population_municipality",
        grid_total=D(4),
        grid_intersection=D(1),
    )
    assert (
        apportion((replace(r, **{field: None}),), "invented_shape", grid()).status
        == "REFUSED"
    )


def test_grid_lineage_must_be_complete_and_match_source():
    for source in [
        lineage(source_id="invented_other"),
        lineage(source_id="worldpop_qat_2020", method_version=""),
    ]:
        with pytest.raises(ValueError, match="weight"):
            select_people_weight(grid(lineage=source))


def test_empty_shape_refused():
    assert apportion((row(),), "").status == "REFUSED"


def test_invalid_count_result_status_and_empty_contributions():
    result = apportion((row(),), "invented_shape")
    for changed in [
        replace(result, status="UNBLENDED"),
        replace(result, contributions=()),
        replace(
            result,
            contributions=(
                replace(result.contributions[0], row=row(status="unreleased")),
            ),
        ),
    ]:
        with pytest.raises(ValueError, match="result"):
            validate_result(changed)


def withheld(**changes):
    return replace(
        simulated(),
        status="withheld",
        value=None,
        low=None,
        high=None,
        complete_group=False,
        **changes,
    )


@pytest.mark.parametrize("published_neighbor", [False, True])
def test_withheld_presence_nulls_withhold_shape(published_neighbor):
    rows = (simulated(), withheld()) if published_neighbor else (withheld(),)
    result = apportion(rows, "invented_shape")
    assert result.status == "BELOW_PANEL_MINIMUM"
    assert (result.value, result.low, result.high, result.contributions) == (
        None,
        None,
        None,
        (),
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"in_release": False},
        {"split": "sex"},
        {"geography": ""},
        {"lineage": lineage(method_version="")},
        {"geometry_lineage": lineage(sha256="")},
        {"geography_kind": "official"},
        {"table": "presence_split"},
        {"geometry_origin": "protected"},
        {"provenance": "public"},
        {"metric": "flow_hourly", "table": "flow_hourly"},
    ],
)
def test_withheld_presence_still_requires_release_eligibility(changes):
    result = apportion((withheld(**changes),), "invented_shape")
    assert result.status == "REFUSED"
    assert (result.value, result.low, result.high, result.contributions) == (
        None,
        None,
        None,
        (),
    )


@pytest.mark.parametrize("status", ["suppressed", "unreleased"])
def test_other_presence_status_refused(status):
    assert (
        apportion((replace(withheld(), status=status),), "invented_shape").status
        == "REFUSED"
    )


@pytest.mark.parametrize("neighbor", [simulated(in_release=False), row()])
@pytest.mark.parametrize("reverse", [False, True])
def test_withheld_does_not_mask_forbidden_or_mixed_neighbor(neighbor, reverse):
    rows = (withheld(), neighbor)
    result = apportion(rows[::-1] if reverse else rows, "invented_shape")
    assert result.status == "REFUSED"
    assert result.contributions == ()


@pytest.mark.parametrize(
    "r",
    [
        row(value=None),
        replace(simulated(), value=None),
        row(metric="share", value=None),
    ],
)
def test_published_null_value_refused(r):
    assert apportion((r,), "invented_shape").status == "REFUSED"


@pytest.mark.parametrize("low,high", [(D(110), D(130)), (D(110), None), (None, D(130))])
def test_flow_bounds_are_not_in_contract(low, high):
    r = replace(
        simulated(), table="flow_hourly", metric="flow_hourly", low=low, high=high
    )
    result = apportion((r,), "invented_shape")
    assert result.status == "REFUSED"
    assert (result.value, result.low, result.high) == (None, None, None)


@pytest.mark.parametrize("field", ["low", "high"])
def test_presence_requires_each_bound(field):
    result = apportion((replace(simulated(), **{field: None}),), "invented_shape")
    assert result.status == "REFUSED"
    assert (result.value, result.low, result.high) == (None, None, None)


def test_apportioned_value_over_incomplete_group_rejected():
    result = apportion((simulated(),), "invented_shape")
    with pytest.raises(ValueError, match="result violates DAT-147"):
        validate_result(
            replace(
                result,
                contributions=(
                    replace(
                        result.contributions[0], row=simulated(complete_group=False)
                    ),
                ),
            )
        )


def test_public_count_does_not_require_presence_group():
    assert apportion((row(complete_group=False),), "invented_shape").value == 125


@pytest.mark.parametrize("r", [row(), simulated()])
def test_area_calculation_names_area_weight(r):
    result = apportion((r,), "invented_shape", grid())
    assert result.method == "area"
    assert result.weight_source.source_id == "area"


@pytest.mark.parametrize("r", [row(), simulated()])
@pytest.mark.parametrize(
    "weight,message",
    [
        (
            grid(
                source_id="worldpop_qat_agesex",
                lineage=lineage(source_id="worldpop_qat_agesex"),
            ),
            "weight grid is not admitted",
        ),
        (Weight(provenance="protected"), "weight must derive"),
        (grid(), "result violates DAT-147"),
    ],
)
def test_area_result_rejects_wrong_weight_source(r, weight, message):
    result = apportion((r,), "invented_shape")
    with pytest.raises(ValueError, match=message):
        validate_result(replace(result, weight_source=weight))


@pytest.mark.parametrize("metric", ["labour_force", "employed", "unemployed"])
def test_labour_count_cannot_bypass_split_table(metric):
    result = apportion(
        (row(metric=metric, table="pub_population_municipality"),), "invented_shape"
    )
    assert result.status == "REFUSED"
    assert (result.value, result.low, result.high, result.contributions) == (
        None,
        None,
        None,
        (),
    )


@pytest.mark.parametrize("reverse", [False, True])
def test_every_simulated_group_must_be_complete(reverse):
    rows = (
        simulated(),
        replace(simulated(), geography="invented_U2", complete_group=False),
    )
    result = apportion(rows[::-1] if reverse else rows, "invented_shape")
    assert result.status == "BELOW_PANEL_MINIMUM"
    assert (result.value, result.low, result.high, result.contributions) == (
        None,
        None,
        None,
        (),
    )


@pytest.mark.parametrize("table", ["presence_split", "flow_split"])
def test_simulated_split_table_refused(table):
    result = apportion((replace(simulated(), table=table),), "invented_shape")
    assert result.status == "REFUSED"
    assert (result.value, result.low, result.high) == (None, None, None)


@pytest.mark.parametrize(
    "table",
    ["employment", "residence", "business_register", "wages", "pub_pop_agesex_grid"],
)
def test_forbidden_statistic_table_refused(table):
    result = apportion((row(metric="share", table=table),), "invented_shape")
    assert result.status == "REFUSED"
    assert result.originals == ()


@pytest.mark.parametrize(
    "r",
    [
        replace(
            simulated(),
            table="access_score",
            metric="access_score",
            low=None,
            high=None,
        ),
        replace(simulated(), geography_kind="official"),
    ],
)
def test_simulated_metric_and_geography_guards(r):
    result = apportion((r,), "invented_shape")
    assert result.status == "REFUSED"
    assert result.contributions == ()


@pytest.mark.parametrize("metric", ["share", "building_permits"])
def test_every_input_must_be_eligible(metric):
    rows = (
        row(metric=metric),
        row(metric=metric, geography="invented_G2", status="suppressed"),
    )
    result = apportion(rows, "invented_shape")
    assert result.status == "REFUSED"
    assert result.originals == ()


@pytest.mark.parametrize(
    "neighbor",
    [
        row(geography="invented_G2", status="unreleased"),
        replace(simulated(), geography="invented_G2"),
    ],
)
def test_validator_checks_every_contribution(neighbor):
    result = apportion((row(), row(geography="invented_G2")), "invented_shape")
    contributions = (
        result.contributions[0],
        replace(result.contributions[1], row=neighbor),
    )
    with pytest.raises(ValueError, match="result violates DAT-147"):
        validate_result(replace(result, contributions=contributions))


@pytest.mark.parametrize(
    "r,expected",
    [
        (row(grid_total=D(4), grid_intersection=D(3)), (125, None, None)),
        (
            row(
                table="pub_licence_active",
                metric="licences",
                grid_total=D(4),
                grid_intersection=D(3),
            ),
            (125, None, None),
        ),
        (replace(simulated(), grid_total=D(4), grid_intersection=D(3)), (60, 55, 65)),
    ],
)
def test_nonpeople_counts_use_area_even_with_admitted_grid(r, expected):
    result = apportion((r,), "invented_shape", grid())
    assert result.status == "APPORTIONED"
    assert (result.value, result.low, result.high) == expected
    assert result.method == "area"


def test_grid_mode_still_requires_nonzero_area():
    r = row(
        metric="population",
        table="pub_population_municipality",
        area=D(0),
        grid_total=D(4),
        grid_intersection=D(1),
    )
    assert apportion((r,), "invented_shape", grid()).status == "NO_DATA"


def test_withheld_status_overrides_complete_flag():
    result = apportion((replace(withheld(), complete_group=True),), "invented_shape")
    assert result.status == "BELOW_PANEL_MINIMUM"
    assert (result.value, result.low, result.high, result.contributions) == (
        None,
        None,
        None,
        (),
    )


def test_nonpeople_result_cannot_claim_grid_method():
    result = apportion((row(),), "invented_shape")
    with pytest.raises(ValueError, match="result violates DAT-147"):
        validate_result(
            replace(result, method="worldpop_qat_2020", weight_source=grid())
        )
