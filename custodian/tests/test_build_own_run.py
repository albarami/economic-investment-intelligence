"""Invented evidence for the separate tender acquisition and pending gate path."""

import json
from dataclasses import replace
from pathlib import Path

import pytest
from custodian.tests.singles_entries import tender_entry
from custodian.tests.test_production_adapters import context
from hypothesis import given
from hypothesis import strategies as st

from eii_custodian.publicdata.assembly import AssemblyError
from eii_custodian.publicdata.assembly_tenders import verify_archive_terms
from eii_custodian.publicdata.confirm_s2_t13 import (
    completion_evidence,
    load_confirmation,
    own_run_pending,
)
from eii_custodian.publicdata.fetch import build as fetch_build
from eii_custodian.publicdata.fetch import kinds
from eii_custodian.publicdata.fetch.checks import AttemptFailure
from eii_custodian.publicdata.fetch.kinds import Prepared, TermsPage
from eii_custodian.publicdata.fetch.own_run import (
    OWN_RUN_CACHE_RELATIVE,
    OWN_RUN_CAVEAT,
    OWN_RUN_REASON,
    is_tender_entry,
    own_run_cache,
)
from eii_custodian.publicdata.fetch.terms_text import terms_text_sha256
from eii_custodian.publicdata.singles.tenders import (
    LIST_PATHS,
    ListReading,
    _write_pages,
)


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
    committed = load_confirmation(build.review / "s2_t13_confirmation.yaml")
    assert own_run_pending(committed, row, None)
    assert completion_evidence(committed, row, None) == committed


@given(st.text().filter(lambda value: value != "tenders_pub"))
def test_pending_is_closed_to_every_other_key(value: str) -> None:
    row = replace(tender_entry(), key=value)
    committed = load_confirmation(
        Path("custodian/publicdata/review/s2_t13_confirmation.yaml")
    )
    assert not own_run_pending(committed, row, None)
    with pytest.raises(
        ValueError, match=r"^registry and fetched evidence do not confirm tender$"
    ):
        completion_evidence(committed, row, None)


@pytest.mark.parametrize(
    "body,receipt",
    [
        (b"not JSON", {"terms_sha256": "a" * 64}),
        (b"[]", {"terms_sha256": "a" * 64}),
        (json.dumps({"terms_sha256": "a" * 64}).encode(), {}),
        (
            json.dumps({"terms_sha256": "bad"}).encode(),
            {"terms_sha256": "bad"},
        ),
        (
            json.dumps({"terms_sha256": "b" * 64}).encode(),
            {"terms_sha256": "a" * 64},
        ),
    ],
    ids=[
        "invalid_json",
        "non_object",
        "missing_receipt",
        "bad_digest",
        "body_mismatch",
    ],
)
def test_archive_terms_refuses_one_invalid_field(
    body: bytes, receipt: dict[str, str]
) -> None:
    with pytest.raises(AssemblyError, match=r"^assembly_tender_terms_incomplete$"):
        verify_archive_terms(body, receipt)


def test_archive_terms_accepts_matching_body_and_receipt() -> None:
    verify_archive_terms(
        json.dumps({"terms_sha256": "a" * 64}).encode(),
        {"terms_sha256": "a" * 64},
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("source_id", "SYN-other"),
        ("key", "SYN-other"),
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
        ("skip_reason", "unavailable"),
        ("terms_words", "SYN changed terms words"),
        ("terms_read_on", "2000-01-01"),
    ],
)
def test_pending_rejects_changed_binding(field: str, value: object) -> None:
    row = replace(tender_entry(), **{field: value})
    committed = load_confirmation(
        Path("custodian/publicdata/review/s2_t13_confirmation.yaml")
    )
    assert not own_run_pending(committed, row, None)
    with pytest.raises(
        ValueError, match=r"^registry and fetched evidence do not confirm tender$"
    ):
        completion_evidence(committed, row, None)


def test_present_receipt_and_missing_other_pin_never_become_pending(
    tmp_path: Path,
) -> None:
    row = tender_entry()
    committed = load_confirmation(
        Path("custodian/publicdata/review/s2_t13_confirmation.yaml")
    )
    assert not own_run_pending(committed, row, {})
    with pytest.raises(ValueError):
        completion_evidence(committed, row, {})
    other = replace(row, key="SYN-other", source_id="SYN-other")
    build = context(tmp_path, (row, other))
    (tmp_path / "snapshot_pins.json").write_text(json.dumps({}))
    with pytest.raises(AssemblyError, match="snapshot_selection_invalid"):
        build.reviewed_selections()


def test_pending_reason_is_exact() -> None:
    assert OWN_RUN_REASON == "own_run_pending"


def test_own_run_cache_relative_path(tmp_path: Path) -> None:
    assert own_run_cache(tmp_path / "data/public_cache") == (
        tmp_path / OWN_RUN_CACHE_RELATIVE
    )


def test_ordinary_archive_refuses_unexpected_active_paged_source(
    tmp_path: Path,
) -> None:
    row = replace(tender_entry(), source_id="SYN-other")
    build = context(tmp_path, (row,))
    build.fetcher = lambda: fetch_build.BuildOutcome((), None)
    with pytest.raises(AssemblyError, match=r"^assembly_tender_pages_incomplete$"):
        build.fetch_archive()


@given(st.text(), st.text())
def test_tender_identity_is_key_or_source_id(key: str, source_id: str) -> None:
    row = replace(tender_entry(), key=key, source_id=source_id)
    assert is_tender_entry(row) is ("tenders_pub" in {key, source_id})


@pytest.mark.parametrize(
    "key,source_id,expected",
    [
        ("tenders_pub", "SYN-other", True),
        ("SYN-other", "tenders_pub", True),
        ("SYN-other", "SYN-other", False),
    ],
)
def test_tender_identity_named_by_either_field(
    key: str, source_id: str, expected: bool
) -> None:
    row = replace(tender_entry(), key=key, source_id=source_id)
    assert is_tender_entry(row) is expected


@pytest.mark.parametrize(
    "field,value",
    [
        ("kind", "https_file"),
        ("key", "SYN-other"),
        ("source_id", "SYN-other"),
        ("skip_reason", "unavailable"),
    ],
)
def test_changed_tender_row_refuses_before_transport(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, field: str, value: str
) -> None:
    calls: list[str] = []
    monkeypatch.setattr(kinds, "_paged_cards", lambda *_: calls.append("list"))
    monkeypatch.setattr(
        fetch_build, "read_terms_page", lambda *_: calls.append("terms")
    )
    row = replace(tender_entry(), **{field: value})
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
    if field == "skip_reason":
        assert outcome.failure.observed == value


@pytest.mark.parametrize(
    "field,value",
    [
        ("kind", "https_file"),
        ("key", "SYN-other"),
        ("source_id", "SYN-other"),
        ("skip_reason", "unavailable"),
    ],
)
def test_changed_tender_row_pin_refuses_before_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, field: str, value: str
) -> None:
    from eii_custodian.publicdata import assembly_adapters

    row = replace(tender_entry(), **{field: value})
    (tmp_path / "snapshot_pins.json").write_text(json.dumps({row.key: "a" * 64}))
    build = context(tmp_path, (row,))
    monkeypatch.setattr(
        assembly_adapters,
        "read_snapshot",
        lambda *_: pytest.fail("snapshot read before refusal"),
    )
    with pytest.raises(AssemblyError, match=r"^snapshot_selection_invalid$"):
        build.reviewed_selections()


def test_changed_tender_row_raw_refuses_before_cache_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from eii_custodian.publicdata import assembly_adapters

    row = replace(tender_entry(), kind="https_file")
    build = context(tmp_path, (row,))
    monkeypatch.setattr(
        assembly_adapters,
        "read_cached",
        lambda *_args, **_kwargs: pytest.fail("cache read before refusal"),
    )
    with pytest.raises(AssemblyError, match=r"^snapshot_selection_invalid$"):
        build.raw(row)


def test_pending_completeness_and_gate_have_one_absence_no_table(
    tmp_path: Path,
) -> None:
    from eii_custodian.publicdata import completeness as c
    from eii_custodian.publicdata import gate_report as g

    row = tender_entry()
    committed = load_confirmation(
        Path("custodian/publicdata/review/s2_t13_confirmation.yaml")
    )
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
    results = c.check(**inputs)
    assert [item for item in results if item["id"] == row.key] == [
        {
            "id": row.key,
            "state": "NO_DATA",
            "reason": OWN_RUN_REASON,
            "caveat": OWN_RUN_CAVEAT,
        }
    ]
    evidence = g.tender_evidence(committed, row, None, "s2_t13_confirmation.yaml")
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
    inputs["outputs"] = {row.key: ("pub_tender",)}
    assert any(
        item["state"] == "failed" and "output for absent source" in item["reason"]
        for item in c.check(**inputs)
    )


@pytest.mark.parametrize("plant", ["key", "kind", "receipt"])
def test_gate_refuses_foreign_pending_evidence(plant: str) -> None:
    from eii_custodian.publicdata import gate_report as g

    row = tender_entry()
    if plant == "key":
        row = replace(row, key="SYN-other")
    elif plant == "kind":
        row = replace(row, kind="https_file")
    receipts = {row.key: {"sha256": "a" * 64}} if plant == "receipt" else {}
    evidence = g.ConfirmationEvidence(
        "S2-T13",
        (row.key,),
        ("s2_t13_confirmation.yaml",),
        {"completion_evidence": True},
        absence_reasons={row.key: OWN_RUN_REASON},
    )
    result = next(
        item
        for item in g.confirmations([evidence], [row], receipts)
        if item["task"] == "S2-T13"
    )
    assert result["state"] == "pending"
    assert result["reason"] == "confirmation_pending"


def test_pinned_tender_missing_or_malformed_bytes_never_downgrades(
    tmp_path: Path,
) -> None:
    row = tender_entry()
    digest = "a" * 64
    (tmp_path / "snapshot_pins.json").write_text(json.dumps({row.key: digest}))
    build = context(tmp_path, (row,))
    with pytest.raises(ValueError, match=r"^snapshot_index_invalid$"):
        build.reviewed_selections()
    assert not build.source_tables
    assert not build.tables


def _fake_tender_adapter(
    monkeypatch: pytest.MonkeyPatch,
    seen: list[str],
    body: bytes = b"<html>SYN tender terms</html>",
) -> None:

    def pages(row, _sleep, cache):
        seen.append(row.key)
        assert cache is not None
        from eii_custodian.publicdata.fetch.awards import intake_cutoff

        cutoff, reason, digest = intake_cutoff(cache, "2026-11-21T00:00:00Z")
        assert cutoff is None
        pairs = [(name, lang) for name, _ in LIST_PATHS for lang in ("en", "ar")]
        _write_pages(
            cache / row.key,
            [(name, lang, 1, b"<html>SYN page</html>") for name, lang in pairs],
            [
                ListReading(
                    name,
                    lang,
                    1,
                    1,
                    "SYN",
                    "SYN",
                    cutoff_reason=reason,
                    workbook_sha256=digest,
                )
                for name, lang in pairs
            ],
        )
        return Prepared(b"", row.url, row.fetch_host, row.publisher, "", None, "", None)

    monkeypatch.setattr(kinds, "_paged_cards", pages)
    monkeypatch.setattr(
        fetch_build,
        "read_terms_page",
        lambda *_: TermsPage(terms_text_sha256(body), None, body),
    )


def _own_run(
    tmp_path: Path,
    *,
    resume: bool = False,
    stamp: str = "2026-11-21T00:00:00Z",
):
    return fetch_build.run_tenders_only(
        (tender_entry(),),
        lambda _url: pytest.fail("ordinary tender transport called"),
        tmp_path / "public_cache",
        tmp_path / "public_cache_tenders",
        lambda: stamp,
        lambda _seconds: None,
        resume=resume,
    )


@pytest.mark.parametrize("inventory", ["missing", "duplicate", "same_host"])
def test_only_exactly_one_tender_entry_can_enter_own_run(
    tmp_path: Path, inventory: str
) -> None:
    row = tender_entry()
    rows = (
        ()
        if inventory == "missing"
        else (
            row,
            row
            if inventory == "duplicate"
            else replace(
                row,
                key="awards_owner_scrape",
                source_id="awards_owner_scrape",
                kind="awards_intake",
            ),
        )
    )
    outcome = fetch_build.run_tenders_only(
        rows,
        lambda _url: pytest.fail("acquisition called"),
        tmp_path / "main",
        tmp_path / "own",
        lambda: "2026-11-21T00:00:00Z",
        lambda _: None,
    )
    assert outcome.failure is not None
    assert outcome.failure.check == "own_run_inventory_invalid"
    assert not (tmp_path / "own" / "build-run.json").exists()
    assert "own_run_inventory_invalid" in (tmp_path / "own/build-log.json").read_text()


def test_own_run_fetches_one_entry_and_keeps_main_journal_separate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[str] = []
    _fake_tender_adapter(monkeypatch, seen)
    outcome = _own_run(tmp_path)
    assert outcome.failure is None
    assert seen == ["tenders_pub"]
    own = tmp_path / "public_cache_tenders"
    assert json.loads((own / "build-run.json").read_bytes())["state"] == "complete"
    assert (own / "build-log.json").exists()
    assert not (tmp_path / "public_cache" / "build-run.json").exists()
    assert not (tmp_path / "public_cache" / "build-log.json").exists()
    assert not (tmp_path / "public_cache" / "snapshot_pins.json").exists()


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
    assert any("own_run" in line for line in outcome.lines)


def test_archive_failure_keeps_journal_interrupted_then_resume_reuses_pages(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from eii_custodian.publicdata import assembly_tenders

    seen: list[str] = []
    _fake_tender_adapter(monkeypatch, seen)
    archive = assembly_tenders.archive_pages
    monkeypatch.setattr(
        assembly_tenders,
        "archive_pages",
        lambda *_args, **_kw: (_ for _ in ()).throw(AssemblyError("plant")),
    )
    first = _own_run(tmp_path)
    own = tmp_path / "public_cache_tenders"
    assert first.failure is not None
    assert first.failure.check == "assembly_tender_pages_incomplete"
    assert json.loads((own / "build-run.json").read_bytes())["state"] == "interrupted"
    assert "assembly_tender_pages_incomplete" in (own / "build-log.json").read_text()
    monkeypatch.setattr(assembly_tenders, "archive_pages", archive)
    second = _own_run(tmp_path, resume=True)
    assert second.failure is None
    assert seen == ["tenders_pub"]
    assert any(line.startswith("REUSE tenders_pub ") for line in second.lines)
    assert json.loads((own / "build-run.json").read_bytes())["state"] == "complete"


def test_archive_log_failure_keeps_journal_interrupted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _fake_tender_adapter(monkeypatch, [])
    original = fetch_build._write_log

    def write_log(*args, **kwargs):
        if any(line.startswith("ARCHIVE ") for line in args[1]):
            raise OSError("SYN log write failure")
        return original(*args, **kwargs)

    monkeypatch.setattr(fetch_build, "_write_log", write_log)
    result = _own_run(tmp_path)
    own = tmp_path / "public_cache_tenders"
    assert result.failure is not None
    assert result.failure.check == "assembly_tender_pages_incomplete"
    assert json.loads((own / "build-run.json").read_bytes())["state"] == "interrupted"
    assert "assembly_tender_pages_incomplete" in (own / "build-log.json").read_text()


@pytest.mark.parametrize("plant", ["page", "receipt", "intake"])
def test_resume_refetches_changed_tender_input(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, plant: str
) -> None:
    from eii_custodian.publicdata import assembly_tenders

    seen: list[str] = []
    _fake_tender_adapter(monkeypatch, seen)
    archive = assembly_tenders.archive_pages
    monkeypatch.setattr(
        assembly_tenders,
        "archive_pages",
        lambda *_a, **_k: (_ for _ in ()).throw(AssemblyError("plant")),
    )
    assert _own_run(tmp_path).failure is not None
    own = tmp_path / "public_cache_tenders"
    monkeypatch.setattr(assembly_tenders, "archive_pages", archive)
    if plant == "page":
        (own / "tenders_pub/available/en/1.html").write_bytes(b"changed")
    elif plant == "receipt":
        (own / "tenders_pub/available/en.receipt.json").write_text("{}")
    else:
        folder = own / "intake/awards_owner_scrape"
        folder.mkdir(parents=True)
        (folder / "intake.json").write_text("{}")
    result = _own_run(tmp_path, resume=True)
    assert result.failure is None
    assert seen == ["tenders_pub", "tenders_pub"]
    assert any(
        line == "REFETCH tenders_pub resume_input_unproven" for line in result.lines
    )


@pytest.mark.parametrize(
    "plant,expected",
    [
        ("entries", "resume_record_invalid"),
        ("seed", "resume_seed_mismatch"),
        ("head", "resume_head_mismatch"),
        ("complete", "resume_not_interrupted"),
    ],
)
def test_own_run_resume_refuses_wrong_journal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, plant: str, expected: str
) -> None:
    from eii_custodian.publicdata import assembly_tenders

    _fake_tender_adapter(monkeypatch, [])
    monkeypatch.setattr(
        assembly_tenders,
        "archive_pages",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssemblyError("SYN stop")),
    )
    first = _own_run(tmp_path)
    assert first.failure is not None
    assert first.failure.check == "assembly_tender_pages_incomplete"
    path = tmp_path / "public_cache_tenders/build-run.json"
    row = json.loads(path.read_bytes())
    if plant == "entries":
        row["entries"]["SYN-extra"] = {"completed": False}
    elif plant == "seed":
        row["seed"] = 1
    elif plant == "head":
        row["head"] = "a" * 40
    else:
        row["state"] = "complete"
    path.write_text(json.dumps(row))
    result = _own_run(tmp_path, resume=True)
    assert result.failure is not None
    assert result.failure.check == expected


@pytest.mark.parametrize("plant", ["fetch", "terms"])
def test_own_run_failure_never_completes_or_overwrites_main(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, plant: str
) -> None:
    seen: list[str] = []
    _fake_tender_adapter(monkeypatch, seen)
    row = tender_entry()
    if plant == "fetch":
        monkeypatch.setattr(
            kinds,
            "_paged_cards",
            lambda *_: Prepared(
                b"",
                row.url,
                row.fetch_host,
                row.publisher,
                "",
                None,
                "",
                AttemptFailure(1, row.url, "SYN_fetch_failure", "", ""),
            ),
        )
    else:
        monkeypatch.setattr(
            fetch_build,
            "read_terms_page",
            lambda *_: TermsPage(
                "", AttemptFailure(1, row.terms_url, "SYN_terms_failure", "", "")
            ),
        )
    main = tmp_path / "public_cache"
    main.mkdir()
    (main / "build-run.json").write_text("SYN main journal")
    (main / "build-log.json").write_text("SYN main log")
    (main / "snapshot_pins.json").write_text("{}")
    result = _own_run(tmp_path)
    assert result.failure is not None
    assert result.failure.check == (
        "SYN_fetch_failure" if plant == "fetch" else "assembly_tender_pages_incomplete"
    )
    own = tmp_path / "public_cache_tenders"
    assert json.loads((own / "build-run.json").read_bytes())["state"] == "interrupted"
    assert "FAIL" in (own / "build-log.json").read_text()
    assert (main / "build-run.json").read_text() == "SYN main journal"
    assert (main / "build-log.json").read_text() == "SYN main log"
    assert (main / "snapshot_pins.json").read_text() == "{}"


def _prior_archive(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    stamped_hash: str | None = None,
) -> tuple[Path, str]:
    from eii_custodian.publicdata import assembly_tenders, confirm_s2_t13
    from eii_custodian.publicdata.fetch.snapshots import read_snapshot

    _fake_tender_adapter(monkeypatch, [])
    visible_hash = terms_text_sha256(b"<html>SYN tender terms</html>")
    if stamped_hash is not None:
        monkeypatch.setattr(
            assembly_tenders, "terms_visible_hash", lambda *_: stamped_hash
        )
    real = load_confirmation(
        Path("custodian/publicdata/review/s2_t13_confirmation.yaml")
    )
    invented = replace(
        real, tender=replace(real.tender, terms_sha256=stamped_hash or visible_hash)
    )
    monkeypatch.setattr(confirm_s2_t13, "load_confirmation", lambda *_: invented)
    main = tmp_path / "data/public_cache"
    outcome = fetch_build.run_tenders_only(
        (tender_entry(),),
        lambda _url: pytest.fail("transport called"),
        tmp_path / "unused",
        main,
        lambda: "2026-11-21T00:00:00Z",
        lambda _: None,
    )
    assert outcome.failure is None
    index = next((main / "tenders_pub/index").glob("*.json"))
    identity = index.stem
    assert read_snapshot(main / "tenders_pub", identity).sidecar["terms_sha256"] == (
        stamped_hash or visible_hash
    )
    (main / "snapshot_pins.json").write_text(json.dumps({"tenders_pub": identity}))
    return main, identity


def _archive_with_mismatched_body_terms(directory: Path, identity: str) -> str:
    from eii_custodian.publicdata.fetch.receipts import sha256_hex
    from eii_custodian.publicdata.fetch.snapshots import (
        publish_snapshot,
        read_snapshot,
    )

    original = read_snapshot(directory, identity)
    payload = json.loads(original.body)
    payload["terms_sha256"] = "f" * 64
    body = (json.dumps(payload, sort_keys=True) + "\n").encode()
    receipt = dict(original.sidecar, sha256=sha256_hex(body), bytes=len(body))
    return publish_snapshot(directory, "json", body, receipt).sha256


def test_handoff_refuses_archive_body_terms_mismatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    main, identity = _prior_archive(tmp_path, monkeypatch)
    forged = _archive_with_mismatched_body_terms(main / "tenders_pub", identity)
    (main / "snapshot_pins.json").write_text(json.dumps({"tenders_pub": forged}))
    own = tmp_path / "data/public_cache_tenders"
    result = fetch_build.run_tenders_only(
        (tender_entry(),),
        lambda _url: pytest.fail("network called"),
        main,
        own,
        lambda: "2026-11-21T01:00:00Z",
        lambda _: None,
    )
    assert result.failure is not None
    assert result.failure.check == "tender_handoff_refused"


def test_pickup_refuses_archive_body_terms_mismatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    main, identity = _prior_archive(tmp_path, monkeypatch)
    own = tmp_path / "data/public_cache_tenders"
    adopted = fetch_build.run_tenders_only(
        (tender_entry(),),
        lambda _url: pytest.fail("network called"),
        main,
        own,
        lambda: "2026-11-21T01:00:00Z",
        lambda _: None,
    )
    assert adopted.failure is None
    forged = _archive_with_mismatched_body_terms(own / "tenders_pub", identity)
    (main / "snapshot_pins.json").write_text(json.dumps({"tenders_pub": forged}))
    build = context(main, (tender_entry(),))
    with pytest.raises(AssemblyError, match=r"^assembly_tender_terms_incomplete$"):
        build.reviewed_selections()


def test_verified_handoff_keeps_identity_date_terms_and_avoids_request(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from eii_custodian.publicdata.fetch.snapshots import read_snapshot

    main, identity = _prior_archive(tmp_path, monkeypatch)
    own = tmp_path / "data/public_cache_tenders"
    result = fetch_build.run_tenders_only(
        (tender_entry(),),
        lambda _url: pytest.fail("network called"),
        main,
        own,
        lambda: "2026-11-21T01:00:00Z",
        lambda _: None,
    )
    assert result.failure is None
    assert result.lines == (f"HANDOFF tenders_pub sha256={identity}",)
    source = read_snapshot(main / "tenders_pub", identity)
    adopted = read_snapshot(own / "tenders_pub", identity)
    assert adopted.sidecar == source.sidecar
    assert adopted.body == source.body
    assert json.loads((own / "build-log.json").read_bytes())["terms"]
    assert json.loads((own / "build-run.json").read_bytes())["state"] == "complete"
    build = context(main, (tender_entry(),))
    build.reviewed_selections()
    assert (
        build.receipts["tenders_pub"]["retrieved_utc"]
        == source.sidecar["retrieved_utc"]
    )
    archive = build.raw(tender_entry(), standard_json=True)
    assert archive["method"] == "assembly-tender-pages.v1"
    from eii_custodian.publicdata import confirm_s2_t13
    from eii_custodian.publicdata import gate_report as g

    evidence = g.tender_evidence(
        confirm_s2_t13.load_confirmation(
            Path("custodian/publicdata/review/s2_t13_confirmation.yaml")
        ),
        tender_entry(),
        build.receipts["tenders_pub"],
        "invented review",
        archive,
    )
    assert evidence.details["sha256"] == identity
    assert evidence.details["retrieved_utc"] == source.sidecar["retrieved_utc"]
    assert len(evidence.details["awarded_readings"]) == 2


def test_legacy_page_proof_handoff_uses_archive_intake_without_request(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    main, identity = _prior_archive(tmp_path, monkeypatch)
    journal_path = main / "build-run.json"
    journal = json.loads(journal_path.read_bytes())
    journal["entries"]["tenders_pub"]["page_meta"].pop("intake")
    journal_path.write_text(json.dumps(journal))
    own = tmp_path / "data/public_cache_tenders"
    result = fetch_build.run_tenders_only(
        (tender_entry(),),
        lambda _url: pytest.fail("network called"),
        main,
        own,
        lambda: "2026-11-21T01:00:00Z",
        lambda _: None,
    )
    assert result.failure is None
    assert result.lines == (f"HANDOFF tenders_pub sha256={identity}",)
    assert (own / "tenders_pub/index" / f"{identity}.json").exists()


@pytest.mark.parametrize("plant", ["missing_named", "corrupt_receipt"])
def test_pinned_archive_never_falls_back_to_another_valid_archive(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, plant: str
) -> None:
    from eii_custodian.publicdata.fetch.snapshots import (
        publish_snapshot,
        read_snapshot,
    )

    main, identity = _prior_archive(tmp_path, monkeypatch)
    own = tmp_path / "data/public_cache_tenders"
    assert (
        fetch_build.run_tenders_only(
            (tender_entry(),),
            lambda _url: pytest.fail("network called"),
            main,
            own,
            lambda: "2026-11-21T01:00:00Z",
            lambda _: None,
        ).failure
        is None
    )
    named = read_snapshot(own / "tenders_pub", identity)
    other_sidecar = dict(named.sidecar)
    other_sidecar.pop("sha256")
    other_sidecar.pop("bytes")
    other = publish_snapshot(
        own / "tenders_pub", "json", named.body + b"\n", other_sidecar
    )
    assert other.sha256 != identity
    if plant == "missing_named":
        (own / "tenders_pub/index" / f"{identity}.json").unlink()
    else:
        named.receipt_path.write_text("{}")
    with pytest.raises(ValueError):
        context(main, (tender_entry(),)).reviewed_selections()


@pytest.mark.parametrize("plant", ["page", "receipt", "terms", "intake"])
def test_handoff_refuses_unproven_prior_result_and_records_refusal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, plant: str
) -> None:
    main, _identity = _prior_archive(tmp_path, monkeypatch)
    if plant == "page":
        (main / "tenders_pub/available/en/1.html").write_bytes(b"SYN changed")
    elif plant == "receipt":
        (main / "tenders_pub/available/en.receipt.json").write_text("{}")
    elif plant == "terms":
        log = json.loads((main / "build-log.json").read_bytes())
        log["terms"][0].pop("terms_body_sha256")
        (main / "build-log.json").write_text(json.dumps(log))
    else:
        folder = main / "intake/awards_owner_scrape"
        folder.mkdir(parents=True)
        (folder / "intake.json").write_text("{}")
    own = tmp_path / "data/public_cache_tenders"
    result = fetch_build.run_tenders_only(
        (tender_entry(),),
        lambda _url: pytest.fail("network called"),
        main,
        own,
        lambda: "2026-11-21T01:00:00Z",
        lambda _: None,
    )
    assert result.failure is not None
    assert result.failure.check == "tender_handoff_refused"
    assert json.loads((own / "build-run.json").read_bytes())["state"] == "interrupted"
    assert "tender_handoff_refused" in (own / "build-log.json").read_text()
    assert (main / "snapshot_pins.json").exists()


def test_own_run_log_write_failure_returns_named_refusal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        fetch_build,
        "_write_log",
        lambda *_args: (_ for _ in ()).throw(OSError("SYN log write failure")),
    )
    result = _own_run(tmp_path)
    assert result.failure is not None
    assert result.failure.check == "own_run_fetch_write_failed"
    assert "FAIL tenders_pub own_run_fetch_write_failed" in result.lines
    journal = json.loads(
        (tmp_path / "public_cache_tenders/build-run.json").read_bytes()
    )
    assert journal["state"] == "interrupted"


def test_handoff_refuses_proofless_main_skip_marker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    main, _identity = _prior_archive(tmp_path, monkeypatch)
    journal_path = main / "build-run.json"
    journal = json.loads(journal_path.read_bytes())
    journal["entries"]["tenders_pub"] = {"completed": True}
    journal_path.write_text(json.dumps(journal))
    own = tmp_path / "data/public_cache_tenders"
    result = fetch_build.run_tenders_only(
        (tender_entry(),),
        lambda _url: pytest.fail("network called"),
        main,
        own,
        lambda: "2026-11-21T01:00:00Z",
        lambda _: None,
    )
    assert result.failure is not None
    assert result.failure.check == "tender_handoff_refused"
    assert json.loads((own / "build-run.json").read_bytes())["state"] == "interrupted"


def test_handoff_refuses_archive_stamp_that_disagrees_with_verified_terms_log(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    main, _identity = _prior_archive(tmp_path, monkeypatch, stamped_hash="f" * 64)
    own = tmp_path / "data/public_cache_tenders"
    result = fetch_build.run_tenders_only(
        (tender_entry(),),
        lambda _url: pytest.fail("network called"),
        main,
        own,
        lambda: "2026-11-21T01:00:00Z",
        lambda _: None,
    )
    assert result.failure is not None
    assert result.failure.check == "tender_handoff_refused"
    assert json.loads((own / "build-run.json").read_bytes())["state"] == "interrupted"


@pytest.mark.parametrize("plant", ["log", "finish"])
def test_handoff_write_failure_retains_identity_record_and_refetches_on_resume(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, plant: str
) -> None:
    from eii_custodian.publicdata.fetch.resume import RunRecord

    main, identity = _prior_archive(tmp_path, monkeypatch)
    own = tmp_path / "data/public_cache_tenders"
    original_log = fetch_build._write_log
    original_finish = RunRecord.finish
    if plant == "log":
        calls = 0

        def fail_handoff_log(*args):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise OSError("SYN handoff log failure")
            return original_log(*args)

        monkeypatch.setattr(fetch_build, "_write_log", fail_handoff_log)
    else:
        monkeypatch.setattr(
            RunRecord,
            "finish",
            lambda _self: (_ for _ in ()).throw(OSError("SYN finish failure")),
        )
    failed = fetch_build.run_tenders_only(
        (tender_entry(),),
        lambda _url: pytest.fail("network called"),
        main,
        own,
        lambda: "2026-11-21T01:00:00Z",
        lambda _: None,
    )
    assert failed.failure is not None
    assert failed.failure.check == "tender_handoff_write_failed"
    assert f"HANDOFF tenders_pub sha256={identity}" in failed.lines
    assert "FAIL tenders_pub tender_handoff_write_failed" in failed.lines
    log = json.loads((own / "build-log.json").read_bytes())
    assert log["terms"]
    assert f"HANDOFF tenders_pub sha256={identity}" in log["lines"]
    assert json.loads((own / "build-run.json").read_bytes())["state"] == "interrupted"
    monkeypatch.setattr(fetch_build, "_write_log", original_log)
    monkeypatch.setattr(RunRecord, "finish", original_finish)
    resumed = fetch_build.run_tenders_only(
        (tender_entry(),),
        lambda _url: pytest.fail("network called"),
        main,
        own,
        lambda: "2026-11-21T01:00:00Z",
        lambda _: None,
        resume=True,
    )
    assert resumed.failure is None
    if plant == "finish":
        assert "REFETCH tenders_pub resume_input_unproven" in resumed.lines
    else:
        assert any(line.startswith("PASS tenders_pub ") for line in resumed.lines)
