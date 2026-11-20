"""Join regressions on invented inputs; no network or downloaded data."""

import locale
from dataclasses import replace
from pathlib import Path

import pytest
from custodian.tests.repository_root import repository_root
from custodian.tests.support.fetch_build import run_build as support_run_build
from custodian.tests.test_places_fsq import _release_entry
from custodian.tests.test_publicdata_behaviour import _clock, _entry, _ok, _sleep

import h3
from eii_custodian.publicdata.fetch import build as fetch_build_module
from eii_custodian.publicdata.places_fsq.assemble import _table_row
from eii_custodian.publicdata.places_fsq.errors import PlacesFsqError
from eii_custodian.publicdata.places_fsq.parse import parse_file
from eii_custodian.publicdata.places_fsq.policy import assert_policy, load_mapping


def test_skipped_fsq_preserves_other_build_stages(tmp_path, monkeypatch):
    """A skipped copy adds only its skip line, preserving stage calls and output."""
    events = []
    original_publish = fetch_build_module.publish_investment
    original_stage = fetch_build_module.run_stage

    def publish(*args, **kwargs):
        events.append("investment")
        return original_publish(*args, **kwargs)

    def stage(*args, **kwargs):
        events.append("series" if "build_entries" in kwargs else "regression")
        return original_stage(*args, **kwargs)

    def transport(url):
        return _ok(url, b"invented-bytes")

    monkeypatch.setattr(fetch_build_module, "publish_investment", publish)
    monkeypatch.setattr(fetch_build_module, "run_stage", stage)
    baseline = support_run_build(
        (_entry(),), transport, tmp_path / "baseline", _clock, _sleep
    )
    assert baseline.failure is None
    assert events == ["investment", "series", "regression"]
    events.clear()
    skipped = replace(_release_entry(), skip_reason="SYN-disabled")
    joined = support_run_build(
        (skipped, _entry()), transport, tmp_path / "joined", _clock, _sleep
    )
    assert joined.failure is None
    assert joined.lines[0] == "SKIP places_fsq/copy SYN-disabled"
    assert joined.lines[1:] == baseline.lines
    assert events == ["investment", "series", "regression"]


def test_missing_base_cell_still_refuses(tmp_path):
    """The frame's nullable lookup must not relax this table's cell refusal."""
    from custodian.tests.fixtures.places_fsq.invented import place, write_places

    path = tmp_path / "places.parquet"
    write_places(path, [place()])
    with pytest.raises(PlacesFsqError, match=r"^cell$"):
        _table_row(parse_file(path)[0], [], "2025-01-10")


def test_ambiguous_base_cell_refuses_with_exact_reason(tmp_path: Path) -> None:
    """A fine cell and its parent cannot both own an invented place."""
    from custodian.tests.fixtures.places_fsq.invented import place, write_places

    path = tmp_path / "places.parquet"
    write_places(path, [place()])
    row = parse_file(path)[0]
    fine = h3.latlng_to_cell(float(row.lat), float(row.lon), 9)
    grid = [
        {"cell": h3.str_to_int(fine)},
        {"cell": h3.str_to_int(h3.cell_to_parent(fine, 8))},
    ]
    with pytest.raises(PlacesFsqError) as caught:
        _table_row(row, grid, "2025-01-10")
    assert caught.value.reason == "cell"


def test_policy_text_is_read_as_utf8(tmp_path: Path) -> None:
    """The policy is UTF-8 even when the process locale is ASCII."""
    policy = (
        repository_root(Path(__file__))
        / "custodian"
        / "publicdata"
        / "review"
        / "places_fsq_policy.yaml"
    )
    path = tmp_path / "policy.yaml"
    path.write_text(policy.read_text(encoding="utf-8") + "\n# café\n", encoding="utf-8")
    previous = locale.setlocale(locale.LC_ALL)
    try:
        locale.setlocale(locale.LC_ALL, "C")
        assert_policy(path)
    finally:
        locale.setlocale(locale.LC_ALL, previous)


def test_mapping_text_is_read_as_utf8(tmp_path: Path) -> None:
    """An approved rationale survives even when the process locale is ASCII."""
    path = tmp_path / "mapping.csv"
    path.write_text(
        "source_category_id,place_category_key,mapping_version,review_status,"
        "reviewer_role,review_date,rationale\n"
        "SYN-category,SYN-target,SYN-version,approved,SYN-reviewer,"
        "2025-01-10,SYN-café rationale\n",
        encoding="utf-8",
    )
    previous = locale.setlocale(locale.LC_ALL)
    try:
        locale.setlocale(locale.LC_ALL, "C")
        loaded = load_mapping(path, frozenset({"SYN-target"}))
        assert len(loaded) == 1
        assert loaded[0].rationale == "SYN-café rationale"
    finally:
        locale.setlocale(locale.LC_ALL, previous)
