"""Invented exports for the Public split families. No real row is used."""

from __future__ import annotations

from copy import deepcopy
from decimal import Decimal
from pathlib import Path

import pytest
import yaml

from eii_custodian.publicdata.additions.build import parsers
from eii_custodian.publicdata.additions.common import (
    AdditionError,
    Coverage,
    FamilyParse,
    parse_period_rule,
    require_lineage,
)
from eii_custodian.publicdata.additions.splits import PARSERS
from eii_custodian.publicdata.fetch.registry import Entry, load_registry

REVIEW = Path(__file__).resolve().parents[1] / "publicdata" / "review"
METHOD = "eii_custodian.publicdata.additions.splits.parse@1"
HOTEL_RATING_BREAKDOWN = "hotel_rating=Two & One Star"
RECEIPT = {
    "retrieved_utc": "2026-01-02T03:04:05Z",
    "sha256": "abc123def",
    "source_modified": "1999-01-01",
}
FEMALE = "female-population-and-labour-force-by-municipality"
MALE = "male-population-and-labour-force-by-municipality"
EMPLOYED = "employed-persons-15-years-and-above-by-gender-and-municipality"
UNEMPLOYED = "unemployed-persons-15-years-and-above-by-gender-and-municipality"
POP_F = "females-population-by-municipality-and-age-groups-december-2020"
ACTIVE_F = (
    "economically-active-females-15-years-and-above-by-age-group-and-economic-activity"
)
NAT_MALES = "economically-active-non-qatari-males-15-years-and-above-by-occupation-and-economic-activity"
NAT_POP = "economically-active-qatari-population-15-years-and-above-by-occupation-and-economic-activity"
COMP_BASE = "number-of-employees-and-compensation-of-employees-by-nationality-and-main-economic-activity"
COMP_SOCIAL = "number-of-employees-and-compensation-of-employees-by-nationality-and-main-economic-activity-social0"
STUDENTS = "students-by-level-of-education-municipality-gender-type-of-education-and-nationality-2025-2026"
HOTEL = "hotel-guests-by-nationality-hotel-rating-and-hotel-stays"
MODE = "visitor-arrivals-by-mode-of-entry"
REGION = "visitor-arrivals-by-region"
TRENDS = "visitor-arrivals-trends-by-mode-of-transport-air-land-sea"


def test_labour_year_field_replaces_the_unconfirmed_marker() -> None:
    """The four labour files name the year column. The unemployed year is a date."""
    rules = {
        entry.slug: (entry.period_field, dict(entry.columns))
        for entry in load_registry()
        if entry.source_id == "lf_muni_sex"
    }
    assert rules[FEMALE][0] == "sit=row;form=year_text;field=year"
    assert rules[MALE][0] == "sit=row;form=year_text;field=year"
    assert rules[EMPLOYED][0] == "sit=row;form=year_text;field=year"
    assert rules[UNEMPLOYED][0] == "sit=row;form=date_as_year;field=year"
    assert rules[FEMALE][1]["year"] == "string"
    assert rules[UNEMPLOYED][1]["year"] == "string"


def test_both_population_files_hold_a_text_year(tmp_path: Path) -> None:
    """Both registry rows use a four-digit text year, and each slug parses one."""
    entries = [
        entry for entry in load_registry() if entry.source_id == "pop_muni_age_sex"
    ]
    assert len(entries) == 2
    sexes: list[str] = []
    for entry in entries:
        assert entry.period_field == "sit=row;form=year_text;field=years"
        rule = parse_period_rule(entry.period_field)
        assert rule.form == "year_text"
        assert rule.field == "years"
        folder = tmp_path / entry.slug
        folder.mkdir()
        parsed = _parse(entry, [_population_age_sex_row(entry)], folder)
        assert parsed.rows[0]["period"] == "2016"
        assert parsed.period_first == "2016"
        sex = parsed.rows[0]["sex"]
        assert isinstance(sex, str)
        sexes.append(sex)
    assert sorted(sexes) == ["female", "male"]


def test_employed_row_keeps_its_category_and_its_lineage(tmp_path: Path) -> None:
    """One employed cell is one row. The municipality key comes from the lookup."""
    entry = _labour(EMPLOYED, "employed")
    parsed = _parse(
        entry,
        [
            {
                "year": "2022",
                "municipality": "North Ward",
                "lbldy": "حي مخترع",
                "gender": "Females",
                "ljns": "اناث",
                "number": 4,
            }
        ],
        tmp_path,
    )
    assert parsed.table == "pub_labour_sex_municipality"
    assert parsed.period_first == "2022"
    assert parsed.period_last == "2022"
    assert parsed.coverage == ()
    assert parsed.questions == ()
    assert parsed.rows == (
        {
            "municipality_code": "north_ward",
            "sex": "female",
            "indicator": "employed",
            "value": Decimal("4"),
            "unit": "persons",
            **_line(entry.key, "2022"),
        },
    )


def test_unemployed_date_text_is_a_year_and_a_zero_stays_zero(tmp_path: Path) -> None:
    """A date used as a year is not stored as a date. A published zero is not dropped."""
    entry = _labour(UNEMPLOYED, "unemployed", form="date_as_year")
    parsed = _parse(
        entry,
        [
            {
                "year": "2020-01-01",
                "municipality": "South Ward",
                "lbldy": "حي آخر",
                "gender": "Males",
                "ljns": "ذكور",
                "number": 0,
            }
        ],
        tmp_path,
    )
    assert parsed.rows == (
        {
            "municipality_code": "south_ward",
            "sex": "male",
            "indicator": "unemployed",
            "value": Decimal("0"),
            "unit": "persons",
            **_line(entry.key, "2020"),
        },
    )
    assert parsed.period_first == "2020"
    assert parsed.rows[0]["period"] == "2020"


def test_a_date_that_is_not_the_first_of_january_fails(tmp_path: Path) -> None:
    """date_as_year accepts only the closed form YYYY-01-01."""
    entry = _labour(UNEMPLOYED, "unemployed", form="date_as_year")
    with pytest.raises(AdditionError) as caught:
        _parse(entry, [_gender_row("2024-06-01", 1)], tmp_path)
    assert caught.value.name == "period_form"


def test_population_indicators_are_not_renamed_or_repeated(tmp_path: Path) -> None:
    """Labels the contract does not name are left out. Employed is not stored twice."""
    entry = _population_labour(FEMALE, "female")
    parsed = _parse(
        entry,
        [
            _indicator_row("2019", "Economically Inactive", 2),
            _indicator_row("2019", "Employed", 4),
            _indicator_row("2019", "Female Population", 9),
            _indicator_row("2021", "Economically Active", 5),
            _indicator_row("2021", "Female Population (15 Years & above)", 8),
        ],
        tmp_path,
    )
    assert parsed.rows == ()
    assert parsed.period_first == "2019"
    assert parsed.period_last == "2021"
    reasons = {item.reason: item.count for item in parsed.coverage}
    assert reasons == {"indicator_unheld": 4, "published_twice": 1}
    assert len(parsed.questions) == 1
    question = parsed.questions[0]
    assert question.contract == (
        "indicator is population, labour_force, employed or unemployed"
    )
    assert "two population indicators" in question.inventory
    assert "Economically Active" in question.inventory
    assert "labour_force" in question.change


def test_an_unknown_labour_label_stops(tmp_path: Path) -> None:
    """A category outside the closed list is not stored under a nearby name."""
    entry = _population_labour(FEMALE, "female")
    with pytest.raises(AdditionError) as caught:
        _parse(entry, [_indicator_row("2019", "Something else", 1)], tmp_path)
    assert caught.value.name == "category_unlisted"


def test_null_measure_is_omitted_and_other_text_stops(tmp_path: Path) -> None:
    """A missing number is not zero. Text outside the empty missing list stops."""
    entry = _labour(EMPLOYED, "employed")
    parsed = _parse(entry, [_gender_row("2022", None)], tmp_path)
    assert parsed.rows == ()
    assert parsed.coverage[0].reason == "missing_measure"
    assert parsed.coverage[0].count == 1
    with pytest.raises(AdditionError) as caught:
        _parse(entry, [_gender_row("2022", "n/a")], tmp_path)
    assert caught.value.name == "measure_unparsed"


def test_blank_municipality_is_unheld_and_a_spelling_stops(tmp_path: Path) -> None:
    """An empty place is left out. An unmapped spelling stops, and so does a mismatch."""
    entry = _labour(EMPLOYED, "employed")
    blank = _gender_row("2022", 3)
    blank["municipality"] = ""
    blank["lbldy"] = ""
    parsed = _parse(entry, [blank], tmp_path)
    assert parsed.rows == ()
    assert parsed.coverage == (Coverage("contract_key_unheld", 1),)
    english_only = _gender_row("2022", 3)
    english_only["municipality"] = ""
    english_only_parsed = _parse(entry, [english_only], tmp_path)
    assert english_only_parsed.coverage == (Coverage("contract_key_unheld", 1),)
    arabic_only = _gender_row("2022", 3)
    arabic_only["lbldy"] = ""
    arabic_only_parsed = _parse(entry, [arabic_only], tmp_path)
    assert arabic_only_parsed.coverage == (Coverage("contract_key_unheld", 1),)
    unknown = _gender_row("2022", 3)
    unknown["municipality"] = "Nowhere"
    with pytest.raises(AdditionError) as caught:
        _parse(entry, [unknown], tmp_path)
    assert caught.value.name == "unmapped_municipality"
    crossed = _gender_row("2022", 3)
    crossed["lbldy"] = "حي آخر"
    with pytest.raises(AdditionError) as bilingual:
        _parse(entry, [crossed], tmp_path)
    assert bilingual.value.name == "bilingual_municipality"


def test_duplicate_key_unknown_field_and_unconfirmed_year_stop(tmp_path: Path) -> None:
    """Two cells of one key, an undeclared field, and an unnamed year each stop."""
    entry = _labour(EMPLOYED, "employed")
    with pytest.raises(AdditionError) as duplicate:
        _parse(entry, [_gender_row("2022", 1), _gender_row("2022", 2)], tmp_path)
    assert duplicate.value.name == "duplicate_key"
    extra = _gender_row("2022", 1)
    extra["note"] = "x"
    with pytest.raises(AdditionError) as unknown:
        _parse(entry, [extra], tmp_path)
    assert unknown.value.name == "unknown_source_field"
    unnamed = _labour(EMPLOYED, "employed")
    unnamed = _replace_period(unnamed, "sit=row;form=year_text;field=to_be_confirmed")
    with pytest.raises(AdditionError) as unconfirmed:
        _parse(unnamed, [_gender_row("2022", 1)], tmp_path)
    assert unconfirmed.value.name == "period_field_unconfirmed"


def test_lineage_refuses_each_missing_part(tmp_path: Path) -> None:
    """Source, period, retrieval, method, licence and hash each refuse on their own."""
    entry = _labour(EMPLOYED, "employed")
    parsed = _parse(entry, [_gender_row("2022", 4)], tmp_path)
    row = dict(parsed.rows[0])
    require_lineage(row)
    for field in (
        "source_key",
        "period",
        "retrieved_utc",
        "method",
        "licence_id",
        "sha256",
    ):
        broken = dict(row)
        broken[field] = ""
        with pytest.raises(AdditionError) as caught:
            require_lineage(broken)
        assert caught.value.name == "lineage_incomplete"
    with pytest.raises(AdditionError) as missing_hash:
        PARSERS["lf_muni_sex"](
            entry,
            [_gender_row("2022", 4)],
            {"retrieved_utc": RECEIPT["retrieved_utc"]},
            {},
            _cross(tmp_path),
        )
    assert missing_hash.value.name == "lineage_incomplete"


def test_population_age_sex_uses_the_slug_and_drops_geometry(tmp_path: Path) -> None:
    """Sex comes from the reviewed slug. Geometry is not a column of the table."""
    entry = _pop()
    parsed = _parse(
        entry,
        [
            {
                "years": "2016",
                "fy_t_l_mr_blsnwt": "1 - 4",
                "age_groups_in_years": "1 - 4",
                "lbldy": "حي مخترع",
                "municipality": "North Ward",
                "value": 6,
                "geo_point": None,
                "geo_shape": {"kind": "invented"},
            }
        ],
        tmp_path,
    )
    assert parsed.table == "pub_population_age_sex"
    assert parsed.rows == (
        {
            "municipality_code": "north_ward",
            "age_group": "1 - 4",
            "sex": "female",
            "indicator": "residents",
            "value": Decimal("6"),
            "unit": "persons",
            **_line(entry.key, "2016"),
        },
    )
    assert "geo_shape" not in parsed.rows[0]
    with pytest.raises(AdditionError) as fraction:
        _parse(
            entry,
            [
                {
                    "years": "2016",
                    "fy_t_l_mr_blsnwt": "1 - 4",
                    "age_groups_in_years": "1 - 4",
                    "lbldy": "حي مخترع",
                    "municipality": "North Ward",
                    "value": 1.5,
                    "geo_point": None,
                    "geo_shape": None,
                }
            ],
            tmp_path,
        )
    assert fraction.value.name == "measure_not_integral"


def test_active_sex_keeps_one_cell_and_does_not_fill_a_gap(tmp_path: Path) -> None:
    """The measure field named total is the cell, not a total row, and no age is invented."""
    entry = _active_sex()
    parsed = _parse(
        entry,
        [
            {
                "year": "2019",
                "age_group": "15 - 19",
                "economic_activity": "Education",
                "lnsht_lqtsdy": "تعليم",
                "total": 7,
            }
        ],
        tmp_path,
    )
    assert parsed.table == "pub_active_sex_age"
    assert parsed.rows == (
        {
            "sex": "female",
            "age_group": "15 - 19",
            "activity_key": "Education",
            "indicator": "economically_active",
            "value": Decimal("7"),
            "unit": "persons",
            **_line(entry.key, "2019"),
        },
    )
    assert all(row["age_group"] != "20 - 24" for row in parsed.rows)


def test_nationality_and_sex_come_from_the_slug_map(tmp_path: Path) -> None:
    """The population slug is sex all. The males slug reads the measure field total."""
    males = _active_nat(NAT_MALES, "male", "non_qatari", "total")
    parsed = _parse(males, [_nat_row("2018", 3)], tmp_path)
    assert parsed.table == "pub_active_nationality_occupation"
    assert parsed.rows[0]["sex"] == "male"
    assert parsed.rows[0]["nationality_group"] == "non_qatari"
    assert parsed.rows[0]["occupation_key"] == "Clerks"
    assert parsed.rows[0]["activity_key"] == "Education"
    assert parsed.rows[0]["value"] == Decimal("3")
    assert parsed.rows[0]["indicator"] == "economically_active"
    population = _active_nat(NAT_POP, "all", "qatari", "number")
    kept = _parse(population, [_nat_row("2024", 11, field="number")], tmp_path)
    assert len(kept.rows) == 1
    assert kept.rows[0]["sex"] == "all"
    assert kept.rows[0]["nationality_group"] == "qatari"
    assert kept.rows[0]["period"] == "2024"


def test_compensation_keeps_levels_codes_and_a_null(tmp_path: Path) -> None:
    """Mixed levels stay separate. A text code keeps its zero. A null is not zero."""
    base = _comp(COMP_BASE, "bulletin", "code", "labor_indicator")
    parsed = _parse(
        base,
        [
            _comp_row("2018", "06", "Qatari", "Number of Employees", 4, "code"),
            _comp_row(
                "2018", "B", "Non-Qatari", "Compensation of Employees", 9, "code"
            ),
        ],
        tmp_path,
    )
    assert parsed.table == "pub_compensation_nationality"
    assert len(parsed.rows) == 2
    by_code = {str(row["activity_key"]): row for row in parsed.rows}
    assert by_code["06"]["nationality_group"] == "qatari"
    assert by_code["06"]["indicator"] == "employees"
    assert by_code["06"]["unit"] == "to_be_confirmed"
    assert by_code["06"]["value"] == Decimal("4")
    assert by_code["06"]["table_code"] == "bulletin"
    assert by_code["B"]["indicator"] == "compensation"
    assert by_code["B"]["unit"] == "annual"
    assert by_code["B"]["nationality_group"] == "non_qatari"
    assert by_code["B"]["value"] == Decimal("9")
    assert "_x000D_" not in repr(parsed.rows)
    social = _comp(COMP_SOCIAL, "social0", "activity_code", "indicator")
    emptied = _parse(
        social,
        [
            {
                "year": "2018",
                "activity_code": 410,
                "main_economic_activity": "invented",
                "lnsht_lqtsdy_lry_ysy": "ملصق_x000D_",
                "nationality": "Qataris",
                "ljnsy": "قطريون",
                "indicator": "Number of Employees",
                "lbyn": "عدد",
                "value": None,
            }
        ],
        tmp_path,
    )
    assert emptied.rows == ()
    assert emptied.coverage[0].reason == "missing_measure"
    assert emptied.coverage[0].count == 1
    kept = _parse(
        social,
        [
            {
                "year": "2018",
                "activity_code": 410,
                "main_economic_activity": "invented",
                "lnsht_lqtsdy_lry_ysy": "ملصق_x000D_",
                "nationality": "Non Qatari",
                "ljnsy": "غير قطريون",
                "indicator": "Compensation of Employees",
                "lbyn": "تعويضات",
                "value": 2,
            }
        ],
        tmp_path,
    )
    assert kept.rows[0]["activity_key"] == "410"
    assert kept.rows[0]["nationality_group"] == "non_qatari"
    assert "_x000D_" not in repr(kept.rows)


def test_students_school_year_and_published_levels(tmp_path: Path) -> None:
    """A school year stays a school year. An absent combination is not written as zero."""
    entry = _students()
    parsed = _parse(
        entry,
        [
            {
                "year": "2025-2026",
                "municipality": "North Ward",
                "lbldy": "حي مخترع",
                "level_of_education": "Pre primary",
                "lmrhl_lt_lymy": "ما قبل",
                "type_of_education": "Government",
                "nw_lt_lym": "حكومي",
                "nationality": "Non Qatari",
                "ljnsy": "غير قطري",
                "gender": "Female",
                "ljns": "انثى",
                "number_of_students": 12,
            }
        ],
        tmp_path,
    )
    assert parsed.table == "pub_students"
    assert parsed.rows == (
        {
            "municipality_code": "north_ward",
            "education_level": "Pre primary",
            "education_type": "Government",
            "sex": "female",
            "nationality_group": "non_qatari",
            "indicator": "students",
            "value": 12,
            "unit": "persons",
            **_line(
                entry.key, "2025-2026", "Ministry of Education and Higher Education"
            ),
        },
    )
    assert type(parsed.rows[0]["value"]) is int
    with pytest.raises(AdditionError) as caught:
        _parse(
            entry,
            [
                {
                    "year": "2025-2027",
                    "municipality": "North Ward",
                    "lbldy": "حي مخترع",
                    "level_of_education": "Pre primary",
                    "lmrhl_lt_lymy": "ما قبل",
                    "type_of_education": "Government",
                    "nw_lt_lym": "حكومي",
                    "nationality": "Qatari",
                    "ljnsy": "قطري",
                    "gender": "Male",
                    "ljns": "ذكر",
                    "number_of_students": 1,
                }
            ],
            tmp_path,
        )
    assert caught.value.name == "period_form"


def test_hotel_guests_keep_eight_groups_and_a_fraction(tmp_path: Path) -> None:
    """Nationality stays the published group. Rating is dimension=value. Nights may fraction."""
    entry = _hotel()
    parsed = _parse(
        entry,
        [
            {
                "year": "2021",
                "nationality": "Qataris",
                "ljnsy": "قطريون",
                "hotel_rating": "Two & One Star",
                "drj_lfndq": "نجمتان",
                "metric": "Nights",
                "lmqys": "ليالي",
                "number": "1.5",
            }
        ],
        tmp_path,
    )
    assert parsed.table == "pub_visitor_markets"
    assert parsed.rows == (
        {
            "table_code": "hotel_guests",
            "nationality_group": "Qataris",
            "breakdown_key": HOTEL_RATING_BREAKDOWN,
            "indicator": "nights",
            "value": Decimal("1.5"),
            "unit": "to_be_confirmed",
            **_line(entry.key, "2021"),
        },
    )


def test_arrival_tables_are_not_added_together(tmp_path: Path) -> None:
    """Month columns become one row each. Neither table gains a total the file lacks."""
    mode = _wide(MODE, "mode_of_entry", "tryq_ldkhwl")
    mode_rows = _parse(
        mode,
        [
            {
                "mode_of_entry": "Air",
                "tryq_ldkhwl": "الجو",
                "june_2024": 2,
                "july_2024": 5,
                "august_2024": None,
                "september_2024": 1,
                "october_2024": 1,
                "november_2024": 1,
            }
        ],
        tmp_path,
    )
    assert mode_rows.table == "pub_visitor_markets"
    assert [row["period"] for row in mode_rows.rows] == [
        "2024-06",
        "2024-07",
        "2024-09",
        "2024-10",
        "2024-11",
    ]
    assert [row["value"] for row in mode_rows.rows] == [
        Decimal("2"),
        Decimal("5"),
        Decimal("1"),
        Decimal("1"),
        Decimal("1"),
    ]
    assert all(row["nationality_group"] == "all" for row in mode_rows.rows)
    assert all(row["breakdown_key"] == "mode_of_entry=Air" for row in mode_rows.rows)
    assert all(row["indicator"] == "arrivals" for row in mode_rows.rows)
    assert all(row["table_code"] == "arrivals_by_mode" for row in mode_rows.rows)
    assert mode_rows.coverage[0].reason == "missing_measure"
    assert mode_rows.coverage[0].count == 1
    assert Decimal("7") not in [row["value"] for row in mode_rows.rows]
    region = _wide(REGION, "region", "lmntq")
    region_rows = _parse(
        region,
        [
            {
                "region": "Europe",
                "lmntq": "اوروبا",
                "june_2024": 2,
                "july_2024": 5,
            }
        ],
        tmp_path,
    )
    assert region_rows.rows[0]["nationality_group"] == "Europe"
    assert region_rows.rows[0]["breakdown_key"] == "ALL"
    assert region_rows.rows[0]["table_code"] == "arrivals_by_region"
    assert region_rows.rows[0]["value"] == Decimal("2")
    assert len(region_rows.rows) == 2
    with pytest.raises(AdditionError) as fraction:
        _parse(
            mode,
            [
                {
                    "mode_of_entry": "Air",
                    "tryq_ldkhwl": "الجو",
                    "june_2024": 1.5,
                }
            ],
            tmp_path,
        )
    assert fraction.value.name == "measure_not_integral"


def test_trends_do_not_invent_a_missing_mode(tmp_path: Path) -> None:
    """A year with one mode stays one row. The publisher on the row is the entry's."""
    entry = _trends()
    parsed = _parse(
        entry,
        [
            {
                "year": "2020",
                "mode_of_transportation": "Sea",
                "wsyl_lnql": "البحر",
                "arrivals": 8,
            }
        ],
        tmp_path,
    )
    assert parsed.rows == (
        {
            "table_code": "arrival_trends",
            "nationality_group": "all",
            "breakdown_key": "mode_of_transportation=Sea",
            "indicator": "arrivals",
            "value": Decimal("8"),
            "unit": "to_be_confirmed",
            **_line(entry.key, "2020", "Qatar Tourism"),
        },
    )
    assert parsed.period_first == "2020"
    assert parsed.period_last == "2020"


def test_modified_date_is_not_the_period(tmp_path: Path) -> None:
    """The sidecar modified date is not read as a year."""
    entry = _labour(EMPLOYED, "employed")
    parsed = _parse(entry, [_gender_row("2022", 4)], tmp_path)
    assert parsed.period_first == "2022"
    assert parsed.rows[0]["period"] != "1999"


def test_a_column_period_on_a_row_family_stops(tmp_path: Path) -> None:
    """A month-column rule is not applied to a family whose period sits on the row."""
    entry = _replace_period(
        _labour(EMPLOYED, "employed"), "sit=columns;form=month_name_year"
    )
    with pytest.raises(AdditionError) as caught:
        _parse(entry, [_gender_row("2022", 1)], tmp_path)
    assert caught.value.name == "period_sit"


def test_a_missing_review_or_frame_stops(tmp_path: Path) -> None:
    """A slug with no reviewed role, or a municipal row with no names file, stops."""
    entry = _labour(EMPLOYED, "employed")
    entry = _replace_period(entry, entry.period_field)
    missing = _entry(key="lf_muni_sex/not-a-slug", slug="not-a-slug")
    with pytest.raises(AdditionError) as unreadable:
        PARSERS["lf_muni_sex"](
            missing, [_gender_row("2022", 1)], RECEIPT, {}, _cross(tmp_path)
        )
    assert unreadable.value.name == "field_map_unreadable"
    with pytest.raises(AdditionError) as frame:
        PARSERS["lf_muni_sex"](
            entry,
            [_gender_row("2022", 1)],
            RECEIPT,
            {},
            {"frame": "not-a-path", "review": REVIEW},
        )
    assert frame.value.name == "crosswalk_missing"


def test_a_blank_side_an_unknown_category_and_a_bad_code_stop(tmp_path: Path) -> None:
    """Each closed list and each code shape refuses one invented cell."""
    population = _pop()
    twin = {
        "years": "2016",
        "fy_t_l_mr_blsnwt": "5 - 9",
        "age_groups_in_years": "1 - 4",
        "lbldy": "حي مخترع",
        "municipality": "North Ward",
        "value": 6,
        "geo_point": None,
        "geo_shape": None,
    }
    with pytest.raises(AdditionError) as ages:
        _parse(population, [twin], tmp_path)
    assert ages.value.name == "category_unlisted"
    unknown_age = dict(twin)
    unknown_age["fy_t_l_mr_blsnwt"] = "not-an-age"
    unknown_age["age_groups_in_years"] = "not-an-age"
    with pytest.raises(AdditionError) as unlisted:
        _parse(population, [unknown_age], tmp_path)
    assert unlisted.value.name == "category_unlisted"
    missing_age = dict(twin)
    missing_age["fy_t_l_mr_blsnwt"] = "1 - 4"
    missing_age["value"] = None
    omitted = _parse(population, [missing_age], tmp_path)
    assert omitted.rows == ()
    assert omitted.coverage == (Coverage("missing_measure", 1),)
    gender = _gender_row("2022", 4)
    gender["gender"] = "Other"
    with pytest.raises(AdditionError) as other:
        _parse(_labour(EMPLOYED, "employed"), [gender], tmp_path)
    assert other.value.name == "category_unlisted"
    active = _active_sex()
    gap = {
        "year": "2019",
        "age_group": "15 - 19",
        "economic_activity": "Education",
        "lnsht_lqtsdy": "تعليم",
        "total": None,
    }
    active_missing = _parse(active, [gap], tmp_path)
    assert active_missing.rows == ()
    assert active_missing.coverage == (Coverage("missing_measure", 1),)
    nat = _active_nat(NAT_MALES, "male", "non_qatari", "total")
    nat_missing = _parse(nat, [_nat_row("2019", None)], tmp_path)
    assert nat_missing.rows == ()
    assert nat_missing.coverage == (Coverage("missing_measure", 1),)
    hotel = _hotel()
    hotel_missing = _parse(
        hotel,
        [
            {
                "year": "2021",
                "nationality": "Qataris",
                "ljnsy": "قطريون",
                "hotel_rating": "Two & One Star",
                "drj_lfndq": "نجمتان",
                "metric": "Nights",
                "lmqys": "ليالي",
                "number": None,
            }
        ],
        tmp_path,
    )
    assert hotel_missing.rows == ()
    assert hotel_missing.coverage == (Coverage("missing_measure", 1),)
    trends = _trends()
    trends_missing = _parse(
        trends,
        [
            {
                "year": "2020",
                "mode_of_transportation": "Sea",
                "wsyl_lnql": "البحر",
                "arrivals": None,
            }
        ],
        tmp_path,
    )
    assert trends_missing.rows == ()
    assert trends_missing.coverage == (Coverage("missing_measure", 1),)
    students = _students()
    students_missing = _parse(
        students,
        [
            {
                "year": "2025-2026",
                "municipality": "North Ward",
                "lbldy": "حي مخترع",
                "level_of_education": "Pre primary",
                "lmrhl_lt_lymy": "ما قبل",
                "type_of_education": "Government",
                "nw_lt_lym": "حكومي",
                "nationality": "Non Qatari",
                "ljnsy": "غير قطري",
                "gender": "Female",
                "ljns": "انثى",
                "number_of_students": None,
            }
        ],
        tmp_path,
    )
    assert students_missing.rows == ()
    assert students_missing.coverage == (Coverage("missing_measure", 1),)
    social = _comp(COMP_SOCIAL, "social0", "activity_code", "indicator")
    whole = {
        "year": "2018",
        "activity_code": 410.0,
        "main_economic_activity": "invented",
        "lnsht_lqtsdy_lry_ysy": "ملصق",
        "nationality": "Qataris",
        "ljnsy": "قطريون",
        "indicator": "Number of Employees",
        "lbyn": "عدد",
        "value": 4,
    }
    assert _parse(social, [whole], tmp_path).rows[0]["activity_key"] == "410"
    fraction = dict(whole)
    fraction["activity_code"] = 1.5
    with pytest.raises(AdditionError) as coded:
        _parse(social, [fraction], tmp_path)
    assert coded.value.name == "category_unlisted"
    flag = dict(whole)
    flag["activity_code"] = True
    with pytest.raises(AdditionError) as boolean:
        _parse(social, [flag], tmp_path)
    assert boolean.value.name == "category_unlisted"


def test_a_bad_review_map_stops(tmp_path: Path) -> None:
    """A review file or an in-memory map that is not the closed shape stops."""
    entry = _labour(EMPLOYED, "employed")
    row = [_gender_row("2022", 4)]
    cross = _cross(tmp_path)
    empty = tmp_path / "empty-review"
    empty.mkdir()
    with pytest.raises(AdditionError) as missing_file:
        PARSERS["lf_muni_sex"](entry, row, RECEIPT, {}, {**cross, "review": empty})
    assert missing_file.value.name == "field_map_unreadable"
    with pytest.raises(AdditionError) as not_path:
        PARSERS["lf_muni_sex"](entry, row, RECEIPT, {}, {**cross, "review": "nope"})
    assert not_path.value.name == "field_map_unreadable"
    listed = tmp_path / "listed-review"
    listed.mkdir()
    (listed / "additions_splits.yaml").write_text("[]\n", encoding="utf-8")
    with pytest.raises(AdditionError) as not_dict:
        PARSERS["lf_muni_sex"](entry, row, RECEIPT, {}, {**cross, "review": listed})
    assert not_dict.value.name == "field_map_unreadable"
    spec = yaml.safe_load(
        (REVIEW / "additions_splits.yaml").read_text(encoding="utf-8")
    )
    assert isinstance(spec, dict)

    def _run(changed: dict[str, object]) -> str:
        with pytest.raises(AdditionError) as caught:
            PARSERS["lf_muni_sex"](entry, row, RECEIPT, changed, cross)
        return caught.value.name

    broken_vocab = deepcopy(spec)
    broken_vocab["vocab"] = []
    assert _run(broken_vocab) == "field_map_unreadable"
    broken_role = deepcopy(spec)
    broken_role["roles"][entry.key] = "nope"
    assert _run(broken_role) == "field_map_unreadable"
    broken_sex = deepcopy(spec)
    broken_sex["roles"][entry.key]["sex"] = 1
    assert _run(broken_sex) == "field_map_unreadable"
    broken_measure = deepcopy(spec)
    broken_measure["roles"][entry.key]["measure"] = None
    assert _run(broken_measure) == "field_map_unreadable"
    broken_flag = deepcopy(spec)
    broken_flag["roles"][entry.key]["integral"] = "yes"
    assert _run(broken_flag) == "field_map_unreadable"
    broken_map = deepcopy(spec)
    broken_map["vocab"]["sex"] = ["Females"]
    assert _run(broken_map) == "field_map_unreadable"
    broken_pair = deepcopy(spec)
    broken_pair["vocab"]["sex"] = {"Females": 1}
    assert _run(broken_pair) == "field_map_unreadable"
    narrowed = deepcopy(spec)
    del narrowed["vocab"]["sex"]["Females"]
    assert _run(narrowed) == "category_unlisted"
    population = _pop()
    ages = deepcopy(spec)
    ages["vocab"]["ages_population"] = [1]
    with pytest.raises(AdditionError) as age_list:
        PARSERS["pop_muni_age_sex"](
            population,
            [
                {
                    "years": "2016",
                    "fy_t_l_mr_blsnwt": "1 - 4",
                    "age_groups_in_years": "1 - 4",
                    "lbldy": "حي مخترع",
                    "municipality": "North Ward",
                    "value": 6,
                    "geo_point": None,
                    "geo_shape": None,
                }
            ],
            RECEIPT,
            ages,
            cross,
        )
    assert age_list.value.name == "field_map_unreadable"


def test_parsers_are_registered_by_source_id() -> None:
    """The build finds this pass by the PARSERS export, keyed by source_id."""
    assert set(PARSERS) == {
        "lf_muni_sex",
        "pop_muni_age_sex",
        "active_sex_age_act",
        "active_nat_occ_act",
        "comp_nat_act",
        "students_muni",
        "visitors_markets",
    }
    found = parsers()
    assert found["students_muni"] is PARSERS["students_muni"]


def _parse(entry: Entry, raw: list[dict[str, object]], tmp_path: Path) -> FamilyParse:
    parser = PARSERS[entry.source_id]
    return parser(entry, raw, RECEIPT, {}, _cross(tmp_path))


def _cross(tmp_path: Path) -> dict[str, object]:
    frame = tmp_path / "frame"
    frame.mkdir(exist_ok=True)
    (frame / "municipality_names.csv").write_text(
        "name,municipality_code\n"
        "North Ward,north_ward\n"
        "حي مخترع,north_ward\n"
        "South Ward,south_ward\n"
        "حي آخر,south_ward\n",
        encoding="utf-8",
    )
    return {"frame": frame, "review": REVIEW, "venues": ()}


def _line(
    source_key: str, period: str, publisher: str = "National Planning Council"
) -> dict[str, str]:
    return {
        "source_key": source_key,
        "publisher": publisher,
        "licence_id": "CC-BY-4.0",
        "licence_basis": "dataset",
        "retrieved_utc": "2026-01-02T03:04:05Z",
        "sha256": "abc123def",
        "period": period,
        "method": METHOD,
    }


def _entry(**overrides: object) -> Entry:
    values: dict[str, object] = {
        "key": f"lf_muni_sex/{EMPLOYED}",
        "source_id": "lf_muni_sex",
        "slug": EMPLOYED,
        "kind": "portal_dataset",
        "title_en": "invented labour",
        "publisher": "National Planning Council",
        "licence_id": "CC-BY-4.0",
        "licence_basis": "dataset",
        "decision_record": "",
        "fetch_host": "www.data.gov.qa",
        "url": "https://www.data.gov.qa/api/explore/v2.1/catalog/datasets/invented/exports/json",
        "terms_url": "",
        "nightly_live_fetch": False,
        "public_splits": ("sex",),
        "commit_allowed": False,
        "release_tables": ("pub_labour_sex_municipality",),
        "caveat_keys": (),
        "columns": (
            ("year", "string"),
            ("municipality", "string"),
            ("lbldy", "string"),
            ("gender", "string"),
            ("ljns", "string"),
            ("number", "integer"),
        ),
        "row_count_min": 1,
        "row_count_max": 1,
        "period_first": "2020",
        "period_last": "2025",
        "period_field": "sit=row;form=year_text;field=year",
        "reconciliation": "none",
        "skip_reason": "",
        "extension": "json",
        "landing_url": "https://www.data.gov.qa/explore/dataset/invented/",
        "licence_url": "https://www.data.gov.qa/pages/license/annexes",
    }
    values.update(overrides)
    return _entry_from(values)


def _replace_period(entry: Entry, period_field: str) -> Entry:
    from dataclasses import replace

    return replace(entry, period_field=period_field)


def _labour(slug: str, indicator: str, form: str = "year_text") -> Entry:
    return _entry(
        key=f"lf_muni_sex/{slug}",
        slug=slug,
        period_field=f"sit=row;form={form};field=year",
    )


def _population_labour(slug: str, sex: str) -> Entry:
    return _entry(
        key=f"lf_muni_sex/{slug}",
        slug=slug,
        columns=(
            ("year", "string"),
            ("municipality", "string"),
            ("lbldy", "string"),
            ("indicator", "string"),
            ("lmw_shr", "string"),
            ("count", "integer"),
        ),
    )


def _gender_row(year: str, number: object) -> dict[str, object]:
    return {
        "year": year,
        "municipality": "North Ward",
        "lbldy": "حي مخترع",
        "gender": "Females",
        "ljns": "اناث",
        "number": number,
    }


def _indicator_row(year: str, indicator: str, count: int) -> dict[str, object]:
    return {
        "year": year,
        "municipality": "North Ward",
        "lbldy": "حي مخترع",
        "indicator": indicator,
        "lmw_shr": "مؤشر",
        "count": count,
    }


def _population_age_sex_row(entry: Entry) -> dict[str, object]:
    invented: dict[str, object] = {
        "years": "2016",
        "fy_t_l_mr_blsnwt": "1 - 4",
        "age_groups_in_years": "1 - 4",
        "lbldy": "حي مخترع",
        "municipality": "North Ward",
        "value": 6,
    }
    row: dict[str, object] = {}
    for name, kind in entry.columns:
        if name in invented:
            row[name] = invented[name]
            continue
        if kind == "object":
            row[name] = None
            continue
        raise AssertionError(name)
    return row


def _pop() -> Entry:
    return _entry(
        key=f"pop_muni_age_sex/{POP_F}",
        source_id="pop_muni_age_sex",
        slug=POP_F,
        release_tables=("pub_population_age_sex",),
        columns=(
            ("years", "string"),
            ("fy_t_l_mr_blsnwt", "string"),
            ("age_groups_in_years", "string"),
            ("lbldy", "string"),
            ("municipality", "string"),
            ("value", "number"),
            ("geo_point", "object"),
            ("geo_shape", "object"),
        ),
        period_field="sit=row;form=year_text;field=years",
        period_first="2014",
        period_last="2023",
    )


def _active_sex() -> Entry:
    return _entry(
        key=f"active_sex_age_act/{ACTIVE_F}",
        source_id="active_sex_age_act",
        slug=ACTIVE_F,
        release_tables=("pub_active_sex_age",),
        columns=(
            ("year", "string"),
            ("age_group", "string"),
            ("economic_activity", "string"),
            ("lnsht_lqtsdy", "string"),
            ("total", "integer"),
        ),
        period_first="2017",
        period_last="2023",
    )


def _active_nat(slug: str, sex: str, nationality: str, measure: str) -> Entry:
    return _entry(
        key=f"active_nat_occ_act/{slug}",
        source_id="active_nat_occ_act",
        slug=slug,
        public_splits=("nationality", "sex"),
        release_tables=("pub_active_nationality_occupation",),
        columns=(
            ("year", "string"),
            ("economic_activity", "string"),
            ("lnsht_lqtsdy", "string"),
            ("occupation", "string"),
            ("lmhn", "string"),
            (measure, "integer"),
        ),
        period_first="2017",
        period_last="2024",
    )


def _nat_row(year: str, value: int | None, field: str = "total") -> dict[str, object]:
    return {
        "year": year,
        "economic_activity": "Education",
        "lnsht_lqtsdy": "تعليم",
        "occupation": "Clerks",
        "lmhn": "كتبة",
        field: value,
    }


def _comp(slug: str, table_code: str, code_field: str, indicator_field: str) -> Entry:
    columns = [
        ("year", "string"),
        (code_field, "string"),
        ("main_economic_activity", "string"),
        ("nationality", "string"),
        (indicator_field, "string"),
        ("value", "number"),
    ]
    if code_field == "code":
        columns[1:1] = []
        columns.extend(
            [
                ("main_economic_activity_ar", "string"),
                ("economic_activity", "string"),
                ("economic_activity_ar", "string"),
                ("labor_indicator_ar", "string"),
                ("nationality_ar", "string"),
            ]
        )
    else:
        columns.extend(
            [
                ("lnsht_lqtsdy_lry_ysy", "string"),
                ("ljnsy", "string"),
                ("lbyn", "string"),
            ]
        )
    return _entry(
        key=f"comp_nat_act/{slug}",
        source_id="comp_nat_act",
        slug=slug,
        public_splits=("nationality",),
        release_tables=("pub_compensation_nationality",),
        columns=tuple(columns),
        period_first="2015",
        period_last="2022",
    )


def _comp_row(
    year: str,
    code: str,
    nationality: str,
    indicator: str,
    value: int,
    code_field: str,
) -> dict[str, object]:
    row: dict[str, object] = {
        "year": year,
        "main_economic_activity": "B Mining and quarrying",
        "nationality": nationality,
        "value": value,
        code_field: code,
    }
    if code_field == "code":
        row.update(
            {
                "main_economic_activity_ar": "تعدين_x000D_",
                "economic_activity": "quarrying",
                "economic_activity_ar": "محاجر",
                "labor_indicator": indicator,
                "labor_indicator_ar": "عدد",
                "nationality_ar": "قطريون",
            }
        )
    return row


def _students() -> Entry:
    return _entry(
        key=f"students_muni/{STUDENTS}",
        source_id="students_muni",
        slug=STUDENTS,
        publisher="Ministry of Education and Higher Education",
        public_splits=("sex", "nationality"),
        release_tables=("pub_students",),
        columns=(
            ("year", "string"),
            ("municipality", "string"),
            ("lbldy", "string"),
            ("level_of_education", "string"),
            ("lmrhl_lt_lymy", "string"),
            ("type_of_education", "string"),
            ("nw_lt_lym", "string"),
            ("nationality", "string"),
            ("ljnsy", "string"),
            ("gender", "string"),
            ("ljns", "string"),
            ("number_of_students", "integer"),
        ),
        period_field="sit=row;form=school_year;field=year",
        period_first="2020-2021",
        period_last="2025-2026",
    )


def _hotel() -> Entry:
    return _entry(
        key=f"visitors_markets/{HOTEL}",
        source_id="visitors_markets",
        slug=HOTEL,
        public_splits=("nationality",),
        release_tables=("pub_visitor_markets",),
        columns=(
            ("year", "string"),
            ("nationality", "string"),
            ("ljnsy", "string"),
            ("hotel_rating", "string"),
            ("drj_lfndq", "string"),
            ("metric", "string"),
            ("lmqys", "string"),
            ("number", "number"),
        ),
        period_first="2020",
        period_last="2022",
    )


def _wide(slug: str, dimension: str, arabic: str) -> Entry:
    columns = [(dimension, "string"), (arabic, "string")]
    for month in (
        "june_2024",
        "july_2024",
        "august_2024",
        "september_2024",
        "october_2024",
        "november_2024",
    ):
        columns.append((month, "number"))
    return _entry(
        key=f"visitors_markets/{slug}",
        source_id="visitors_markets",
        slug=slug,
        public_splits=("nationality",),
        release_tables=("pub_visitor_markets",),
        columns=tuple(columns),
        period_field="sit=columns;form=month_name_year",
        period_first="2024-06",
        period_last="2024-11",
    )


def test_a_missing_broken_or_non_utf8_splits_review_stops(tmp_path: Path) -> None:
    """A review file that cannot be opened, decoded or parsed stops by name."""
    entry = _labour(EMPLOYED, "employed")
    row = [_gender_row("2022", 4)]
    cross = _cross(tmp_path)
    missing = tmp_path / "missing"
    missing.mkdir()
    with pytest.raises(AdditionError) as absent:
        PARSERS["lf_muni_sex"](entry, row, RECEIPT, {}, {**cross, "review": missing})
    assert absent.value.name == "field_map_unreadable"
    syntax = tmp_path / "syntax"
    syntax.mkdir()
    (syntax / "additions_splits.yaml").write_text("roles: [\n", encoding="utf-8")
    with pytest.raises(AdditionError) as broken:
        PARSERS["lf_muni_sex"](entry, row, RECEIPT, {}, {**cross, "review": syntax})
    assert broken.value.name == "field_map_unreadable"
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "additions_splits.yaml").write_bytes(b"\xff\xfe not utf-8")
    with pytest.raises(AdditionError) as decoded:
        PARSERS["lf_muni_sex"](entry, row, RECEIPT, {}, {**cross, "review": raw})
    assert decoded.value.name == "field_map_unreadable"


def _trends() -> Entry:
    return _entry(
        key=f"visitors_markets/{TRENDS}",
        source_id="visitors_markets",
        slug=TRENDS,
        publisher="Qatar Tourism",
        public_splits=("nationality",),
        release_tables=("pub_visitor_markets",),
        columns=(
            ("year", "string"),
            ("mode_of_transportation", "string"),
            ("wsyl_lnql", "string"),
            ("arrivals", "integer"),
        ),
        period_first="2019",
        period_last="2025",
    )


def _entry_from(values: dict[str, object]) -> Entry:
    """Build one entry from a fixture map, narrowing each field to its exact type."""
    return Entry(
        key=_map_text(values, "key"),
        source_id=_map_text(values, "source_id"),
        slug=_map_text(values, "slug"),
        kind=_map_text(values, "kind"),
        title_en=_map_text(values, "title_en"),
        publisher=_map_text(values, "publisher"),
        licence_id=_map_text(values, "licence_id"),
        licence_basis=_map_text(values, "licence_basis"),
        decision_record=_map_text(values, "decision_record"),
        fetch_host=_map_text(values, "fetch_host"),
        url=_map_text(values, "url"),
        terms_url=_map_text(values, "terms_url"),
        terms_words="invented terms words for a test",
        terms_read_on="2026-11-14",
        nightly_live_fetch=_map_flag(values, "nightly_live_fetch"),
        public_splits=_map_texts(values, "public_splits"),
        commit_allowed=_map_flag(values, "commit_allowed"),
        release_tables=_map_texts(values, "release_tables"),
        caveat_keys=_map_texts(values, "caveat_keys"),
        columns=_map_columns(values, "columns"),
        row_count_min=_map_count(values, "row_count_min"),
        row_count_max=_map_count(values, "row_count_max"),
        period_first=_map_text(values, "period_first"),
        period_last=_map_text(values, "period_last"),
        period_field=_map_text(values, "period_field"),
        reconciliation=_map_text(values, "reconciliation"),
        skip_reason=_map_text(values, "skip_reason"),
        extension=_map_text(values, "extension"),
        landing_url=_map_text(values, "landing_url"),
        licence_url=_map_text(values, "licence_url"),
    )


def _map_text(values: dict[str, object], name: str) -> str:
    value = values[name]
    if isinstance(value, str):
        return value
    raise AssertionError(name)


def _map_flag(values: dict[str, object], name: str) -> bool:
    value = values[name]
    if isinstance(value, bool):
        return value
    raise AssertionError(name)


def _map_texts(values: dict[str, object], name: str) -> tuple[str, ...]:
    value = values[name]
    if isinstance(value, tuple) and all(isinstance(item, str) for item in value):
        return value
    raise AssertionError(name)


def _map_columns(values: dict[str, object], name: str) -> tuple[tuple[str, str], ...]:
    value = values[name]
    if isinstance(value, tuple) and all(
        isinstance(pair, tuple)
        and len(pair) == 2
        and isinstance(pair[0], str)
        and isinstance(pair[1], str)
        for pair in value
    ):
        return value
    raise AssertionError(name)


def _map_count(values: dict[str, object], name: str) -> int | None:
    value = values[name]
    if value is None:
        return None
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    raise AssertionError(name)
