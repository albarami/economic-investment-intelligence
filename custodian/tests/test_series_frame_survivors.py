"""Read-back refuses wrong field types and retains exact refusal text."""

from pathlib import Path

import pytest
from custodian.tests.test_frame_live_survivors import _ascii_locale
from custodian.tests.test_series_frame import _output

from eii_custodian.publicdata.series.frame import (
    MunicipalityFrameRefused,
    frame_municipalities,
)


def _whole_text(found: BaseException, literal: str) -> None:
    assert str(found) == literal


@pytest.mark.parametrize(
    "row",
    [
        {"municipality_code": "SYN-A", "name_ar": 7},
        {"municipality_code": 7, "name_ar": "تجريبي"},
    ],
)
def test_wrong_field_types_refuse(tmp_path: Path, row: dict[str, object]) -> None:
    _output(tmp_path, [row])
    with pytest.raises(MunicipalityFrameRefused) as caught:
        frame_municipalities(tmp_path)
    _whole_text(caught.value, "municipality_frame_absent")


def test_readback_is_utf8_under_ascii_locale(tmp_path: Path) -> None:
    _output(tmp_path, [{"municipality_code": "SYN-A", "name_ar": "تجريبي"}])
    with _ascii_locale():
        rows = frame_municipalities(tmp_path)
    assert len(rows) == 1
    assert rows[0].code == "SYN-A"
    assert rows[0].name_ar == "تجريبي"
