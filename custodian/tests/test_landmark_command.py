"""The actual build-public command reaches citation acquisition on invented I/O."""

from custodian.tests.test_landmark_snapshots import BODY, STAMP, URL, citation_setup

from commands import build_public
from eii_custodian.publicdata.fetch.receipts import sha256_hex
from eii_custodian.publicdata.fetch.snapshots import read_snapshot
from eii_custodian.publicdata.fetch.transport import Response


def test_real_command_reaches_citation_fetch_before_assembly(
    tmp_path, monkeypatch, capsys
):
    from custodian.tests.method_pin_config_fixture import stage_tracked_configuration

    stage_tracked_configuration(tmp_path)

    row, _ = citation_setup(monkeypatch)
    monkeypatch.setattr(build_public, "load_registry", lambda: (row,))
    monkeypatch.setattr(build_public, "utc_now", lambda: STAMP)

    def transport(url):
        assert url == URL
        return Response(url, BODY, ())

    result = build_public.run(
        tmp_path, {}, [], transport=transport, sleep=lambda _: None
    )
    output = capsys.readouterr()
    assert result == 1  # No reviewed frame selection is supplied by this fixture.
    assert "PASS " + row.key in output.out
    assert "FAIL assembly snapshot_selection_invalid" in output.out
    cache = tmp_path / "data/public_cache"
    raw = read_snapshot(cache / row.key / "inputs/input-0", sha256_hex(BODY))
    assert raw.body == BODY
    assert raw.sidecar["key"] == row.key
    assert raw.sidecar["retrieved_utc"] == STAMP
    assert raw.sidecar["commit_allowed"] is False
