"""Offline archive-revision and intermediate-pin boundaries for assembly adapters."""

import hashlib
import json
import ssl

import pytest
from custodian.tests.fixtures.invented_chain import invented_pems
from custodian.tests.investment_fixtures import invented_record
from custodian.tests.test_investment_evidence import _archive_dashboard

from eii_custodian.publicdata.fetch.certificate_pins import (
    PinError,
    load_pin,
    verified_context,
)
from eii_custodian.publicdata.fetch.snapshots import SnapshotError, read_snapshot
from eii_custodian.publicdata.investment_contracts import ProjectArchiveSelection
from eii_custodian.publicdata.investment_evidence import build_cache_evidence


def projection(cache, *identities):
    return build_cache_evidence(
        cache,
        projects=tuple(
            ProjectArchiveSelection("fdi_projects", identity, {})
            for identity in identities
        ),
        milestones=(),
        expected=(),
        attempts=(),
    )


def test_revision_boundary_uses_all_explicit_archives_and_never_newest(tmp_path):
    old = _archive_dashboard(
        tmp_path, "2024-01-01", (invented_record(project_id=1001, capex=("n", "12.5")),)
    )
    new = _archive_dashboard(
        tmp_path, "2024-02-01", (invented_record(project_id=1001, capex=("n", "14.5")),)
    )
    older_only = projection(tmp_path, old)
    assert [row.announced["capex"] for row in older_only.evidence.revisions] == ["12.5"]
    both = projection(tmp_path, old, new)
    assert [row.snapshot_identity for row in both.evidence.revisions] == [old, new]
    assert [row.announced["capex"] for row in both.evidence.revisions] == [
        "12.5",
        "14.5",
    ]
    overwritten = projection(tmp_path, old, old)
    assert overwritten.check == "revision_overwrite"


@pytest.mark.parametrize("target", ["body", "receipt"])
def test_revision_boundary_refuses_hash_substitution(tmp_path, target):
    identity = _archive_dashboard(
        tmp_path, "2024-01-01", (invented_record(project_id=1001),)
    )
    snapshot = read_snapshot(tmp_path / "fdi_projects", identity)
    if target == "body":
        snapshot.path.write_bytes(b"{}")
    else:
        side = dict(snapshot.sidecar, publisher="SYN-substituted-publisher")
        snapshot.receipt_path.write_text(json.dumps(side))
    with pytest.raises(SnapshotError, match=r"^snapshot_hash_mismatch$"):
        projection(tmp_path, identity)


def pin_config(tmp_path, part="intermediate"):
    der = ssl.PEM_cert_to_DER_cert(invented_pems()[part].decode("ascii"))
    folder = tmp_path / "intake" / "syn_source"
    folder.mkdir(parents=True)
    (folder / "syn.der").write_bytes(der)
    return dict(
        host="www.qcb.gov.qa",
        sha256=hashlib.sha256(der).hexdigest(),
        file="syn.der",
        security_review="APPROVED",
    )


def test_pin_boundary_reuses_inspected_bytes_and_verifying_context(tmp_path):
    config = pin_config(tmp_path)
    pin = load_pin(tmp_path, "syn_source", config)
    context = verified_context(config["host"], pin)
    assert context.verify_mode == ssl.CERT_REQUIRED
    assert context.check_hostname
    assert not context.verify_flags & ssl.VERIFY_X509_PARTIAL_CHAIN


@pytest.mark.parametrize(
    "defect,reason",
    [
        ("hash", "certificate_chain_incomplete"),
        ("review", "certificate_review_pending"),
        ("host", "certificate_host_mismatch"),
        ("root", "certificate_chain_incomplete"),
        ("missing", "certificate_chain_incomplete"),
    ],
)
def test_pin_boundary_refuses_unreviewed_or_substituted_chain(tmp_path, defect, reason):
    config = pin_config(tmp_path, "root" if defect == "root" else "intermediate")
    if defect == "hash":
        config["sha256"] = "a" * 64
    elif defect == "review":
        config["security_review"] = "pending"
    elif defect == "host":
        config["host"] = "syn.example"
    elif defect == "missing":
        (tmp_path / "intake/syn_source/syn.der").unlink()
    with pytest.raises(PinError, match=r"^" + reason + "$"):
        load_pin(tmp_path, "syn_source", config)


def test_pin_for_one_host_never_authorises_a_second_host(tmp_path):
    config = pin_config(tmp_path)
    pin = load_pin(tmp_path, "syn_source", config)
    with pytest.raises(PinError, match=r"^certificate_host_mismatch$"):
        verified_context("www.edu.gov.qa", pin)
