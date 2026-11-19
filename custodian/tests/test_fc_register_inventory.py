"""Complete-name composition, pinned lineage and source-only collision plant."""

import json
from dataclasses import replace

import pytest

# Explicit fixture re-export for the same invented pin boundary.
from custodian.tests.test_fc_register import (
    invented_pin_context as invented_pin_context,
)
from custodian.tests.test_fc_register import live, page, review, row

from eii_custodian.publicdata.fc_register.build import build_inventory
from eii_custodian.publicdata.fc_register.names import contribution
from eii_custodian.publicdata.fetch.page_records import PageError
from eii_custodian.publicdata.fetch.snapshots import SnapshotError
from eii_custodian.publicdata.fetch.terms_text import terms_text_sha256
from eii_custodian.publicdata.name_inventory import Contribution, check_inventory


def selected(tmp_path):
    result, _ = live(
        tmp_path, [page(1), page(2, True).replace(b"SYN-QFC-2", b"SYN-QFC-1")]
    )
    (tmp_path / "snapshot_pins.json").write_text(
        json.dumps({"fc_register": result.sha256})
    )
    return result


def test_inventory_with_terms_keeps_only_company_page_inputs(
    tmp_path, invented_pin_context
):
    terms_url = "https://www.qfc.qa/SYN-terms"
    terms = b"<p>SYN terms record</p>"
    ent = replace(row(), terms_url=terms_url)
    dec = review()
    dec["reviewed_urls"].append(terms_url)
    result, sent = live(tmp_path, [page(1), page(2, True), terms], ent, dec)
    (tmp_path / "snapshot_pins.json").write_text(
        json.dumps({"fc_register": result.sha256})
    )

    fc = contribution(tmp_path, ent)
    assert fc.names == (
        "SYN Glass Orchard 1",
        "SYN بستان زجاج 1",
        "SYN Glass Orchard 2",
        "SYN بستان زجاج 2",
    )
    assert [str(request) for request in sent] == [ent.url, ent.url, terms_url]
    assert len(fc.lineage["inputs"]) == 2
    assert all(
        item["representation"] == "fc_company_pane@v1" for item in fc.lineage["inputs"]
    )
    assert result.sidecar["terms_sha256"] == terms_text_sha256(terms)


def test_complete_inventory_retains_hidden_duplicate_names_and_caller_refuses(
    tmp_path, invented_pin_context
):
    selected(tmp_path)
    fc = contribution(tmp_path, row())
    other = Contribution(
        "SYN-other", ("SYN Copper Meadow",), {"method": "SYN-invented"}
    )
    label = "SYN Glass Orchard 2"
    assert check_inventory([label], [other], 1).ok
    assert not check_inventory([label], [other, fc], 1).ok
    # A display deduplicating by QFC number would hide the second name;
    # the inventory receives both raw names before that display could filter.
    assert fc.names == (
        "SYN Glass Orchard 1",
        "SYN بستان زجاج 1",
        "SYN Glass Orchard 2",
        "SYN بستان زجاج 2",
    )
    assert not check_inventory([label], [other, fc, fc], 1).ok
    with pytest.raises(ValueError, match="name_collision"):
        build_inventory(tmp_path, row(), [label], [other], 1)
    assert build_inventory(tmp_path, row(), ["SYN Violet Estuary"], [other], 1).ok
    assert fc.lineage["snapshot_identity"] and fc.lineage["retrieved_utc"]


@pytest.mark.parametrize(
    "plant",
    [
        "missing_pin",
        "wrong_pin",
        "tampered_input",
        "missing_publisher",
        "missing_receipt",
        "malformed_metadata",
    ],
)
def test_inventory_lineage_refusals(tmp_path, invented_pin_context, plant):
    result = selected(tmp_path)
    if plant == "missing_pin":
        (tmp_path / "snapshot_pins.json").unlink()
    elif plant == "wrong_pin":
        (tmp_path / "snapshot_pins.json").write_text(
            json.dumps({"fc_register": "a" * 64})
        )
    elif plant == "tampered_input":
        item = json.loads(result.body)["inputs"][0]
        for path in (tmp_path / "fc_register" / item["key"]).rglob("*.json"):
            if path.name == item["sha256"] + ".json":
                path.write_bytes(b"SYN-tampered")
    elif plant == "malformed_metadata":
        result.receipt_path.write_bytes(b"[]")
    else:
        side = json.loads(result.receipt_path.read_bytes())
        del side["publisher" if plant == "missing_publisher" else "licence_basis"]
        result.receipt_path.write_text(json.dumps(side))
    with pytest.raises(
        (PageError, SnapshotError, ValueError), match=r"snapshot_|receipt_missing"
    ):
        contribution(tmp_path, row())


def test_committed_fetched_byte_refused():
    from eii_custodian.publicdata.completeness import committed_derived_check

    # The scan refuses any committed derived content claiming this source,
    # independently of its size (even a single invented source byte).
    from eii_custodian.publicdata.fetch.registry import load_registry

    rows = load_registry()
    value = committed_derived_check(
        {"SYN-derived.json": {"source_id": "fc_register", "value": "x"}}, rows
    )
    assert value == [
        {
            "id": "SYN-derived.json",
            "state": "failed",
            "reason": "committed_source_value",
        }
    ]


def test_missing_basis_does_not_accept_an_unknown_decision_record(tmp_path):
    from custodian.tests.test_publicdata_registry import _mutated, _row

    from eii_custodian.publicdata.fetch.registry import RegistryError, load_registry

    def corrupt(document):
        target = _row(document, "fc_register")
        del target["licence_basis"]
        target["decision_record"] = "SYN-unknown"

    with pytest.raises(
        RegistryError, match="decision_record set without owner_decision"
    ):
        load_registry(_mutated(tmp_path, "SYN-wrong-record.yaml", corrupt))


def test_fc_snapshot_identity_cannot_be_overwritten(tmp_path, invented_pin_context):
    from eii_custodian.publicdata.fetch.receipts import sha256_hex
    from eii_custodian.publicdata.fetch.snapshots import publish_snapshot

    original = selected(tmp_path)
    body = b'{"SYN":"different"}'
    side = {**original.sidecar, "sha256": sha256_hex(body), "bytes": len(body)}
    with pytest.raises(SnapshotError, match="snapshot_conflict"):
        publish_snapshot(
            tmp_path / "fc_register", "json", body, side, identity=original.sha256
        )
    assert contribution(tmp_path, row()).lineage["snapshot_identity"] == original.sha256
