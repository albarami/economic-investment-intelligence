"""Record-boundary CSV comments; all generated content is invented."""

import csv
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from custodian.tests.repository_root import repository_root
from hypothesis import example, given, settings
from hypothesis import strategies as st

from eii_custodian.publicdata.frame.checks import FrameError
from eii_custodian.publicdata.frame.crosswalk import read_csv

# Frozen tracked CSV inventory at the task base; no cache or register inputs.
COMMITTED_CSVS = (
    "custodian/publicdata/review/activity_spine.csv",
    "custodian/publicdata/review/busy_besttime_venues.csv",
    "custodian/publicdata/review/category_allowlist.csv",
    "custodian/publicdata/review/country_aliases.csv",
    "custodian/publicdata/review/country_iso3.csv",
    "custodian/publicdata/review/district_crosswalk.csv",
    "custodian/publicdata/review/district_layer_aliases.csv",
    "custodian/publicdata/review/greater_doha_municipalities.csv",
    "custodian/publicdata/review/municipality_names.csv",
    "custodian/publicdata/review/places_fsq_categories.csv",
    "custodian/publicdata/review/places_ovt_attribution.csv",
    "custodian/publicdata/review/places_ovt_categories.csv",
    "custodian/publicdata/review/population_indicators.csv",
    "custodian/publicdata/review/property_use_map.csv",
    "custodian/publicdata/review/venue_busyness_crosswalk.csv",
    "custodian/publicdata/review/venue_crosswalk.csv",
    "custodian/publicdata/review/verified_places.csv",
    "custodian/publicdata/review/zone_crosswalk.csv",
    "custodian/publicdata/review/zones_without_districts.csv",
    "custodian/tests/fixtures/places/syn_review/places_ovt_attribution.csv",
    "custodian/tests/fixtures/places/syn_review/places_ovt_categories.csv",
    "custodian/tests/fixtures/places/syn_review/verified_places.csv",
    "custodian/tests/fixtures/property/use_map.csv",
)


def _old_read_csv(
    path: Path, *, header: tuple[str, ...] | None = None
) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        lines = (line for line in handle if not line.startswith("#"))
        if header is None:
            return list(csv.DictReader(lines))
        reader = csv.reader(lines, strict=True)
        try:
            if next(reader, None) != list(header):
                raise FrameError("district_alias: CSV header")
            rows = []
            for row in reader:
                if len(row) != len(header):
                    raise FrameError("district_alias: CSV row width")
                rows.append(dict(zip(header, row, strict=True)))
            return rows
        except csv.Error as exc:
            raise FrameError("district_alias: CSV row width or syntax") from exc


@pytest.mark.parametrize("relative", COMMITTED_CSVS)
def test_crosswalk_committed_csv_parity(relative: str) -> None:
    path = repository_root(Path(__file__)) / relative
    expected = _old_read_csv(path)
    assert read_csv(path) == expected
    with path.open(encoding="utf-8", newline="") as handle:
        header = tuple(
            next(csv.reader(line for line in handle if not line.startswith("#")))
        )
    assert read_csv(path, header=header) == _old_read_csv(path, header=header)


@pytest.mark.parametrize("header", [None, ("key", "value")])
@pytest.mark.parametrize(
    "content, expected",
    [
        ('key,value\nSYN,"a\n#b"\n', [{"key": "SYN", "value": "a\n#b"}]),
        (
            "key,value\nSYN,a\n#comment\nSYN,b\n",
            [{"key": "SYN", "value": "a"}, {"key": "SYN", "value": "b"}],
        ),
        (
            '#comment with " ignored\nkey,value\nSYN,"a"\n#comment\n',
            [{"key": "SYN", "value": "a"}],
        ),
        (
            'key,value\nSYN,"a""\n#b"\n#comment\nSYN,c\n',
            [{"key": "SYN", "value": 'a"\n#b'}, {"key": "SYN", "value": "c"}],
        ),
    ],
)
def test_crosswalk_comment_boundaries(
    tmp_path: Path,
    header: tuple[str, ...] | None,
    content: str,
    expected: list[dict[str, str]],
) -> None:
    path = tmp_path / "invented.csv"
    path.write_text(content, encoding="utf-8", newline="")
    assert read_csv(path, header=header) == expected


def test_crosswalk_unterminated_permissive_value(tmp_path: Path) -> None:
    path = tmp_path / "invented.csv"
    path.write_text('key,value\nSYN,"unfinished', encoding="utf-8")
    assert read_csv(path) == [{"key": "SYN", "value": "unfinished"}]
    assert read_csv(path) == _old_read_csv(path)


@pytest.mark.parametrize(
    "content, reason",
    [
        ("wrong,value\nSYN,a\n", "district_alias: CSV header"),
        ("key,value\nSYN,a,extra\n", "district_alias: CSV row width"),
        ('key,value\nSYN,"unfinished', "district_alias: CSV row width or syntax"),
    ],
)
def test_crosswalk_strict_refusal(tmp_path: Path, content: str, reason: str) -> None:
    path = tmp_path / "invented.csv"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(FrameError, match=f"^{reason}$"):
        read_csv(path, header=("key", "value"))
    with pytest.raises(FrameError, match=f"^{reason}$"):
        _old_read_csv(path, header=("key", "value"))


@settings(deadline=None)
@given(st.text())
@example("a\n#b")
@example('a"\n#b')
@example("")
def test_crosswalk_writer_roundtrip(value: str) -> None:
    with TemporaryDirectory() as folder:
        path = Path(folder) / "invented.csv"
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["key", "value"])
            writer.writerow(["SYN", value])
        expected = [{"key": "SYN", "value": value}]
        assert read_csv(path) == expected
        assert read_csv(path, header=("key", "value")) == expected
