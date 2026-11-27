"""Company-web completeness uses metadata only; all evidence is invented."""

from dataclasses import replace
from pathlib import Path

import pytest
from custodian.tests.repository_root import repository_root
from custodian.tests.test_production_adapters import context
from custodian.tests.test_source_completeness import entry, failures, inputs, receipt

from eii_custodian.publicdata import completeness as c
from eii_custodian.publicdata.assembly_reports import gather_audit
from eii_custodian.publicdata.fetch.build import run_build
from eii_custodian.publicdata.fetch.registry import load_registry

REASON = "company_web_not_selected"
CAVEAT = "company_web_lead_shell_only"


def test_company_web_tracked_full_profile_completeness(tmp_path: Path) -> None:
    """Actual ordinary-build inventory: no cache inputs, receipts or network."""
    root = repository_root(Path(__file__))
    entries = load_registry(root / "custodian/publicdata/sources.yaml")
    ordinary = tuple(
        row for row in entries if row.kind not in {"company_web", "cdse_backup"}
    )
    state = replace(context(tmp_path, ordinary), root=root)
    record = gather_audit(state)["completeness"]
    company = [row for row in record if row["id"] == "company_web"]
    assert company == [
        {"id": "company_web", "state": "NO_DATA", "reason": REASON, "caveat": CAVEAT}
    ]
    assert not any(
        row["reason"] == "source_completeness: duplicate key" for row in record
    )
    assert state.entries == ordinary
    assert state.receipts == state.selected == state.source_tables == {}


def company_row():
    return entry(
        source="company_web",
        kind="company_web",
        release_tables=(),
        caveat_keys=(CAVEAT,),
    )


def test_company_web_fetch_loop_never_contacts_source(tmp_path: Path) -> None:
    calls = []

    def refuse(url):
        calls.append(url)
        pytest.fail("company_web_request")

    # An admitted fixture host prevents an earlier host guard masking dispatch.
    row = replace(
        company_row(),
        fetch_host="www.qfc.qa",
        url="https://www.qfc.qa/SYN-company-web.json",
        terms_url="",
    )
    outcome = run_build(
        (row,),
        refuse,
        tmp_path,
        lambda: "2026-11-26T00:00:00Z",
        lambda _: None,
        _fetch_only=True,
    )
    assert outcome.failure is None
    assert calls == []
    assert outcome.manifests == {}


@pytest.mark.parametrize(
    "evidence", ["selected", "receipt", "selected_and_receipt", "invalid_receipt"]
)
def test_company_web_existing_evidence_is_not_replaced_by_absence(
    tmp_path: Path, evidence: str
) -> None:
    row = company_row()
    state = context(
        tmp_path,
        (*(e for e in load_registry() if e.source_id != row.source_id), row),
    )
    if "selected" in evidence:
        state.selected[row.key] = "a" * 64
    if "receipt" in evidence:
        state.receipts[row.key] = receipt(row)
    if evidence == "invalid_receipt":
        state.receipts[row.key]["sha256"] = "SYN-invalid"
    record = gather_audit(state)["completeness"]
    company = [item for item in record if item["id"] == row.key]
    expected = (
        {"id": row.key, "state": "in use", "reason": ""}
        if "receipt" in evidence and evidence != "invalid_receipt"
        else {
            "id": row.key,
            "state": "failed",
            "reason": (
                "source_receipt_missing: field=digest"
                if evidence == "invalid_receipt"
                else "source_receipt_missing: missing or invalid receipt"
            ),
        }
    )
    assert company == [expected]


@pytest.mark.parametrize(
    "plant,reason",
    [
        ("missing", "source_completeness: missing registry source"),
        ("duplicate", "source_completeness: duplicate or missing row"),
    ],
)
def test_company_web_missing_and_duplicate_registry_rows_still_fail(plant, reason):
    args = inputs()
    row = company_row()
    args.update(
        entries=[row],
        pack=c.Pack({row.source_id: ()}, frozenset()),
        inventory={row.source_id: ()},
        receipts={},
        outputs={},
        absences={row.key: c.Absence(REASON, CAVEAT)},
    )
    assert not failures(c.check(**args))
    # Only the registry entries change; all evidence and contracts stay valid.
    args["entries"] = [] if plant == "missing" else [row, row]
    assert {"id": row.source_id, "state": "failed", "reason": reason} in failures(
        c.check(**args)
    )


def test_company_web_absence_does_not_cover_another_source(tmp_path: Path) -> None:
    row = replace(
        next(e for e in load_registry() if e.key == "lic_issued"), caveat_keys=(CAVEAT,)
    )
    state = context(
        tmp_path,
        (*(e for e in load_registry() if e.source_id != row.source_id), row),
    )
    state.receipts[row.key] = receipt(row)
    state.source_tables[row.key] = list(row.release_tables)
    assert {"id": row.key, "state": "in use", "reason": ""} in gather_audit(state)[
        "completeness"
    ]
    # Remove only this source's receipt; the company-web caveat cannot excuse it.
    state.receipts.pop(row.key)
    company = [
        item for item in gather_audit(state)["completeness"] if item["id"] == row.key
    ]
    assert company == [
        {
            "id": row.key,
            "state": "failed",
            "reason": "source_receipt_missing: missing or invalid receipt",
        }
    ]


def test_company_web_absent_registry_row_is_not_invented(
    tmp_path: Path, monkeypatch
) -> None:
    from eii_custodian.publicdata.fetch import registry

    ordinary = tuple(e for e in load_registry() if e.kind != "company_web")
    monkeypatch.setattr(registry, "load_registry", lambda: ordinary)
    record = gather_audit(context(tmp_path, ordinary))["completeness"]
    assert {
        "id": "company_web",
        "state": "failed",
        "reason": "source_completeness: missing registry source",
    } in record
    assert {
        "id": "company_web",
        "state": "failed",
        "reason": "source_completeness: duplicate or missing row",
    } in record


def test_company_web_unselected_output_still_fails(tmp_path: Path) -> None:
    state = context(tmp_path, load_registry())
    initial = gather_audit(state)["completeness"]
    assert not any(item["id"] == "company_web" for item in failures(initial))
    state.source_tables["company_web"] = ["pub_invented"]
    assert {
        "id": "company_web",
        "state": "failed",
        "reason": "source_completeness: output for absent source",
    } in gather_audit(state)["completeness"]
