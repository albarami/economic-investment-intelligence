"""Exact gate records over invented inputs, with no source or cache access."""

import hashlib
from dataclasses import replace

import pytest
from custodian.tests.test_gate_records import reconciliation
from custodian.tests.test_source_completeness import entry, receipt

from eii_custodian.publicdata import gate_report as g


def assert_message(error, expected):
    assert str(error.value) == expected


@pytest.mark.parametrize(
    "case,expected",
    [
        ("zone", {"geography": "ZONE", "row": "census_zone_sector", "reason": ""}),
        (
            "no_zone",
            {
                "geography": "MUNICIPALITY",
                "row": "pop_muni",
                "reason": "zone_row_absent",
            },
        ),
        (
            "missing_columns",
            {
                "geography": "MUNICIPALITY",
                "row": "pop_muni",
                "reason": "zone_row_without_share_columns",
            },
        ),
        (
            "empty_contract",
            {
                "geography": "MUNICIPALITY",
                "row": "pop_muni",
                "reason": "zone_row_without_share_columns",
            },
        ),
        (
            "national",
            {"geography": "NATIONAL", "row": "", "reason": "municipality_row_absent"},
        ),
    ],
)
def test_coverage_exact_record(case, expected):
    zone = entry(
        "census_zone_sector", columns=(("private", "integer"), ("total", "integer"))
    )
    muni = entry("pop_muni")
    rows = [zone, muni]
    shares = {"private", "total"}
    if case == "no_zone":
        rows = [muni]
    elif case == "missing_columns":
        rows = [replace(zone, columns=(("total", "integer"),)), muni]
    elif case == "empty_contract":
        shares = set()
    elif case == "national":
        rows = []
    assert (
        g.coverage_geography(rows, {r.key: receipt(r) for r in rows}, shares)
        == expected
    )


def expected_reconciliation(**changes):
    expected = {
        "id": "OI-03",
        "state": "recorded",
        "decision_status": "Accepted",
        "open_item_state": "CLOSED",
        "open_rows": [],
        "binding": "resolved:0025-invented",
        "dispositions": {
            "R1": "closed: not published",
            "R2": "reconciled: tables differ, occupation table used",
        },
    }
    expected.update(changes)
    return expected


@pytest.mark.parametrize("status", ["Accepted", "Accepted, invented qualification"])
@pytest.mark.parametrize(
    "r2",
    [
        "reconciled: means equal, occupation table used",
        "reconciled: tables differ, occupation table used",
    ],
)
def test_reconciliation_multiline_status_and_both_resolutions(status, r2):
    args = reconciliation()
    args["decision"] = ("# Invented record\n\n| Status | " + status + " |\n").encode()
    args["signoff"]["record_sha256"] = hashlib.sha256(args["decision"]).hexdigest()
    args["dispositions"]["R2"]["status"] = r2
    assert g.oi03_line(**args) == expected_reconciliation(
        decision_status=status, dispositions={"R1": "closed: not published", "R2": r2}
    )


@pytest.mark.parametrize(
    "plant",
    ["no_status", "open_rows", "missing_dispositions", "empty_dispositions", "unbound"],
)
def test_pending_reconciliation_preserves_full_report(plant):
    args = reconciliation()
    expected = expected_reconciliation(state="pending")
    if plant == "no_status":
        args["decision"] = b"# Invented record without status\n"
        args["signoff"]["record_sha256"] = hashlib.sha256(args["decision"]).hexdigest()
        expected["decision_status"] = "not recorded"
    elif plant == "open_rows":
        args["entries"].extend(
            [
                entry("invented_z", reconciliation="open"),
                entry("invented_a", reconciliation="open"),
            ]
        )
        expected["open_rows"] = ["invented_a", "invented_z"]
    elif plant == "missing_dispositions":
        args["dispositions"] = {}
        expected["dispositions"] = {"R1": "pending", "R2": "pending"}
    elif plant == "empty_dispositions":
        args["dispositions"] = {"R1": {}, "R2": {}}
        expected["dispositions"] = {"R1": "pending", "R2": "pending"}
    elif plant == "unbound":
        args["signoff"] = {}
        expected["binding"] = "open"
    assert g.oi03_line(**args) == expected


@pytest.mark.parametrize(
    "lineage,registry,affected,allowed",
    [
        (["invented"], {}, frozenset(), False),
        (["invented"], {"invented": "open"}, frozenset(), False),
        (["invented"], {"invented": "resolved:0025-invented"}, frozenset(), False),
        (["invented"], {"invented": "none"}, frozenset({"invented"}), False),
        (["invented"], {"invented": "none"}, frozenset(), True),
        (
            ["invented"],
            {"invented": "resolved:0025-invented"},
            frozenset({"invented"}),
            True,
        ),
    ],
)
def test_display_refuses_missing_open_and_unbound_lineage(
    lineage, registry, affected, allowed
):
    assert (
        g.display_allowed(lineage, registry, expected_reconciliation(), affected)
        is allowed
    )


def confirmation_record(task, **changes):
    record = {
        "task": task,
        "state": "pending",
        "reason": "confirmation_pending",
        "references": [],
        "open_entries": [],
        "absences": {},
    }
    record.update(changes)
    return record


def test_confirmations_exact_missing_and_recorded_records():
    tasks = ("S2-T12", "S2-T13", "S2-T15", "S2-T17", "S2-T19", "S2-T20")
    assert g.confirmations([], [], {}) == [confirmation_record(task) for task in tasks]
    row = entry()
    item = g.ConfirmationEvidence(
        "S2-T19",
        ("invented",),
        ("invented review",),
        {"confirmed": True},
        ("invented open series",),
        receipt_sha256={"invented": "a" * 64},
    )
    expected = [confirmation_record(task) for task in tasks]
    expected[4] = confirmation_record(
        "S2-T19",
        state="recorded",
        reason="",
        references=["invented review"],
        open_entries=["invented open series"],
    )
    assert g.confirmations([item], [row], {"invented": receipt(row)}) == expected
    with pytest.raises(ValueError) as error:
        g.confirmations([replace(item, task="invented unknown")], [], {})
    assert_message(error, "confirmation_task_unknown")


def test_s2_t12_arabic_evidence_documents_s2_t39_attribution():
    from eii_custodian.publicdata import gate_report as g

    assert "investqa_pages:arabic_evidence" in g.CONFIRMATION_CHECKS["S2-T12"]
    note = (g.investment_evidence.__doc__ or "") + (g.__doc__ or "")
    assert "S2-T39" in note


def test_investment_adapter_exact_identity_and_each_check():
    flags = {
        "inventory_recorded": True,
        "field_coverage_recorded": True,
        "fixture_comparison_recorded": True,
        "live_page_compared": True,
    }
    document = {
        "sources": {
            key: {"confirmation": dict(flags)}
            for key in ("fdi_projects", "investqa_pages")
        }
    }
    assert g.investment_evidence(document, "invented review") == g.ConfirmationEvidence(
        "S2-T12",
        ("fdi_projects", "investqa_pages"),
        ("invented review",),
        {
            "fdi_projects:inventory_recorded": True,
            "fdi_projects:field_coverage_recorded": True,
            "fdi_projects:fixture_comparison_recorded": True,
            "fdi_projects:live_page_compared": True,
            "investqa_pages:inventory_recorded": True,
            "investqa_pages:field_coverage_recorded": True,
            "investqa_pages:fixture_comparison_recorded": True,
            "investqa_pages:live_page_compared": True,
            "investqa_pages:arabic_evidence": False,
        },
    )


@pytest.mark.parametrize(
    "document",
    [
        {},
        {"sources": None},
        {"sources": []},
        {"sources": {"fdi_projects": []}},
        {"sources": {"fdi_projects": {"confirmation": []}}},
    ],
)
def test_investment_missing_blocks_have_exact_false_checks(document):
    result = g.investment_evidence(document, "invented review")
    assert result == g.ConfirmationEvidence(
        "S2-T12",
        ("fdi_projects", "investqa_pages"),
        ("invented review",),
        {
            "fdi_projects:inventory_recorded": False,
            "fdi_projects:field_coverage_recorded": False,
            "fdi_projects:fixture_comparison_recorded": False,
            "fdi_projects:live_page_compared": False,
            "investqa_pages:inventory_recorded": False,
            "investqa_pages:field_coverage_recorded": False,
            "investqa_pages:fixture_comparison_recorded": False,
            "investqa_pages:live_page_compared": False,
            "investqa_pages:arabic_evidence": False,
        },
    )


@pytest.mark.parametrize(
    "release,receipt_release,policy,matched",
    [
        ("", "", {"release": "newest_dated_at_each_refresh"}, False),
        (
            "2032-02-30",
            "2032-02-30",
            {"release": "newest_dated_at_each_refresh"},
            False,
        ),
        (
            "2032-04-05",
            "2031-02-03",
            {"release": "newest_dated_at_each_refresh"},
            False,
        ),
        ("2032-04-05", "2032-04-05", {"release": "2025-01-10"}, False),
        (
            "2032-04-05",
            "2032-04-05",
            {"release": "newest_dated_at_each_refresh"},
            True,
        ),
    ],
)
def test_fsq_actual_release_matches_policy_and_receipt(
    release, receipt_release, policy, matched
):
    assert g.fsq_evidence(
        release, policy, "invented policy", receipt_release
    ) == g.ConfirmationEvidence(
        "S2-T15",
        ("places_fsq/copy",),
        ("invented policy",),
        {"release_matches": matched},
    )
