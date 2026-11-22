"""Source-owner terms readings must bind exact registry wording and date."""

import json
from dataclasses import replace
from pathlib import Path

import pytest
from custodian.tests.test_production_adapters import context
from custodian.tests.test_source_completeness import entry

from eii_custodian.publicdata.assembly import AssemblyError
from eii_custodian.publicdata.fetch.terms_text import terms_text_sha256


def test_terms_pending_without_separate_review(tmp_path: Path) -> None:
    from eii_custodian.publicdata.assembly_reports import own_words_confirmed

    assert own_words_confirmed(context(tmp_path, (entry(),))) == frozenset()


@pytest.mark.parametrize(
    "change", [None, "hash", "date", "basis", "unknown", "duplicate", "reference"]
)
def test_terms_review_binds_registered_input(
    tmp_path: Path, change: str | None
) -> None:
    from eii_custodian.publicdata.assembly_reports import own_words_confirmed

    row = replace(entry(), terms_read_on="2026-11-18")
    state = context(tmp_path, (row,))
    value = {
        "key": row.key,
        "terms_sha256": terms_text_sha256(row.terms_words.encode()),
        "terms_read_on": row.terms_read_on,
        "licence_basis": row.licence_basis,
        "review_ref": "SYN-source-owner-review",
    }
    if change:
        field = {
            "hash": "terms_sha256",
            "date": "terms_read_on",
            "basis": "licence_basis",
            "unknown": "key",
            "reference": "review_ref",
        }.get(change)
        if field:
            value[field] = "" if change == "reference" else "SYN-wrong"
    document = {
        "method": "s2-t08-terms.v1",
        "reviews": [value, value] if change == "duplicate" else [value],
    }
    path = tmp_path / "review/s2_t08_terms.json"
    path.parent.mkdir()
    path.write_text(json.dumps(document))
    if change:
        with pytest.raises(AssemblyError, match="assembly_terms_review_invalid"):
            own_words_confirmed(state)
    else:
        assert own_words_confirmed(state) == frozenset({row.key})
        from eii_custodian.publicdata.fetch.bounded import file_hash

        assert state.files["review/s2_t08_terms.json"] == file_hash(path)


def test_required_register_rows_cannot_disappear_from_assembly_audit(
    tmp_path: Path,
) -> None:
    from eii_custodian.publicdata.assembly_reports import gather_audit
    from eii_custodian.publicdata.fetch.registry import load_registry

    state = context(
        tmp_path,
        tuple(
            e
            for e in load_registry()
            if e.source_id not in {"biz_register", "fc_register"}
        ),
    )
    audit = gather_audit(state)
    for source in ("biz_register", "fc_register"):
        assert any(
            row["id"] == source and row["state"] == "not yet read"
            for row in audit["completeness"]
        )
        assert any(
            row["id"] == source and row["state"] == "failed"
            for row in audit["completeness"]
        )


@pytest.mark.parametrize(
    "change", [None, "check", "seed", "double_space", "incomplete"]
)
def test_awards_audit_checks_actual_receipt_and_retains_normalisation_count(
    change,
) -> None:
    from custodian.tests.test_s2_t29_awards import profile, proof_row, row

    from eii_custodian.publicdata.assembly_reports import awards_evidence
    from eii_custodian.publicdata.fetch.award_checks import check_awards
    from eii_custodian.publicdata.fetch.award_links import check_all_awards

    rows = [row(index) for index in range(30)]
    lookup = {item["report_url"]: proof_row(index) for index, item in enumerate(rows)}
    check = check_awards(rows, profile(), 17, lookup.__getitem__)
    receipt = {
        "source_id": "awards_owner_scrape",
        "sha256": "a" * 64,
        "award_check": check,
        "award_check_scope": "sample",
        "award_links": check_all_awards(rows, profile(), lookup.__getitem__),
        "registration_double_space_only": 2,
    }
    if change == "check":
        receipt.pop("award_check")
    elif change == "seed":
        check["seed"] = 18
    elif change == "double_space":
        receipt["registration_double_space_only"] = True
    elif change == "incomplete":
        receipt["award_check"] = check_awards(
            rows[:2], profile(), 17, lookup.__getitem__
        )
    if change:
        with pytest.raises(AssemblyError, match="assembly_t29_refused"):
            awards_evidence(receipt, 17)
    else:
        result = awards_evidence(receipt, 17)
        assert result["registration_double_space_only"] == 2
        assert result["award_check"]["selected_count"] == 30
        assert result["award_check"]["matched"] == 30
        assert "results" not in result["award_check"]
        assert "SYN Company" not in str(result)
