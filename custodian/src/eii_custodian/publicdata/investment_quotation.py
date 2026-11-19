"""Exact original agency bytes from an explicitly selected immutable manifest.

This is cache-only acquisition evidence. It defines no release column, text
serialization or rendering rule; those remain with S2-T39 part B.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path

from eii_custodian.publicdata.fetch.receipts import sha256_hex
from eii_custodian.publicdata.fetch.snapshots import (
    Snapshot,
    SnapshotError,
    read_snapshot,
    utc,
)
from eii_custodian.publicdata.investment_contracts import (
    AGENCY_KINDS,
    InvestmentFailure,
)


@dataclass(frozen=True)
class AgencyQuotation:
    """Original bytes, their verified receipt and their inventory position."""

    snapshot: Snapshot
    page_url: str
    language: str
    retrieved_utc: str
    page_sha256: str
    order: int

    @property
    def body(self) -> bytes:
        return self.snapshot.body


class _Language(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.languages: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "html":
            self.languages.append(
                (dict(attrs).get("lang") or "").split("-")[0].casefold()
            )


def _failure(check: str, url: str = "") -> InvestmentFailure:
    return InvestmentFailure(
        1, "investqa_pages", url, check, "complete original page evidence", "invalid"
    )


def page_evidence(
    directory: Path, page: object, order: int
) -> Snapshot | InvestmentFailure:
    """Bind hash, URL, date, kind, language and order to verified archived bytes."""
    if not isinstance(page, dict):
        return _failure("page_evidence")
    page_url = page.get("url")
    url = page_url if isinstance(page_url, str) else ""
    if (
        page.get("order") != order
        or type(page.get("order")) is not int
        or not isinstance(page.get("language"), str)
        or page.get("language") not in {"en", "ar"}
        or page.get("kind") not in AGENCY_KINDS
        or not isinstance(page.get("sha256"), str)
        or not isinstance(page.get("url"), str)
        or not page.get("url")
    ):
        return _failure("page_evidence", url)
    try:
        utc(page.get("retrieved_utc"))
        snapshot = read_snapshot(directory, page["sha256"])
        if (
            snapshot.sidecar.get("fetch_url") != page["url"]
            or snapshot.sidecar.get("retrieved_utc") != page["retrieved_utc"]
            or snapshot.sidecar.get("source_id") != "investqa_pages"
        ):
            return _failure("page_evidence", url)
        language = _Language()
        language.feed(snapshot.body.decode("utf-8"))
        language.close()
        if language.languages != [page["language"]]:
            return _failure("page_language", url)
    except (OSError, SnapshotError, UnicodeError):
        return _failure("page_evidence", url)
    return snapshot


def read_quotation(
    cache: Path, manifest_identity: str, order: int
) -> AgencyQuotation | InvestmentFailure:
    """Read an explicit archived manifest, never a mutable/latest pointer."""
    directory = cache / "investqa_pages"
    try:
        manifest = read_snapshot(directory / "evidence", manifest_identity)
        document = json.loads(manifest.body)
        if (
            not isinstance(document, dict)
            or document.get("source_id") != "investqa_pages"
        ):
            return _failure("page_evidence")
        pages = document.get("pages")
        if (
            not isinstance(pages, list)
            or isinstance(order, bool)
            or not 1 <= order < len(pages)
        ):
            return _failure("page_evidence")
        page = pages[order]
        snapshot = page_evidence(directory, page, order)
        if isinstance(snapshot, InvestmentFailure):
            return snapshot
        return AgencyQuotation(
            snapshot,
            page["url"],
            page["language"],
            page["retrieved_utc"],
            page["sha256"],
            order,
        )
    except (OSError, SnapshotError, ValueError, TypeError):
        return _failure("page_evidence")


def validate_quotation(
    quotation: AgencyQuotation, candidate: bytes
) -> InvestmentFailure | None:
    """A shortened, rewritten, substituted or translated capture is never exact."""
    try:
        if (
            sha256_hex(candidate) != quotation.page_sha256
            or candidate != quotation.body
        ):
            return _failure("quotation_mismatch", quotation.page_url)
    except (OSError, SnapshotError):
        return _failure("page_evidence", quotation.page_url)
    return None
