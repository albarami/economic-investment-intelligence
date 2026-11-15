"""Registry entries for the singles parsers.

Each helper is the loaded registry row of that key. The row is the truth
(join section 4b, ruling J2).
"""

from __future__ import annotations

from pathlib import Path

from custodian.tests.repository_root import repository_root

from eii_custodian.publicdata.fetch.registry import Entry, load_registry

TENDER_HOST = "monaqasat.mof.gov.qa"
TENDER_TERMS = (
    "If not stated otherwise, it must not reproduce, republish, upload, send, "
    "distribute or publicly display or edit the contents of this website "
    "without the prior written consent of through the Ministry of Finance"
)


def _loaded(key: str) -> Entry:
    """Return the registry row for key. The helper does not restate the row."""
    path = repository_root(Path(__file__)) / "custodian/publicdata/sources.yaml"
    return next(entry for entry in load_registry(path) if entry.key == key)


def tender_entry() -> Entry:
    """The tenders_pub row as the registry records it."""
    return _loaded("tenders_pub")


def bank_credit_entry() -> Entry:
    """The bank-credit row as the registry records it."""
    return _loaded("bank_credit_act/local-banks-credit-by-economic-activity")


def dcool_entry() -> Entry:
    """The design-capacity row as the registry records it."""
    return _loaded(
        "dcool_capacity/design-cooling-capacity-by-status-municipality-and-sector-tr"
    )
