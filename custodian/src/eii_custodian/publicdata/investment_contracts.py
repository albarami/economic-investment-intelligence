"""Typed investment rows, closed Public provenance and value checks.

Numbers are parsed here and nowhere else in the investment readers. An
unrepresentable value fails. It is never rounded into the contract scale.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from eii_custodian.publicdata.fetch.snapshots import Snapshot
    from eii_custodian.publicdata.investment_crosswalk import ReviewedCrosswalk

PARSER_VERSION = "1"
AGENCY_PARSER_VERSION = "2"
FDI_METHOD = "eii_custodian.publicdata.investment_parse.parse_fdi"
AGENCY_METHOD = "eii_custodian.publicdata.investment_parse.parse_agency"
CAVEAT_KEY = "fdi_estimates"
PROVENANCE_PUBLIC = "public"
SCHEMA_FDI = "fdi_projects.v1"
SCHEMA_AGENCY = "pub_investqa_record.v1"
SCHEMA_MANIFEST = "source_snapshot.v1"

CAPEX_PRECISION = 18
CAPEX_SCALE = 2
PARAMETER_PRECISION = 18
PARAMETER_SCALE = 4


class ValueKind(Enum):
    """The JSON value a published field may carry, after the note's type table."""

    INTEGER = "integer"
    DECIMAL_18_2 = "decimal(18,2)"
    DECIMAL_15_12 = "decimal(15,12)"
    TEXT = "text"
    TAGS = "tags"


STRING_TEXT = "text"
STRING_EMPTY = "empty"
STRING_NULL = "null"
_TEXT_OR_EMPTY = frozenset({STRING_TEXT, STRING_EMPTY})
_EMPTY = frozenset({STRING_EMPTY})
_NONE = frozenset({STRING_NULL})

# The 46 fields of the live page, in the note's order. The hash sorts them.
PUBLISHED_FIELDS = (
    "tech_level_id",
    "src_state_name",
    "project_type_name",
    "freezone_name",
    "city_id",
    "city_name",
    "world_region_id",
    "state_name",
    "src_country_id",
    "src_world_region_name",
    "lat",
    "sub_sector_name",
    "function_name",
    "fdi_sector_id",
    "src_world_region_id",
    "src_state_id",
    "country_name",
    "description",
    "parent_company_name",
    "tags",
    "naics_sub_sector_name",
    "project_year",
    "src_city_name",
    "project_date",
    "function_id",
    "sector_name",
    "src_country_name",
    "investing_company_name",
    "state_abbr",
    "src_city_id",
    "capex_currency",
    "sector_id",
    "world_region_name",
    "project_address",
    "project_id",
    "parent_company_website",
    "lng",
    "state_id",
    "fdi_sector_name",
    "capex",
    "jobs",
    "country_id",
    "parent_company_id",
    "project_type_id",
    "province",
    "project_month",
)
FIELD_SPECS: dict[str, tuple[ValueKind, frozenset[str]]] = {
    "tech_level_id": (ValueKind.INTEGER, frozenset()),
    "src_state_name": (ValueKind.TEXT, _TEXT_OR_EMPTY),
    "project_type_name": (ValueKind.TEXT, _TEXT_OR_EMPTY),
    "freezone_name": (ValueKind.TEXT, _TEXT_OR_EMPTY),
    "city_id": (ValueKind.INTEGER, frozenset()),
    "city_name": (ValueKind.TEXT, _TEXT_OR_EMPTY),
    "world_region_id": (ValueKind.INTEGER, frozenset()),
    "state_name": (ValueKind.TEXT, _TEXT_OR_EMPTY),
    "src_country_id": (ValueKind.INTEGER, frozenset()),
    "src_world_region_name": (ValueKind.TEXT, _TEXT_OR_EMPTY),
    "lat": (ValueKind.DECIMAL_15_12, frozenset()),
    "sub_sector_name": (ValueKind.TEXT, _TEXT_OR_EMPTY),
    "function_name": (ValueKind.TEXT, _TEXT_OR_EMPTY),
    "fdi_sector_id": (ValueKind.INTEGER, frozenset()),
    "src_world_region_id": (ValueKind.INTEGER, frozenset()),
    "src_state_id": (ValueKind.INTEGER, frozenset()),
    "country_name": (ValueKind.TEXT, _TEXT_OR_EMPTY),
    "description": (ValueKind.TEXT, _TEXT_OR_EMPTY),
    "parent_company_name": (ValueKind.TEXT, _TEXT_OR_EMPTY),
    "tags": (ValueKind.TAGS, frozenset()),
    "naics_sub_sector_name": (ValueKind.TEXT, _TEXT_OR_EMPTY),
    "project_year": (ValueKind.INTEGER, _EMPTY),
    "src_city_name": (ValueKind.TEXT, _TEXT_OR_EMPTY),
    "project_date": (ValueKind.TEXT, _TEXT_OR_EMPTY),
    "function_id": (ValueKind.INTEGER, frozenset()),
    "sector_name": (ValueKind.TEXT, _TEXT_OR_EMPTY),
    "src_country_name": (ValueKind.TEXT, _TEXT_OR_EMPTY),
    "investing_company_name": (ValueKind.TEXT, _TEXT_OR_EMPTY),
    "state_abbr": (ValueKind.TEXT, _TEXT_OR_EMPTY),
    "src_city_id": (ValueKind.INTEGER, frozenset()),
    "capex_currency": (ValueKind.TEXT, _TEXT_OR_EMPTY),
    "sector_id": (ValueKind.INTEGER, frozenset()),
    "world_region_name": (ValueKind.TEXT, _TEXT_OR_EMPTY),
    "project_address": (ValueKind.TEXT, _TEXT_OR_EMPTY),
    "project_id": (ValueKind.INTEGER, frozenset()),
    "parent_company_website": (ValueKind.TEXT, _TEXT_OR_EMPTY),
    "lng": (ValueKind.DECIMAL_15_12, frozenset()),
    "state_id": (ValueKind.INTEGER, frozenset()),
    "fdi_sector_name": (ValueKind.TEXT, _TEXT_OR_EMPTY),
    "capex": (ValueKind.DECIMAL_18_2, frozenset()),
    "jobs": (ValueKind.DECIMAL_18_2, _EMPTY),
    "country_id": (ValueKind.INTEGER, frozenset()),
    "parent_company_id": (ValueKind.INTEGER, frozenset()),
    "project_type_id": (ValueKind.INTEGER, frozenset()),
    "province": (ValueKind.TEXT, _TEXT_OR_EMPTY),
    "project_month": (ValueKind.INTEGER, _NONE),
}
# Contract column from the page field. capex_unit is derived, not mapped.
COLUMN_FROM_PAGE = {
    "company": "investing_company_name",
    "source_country": "src_country_name",
    "sector": "sector_name",
    "sub_sector": "sub_sector_name",
    "business_function": "function_name",
    "project_type": "project_type_name",
    "capex_value": "capex",
    "jobs": "jobs",
    "announced": "project_date",
    "location_text": "project_address",
}
_RENAMED = frozenset(
    page for column, page in COLUMN_FROM_PAGE.items() if column != page
)
FURTHER_FIELDS = tuple(name for name in PUBLISHED_FIELDS if name not in _RENAMED)
PAGE_FIELDS = tuple(COLUMN_FROM_PAGE)
TOP_LEVEL_KEYS = frozenset(
    {"clientProjects", "indexBaseMetrics", "currencyText", "latestDate"}
)
SHAPE_ID = "fdi-dashboard-v2"
CAPEX_UNIT_USD = "Mn USD"
CAPEX_LABEL_WORDS = ("Capex", "Mn", "USD")
CAVEAT_PHRASES = (
    ("announced_estimates", "estimates of publicly announced projects"),
    ("incomplete_coverage", "does not capture all investment projects"),
)
MEASURED_ROW_MIN = 1400
MEASURED_ROW_MAX = 2500
MEASURED_PERIOD_FIRST = "2017"
MEASURED_PERIOD_LAST = "2026"
USED_PARAMETERS = frozenset(
    {"rent_share", "rent_amount", "staff_share", "staff_amount"}
)
PARAMETER_KINDS = USED_PARAMETERS | {"other"}
PARAMETER_UNITS = {
    "rent_share": "ratio",
    "rent_amount": "qar_per_month",
    "staff_share": "ratio",
    "staff_amount": "qar_per_month",
}
AGENCY_KINDS = ("sector", "opportunity", "incentive", "setup", "law")
AGENCY_RECORD_TYPES = (
    "sector",
    "opportunity",
    "incentive",
    "incentive_parameter",
    "setup_step",
    "law",
)
LINEAGE_FIELDS = (
    "publisher",
    "page_url",
    "licence_id",
    "licence_basis",
    "decision_record",
    "terms_sha256",
    "retrieved_utc",
    "page_sha256",
)
# Ruling L-1001: a missing terms reading (hash or page) is a pending record
# that fails nothing; every other lineage element still does.
TERMS_READING_FIELDS = frozenset({"terms_sha256", "terms_url"})

_DECIMAL = re.compile(r"^[0-9]+(?:\.[0-9]+)?$")
_INTEGER = re.compile(r"^[0-9]+$")
_YEAR = re.compile(r"^[0-9]{4}$")
_MONTH = re.compile(r"^[0-9]{4}-[0-9]{2}$")
_DAY = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
_SNAKE = re.compile(r"^[a-z][a-z0-9_]*$")
_BARE_DIGITS = re.compile(r"(?<![0-9])(?:[0-9]{8}|[0-9]{11})(?![0-9])")
_HTTPS = re.compile(r"^https://[A-Za-z0-9.-]+(?::[0-9]+)?(?:/[^\s]*)?$")


@dataclass(frozen=True)
class InvestmentFailure:
    """A source-named refusal. code 6 is an unreachable read; code 1 is any other check."""

    code: int
    source_id: str
    url: str
    check: str
    expected: str
    observed: str


@dataclass(frozen=True)
class SourceEnvelope:
    """Provenance copied onto every row. Every element is required."""

    source_id: str
    publisher: str
    page_url: str
    licence_id: str
    licence_basis: str
    decision_record: str
    terms_sha256: str
    terms_url: str
    retrieved_utc: str
    page_sha256: str
    method: str
    method_version: str

    def missing(self) -> str:
        """Return the first empty lineage element, or an empty string when complete."""
        for name in LINEAGE_FIELDS:
            if getattr(self, name) == "":
                return name
        if self.method == "" or self.method_version == "":
            return "method"
        if self.terms_url == "":
            return "terms_url"
        return ""

    def missing_refusal(self) -> str:
        """Return the first empty lineage element outside the terms reading.

        Ruling L-1001: a missing terms reading (hash or page) is a pending
        record and never a refusal, so those elements are skipped here; every
        other empty element still names its refusal.
        """
        for name in LINEAGE_FIELDS:
            if name in TERMS_READING_FIELDS:
                continue
            if getattr(self, name) == "":
                return name
        if self.method == "" or self.method_version == "":
            return "method"
        return ""


@dataclass(frozen=True)
class SourceAssertion:
    """A source-stated value at its own precision, or its explicit absence."""

    value: str | None
    precision: str
    absence_reason: str


@dataclass(frozen=True)
class ProjectArchiveSelection:
    """One explicitly selected raw dashboard archive and its coverage metadata."""

    key: str
    identity: str
    coverage: Mapping[str, object]


@dataclass(frozen=True)
class ProjectSnapshot:
    """Parsed project rows bound to one explicitly selected archived page."""

    identity: str
    snapshot: Snapshot
    rows: tuple[Mapping[str, object], ...]
    schema: str
    coverage: Mapping[str, object]
    observation: SourceAssertion
    publication: SourceAssertion
    correction: SourceAssertion


@dataclass(frozen=True)
class ProjectRevision:
    """One immutable announced-project revision; announced values stay labelled."""

    project_identity: str
    source_id: str
    project_id: str
    snapshot_identity: str
    project_key: str
    observation: SourceAssertion
    publication: SourceAssertion
    retrieved_utc: str
    checksum: str
    schema: str
    geography: str | None
    geography_absence_reason: str
    correction: SourceAssertion
    announced: Mapping[str, object]
    source_chain: Mapping[str, object]


@dataclass(frozen=True)
class MilestoneShape:
    """A reviewed, closed milestone page shape; no real source shape is implied."""

    shape_id: str
    fields: frozenset[str]
    confirmed: bool


@dataclass(frozen=True)
class MilestoneCandidate:
    """A parsed milestone candidate, not independent evidence until reviewed."""

    candidate_id: str
    source_id: str
    milestone_id: str
    project_source_id: str | None
    published_project_id: str | None
    status: str
    snapshot_identity: str
    checksum: str
    retrieved_utc: str
    schema: str
    geography: str
    observation: SourceAssertion
    publication: SourceAssertion
    correction: SourceAssertion
    independence: str
    source_chain: Mapping[str, object]
    snapshot: Snapshot | None = None
    completion: str | None = None
    observed_investment: str | None = None
    shape: MilestoneShape | None = None


@dataclass(frozen=True)
class ReviewedMilestoneLink:
    """A lead-reviewed project and independence assertion for one candidate."""

    candidate_id: str
    project_identity: str
    independence: str
    reviewed: bool
    review_reference: str
    crosswalk_sha256: str
    crosswalk_key: str = ""
    crosswalk: Snapshot | None = None


@dataclass(frozen=True)
class MilestoneArchiveSelection:
    """One explicitly selected milestone page and its reviewed link evidence."""

    key: str
    identity: str
    shape: MilestoneShape
    envelope: SourceEnvelope
    links: tuple[ReviewedMilestoneLink, ...]
    crosswalk_key: str


@dataclass(frozen=True)
class MilestoneEvidence:
    """A validated milestone or a retained candidate with its exact absence."""

    candidate: MilestoneCandidate
    project_identity: str | None
    evidence_status: str
    missing_reason: str


@dataclass(frozen=True)
class ProjectAbsence:
    """A previously seen project's absence from one later source snapshot."""

    project_identity: str
    source_id: str
    snapshot_identity: str
    reason: str


@dataclass(frozen=True)
class ExpectedInput:
    """One registered project or milestone input expected by the evidence audit."""

    source_id: str
    key: str
    kind: str


@dataclass(frozen=True)
class FetchAttempt:
    """The exact outcome of one expected input in the current build."""

    source_id: str
    key: str
    status: str
    snapshot_identity: str | None
    reason: str
    closure_claimed: bool = False


@dataclass(frozen=True)
class EvidenceAuditEntry:
    """One Public evidence row with separate evidence and coverage states."""

    source_id: str
    key: str
    subject_id: str
    revision_identity: str
    provenance: str
    evidence_status: str
    coverage: str
    reason: str


@dataclass(frozen=True)
class EvidenceAudit:
    """The exhaustive cache-only projection consumed by the S2 evidence bundle."""

    entries: tuple[EvidenceAuditEntry, ...]


@dataclass(frozen=True)
class VerifiedArchive:
    """Archive metadata that can satisfy exactly one registration kind."""

    source_id: str
    key: str
    kind: str
    identity: str
    snapshot: Snapshot
    milestone_shape: MilestoneShape | None = None


@dataclass(frozen=True)
class EvidenceProjection:
    """Complete cache-only evidence and audit output for S2-T08."""

    evidence: ProjectEvidence
    audit: EvidenceAudit
    snapshots: tuple[ProjectSnapshot, ...]
    archives: tuple[VerifiedArchive, ...]


@dataclass(frozen=True)
class ObservedInvestment:
    """An attempted observed-investment assertion requiring its own archived source."""

    project_identity: str
    amount: str
    source_id: str
    evidence_kind: str
    snapshot_identity: str


@dataclass(frozen=True)
class ProjectEvidence:
    """Retained project history, without any observed-investment inference."""

    revisions: tuple[ProjectRevision, ...]
    milestones: tuple[MilestoneEvidence, ...] = ()
    observed_investment: tuple[ObservedInvestment, ...] = ()
    absences: tuple[ProjectAbsence, ...] = ()


@dataclass(frozen=True)
class KindRule:
    """How one agency page kind names its page record and its blocks."""

    page_kind: str
    block_kind: str
    level_kinds: Mapping[int, str]
    h3_under_h4: str
    leading_level: int
    minimum_blocks: int
    minimum_paragraphs: int


@dataclass(frozen=True)
class DashboardShape:
    """The confirmed dashboard shape. Crosswalk misses stay null."""

    shape_id: str
    fields: frozenset[str]
    column_from: Mapping[str, str]
    country_iso3: Mapping[str, str]
    municipality_code: Mapping[str, str]
    place_key: Mapping[str, str]
    crosswalk: ReviewedCrosswalk | None = None


@dataclass(frozen=True)
class Confirmation:
    """Synthetic confirmation recorded for the slice S2 gate."""

    inventory_recorded: bool
    field_coverage_recorded: bool
    fixture_comparison_recorded: bool
    live_page_compared: bool


@dataclass(frozen=True)
class Bounds:
    """Declared count range and last period. An unconfirmed bound cannot publish."""

    row_count_min: int
    row_count_max: int
    period_field: str
    period_last: str
    confirmed: bool


def fail(
    envelope: SourceEnvelope,
    check: str,
    expected: str,
    observed: str,
    *,
    code: int = 1,
) -> InvestmentFailure:
    """Name the source, the page and the check that refused the batch."""
    return InvestmentFailure(
        code, envelope.source_id, envelope.page_url, check, expected, observed
    )


def project_key(published_tokens: Mapping[str, str]) -> str:
    """Return fdi_ plus 16 hex characters of the canonical JSON of the published tokens.

    Numbers stay their published digits. The caller passes every published field,
    before an empty text or a zero coordinate is stored as null.
    """
    parts = [
        json.dumps(name, ensure_ascii=True) + ":" + published_tokens[name]
        for name in sorted(published_tokens)
    ]
    encoded = "{" + ",".join(parts) + "}"
    digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
    return "fdi_" + digest[:16]


def parse_decimal(
    text: str, *, precision: int, scale: int, signed: bool = False
) -> str | None:
    """Return the source text when its integer and fractional digits fit.

    Integer digits are at most precision minus scale, and fractional digits are
    at most scale. The text is not rounded.
    """
    body = text
    if signed and text.startswith("-"):
        body = text[1:]
    if body == "" or _DECIMAL.fullmatch(body) is None:
        return None
    integer, _dot, fraction = body.partition(".")
    if len(fraction) > scale:
        return None
    width = integer.lstrip("0")
    if len(width) > precision - scale:
        return None
    return text


def parse_int(text: str) -> int | None:
    """Return a non-negative integer. A padded or fractional token is refused."""
    if _INTEGER.fullmatch(text) is None:
        return None
    if len(text) > 1 and text.startswith("0"):
        return None
    return int(text)


def parse_announced(text: str) -> str | None:
    """Return a year, a month or a calendar day at the precision the page gave."""
    if _YEAR.fullmatch(text) is not None:
        return text
    if _MONTH.fullmatch(text) is not None:
        month = int(text[5:7])
        if 1 <= month <= 12:
            return text
        return None
    if _DAY.fullmatch(text) is None:
        return None
    try:
        datetime.strptime(text, "%Y-%m-%d")
    except ValueError:
        return None
    return text


def snake_key(value: str) -> str | None:
    """Return a lower snake key, or None when the token is not one."""
    key = value.strip().replace("-", "_").casefold()
    if _SNAKE.fullmatch(key) is None:
        return None
    return key


def bare_digit_run(value: str) -> bool:
    """Return whether value holds a bare run of exactly eight or eleven digits."""
    return _BARE_DIGITS.search(value) is not None


def https_url(value: str) -> bool:
    """Return whether value is an https URL with a host and no embedded space."""
    return _HTTPS.fullmatch(value) is not None


def lookup(table: Mapping[str, str], key: str | None) -> str | None:
    """Return a reviewed crosswalk hit. A miss stays unmapped."""
    if key is None or key == "":
        return None
    found = table.get(key, "")
    if found == "":
        return None
    return found


def accept_project_slot(provenance: str, join_key: str) -> InvestmentFailure | None:
    """Refuse every provenance other than Public, and every join key."""
    if provenance != PROVENANCE_PUBLIC:
        return InvestmentFailure(
            1, "fdi_projects", "", "provenance", PROVENANCE_PUBLIC, provenance
        )
    if join_key != "":
        return InvestmentFailure(
            1, "fdi_projects", "", "prohibited_join", "no join", "joined"
        )
    return None


def retrieval_year(retrieved_utc: str) -> int | None:
    """Return the year of a retrieval timestamp, or None when it has none."""
    if len(retrieved_utc) < 4 or not retrieved_utc[:4].isdigit():
        return None
    return int(retrieved_utc[:4])


def period_is_future(period: str, retrieved_utc: str) -> bool:
    """Return whether a stated period's year is after the retrieval year."""
    year = retrieval_year(retrieved_utc)
    if year is None or len(period) < 4 or not period[:4].isdigit():
        return False
    return int(period[:4]) > year
