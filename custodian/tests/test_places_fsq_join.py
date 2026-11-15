"""Join regressions on invented inputs; no network or downloaded data."""

from dataclasses import replace

import pytest
from custodian.tests.test_places_fsq import _release_entry
from custodian.tests.test_publicdata_behaviour import _clock, _entry, _ok, _sleep

from eii_custodian.publicdata.fetch import build
from eii_custodian.publicdata.places_fsq.assemble import _table_row
from eii_custodian.publicdata.places_fsq.errors import PlacesFsqError
from eii_custodian.publicdata.places_fsq.parse import parse_file


def test_skipped_fsq_preserves_other_build_stages(tmp_path, monkeypatch):
    """A skipped copy adds only its skip line, preserving stage calls and output."""
    events = []
    original_publish = build.publish_investment
    original_stage = build.run_stage

    def publish(*args, **kwargs):
        events.append("investment")
        return original_publish(*args, **kwargs)

    def stage(*args, **kwargs):
        events.append("series" if "build_entries" in kwargs else "regression")
        return original_stage(*args, **kwargs)

    def transport(url):
        return _ok(url, b"invented-bytes")

    monkeypatch.setattr(build, "publish_investment", publish)
    monkeypatch.setattr(build, "run_stage", stage)
    baseline = build.run_build(
        (_entry(),), transport, tmp_path / "baseline", _clock, _sleep
    )
    assert baseline.failure is None
    assert events == ["investment", "series", "regression"]
    events.clear()
    skipped = replace(_release_entry(), skip_reason="SYN-disabled")
    joined = build.run_build(
        (skipped, _entry()), transport, tmp_path / "joined", _clock, _sleep
    )
    assert joined.failure is None
    assert joined.lines[0] == "SKIP places_fsq/copy-2025-01-10 SYN-disabled"
    assert joined.lines[1:] == baseline.lines
    assert events == ["investment", "series", "regression"]


def test_missing_base_cell_still_refuses(tmp_path):
    """The frame's nullable lookup must not relax this table's cell refusal."""
    from custodian.tests.fixtures.places_fsq.invented import place, write_places

    path = tmp_path / "places.parquet"
    write_places(path, [place()])
    with pytest.raises(PlacesFsqError, match=r"^cell$"):
        _table_row(parse_file(path)[0], [], "2025-01-10")
