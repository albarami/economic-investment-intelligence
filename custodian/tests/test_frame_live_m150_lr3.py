"""LR3: the first report filter of the live frame matches its lowercase marker only (m150)."""

from dataclasses import replace

from custodian.tests.test_frame_census import entry
from custodian.tests.test_frame_live_survivors import _world

from eii_custodian.publicdata.frame.build import build_frame


def test_uppercase_marker_text_stays_in_the_report(tmp_path):
    prepared = _world(tmp_path)
    skipped = replace(entry("util_water"), skip_reason="SYN UNLISTED ZONE NUMBERS")
    registry = tuple(e for e in prepared.entries if e.source_id != "util_water")
    result = build_frame(prepared.cache, (*registry, skipped), prepared.review)
    assert "util_water: SYN UNLISTED ZONE NUMBERS" in result.report
