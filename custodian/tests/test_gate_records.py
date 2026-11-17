"""Loaded, invented evidence only; no live records or source-cache reads."""

import hashlib
from dataclasses import replace

import pytest
from custodian.tests.test_source_completeness import entry, receipt

from eii_custodian.publicdata import gate_report as g


def test_coverage_geography():
    muni = entry("pop_muni")
    district = entry("district_population")
    zone = entry(
        "census_zone_sector", columns=(("private", "integer"), ("total", "integer"))
    )
    receipts = {r.key: receipt(r) for r in (zone, muni, district)}
    assert (
        g.coverage_geography([district], receipts, {"private", "total"})["geography"]
        == "NATIONAL"
    )
    assert (
        g.coverage_geography([zone, muni], receipts, {"private", "total"})["geography"]
        == "ZONE"
    )
    assert (
        g.coverage_geography(
            [replace(zone, columns=()), muni], receipts, {"private", "total"}
        )["geography"]
        == "MUNICIPALITY"
    )
    assert (
        g.coverage_geography(
            [zone, muni], {muni.key: receipt(muni)}, {"private", "total"}
        )["row"]
        == "pop_muni"
    )
    assert g.coverage_geography([zone], receipts, set())["geography"] == "NATIONAL"


def reconciliation():
    decision = b"| Status | Accepted |\n"
    row = entry("affected", reconciliation="resolved:0025-invented")
    signoff = dict(
        approved=True,
        reviewer_role="owner-delegated advisor",
        record="0025-invented.md",
        record_sha256=hashlib.sha256(decision).hexdigest(),
        sources=["affected"],
    )
    return dict(
        entries=[row],
        decision=decision,
        decision_name="0025-invented.md",
        signoff=signoff,
        sources=frozenset({"affected"}),
        open_item_type="CLOSED",
        dispositions={
            "R1": {"status": "closed: not published"},
            "R2": {"status": "reconciled: tables differ, occupation table used"},
        },
    )


def test_reconciliation_closure_and_transitive_refusal():
    args = reconciliation()
    report = g.oi03_line(**args)
    assert report["state"] == "recorded"
    assert g.display_allowed(
        ["leaf", "affected"],
        {"leaf": "none", "affected": "resolved:0025-invented"},
        report,
        args["sources"],
    )
    assert not g.display_allowed(
        ["leaf", "affected"],
        {"leaf": "none", "affected": "open"},
        report,
        args["sources"],
    )
    assert not g.display_allowed([], {}, report, args["sources"])


@pytest.mark.parametrize(
    "plant", ["proposed", "hash", "signoff", "open", "missing", "disposition", "item"]
)
def test_reconciliation_stays_pending(plant):
    args = reconciliation()
    if plant == "proposed":
        args["decision"] = b"| Status | Proposed |\n"
    if plant == "hash":
        args["signoff"]["record_sha256"] = "b" * 64
    if plant == "signoff":
        args["signoff"] = {}
    if plant == "open":
        args["entries"] = [replace(args["entries"][0], reconciliation="open")]
    if plant == "missing":
        args["entries"] = []
    if plant == "disposition":
        args["dispositions"]["R2"] = {"status": "open"}
    if plant == "item":
        args["open_item_type"] = "OPEN"
    report = g.oi03_line(**args)
    assert report["id"] == "OI-03" and report["state"] == "pending"
    assert not g.display_allowed(
        ["affected"], {"affected": "resolved:0025-invented"}, report, args["sources"]
    )


def test_confirmations_require_all_six_and_fetched_binding():
    row = entry()
    evidence = g.ConfirmationEvidence(
        "S2-T19", (row.key,), ("invented review",), {"confirmed": True}
    )
    evidence = replace(evidence, receipt_sha256={row.key: "a" * 64})
    report = g.confirmations([evidence], [row], {row.key: receipt(row)})
    assert {r["task"] for r in report} == set(g.CONFIRMATION_TASKS)
    assert next(r for r in report if r["task"] == "S2-T19")["state"] == "recorded"
    for bad in (
        replace(evidence, references=()),
        replace(evidence, checks={"confirmed": False}),
        replace(evidence, source_keys=()),
    ):
        assert (
            next(
                r
                for r in g.confirmations([bad], [row], {row.key: receipt(row)})
                if r["task"] == "S2-T19"
            )["state"]
            == "pending"
        )
    assert all(r["state"] == "pending" for r in g.confirmations([evidence], [row], {}))
    changed = {row.key: {**receipt(row), "sha256": "b" * 64}}
    assert all(
        r["state"] == "pending" for r in g.confirmations([evidence], [row], changed)
    )


def test_pending_forecast_and_height_evidence_is_preserved():
    forecast = g.ConfirmationEvidence(
        "S2-T17",
        (),
        ("invented series review",),
        {"validated": False},
        ("invented held series reason",),
    )
    report = g.confirmations([forecast], [], {})
    item = next(r for r in report if r["task"] == "S2-T17")
    assert item["state"] == "pending" and item["open_entries"] == [
        "invented held series reason"
    ]
    height = g.ConfirmationEvidence(
        "S2-T20",
        (),
        ("invented height rules",),
        {"storey_height_recorded": False, "fallback_errors_recorded": False},
    )
    assert all(r["state"] == "pending" for r in g.confirmations([height], [], {}))
    with pytest.raises(ValueError):
        g.confirmations([replace(forecast, task="unknown")], [], {})


def test_existing_investment_confirmation_flags_are_used():
    flags = dict(
        inventory_recorded=True,
        field_coverage_recorded=True,
        fixture_comparison_recorded=True,
        live_page_compared=True,
    )
    document = {
        "sources": {
            key: {"confirmation": dict(flags)}
            for key in ("fdi_projects", "investqa_pages")
        }
    }
    item = g.investment_evidence(document, "invented investment review")
    assert all(item.checks.values())
    document["sources"]["fdi_projects"]["confirmation"]["live_page_compared"] = False
    assert not all(g.investment_evidence(document, "invented review").checks.values())


def test_arbitrary_checks_do_not_complete_a_confirmation():
    row = entry()
    item = g.ConfirmationEvidence(
        "S2-T20", (row.key,), ("invented ref",), {"anything": True}
    )
    assert all(
        r["state"] == "pending"
        for r in g.confirmations([item], [row], {row.key: receipt(row)})
    )


def test_fsq_release_must_match_policy_and_fetched_evidence():
    item = g.fsq_evidence(
        "invented-release", {"release": "invented-release"}, "invented policy"
    )
    row = entry("places_fsq")
    item = replace(item, receipt_sha256={row.key: "a" * 64})
    assert (
        next(
            r
            for r in g.confirmations([item], [row], {row.key: receipt(row)})
            if r["task"] == "S2-T15"
        )["state"]
        == "recorded"
    )
    bad = g.fsq_evidence(
        "invented-release", {"release": "other-release"}, "invented policy"
    )
    assert all(
        r["state"] == "pending"
        for r in g.confirmations([bad], [row], {row.key: receipt(row)})
    )


def test_confirmed_absence_is_evidence_without_claiming_a_fetch():
    row = entry(skip_reason="invented access failure")
    item = g.ConfirmationEvidence(
        "S2-T19",
        (row.key,),
        ("invented review",),
        {"confirmed": True},
        absence_reasons={row.key: row.skip_reason},
    )
    report = g.confirmations([item], [row], {})
    assert next(r for r in report if r["task"] == "S2-T19")["state"] == "recorded"
    assert next(r for r in report if r["task"] == "S2-T19")["absences"] == {
        row.key: row.skip_reason
    }
    bad = replace(item, absence_reasons={row.key: "different reason"})
    assert all(r["state"] == "pending" for r in g.confirmations([bad], [row], {}))


def test_terms_markers_are_reported_without_own_words_completion():
    row = entry(
        terms_words="terms to be read; checked 2026-11-17",
        licence_basis="owner_decision",
        decision_record="0026",
    )
    report = g.terms_evidence([row])
    assert report == [
        {
            "id": row.key,
            "terms_words": row.terms_words,
            "terms_read_on": row.terms_read_on,
            "licence_basis": "owner_decision",
            "decision_record": "0026",
            "own_words_state": "pending",
        }
    ]
    # A separate source-owner confirmation, never the marker itself, supplies completion.
    assert (
        g.terms_evidence([entry()], frozenset({"invented"}))[0]["own_words_state"]
        == "recorded"
    )


def test_duplicate_confirmation_task_refuses():
    item = g.ConfirmationEvidence("S2-T19", (), (), {"confirmed": False})
    with pytest.raises(ValueError, match=r"^confirmation_task_duplicate$"):
        g.confirmations(
            [item, replace(item, references=("invented other review",))], [], {}
        )
