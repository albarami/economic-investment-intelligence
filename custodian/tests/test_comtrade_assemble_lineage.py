"""Comtrade assembly refuses receipts without a known data API class."""

import json
from pathlib import Path

import pytest
from custodian.tests.fixtures.comtrade.invented import (
    body_for,
    invented_entry,
    invented_policy,
    trusted_source,
)

from eii_custodian.publicdata.comtrade.assemble import assemble
from eii_custodian.publicdata.comtrade.fetch import fetch_source
from eii_custodian.publicdata.comtrade.policy import SafeRefusal
from eii_custodian.publicdata.fetch.receipts import sha256_hex
from eii_custodian.publicdata.fetch.transport import AttemptResult, SlotSecrets


@pytest.mark.parametrize(
    "api_class",
    ["invented-unknown-class", 7],
    ids=["unknown-class", "non-string-class"],
)
def test_assembly_refuses_an_unknown_api_class_without_a_host(
    tmp_path: Path, api_class: object
) -> None:
    """A resealed manifest cannot supply an empty host without a known class."""
    policy = invented_policy(
        frequencies=["annual"], periods=["2099"], flows=["flow-in"]
    )
    fetched = fetch_source(
        invented_entry(policy),
        tmp_path,
        lambda: "2026-11-16T08:00:00Z",
        lambda _seconds: None,
        lambda request: AttemptResult("ok", body_for(request)),
        SlotSecrets("invented-primary", ""),
    )
    assert fetched.failure is None
    control = assemble(
        tmp_path,
        "un_comtrade",
        policy,
        manifest_sha256=fetched.digest,
        **trusted_source(policy),
    )
    assert control.fetch_host == "invented.example"
    assert len(control.rows) == 4

    folder = tmp_path / "un_comtrade"
    manifest = json.loads((folder / "manifest.json").read_bytes())
    for child in manifest["children"]:
        old = child["receipt_sha256"]
        receipt = json.loads((folder / f"{old}.meta.json").read_bytes())
        receipt["api_class"] = api_class
        receipt["fetch_host"] = ""
        raw = json.dumps(receipt).encode()
        new = sha256_hex(raw)
        (folder / f"{new}.meta.json").write_bytes(raw)
        (folder / f"{new}.json").write_bytes((folder / f"{old}.json").read_bytes())
        child["receipt_sha256"] = new
    raw = json.dumps(manifest).encode()
    digest = sha256_hex(raw)
    (folder / "manifests" / f"{digest}.json").write_bytes(raw)

    with pytest.raises(SafeRefusal) as caught:
        assemble(
            tmp_path,
            "un_comtrade",
            policy,
            manifest_sha256=digest,
            **trusted_source(policy),
        )
    assert caught.value.check == "lineage_missing"
