"""Registry entries for the singles parsers.

The rows for these sources are not in sources.yaml in this workspace: part R
appends that block. This helper builds the entries field for field as build
point B2 states them.
"""

from __future__ import annotations

from eii_custodian.publicdata.fetch.registry import Entry

TENDER_HOST = "monaqasat.mof.gov.qa"
TENDER_TERMS = (
    "If not stated otherwise, it must not reproduce, republish, upload, send, "
    "distribute or publicly display or edit the contents of this website "
    "without the prior written consent of through the Ministry of Finance"
)
BANK_SLUG = "local-banks-credit-by-economic-activity"
DCOOL_SLUG = "design-cooling-capacity-by-status-municipality-and-sector-tr"
PORTAL_HOST = "www.data.gov.qa"


def tender_entry() -> Entry:
    """The tenders_pub row: owner decision 0026, host and release table."""
    return Entry(
        key="tenders_pub",
        source_id="tenders_pub",
        slug="",
        kind="paged_cards",
        title_en="Public tenders by buying entity and category",
        publisher="Ministry of Finance",
        licence_id="",
        licence_basis="owner_decision",
        decision_record="0026",
        fetch_host=TENDER_HOST,
        url=f"https://{TENDER_HOST}/",
        terms_url=f"https://{TENDER_HOST}/",
        nightly_live_fetch=False,
        public_splits=(),
        commit_allowed=False,
        release_tables=("pub_tender",),
        caveat_keys=(),
        columns=(),
        row_count_min=None,
        row_count_max=None,
        period_first="",
        period_last="",
        period_field="",
        reconciliation="none",
        skip_reason="",
        extension="html",
        landing_url=f"https://{TENDER_HOST}/",
        terms_words=TENDER_TERMS,
        terms_read_on="2026-11-14",
    )


def bank_credit_entry() -> Entry:
    """The bank-credit slug: dataset licence, year period, four columns."""
    return Entry(
        key=f"bank_credit_act/{BANK_SLUG}",
        source_id="bank_credit_act",
        slug=BANK_SLUG,
        kind="portal_dataset",
        title_en="Local Banks Credit by Economic Activity",
        publisher="National Planning Council",
        licence_id="CC-BY-4.0",
        licence_basis="dataset",
        decision_record="",
        fetch_host=PORTAL_HOST,
        url=f"https://{PORTAL_HOST}/api/1.0/dataset/{BANK_SLUG}",
        terms_url="",
        nightly_live_fetch=False,
        public_splits=(),
        commit_allowed=False,
        release_tables=("pub_bank_credit",),
        caveat_keys=(),
        columns=(
            ("year", "date"),
            ("economic_activity", "text"),
            ("lnsht_lqtsdy", "text"),
            ("value", "double"),
        ),
        row_count_min=None,
        row_count_max=None,
        period_first="2012-01-01",
        period_last="2022-01-01",
        period_field="year",
        reconciliation="none",
        skip_reason="",
        extension="json",
        landing_url=f"https://{PORTAL_HOST}/",
        terms_words="terms to be read",
        terms_read_on="2026-11-15",
    )


def dcool_entry() -> Entry:
    """The design-capacity slug: dataset licence, culture text, other sectors int."""
    sectors = (
        "other",
        "industrial",
        "real_estate_development",
        "sport",
        "culture",
        "health",
        "transport",
        "education",
        "hotels",
        "commercial",
        "district_cooling_service_supply",
    )
    columns: list[tuple[str, str]] = [
        ("year", "date"),
        ("project_status", "text"),
        ("municipality", "text"),
    ]
    for name in sectors:
        columns.append((name, "text" if name == "culture" else "int"))
    columns.extend(
        (
            ("lbldy", "text"),
            ("hl_lmshry", "text"),
            ("geo_point", "geo_point_2d"),
            ("geo_shape", "geo_shape"),
        )
    )
    return Entry(
        key=f"dcool_capacity/{DCOOL_SLUG}",
        source_id="dcool_capacity",
        slug=DCOOL_SLUG,
        kind="portal_dataset",
        title_en="Design Cooling Capacity by Status, Municipality, and Sector (TR)",
        publisher="National Planning Council",
        licence_id="CC-BY-4.0",
        licence_basis="dataset",
        decision_record="",
        fetch_host=PORTAL_HOST,
        url=f"https://{PORTAL_HOST}/api/1.0/dataset/{DCOOL_SLUG}",
        terms_url="",
        nightly_live_fetch=False,
        public_splits=(),
        commit_allowed=False,
        release_tables=("pub_district_cooling",),
        caveat_keys=(),
        columns=tuple(columns),
        row_count_min=None,
        row_count_max=None,
        period_first="2019-01-01",
        period_last="2023-01-01",
        period_field="year",
        reconciliation="none",
        skip_reason="",
        extension="json",
        landing_url=f"https://{PORTAL_HOST}/",
        terms_words="terms to be read",
        terms_read_on="2026-11-15",
    )
