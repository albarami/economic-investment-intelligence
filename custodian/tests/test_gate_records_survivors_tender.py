"""Reach the tender adapter in process using existing wholly invented builders."""

from dataclasses import replace

import pytest
from custodian.tests.test_s2_t13_confirmation import (
    receipt,
    registry_record,
    tender,
)

from eii_custodian.publicdata import gate_report as g
from eii_custodian.publicdata.confirm_s2_t13 import (
    Confirmation,
    Tender,
    WeightConfirmation,
)


def test_tender_success_binds_adapter_to_confirmation_registry_and_receipt():
    t = tender()
    row = registry_record(t)
    fetched = receipt(t, row)
    evidence = g.tender_evidence(
        Confirmation(t, WeightConfirmation()), row, fetched, "invented review"
    )
    assert evidence == g.ConfirmationEvidence(
        "S2-T13",
        ("tenders_pub",),
        ("invented review",),
        {"completion_evidence": True},
        receipt_sha256={"tenders_pub": "a" * 64},
    )
    assert evidence.checks["completion_evidence"] is True
    assert g.confirmations([evidence], [row], {row.key: fetched})[1] == {
        "task": "S2-T13",
        "state": "recorded",
        "reason": "",
        "references": ["invented review"],
        "open_entries": [],
        "absences": {},
    }


@pytest.mark.parametrize(
    "plant",
    ["no_row", "no_receipt", "empty_receipt", "no_hash", "pending", "wrong_hash"],
)
def test_tender_failed_validation_is_false_and_preserves_only_supplied_metadata(plant):
    t = tender()
    row = registry_record(t)
    fetched = receipt(t, row)
    confirmation = Confirmation(t, WeightConfirmation())
    expected_sources = ("tenders_pub",)
    expected_hashes = {"tenders_pub": "a" * 64}
    if plant == "no_row":
        row = None
        expected_sources = ()
        expected_hashes = {}
    elif plant == "no_receipt":
        fetched = None
        expected_hashes = {}
    elif plant == "empty_receipt":
        fetched = {}
        expected_hashes = {}
    elif plant == "no_hash":
        fetched.pop("sha256")
        expected_hashes = {}
    elif plant == "pending":
        confirmation = Confirmation(Tender(), WeightConfirmation())
    elif plant == "wrong_hash":
        fetched["sha256"] = "b" * 64
        expected_hashes = {"tenders_pub": "b" * 64}
    evidence = g.tender_evidence(confirmation, row, fetched, "invented review")
    assert evidence == g.ConfirmationEvidence(
        "S2-T13",
        expected_sources,
        ("invented review",),
        {"completion_evidence": False},
        receipt_sha256=expected_hashes,
    )
    assert evidence.checks["completion_evidence"] is False


@pytest.mark.parametrize("confirmed", [False, True])
def test_tender_evidenced_absence_requires_successful_completion(confirmed):
    t = tender(
        outcome="none_found",
        source_id="",
        shown=False,
        release_tables=(),
        search_note="Invented search found no source",
    )
    row = replace(registry_record(t), skip_reason="none_found")
    confirmation = Confirmation(t if confirmed else Tender(), WeightConfirmation())
    expected_absence = {"tenders_pub": "none_found"} if confirmed else {}
    assert g.tender_evidence(
        confirmation, row, None, "invented absence review"
    ) == g.ConfirmationEvidence(
        "S2-T13",
        ("tenders_pub",),
        ("invented absence review",),
        {"completion_evidence": confirmed},
        absence_reasons=expected_absence,
    )
