"""The public_data stage fails a planted figure and accepts the section 10 anchors."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from eii_custodian.publicdata.fetch.build import run_build
from eii_custodian.publicdata.fetch.transport import Response
from eii_custodian.publicdata.stage import EXPECTED, SECTION_10_IDS, run_stage


@pytest.mark.public_data
def test_section_10_ids_and_matching_fixture(tmp_path: Path) -> None:
    """Every section 10 anchor is registered, and a matching fixture passes."""
    assert SECTION_10_IDS == tuple(f"PUB-{number}" for number in range(62, 74))
    folder = tmp_path / "figures"
    folder.mkdir()
    for figure_id, parts in EXPECTED.items():
        (folder / f"{figure_id}.json").write_text(json.dumps(parts), encoding="utf-8")
    result = run_stage(tmp_path)
    assert result.mismatch == ""
    assert result.missing == ()


@pytest.mark.public_data
def test_planted_wrong_figure_fails_the_stage(tmp_path: Path) -> None:
    """A figure file that disagrees with the published anchor fails the build."""
    folder = tmp_path / "figures"
    folder.mkdir()
    planted = dict(EXPECTED["PUB-62"])
    planted["zone_69_2021"] = "1"
    (folder / "PUB-62.json").write_text(json.dumps(planted), encoding="utf-8")

    def unused(url: str) -> Response:
        raise AssertionError(url)

    outcome = run_build(
        (), unused, tmp_path, lambda: "2026-11-13T08:00:00Z", lambda _seconds: None
    )
    assert outcome.failure is not None
    assert outcome.failure.check == "public_data"
    assert outcome.failure.source_id == "PUB-62"
