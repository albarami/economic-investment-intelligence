"""S2-T49 schema metadata from the lead's structural contract, never source values."""

from __future__ import annotations

import re
from typing import NoReturn


class RegisterError(ValueError):
    """A fixed reason code; no row, identifier, upstream error or path."""


def refuse(reason: str) -> NoReturn:
    raise RegisterError(reason) from None


# CSV has textual lexemes, even for a numeric source column. These declarations
# validate the lexeme before any conversion. Empty means null, never a zero.
SCHEMAS: dict[str, dict[str, str]] = {
    "establishments": dict(
        row_key="row_key",
        name_ar="text",
        name_en="text?",
        establishment_type="text?",
        establishment_subtype="text?",
        legal_form="text?",
        business_type="text?",
        business_category="text?",
        classification="text",
        registration_status="text?",
        registration_issue_date="date",
        registration_expiry_date="date",
        licence_status="text",
        licence_issue_date="date",
        licence_expiry_date="date",
        branches="empty",
        municipality="text",
        zone="integer",
        lon="longitude",
        lat="latitude",
        registration_number="registration?",
        licence_number="integer",
        tax_registered="yes_no",
        tax_registration_number="text?",
        tax_classification_year="year?",
        tax_type="text?",
        capital_qar="integer?",
        establishment_nationality="text",
        street_number="integer",
        building_number="text",
        establishment_type_ar="text?",
        establishment_subtype_ar="text?",
        legal_form_ar="text?",
        classification_ar="text",
        registration_status_ar="text?",
        licence_status_ar="text",
        municipality_ar="text",
        district_en="text?",
        district_ar="text?",
        block_en="integer",
        block_ar="integer",
        nationality_group="text",
        nationality_group_ar="text",
        establishment_nationality_ar="text",
        points_at_location="integer",
    ),
    "companies": dict(
        row_key="row_key",
        qfc_number="fc_number",
        name_en="text",
        name_ar="text?",
        registered_address="text",
        licence_status="text",
        register_order="integer",
    ),
    "geocoded": dict(
        row_key="row_key",
        qfc_number="fc_number",
        building_name="text?",
        matched_place="text?",
        match_quality="text",
        lon="longitude?",
        lat="latitude?",
    ),
    "events": dict(
        qfc_number="fc_number", event="text", notice_expiration_date="date?"
    ),
}
ROLES = {
    "biz_register": frozenset({"establishments"}),
    "fc_register": frozenset({"companies", "geocoded", "events"}),
}
REGISTRY_KEYS = {"biz_register": "biz_register", "fc_register": "fc_register/file"}
REGISTRATION = re.compile(r"(?:[0-9]{5,6}|[0-9]+/[0-9]{1,2})\Z")
BARE_DIGITS = re.compile(r"(?<![0-9])(?:[0-9]{8}|[0-9]{11})(?![0-9])")
PREFIXES = ("SYN-E-", "SYN-L-", "SYN-G-", "SYN-P-", "SYN-F-")
METHOD = "register_file_projection"
VERSION = "v1"

# Derived/internal fields are validated at intake but are not Public card facts.
# In particular an inferred geocoder building is never promoted to a named tower.
INPUT_ONLY = frozenset(
    {"row_key", "nationality_group", "nationality_group_ar", "points_at_location"}
)
CARD_COLUMNS = (
    *(name for name in SCHEMAS["establishments"] if name not in INPUT_ONLY),
    "registered_address",
    "event",
    "notice_expiration_date",
    "registered_cell",
    "source_id",
)
SNAPSHOT_COLUMNS = ("registration_number", "period", "source_id", "registered_cell")
LIST_COLUMNS = (
    "registration_number",
    "period",
    "employee_count",
    "suppression_reason_code",
)
TABLE_COLUMNS = {
    "pub_register_company": CARD_COLUMNS,
    "pub_register_snapshot": SNAPSHOT_COLUMNS,
    "register_company_list": LIST_COLUMNS,
}


def column_type(name: str) -> str:
    return "UBIGINT" if name == "registered_cell" else "VARCHAR"
