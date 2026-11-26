"""TST-196 schema and DAT-83 identifier checks before either release publishes."""

from __future__ import annotations

import re
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass

from eii_custodian.publicdata.fetch.snapshots import SnapshotError, utc

from .contracts import (
    APPROVED_RECEIPT_WORDING,
    BARE_DIGITS,
    DIGEST_FIELDS,
    FIXED_METADATA,
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
from .provenance import Capture, Frame, month

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
pub_night_lights pub_place_fsq pub_comtrade_trade pub_baci_trade pub_baci_country
pub_baci_product pub_gravity_bilateral pub_gravity_country
pub_atlas_country_product_year pub_atlas_country_partner_product_year
pub_atlas_cpy_country pub_atlas_cpy_product pub_atlas_cppy_country
pub_atlas_cppy_product pub_wdi_benchmark pub_unctad_fdi_benchmark pub_weo_benchmark
pub_ilostat_benchmark pub_pop_agesex_grid graph_node
graph_edge fact_lineage source_registry rules_version suppression_reason survival_report
""".split()
)
_DIGIT_TOKEN = re.compile(r"[0-9]+(?:/[0-9]+)?")
_ROW_TOKEN = re.compile(ROW_KEY.pattern.removesuffix(r"\Z"))
_DIGEST = re.compile(r"[a-f0-9]{64}")


_BANNED_COLUMNS = frozenset(
    {
        "person_id",
        "establishment_id",
        "legal_entity_id",
        "group_id",
        "file_id",
        "firm_key",
        "licence_number",
    }
)


def _digest_field(path: str, value: object) -> bool:
    """Decision 0119 item 6: true for a named digest field, whose value must be
    one SHA-256 and is then exempt from the scans; false for any other field."""
    if path not in DIGEST_FIELDS:
        return False
    if type(value) is not str or _DIGEST.fullmatch(value) is None:
        refuse("digest_field_format")
    return True


def _child(path: str, key: object) -> str:
    """The path below a mapping key; a key holding a dot ends the path."""
    return f"{path}.{key}" if path and "." not in str(key) else ""


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

    Every string is scanned, even one shaped like a digest; only a caller that
    knows a named digest field (`_digest_field`) skips it. Mapping keys are
    scanned as well as values; no diagnostic echoes a match.
    """
    if isinstance(value, bytes):
        try:
            scan_artefact(value.decode("utf-8"), keys)
        except UnicodeError:
            refuse("artefact_encoding")
    elif isinstance(value, str):
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


@dataclass(frozen=True)
class MetadataInputs:
    """Independent build inputs, never counts read back from checked metadata."""

    current: tuple[Capture, ...]
    snapshots: tuple[Capture, ...]
    tables: Mapping[str, Sequence[Mapping[str, object]]]


def _metadata_count(
    authority: str, path: str, inputs: MetadataInputs, scope: Mapping[str, object]
) -> int | None:
    if authority == "table_rows":
        name = scope.get("name")
        rows = inputs.tables.get(name) if isinstance(name, str) else None
        return len(rows) if rows is not None else None  # unit: rows
    receipt = scope.get("receipt")
    if not isinstance(receipt, Mapping):
        return None
    batch = {"current": inputs.current, "snapshot": inputs.snapshots}.get(
        str(scope.get("use")), ()
    )
    role = path.split(".")[-2]
    for item in batch:
        if (item.source_id, item.period) == (
            receipt.get("source_id"),
            receipt.get("period"),
        ):
            body = item.files.get(role)
            return len(body) if isinstance(body, bytes) else None  # unit: bytes
    return None


def _metadata_verdict(
    value: object,
    path: str,
    inputs: MetadataInputs | None,
    scope: Mapping[str, object],
) -> str | None:
    """None: ordinary scan; empty: exact exemption; otherwise scan then refuse."""
    rule = FIXED_METADATA.get(path)
    if rule is None or rule[0] == "schema_keys":
        return None
    kind, authority = rule
    if kind == "exact_count":
        if inputs is None:
            return None  # A raw scanner has no independent bundle quantity.
        assert isinstance(authority, str)
        expected = _metadata_count(authority, path, inputs, scope)
        return (
            ""
            if type(value) is int and value == expected
            else "metadata_count_mismatch"
        )
    approved: Sequence[str | None] | frozenset[str]
    if authority == "receipt_wording":
        receipt = scope.get("receipt")
        source = receipt.get("source_id") if isinstance(receipt, Mapping) else None
        wording = (
            APPROVED_RECEIPT_WORDING.get(source, {}) if isinstance(source, str) else {}
        )
        approved = (wording.get(path.rsplit(".", 1)[-1]),)
    else:
        assert isinstance(authority, frozenset)
        approved = authority
    if type(value) is str and value in approved:
        return ""
    return (
        None
        if kind == "approved_exempt" or inputs is None
        else "metadata_fixed_text_mismatch"
    )


def _metadata_scope(
    path: str, value: object, scope: Mapping[str, object]
) -> Mapping[str, object]:
    if path in {"manifest.receipts", "manifest.tables"} and isinstance(value, Mapping):
        return value
    return scope


def _metadata_item_path(path: str) -> str:
    """A fixed scalar never grants its exemption to items of a wrong-shape list."""
    rule = FIXED_METADATA.get(path)
    return "" if rule is not None and rule[0] != "schema_keys" else path


def _schema_key(
    path: str,
    key: object,
    keys: frozenset[str],
    content: frozenset[str],
    *,
    closed: bool = True,
) -> bool:
    rule = FIXED_METADATA.get(path)
    if rule is None or rule[0] != "schema_keys":
        return False
    if type(key) is str and key in rule[1]:
        return True
    if not closed:
        return False
    scan_artefact(key, keys)
    scan_content(key, content)
    refuse("metadata_key_not_schema")


def scan_metadata(
    value: object,
    keys: frozenset[str],
    path: str,
    *,
    inputs: MetadataInputs | None = None,
    content: frozenset[str] = frozenset(),
    _scope: Mapping[str, object] | None = None,
) -> None:
    """Scan a manifest or report as an artefact; a listed field is typed.

    `path` is the artefact and the mapping keys down to `value`; list positions
    are not part of it, and a key holding a dot ends typing below it. A listed
    field's shape and format are checked, never skipped, then it meets
    `_typed_keys`. Decision 0124 exempts exact approved labels and schema keys;
    bound `inputs` additionally enforce fixed-label mismatches and recompute
    counts. A mismatch meets the legacy scans first, including `content`.
    Without inputs this remains a raw scanner and never exempts counts.
    A named digest field is checked and not scanned.
    """
    scope = _metadata_scope(path, value, _scope or {})
    verdict = _metadata_verdict(value, path, inputs, scope)
    if verdict is not None:
        if verdict:
            # L-2139: preserve existing reasons before the closed mismatch.
            scan_metadata(value, keys, path)
            scan_content(value, content, path)
            refuse(verdict)
        return
    kind = TYPED_FIELDS.get(path)
    if _digest_field(path, value):
        return
    if kind is not None:
        _typed_value(path, kind, value)
        scan_artefact(value, _typed_keys(keys))
    elif isinstance(value, Mapping):
        for key, item in value.items():
            if not _schema_key(path, key, keys, content):
                scan_artefact(key, keys)
            scan_metadata(
                item,
                keys,
                _child(path, key),
                inputs=inputs,
                content=content,
                _scope=scope,
            )
    elif isinstance(value, list | tuple):
        for item in value:
            scan_metadata(
                item,
                keys,
                _metadata_item_path(path),
                inputs=inputs,
                content=content,
                _scope=scope,
            )
    else:
        scan_artefact(value, keys)


def scan_content(
    value: object,
    content: frozenset[str],
    path: str = "",
    *,
    inputs: MetadataInputs | None = None,
    _scope: Mapping[str, object] | None = None,
) -> None:
    """Card names and published addresses belong in tables, never metadata.

    `path` names the field as in `scan_metadata`; exact metadata and named
    digests share its exemptions. Run `scan_metadata` with bound inputs first
    to enforce mismatches. With no path every string is scanned.
    """
    scope = _metadata_scope(path, value, _scope or {})
    if _metadata_verdict(value, path, inputs, scope) == "":
        return
    if _digest_field(path, value):
        return
    if isinstance(value, bytes):
        try:
            scan_content(value.decode("utf-8"), content)
        except UnicodeError:
            refuse("artefact_encoding")
    elif isinstance(value, str):
        if any(text in value for text in content):
            refuse("register_content_egress")
    elif isinstance(value, Mapping):
        for key, item in value.items():
            if not _schema_key(path, key, frozenset(), content):
                scan_content(key, content)
            scan_content(item, content, _child(path, key), inputs=inputs, _scope=scope)
    elif isinstance(value, list | tuple):
        for item in value:
            scan_content(
                item, content, _metadata_item_path(path), inputs=inputs, _scope=scope
            )


def _scan_release_value(value: object, keys: frozenset[str]) -> None:
    """DAT-11 / L-1288: a typed number is no identifier string, so no prefix or
    digit-run check; its tokens still meet every key given (owner condition 1),
    the row's own licences and all withheld duplicates under proposed decision 0123."""
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


def _scan_release_row(
    table: str,
    row: Mapping[str, object],
    licences_by_registration: Mapping[str, frozenset[str]],
    withheld_registrations: frozenset[str],
) -> None:
    """Proposed decision 0123: own licences plus every withheld duplicate."""
    registration = row.get("registration_number")
    own = (
        licences_by_registration.get(registration, frozenset())
        if isinstance(registration, str)
        else frozenset()
    )
    egress_keys = own | withheld_registrations
    typed_keys = _typed_keys(egress_keys)
    for column, value in row.items():
        if column in _BANNED_COLUMNS or (
            column == "registration_number" and table not in TABLE_COLUMNS
        ):
            refuse("release_identifier_column")
        if not _schema_key(
            f"released.{table}", column, egress_keys, frozenset(), closed=False
        ):
            scan_artefact(column, egress_keys)
        if column == "registration_number" and table in TABLE_COLUMNS:
            continue
        if _digest_field(f"{table}.{column}", value):
            continue
        # DAT-11 scans every column; numbers meet keys but no string
        # check. The caller validates listed formats before this row scan.
        listed = f"{table}.{column}" in TYPED_FIELDS
        _scan_release_value(value, typed_keys if listed else egress_keys)


def validate_release(
    tables: Mapping[str, Sequence[Mapping[str, object]]],
    frame: Frame,
    *,
    licences_by_registration: Mapping[str, frozenset[str]] | None = None,
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
    for table, rows in tables.items():
        for row in rows:
            _scan_release_row(
                table, row, licences_by_registration or {}, withheld_registrations
            )
    return frozen
