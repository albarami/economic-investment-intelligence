"""Tests that kill the surviving mutants of the S2-T22 mutation pass on stage.py."""

from __future__ import annotations

import json
import locale
from pathlib import Path

import pytest

from eii_custodian.publicdata.stage import EXPECTED, run_stage

# Invented stand-ins of PUB-71's five field names (decision 0026 item 5), same
# shape as the stand-ins of test_public_data_stage.py; none is a real figure.
INVENTED_PUB_71 = {
    "national_private": "345678",
    "national_all": "456789",
    "national_1dp": "43.7",
    "zone_69_0dp": "52",
    "zone_70_0dp": "28",
}


@pytest.mark.public_data
def test_local_record_is_read_as_utf8(tmp_path: Path) -> None:
    """PUB-71's record is refused by the fixed reason even in an ASCII locale."""
    record = {**INVENTED_PUB_71, "zone_70_0dp": "café"}
    path = tmp_path / "local_expectations" / "PUB-71.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
    previous = locale.setlocale(locale.LC_ALL)
    try:
        locale.setlocale(locale.LC_ALL, "C")
        with pytest.raises(ValueError) as caught:
            run_stage(tmp_path)
    finally:
        locale.setlocale(locale.LC_ALL, previous)
    assert str(caught.value) == "PUB-71: local expectations record refused"


@pytest.mark.public_data
def test_selected_fetch_lines_error_text(tmp_path: Path) -> None:
    """build_entries without build_lines is refused by one fixed sentence."""
    with pytest.raises(ValueError) as caught:
        run_stage(tmp_path, build_entries=[])
    assert str(caught.value) == "selected fetch lines required"


@pytest.mark.public_data
def test_build_entries_result_has_empty_missing_and_mismatch(
    tmp_path: Path,
) -> None:
    """A build_entries run reports no missing row and no mismatch."""
    result = run_stage(tmp_path, build_entries=[], build_lines=[])
    assert result.missing == ()
    assert result.mismatch == ""
    assert result.failure is None


@pytest.mark.public_data
def test_unrecorded_is_empty_text_when_nothing_is_unrecorded(
    tmp_path: Path,
) -> None:
    """With no produced figure lacking a record, unrecorded is empty text."""
    result = run_stage(tmp_path)
    assert result.unrecorded == ""


@pytest.mark.public_data
def test_unknown_required_regression_error_text(tmp_path: Path) -> None:
    """A required row outside the section 10 ids is refused by one fixed sentence."""
    with pytest.raises(ValueError) as caught:
        run_stage(tmp_path, required=("PUB-99",))
    assert str(caught.value) == "unknown required regression"


@pytest.mark.public_data
def test_figure_text_is_read_as_utf8(tmp_path: Path) -> None:
    """A figure file is read as UTF-8 even when the process locale is ASCII."""
    figure = {**EXPECTED["PUB-62"], "zone_69_2021": "café"}
    folder = tmp_path / "figures"
    folder.mkdir()
    (folder / "PUB-62.json").write_text(
        json.dumps(figure, ensure_ascii=False), encoding="utf-8"
    )
    previous = locale.setlocale(locale.LC_ALL)
    try:
        locale.setlocale(locale.LC_ALL, "C")
        result = run_stage(tmp_path)
    finally:
        locale.setlocale(locale.LC_ALL, previous)
    assert result.mismatch == "PUB-62"
