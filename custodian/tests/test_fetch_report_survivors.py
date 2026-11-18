"""Tests killing mutation survivors in fetch/report.py."""

from __future__ import annotations

from eii_custodian.publicdata.fetch.report import evidence_line


def test_evidence_line_mutations() -> None:
    # 61: reason="XXXX" default, 62: if (reason) or True, 63: else "XXXX"
    keys = frozenset(["syn_project"])
    result = evidence_line("syn_project", "retained", registry_keys=keys)
    assert result == "EVIDENCE syn_project retained"
