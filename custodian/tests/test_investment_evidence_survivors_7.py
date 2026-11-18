"""Direct diagnostic checks for identity metadata absent from a verified receipt."""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock

import pytest
from custodian.tests.test_investment_evidence_survivors import (
    DASHBOARD_URL,
    PROJECT,
    SOURCE,
    URL,
    candidate,
    failure,
    project,
)

import eii_custodian.publicdata.investment_evidence as evidence
from eii_custodian.publicdata.fetch.snapshots import SnapshotError, read_snapshot
from eii_custodian.publicdata.investment_contracts import ProjectEvidence


def test_missing_receipt_source_has_an_empty_diagnostic_source(tmp_path: Path):
    item = project(tmp_path)
    # Build an internally consistent invented archive with no source binding.
    # read_snapshot checks the index against the receipt; the evidence audit
    # must still reject the missing source before any record can be evidence.
    receipt = dict(item.snapshot.sidecar)
    del receipt["source_id"]
    body = (json.dumps(receipt, sort_keys=True) + "\n").encode()
    item.snapshot.receipt_path.write_bytes(body)
    directory = item.snapshot.receipt_path.parent.parent
    index_path = directory / "index" / f"{item.identity}.json"
    index = json.loads(index_path.read_bytes())
    del index["source_id"]
    index["receipt_sha256"] = hashlib.sha256(body).hexdigest()
    index_path.write_text(json.dumps(index, sort_keys=True) + "\n", encoding="utf-8")
    selected = read_snapshot(directory, item.identity)
    result = evidence._audit_archives((replace(item, snapshot=selected),), (), ())
    assert result == failure(
        "",
        "",
        "evidence_audit_incomplete",
        "every registration, revision and absence",
        "archive metadata differs",
    )


def test_revision_uses_verified_metadata_after_validation(tmp_path: Path):
    class DisplaySubstitution(str):
        def __str__(self) -> str:
            return "SYN-SUBSTITUTED"

    item = project(tmp_path)
    supplied = replace(
        item,
        snapshot=replace(
            item.snapshot,
            sidecar={
                **item.snapshot.sidecar,
                "retrieved_utc": DisplaySubstitution("2026-11-14T08:00:00Z"),
            },
        ),
    )
    result = evidence.build_project_evidence((supplied,))
    assert isinstance(result, ProjectEvidence)
    assert result.revisions[0].retrieved_utc == "2026-11-14T08:00:00Z"


@pytest.mark.parametrize(
    ("index_missing", "refusal"),
    [(True, "snapshot_date_missing"), (False, "snapshot_index_invalid")],
)
def test_project_archive_requires_retrieval_time_before_building_revisions(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    index_missing: bool,
    refusal: str,
) -> None:
    item = project(tmp_path)
    receipt = dict(item.snapshot.sidecar)
    del receipt["retrieved_utc"]
    body = (json.dumps(receipt, sort_keys=True) + "\n").encode("utf-8")
    item.snapshot.receipt_path.write_bytes(body)
    directory = item.snapshot.receipt_path.parent.parent
    index_path = directory / "index" / f"{item.identity}.json"
    index = json.loads(index_path.read_bytes())
    if index_missing:
        del index["retrieved_utc"]
    # Keep the checksum valid so the receipt-only case reaches timestamp parity.
    index["receipt_sha256"] = hashlib.sha256(body).hexdigest()
    index_path.write_text(json.dumps(index, sort_keys=True) + "\n", encoding="utf-8")
    supplied = replace(item, snapshot=replace(item.snapshot, sidecar=receipt))
    revision_builder = Mock(wraps=evidence.ProjectRevision)
    monkeypatch.setattr(evidence, "ProjectRevision", revision_builder)

    with pytest.raises(SnapshotError, match=f"^{refusal}$"):
        evidence.build_project_evidence((supplied,))
    revision_builder.assert_not_called()


@pytest.mark.parametrize("metadata", ["valid", "absent", "wrong_type"])
def test_failure_diagnostics_preserve_complete_typed_metadata(
    tmp_path: Path, metadata: str
):
    item = project(tmp_path)
    row = candidate(tmp_path)
    if metadata == "valid":
        side = {"source_id": PROJECT, "fetch_url": DASHBOARD_URL}
        chain = {"page_url": URL}
        project_failure = failure(
            PROJECT, DASHBOARD_URL, "SYN-CHECK", "SYN-EXPECTED", "SYN-OBSERVED"
        )
        candidate_failure = failure(
            SOURCE, URL, "SYN-CHECK", "SYN-EXPECTED", "SYN-OBSERVED"
        )
        snapshot_failure = failure(
            PROJECT,
            DASHBOARD_URL,
            "invalid_evidence_metadata",
            "SYN-EXPECTED",
            "SYN-OBSERVED",
        )
    else:
        side = {} if metadata == "absent" else {"source_id": 3, "fetch_url": 4}
        chain = {} if metadata == "absent" else {"page_url": 3}
        project_failure = failure("", "", "SYN-CHECK", "SYN-EXPECTED", "SYN-OBSERVED")
        candidate_failure = failure(
            SOURCE, "", "SYN-CHECK", "SYN-EXPECTED", "SYN-OBSERVED"
        )
        snapshot_failure = failure(
            "", "", "invalid_evidence_metadata", "SYN-EXPECTED", "SYN-OBSERVED"
        )
    planted = replace(item, snapshot=replace(item.snapshot, sidecar=side))
    assert (
        evidence._refusal(planted, "SYN-CHECK", "SYN-EXPECTED", "SYN-OBSERVED")
        == project_failure
    )
    assert (
        evidence._snapshot_failure(planted.snapshot, "SYN-EXPECTED", "SYN-OBSERVED")
        == snapshot_failure
    )
    assert (
        evidence._candidate_failure(
            replace(row, source_chain=chain),
            "SYN-CHECK",
            "SYN-EXPECTED",
            "SYN-OBSERVED",
        )
        == candidate_failure
    )
