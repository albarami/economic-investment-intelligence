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
REGISTRATION = re.compile(r"[0-9]{1,6}(?:/[0-9]{1,3})?\Z")
# The published row key (lowercase hexadecimal) and its released identity. Each
# digit is spelled as one letter, 0-9 to g-p (decision 0104 item 1): lossless,
# one-to-one and digit-free, so no identity holds a rule-9 digit run.
SOURCE_ROW_KEY = re.compile(r"[a-f0-9]{20}\Z")
ROW_KEY = re.compile(r"ROW-[a-p]{20}\Z")
_ROW_LETTERS = str.maketrans("0123456789", "ghijklmnop")
BARE_DIGITS = re.compile(r"(?<![0-9])(?:[0-9]{8}|[0-9]{11})(?![0-9])")
PREFIXES = ("SYN-E-", "SYN-L-", "SYN-G-", "SYN-P-", "SYN-F-")
METHOD = "register_file_projection"
VERSION = "v2"
RECEIPT_VERSION = "register_input_v1"
ABSENCE_KINDS = frozenset(
    {
        ("fc_register", "notice_expiration_date", "published_non_iso_notice_shape"),
        ("fc_register", "event", "published_event_conflict"),
        ("biz_register", "registration_number", "published_non_registration_value"),
        ("biz_register", "registration_number", "published_duplicate_registration"),
    }
)

# These source headers are required at intake; their values are dropped before parsing.
HEADER_ONLY = ("nationality_group", "nationality_group_ar")

# Derived/internal fields are validated at intake but are not Public card facts.
# In particular an inferred geocoder building is never promoted to a named tower.
INPUT_ONLY = frozenset({"row_key", "points_at_location", "licence_number"})
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
NUMERIC_COLUMNS = {"capital_qar": "BIGINT", "lon": "DOUBLE", "lat": "DOUBLE"}
# Decision 0105: the closed list of typed fields, `table.column` for a release
# column and `manifest.` or `report.` plus mapping keys for a metadata field.
# Each format is checked before the scan. In these fields alone a token may
# equal a registration or licence number of 1 to 2 digits or of the shape 19xx
# or 20xx; every other field, and every longer number, keeps the full scan.
TYPED_FIELDS = {
    "pub_register_company.registration_issue_date": "date",
    "pub_register_company.registration_expiry_date": "date",
    "pub_register_company.licence_issue_date": "date",
    "pub_register_company.licence_expiry_date": "date",
    "pub_register_company.notice_expiration_date": "date",
    "pub_register_company.zone": "integer",
    "pub_register_company.street_number": "integer",
    "pub_register_company.block_en": "integer",
    "pub_register_company.block_ar": "integer",
    "pub_register_company.lon": "longitude",
    "pub_register_company.lat": "latitude",
    "pub_register_company.tax_classification_year": "year",
    "pub_register_company.tax_registered": "yes_no",
    "pub_register_company.capital_qar": "integer",
    "register_company_list.employee_count": "count",
    "pub_register_snapshot.period": "month",
    "register_company_list.period": "month",
    "manifest.version": "manifest_version",
    "manifest.receipts.receipt.version": "receipt_version",
    "manifest.receipts.receipt.retrieved_utc": "timestamp",
    "manifest.receipts.receipt.terms_read_on": "date_or_pending",
    "manifest.receipts.receipt.period": "month",
    "manifest.snapshot_coverage.biz_register": "month",
    "manifest.snapshot_coverage.fc_register": "month",
    "manifest.field_absences.period": "month",
    "manifest.field_absences.count": "count",
    "manifest.tables.rows": "count",
    "report.version": "report_version",
}
# Decision 0105 item 1: these listed fields hold a list of months; every other
# listed field holds one value.
TYPED_SEQUENCES = frozenset(
    {
        "manifest.snapshot_coverage.biz_register",
        "manifest.snapshot_coverage.fc_register",
    }
)
# Decision 0105 item 1 (the owner's a3; the report's version by the advisor's
# note of 2026-11-23): a fixed-text format admits its one text alone, so the
# field can carry nothing else.
FIXED_TEXTS = {
    "manifest_version": VERSION,
    "receipt_version": RECEIPT_VERSION,
    "report_version": VERSION,
}
FORMAT_ONLY_NUMBER = re.compile(r"[0-9]{1,2}|(?:19|20)[0-9]{2}")
# Decision 0119 item 6: the closed list of digest fields, named as in
# TYPED_FIELDS. Only these are exempt from the token and content scans, and
# each holds exactly one SHA-256 (64 lowercase hexadecimal characters) or
# refuses `digest_field_format`; a digest-shaped string anywhere else is
# scanned. Release columns of document 03 section 7.3 that hold a SHA-256:
DIGEST_FIELDS = frozenset(
    {
        "source_registry.sha256",
        "pub_investqa_page.page_sha256",
        "pub_comtrade_trade.receipt_sha256",
    }
    | {
        f"{table}.sha256"
        for table in (
            "pub_completions_ext pub_coverage_ext pub_fdi_stats pub_hotel_ext "
            "pub_jobseekers pub_price_ext pub_survey_ext pub_talent_ext "
            "pub_trade_ext pub_utilities_ext"
        ).split()
    }
    # The manifest: `build.py` (frame and receipt digests), the receipt's file
    # digests (`provenance.py`) and storage's table descriptors.
    | {
        "manifest.frame_sha256",
        "manifest.receipts.receipt_sha256",
        "manifest.tables.sha256",
    }
    | {
        f"manifest.receipts.receipt.files.{role}.sha256"
        for roles in ROLES.values()
        for role in roles
    }
)


# Decision 0124 / L-2139: lead-authored intake wording, copied byte for byte
# from the bounded job's approved_receipt_wording.json; never receipt-supplied
# values or registry placeholders. The source_id selects its one wording row.
APPROVED_RECEIPT_WORDING = {
    "biz_register": {
        "publisher": "Public business register map of the State of Qatar (visitor capture of the public map page)",
        "dataset": "Business types map lists: active and expired licences, all ownership groups",
        "basis_note": "Decision 0026; personal local use. Collected by visitor capture on 2026-11-13 from about 16:45 to 17:00 +03; the timestamp is the start of that window in UTC under the owner's note of 2026-11-13 (ruling L-133).",
    },
    "fc_register": {
        "publisher": "Qatar Financial Centre public register (visitor capture of the register pages)",
        "dataset": "Company register pages and voluntary and involuntary notices",
        "basis_note": "Decision 0026; personal local use. Verified visitor capture of the register pages on 2026-11-02 (191 pages); its time of day was not recorded, so the timestamp is that date at 00:00 UTC, added 2026-11-13 under ruling L-137.",
    },
}
TERMS_WORDS_EXEMPT_SET = frozenset(["terms to be read"])

# One closed path table. exact_count authorities identify independently read
# quantities; fixed_text authorities are code/schema constants or the wording
# above. A schema_keys entry applies to mapping keys only, never their values.
FIXED_METADATA: dict[str, tuple[str, str | frozenset[str]]] = {
    **{
        f"manifest.receipts.receipt.files.{role}.bytes": ("exact_count", "file_bytes")
        for roles in ROLES.values()
        for role in roles
    },
    "manifest.tables.rows": ("exact_count", "table_rows"),
    **{
        f"manifest.receipts.receipt.{field}": ("fixed_text", "receipt_wording")
        for field in ("publisher", "dataset", "basis_note")
    },
    "manifest.receipts.receipt.terms_words": (
        "approved_exempt",
        TERMS_WORDS_EXEMPT_SET,
    ),
    "manifest.field_absences.field": (
        "fixed_text",
        frozenset(f for _, f, _ in ABSENCE_KINDS),
    ),
    "manifest.field_absences.reason": (
        "fixed_text",
        frozenset(r for _, _, r in ABSENCE_KINDS),
    ),
    "report.source_status": ("fixed_text", frozenset({"validated"})),
    "report.missing_snapshot_reason": ("fixed_text", frozenset({"snapshot_not_kept"})),
    "released.pub_register_company": ("schema_keys", frozenset(CARD_COLUMNS)),
    "released.pub_register_snapshot": ("schema_keys", frozenset(SNAPSHOT_COLUMNS)),
}


def column_type(name: str) -> str:
    if name == "registered_cell":
        return "UBIGINT"
    return NUMERIC_COLUMNS.get(name, "VARCHAR")


def row_identity(row_key: str) -> str:
    """The released `ROW-` identity of a validated published row key."""
    return "ROW-" + row_key.translate(_ROW_LETTERS)


def company_key_ok(value: object) -> bool:
    return isinstance(value, str) and (
        REGISTRATION.fullmatch(value) is not None
        or ROW_KEY.fullmatch(value) is not None
    )
