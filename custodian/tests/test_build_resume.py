"""S2-P37: invented SYN entries and in-memory transport; no public bytes."""

from __future__ import annotations

import json
import os
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from commands import build_public
from eii_custodian.publicdata.assembly import AssemblyError
from eii_custodian.publicdata.assembly_adapters import Production
from eii_custodian.publicdata.fetch.build import run_build
from eii_custodian.publicdata.fetch.cadence import Cadence
from eii_custodian.publicdata.fetch.registry import Entry
from eii_custodian.publicdata.fetch.transport import Response, TransportFault

START = "2026-11-21T00:00:00Z"
EARLIER = "2026-11-20T00:00:00Z"
LATER = "2026-11-21T01:00:00Z"
HEAD = "a" * 40


def entry(key: str) -> Entry:
    return Entry(
        refetch=Cadence("none", "frequency_unconfirmed", ""),
        key=key,
        source_id=key,
        slug="",
        kind="https_file",
        title_en="SYN invented source",
        publisher="SYN invented publisher",
        licence_id="CC-BY-4.0",
        licence_basis="dataset",
        decision_record="",
        fetch_host="www.data.gov.qa",
        url=f"https://www.data.gov.qa/SYN/{key}.bin",
        terms_url="",
        nightly_live_fetch=False,
        public_splits=(),
        commit_allowed=False,
        release_tables=(),
        caveat_keys=(),
        columns=(),
        row_count_min=None,
        row_count_max=None,
        period_first="",
        period_last="",
        period_field="",
        reconciliation="none",
        skip_reason="",
        extension="bin",
        landing_url="",
        terms_words="SYN invented terms",
        terms_read_on="2026-11-21",
    )


class Harness:
    def __init__(self, cache: Path) -> None:
        self.cache = cache
        self.entries = (entry("SYN-first"), entry("SYN-second"))
        self.seen: list[str] = []
        self.fail = True
        self.stamp = START
        self.assembled: list[int] = []

    def transport(self, url: str) -> Response:
        self.seen.append(url)
        if self.fail and url == self.entries[1].url:
            raise TransportFault("unreachable", url)
        return Response(url, b"SYN invented bytes " + url.encode(), ())

    def run(self, **kwargs: Any) -> Any:
        return run_build(
            self.entries,
            self.transport,
            self.cache,
            lambda: self.stamp,
            lambda seconds: None,
            seed=17,
            **kwargs,
        )

    def interrupt(self) -> None:
        outcome = self.run()
        assert outcome.failure is not None
        assert outcome.failure.code == 6
        self.fail = False
        self.seen.clear()
        self.stamp = LATER


@pytest.fixture
def harness(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Harness:
    fixture = Harness(tmp_path / "cache")

    def assemble(self: Production) -> tuple[str, ...]:
        # Exercise the actual fetcher. Only the unrelated production producers
        # are replaced, so every invocation must cross this boundary again.
        assert self.fetcher is not None
        self.fetched = self.fetcher()
        self.lines.extend(self.fetched.lines)
        if self.fetched.failure:
            raise AssemblyError("assembly_fetch_refused")
        fixture.assembled.append(self.seed)
        return ()

    monkeypatch.setattr(Production, "run", assemble)
    return fixture


def record(harness: Harness) -> dict[str, Any]:
    return json.loads((harness.cache / "build-run.json").read_bytes())


def test_interrupted_run_is_durable_before_resume(harness: Harness) -> None:
    harness.interrupt()
    row = record(harness)
    assert row["started_utc"] == START
    assert row["seed"] == 17
    assert len(row["head"]) == 40
    assert row["state"] == "interrupted"
    assert row["entries"]["SYN-first"]["completed"] is True
    assert row["entries"]["SYN-second"]["completed"] is False


def test_resume_reuses_only_completed_bytes_and_preserves_provenance(
    harness: Harness,
) -> None:
    harness.interrupt()
    before = {
        p: p.read_bytes()
        for p in (harness.cache / "SYN-first").rglob("*")
        if p.is_file()
    }
    outcome = harness.run(resume=True)
    assert outcome.failure is None
    assert harness.seen == [harness.entries[1].url]
    assert all(p.read_bytes() == body for p, body in before.items())
    log = json.loads((harness.cache / "build-log.json").read_bytes())
    reused = [line for line in log["lines"] if line.startswith("REUSE SYN-first ")]
    assert len(reused) == 1
    assert f"interrupted_start={START}" in reused[0]
    assert f"retrieved_utc={START}" in reused[0]
    assert "publisher=SYN invented publisher" in reused[0]
    side = json.loads(
        next((harness.cache / "SYN-first").glob("*.meta.json")).read_bytes()
    )
    assert f"sha256={side['sha256']}" in reused[0]
    assert record(harness)["state"] == "complete"
    assert harness.assembled == [17]


@pytest.mark.parametrize(
    "plant",
    [
        "body",
        "receipt",
        "missing_body",
        "index",
        "old_body",
        "old_receipt",
        "old_retrieval",
        "publisher",
    ],
)
def test_unproven_completed_bytes_are_refetched(harness: Harness, plant: str) -> None:
    harness.interrupt()
    directory = harness.cache / "SYN-first"
    index = next((directory / "index").glob("*.json"))
    row = json.loads(index.read_bytes())
    body = directory / row["path"]
    receipt = directory / row["receipt"]
    if plant == "body":
        body.write_bytes(b"SYN tampered")
    elif plant == "receipt":
        receipt.unlink()
    elif plant == "missing_body":
        body.unlink()
    elif plant == "index":
        index.write_text("{}")
    elif plant.startswith("old_") and plant != "old_retrieval":
        old = 1
        os.utime(body if plant == "old_body" else receipt, (old, old))
    else:
        side = json.loads(receipt.read_bytes())
        side["retrieved_utc" if plant == "old_retrieval" else "publisher"] = (
            "2020-01-01T00:00:00Z"
            if plant == "old_retrieval"
            else "SYN changed publisher"
        )
        receipt.write_text(json.dumps(side))
    # Refetch has different invented bytes: immutable archive damage must not
    # be repaired by overwriting historical objects in order to pass the test.
    original = harness.transport

    def fresh(url: str) -> Response:
        response = original(url)
        return replace(response, body=response.body + b" SYN refreshed")

    harness.transport = fresh  # type: ignore[method-assign]
    outcome = harness.run(resume=True)
    assert harness.entries[0].url in harness.seen
    assert harness.entries[1].url in harness.seen
    assert not any(line.startswith("REUSE SYN-first ") for line in outcome.lines)
    assert outcome.failure is None


@pytest.mark.parametrize(
    "plant,reason",
    [
        ("missing", "resume_record_missing"),
        ("complete", "resume_not_interrupted"),
        ("seed", "resume_seed_mismatch"),
        ("head", "resume_head_mismatch"),
        ("invalid", "resume_record_invalid"),
    ],
)
def test_resume_refuses_unmatched_run_without_fetch(
    harness: Harness, plant: str, reason: str
) -> None:
    harness.interrupt()
    path = harness.cache / "build-run.json"
    row = record(harness)
    if plant == "missing":
        path.unlink()
    else:
        if plant == "complete":
            row["state"] = "complete"
        elif plant == "seed":
            row["seed"] = 18
        elif plant == "head":
            row["head"] = HEAD if row["head"] != HEAD else "b" * 40
        if plant == "invalid":
            path.write_text("[]")
        else:
            path.write_text(json.dumps(row))
    before = path.read_bytes() if path.exists() else None
    outcome = harness.run(resume=True)
    assert outcome.failure is not None
    assert outcome.failure.check == reason
    assert harness.seen == []
    assert (path.read_bytes() if path.exists() else None) == before


def test_completed_build_is_not_resumable_and_ordinary_build_refetches(
    harness: Harness,
) -> None:
    harness.fail = False
    assert harness.run().failure is None
    assert record(harness)["state"] == "complete"
    harness.seen.clear()
    assert harness.run(resume=True).failure.check == "resume_not_interrupted"
    assert harness.seen == []
    assert harness.run().failure is None
    assert harness.seen == [e.url for e in harness.entries]
    assert harness.assembled == [17, 17]


def test_resume_rechecks_terms_instead_of_reusing_readings(harness: Harness) -> None:
    harness.entries = (
        replace(harness.entries[0], terms_url="https://www.data.gov.qa/SYN/terms"),
        harness.entries[1],
    )
    harness.interrupt()
    outcome = harness.run(resume=True)
    assert outcome.failure is None
    assert harness.entries[0].url not in harness.seen
    assert harness.entries[0].terms_url in harness.seen
    assert harness.entries[1].url in harness.seen


def test_exact_resume_command_form_reaches_assembly(
    harness: Harness, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    harness.interrupt()
    monkeypatch.setattr(build_public, "CACHE_RELATIVE", "cache")
    monkeypatch.setattr(build_public, "load_registry", lambda: harness.entries)
    monkeypatch.setattr(build_public, "utc_now", lambda: harness.stamp)
    assert (
        build_public.run(
            tmp_path,
            {},
            ("--seed", "17", "--resume"),
            transport=harness.transport,
            sleep=lambda seconds: None,
        )
        == 0
    )
    assert harness.entries[0].url not in harness.seen


@pytest.mark.parametrize(
    "args",
    [
        ("--resume",),
        ("--resume", "--seed", "17"),
        ("--seed", "17", "--resume", "extra"),
        ("--seed", "17", "--resume", "--resume"),
        ("--company-web", "--resume"),
        ("--seed", "oops", "--resume"),
    ],
)
def test_other_resume_forms_are_usage_errors_before_reads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, args: tuple[str, ...]
) -> None:
    def forbidden(*args: Any, **kwargs: Any) -> Any:
        pytest.fail("SYN unexpected input or network")

    monkeypatch.setattr(build_public, "load_registry", forbidden)
    monkeypatch.setattr(build_public, "earthdata_token", forbidden)
    assert build_public.run(tmp_path, {}, args, transport=forbidden) == 2
    assert list(tmp_path.iterdir()) == []


def test_data_completion_survives_exception_before_terms(harness: Harness) -> None:
    from eii_custodian.publicdata.fetch.certificate_pins import PinError

    harness.entries = (
        replace(harness.entries[0], terms_url="https://www.data.gov.qa/SYN/terms"),
        harness.entries[1],
    )
    original = harness.transport

    def interrupted(url: str) -> Response:
        if url == harness.entries[0].terms_url:
            raise PinError("certificate_chain_incomplete")
        return original(url)

    harness.transport = interrupted  # type: ignore[method-assign]
    result = harness.run()
    assert result.failure is not None
    assert record(harness)["entries"]["SYN-first"]["completed"] is True
    assert record(harness)["state"] == "interrupted"
    harness.transport = original  # type: ignore[method-assign]
    harness.fail = False
    harness.seen.clear()
    assert harness.run(resume=True).failure is None
    assert harness.entries[0].url not in harness.seen
    assert harness.entries[0].terms_url in harness.seen
    assert harness.entries[1].url in harness.seen


def test_keyboard_interruption_leaves_durable_progress(harness: Harness) -> None:
    original = harness.transport

    def interrupted(url: str) -> Response:
        if url == harness.entries[1].url:
            raise KeyboardInterrupt
        return original(url)

    harness.transport = interrupted  # type: ignore[method-assign]
    with pytest.raises(KeyboardInterrupt):
        harness.run()
    assert record(harness)["entries"]["SYN-first"]["completed"] is True
    harness.transport = original  # type: ignore[method-assign]
    harness.fail = False
    harness.seen.clear()
    assert harness.run(resume=True).failure is None
    assert harness.seen == [harness.entries[1].url]


def test_resume_does_not_replay_post_fetch_success(
    harness: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    harness.interrupt()

    def refuse(self: Production) -> tuple[str, ...]:
        assert self.fetcher is not None
        self.fetched = self.fetcher()
        self.lines.extend(self.fetched.lines)
        assert self.fetched.failure is None
        raise AssemblyError("assembly_regression_refused")

    monkeypatch.setattr(Production, "run", refuse)
    result = harness.run(resume=True)
    assert result.failure is not None
    assert result.failure.check == "assembly_regression_refused"
    assert record(harness)["state"] == "interrupted"
    assert harness.seen == [harness.entries[1].url]


def test_incomplete_marker_always_refetches_even_with_valid_proof(
    harness: Harness,
) -> None:
    harness.interrupt()
    row = record(harness)
    row["entries"]["SYN-first"]["completed"] = False
    (harness.cache / "build-run.json").write_text(json.dumps(row))
    assert harness.run(resume=True).failure is None
    assert harness.seen == [e.url for e in harness.entries]


@pytest.mark.parametrize(
    "plant",
    ["alias", "alias_receipt", "alias_missing", "state", "proof_schema", "auxiliary"],
)
def test_secondary_receipt_proofs_are_required(
    harness: Harness, plant: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    if plant == "auxiliary":
        from eii_custodian.publicdata.fetch import build
        from eii_custodian.publicdata.fetch.receipts import archive_auxiliary

        original = build._fetch_row

        def fetch(*args: Any, **kwargs: Any) -> Any:
            fetched, failure = original(*args, **kwargs)
            if fetched is not None:
                source = args[0]
                archive_auxiliary(
                    source,
                    harness.cache / source.key,
                    "inputs",
                    b"SYN auxiliary bytes",
                    START,
                    source.url,
                )
            return fetched, failure

        monkeypatch.setattr(build, "_fetch_row", fetch)
    harness.interrupt()
    folder = harness.cache / "SYN-first"
    row = record(harness)
    if plant == "state":
        row["entries"]["SYN-first"]["fetch"]["retrieved_utc"] = LATER
    elif plant == "proof_schema":
        row["entries"]["SYN-first"]["proofs"] = [None]
    elif plant == "auxiliary":
        auxiliary = next((folder / "inputs").glob("????-??-??/*.html"))
        auxiliary.write_bytes(b"SYN damaged auxiliary")
    else:
        alias = next(
            folder.glob("*.meta.json" if plant == "alias_receipt" else "*.bin")
        )
        alias.unlink()
        if plant != "alias_missing":
            alias.write_bytes(b"SYN damaged alias")
    if plant in {"state", "proof_schema"}:
        (harness.cache / "build-run.json").write_text(json.dumps(row))
    # This check is about the decision to refetch, including an immutable cache
    # refusal if a damaged content-addressed object cannot be overwritten.
    harness.run(resume=True)
    assert harness.entries[0].url in harness.seen


@pytest.mark.parametrize("layout", ["detached", "loose", "packed", "worktree"])
def test_head_reader_uses_only_git_metadata(tmp_path: Path, layout: str) -> None:
    from eii_custodian.publicdata.fetch.resume import repository_head

    git = tmp_path / ".git"
    if layout == "worktree":
        metadata = tmp_path / "SYN-worktree-metadata"
        common = tmp_path / "SYN-common-metadata"
        metadata.mkdir()
        common.mkdir()
        git.write_text("gitdir: SYN-worktree-metadata\n")
        (metadata / "commondir").write_text("../SYN-common-metadata\n")
    else:
        git.mkdir()
        metadata = common = git
    (metadata / "HEAD").write_text(
        HEAD + "\n" if layout == "detached" else "ref: refs/heads/SYN-branch\n"
    )
    if layout in {"loose", "worktree"}:
        ref = common / "refs/heads/SYN-branch"
        ref.parent.mkdir(parents=True)
        ref.write_text(HEAD + "\n")
    elif layout == "packed":
        (common / "packed-refs").write_text(
            "# pack-refs with: peeled\n" + HEAD + " refs/heads/SYN-branch\n"
        )
    assert repository_head(tmp_path) == HEAD


def test_unreadable_head_is_named_and_never_fetches(
    harness: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    from eii_custodian.publicdata.fetch import resume

    def refuse() -> str:
        raise resume.ResumeError("resume_head_unavailable")

    monkeypatch.setattr(resume, "repository_head", refuse)
    result = harness.run()
    assert result.failure.check == "resume_head_unavailable"
    assert harness.seen == []


def test_changed_run_entry_set_is_refused(harness: Harness) -> None:
    harness.interrupt()
    row = record(harness)
    del row["entries"]["SYN-first"]
    (harness.cache / "build-run.json").write_text(json.dumps(row))
    assert harness.run(resume=True).failure.check == "resume_record_invalid"
    assert harness.seen == []


@pytest.fixture
def paged(harness: Harness, monkeypatch: pytest.MonkeyPatch) -> Harness:
    from eii_custodian.publicdata.fetch import kinds
    from eii_custodian.publicdata.singles.tenders import (
        LIST_PATHS,
        ListReading,
        _write_pages,
    )

    harness.entries = (
        replace(harness.entries[0], kind="paged_cards"),
        harness.entries[1],
    )

    def fetch_pages(source: Entry, sleep: Any, cache: Path | None) -> Any:
        assert cache is not None
        stored = []
        readings = []
        for name, _ in LIST_PATHS:
            for language in ("en", "ar"):
                response = harness.transport(f"{source.url}/{name}/{language}/1")
                stored.append((name, language, 1, response.body))
                readings.append(
                    ListReading(name, language, 1, 1, harness.stamp, harness.stamp)
                )
        _write_pages(cache / source.key, stored, readings)
        return kinds.Prepared(
            b"", source.url, source.fetch_host, source.publisher, "", None, "", None
        )

    monkeypatch.setattr(kinds, "_paged_cards", fetch_pages)
    return harness


def test_paged_portal_resume_reuses_every_page_and_receipt(paged: Harness) -> None:
    paged.interrupt()
    folder = paged.cache / "SYN-first"
    before = {path: path.read_bytes() for path in folder.rglob("*") if path.is_file()}
    result = paged.run(resume=True)
    assert result.failure is None
    assert paged.seen == [paged.entries[1].url]
    assert all(path.read_bytes() == body for path, body in before.items())
    assert any(line.startswith("REUSE SYN-first ") for line in result.lines)


@pytest.mark.parametrize(
    "plant",
    [
        "page",
        "receipt",
        "missing_page",
        "missing_receipt",
        "old_page",
        "old_receipt",
        "extra_page",
    ],
)
def test_paged_portal_refetches_any_unproven_page(paged: Harness, plant: str) -> None:
    paged.interrupt()
    folder = paged.cache / "SYN-first"
    page = next(folder.rglob("*.html"))
    receipt = next(folder.rglob("*.receipt.json"))
    if plant == "page":
        page.write_bytes(b"SYN changed page")
    elif plant == "receipt":
        receipt.write_bytes(b"SYN changed receipt")
    elif plant.startswith("missing"):
        (page if plant == "missing_page" else receipt).unlink()
    elif plant.startswith("old"):
        os.utime(page if plant == "old_page" else receipt, (1, 1))
    else:
        page.with_name("2.html").write_bytes(b"SYN extra page")
    result = paged.run(resume=True)
    assert result.failure is None
    assert len(paged.seen) > 1
    assert not any(line.startswith("REUSE SYN-first ") for line in result.lines)


def test_paged_receipt_valid_json_is_still_bound_to_original_hash(
    paged: Harness,
) -> None:
    paged.interrupt()
    receipt = next((paged.cache / "SYN-first").rglob("*.receipt.json"))
    reading = json.loads(receipt.read_bytes())
    reading["first_hour"] = LATER
    receipt.write_text(json.dumps(reading))
    assert paged.run(resume=True).failure is None
    assert len(paged.seen) > 1


@pytest.mark.parametrize("field", ["language", "pages_read", "list_name"])
def test_new_malformed_page_receipt_never_becomes_reuse_proof(
    paged: Harness, monkeypatch: pytest.MonkeyPatch, field: str
) -> None:
    from eii_custodian.publicdata.fetch import kinds

    original = kinds._paged_cards

    def malformed(*args: Any, **kwargs: Any) -> Any:
        prepared = original(*args, **kwargs)
        receipt = next((paged.cache / "SYN-first").rglob("*.receipt.json"))
        reading = json.loads(receipt.read_bytes())
        reading[field] = 0 if field == "pages_read" else "SYN-other"
        receipt.write_text(json.dumps(reading))
        return prepared

    monkeypatch.setattr(kinds, "_paged_cards", malformed)
    paged.interrupt()
    monkeypatch.setattr(kinds, "_paged_cards", original)
    assert paged.run(resume=True).failure is None
    assert len(paged.seen) > 1


def test_reuse_proof_cannot_select_a_sibling_entry(harness: Harness) -> None:
    import shutil

    harness.interrupt()
    row = record(harness)
    proof = row["entries"]["SYN-first"]["proofs"][0]
    old_directory = proof["directory"]
    new_directory = "SYN-other"
    shutil.copytree(harness.cache / old_directory, harness.cache / new_directory)
    proof["directory"] = new_directory
    proof["files"] = {
        name.replace(old_directory + "/", new_directory + "/", 1): digest
        for name, digest in proof["files"].items()
    }
    (harness.cache / "build-run.json").write_text(json.dumps(row))
    assert harness.run(resume=True).failure is None
    assert harness.entries[0].url in harness.seen


@pytest.mark.parametrize(
    "state", [None, {}, {"digest": "SYN"}, "extra_field", "wrong_bool"]
)
def test_malformed_fetch_state_refetches_instead_of_breaking_resume(
    harness: Harness, state: object
) -> None:
    harness.interrupt()
    row = record(harness)
    if state == "extra_field":
        state = dict(row["entries"]["SYN-first"]["fetch"], SYN_unknown="SYN-value")
    elif state == "wrong_bool":
        state = dict(
            row["entries"]["SYN-first"]["fetch"], licence_unstated="SYN-not-a-boolean"
        )
    row["entries"]["SYN-first"]["fetch"] = state
    (harness.cache / "build-run.json").write_text(json.dumps(row))
    assert harness.run(resume=True).failure is None
    assert harness.seen == [e.url for e in harness.entries]


def test_missing_file_meta_hash_is_not_a_complete_proof(harness: Harness) -> None:
    harness.interrupt()
    row = record(harness)
    files = row["entries"]["SYN-first"]["proofs"][0]["files"]
    files.pop(
        next(name for name in files if name.endswith(".bin") and name.count("/") == 1)
    )
    (harness.cache / "build-run.json").write_text(json.dumps(row))
    assert harness.run(resume=True).failure is None
    assert harness.entries[0].url in harness.seen


def test_reuse_log_survives_later_terms_exception(harness: Harness) -> None:
    from eii_custodian.publicdata.fetch.certificate_pins import PinError

    harness.entries = (
        replace(harness.entries[0], terms_url="https://www.data.gov.qa/SYN/terms"),
        harness.entries[1],
    )
    harness.interrupt()
    original = harness.transport

    def fail_terms(url: str) -> Response:
        if url == harness.entries[0].terms_url:
            raise PinError("certificate_chain_incomplete")
        return original(url)

    harness.transport = fail_terms  # type: ignore[method-assign]
    result = harness.run(resume=True)
    assert result.failure is not None
    log = json.loads((harness.cache / "build-log.json").read_bytes())
    assert any(line.startswith("REUSE SYN-first ") for line in result.lines)
    assert any(line.startswith("REUSE SYN-first ") for line in log["lines"])
    assert record(harness)["state"] == "interrupted"


def test_first_fetch_failure_still_leaves_run_record(harness: Harness) -> None:
    def fail(url: str) -> Response:
        raise TransportFault("unreachable", url)

    harness.transport = fail  # type: ignore[method-assign]
    result = harness.run()
    assert result.failure is not None
    assert result.failure.code == 6
    row = record(harness)
    assert row["started_utc"] == START
    assert row["state"] == "interrupted"
    assert not any(item["completed"] for item in row["entries"].values())


def test_journal_keeps_existing_secret_guard(harness: Harness) -> None:
    marker = harness.entries[0].publisher
    harness.run(environ={"BESTTIME_API_KEY_PRIVATE": marker})
    assert marker not in (harness.cache / "build-run.json").read_text()


def test_exception_log_keeps_existing_secret_guard(
    harness: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    from eii_custodian.publicdata.fetch import build
    from eii_custodian.publicdata.fetch.certificate_pins import PinError

    harness.entries = (
        replace(harness.entries[0], terms_url="https://www.data.gov.qa/SYN/terms"),
        harness.entries[1],
    )

    reached: list[bool] = []

    def fail(*args: Any, **kwargs: Any) -> None:
        reached.append(True)
        args[4].append("api_key_private=SYN-invented-marker")
        raise PinError("certificate_chain_incomplete")

    monkeypatch.setattr(build, "_read_terms_apart", fail)
    try:
        harness.run()
    except ValueError as error:
        assert "secret_in_output" in str(error)
    assert reached == [True]
    log = (harness.cache / "build-log.json").read_text()
    assert "api_key_private=" not in log


def test_paged_archive_retains_original_retrieval_time(
    paged: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    from eii_custodian.publicdata.fetch.snapshots import read_snapshot

    paged.interrupt()

    def assemble(self: Production) -> tuple[str, ...]:
        self.stamp = LATER
        self.fetch_archive()
        return ()

    monkeypatch.setattr(Production, "run", assemble)
    assert paged.run(resume=True).failure is None
    assert paged.seen == [paged.entries[1].url]
    folder = paged.cache / "SYN-first"
    index = next((folder / "index").glob("*.json"))
    snapshot = read_snapshot(folder, index.stem)
    assert snapshot.sidecar["retrieved_utc"] == START


def test_review_auxiliary_retrieved_before_start_is_refetched(
    harness: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Fresh mtimes cannot override an auxiliary receipt's older retrieval."""
    from eii_custodian.publicdata.fetch import build
    from eii_custodian.publicdata.fetch.receipts import archive_auxiliary

    original = build._fetch_row

    def fetch(*args: Any, **kwargs: Any) -> Any:
        fetched, failure = original(*args, **kwargs)
        if fetched is not None:
            source = args[0]
            archive_auxiliary(
                source,
                harness.cache / source.key,
                "inputs",
                b"SYN auxiliary bytes",
                EARLIER,
                source.url,
            )
        return fetched, failure

    monkeypatch.setattr(build, "_fetch_row", fetch)
    harness.interrupt()
    outcome = harness.run(resume=True)
    assert outcome.failure is None
    assert harness.entries[0].url in harness.seen
    assert not any(line.startswith("REUSE SYN-first ") for line in outcome.lines)


@pytest.mark.parametrize("terms_url", [False, True])
def test_review_paged_portal_with_archived_terms_is_reused(
    paged: Harness, terms_url: bool
) -> None:
    """Earlier terms and terms read after page fetch are outside its inventory."""
    from eii_custodian.publicdata.fetch.receipts import archive_auxiliary

    url = "https://www.data.gov.qa/SYN/terms"
    if terms_url:
        paged.entries = (replace(paged.entries[0], terms_url=url), paged.entries[1])
    source = paged.entries[0]
    archive_auxiliary(
        source,
        paged.cache / source.key,
        "terms",
        b"SYN earlier terms page",
        EARLIER,
        url,
    )
    paged.interrupt()
    result = paged.run(resume=True)
    assert result.failure is None
    assert paged.seen == ([url] if terms_url else []) + [paged.entries[1].url]
    assert any(line.startswith("REUSE SYN-first ") for line in result.lines)


@pytest.mark.parametrize("operation", ["fetched", "paged_fetched", "reuse"])
def test_later_journal_write_failure_is_named(
    harness: Harness, paged: Harness, monkeypatch: pytest.MonkeyPatch, operation: str
) -> None:
    from eii_custodian.publicdata.fetch.resume import RunRecord

    # The paged fixture shares the harness; restore the standard source for
    # the other cases, so both fetched() branches get exercised.
    if operation != "paged_fetched":
        harness.entries = (entry("SYN-first"), harness.entries[1])
    if operation == "reuse":
        harness.interrupt()
        row = record(harness)
        row["entries"]["SYN-first"]["proofs"] = []
        (harness.cache / "build-run.json").write_text(json.dumps(row))
    original = RunRecord.write
    attempts = []

    def fail_later(self: RunRecord) -> None:
        attempts.append(self.row["entries"]["SYN-first"]["completed"])
        if operation == "reuse" or len(attempts) > 1:
            raise OSError("SYN journal write failure")
        original(self)

    monkeypatch.setattr(RunRecord, "write", fail_later)
    result = harness.run(resume=operation == "reuse")
    assert len(attempts) == (1 if operation == "reuse" else 2)
    assert result.failure is not None
    assert result.failure.code == 1
    assert result.failure.source_id == harness.entries[0].source_id
    assert result.failure.check == "resume_record_write_failed"
    assert any("resume_record_write_failed" in line for line in result.lines)
    assert harness.entries[1].url not in harness.seen
    assert record(harness)["state"] == "interrupted"


@pytest.mark.parametrize(
    "adapter",
    [
        "benchmark",
        "baci",
        "gravity",
        "atlas",
        "page",
        "citation",
        "comtrade",
        "release",
        "place",
    ],
)
def test_note_journal_write_failure_is_named(
    harness: Harness, monkeypatch: pytest.MonkeyPatch, adapter: str
) -> None:
    """Every specialised fetch seam stops on a failed completion write."""
    from types import SimpleNamespace

    from eii_custodian.publicdata.fetch import build, page_records
    from eii_custodian.publicdata.fetch.resume import RunRecord

    source = harness.entries[0]
    if adapter == "benchmark":
        monkeypatch.setattr(build, "BENCHMARK_TABLES", {source.source_id: "SYN-table"})
        monkeypatch.setattr(
            build,
            "load_policies",
            lambda: {source.source_id: SimpleNamespace(confirmed=True)},
        )
        monkeypatch.setattr(build, "owner_obstacle", lambda policy: None)
        monkeypatch.setattr(build, "fetch_benchmark", lambda *args: object())
    elif adapter in {"baci", "gravity", "atlas"}:
        source = replace(
            source,
            source_id={
                "baci": "cepii_baci",
                "gravity": "cepii_gravity",
                "atlas": "atlas_complexity",
            }[adapter],
        )
        monkeypatch.setattr(
            build,
            "load_config" if adapter == "baci" else f"load_{adapter}_config",
            lambda: None,
        )
        monkeypatch.setattr(build, f"fetch_{adapter}", lambda *args: object())
    elif adapter == "page":
        source = replace(source, kind="public_page")
        monkeypatch.setattr(page_records, "fetch_page", lambda *args: object())
    elif adapter == "citation":
        source = replace(source, kind="citation_only")
    elif adapter == "comtrade":
        source = replace(source, kind="comtrade_api")
        monkeypatch.setattr(build, "_comtrade_dispatch", lambda *args: None)
    else:
        monkeypatch.setattr(
            build,
            "is_release_entry" if adapter == "release" else "is_place_file",
            lambda entry: True,
        )
        monkeypatch.setattr(
            build,
            "fetch_release" if adapter == "release" else "fetch_place_file",
            lambda *args, **kwargs: (object(), None),
        )
    harness.entries = (source, harness.entries[1])
    original = RunRecord.write
    attempts = []

    def fail_later(self: RunRecord) -> None:
        attempts.append(self.row["entries"][source.key]["completed"])
        if len(attempts) > 1:
            raise OSError("SYN journal write failure")
        original(self)

    monkeypatch.setattr(RunRecord, "write", fail_later)
    result = harness.run()
    assert attempts == [False, True]
    assert result.failure is not None
    assert result.failure.code == 1
    assert result.failure.source_id == source.source_id
    assert result.failure.check == "resume_record_write_failed"
    assert any("resume_record_write_failed" in line for line in result.lines)
    assert harness.entries[1].url not in harness.seen
    assert record(harness)["state"] == "interrupted"


def test_fetched_symlink_outside_cache_records_unavailable_proof(
    harness: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    from eii_custodian.publicdata.fetch import build

    original = build._fetch_row

    def fetch(*args: Any, **kwargs: Any) -> Any:
        fetched, failure = original(*args, **kwargs)
        if fetched is not None:
            folder = harness.cache / args[0].key
            destination = harness.cache.parent / "SYN-outside-cache"
            folder.rename(destination)
            folder.symlink_to(destination, target_is_directory=True)
        return fetched, failure

    monkeypatch.setattr(build, "_fetch_row", fetch)
    harness.interrupt()
    completed = record(harness)["entries"]["SYN-first"]
    assert completed == {"completed": True, "reuse_unavailable": "receipt_unproven"}
