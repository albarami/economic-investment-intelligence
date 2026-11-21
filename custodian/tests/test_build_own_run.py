"""Invented evidence for the ordinary run's tender skip and the pending gate path.

Carried over from task S2-TSEP; the own run, its pick-up and its review binding
are not built here (decision 0084, last line of its Decision section).
"""

import json
from dataclasses import replace
from pathlib import Path

import pytest
from custodian.tests.singles_entries import tender_entry
from custodian.tests.test_production_adapters import context
from hypothesis import given
from hypothesis import strategies as st

from eii_custodian.publicdata.assembly import AssemblyError
from eii_custodian.publicdata.confirm_s2_t13 import (
    completion_evidence,
    load_confirmation,
    own_run_pending,
)
from eii_custodian.publicdata.fetch import build as fetch_build
from eii_custodian.publicdata.fetch import kinds
from eii_custodian.publicdata.fetch.own_run import (
    OWN_RUN_CAVEAT,
    OWN_RUN_PIN_REFUSAL,
    OWN_RUN_REASON,
    is_own_run_entry,
)

CONFIRMATION = Path("custodian/publicdata/review/s2_t13_confirmation.yaml")


def _committed():
    return load_confirmation(CONFIRMATION)


def test_pending_selection_layer_and_gate_without_tender_output(tmp_path: Path) -> None:
    row = tender_entry()
    build = context(tmp_path, (row,))
    (tmp_path / "snapshot_pins.json").write_text("{}")
    build.reviewed_selections()
    build.frame_result = type("Frame", (), {"tables": {"grid_cell": []}})()
    build.gis_property_singles()
    assert row.key not in build.receipts
    assert "pub_tender" not in build.tables
    assert row.key not in build.source_tables
    committed = _committed()
    assert own_run_pending(committed, row, None)
    assert completion_evidence(committed, row, None) == committed


@given(st.text().filter(lambda value: value != "tenders_pub"))
def test_pending_is_closed_to_every_other_key(value: str) -> None:
    assert not own_run_pending(_committed(), replace(tender_entry(), key=value), None)


@given(
    st.sampled_from(("key", "source_id", "kind", "skip_reason")),
    st.text(),
)
def test_own_run_identity_is_closed(field: str, value: str) -> None:
    row = tender_entry()
    assert is_own_run_entry(row)
    if value != getattr(row, field):
        assert not is_own_run_entry(replace(row, **{field: value}))


@given(st.text().filter(lambda value: value != "paged_cards"))
def test_pending_is_closed_to_every_other_kind(value: str) -> None:
    assert not own_run_pending(_committed(), replace(tender_entry(), kind=value), None)


@pytest.mark.parametrize(
    "field,value",
    [
        ("source_id", "SYN-other"),
        ("key", "SYN-other"),
        ("kind", "SYN-other"),
        ("publisher", "SYN changed"),
        ("fetch_host", "other.invalid"),
        ("terms_url", "https://other.invalid/terms"),
        ("licence_id", "SYN-other-licence"),
        ("licence_basis", "dataset"),
        ("decision_record", "SYN-other-decision"),
        ("period_first", "SYN-other-period"),
        ("period_last", "SYN-other-period"),
        ("release_tables", ()),
        ("basis_note", ""),
        ("basis_note", " \n"),
        ("skip_reason", "unavailable"),
    ],
)
def test_pending_rejects_changed_binding(field: str, value: object) -> None:
    row = replace(tender_entry(), **{field: value})
    assert not own_run_pending(_committed(), row, None)


def test_present_receipt_and_missing_other_pin_never_become_pending(
    tmp_path: Path,
) -> None:
    row = tender_entry()
    committed = _committed()
    assert not own_run_pending(committed, row, {})
    with pytest.raises(ValueError):
        completion_evidence(committed, row, {})
    other = replace(row, key="SYN-other", source_id="SYN-other")
    build = context(tmp_path, (row, other))
    (tmp_path / "snapshot_pins.json").write_text(json.dumps({}))
    with pytest.raises(AssemblyError, match="snapshot_selection_invalid"):
        build.reviewed_selections()


def test_pending_reason_and_caveat_are_exact() -> None:
    assert OWN_RUN_REASON == "own_run_pending"
    assert OWN_RUN_CAVEAT in tender_entry().caveat_keys


def test_pending_completeness_and_gate_have_one_absence_no_table() -> None:
    from eii_custodian.publicdata import completeness as c
    from eii_custodian.publicdata import gate_report as g

    row = tender_entry()
    inputs = dict(
        entries=[row],
        pack=c.Pack({row.source_id: ()}, frozenset()),
        inventory={row.source_id: ()},
        catalogue={"pub_tender"},
        receipts={},
        outputs={},
        absences={row.key: c.Absence(OWN_RUN_REASON, OWN_RUN_CAVEAT)},
        cached_source_ids=(),
    )
    assert [item for item in c.check(**inputs) if item["id"] == row.key] == [
        {
            "id": row.key,
            "state": "NO_DATA",
            "reason": OWN_RUN_REASON,
            "caveat": OWN_RUN_CAVEAT,
        }
    ]
    evidence = g.tender_evidence(_committed(), row, None, "s2_t13_confirmation.yaml")
    assert evidence.absence_reasons == {row.key: OWN_RUN_REASON}
    assert evidence.details == {
        "state": "NO_DATA",
        "reason": OWN_RUN_REASON,
        "caveat": OWN_RUN_CAVEAT,
    }
    rows = g.confirmations([evidence], [row], {})
    tender_row = next(item for item in rows if item["task"] == "S2-T13")
    assert tender_row["state"] == "recorded"
    assert tender_row["absences"] == {row.key: OWN_RUN_REASON}
    assert tender_row["details"] == evidence.details
    inputs["outputs"] = {row.key: ("pub_tender",)}
    assert any(
        item["state"] == "failed" and "output for absent source" in item["reason"]
        for item in c.check(**inputs)
    )


def test_gate_refuses_pending_claim_for_a_foreign_key() -> None:
    from eii_custodian.publicdata import gate_report as g

    row = replace(tender_entry(), key="SYN-other")
    evidence = g.ConfirmationEvidence(
        "S2-T13",
        (row.key,),
        ("s2_t13_confirmation.yaml",),
        {"completion_evidence": True},
        absence_reasons={row.key: OWN_RUN_REASON},
    )
    rows = g.confirmations([evidence], [row], {})
    assert next(i for i in rows if i["task"] == "S2-T13")["state"] == "pending"


def test_gate_refuses_pending_claim_beside_a_receipt() -> None:
    from eii_custodian.publicdata import gate_report as g

    row = tender_entry()
    evidence = g.ConfirmationEvidence(
        "S2-T13",
        (row.key,),
        ("s2_t13_confirmation.yaml",),
        {"completion_evidence": True},
        absence_reasons={row.key: OWN_RUN_REASON},
    )
    rows = g.confirmations([evidence], [row], {row.key: {"sha256": "a" * 64}})
    assert next(i for i in rows if i["task"] == "S2-T13")["state"] == "pending"


@pytest.mark.parametrize("pin", ["a" * 64, "not-a-hash"])
def test_present_tender_pin_refuses_by_name_never_pending(
    tmp_path: Path, pin: str
) -> None:
    row = tender_entry()
    (tmp_path / "snapshot_pins.json").write_text(json.dumps({row.key: pin}))
    build = context(tmp_path, (row,))
    # A well-formed pin refuses by name; a malformed one already refuses at
    # the pin reader. Neither becomes the pending absence.
    reason = OWN_RUN_PIN_REFUSAL if pin == "a" * 64 else "snapshot_selection_invalid"
    with pytest.raises(ValueError, match=reason):
        build.reviewed_selections()
    assert row.key not in build.receipts
    assert not build.source_tables
    assert not build.tables


def test_layers_refuse_an_unselected_tender_that_is_not_pending(
    tmp_path: Path,
) -> None:
    row = replace(tender_entry(), publisher="SYN changed")
    build = context(tmp_path, (row,))
    build.frame_result = type("Frame", (), {"tables": {"grid_cell": []}})()
    with pytest.raises(AssemblyError, match="snapshot_selection_invalid"):
        build.gis_property_singles()
    assert "pub_tender" not in build.tables


def test_ordinary_fetch_never_enters_tender_list_or_terms_adapter(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        kinds, "_paged_cards", lambda *_: pytest.fail("tender list called")
    )
    monkeypatch.setattr(
        fetch_build, "read_terms_page", lambda *_: pytest.fail("tender terms called")
    )
    outcome = fetch_build.run_build(
        (tender_entry(),),
        lambda _url: pytest.fail("transport called"),
        tmp_path,
        lambda: "2026-11-21T00:00:00Z",
        lambda _: None,
        _fetch_only=True,
    )
    assert outcome.failure is None
    assert "SKIP tenders_pub own_run" in outcome.lines
    assert not (tmp_path / "tenders_pub").exists()


def test_ordinary_fetch_keeps_other_paged_entries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[str] = []

    def pages(row, *_args):
        seen.append(row.key)
        raise ValueError("SYN stop")

    monkeypatch.setattr(kinds, "_paged_cards", pages)
    other = replace(tender_entry(), key="SYN-other", source_id="SYN-other")
    fetch_build.run_build(
        (other,),
        lambda _url: pytest.fail("transport called"),
        tmp_path,
        lambda: "2026-11-21T00:00:00Z",
        lambda _: None,
        _fetch_only=True,
    )
    assert seen == ["SYN-other"]
