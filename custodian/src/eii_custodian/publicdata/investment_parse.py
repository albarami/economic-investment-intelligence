"""Deterministic readers for the dashboard page and the agency pages.

The dashboard reader joins payload scripts. The agency reader walks headings.
Page prose outside a heading block does not become a block.
"""

from __future__ import annotations

from eii_custodian.publicdata.investment_agency import parse_agency
from eii_custodian.publicdata.investment_contracts import (
    AGENCY_METHOD,
    FDI_METHOD,
    PAGE_FIELDS,
    PARSER_VERSION,
    DashboardShape,
    InvestmentFailure,
    SourceEnvelope,
)
from eii_custodian.publicdata.investment_flight import read_dashboard

_PAGE_FIELD_SET = frozenset(PAGE_FIELDS)

__all__ = [
    "agency_envelope",
    "dashboard_envelope",
    "field_coverage_failure",
    "parse_agency",
    "parse_fdi",
]


def parse_fdi(
    body: bytes, shape: DashboardShape, envelope: SourceEnvelope
) -> tuple[tuple[dict[str, object], ...], int] | InvestmentFailure:
    """Return project rows and the empty-coordinate count, or one source failure."""
    read = read_dashboard(body, shape, envelope)
    if isinstance(read, InvestmentFailure):
        return read
    rows, empty_coordinates = read
    return tuple(_with_lineage(row, envelope) for row in rows), empty_coordinates


def _with_lineage(
    row: dict[str, object], envelope: SourceEnvelope
) -> dict[str, object]:
    row.update(
        {
            "source_id": envelope.source_id,
            "publisher": envelope.publisher,
            "page_url": envelope.page_url,
            "licence_id": envelope.licence_id,
            "licence_basis": envelope.licence_basis,
            "decision_record": envelope.decision_record,
            "terms_sha256": envelope.terms_sha256,
            "terms_url": envelope.terms_url,
            "retrieved_utc": envelope.retrieved_utc,
            "page_sha256": envelope.page_sha256,
            "method": envelope.method,
            "method_version": envelope.method_version,
        }
    )
    return row


def field_coverage_failure(fields: frozenset[str]) -> InvestmentFailure | None:
    """Fail when a confirmed dashboard shape omits a documented project field."""
    missing = _PAGE_FIELD_SET - fields
    if not missing:
        return None
    return InvestmentFailure(
        1,
        "fdi_projects",
        "",
        "confirmation_fields",
        "mapped fields",
        ",".join(sorted(missing)),
    )


def dashboard_envelope(envelope: SourceEnvelope) -> SourceEnvelope:
    """Return the envelope with the dashboard parser method."""
    return SourceEnvelope(
        source_id=envelope.source_id,
        publisher=envelope.publisher,
        page_url=envelope.page_url,
        licence_id=envelope.licence_id,
        licence_basis=envelope.licence_basis,
        decision_record=envelope.decision_record,
        terms_sha256=envelope.terms_sha256,
        terms_url=envelope.terms_url,
        retrieved_utc=envelope.retrieved_utc,
        page_sha256=envelope.page_sha256,
        method=FDI_METHOD,
        method_version=PARSER_VERSION,
    )


def agency_envelope(envelope: SourceEnvelope) -> SourceEnvelope:
    """Return the envelope with the agency parser method."""
    return SourceEnvelope(
        source_id=envelope.source_id,
        publisher=envelope.publisher,
        page_url=envelope.page_url,
        licence_id=envelope.licence_id,
        licence_basis=envelope.licence_basis,
        decision_record=envelope.decision_record,
        terms_sha256=envelope.terms_sha256,
        terms_url=envelope.terms_url,
        retrieved_utc=envelope.retrieved_utc,
        page_sha256=envelope.page_sha256,
        method=AGENCY_METHOD,
        method_version=PARSER_VERSION,
    )
