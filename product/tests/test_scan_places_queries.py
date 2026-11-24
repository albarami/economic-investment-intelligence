"""Portable query inventory contract for scan_places (B3)."""

import pytest
import sqlglot
from sqlglot import exp

from eii_product.store.lint import lint_inventory
from eii_product.store.protocol import StoreRefusal
from eii_product.store.registry import (
    bind,
    load_inventory,
    packaged_sql_dir,
    require_query,
)

NAMES = {
    "scan_places_" + name
    for name in (
        "places",
        "fsq",
        "verification",
        "visits",
        "categories",
        "neighbours",
        "lineage",
        "sources",
    )
}


def test_queries_are_present_and_linted():
    inventory = load_inventory(packaged_sql_dir())
    assert {
        q.name for q in inventory.queries if q.name.startswith("scan_places_")
    } == NAMES
    lint_inventory(inventory)
    require_scan_contract(inventory)


def require_scan_contract(inventory):
    allowed = {
        "pub_place",
        "pub_place_fsq",
        "pub_place_verification",
        "pub_venue_visits",
        "graph_node",
        "graph_edge",
        "fact_lineage",
        "source_registry",
    }
    for query in inventory.queries:
        if not query.name.startswith("scan_places_"):
            continue
        assert all(table.name in allowed for table in query.tables), "non_public_table"
        tree = sqlglot.parse_one(query.text, read="postgres")
        assert all(
            isinstance(item, exp.Alias) and isinstance(item.this, exp.Column)
            for item in tree.expressions
        ), "plain_columns_required"
        for clause in tree.find_all(exp.Where, exp.Order, exp.Limit):
            assert not any(
                literal.is_number for literal in clause.find_all(exp.Literal)
            ), "numeric_selection"
        if query.name == "scan_places_fsq":
            assert "confidence" not in {column.name for column in query.returns}, (
                "invented_confidence"
            )


@pytest.mark.parametrize(
    "plant",
    ["missing_contract", "spatial", "numeric_where", "fsq_confidence", "protected"],
)
def test_query_plants(tmp_path, plant):
    (tmp_path / "__init__.py").write_text('"""Invented query package."""\n')
    name = "scan_places_fsq" if plant == "fsq_confidence" else "scan_places_places"
    folder = packaged_sql_dir()
    sql = (folder / (name + ".sql")).read_text()
    contract = (folder / (name + ".toml")).read_text()
    if plant == "spatial":
        sql = sql.replace("p.lon AS lon", "ST_X(p.lon) AS lon")
    elif plant == "numeric_where":
        sql = sql.replace("ORDER BY", "AND p.confidence >= 0.7\nORDER BY")
    elif plant == "fsq_confidence":
        sql = sql.replace("licence text", "licence text, confidence numeric").replace(
            "p.licence AS licence", "p.licence AS licence, p.confidence AS confidence"
        )
    elif plant == "protected":
        sql = sql.replace("pub_place", "protected_place")
        contract = contract.replace("pub_place", "protected_place")
    (tmp_path / (name + ".sql")).write_text(sql)
    if plant != "missing_contract":
        (tmp_path / (name + ".toml")).write_text(contract)
    reasons = {
        "missing_contract": "query header invalid",
        "spatial": "forbidden construct",
        # The store's literal guard refuses the fractional threshold first.
        "numeric_where": "forbidden construct",
        "fsq_confidence": "invented_confidence",
        "protected": "non_public_table",
    }
    with pytest.raises((StoreRefusal, AssertionError), match=reasons[plant]):
        inventory = load_inventory(tmp_path)
        lint_inventory(inventory)
        require_scan_contract(inventory)


def test_query_tokens_and_list_parameters():
    inventory = load_inventory(packaged_sql_dir())
    query = inventory.get("scan_places_places")
    for engine in ("embedded", "postgres"):
        _, values = bind(query, {"categories": ["SYN-food", "SYN-drink"]}, engine)
        assert values == {"categories": ["SYN-food", "SYN-drink"]}
    with pytest.raises(StoreRefusal):
        require_query(inventory, "SELECT * FROM pub_place")
    foreign = load_inventory(packaged_sql_dir())
    with pytest.raises(StoreRefusal):
        require_query(inventory, foreign.lookup("scan_places_places"))


def test_only_public_contract_tables():
    inventory = load_inventory(packaged_sql_dir())
    allowed = {
        "pub_place",
        "pub_place_fsq",
        "pub_place_verification",
        "pub_venue_visits",
        "graph_node",
        "graph_edge",
        "fact_lineage",
        "source_registry",
    }
    selected = [q for q in inventory.queries if q.name in NAMES]
    assert {t.name for q in selected for t in q.tables} == allowed
    assert "confidence" not in {
        c.name for c in inventory.get("scan_places_fsq").returns
    }
    assert "category_ids" in {c.name for c in inventory.get("scan_places_fsq").returns}
    assert "attr_value_2" not in {
        c.name for c in inventory.get("scan_places_neighbours").returns
    }


# Independently transcribed from brief B3, not derived from query headers.
EXPECTED_RETURNS = {
    "places": "place_id:text name:text name_ar:text category:text lon:numeric lat:numeric cell:bigint source_release:text source_provider:text licence:text confidence:numeric",
    "fsq": "fsq_place_id:text name:text name_ar:text category_ids:text category_labels:text lon:numeric lat:numeric cell:bigint source_release:text licence:text",
    "verification": "place_id:text check_date:date reviewer_role:text verification_link:text status:text source_id:text",
    "visits": "venue_key:text place_id:text venue_kind:text name_en:text name_ar:text region:text period:text indicator:text value:bigint unit:text",
    "categories": "node_id:text node_type:text code:text label_en:text label_ar:text provenance:text source_id:text",
    "neighbours": "edge_id:text edge_type:text from_node_id:text to_node_id:text provenance:text basis:text period:text attr_value:numeric attr_unit:text source_id:text",
    "lineage": "lineage_id:text table_name:text source_id:text input_class:text transform:text",
    "sources": "source_id:text publisher:text title:text url:text licence:text licence_basis:text retrieved_on:date sha256:text attribution:text",
}


@pytest.mark.parametrize("name", EXPECTED_RETURNS)
def test_exact_return_names_and_types(name):
    query = load_inventory(packaged_sql_dir()).get("scan_places_" + name)
    assert [(column.name, column.type_name) for column in query.returns] == [
        tuple(field.split(":")) for field in EXPECTED_RETURNS[name].split()
    ]
