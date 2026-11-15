"""ISO reference invariants and invented alias violations (L-216 Q1)."""

import csv
import re
from pathlib import Path

import pytest

from eii_custodian.publicdata.series.parse import country_crosswalk

REVIEW = Path(__file__).resolve().parents[1] / "publicdata/review"


def test_complete_reference_and_explicit_aliases():
    with (REVIEW / "country_iso3.csv").open() as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 249
    assert len({row["iso3"] for row in rows}) == len(rows)
    assert len({row["name_en"] for row in rows}) == len(rows)
    assert all(re.fullmatch(r"[A-Z]{3}", row["iso3"]) for row in rows)
    assert all(row["human_reviewed"] == "false" for row in rows)
    with (REVIEW / "country_aliases.csv").open() as stream:
        aliases = list(csv.DictReader(stream))
    assert len(aliases) == 33
    assert sum(bool(row["iso3"]) for row in aliases) == 28
    assert all(row["human_reviewed"] == "false" for row in aliases)
    mapped = country_crosswalk()
    assert mapped == {row["name_en"]: row["iso3"] or None for row in rows + aliases}
    assert mapped["Åland Islands"] == "ALA"
    assert mapped["Zimbabwe"] == "ZWE"


@pytest.mark.parametrize(
    "rows,error",
    [
        ("Invented alias,ZZZ,true\n", "absent reference code"),
        ("Italy,QAT,true\n", "repeated country name"),
        ("Invented alias,ITA,true\nInvented alias,QAT,true\n", "repeated country name"),
    ],
)
def test_alias_violations_refused(tmp_path, rows, error):
    aliases = tmp_path / "aliases.csv"
    aliases.write_text("name_en,iso3,human_reviewed\n" + rows)
    with pytest.raises(ValueError, match=error):
        country_crosswalk(aliases=aliases)


def test_alias_uses_reference_code(tmp_path):
    aliases = tmp_path / "aliases.csv"
    aliases.write_text("name_en,iso3,human_reviewed\nInvented alias,ITA,true\n")
    assert country_crosswalk(aliases=aliases)["Invented alias"] == "ITA"
