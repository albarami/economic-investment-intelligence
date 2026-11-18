"""LR3 frame receipt and report survivors; all receipts are invented."""

from dataclasses import replace

import pytest
from custodian.tests.snapshot_fixture import update_receipt
from custodian.tests.test_frame_census import cache_fixture, entry
from custodian.tests.test_frame_live_survivors import _ascii_locale

from eii_custodian.publicdata.fetch.snapshots import reviewed_selections
from eii_custodian.publicdata.frame.build import build_frame, read_cached
from eii_custodian.publicdata.frame.checks import FrameError


def _whole_text(found: object, literal: str) -> None:
    assert str(found) == literal


def test_receipt_is_utf8_under_ascii_locale(tmp_path):
    source = entry("util_elec")
    cache_fixture(tmp_path, source, [])
    digest = reviewed_selections(tmp_path)[source.key]
    update_receipt(tmp_path, source.key, digest, {"publisher": "SYN éditeur"})
    with _ascii_locale():
        body, loaded = read_cached(tmp_path, source, digest=digest)
    assert body == []
    assert loaded["publisher"] == "SYN éditeur"


def test_marker_character_is_not_a_hash_digit(tmp_path):
    source = entry("util_elec")
    cache_fixture(tmp_path, source, [])
    digest = reviewed_selections(tmp_path)[source.key]
    update_receipt(tmp_path, source.key, digest, {"sha256": "X" * 64})
    with pytest.raises(FrameError) as caught:
        read_cached(tmp_path, source, digest=digest)
    _whole_text(caught.value, "util_elec: snapshot_index_invalid")


@pytest.mark.parametrize("target", ["cache", "review"])
def test_overlapping_output_whole_refusal(tmp_path, target):
    cache, review = tmp_path / "cache", tmp_path / "review"
    output = (cache if target == "cache" else review) / "SYN-output"
    with pytest.raises(FrameError) as caught:
        build_frame(cache, (), review, output)
    _whole_text(caught.value, "review output overlaps inputs")


def test_without_geometry_reports_each_inventory_only_once(tmp_path):
    source = entry("util_elec")
    cache_fixture(tmp_path, source, [{"year": "2025", "zone_number": "42", "value": 3}])
    review = tmp_path / "review"
    review.mkdir()
    (review / "zone_crosswalk.csv").write_text("zone_code,util_elec,status\n")
    refused_hdx = replace(entry("bnd_hdx"), skip_reason="SYN-disabled")
    result = build_frame(tmp_path, (source, refused_hdx), review)
    assert result.report == [
        "bnd_hdx: SYN-disabled",
        "util_elec: inventory_only: utility figures belong to S2-T03",
        "frame: required geometry unavailable; dependent tables not built",
        "util_elec: 1 unlisted zone numbers",
    ]


@pytest.mark.parametrize("name", ["XXest_censusXX", "EST_CENSUS"])
def test_unknown_establishment_source_is_not_selected(tmp_path, name):
    """The redundant union term must not admit a new marker source identity."""
    review = tmp_path / "review"
    review.mkdir()
    (review / "zone_crosswalk.csv").write_text("zone_code,status\n")
    source = replace(entry("est_census"), source_id=name, skip_reason="SYN-disabled")
    result = build_frame(tmp_path, (source,), review)
    assert result.report == [
        "frame: required geometry unavailable; dependent tables not built"
    ]
