"""Archived register readers: invented JSON/CSV, precise refusals and lineage."""

from dataclasses import replace

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
        "basis",
        "format",
        "decode",
        "records",
        "record",
        "registration",
        "name",
    ],
)
def test_register_closed_refusals(tmp_path, monkeypatch, plant):
    snap, selection = register(tmp_path)
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
    elif plant in {"source_receipt", "key_receipt", "publisher", "basis"}:
        key, bad = {
            "source_receipt": ("source_id", "SYN-other"),
            "key_receipt": ("key", "SYN-other"),
            "publisher": ("publisher", ""),
            "basis": ("licence_basis", ""),
        }[plant]
        # read_snapshot is already independently tested for integrity; isolate
        # the awards adapter's additional mandatory receipt fields.
        side = dict(snap.sidecar, **{key: bad})
        monkeypatch.setattr(
            awards, "read_snapshot", lambda *args: replace(snap, sidecar=side)
        )
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
