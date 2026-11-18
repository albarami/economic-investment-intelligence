"""Read an explicitly selected S2-T01 receipt; copy confirmed fields only."""

from __future__ import annotations

import csv
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path

from eii_custodian.publicdata.fetch.registry import Entry
from eii_custodian.publicdata.fetch.snapshots import read_snapshot


def selected_body(
    cache: Path, entry: Entry, digest: str
) -> tuple[bytes, dict[str, object]]:
    """No latest-file search and no network; bind the body to its exact receipt."""
    if re.fullmatch(r"[a-f0-9]{64}", digest) is None:
        raise ValueError("invalid selected hash")
    selected = read_snapshot(cache / entry.key, digest)
    body, receipt = selected.body, selected.sidecar
    if not isinstance(receipt, dict):
        raise ValueError("selected receipt mismatch")
    expected = {
        "sha256": digest,
        "key": entry.key,
        "source_id": entry.source_id,
        "slug": entry.slug,
        "licence_id": entry.licence_id,
        "licence_basis": entry.licence_basis,
        "release_tables": list(entry.release_tables),
        "switched_off": False,
    }
    if any(receipt.get(key) != value for key, value in expected.items()):
        raise ValueError("selected receipt mismatch")
    for key in ("publisher", "retrieved_utc", "licence_id", "fetch_url"):
        value = receipt.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError("incomplete receipt")
    return body, receipt


def selected_source(
    cache: Path, entry: Entry, digest: str
) -> tuple[list[dict[str, object]], dict[str, object]]:
    """Decode JSON rows after the shared selected body/receipt checks."""
    body, receipt = selected_body(cache, entry, digest)
    rows = json.loads(body, parse_float=Decimal)
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        raise ValueError("source must contain rows")
    return rows, receipt


def parse_rows(
    entry: Entry, rows: Sequence[dict[str, object]], field_map: Mapping[str, str]
) -> list[dict[str, object]]:
    """Rename fields without converting values; unknown fields fail the whole table.

    Generic exact-copy helper. The confirmed export adapter below additionally
    checks nullable types and the closed source-to-contract mapping.
    """
    columns = dict(entry.columns)
    if not columns:
        raise ValueError("unconfirmed source columns")
    if set(field_map) != set(columns) or len(set(field_map.values())) != len(field_map):
        raise ValueError("incomplete or duplicate field mapping")
    result = []
    for row in rows:
        if set(row) != set(columns):
            raise ValueError(
                "unknown or missing source fields: "
                + ",".join(sorted(set(row) ^ set(columns)))
            )
        for key, kind in columns.items():
            value = row[key]
            valid = {
                "string": isinstance(value, str),
                "integer": type(value) is int,
                "number": type(value) in (int, Decimal),
            }
            if not valid[kind]:
                raise ValueError("source field type mismatch")
        copied = {target: row[source] for source, target in field_map.items()}
        if entry.source_id in {"wage_occ", "wage_act"}:
            if "table_code" in copied:
                raise ValueError("table identity comes from the source registry")
            copied["table_code"] = entry.source_id
        result.append(copied)
    return result


# Lead-confirmed shapes, S2-T03 continuation; document 03 contract columns.
# UNRESOLVED entries are evidence only and can never become a contract value.
FIELD_MAP: dict[str, dict[str, tuple[str, str]]] = {
    "lic_active": {
        "lbldy": ("pub_licence_active", "municipality_code"),
        "rmz_lnsht_ltjry": ("pub_licence_active", "activity_code"),
        "lnsht_ltjry": ("pub_licence_active", "activity_name_ar"),
        "dd_lrkhs_lnsht": ("pub_licence_active", "active_count"),
    },
    "lic_cancelled": {
        "sn_llg": ("pub_licence_cancelled", "period"),
        "shhr_llg": ("pub_licence_cancelled", "period"),
        "lbldy": ("pub_licence_cancelled", "municipality_code"),
        "rmz_lnsht_ltjry": ("pub_licence_cancelled", "activity_code"),
        "sm_lnsht_ltjry": ("pub_licence_cancelled", "EVIDENCE_ONLY:activity_name_ar"),
        "dd_lrkhs_lmlg": ("pub_licence_cancelled", "cancelled_count"),
    },
    "lic_issued": {
        "sn_lsdr": ("pub_licence_issued", "period"),
        "shhr_lsdr": ("pub_licence_issued", "period"),
        "lbldy": ("pub_licence_issued", "municipality_code"),
        "rmz_lnsht_ltjry": ("pub_licence_issued", "activity_code"),
        "sm_lnsht_ltjry": ("pub_licence_issued", "EVIDENCE_ONLY:activity_name_ar"),
        "dd_lrkhs_lsdr": ("pub_licence_issued", "issued_count"),
    },
    "cus_imp_2025": {
        "year": ("pub_customs_import", "period"),
        "quarter": ("pub_customs_import", "period"),
        "lrb": ("pub_customs_import", "period"),
        "month": ("pub_customs_import", "period"),
        "harmonized_system_code": ("pub_customs_import", "tariff_code"),
        "details": ("pub_customs_import", "description_en"),
        "ltfsyl": ("pub_customs_import", "description_ar"),
        "country_of_origin": ("pub_customs_import", "origin_iso3"),
        "dwl_lmnsh": ("pub_customs_import", "origin_iso3"),
        "quantity": ("pub_customs_import", "quantity"),
        "weight_in_kilograms": ("pub_customs_import", "weight_kg"),
        "value_in_qatari_riyals": ("pub_customs_import", "value_qar"),
    },
    "cus_imp_2019": {
        "lsn_year": ("pub_customs_import", "period"),
        "lrb_quarter": ("pub_customs_import", "period"),
        "lshhr_month": ("pub_customs_import", "period"),
        "hs8": ("pub_customs_import", "tariff_code"),
        "ltfsyl": ("pub_customs_import", "description_ar"),
        "details": ("pub_customs_import", "description_en"),
        "dwl_lmnsh": ("pub_customs_import", "origin_iso3"),
        "country_of_origin": ("pub_customs_import", "origin_iso3"),
        "quantity": ("pub_customs_import", "quantity"),
        "weight_kg": ("pub_customs_import", "weight_kg"),
        "value_qr": ("pub_customs_import", "value_qar"),
    },
    "sec_hr_ind": {
        "year": ("pub_sector_accounts", "period"),
        "activity_code": ("pub_sector_accounts", "activity_code"),
        "main_economic_activity": ("pub_sector_accounts", "activity_code:label_en"),
        "lnsht_lqtsdy_lry_ysy": ("pub_sector_accounts", "activity_code:label_ar"),
        "operating_surplus_value_in_1_000_qr": (
            "pub_sector_accounts",
            "value:operating_surplus",
        ),
        "compensation_of_employees_value_in_1_000_qr": (
            "pub_sector_accounts",
            "value:compensation",
        ),
        "value_added_per_worker_qr": (
            "pub_sector_accounts",
            "value:value_added_per_worker",
        ),
        "productivity_of_employee_qr": (
            "pub_sector_accounts",
            "value:productivity_of_employee",
        ),
        "percentage_of_intermediate_services_to_output": (
            "pub_sector_accounts",
            "value:services_share",
        ),
        "percentage_of_intermediate_goods_to_output": (
            "pub_sector_accounts",
            "value:goods_share",
        ),
        "average_annual_wage_qr": ("pub_sector_accounts", "value:average_annual_wage"),
    },
    "sec_hr_goods": {
        "year": ("pub_sector_accounts", "period"),
        "activity_code": ("pub_sector_accounts", "activity_code"),
        "type_of_commodity": ("pub_sector_accounts", "indicator"),
        "nw_lsl": ("pub_sector_accounts", "indicator:label_ar"),
        "main_economic_activity": ("pub_sector_accounts", "activity_code:label_en"),
        "lnsht_lqtsdy_lry_ysy": ("pub_sector_accounts", "activity_code:label_ar"),
        "estimates_of_intermediate_goods_value_value_in_1_000_qr": (
            "pub_sector_accounts",
            "value:intermediate_goods",
        ),
    },
    "sec_hr_serv": {
        "year": ("pub_sector_accounts", "period"),
        "activity_code": ("pub_sector_accounts", "activity_code"),
        "main_economic_activity": ("pub_sector_accounts", "activity_code:label_en"),
        "lnsht_lqtsdy_lry_ysy": ("pub_sector_accounts", "activity_code:label_ar"),
        "type_of_service": ("pub_sector_accounts", "indicator"),
        "nw_lkhdm": ("pub_sector_accounts", "indicator:label_ar"),
        "estimates_of_intermediate_services_value_value_in_1_000_qr": (
            "pub_sector_accounts",
            "value:intermediate_services",
        ),
    },
    "sec_hr_size": {
        "year": ("pub_sector_accounts", "period"),
        "activity_code": ("pub_sector_accounts", "activity_code"),
        "main_economic_activity": ("pub_sector_accounts", "activity_code:label_en"),
        "lnsht_lqtsdy_lry_ysy": ("pub_sector_accounts", "activity_code:label_ar"),
        "size_of_establishment": ("pub_sector_accounts", "indicator"),
        "hjm_lmnsh": ("pub_sector_accounts", "indicator:label_ar"),
        "number_of_employees": ("pub_sector_accounts", "value:employees"),
        "number_of_establishments": ("pub_sector_accounts", "value:establishments"),
    },
    "wage_occ": {
        "year": ("pub_wage_table", "period"),
        "gender": ("pub_wage_table", "breakdown_key"),
        "lnw": ("pub_wage_table", "breakdown_key:label_ar"),
        "occupation": ("pub_wage_table", "breakdown_key"),
        "lmhn": ("pub_wage_table", "breakdown_key:label_ar"),
        "paid_employment_workers": ("pub_wage_table", "value:paid_workers"),
        "monthly_average_wage_qr": ("pub_wage_table", "value:monthly_average_wage"),
    },
    "wage_act": {
        "year": ("pub_wage_table", "period"),
        "gender": ("pub_wage_table", "breakdown_key"),
        "lnw": ("pub_wage_table", "breakdown_key:label_ar"),
        "economic_activity": ("pub_wage_table", "breakdown_key"),
        "lnsht_lqtsdy": ("pub_wage_table", "breakdown_key:label_ar"),
        "paid_employment_workers": ("pub_wage_table", "value:paid_workers"),
        "monthly_average_wage_qr": ("pub_wage_table", "value:monthly_average_wage"),
    },
    "util_elec": {
        "year": ("pub_zone_utility", "period"),
        "zone_number": ("pub_zone_utility", "zone_code"),
        "value": ("pub_zone_utility", "value"),
    },
    "transit_monthly": {
        "year": ("pub_transit_monthly", "period"),
        "month": ("pub_transit_monthly", "period"),
        "lshhr": ("pub_transit_monthly", "period"),
        "public_transport_buses": ("pub_transit_monthly", "riders:bus"),
        "doha_metro": ("pub_transit_monthly", "riders:metro"),
        "lusail_tram": ("pub_transit_monthly", "riders:tram"),
    },
}
NULLABLE = {
    "lic_cancelled": ("sn_llg", "shhr_llg"),
    "cus_imp_2025": ("country_of_origin", "dwl_lmnsh"),
    "cus_imp_2019": ("dwl_lmnsh", "country_of_origin"),
}


def mapping_gaps(source: str) -> tuple[str, ...]:
    """Known absent values use nulls and coverage reports, never fabricated fields."""
    return ()


def confirmed_rows(
    entry: Entry, rows: Sequence[dict[str, object]]
) -> list[dict[str, object]]:
    """Check every row, naming every unknown, missing or retyped field."""
    mapping = FIELD_MAP[entry.source_id]
    columns = dict(entry.columns)
    if set(columns) != set(mapping):
        raise ValueError(
            entry.source_id
            + " registry fields: "
            + ",".join(sorted(set(columns) ^ set(mapping)))
        )
    for row in rows:
        if set(row) != set(mapping):
            raise ValueError(
                entry.source_id
                + " source fields: "
                + ",".join(sorted(set(row) ^ set(mapping)))
            )
        for field, kind in columns.items():
            value = row[field]
            if value is None and field in NULLABLE.get(entry.source_id, ()):
                continue
            valid = {
                "string": isinstance(value, str),
                "integer": type(value) is int,
                "number": type(value) in (int, Decimal),
            }
            if not valid[kind]:
                raise ValueError(entry.source_id + " field type: " + field)
    return [dict(row) for row in rows]


MONTHS = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)
MONTH_FIELDS = {
    "transit_monthly": "month",
    "cus_imp_2025": "month",
    "cus_imp_2019": "lshhr_month",
    "lic_cancelled": "shhr_llg",
    "lic_issued": "shhr_lsdr",
}


def source_period(source: str, year: object, month: object) -> str | None:
    """Source-specific forms confirmed by ruling L-203, R1; no guessed dates."""
    if source == "lic_cancelled" and (year in (None, "") or month is None):
        if year not in (None, "") and re.fullmatch(r"[0-9]{4}", str(year)) is None:
            raise ValueError("lic_cancelled sn_llg: four digits required")
        if month is not None and (
            type(month) is not int or not 1 <= int(str(month)) <= 12
        ):
            raise ValueError("lic_cancelled shhr_llg: integer month required")
        return None
    if re.fullmatch(r"[0-9]{4}", str(year)) is None:
        raise ValueError(source + " year: four digits required")
    field = MONTH_FIELDS[source]
    if source == "transit_monthly":
        if month not in MONTHS:
            raise ValueError(source + " " + field + ": English month name required")
        number = MONTHS.index(str(month)) + 1
    elif source == "cus_imp_2019":
        if (
            type(month) not in (int, Decimal)
            or not Decimal(str(month)).is_finite()
            or Decimal(str(month)) != Decimal(str(month)).to_integral_value()
        ):
            raise ValueError(source + " " + field + ": zero fraction required")
        number = int(Decimal(str(month)))
    else:
        if type(month) is not int:
            raise ValueError(source + " " + field + ": integer required")
        number = int(str(month))
    if not 1 <= number <= 12:
        raise ValueError(source + " " + field + ": outside month range")
    return f"{year}-{number:02}"


@dataclass(frozen=True)
class Municipality:
    """S2-T02 boundary-frame input: official code and exact adm1_name1 text."""

    code: str
    name_ar: str


def country_crosswalk(*, aliases: Path | None = None) -> dict[str, str | None]:
    """ISO reference plus explicit source aliases; unmatched names stay null."""
    root = Path(__file__).resolve().parents[4] / "publicdata/review"
    with (root / "country_iso3.csv").open(newline="", encoding="utf-8") as stream:
        countries: dict[str, str | None] = {
            row["name_en"]: row["iso3"] for row in csv.DictReader(stream)
        }
    codes = set(countries.values())
    alias_path = root / "country_aliases.csv" if aliases is None else aliases
    with alias_path.open(newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            if not row["iso3"]:
                if row.get("reason") not in {
                    "ambiguous",
                    "no_code_in_reference",
                    "not_a_country",
                    "part_of_a_country",
                }:
                    raise ValueError("country alias: invalid unattributed reason")
            elif row["iso3"] not in codes:
                raise ValueError("country alias: absent reference code")
            if row["name_en"] in countries:
                raise ValueError("country alias: repeated country name")
            countries[row["name_en"]] = row["iso3"] or None
    return countries


def customs_code(source: str, value: object) -> str | None:
    """Restore only the explicitly authorised dropped leading zero (R2)."""
    field = "hs8" if source == "cus_imp_2019" else "harmonized_system_code"
    text = str(value)
    if source == "cus_imp_2019":
        if not isinstance(value, str) or re.fullmatch(r"[0-9]{8}", text) is None:
            raise ValueError(
                source + " " + field + ": expected eight digits; lengths require review"
            )
        return text
    if type(value) is not int or re.fullmatch(r"[0-9]+", text) is None:
        raise ValueError(source + " " + field + ": integer code required")
    if len(text) == 1:
        return None
    if len(text) not in (11, 12):
        raise ValueError(source + " " + field + ": unexpected code length")
    return text.zfill(12)


def municipality_names(
    frame: Sequence[Municipality], review: Path | None = None
) -> dict[str, str]:
    """Exact frame names, followed only by explicitly reviewed alias rows."""
    names = {item.name_ar: item.code for item in frame}
    path = (
        review
        if review is not None
        else Path(__file__).resolve().parents[4]
        / "publicdata/review/municipality_aliases.json"
    )
    for row in json.loads(path.read_text()):
        if (
            not row.get("reviewer_role")
            or not row.get("review_date")
            or row.get("frame_name_ar") not in names
        ):
            raise ValueError("municipality alias: missing review or frame name")
        date.fromisoformat(row["review_date"])
        names[row["source_name_ar"]] = names[row["frame_name_ar"]]
    return names
