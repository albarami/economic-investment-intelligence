"""Committed release contracts, never cache rows or producer execution.

Table inventory: assembly_native.read_native, Production.frame/register_tables/fsq/
busyness, assembly_layers.build_layers, COLLECTED_FAMILIES, series.FIELD_MAP,
and additions.build (S2-DRAWCLS; document 03 section 7.3 and owning-task sections).
"""

import ast
import re
from pathlib import Path

from custodian.tests.repository_root import repository_root

from eii_custodian.publicdata import assembly_reports as reports
from eii_custodian.publicdata.fetch.registry import COLLECTED_FAMILIES

ROOT = repository_root(Path(__file__))
PHASE_TABLES = {
    "reviewed_selections": (
        "fdi_projects",
        "pub_atlas_country_partner_product_year",
        "pub_atlas_country_product_year",
        "pub_atlas_cppy_country",
        "pub_atlas_cppy_product",
        "pub_atlas_cpy_country",
        "pub_atlas_cpy_product",
        "pub_baci_country",
        "pub_baci_product",
        "pub_baci_trade",
        "pub_comtrade_trade",
        "pub_gravity_bilateral",
        "pub_gravity_country",
        "pub_ilostat_benchmark",
        "pub_investqa_page",
        "pub_investqa_record",
        "pub_unctad_fdi_benchmark",
        "pub_wdi_benchmark",
        "pub_weo_benchmark",
    ),
    "frame": (
        "district",
        "gazetteer",
        "grid_cell",
        "municipality",
        "pub_census_district",
        "pub_census_national",
        "pub_census_zone",
        "pub_place",
        "pub_place_verification",
        "pub_population_municipality",
        "zone",
    ),
    "register_tables": ("pub_register_company", "pub_register_snapshot"),
    "gis_property_singles": (
        "gazetteer",
        "pub_address_point",
        "pub_bank_credit",
        "pub_completions_ext",
        "pub_coverage_ext",
        "pub_district_cooling",
        "pub_fdi_stats",
        "pub_health_centre",
        "pub_hotel_ext",
        "pub_jobseekers",
        "pub_land_price",
        "pub_parcel",
        "pub_poi_comm",
        "pub_price_ext",
        "pub_property_quarter",
        "pub_property_sale",
        "pub_rail_plan",
        "pub_survey_ext",
        "pub_talent_ext",
        "pub_tender",
        "pub_trade_ext",
        "pub_utilities_ext",
        "pub_zoning",
    ),
    "fsq": ("pub_place_fsq",),
    "series_stage": (
        "pub_customs_import",
        "pub_licence_active",
        "pub_licence_cancelled",
        "pub_licence_issued",
        "pub_sector_accounts",
        "pub_transit_monthly",
        "pub_wage_table",
        "pub_zone_utility",
    ),
    "additions": (
        "pub_active_nationality_occupation",
        "pub_active_sex_age",
        "pub_building_permits",
        "pub_census_2015_municipality",
        "pub_compensation_nationality",
        "pub_establishment_size",
        "pub_hotels_municipality",
        "pub_labour_sex_municipality",
        "pub_manufacturing",
        "pub_population_age",
        "pub_population_age_sex",
        "pub_property_resi",
        "pub_students",
        "pub_trade_logistics",
        "pub_trade_wr",
        "pub_venue_visits",
        "pub_visitor_markets",
    ),
    "busyness": ("pub_venue_busyness",),
}


def section(text: str, heading: str) -> str:
    match = re.search(r"^#{2,4} " + re.escape(heading) + r"$", text, re.M)
    assert match is not None, heading
    return re.split(r"\n#{2,4} ", text[match.end() :], maxsplit=1)[0]


def without_explanations(row: str) -> str:
    while re.search(r"\([^()]*\)", row):
        row = re.sub(r"\([^()]*\)", "", row)
    return row


def row_columns(row: str) -> set[str]:
    row = without_explanations(row)
    row = re.sub(r"on an? .*? row:", "", row)
    result = set()
    for clause in row.split(";"):
        prefix = re.match(r"\s*((?:`[a-z][a-z0-9_]*`(?:, | and |\s)*)+)", clause)
        result.update(re.findall(r"(?:, | and )`([a-z][a-z0-9_]*)`\s*$", clause))
        if prefix:
            result.update(re.findall(r"`([^`]+)`", prefix[0]))
    for phrase in ("the remaining `_id` fields ", "and the text fields "):
        if phrase in row:
            tail = row.split(phrase, 1)[1].split(" as ", 1)[0]
            result.update(re.findall(r"`([^`]+)`", tail))
    result.update(
        re.findall(r"`([a-z][a-z0-9_]*)`\s+(?:string|int|decimal|date|bool)", row)
    )
    return result


def tokens(text: str) -> set[str]:
    return set(re.findall(r"`([a-z][a-z0-9_]*)`", text))


def between(text: str, start: str, end: str) -> set[str]:
    return tokens(without_explanations(text.split(start, 1)[1].split(end, 1)[0]))


def native_columns(text: str) -> dict[str, set[str]]:
    """Read native prose lists plus their declared keys in 7.2 Table catalogue."""
    keys = {}
    for line in section(text, "7.2 Table catalogue").splitlines():
        if line.startswith("| `"):
            cells = line.split(" | ")
            keys[next(iter(tokens(cells[0])))] = tokens(cells[3])
    baci = section(text, "BACI columns and source chain (S2-T24)")
    gravity = section(text, "Gravity and Atlas columns and source chain (S2-T25)")
    result = {
        "pub_baci_trade": keys["pub_baci_trade"]
        | between(baci, "Trade\ncolumns additionally hold ", ". Country"),
        "pub_baci_country": keys["pub_baci_country"]
        | between(baci, "Country columns additionally\nhold ", ".\nProduct"),
        "pub_baci_product": keys["pub_baci_product"]
        | between(baci, "Product columns additionally hold ", ".\nLeading"),
        "pub_gravity_bilateral": between(
            gravity, "Gravity bilateral columns hold ", ". The three"
        ),
        "pub_gravity_country": between(
            gravity, "Country columns hold ", ". `hs_revision`"
        ),
        "pub_atlas_country_product_year": between(
            gravity, "country-product rows hold ", ". Atlas"
        ),
    }
    result["pub_atlas_country_partner_product_year"] = result[
        "pub_atlas_country_product_year"
    ] - {"country_code"} | between(
        gravity, "country-partner-product rows hold ", " in place"
    )
    for grain in ("cpy", "cppy"):
        for kind, label in (
            ("country", "source_name"),
            ("product", "source_description"),
        ):
            table = f"pub_atlas_{grain}_{kind}"
            result[table] = keys[table] | {"source_id", label}
    return result


def declared_fields(module: str, name: str) -> set[str]:
    tree = ast.parse(
        (ROOT / "custodian/src/eii_custodian/publicdata" / module).read_text()
    )
    row = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == name
    )
    return {
        node.target.id
        for node in row.body
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
    }


def contract_columns() -> dict[str, set[str]]:
    text = (ROOT / "docs/03_DATA_CONTRACTS.md").read_text()
    rows = {}
    for line in section(text, "7.3 Columns").splitlines():
        if line.startswith("| `"):
            table_cell, columns = line.split(" | ", 2)[:2]
            if "Release columns:" in columns:
                columns = columns.split("Release columns:", 1)[1]
            for table in re.findall(r"`([^`]+)`", table_cell):
                rows[table] = row_columns(columns)
    register = section(text, "Register file projections (S2-T49)")
    register = register.split("The retained commerce fields are ", 1)[1]
    rows["pub_register_company"] = set(
        re.findall(r"`([^`]+)`", register.split("`capital_qar` is nullable", 1)[0])
    )
    rows.update(native_columns(text))
    fields = declared_fields("benchmarks/contracts.py", "Benchmark")
    for table in PHASE_TABLES["reviewed_selections"]:
        if table.endswith("_benchmark"):
            rows[table] = fields
    return rows


def test_every_draw_contract_column_is_classified() -> None:
    columns = contract_columns()
    groups = (
        reports.MONEY_FIELDS,
        reports.RATIO_FIELDS,
        reports.COUNT_FIELDS,
        reports.ADMIN_FIELDS,
        reports.TEXT_FIELDS,
    )
    failures = []
    for tables in PHASE_TABLES.values():
        for table in tables:
            if table == "grid_cell":  # draw_tables explicitly excludes it.
                continue
            assert table in columns, table
            assert columns[table], table
            for field in sorted(columns[table]):
                if (
                    field == "field_value"
                    and table.removeprefix("pub_") in COLLECTED_FAMILIES
                ):
                    continue  # L-2309: per-cell registry kind, exercised separately.
                if sum(field in group for group in groups) != 1:
                    failures.append(table + "." + field)
    assert not failures, "unclassified or overlapping: " + ", ".join(
        sorted(set(failures))
    )


def test_nonleading_contract_lists_are_complete() -> None:
    columns = contract_columns()
    assert {
        "median_price",
        "median_price_per_ft2",
        "land_deal_count",
        "land_median_price_per_ft2",
        "price_basis",
    } <= columns["pub_property_quarter"]
    assert {
        "province",
        "parent_company_website",
        "project_type_id",
        "tech_level_id",
        "src_state_name",
    } <= columns["fdi_projects"]
    assert "buying_entity_ar" in columns["pub_tender"]


def test_native_emitted_columns_match_their_contracts() -> None:
    columns = contract_columns()
    models = {
        "baci": {"trade": "Trade", "country": "Country", "product": "Product"},
        "gravity": {"bilateral": "Bilateral", "country": "Country"},
        "atlas": {
            "country_product_year": "CountryProduct",
            "country_partner_product_year": "CountryPartnerProduct",
            "cpy_country": "Country",
            "cppy_country": "Country",
            "cpy_product": "Product",
            "cppy_product": "Product",
        },
    }
    for module, rows in models.items():
        for suffix, model in rows.items():
            table = f"pub_{module}_{suffix}"
            assert columns[table] == declared_fields(f"{module}/contracts.py", model), (
                table
            )
