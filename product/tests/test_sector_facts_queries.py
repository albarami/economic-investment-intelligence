"""Named Public queries: registry, portability and embedded preparation."""

import re
from pathlib import Path

import pytest
from product.tests.sector_fixture import repository_path

from eii_product.store.lint import lint_inventory
from eii_product.store.registry import PACKAGED


def test_sector_queries_exist_and_lint():
    names = {q.name for q in PACKAGED.queries}
    assert "sector_facts_licence_local" in names
    lint_inventory(PACKAGED)


def scan_query(text):
    body = "\n".join(line for line in text.splitlines() if not line.startswith("--"))
    assert "%" not in body
    assert re.search(r"\$[A-Za-z_]*\$", body) is None
    assert set(re.findall(r"\b([A-Za-z_]+)\s*\(", body)) <= {
        "SUM",
        "COUNT",
        "MIN",
        "MAX",
        "COALESCE",
        "NULLIF",
        "CAST",
        "ANY",
        "IN",
    }
    projection = body.split("FROM")[0].removeprefix("SELECT ")
    for item in projection.split(","):
        assert "." in item


@pytest.mark.parametrize(
    "text",
    [
        "SELECT IFNULL(a.x, 0) FROM a",
        "SELECT a.x FROM a WHERE a.x = '%'",
        "SELECT x FROM a",
    ],
)
def test_query_scan_plants(text):
    with pytest.raises(AssertionError):
        scan_query(text)


def scan_folder(folder: Path):
    paths = list(folder.glob("sector_facts_*.sql"))
    if not paths:
        raise AssertionError("sector_facts SQL files missing")
    for path in paths:
        scan_query(path.read_text())


def test_every_query_prepares_on_embedded():
    from product.tests.sector_fixture import SECTOR_INVENTORY, licence_store

    from eii_product.store.parity import prepare_all

    with licence_store() as store:
        prepare_all(store, SECTOR_INVENTORY)


@pytest.mark.parametrize(
    "plant,reason",
    [
        ("division", "forbidden construct"),
        ("placeholder", "forbidden construct"),
        ("join", "order unproved"),
        ("contract", "query header invalid"),
    ],
)
def test_query_guard_plants(tmp_path, plant, reason):
    from eii_product.store import StoreRefusal
    from eii_product.store.registry import load_inventory, packaged_sql_dir

    name = "sector_facts_licence_local"
    source = packaged_sql_dir()
    text = (source / (name + ".sql")).read_text()
    if plant == "division":
        text = text.replace("p.active_count,", "p.active_count / 2 AS active_count,")
    elif plant == "placeholder":
        text = text.replace(":activity", ":undeclared")
    elif plant == "join":
        text = text.replace(
            "WHERE",
            "INNER JOIN pub_licence_active AS q ON p.activity_code = q.activity_code\nWHERE",
        )
    (tmp_path / "__init__.py").write_text("")
    (tmp_path / (name + ".sql")).write_text(text)
    if plant != "contract":
        (tmp_path / (name + ".toml")).write_text(
            (source / (name + ".toml")).read_text()
        )
    with pytest.raises(StoreRefusal, match=reason):
        lint_inventory(load_inventory(tmp_path))


def test_churn_whole_table_sum_has_one_row_order_proof(tmp_path):
    from eii_product.store.registry import load_inventory, packaged_sql_dir

    name = "sector_facts_churn_total"
    (tmp_path / "__init__.py").write_text("")
    (tmp_path / (name + ".toml")).write_text(
        (packaged_sql_dir() / "sector_facts_churn_national.toml").read_text()
    )
    (tmp_path / (name + ".sql")).write_text(
        "-- name: "
        + name
        + "\n-- params:\n-- returns: cancelled_count numeric\n-- order:\nSELECT SUM(p.cancelled_count) AS cancelled_count\nFROM pub_licence_cancelled AS p\n"
    )
    lint_inventory(load_inventory(tmp_path))


def test_scan_packaged_queries():
    scan_folder(repository_path("product/src/eii_product/store/sql", __file__))


def test_empty_sql_folder_is_refused(tmp_path):
    with pytest.raises(AssertionError, match=r"^sector_facts SQL files missing$"):
        scan_folder(tmp_path)
