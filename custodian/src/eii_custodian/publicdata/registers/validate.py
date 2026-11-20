"""TST-196 schema and DAT-83 identifier checks before either release publishes."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence

from .contracts import (
    BARE_DIGITS,
    NUMERIC_COLUMNS,
    PREFIXES,
    REGISTRATION,
    TABLE_COLUMNS,
    refuse,
)
from .parse import validate_card
from .provenance import Frame, month

# Document 03 section 7.2. A drift test binds this closed name list to the pack.
# The other builders still own their table schemas and privacy checks.
RELEASE_TABLES = frozenset(
    """
grid_cell release_unit unit_member zone district municipality gazetteer road_link
resident_pay worker_pay home_area_share outlet_register occupation_pay
register_company_list month_change presence_count flow_hourly presence_split
flow_split traffic_hourly access_score pub_licence_active pub_licence_cancelled
pub_licence_issued pub_zone_utility pub_transit_monthly pub_sector_accounts
pub_wage_table pub_customs_import pub_property_sale pub_census_zone
pub_population_municipality pub_census_national pub_census_district pub_place
pub_place_verification pub_register_company pub_register_snapshot pub_hotel_monthly
pub_price_index pub_property_resi pub_property_quarter pub_land_price pub_bank_credit
pub_rail_plan pub_health_centre pub_zoning pub_address_point pub_parcel pub_poi_comm
pub_tender pub_district_cooling pub_completions_ext pub_coverage_ext pub_fdi_stats
pub_hotel_ext pub_jobseekers pub_price_ext pub_survey_ext pub_talent_ext pub_trade_ext
pub_utilities_ext pub_venue_visits pub_building_permits pub_establishment_size
pub_manufacturing pub_trade_wr pub_population_age pub_hotels_municipality
pub_trade_logistics pub_census_2015_municipality pub_labour_sex_municipality
pub_population_age_sex pub_active_sex_age pub_active_nationality_occupation
pub_compensation_nationality pub_students pub_visitor_markets fdi_projects
pub_investqa_record pub_investqa_page zone_type access_score_grid pub_venue_busyness
pub_night_lights pub_place_fsq pub_comtrade_trade pub_pop_agesex_grid graph_node
graph_edge fact_lineage source_registry rules_version suppression_reason survival_report
""".split()
)
_DIGIT_TOKEN = re.compile(r"[0-9]+(?:/[0-9]+)?")


def _text(value: str, keys: frozenset[str]) -> None:
    if any(prefix in value for prefix in PREFIXES):
        refuse("identifier_prefix")
    if BARE_DIGITS.search(value):
        refuse("identifier_digit_run")
    if any(token.group() in keys for token in _DIGIT_TOKEN.finditer(value)):
        refuse("registration_egress")


def scan_artefact(value: object, keys: frozenset[str]) -> None:
    """Refuse source keys in a report, manifest, model payload, log or bundle.

    A validated full SHA-256 is a digest, not a copied registration token.
    Mapping keys are scanned as well as values; no diagnostic echoes a match.
    """
    if isinstance(value, bytes):
        try:
            scan_artefact(value.decode("utf-8"), keys)
        except UnicodeError:
            refuse("artefact_encoding")
    elif isinstance(value, str):
        if re.fullmatch(r"[a-f0-9]{64}", value) is None:
            _text(value, keys)
    elif isinstance(value, Mapping):
        for key, item in value.items():
            scan_artefact(key, keys)
            scan_artefact(item, keys)
    elif isinstance(value, list | tuple):
        for item in value:
            scan_artefact(item, keys)
    elif type(value) is int or type(value) is float:
        _text(str(value), keys)
    elif value is not None and type(value) is not bool:
        refuse("artefact_type")


def scan_content(value: object, content: frozenset[str]) -> None:
    """Card names and published addresses belong in tables, never metadata."""
    if isinstance(value, bytes):
        try:
            scan_content(value.decode("utf-8"), content)
        except UnicodeError:
            refuse("artefact_encoding")
    elif isinstance(value, str):
        if re.fullmatch(r"[a-f0-9]{64}", value) is None and any(
            text in value for text in content
        ):
            refuse("register_content_egress")
    elif isinstance(value, Mapping):
        for key, item in value.items():
            scan_content(key, content)
            scan_content(item, content)
    elif isinstance(value, list | tuple):
        for item in value:
            scan_content(item, content)


def validate_release(
    tables: Mapping[str, Sequence[Mapping[str, object]]],
    frame: Frame,
) -> frozenset[str]:
    if not set(tables) <= RELEASE_TABLES:
        refuse("release_table")
    if not {"pub_register_company", "pub_register_snapshot"} <= tables.keys():
        refuse("release_tables_missing")
    keys: set[str] = set()
    current_keys: set[str] = set()
    owners: dict[str, str] = {}
    for table, rows in tables.items():
        if table not in TABLE_COLUMNS:
            continue
        seen: set[tuple[object, ...]] = set()
        for row in rows:
            if set(row) != set(TABLE_COLUMNS[table]):
                refuse("release_schema")
            key = row["registration_number"]
            if (
                not isinstance(key, str)
                or REGISTRATION.fullmatch(key) is None
                or len(key) > 10
            ):
                refuse("registration_format")
            keys.add(key)
            if table == "pub_register_company":
                current_keys.add(key)
            if "period" in row:
                period = month(row["period"])
                if table == "pub_register_snapshot" and period < "2026-11":
                    refuse("snapshot_month")
            if table != "register_company_list":
                source = row["source_id"]
                if not isinstance(source, str) or source not in {
                    "biz_register",
                    "fc_register",
                }:
                    refuse("release_source")
                if key in owners and owners[key] != source:
                    refuse("ambiguous_cross_source_key")
                owners[key] = source
            identity = (
                (key, row["period"]) if table == "pub_register_snapshot" else (key,)
            )
            if identity in seen:
                refuse("release_duplicate_key")
            seen.add(identity)
            if table == "register_company_list":
                count, reason = row["employee_count"], row["suppression_reason_code"]
                if count is None:
                    if reason != "CARRIED_FORWARD":
                        refuse("release_count")
                elif type(count) is not int or count < 0 or reason is not None:
                    refuse("release_count")
                continue
            cell = row["registered_cell"]
            if cell is not None and (type(cell) is not int or cell not in frame.cells):
                refuse("release_cell")
            for name, value in row.items():
                if (
                    name != "registered_cell"
                    and not (
                        table == "pub_register_company" and name in NUMERIC_COLUMNS
                    )
                    and value is not None
                    and not isinstance(value, str)
                ):
                    refuse("release_type")
            if table == "pub_register_company":
                if not row["name_ar"] and not row["name_en"]:
                    refuse("release_name")
                validate_card(row, frame)
    for row in tables.get("register_company_list", ()):
        if row["registration_number"] not in current_keys:
            refuse("list_company_missing")
    frozen = frozenset(keys)
    banned = {
        "person_id",
        "establishment_id",
        "legal_entity_id",
        "group_id",
        "file_id",
        "firm_key",
    }
    for table, rows in tables.items():
        for row in rows:
            for column, value in row.items():
                if column in banned or (
                    column == "registration_number" and table not in TABLE_COLUMNS
                ):
                    refuse("release_identifier_column")
                scan_artefact(column, frozen)
                if column == "registration_number" and table in TABLE_COLUMNS:
                    continue
                # DAT-11 scans every string column. Typed numeric Public values
                # (including cell keys, capital, counts and coordinates) are not
                # identifier strings. Non-key card strings get the same scan.
                if isinstance(value, str):
                    _text(value, frozen)
    return frozen
