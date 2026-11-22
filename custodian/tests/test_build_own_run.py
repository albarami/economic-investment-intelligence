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
    is_tender_entry,
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


def _withheld(tmp_path: Path, row) -> None:
    """Selection refuses by name and the S2-T13 gate row stays pending."""
    from eii_custodian.publicdata import gate_report as g

    (tmp_path / "snapshot_pins.json").write_text("{}")
    build = context(tmp_path, (row,))
    with pytest.raises(AssemblyError, match=r"^snapshot_selection_invalid$"):
        build.reviewed_selections()
    evidence = g.tender_evidence(_committed(), row, None, "s2_t13_confirmation.yaml")
    rows = g.confirmations([evidence], [row], {})
    tender_row = next(item for item in rows if item["task"] == "S2-T13")
    assert (tender_row["state"], tender_row["reason"]) == (
        "pending",
        "confirmation_pending",
    )


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
        ("terms_words", "SYN changed terms words"),
        ("terms_read_on", "2000-01-01"),
        ("url", "https://other.invalid/SYN/tenders"),
    ],
)
def test_pending_rejects_changed_binding(
    tmp_path: Path, field: str, value: object
) -> None:
    row = tender_entry()
    assert own_run_pending(_committed(), row, None)
    changed = replace(row, **{field: value})
    assert not own_run_pending(_committed(), changed, None)
    _withheld(tmp_path, changed)


def test_pending_rejects_changed_page_host() -> None:
    from eii_custodian.publicdata import gate_report as g

    committed = _committed()
    row = tender_entry()
    changed = replace(
        committed,
        tender=replace(committed.tender, page="https://other.invalid/SYN/tenders"),
    )
    assert not own_run_pending(changed, row, None)
    with pytest.raises(
        ValueError, match=r"^registry and fetched evidence do not confirm tender$"
    ):
        completion_evidence(changed, row, None)
    evidence = g.tender_evidence(changed, row, None, "s2_t13_confirmation.yaml")
    rows = g.confirmations([evidence], [row], {})
    assert next(i for i in rows if i["task"] == "S2-T13")["state"] == "pending"


def test_present_receipt_never_becomes_pending() -> None:
    row = tender_entry()
    committed = _committed()
    assert not own_run_pending(committed, row, {})
    with pytest.raises(
        ValueError, match=r"^registry and fetched evidence do not confirm tender$"
    ):
        completion_evidence(committed, row, {})


@pytest.mark.parametrize(
    "entries",
    [(), (replace(tender_entry(), skip_reason="unavailable"),)],
    ids=["no-entries", "only-a-skipped-row"],
)
def test_empty_selection_refuses_unless_every_entry_is_pending(
    tmp_path: Path, entries: tuple
) -> None:
    # Isolates the empty-selection guard: no later per-entry guard can refuse.
    (tmp_path / "snapshot_pins.json").write_text("{}")
    build = context(tmp_path, entries)
    with pytest.raises(AssemblyError, match=r"^snapshot_selection_invalid$"):
        build.reviewed_selections()


def test_other_missing_pin_refuses_beside_a_pinned_entry(tmp_path: Path) -> None:
    # Isolates the per-entry guard: the selection is not empty.
    row = tender_entry()
    cited = replace(row, key="SYN-cited", source_id="SYN-cited", kind="citation_only")
    other = replace(row, key="SYN-other", source_id="SYN-other")
    (tmp_path / "snapshot_pins.json").write_text(json.dumps({cited.key: "a" * 64}))
    build = context(tmp_path, (row, cited, other))
    with pytest.raises(AssemblyError, match=r"^snapshot_selection_invalid$"):
        build.reviewed_selections()


def test_absent_review_file_refuses(tmp_path: Path) -> None:
    (tmp_path / "snapshot_pins.json").write_text("{}")
    build = context(tmp_path, (tender_entry(),))
    build.review = tmp_path / "SYN-absent-review"
    with pytest.raises(FileNotFoundError, match=r"s2_t13_confirmation\.yaml"):
        build.reviewed_selections()


def test_review_for_another_key_refuses(tmp_path: Path) -> None:
    review = tmp_path / "review"
    review.mkdir()
    row = json.loads(CONFIRMATION.read_text(encoding="utf-8"))
    row["tender"]["source_id"] = "SYN-other"
    (review / "s2_t13_confirmation.yaml").write_text(json.dumps(row))
    (tmp_path / "snapshot_pins.json").write_text("{}")
    build = context(tmp_path, (tender_entry(),))
    build.review = review
    with pytest.raises(ValueError, match=r"^tender source identity missing$"):
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


# Decision 0084 items 1 and 2 name the tender row by its key or its source ID.
TENDER_IDENTITY_CHANGES = [
    {"kind": "https_file"},
    {"key": "SYN-other"},
    {"source_id": "SYN-other"},
]


@pytest.mark.parametrize("change", TENDER_IDENTITY_CHANGES)
def test_changed_tender_row_still_skips_before_transport(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, change: dict
) -> None:
    calls: list[str] = []

    def transport(url: str):
        calls.append(url)
        raise OSError("SYN transport sentinel")

    monkeypatch.setattr(kinds, "_paged_cards", lambda *_: calls.append("list"))
    monkeypatch.setattr(
        fetch_build, "read_terms_page", lambda *_: calls.append("terms")
    )
    row = replace(tender_entry(), **change)
    outcome = fetch_build.run_build(
        (row,),
        transport,
        tmp_path,
        lambda: "2026-11-21T00:00:00Z",
        lambda _: None,
        _fetch_only=True,
    )
    assert calls == []
    assert f"SKIP {row.key} own_run" in outcome.lines


@pytest.mark.parametrize("change", TENDER_IDENTITY_CHANGES)
def test_changed_tender_row_pin_refuses_before_any_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, change: dict
) -> None:
    from eii_custodian.publicdata import assembly_adapters

    row = replace(tender_entry(), **change)
    (tmp_path / "snapshot_pins.json").write_text(json.dumps({row.key: "a" * 64}))
    build = context(tmp_path, (row,))
    monkeypatch.setattr(
        assembly_adapters,
        "read_snapshot",
        lambda *_: pytest.fail("snapshot read before the pin refusal"),
    )
    monkeypatch.setattr(
        build, "raw", lambda *_, **__: pytest.fail("raw read before the pin refusal")
    )
    with pytest.raises(AssemblyError, match=f"^{OWN_RUN_PIN_REFUSAL}$"):
        build.reviewed_selections()


def test_own_run_journal_note_failure_is_named(tmp_path: Path) -> None:
    class Journal:
        def __init__(self) -> None:
            self.fetch_lines: list[str] = []

        def note(self, _entry) -> None:
            raise OSError("SYN journal write failure")

    row = tender_entry()
    outcome = fetch_build.run_build(
        (row,),
        lambda _url: pytest.fail("transport called"),
        tmp_path,
        lambda: "2026-11-21T00:00:00Z",
        lambda _: None,
        _fetch_only=True,
        _run=Journal(),  # type: ignore[arg-type]
    )
    assert outcome.failure is not None
    assert outcome.failure.check == "resume_record_write_failed"
    assert outcome.failure.source_id == row.source_id
    assert f"FAIL {row.key} resume_record_write_failed" in outcome.lines


def test_tender_row_with_a_skip_reason_refuses_before_any_request(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CF1-F1: the skip reason changed alone; no adapter or transport is called."""
    calls: list[str] = []
    monkeypatch.setattr(kinds, "_paged_cards", lambda *_: calls.append("list"))
    monkeypatch.setattr(
        fetch_build, "read_terms_page", lambda *_: calls.append("terms")
    )
    monkeypatch.setattr(
        fetch_build, "_read_terms_apart", lambda *_, **__: calls.append("apart")
    )
    row = replace(tender_entry(), skip_reason="unavailable")
    outcome = fetch_build.run_build(
        (row,),
        lambda url: calls.append(url),
        tmp_path,
        lambda: "2026-11-21T00:00:00Z",
        lambda _: None,
        _fetch_only=True,
    )
    assert calls == []
    assert outcome.failure is not None
    assert outcome.failure.check == "own_run_row_changed"
    assert outcome.failure.source_id == row.source_id
    assert any(
        line.startswith(f"FAIL {row.key} own_run_row_changed") for line in outcome.lines
    )


@given(st.text(), st.text())
def test_tender_identity_is_key_or_source_id(key: str, source_id: str) -> None:
    row = replace(tender_entry(), key=key, source_id=source_id)
    assert is_tender_entry(row) is ("tenders_pub" in {key, source_id})


@pytest.mark.parametrize("change", [{}, {"key": "SYN-other"}])
def test_archive_step_builds_no_tender_archive(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, change: dict
) -> None:
    from eii_custodian.publicdata import assembly_tenders

    monkeypatch.setattr(
        assembly_tenders,
        "archive_pages",
        lambda *_, **__: pytest.fail("tender archive built"),
    )
    build = context(tmp_path, (replace(tender_entry(), **change),))
    build.fetcher = lambda: type(
        "Fetched", (), {"lines": [], "failure": None, "manifests": {}}
    )()
    build.fetch_archive()
