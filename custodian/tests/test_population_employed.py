"""S2-T38: the `Employed` indicator of `pop_muni` as a Public fact (decision 0064 item 15).

Invented fixtures only. The count stays on the source's own geography, keeps its
source and year, is not an audit-count selector (PUB-84, DAT-128) and is never
joined, used to segment, apportioned to a drawn area or combined with a protected
figure (rule 10).
"""

from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import pytest
from custodian.tests import test_frame_seventh as seventh
from custodian.tests.test_frame_census import entry

from eii_custodian.publicdata.additions.split_policy import UseRequest
from eii_custodian.publicdata.frame import census, population
from eii_custodian.publicdata.frame.census import census_rows, validate_tables
from eii_custodian.publicdata.frame.checks import FrameError
from eii_custodian.publicdata.frame.population import load_indicators, population_rows

seventh_build = seventh.seventh_build
RETRIEVED = "2026-11-14T00:00:00Z"
AUDIT_PAIRS = {
    "residents": "persons",
    "households": "households",
    "establishments": "establishments",
    "employees": "persons",
}
NAMES = [{"name": "Invented A", "municipality_code": "SYN-A"}]


def employed_record(**changes):
    record = {
        "municipality_code": "SYN-A",
        "period": "2020",
        "indicator": "employed",
        "value": "17",
        "unit": "persons",
    }
    record.update(changes)
    return record


# AC1: the table carries the indicator by municipality with its source and year.


def test_committed_review_loads_employed_by_municipality_and_year():
    rows, report = population_rows(
        [
            seventh.population("Employed"),
            seventh.population("Population"),
            seventh.population("Economically Active"),
        ],
        seventh.committed_review_dir(),
        NAMES,
        None,
    )
    assert rows == [
        {
            "municipality_code": "SYN-A",
            "period": "2020",
            "indicator": "employed",
            "value": 17,
            "unit": "persons",
        },
        {
            "municipality_code": "SYN-A",
            "period": "2020",
            "indicator": "residents",
            "value": 17,
            "unit": "persons",
        },
    ]
    assert report == "pop_muni: 1 rows not loaded: Economically Active"


def test_live_build_carries_employed_with_source_and_year(seventh_build, tmp_path):
    (tmp_path / "review" / "population_indicators.csv").write_text(
        "indicator,mapped_indicator\nInvented omitted,employed\n"
        "Invented people,residents\n"
    )
    result = seventh_build()
    assert result.tables["pub_population_municipality"] == [
        {
            "municipality_code": "9",
            "period": "2020",
            "indicator": "employed",
            "value": Decimal(17),
            "unit": "persons",
            "source_id": "pop_muni",
        },
        {
            "municipality_code": "9",
            "period": "2020",
            "indicator": "residents",
            "value": Decimal(17),
            "unit": "persons",
            "source_id": "pop_muni",
        },
    ]
    assert result.sources["pop_muni"]["retrieved_utc"] == RETRIEVED
    assert not any("rows not loaded" in line for line in result.report)


def test_census_rows_admits_employed_in_the_population_table():
    rows, ignored = census_rows(
        entry("pop_muni"), [employed_record()], RETRIEVED, "pub_population_municipality"
    )
    assert rows == [{**employed_record(value=Decimal(17)), "source_id": "pop_muni"}]
    assert ignored == []


def test_load_indicators_accepts_the_employed_token(tmp_path):
    (tmp_path / "population_indicators.csv").write_text(
        "indicator,mapped_indicator\nInvented count,employed\n"
    )
    assert load_indicators(tmp_path) == {"Invented count": "employed"}


@pytest.mark.parametrize(
    "source,table,key",
    [
        ("census_zone_hh", "pub_census_zone", "zone_code"),
        ("est_census", "pub_census_national", None),
        ("census_district_pop", "pub_census_district", "district_key"),
    ],
)
def test_plant_employed_in_another_census_table_refused(source, table, key):
    record = employed_record()
    del record["municipality_code"]
    if key:
        record[key] = "SYN-A"
    with pytest.raises(FrameError, match="invalid indicator/unit"):
        census_rows(entry(source), [record], RETRIEVED, table)


@pytest.mark.parametrize("unit", ["households", "establishments", "wrong", None])
def test_plant_employed_with_wrong_unit_refused(unit):
    with pytest.raises(FrameError, match="invalid indicator/unit"):
        census_rows(
            entry("pop_muni"),
            [employed_record(unit=unit)],
            RETRIEVED,
            "pub_population_municipality",
        )


def test_plant_unknown_indicator_with_no_unit_refused():
    with pytest.raises(FrameError, match="invalid indicator/unit"):
        census_rows(
            entry("pop_muni"),
            [employed_record(indicator="invented_other", unit=None)],
            RETRIEVED,
            "pub_population_municipality",
        )


@pytest.mark.parametrize("token", ["invented_other", "Employed", "unemployed"])
def test_plant_unadmitted_token_in_inspection_refused(token):
    from eii_custodian.publicdata.frame.mapping import inspect_source

    with pytest.raises(FrameError, match=f"pop_muni: invalid_indicator: {token}$"):
        inspect_source(
            "pop_muni", [seventh.population("Invented")], {"Invented": token}
        )


def test_plant_employed_without_retrieval_date_refused():
    with pytest.raises(FrameError, match="missing retrieval date"):
        census_rows(
            entry("pop_muni"), [employed_record()], "", "pub_population_municipality"
        )


def test_plant_duplicate_employed_key_refused():
    rows, _ = census_rows(
        entry("pop_muni"), [employed_record()], RETRIEVED, "pub_population_municipality"
    )
    tables = {table: [] for table in census.GEOGRAPHY}
    tables["pub_population_municipality"] = rows
    known = {"municipality_code": {"SYN-A"}, "zone_code": set(), "district_key": set()}
    validate_tables(tables, known)
    tables["pub_population_municipality"] = rows * 2
    with pytest.raises(FrameError, match="duplicate census key"):
        validate_tables(tables, known)


def test_unit_for_admits_employed_in_the_population_table_only():
    assert census.unit_for("pub_population_municipality", "employed") == "persons"
    for table in ("pub_census_zone", "pub_census_national", "pub_census_district"):
        assert census.unit_for(table, "employed") is None
    for table in census.GEOGRAPHY:
        for token, unit in AUDIT_PAIRS.items():
            assert census.unit_for(table, token) == unit
    assert census.unit_for("pub_population_municipality", "invented_other") is None


# AC2: never joined, used to segment, apportioned to a drawn area or combined
# with a protected figure (rule 10); the general guard does the flag checks.


def display(**changes):
    return replace(
        UseRequest(
            table="pub_population_municipality",
            source_splits=(),
            consumer="public_display",
            geography="source",
            categories="source",
            lineage="public",
        ),
        **changes,
    )


def test_employed_display_on_source_geography_admitted():
    verdict = population.validate_employed_use(display())
    assert (verdict.admitted, verdict.reason) == (True, "admitted_public")


@pytest.mark.parametrize(
    "changes,reason",
    [
        ({"join_to": "worker"}, "join_worker"),
        ({"join_to": "residence"}, "join_residence"),
        ({"join_to": "company"}, "join_company"),
        ({"segments": "worker"}, "segment_worker"),
        ({"segments": "residence"}, "segment_residence"),
        ({"segments": "company"}, "segment_company"),
        ({"apportions": True}, "tabulated_apportionment"),
        ({"geography": "area_shape"}, "invented_geography"),
        ({"combines_protected": True}, "protected_composite"),
        ({"categories": "merged"}, "merged_category"),
        ({"lineage": "mixed"}, "mixed_lineage"),
        ({"consumer": "worker_record"}, "worker_record"),
        ({"consumer": "joining_key"}, "joining_key"),
        ({"consumer": "feature"}, "consumer_unlisted"),
    ],
)
def test_plant_each_rule_10_use_refused(changes, reason):
    verdict = population.validate_employed_use(display(**changes))
    assert (verdict.admitted, verdict.reason) == (False, reason)


def test_plant_employed_as_cited_movement_anchor_refused():
    verdict = population.validate_employed_use(
        display(
            consumer="movement_anchor",
            anchor="mob.split_anchor.population_age_sex",
            summed_over_source_categories=True,
        )
    )
    assert (verdict.admitted, verdict.reason) == (False, "employed_not_anchor")


def test_plant_employed_as_reserved_grid_sum_refused():
    verdict = population.validate_employed_use(
        display(reserved_use="grid_whole_cells", geography="area_shape")
    )
    assert (verdict.admitted, verdict.reason) == (False, "employed_reserved_use")


@pytest.mark.parametrize(
    "table", ["pub_labour_sex_municipality", "pub_census_zone", "pub_pop_agesex_grid"]
)
def test_plant_guard_used_for_another_table_refused(table):
    verdict = population.validate_employed_use(display(table=table))
    assert (verdict.admitted, verdict.reason) == (False, "employed_table_unlisted")


# AC3: the contract of the table in document 03 lists the indicator.


def contract_text() -> str:
    from custodian.tests.repository_root import repository_root

    root = repository_root(Path(__file__))
    return (root / "docs" / "03_DATA_CONTRACTS.md").read_text(encoding="utf-8")


def assert_population_contract_lists_employed(text: str) -> None:
    section = text.split("### 7.3 Columns")[1].split("\n### ")[0]
    rows = [
        line
        for line in section.splitlines()
        if line.startswith("| `pub_population_municipality` |")
    ]
    assert len(rows) == 1, f"expected one 7.3 row, got {len(rows)}"
    assert "`indicator` (`residents`, `employed`)" in rows[0]
    assert "`unit` (`persons`)" in rows[0]
    dat_128 = [line for line in text.splitlines() if line.startswith("| DAT-128 |")]
    assert len(dat_128) == 1
    assert "`employed`/`persons` in `pub_population_municipality`" in dat_128[0]


def test_population_contract_lists_employed():
    assert_population_contract_lists_employed(contract_text())


@pytest.mark.parametrize(
    "old,new",
    [
        ("`indicator` (`residents`, `employed`)", "`indicator`"),
        ("`indicator` (`residents`, `employed`)", "`indicator` (`residents`)"),
        ("`employed`/`persons` in `pub_population_municipality`", "a count"),
    ],
)
def test_plant_contract_without_employed_fails(old, new):
    text = contract_text()
    assert old in text
    with pytest.raises(AssertionError):
        assert_population_contract_lists_employed(text.replace(old, new))


# AC4: no audit selector, privacy rule, attack size or tolerance changes.


def assert_audit_selectors_unchanged(units, table_units) -> None:
    assert dict(units) == AUDIT_PAIRS
    assert dict(table_units) == {("pub_population_municipality", "employed"): "persons"}
    assert "employed" not in units


def test_audit_selectors_stay_the_four_pairs():
    assert_audit_selectors_unchanged(census.UNITS, census.TABLE_UNITS)


@pytest.mark.parametrize(
    "units_change,table_change",
    [
        ({"employed": "persons"}, {}),
        ({"labour_force": "persons"}, {}),
        ({}, {("pub_census_zone", "employed"): "persons"}),
        ({}, {("pub_population_municipality", "unemployed"): "persons"}),
    ],
)
def test_plant_fifth_audit_pair_or_wider_table_map_fails(units_change, table_change):
    with pytest.raises(AssertionError):
        assert_audit_selectors_unchanged(
            {**census.UNITS, **units_change}, {**census.TABLE_UNITS, **table_change}
        )
