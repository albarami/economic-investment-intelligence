"""Archived register readers: invented JSON/CSV, precise refusals and lineage."""

import pytest
from custodian.tests.test_s2_t29_awards import STAMP

from eii_custodian.publicdata.fetch import awards
from eii_custodian.publicdata.fetch.award_checks import AwardError
from eii_custodian.publicdata.fetch.snapshots import publish_snapshot


def register(
    tmp_path,
    body=None,
    *,
    key="fc_register/SYN-part",
    format="csv_records",
    receipt_changes=None,
    **side_changes,
):
    if body is None:
        body = b"\xef\xbb\xbfsyn_reg,syn_name\nSYN-reg,SYN Company\n"
    source = key.split("/")[0]
    side = dict(
        source_id=source,
        key=key,
        publisher="SYN publisher",
        licence_basis="owner_decision",
        retrieved_utc=STAMP,
    )
    side.update(side_changes)
    side.update(receipt_changes or {})
    # A receipt change holding None removes the key entirely, so a plant can
    # publish a sidecar without it (an absent key is not a blank value).
    side = {name: value for name, value in side.items() if value is not None}
    snap = publish_snapshot(
        tmp_path / key, "csv" if format == "csv_records" else "json", body, side
    )
    selection = dict(
        key=key,
        identity=snap.sha256,
        format=format,
        registration_column="syn_reg",
        name_column="syn_name",
    )
    return snap, selection


def test_register_csv_bom_and_all_lineage(tmp_path):
    snap, selection = register(tmp_path)
    assert awards.read_registers(tmp_path, [selection]) == (
        [{"registration": "SYN-reg", "name": "SYN Company"}],
        [
            {
                "key": selection["key"],
                "identity": selection["identity"],
                "sha256": snap.sha256,
                "retrieved_utc": STAMP,
            }
        ],
    )


@pytest.mark.parametrize("value", ["", "pending"])
def test_register_pending_basis_is_read_as_written(tmp_path, value):
    """Ruling L-1001 (ruling L-1025 item a): a blank or pending basis in a
    stored receipt is a record, never a refusal; the snapshot is read and its
    basis kept as written."""
    snap, selection = register(tmp_path, receipt_changes={"licence_basis": value})
    assert awards.read_registers(tmp_path, [selection]) == (
        [{"registration": "SYN-reg", "name": "SYN Company"}],
        [
            {
                "key": selection["key"],
                "identity": selection["identity"],
                "sha256": snap.sha256,
                "retrieved_utc": STAMP,
            }
        ],
    )
    assert snap.sidecar["licence_basis"] == value


def test_register_receipt_without_the_basis_key_refuses(tmp_path):
    """Ruling L-1016 R3 (ruling L-1025 item a): the build itself writes every
    stored receipt, so a sidecar without the licence_basis key is a defect,
    never a terms reading, and refuses receipt_missing."""
    cache = tmp_path / "SYN-keyless-receipt"
    _, selection = register(cache, receipt_changes={"licence_basis": None})
    with pytest.raises(AwardError, match=r"^receipt_missing$"):
        awards.read_registers(cache, [selection])


@pytest.mark.parametrize(
    "plant",
    [
        "container",
        "selection",
        "fields",
        "type",
        "source",
        "traversal",
        "escape",
        "source_receipt",
        "key_receipt",
        "publisher",
        "format",
        "decode",
        "records",
        "record",
        "registration",
        "name",
    ],
)
def test_register_closed_refusals(tmp_path, plant):
    _, selection = register(tmp_path)
    selections = [selection]
    reason = "register_schema_missing"
    if plant == "container":
        selections = None
    elif plant == "selection":
        selections = [None]
    elif plant == "fields":
        selection["SYN extra"] = "SYN"
    elif plant == "type":
        selection["identity"] = 7
    elif plant == "source":
        selection["key"] = "SYN-other"
    elif plant == "traversal":
        selection["key"] = "fc_register/../fc_register/SYN-part"
    elif plant == "escape":
        # The link target is another directory inside this test's workspace.
        outside = tmp_path / "SYN-outside"
        outside.mkdir()
        link = tmp_path / "SYN-cache"
        link.mkdir()
        (link / "fc_register").symlink_to("../SYN-outside", target_is_directory=True)
        with pytest.raises(AwardError, match=r"^intake_path_refused$"):
            awards.read_registers(link, [selection])
        return
    elif plant in {"source_receipt", "key_receipt", "publisher"}:
        key, bad = {
            "source_receipt": ("source_id", "SYN-other"),
            "key_receipt": ("key", "SYN-other"),
            "publisher": ("publisher", ""),
        }[plant]
        # Publish a separate, integrity-valid archive with the malformed field.
        cache = tmp_path / "SYN-malformed-receipt"
        _, selection = register(cache, receipt_changes={key: bad})
        tmp_path = cache
        selections = [selection]
        reason = "receipt_missing"
    elif plant == "format":
        selection["format"] = "SYN unknown"
    else:
        body = {
            "decode": b"\xff",
            "records": b"{}",
            "record": b"[null]",
            "registration": b'[{"syn_reg":7,"syn_name":"SYN Company"}]',
            "name": b'[{"syn_reg":"SYN-reg","syn_name":7}]',
        }[plant]
        _, selection = register(
            tmp_path, body, key="biz_register/SYN-part", format="json_records"
        )
        selections = [selection]
    with pytest.raises(AwardError, match=f"^{reason}$"):
        awards.read_registers(tmp_path, selections)
