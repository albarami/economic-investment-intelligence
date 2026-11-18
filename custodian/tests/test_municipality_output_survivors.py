"""Exact invented municipality bytes and directory/locale boundaries."""

from pathlib import Path

from custodian.tests.test_frame_live_survivors import _ascii_locale

from eii_custodian.publicdata.frame.municipality_output import write_municipality_output


def test_nested_output_is_repeatable_utf8_and_sorted(tmp_path: Path) -> None:
    cache = tmp_path / "missing" / "cache"
    rows = [{"municipality_code": "SYN-A", "name_en": "Invented", "name_ar": "تجريبي"}]
    expected = (
        '{"count": 1, "municipalities": [{"municipality_code": "SYN-A", '
        '"name_ar": "تجريبي", "name_en": "Invented"}]}\n'
    ).encode()
    with _ascii_locale():
        write_municipality_output(cache, rows)
        write_municipality_output(cache, rows)
    assert (cache / "frame_s2_t02/municipalities.json").read_bytes() == expected
