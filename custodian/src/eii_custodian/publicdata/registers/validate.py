"""TST-196 schema and DAT-83 identifier checks before either release publishes."""

from __future__ import annotations

import re
from collections.abc import Iterator, Mapping, Sequence

from eii_custodian.publicdata.fetch.snapshots import SnapshotError, utc

from .contracts import (
    BARE_DIGITS,
    FIXED_TEXTS,
    FORMAT_ONLY_NUMBER,
    NUMERIC_COLUMNS,
    PREFIXES,
    ROW_KEY,
    TABLE_COLUMNS,
    TYPED_FIELDS,
    TYPED_SEQUENCES,
    RegisterError,
    company_key_ok,
    refuse,
)
from .parse import parse_value, validate_card
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
pub_rail_plan pub_accident_zone pub_health_centre pub_zoning pub_address_point pub_parcel pub_poi_comm
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
_ROW_TOKEN = re.compile(ROW_KEY.pattern.removesuffix(r"\Z"))


def _tokens(value: str) -> Iterator[str]:
    for pattern in (_DIGIT_TOKEN, _ROW_TOKEN):
        for token in pattern.finditer(value):
            yield token.group()


def _text(value: str, keys: frozenset[str]) -> None:
    if any(prefix in value for prefix in PREFIXES):
        refuse("identifier_prefix")
    if BARE_DIGITS.search(value):
        refuse("identifier_digit_run")
    if any(token in keys for token in _tokens(value)):
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


def _typed_keys(keys: frozenset[str]) -> frozenset[str]:
    """Decision 0105: the keys a typed field still meets (not short, not 19xx/20xx)."""
    return frozenset(key for key in keys if not FORMAT_ONLY_NUMBER.fullmatch(key))


def _field_format(kind: str, value: object) -> None:
    try:
        if kind == "count":
            valid = type(value) is int and value >= 0
        elif kind == "timestamp":
            valid = utc(value) is not None
        elif kind == "date_or_pending":
            valid = value == "pending" or (
                isinstance(value, str) and parse_value(value, "date") == value
            )
        elif kind in FIXED_TEXTS:
            valid = type(value) is str and value == FIXED_TEXTS[kind]
        else:
            valid = kind == "month" and month(value) == value
    except (RegisterError, SnapshotError):
        valid = False
    if not valid:
        refuse("typed_field_format")


def _typed_value(path: str, kind: str, value: object) -> None:
    """Decision 0105 item 1: a listed field's declared shape, before any traversal.

    A listed sequence must be a list or tuple whose every item has the format;
    any other listed field is one value, checked whole, so a list, tuple or
    mapping there fails its format (no format admits a container).
    """
    if path not in TYPED_SEQUENCES:
        _field_format(kind, value)
    elif isinstance(value, list | tuple):
        for item in value:
            _field_format(kind, item)
    else:
        refuse("typed_field_format")


def scan_metadata(value: object, keys: frozenset[str], path: str) -> None:
    """Scan a manifest or report as an artefact; a listed field is typed.

    `path` is the artefact and the mapping keys down to `value`; list positions
    are not part of it, and a key holding a dot ends typing below it. A listed
    field's shape and format are checked, never skipped, then it meets
    `_typed_keys`.
    """
    kind = TYPED_FIELDS.get(path)
    if kind is not None:
        _typed_value(path, kind, value)
        scan_artefact(value, _typed_keys(keys))
    elif isinstance(value, Mapping):
        for key, item in value.items():
            scan_artefact(key, keys)
            typed = path and "." not in str(key)
            scan_metadata(item, keys, f"{path}.{key}" if typed else "")
    elif isinstance(value, list | tuple):
        for item in value:
            scan_metadata(item, keys, path)
    else:
        scan_artefact(value, keys)


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


def _scan_release_value(value: object, keys: frozenset[str]) -> None:
    """DAT-11 / L-1288: a typed number is no identifier string, so no prefix or
    digit-run check; its tokens still meet every key (owner condition 1)."""
    if value is None or type(value) in (bool, int, float):
        if type(value) in (int, float) and any(
            token in keys for token in _tokens(str(value))
        ):
            refuse("registration_egress")
        return
    if isinstance(value, Mapping):
        for key, item in value.items():
            scan_artefact(key, keys)
            _scan_release_value(item, keys)
    elif isinstance(value, list | tuple):
        for item in value:
            _scan_release_value(item, keys)
    else:
        scan_artefact(value, keys)


def validate_release(
    tables: Mapping[str, Sequence[Mapping[str, object]]],
    frame: Frame,
    *,
    licences: frozenset[str] = frozenset(),
    withheld_registrations: frozenset[str] = frozenset(),
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
            if not company_key_ok(key):
                refuse("registration_format")
            assert isinstance(key, str)
            scan_artefact(key, withheld_registrations)
            keys.add(key)
            if table == "pub_register_company":
                current_keys.add(key)
            if "period" in row:
                # Decision 0105 (the owner's a3): a listed period column's
                # format, `YYYY-MM`, checked on every row before the scan.
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
                if ROW_KEY.fullmatch(key) and source != "biz_register":
                    refuse("registration_format")
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
    input_only_keys = licences | withheld_registrations
    egress_keys = frozen | input_only_keys
    # Decision 0105: a listed column admits only a short or year-shaped number.
    typed_keys = _typed_keys(egress_keys)
    banned = {
        "person_id",
        "establishment_id",
        "legal_entity_id",
        "group_id",
        "file_id",
        "firm_key",
        "licence_number",
    }
    for table, rows in tables.items():
        for row in rows:
            for column, value in row.items():
                if column in banned or (
                    column == "registration_number" and table not in TABLE_COLUMNS
                ):
                    refuse("release_identifier_column")
                scan_artefact(column, egress_keys)
                if column == "registration_number" and table in TABLE_COLUMNS:
                    continue
                # DAT-11 scans every column; numbers meet keys but no string
                # check. A listed column's format was checked in the loop above.
                listed = f"{table}.{column}" in TYPED_FIELDS
                _scan_release_value(value, typed_keys if listed else egress_keys)
    return frozen
