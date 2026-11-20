"""C30 generated admission agrees with the tracked pack, never a data cache.

The proposed conformance release registry is absent on this calculation base.
Document 03 sections 7.2/7.3 are the available independent table contract.
"""

from dataclasses import replace
from pathlib import Path

import pytest

from eii_core.calc.forecast import TABLE_GRAINS
from eii_core.calc.forecast_list import DEFINITIONS

ROOT = Path(__file__).resolve().parents[2]
AUDIT = ROOT / "custodian/publicdata/review/s6_t25_generated_series.md"


def assert_agreement(definitions, grains):
    contract = (ROOT / "docs/03_DATA_CONTRACTS.md").read_text()
    table_rows = contract.split("### 7.2 Table catalogue", 1)[1].split(
        "### 7.3 Columns", 1
    )[0]
    columns = contract.split("### 7.3 Columns", 1)[1].split("## 8.", 1)[0]
    expected = {
        "pay_level": (("worker_pay", "resident_pay"), "mean_wage", "qar_per_month"),
        "earner_count": (("worker_pay", "resident_pay"), "earner_count", "count"),
        "wage_bill": (("worker_pay", "resident_pay"), "wage_bill", "qar"),
        "stayer_index": (("month_change",), "stayer_wage_index", "index"),
        "employment_by_area": (("worker_pay",), "earner_count", "count"),
        "employment_by_occupation_residence": (
            ("occupation_pay",),
            "earner_count",
            "count",
        ),
        "employment_by_occupation_workplace": (
            ("occupation_pay",),
            "earner_count",
            "count",
        ),
    }
    rows = tuple(d for d in definitions if d.state == "released")
    assert {d.key for d in rows} == set(expected)
    for row in rows:
        tables, measure, unit = expected[row.key]
        assert (row.tables, row.measures, row.unit) == (tables, (measure,), unit)
        assert (row.input_class, row.frequency, row.subjects) == (
            "synthetic",
            "month",
            ("area",),
        )
        assert row.confirmed_sources
        assert set(row.confirmed_sources) <= {
            "business_register.v1",
            "employment.v1",
            "residence.v1",
            "wages.v1",
        }
        for table in row.tables:
            catalogue_row = next(
                line
                for line in table_rows.splitlines()
                if line.startswith(f"| `{table}` |")
            )
            assert catalogue_row.split("|")[2].strip() == "Protected"
            keys = tuple(
                part.strip().strip("`")
                for part in catalogue_row.split("|")[4].split(",")
            )
            assert grains[table] == keys
            column_row = next(
                line
                for line in columns.splitlines()
                if line.startswith(f"| `{table}` |")
            )
            if measure == "mean_wage":
                assert "`wage_bill`" in column_row and "`earner_count`" in column_row
            else:
                assert f"`{measure}`" in column_row


def test_generated_definitions_match_pack_table_contract():
    assert_agreement(DEFINITIONS, TABLE_GRAINS)


@pytest.mark.parametrize(
    "field,value",
    [
        ("key", "invented"),
        ("tables", ("worker_pay",)),
        ("measures", ("invented",)),
        ("input_class", "public"),
        ("confirmed_sources", ("invented.v1",)),
        ("unit", "qar"),
    ],
)
def test_generated_catalogue_plants_are_detected(field, value):
    planted = tuple(
        replace(d, **{field: value})
        if d.key == "employment_by_occupation_residence"
        else d
        for d in DEFINITIONS
    )
    with pytest.raises(AssertionError):
        assert_agreement(planted, TABLE_GRAINS)


def test_generated_grain_rename_is_detected():
    planted = dict(TABLE_GRAINS, occupation_pay=("invented",))
    with pytest.raises(AssertionError):
        assert_agreement(DEFINITIONS, planted)


def test_every_generated_definition_has_an_audited_source_and_history():
    audit = AUDIT.read_text()
    for row in DEFINITIONS:
        if row.state != "released":
            continue
        section = audit.split(f"### {row.key}\n", 1)[1].split("\n### ", 1)[0]
        assert all(table in section for table in row.tables)
        assert all(feed in section for feed in row.confirmed_sources)
        assert "month" in section
        assert row.unit in section
        assert all(level in section for level in row.levels)
    assert "joiner_count" in audit and "leaver_count" in audit
    assert "S4-T14" in audit and "S4-T15" in audit and "S4-T16" in audit
