"""S3-T12 boxes 2 and 9: no `fdi_projects` field is dropped at loading.

The contract's column list is read from document 03 section 7.3 itself, so a
column added there and not carried by the read or the route fails here.
"""

import re
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st
from product.tests.public_layer_render_fixture import seed_contract_rows
from product.tests.test_tools_http import service as service

from eii_product.api.public_layers import (
    FDI_CONTRACT_FIELDS,
    FDI_FACT_FIELDS,
    FDI_FIELDS,
    fdi_field_problem,
)
from eii_product.store.registry import PACKAGED, require_query

DOC = Path(__file__).resolve().parents[2] / "docs" / "03_DATA_CONTRACTS.md"
ROW_START = "| `fdi_projects` | `project_key` string"


def contract_columns() -> list[str]:
    """Column names of the document 03 section 7.3 row, in first-mention order."""
    line = next(
        line
        for line in DOC.read_text("utf-8").splitlines()
        if line.startswith(ROW_START)
    )
    body = line.split("|")[2].split("No field is dropped")[0]
    names: list[str] = []
    for token in re.findall(r"`([^`]+)`", body):
        if token == "fdi_projects" or token in names:
            continue
        if re.fullmatch(r"[a-z][a-z0-9_]*[a-z0-9]", token):
            names.append(token)
    return names


def test_contract_list_equals_route_and_read_lists():
    columns = contract_columns()
    assert len(columns) == 51
    assert set(columns) == FDI_CONTRACT_FIELDS
    assert len(FDI_FIELDS) + len(FDI_FACT_FIELDS) == len(FDI_CONTRACT_FIELDS)
    query = require_query(PACKAGED, PACKAGED.lookup("layer_fdi_projects"))
    assert {field.name for field in query.returns} - {"source_id"} == set(columns)


def full_row() -> dict[str, object]:
    return {name: None for name in FDI_CONTRACT_FIELDS} | {"source_id": "INVENTED-src"}


def test_complete_row_has_no_problem():
    assert fdi_field_problem(full_row()) is None


@pytest.mark.parametrize("dropped", sorted(FDI_CONTRACT_FIELDS))
def test_each_dropped_column_is_refused(dropped):
    row = full_row()
    del row[dropped]
    assert fdi_field_problem(row) == "fdi_field_dropped"


def test_unknown_column_is_refused_never_left_off_screen():
    assert fdi_field_problem(full_row() | {"INVENTED_extra": None}) == (
        "fdi_field_unexpected"
    )


def test_route_refuses_a_row_with_a_dropped_column(service):
    # The named read projects onto its declared columns, so an unknown column
    # cannot reach the route through the store; the unit case above plants it.
    client, _ledger, store, _calls = service
    seed_contract_rows(store)
    row = dict(store.tables["fdi_projects"][0])
    del row["province"]
    store.tables["fdi_projects"] = [row]
    response = client.get("/api/layers/fdi_projects")
    assert response.status_code == 500 and set(response.json()) == {"error"}


def test_route_refuses_a_read_column_it_would_leave_off_screen(service):
    """Plant a read that returns a column the route does not carry."""
    from unittest.mock import patch

    from eii_product.api import public_layers

    client, _ledger, store, _calls = service
    seed_contract_rows(store)
    original = public_layers.read

    def wider(store, name, **params):
        rows = original(store, name, **params)
        if name == "layer_fdi_projects":
            return [{**row, "INVENTED_extra": "INVENTED value"} for row in rows]
        return rows

    with patch.object(public_layers, "read", wider):
        response = client.get("/api/layers/fdi_projects")
    assert response.status_code == 500 and set(response.json()) == {"error"}


def test_route_feature_carries_every_contract_field(service):
    client, _ledger, store, _calls = service
    seed_contract_rows(store)
    body = client.get("/api/layers/fdi_projects").json()
    feature = next(
        f
        for f in body["payload"]["layers"][0]["features"]
        if f["feature_id"] == "fdi_abcdefabcdefabcd"
    )
    loaded = set(feature["field_segments"])
    slots = {
        "capex_value": "capex_fact_id",
        "jobs": "jobs_fact_id",
        "lng": "lon_fact_id",
        "lat": "lat_fact_id",
        "announced": "announced",
    }
    loaded |= {field for field, slot in slots.items() if feature.get(slot)}
    assert loaded == set(contract_columns())


@given(
    kept=st.sets(st.sampled_from(sorted(FDI_CONTRACT_FIELDS))),
    extra=st.sets(st.from_regex(r"INVENTED_[a-z]{1,8}", fullmatch=True), max_size=3),
    with_source=st.booleans(),
)
def test_problem_over_every_column_subset_and_extra(kept, extra, with_source):
    """Oracle: dropped wins over unexpected; only the full set with no extra passes."""
    row = {name: None for name in kept | extra}
    if with_source:
        row["source_id"] = "INVENTED-src"
    expected = (
        "fdi_field_dropped"
        if kept != FDI_CONTRACT_FIELDS
        else "fdi_field_unexpected"
        if extra
        else None
    )
    assert fdi_field_problem(row) == expected
