"""The public_data stage fails a planted figure and accepts the section 10 anchors."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from eii_custodian.publicdata.fetch.build import run_build
from eii_custodian.publicdata.fetch.report import coverage_line
from eii_custodian.publicdata.fetch.transport import Response
from eii_custodian.publicdata.stage import EXPECTED, SECTION_10_IDS, run_stage

# Invented stand-ins of PUB-71's five field names (decision 0026 item 5): the
# published expected figures stay in the uncommitted cache record and none is
# committed.
INVENTED_PUB_71 = {
    "national_private": "123456",
    "national_all": "234567",
    "national_1dp": "52.6",
    "zone_69_0dp": "61",
    "zone_70_0dp": "39",
}


def _local_record(cache: Path, record: str) -> Path:
    """Write PUB-71's uncommitted expectations record under the cache."""
    path = cache / "local_expectations" / "PUB-71.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(record, encoding="utf-8")
    return path


@pytest.mark.public_data
def test_section_10_ids_and_matching_fixture(tmp_path: Path) -> None:
    """Every section 10 anchor is registered, and a matching fixture passes."""
    assert SECTION_10_IDS == tuple(f"PUB-{number}" for number in range(62, 74))
    folder = tmp_path / "figures"
    folder.mkdir()
    for figure_id, parts in EXPECTED.items():
        (folder / f"{figure_id}.json").write_text(json.dumps(parts), encoding="utf-8")
    # PUB-71's expected record is uncommitted (decision 0026 item 5): the stage
    # reads it from the cache's local record, here an invented stand-in.
    _local_record(tmp_path, json.dumps(INVENTED_PUB_71))
    (folder / "PUB-71.json").write_text(json.dumps(INVENTED_PUB_71), encoding="utf-8")
    result = run_stage(tmp_path)
    assert result.mismatch == ""
    assert result.missing == ()


@pytest.mark.public_data
def test_pub71_matching_local_record_passes(tmp_path: Path) -> None:
    """A local record matching the measured figure passes PUB-71."""
    _local_record(tmp_path, json.dumps(INVENTED_PUB_71))
    folder = tmp_path / "figures"
    folder.mkdir()
    (folder / "PUB-71.json").write_text(json.dumps(INVENTED_PUB_71), encoding="utf-8")
    result = run_stage(tmp_path, required=("PUB-71",))
    assert result.mismatch == ""
    assert "PUB-71" not in result.missing


@pytest.mark.public_data
def test_pub71_differing_local_record_fails_by_figure(tmp_path: Path) -> None:
    """A measured figure that disagrees with the local record fails by name."""
    _local_record(tmp_path, json.dumps(INVENTED_PUB_71))
    folder = tmp_path / "figures"
    folder.mkdir()
    planted = {**INVENTED_PUB_71, "national_all": "1"}
    (folder / "PUB-71.json").write_text(json.dumps(planted), encoding="utf-8")
    result = run_stage(tmp_path, required=("PUB-71",))
    assert result.mismatch == "PUB-71"


@pytest.mark.public_data
def test_pub71_without_local_record_is_not_measured(tmp_path: Path) -> None:
    """With no local record PUB-71 is reported not measured, never a pass."""
    folder = tmp_path / "figures"
    folder.mkdir()
    (folder / "PUB-71.json").write_text(json.dumps(INVENTED_PUB_71), encoding="utf-8")
    result = run_stage(tmp_path)
    assert result.mismatch == ""
    assert "PUB-71" in result.missing
    required = run_stage(tmp_path, required=("PUB-71",))
    assert required.mismatch == "PUB-71"
    assert "PUB-71" in required.missing


@pytest.mark.public_data
def test_pub71_present_figure_without_record_fails_the_build(
    tmp_path: Path,
) -> None:
    """A produced figure with no local record fails the build, named by row."""
    folder = tmp_path / "figures"
    folder.mkdir()
    (folder / "PUB-71.json").write_text(json.dumps(INVENTED_PUB_71), encoding="utf-8")
    result = run_stage(tmp_path)
    assert result.unrecorded == "PUB-71"
    assert "PUB-71" in result.missing

    def unused(url: str) -> Response:
        raise AssertionError(url)

    outcome = run_build(
        (), unused, tmp_path, lambda: "2026-11-13T08:00:00Z", lambda _seconds: None
    )
    assert outcome.failure is not None
    assert outcome.failure.check == "public_data"
    assert outcome.failure.source_id == "PUB-71"
    assert outcome.failure.expected == "local expectations record"
    assert outcome.failure.observed == "missing"
    assert coverage_line("PUB-71") in outcome.lines


@pytest.mark.public_data
def test_pub71_matching_record_passes_the_build(tmp_path: Path) -> None:
    """The same figure with a matching local record leaves the build unfailed."""
    _local_record(tmp_path, json.dumps(INVENTED_PUB_71))
    folder = tmp_path / "figures"
    folder.mkdir()
    (folder / "PUB-71.json").write_text(json.dumps(INVENTED_PUB_71), encoding="utf-8")

    def unused(url: str) -> Response:
        raise AssertionError(url)

    outcome = run_build(
        (), unused, tmp_path, lambda: "2026-11-13T08:00:00Z", lambda _seconds: None
    )
    assert outcome.failure is None
    assert coverage_line("PUB-71") not in outcome.lines


@pytest.mark.public_data
def test_pub71_no_figure_leaves_the_build_unfailed(tmp_path: Path) -> None:
    """No produced figure: the absent local record fails nothing."""

    def unused(url: str) -> Response:
        raise AssertionError(url)

    outcome = run_build(
        (), unused, tmp_path, lambda: "2026-11-13T08:00:00Z", lambda _seconds: None
    )
    assert outcome.failure is None
    assert coverage_line("PUB-71") in outcome.lines


@pytest.mark.public_data
@pytest.mark.parametrize(
    "record",
    [
        json.dumps({"national_private": "1"}),
        json.dumps({**INVENTED_PUB_71, "invented_extra": "1"}),
        json.dumps({**INVENTED_PUB_71, "national_all": "not decimal text"}),
        json.dumps({**INVENTED_PUB_71, "national_all": 7}),
        "not json",
    ],
    ids=["missing-field", "extra-field", "not-decimal-text", "not-text", "malformed"],
)
def test_pub71_malformed_local_record_refused(tmp_path: Path, record: str) -> None:
    """A local record of another shape is refused by one fixed reason."""
    _local_record(tmp_path, record)
    with pytest.raises(ValueError, match="local expectations record refused"):
        run_stage(tmp_path)


@pytest.mark.public_data
def test_planted_wrong_figure_fails_the_stage(tmp_path: Path) -> None:
    """A figure file that disagrees with the published anchor fails the build."""
    folder = tmp_path / "figures"
    folder.mkdir()
    planted = {
        "zone_69_2021": "429964072",
        "zone_69_2025": "1436402796",
        "ratio_2dp": "3.34",
        "sum_ratio_2dp": "1.34",
    }
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
