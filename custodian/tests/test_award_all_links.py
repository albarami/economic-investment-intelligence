"""Invented all-link award checks; every transport is a local stub."""

import copy
import json
import random
from collections import Counter
from dataclasses import replace

import pytest
from custodian.tests.support.fetch_build import run_build
from custodian.tests.test_s2_t29_awards import STAMP, profile, row
from custodian.tests.test_s2_t29_fix import award_intake

from eii_custodian.publicdata.assembly import AssemblyError
from eii_custodian.publicdata.assembly_reports import awards_evidence
from eii_custodian.publicdata.fetch import awards
from eii_custodian.publicdata.fetch.award_checks import AwardError, check_awards
from eii_custodian.publicdata.fetch.award_links import (
    ProofFetchError,
    check_all_awards,
    sample_from_links,
    validate_links_receipt,
)
from eii_custodian.publicdata.fetch.receipts import sha256_hex
from eii_custodian.publicdata.fetch.snapshots import read_snapshot
from eii_custodian.publicdata.fetch.transport import ATTEMPT_LIMIT, TransportFault


def intake(tmp_path, monkeypatch, count=40):
    entry, declaration, proof = award_intake(tmp_path, monkeypatch)
    records = [row(index) for index in range(count)]
    # Duplicate rows/space-padded links are one link; a blank is no proof URL.
    records += [dict(row(), report_url=" " + row()["report_url"] + " ")]
    records += [dict(row(), report_url="")]
    declaration["reviewed_urls"] = [record["report_url"] for record in records[:count]]
    folder = tmp_path / "intake" / entry.key
    body = (
        ",".join(profile()["columns"])
        + "\n"
        + "\n".join(
            ",".join(record[key] for key in profile()["columns"]) for record in records
        )
        + "\n"
    ).encode()
    (folder / "syn.csv").write_bytes(body)
    manifest = json.loads((folder / "intake.json").read_text())
    manifest["sha256"] = sha256_hex(body)
    (folder / "intake.json").write_text(json.dumps(manifest))
    return entry, declaration, proof


def built(tmp_path, entry, send):
    outcome = run_build((entry,), send, tmp_path, lambda: STAMP, lambda _: None)
    assert outcome.failure is None
    indices = list((tmp_path / entry.key / "index").glob("*.json"))
    assert len(indices) == 1
    return read_snapshot(tmp_path / entry.key, indices[0].stem)


def test_awards_build_checks_all_links_once_and_labels_the_sample(
    tmp_path, monkeypatch
):
    entry, declaration, proof = intake(tmp_path, monkeypatch)
    calls = []

    def send(url):
        calls.append(url)
        return proof(url)

    snapshot = built(tmp_path, entry, send)
    urls = sorted(declaration["reviewed_urls"])
    assert Counter(calls) == Counter(dict.fromkeys(urls, 1))
    assert calls == urls
    all_links = snapshot.sidecar["award_links"]
    assert all_links == {
        "method": "awards.report_links@v1",
        "scope": "all_links",
        "report_urls": urls,
        "distinct_frame_count": 40,
        "checked_count": 40,
        "matched": 40,
        "mismatched": 0,
        "failed_fetches": 0,
        "match_rate": "1",
        "incomplete": False,
        "status": "all_links_recorded",
        "results": [
            {"report_url": url, "result": "matched", "reason": "matched"}
            for url in urls
        ],
    }
    evidence = awards_evidence(snapshot.sidecar, 73)
    assert evidence["award_links"] == {
        key: value
        for key, value in all_links.items()
        if key not in {"results", "report_urls"}
    }
    assert evidence["award_check_scope"] == "sample"
    sample = evidence["award_check"]
    assert sample["selected_count"] == 30
    assert sample["status"] == "sample_recorded"
    assert "results" not in sample
    assert "SYN Company" not in str(evidence)


@pytest.mark.parametrize(
    "kind,reason", [("unreachable", "unreachable"), ("http", "http_status")]
)
def test_awards_failure_outside_sample_is_counted_once_with_reason(
    tmp_path, monkeypatch, kind, reason
):
    entry, declaration, proof = intake(tmp_path, monkeypatch)
    urls = sorted(declaration["reviewed_urls"])
    sampled = random.Random(73).sample(urls, 30)
    failed = next(url for url in urls if url not in sampled)
    calls = []

    def send(url):
        calls.append(url)
        if url == failed:
            raise TransportFault(kind, url, 503)
        return proof(url)

    snapshot = built(tmp_path, entry, send)
    expected_calls = Counter(dict.fromkeys(urls, 1))
    expected_calls[failed] = ATTEMPT_LIMIT
    assert Counter(calls) == expected_calls
    check = snapshot.sidecar["award_links"]
    assert (check["checked_count"], check["matched"], check["failed_fetches"]) == (
        40,
        39,
        1,
    )
    assert check["match_rate"] == "0.975"
    assert check["incomplete"] is True
    assert {"report_url": failed, "result": "fetch_failed", "reason": reason} in check[
        "results"
    ]
    assert snapshot.sidecar["award_check"]["match_rate"] == "1"
    # A green sample cannot substitute for a failed full-frame check.
    with pytest.raises(AssemblyError, match=r"^assembly_t29_refused$"):
        awards_evidence(snapshot.sidecar, 73)


def test_awards_transient_failure_recovers_before_recording_outcome(
    tmp_path, monkeypatch
):
    entry, declaration, proof = intake(tmp_path, monkeypatch)
    urls = sorted(declaration["reviewed_urls"])
    calls = Counter()

    def send(url):
        calls[url] += 1
        if url == urls[0] and calls[url] == 1:
            raise TransportFault("unreachable", url)
        return proof(url)

    snapshot = built(tmp_path, entry, send)
    expected = Counter(dict.fromkeys(urls, 1))
    expected[urls[0]] = 2
    assert calls == expected
    check = snapshot.sidecar["award_links"]
    assert check["checked_count"] == check["matched"] == 40
    assert check["failed_fetches"] == 0
    assert check["incomplete"] is False
    assert awards_evidence(snapshot.sidecar, 73)["award_links"]["match_rate"] == "1"


@pytest.mark.parametrize("location", ["hops", "final_url"])
def test_awards_refuses_unlisted_response_url_even_in_reviewed_scope(
    tmp_path, monkeypatch, location
):
    entry, declaration, proof = intake(tmp_path, monkeypatch)
    unlisted = "https://example.invalid/syn-proof"
    declaration["reviewed_urls"].append(unlisted)
    calls = []

    def send(url):
        calls.append(url)
        response = proof(url)
        return replace(
            response, **{location: (unlisted,) if location == "hops" else unlisted}
        )

    outcome = run_build((entry,), send, tmp_path, lambda: STAMP, lambda _: None)
    assert outcome.failure is not None
    assert outcome.failure.check == "blocked_host"
    assert len(calls) == 1
    assert not (tmp_path / entry.key).exists()


def test_awards_mismatch_outside_sample_changes_full_match_rate(tmp_path, monkeypatch):
    entry, declaration, proof = intake(tmp_path, monkeypatch)
    urls = sorted(declaration["reviewed_urls"])
    sampled = random.Random(73).sample(urls, 30)
    mismatched = next(url for url in urls if url not in sampled)

    def send(url):
        response = proof(url)
        if url == mismatched:
            from dataclasses import replace

            return replace(response, body=response.body.replace(b">12.50<", b">13.50<"))
        return response

    snapshot = built(tmp_path, entry, send)
    check = snapshot.sidecar["award_links"]
    evidence = awards_evidence(snapshot.sidecar, 73)["award_links"]
    assert (check["checked_count"], check["matched"], check["mismatched"]) == (
        40,
        39,
        1,
    )
    assert check["match_rate"] == "0.975"
    assert evidence["match_rate"] == check["match_rate"]
    assert {
        "report_url": mismatched,
        "result": "mismatched",
        "reason": "proof_mismatch",
    } in check["results"]
    assert snapshot.sidecar["award_check"]["match_rate"] == "1"


def test_awards_final_audit_excludes_report_urls_and_retains_receipt_details(
    tmp_path, monkeypatch
):
    from custodian.tests.test_production_adapters import context

    from eii_custodian.publicdata.fetch.registry import load_registry

    entry, _, proof = intake(tmp_path, monkeypatch)
    snapshot = built(tmp_path, entry, proof)
    entries = tuple(
        entry if item.key == entry.key else item for item in load_registry()
    )
    state = context(tmp_path, entries)
    state.seed = 73
    state.receipts[entry.key] = snapshot.sidecar
    outputs = state.final_audit()
    assert "assembly/final_audit.json" in outputs
    audit = json.loads((tmp_path / "assembly/final_audit.json").read_text())
    award = next(item for item in audit["t29"] if item["key"] == entry.key)
    assert award["sha256"] == snapshot.sha256
    assert '"report_url' not in json.dumps(audit)
    assert "results" not in award["award_links"]
    assert award["award_links"] == {
        key: value
        for key, value in snapshot.sidecar["award_links"].items()
        if key not in {"results", "report_urls"}
    }
    receipt = read_snapshot(tmp_path / entry.key, snapshot.sha256).sidecar
    assert len(receipt["award_links"]["report_urls"]) == 40
    assert receipt["award_links"]["results"] == [
        {"report_url": url, "result": "matched", "reason": "matched"}
        for url in receipt["award_links"]["report_urls"]
    ]
    assert award["award_links"]["checked_count"] == 40
    assert award["award_links"]["match_rate"] == "1"
    assert award["award_check_scope"] == "sample"
    assert award["award_check"]["selected_count"] == 30


@pytest.mark.parametrize(
    "plant",
    [
        "missing",
        "skip",
        "duplicate",
        "wrong_url",
        "wrong_result",
        "wrong_reason",
        "rate",
        "count",
        "boolean",
        "scope",
        "sample",
        "method",
        "status",
        "incomplete",
        "extra",
        "results_type",
        "frame_order",
        "frame_count",
        "negative",
        "sample_scope",
    ],
)
def test_awards_gate_refuses_incomplete_or_inconsistent_all_link_receipt(
    tmp_path, monkeypatch, plant
):
    entry, _, proof = intake(tmp_path, monkeypatch)
    receipt = copy.deepcopy(built(tmp_path, entry, proof).sidecar)
    check = receipt["award_links"]
    if plant == "missing":
        receipt.pop("award_links")
    elif plant == "skip":
        check["results"].pop()
        check["checked_count"] -= 1
        check["matched"] -= 1
    elif plant == "duplicate":
        check["results"][-1] = dict(check["results"][0])
    elif plant == "wrong_url":
        check["results"][-1]["report_url"] = row(99)["report_url"]
    elif plant == "wrong_result":
        check["results"][-1]["result"] = "SYN-invalid"
    elif plant == "wrong_reason":
        check["results"][-1]["reason"] = "SYN-private-diagnostic"
    elif plant == "rate":
        check["match_rate"] = "0.5"
    elif plant == "count":
        check["failed_fetches"] = 1
    elif plant == "boolean":
        check["checked_count"] = True
    elif plant == "scope":
        check["scope"] = "sample"
    elif plant == "sample":
        receipt["award_check"]["results"][0]["result"] = "mismatched"
    else:
        target = receipt if plant == "sample_scope" else check
        key, value = {
            "method": ("method", "SYN-wrong"),
            "status": ("status", "sample_recorded"),
            "incomplete": ("incomplete", True),
            "extra": ("SYN-extra", None),
            "results_type": ("results", tuple(check["results"])),
            "frame_order": ("report_urls", list(reversed(check["report_urls"]))),
            "frame_count": ("distinct_frame_count", 39),
            "negative": ("checked_count", -1),
            "sample_scope": ("award_check_scope", "all_links"),
        }[plant]
        target[key] = value
    with pytest.raises(AssemblyError, match=r"^assembly_t29_refused$"):
        awards_evidence(receipt, 73)


def test_awards_publication_refuses_a_planted_skipped_link(tmp_path, monkeypatch):
    entry, _, proof = intake(tmp_path, monkeypatch)
    original = awards.check_all_awards

    def skipped(rows, schema, reader):
        # Skip a unique link while preserving the duplicate and blank tail.
        return original(rows[1:-2], schema, reader)

    monkeypatch.setattr(awards, "check_all_awards", skipped)
    outcome = run_build((entry,), proof, tmp_path, lambda: STAMP, lambda _: None)
    assert outcome.failure is not None
    assert outcome.failure.check == "award_links_metadata_missing"
    assert not (tmp_path / entry.key).exists()


def test_awards_publication_rejects_invalid_seed_before_any_proof_read(
    tmp_path, monkeypatch
):
    entry, declaration, _ = intake(tmp_path, monkeypatch)
    batch, _, _ = awards.read_intake(tmp_path, declaration, STAMP)
    calls = []

    def reader(url):
        calls.append(url)
        return row()

    with pytest.raises(AwardError, match=r"^award_seed_pending$"):
        awards._publish_awards(
            entry, tmp_path, batch, profile(), STAMP, "73", reader, [], []
        )
    assert calls == []


@pytest.mark.parametrize("count", [0, 1, 29, 30, 31, 40])
def test_awards_derived_sample_equals_the_original_seeded_sample(count):
    records = [row(index) for index in range(count)]

    def proof(url):
        index = int(url.rsplit("/", 1)[1])
        if index % 4 == 0:
            raise OSError("SYN-private-upstream-message")
        return dict(row(index), syn_value="13.50" if index % 4 == 1 else "12.50")

    full = check_all_awards(records, profile(), proof)
    sample = sample_from_links(full, 73)
    assert sample == check_awards(records, profile(), 73, proof)
    validate_links_receipt(
        {
            "source_id": "awards_owner_scrape",
            "award_check_scope": "sample",
            "award_check": sample,
            "award_links": full,
        },
        records,
    )
    assert full["checked_count"] == count
    assert "SYN-private-upstream-message" not in str(full)
    if count == 0:
        assert full["match_rate"] is None
        assert full["incomplete"] is True


@pytest.mark.parametrize("both_winners", [False, True])
def test_awards_all_link_check_requires_every_winner_on_a_shared_link(both_winners):
    first = row()
    second = dict(first, syn_company="SYN Other", syn_reg="SYN-other", syn_value="7")
    calls = []

    def proof(url):
        calls.append(url)
        return [second, first] if both_winners else [first]

    check = check_all_awards([first, second, first], profile(), proof)
    assert calls == [first["report_url"]]
    assert check["matched"] == int(both_winners)
    assert check["mismatched"] == int(not both_winners)


@pytest.mark.parametrize(
    "reason",
    [
        "unreachable",
        "http_status",
        "proof_fetch_failed",
        "body_bytes",
        "SYN-private-error",
    ],
)
def test_awards_all_link_failure_uses_closed_reasons_only(reason):
    calls = []

    def proof(url):
        calls.append(url)
        raise ProofFetchError(reason)

    check = check_all_awards([row()], profile(), proof)
    assert calls == [row()["report_url"]]
    assert check["checked_count"] == check["failed_fetches"] == 1
    assert check["match_rate"] == "0"
    expected = "proof_fetch_failed" if reason == "SYN-private-error" else reason
    assert check["results"] == [
        {
            "report_url": row()["report_url"],
            "result": "fetch_failed",
            "reason": expected,
        }
    ]
    assert "SYN-private-error" not in str(check)


@pytest.mark.parametrize("error", ["pin", "snapshot", "host", "schema"])
def test_awards_all_link_check_never_converts_hard_refusals_to_fetch_failures(error):
    from eii_custodian.publicdata.fetch.certificate_pins import PinError
    from eii_custodian.publicdata.fetch.snapshots import SnapshotError

    failure = {
        "pin": PinError("certificate_chain_incomplete"),
        "snapshot": SnapshotError("snapshot_hash_mismatch"),
        "host": AwardError("blocked_host"),
        "schema": AwardError("schema_missing"),
    }[error]

    def proof(_):
        raise failure

    with pytest.raises(type(failure), match=f"^{failure}$"):
        check_all_awards([row()], profile(), proof)


def test_awards_all_link_frame_rejects_an_off_host_link_before_any_fetch():
    calls = []
    with pytest.raises(AwardError, match=r"^blocked_host$"):
        check_all_awards(
            [row(), dict(row(1), report_url="https://example.invalid/syn-proof")],
            profile(),
            calls.append,
        )
    assert calls == []
