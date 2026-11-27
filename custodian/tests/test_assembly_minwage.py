"""Statutory rule rows and citation lineage on invented receipts and wages."""

import json
from pathlib import Path

import pytest
from custodian.tests.test_production_adapters import context
from custodian.tests.test_public_series import series_cache
from custodian.tests.test_source_completeness import entry, receipt

from eii_custodian.publicdata import completeness as c
from eii_custodian.publicdata.assembly import AssemblyError


def wage_build(tmp_path, survey, receipt_state="valid"):
    row = entry(
        "ref_min_wage", kind="citation_only", release_tables=("pub_wage_table",)
    )
    build = context(tmp_path, (row,))
    if receipt_state != "absent":
        build.receipts[row.key] = {**receipt(row), "sha256": "CITATION_ONLY"}
        if receipt_state == "licence_drift":
            build.receipts[row.key]["licence_id"] = "Invented different licence"
    if survey:
        fixtures = json.loads(
            (
                Path(__file__).parent / "fixtures/series/confirmed_shapes.json"
            ).read_text()
        )
        wage, digest = series_cache(tmp_path, "wage_occ", fixtures["wage_occ"])
        build.entries += (wage,)
        build.selected[wage.key] = digest
    if survey:
        # Invented wages do not satisfy the unrelated full-pack regression pins.
        with pytest.raises(AssemblyError, match=r"^assembly_regression_refused$"):
            build.series_stage()
    else:
        build.series_stage()
    return row, build


def minimum_check(row, build):
    return c.check(
        entries=(row,),
        pack=c.Pack({row.source_id: ()}, frozenset()),
        inventory={row.source_id: ()},
        catalogue={"pub_wage_table"},
        receipts={
            key: value for key, value in build.receipts.items() if key == row.key
        },
        outputs={
            key: value for key, value in build.source_tables.items() if key == row.key
        },
        absences={},
        cached_source_ids=(),
    )


@pytest.mark.parametrize("survey", [False, True])
def test_minwage_exact_rows_and_credit(tmp_path, survey):
    row, build = wage_build(tmp_path, survey)
    rows = build.tables.get("pub_wage_table", [])
    assert [item for item in rows if item["table_code"] == row.key] == [
        {
            "table_code": "ref_min_wage",
            "period": "2020",
            "breakdown_key": "ALL",
            "indicator": indicator,
            "unit": "QAR",
            "value": value,
            "source_id": "ref_min_wage",
        }
        for indicator, value in (
            ("statutory_minimum_basic", "1000.00"),
            ("statutory_minimum_housing_allowance", "500.00"),
            ("statutory_minimum_food_allowance", "300.00"),
        )
    ]
    result = minimum_check(row, build)
    assert {"id": row.key, "state": "in use", "reason": ""} in result, result
    record = json.loads((tmp_path / "assembly/series_stage.json").read_text())
    assert record["row_sources"]["pub_wage_table"][-3:] == [row.key] * 3
    chain = record["source_chain"][row.key]
    for field in ("sha256", "retrieved_utc", "licence_id"):
        assert chain[field] == build.receipts[row.key][field]
    if survey:
        internal = json.loads(
            (tmp_path / "series/internal/pub_wage_table.json").read_text()
        )
        assert rows[:-3] == internal["rows"]
        assert record["row_sources"]["pub_wage_table"][:-3] == internal["row_sources"]
        assert build.source_tables["wage_occ"] == ["pub_wage_table"]


@pytest.mark.parametrize("receipt_state", ["absent", "licence_drift"])
def test_minwage_invalid_receipt_withholds_rows_and_credit(tmp_path, receipt_state):
    row, build = wage_build(tmp_path, True, receipt_state)
    assert all(item["table_code"] != row.key for item in build.tables["pub_wage_table"])
    assert row.key not in build.table_sources["pub_wage_table"]
    assert row.key not in build.source_tables
    assert {
        "id": row.key,
        "state": "failed",
        "reason": "source_receipt_missing: missing or invalid receipt",
    } in minimum_check(row, build)
