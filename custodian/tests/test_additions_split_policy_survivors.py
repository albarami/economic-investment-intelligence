"""Pins admission and reason together, and the branches the first campaign left alive."""

from __future__ import annotations

import locale

import pytest

from eii_custodian.publicdata.additions import split_policy
from eii_custodian.publicdata.additions.split_policy import (
    ColumnSpec,
    TableSpec,
    UseRequest,
    Verdict,
    _contracts_text,
    _field_tables,
    _forbidden_value,
    _names_sex_or_gender,
    validate_split_use,
    validate_table_dimensions,
    workspace_descriptors,
)

_PRESENCE = (
    "observation_start",
    "observation_end",
    "cell",
    "day_type",
    "summer",
    "hour",
    "split_kind",
    "split_value",
    "count",
    "panel_devices",
)
_WINDOW = (
    "Table `legal_entity`\n"
    "| `before_field` |\n"
    "## 6. Source contracts\n"
    "Table `not_a_feed`\n"
    "| `other` |\n"
    "Table `residence`\n"
    "| `street` |\n"
    "## 7. The release contract\n"
    "Table `salary_record`\n"
    "| `between_field` |\n"
    "## 6. Source contracts\n"
    "Table `employment_spell`\n"
    "| `late_field` |\n"
    "## 7. The release contract\n"
    "Table `establishment`\n"
    "| `after_field` |\n"
)


def _expect(verdict: Verdict, admitted: bool, reason: str) -> None:
    assert verdict == Verdict(admitted, reason)


def _use(
    *,
    table: str = "pub_population_age_sex",
    consumer: str = "public_display",
    geography: str = "source",
    categories: str = "source",
    lineage: str = "public",
    join_to: str = "none",
    segments: str = "none",
    person_key: bool = False,
    device_key: bool = False,
    trip_key: bool = False,
    combines_protected: bool = False,
    apportions: bool = False,
    reserved_use: str = "",
    anchor: str = "",
    summed_over_source_categories: bool = False,
) -> UseRequest:
    return UseRequest(
        table=table,
        source_splits=(("pop_muni_age_sex/females", ("sex",)),),
        consumer=consumer,
        geography=geography,
        categories=categories,
        lineage=lineage,
        join_to=join_to,
        segments=segments,
        person_key=person_key,
        device_key=device_key,
        trip_key=trip_key,
        combines_protected=combines_protected,
        apportions=apportions,
        reserved_use=reserved_use,
        anchor=anchor,
        summed_over_source_categories=summed_over_source_categories,
    )


def _grid(**overrides: object) -> UseRequest:
    values: dict[str, object] = {
        "table": "pub_pop_agesex_grid",
        "geography": "area_shape",
        "reserved_use": "grid_whole_cells",
    }
    values.update(overrides)
    return _use(
        table=str(values["table"]),
        consumer=str(values.get("consumer", "public_display")),
        geography=str(values["geography"]),
        categories=str(values.get("categories", "source")),
        lineage=str(values.get("lineage", "public")),
        join_to=str(values.get("join_to", "none")),
        segments=str(values.get("segments", "none")),
        person_key=bool(values.get("person_key", False)),
        device_key=bool(values.get("device_key", False)),
        trip_key=bool(values.get("trip_key", False)),
        combines_protected=bool(values.get("combines_protected", False)),
        apportions=bool(values.get("apportions", False)),
        reserved_use=str(values["reserved_use"]),
    )


def test_an_unlisted_kind_is_refused_with_its_reason() -> None:
    """A kind outside the three closed families is not admitted."""
    table = TableSpec("notes", "notebook", (ColumnSpec("period"),))
    _expect(validate_table_dimensions(table), False, "kind_unlisted")


def test_record_verdicts_keep_admission_with_the_reason() -> None:
    """Each record refusal and the clean admission carry the boolean, not only the word."""
    clean = TableSpec(
        "employment_spell",
        "worker_source",
        (ColumnSpec("occupation_code"),),
    )
    sex = TableSpec(
        "employment_spell",
        "worker_source",
        (ColumnSpec("sex"),),
    )
    gender_value = TableSpec(
        "employment_spell",
        "worker_source",
        (ColumnSpec("nationality_group", ("female",)),),
    )
    visitors = TableSpec(
        "employment_spell",
        "worker_source",
        (ColumnSpec("nationality_group", ("international_visitors",)),),
    )
    other = TableSpec(
        "employment_spell",
        "worker_source",
        (ColumnSpec("nationality_group", ("other_group",)),),
    )
    closed = TableSpec(
        "residence",
        "residence_source",
        (ColumnSpec("housing_class", ("note_male",)),),
    )
    _expect(validate_table_dimensions(clean), True, "admitted")
    _expect(validate_table_dimensions(sex), False, "forbidden_dimension")
    _expect(validate_table_dimensions(gender_value), False, "forbidden_closed_value")
    _expect(
        validate_table_dimensions(visitors), False, "international_visitors_on_worker"
    )
    _expect(validate_table_dimensions(other), False, "forbidden_closed_value")
    _expect(validate_table_dimensions(closed), False, "forbidden_closed_value")


def test_a_later_forbidden_column_is_still_refused() -> None:
    """An allowed nationality column does not stop the check of the next column."""
    table = TableSpec(
        "employment_spell",
        "worker_source",
        (
            ColumnSpec("nationality_group", ("qatari",)),
            ColumnSpec("sex"),
        ),
    )
    _expect(validate_table_dimensions(table), False, "forbidden_dimension")


def test_movement_verdicts_keep_admission_with_the_reason() -> None:
    """Movement admission, a repeated column and a sex column each keep their boolean."""
    gender = TableSpec(
        "presence_split",
        "movement_split",
        (ColumnSpec("gender"),),
    )
    sex = TableSpec(
        "presence_split",
        "movement_split",
        (ColumnSpec("sex"),),
    )
    repeated = TableSpec(
        "presence_split_hourly",
        "movement_split",
        tuple(ColumnSpec(name) for name in (*_PRESENCE, "hour")),
    )
    _expect(validate_table_dimensions(gender), True, "admitted")
    _expect(validate_table_dimensions(sex), False, "forbidden_dimension")
    _expect(validate_table_dimensions(repeated), False, "movement_column_unlisted")


def test_public_verdicts_keep_admission_with_the_reason() -> None:
    """Public columns and breakdown dimensions keep admission beside the reason."""
    declared = TableSpec(
        "pub_labour_sex_municipality",
        "public_split",
        (ColumnSpec("sex"),),
        source_splits=(("lf_muni_sex/female", ("sex",)),),
    )
    unlisted = TableSpec(
        "pub_place",
        "public_split",
        (ColumnSpec("sex"),),
        source_splits=(("somewhere", ("sex",)),),
    )
    undeclared = TableSpec(
        "pub_labour_sex_municipality",
        "public_split",
        (ColumnSpec("sex"),),
        source_splits=(("lf_muni_sex/female", ()),),
    )
    gender = TableSpec(
        "pub_labour_sex_municipality",
        "public_split",
        (ColumnSpec("gender"),),
        source_splits=(("lf_muni_sex/female", ("sex",)),),
    )
    nationality = TableSpec(
        "pub_visitor_markets",
        "public_split",
        (),
        breakdown_dimensions=("nationality_group",),
        source_splits=(("visitors_markets/hotel", ("nationality",)),),
    )
    dimension = TableSpec(
        "pub_visitor_markets",
        "public_split",
        (),
        breakdown_dimensions=("gender",),
        source_splits=(("visitors_markets/hotel", ("nationality",)),),
    )
    _expect(validate_table_dimensions(declared), True, "admitted")
    _expect(validate_table_dimensions(unlisted), False, "split_table_unlisted")
    _expect(validate_table_dimensions(undeclared), False, "split_undeclared")
    _expect(validate_table_dimensions(gender), False, "forbidden_dimension")
    _expect(validate_table_dimensions(nationality), True, "admitted")
    _expect(validate_table_dimensions(dimension), False, "forbidden_dimension")


def test_a_later_forbidden_dimension_is_still_refused() -> None:
    """A declared nationality breakdown does not stop the next dimension."""
    table = TableSpec(
        "pub_visitor_markets",
        "public_split",
        (),
        breakdown_dimensions=("nationality_group", "gender"),
        source_splits=(("visitors_markets/hotel", ("nationality",)),),
    )
    _expect(validate_table_dimensions(table), False, "forbidden_dimension")


def test_an_unreadable_name_keeps_its_boolean() -> None:
    """A name outside ASCII snake case is refused, not admitted under the same word."""
    table = TableSpec(
        "employment_spell",
        "worker_source",
        (ColumnSpec("worker-sex"),),
    )
    _expect(validate_table_dimensions(table), False, "name_unreadable")


def test_use_verdicts_keep_admission_with_the_reason() -> None:
    """Each public-use refusal and the admitted display carry the boolean."""
    cases = (
        (_use(), True, "admitted_public"),
        (_use(consumer="worker_record"), False, "worker_record"),
        (_use(consumer="joining_key"), False, "joining_key"),
        (_use(consumer="other"), False, "consumer_unlisted"),
        (_use(join_to="worker"), False, "join_worker"),
        (_use(join_to="residence"), False, "join_residence"),
        (_use(join_to="company"), False, "join_company"),
        (_use(join_to="other"), False, "join_worker"),
        (_use(segments="worker"), False, "segment_worker"),
        (_use(segments="residence"), False, "segment_residence"),
        (_use(segments="company"), False, "segment_company"),
        (_use(segments="other"), False, "segment_worker"),
        (_use(person_key=True), False, "person_key"),
        (_use(device_key=True), False, "device_key"),
        (_use(trip_key=True), False, "trip_key"),
        (_use(combines_protected=True), False, "protected_composite"),
        (_use(apportions=True), False, "tabulated_apportionment"),
        (_use(geography="drawn_area"), False, "invented_geography"),
        (_use(categories="merged"), False, "merged_category"),
        (_use(categories="renamed"), False, "renamed_category"),
        (_use(categories="summed_unpublished"), False, "unpublished_total"),
        (_use(categories="invented"), False, "invented_category"),
        (_use(lineage="mixed"), False, "mixed_lineage"),
    )
    for request, admitted, reason in cases:
        _expect(validate_split_use(request), admitted, reason)


def test_anchor_verdicts_keep_admission_with_the_reason() -> None:
    """A cited summed anchor is admitted. An unknown or unsummed anchor is refused."""
    cited = _use(
        consumer="movement_anchor",
        anchor="mob.split_anchor.population_age_sex",
        summed_over_source_categories=True,
    )
    arrivals = _use(
        consumer="movement_anchor",
        anchor="mob.split_anchor.visitor_arrivals",
        summed_over_source_categories=True,
    )
    unknown = _use(
        consumer="movement_anchor",
        anchor="mob.split_anchor.other",
        summed_over_source_categories=True,
    )
    bare = _use(
        consumer="movement_anchor",
        anchor="mob.split_anchor.population_age_sex",
        summed_over_source_categories=False,
    )
    _expect(validate_split_use(cited), True, "admitted_movement_anchor")
    _expect(validate_split_use(arrivals), True, "admitted_movement_anchor")
    _expect(validate_split_use(unknown), False, "anchor_uncited")
    _expect(validate_split_use(bare), False, "anchor_not_summed")


def test_reserved_verdicts_keep_admission_with_the_reason() -> None:
    """The grid sum and each reserved refusal carry the boolean."""
    cases = (
        (_grid(), True, "reserved_grid_cells"),
        (_grid(reserved_use="other"), False, "reserved_unknown"),
        (_grid(consumer="worker_record"), False, "worker_record"),
        (_grid(consumer="joining_key"), False, "joining_key"),
        (_grid(consumer="other"), False, "consumer_unlisted"),
        (_grid(geography="source"), False, "invented_geography"),
        (_grid(categories="merged"), False, "merged_category"),
        (_grid(categories="renamed"), False, "renamed_category"),
        (_grid(categories="summed_unpublished"), False, "unpublished_total"),
        (_grid(categories="invented"), False, "invented_category"),
        (_grid(apportions=True), False, "tabulated_apportionment"),
        (_grid(table="pub_population_age_sex"), False, "reserved_wrong_table"),
        (_grid(combines_protected=True), False, "protected_composite"),
        (_grid(join_to="worker"), False, "join_worker"),
        (_grid(segments="worker"), False, "join_worker"),
        (_grid(person_key=True), False, "person_key"),
        (_grid(device_key=True), False, "person_key"),
        (_grid(trip_key=True), False, "person_key"),
        (_grid(lineage="mixed"), False, "mixed_lineage"),
    )
    for request, admitted, reason in cases:
        _expect(validate_split_use(request), admitted, reason)


def test_closed_values_split_on_underscore_and_hyphen() -> None:
    """A sex or nationality word after either separator is still that word."""
    assert _names_sex_or_gender("note_male") is True
    assert _names_sex_or_gender("note-male") is True
    assert _names_sex_or_gender("male") is True
    assert _forbidden_value("note_male") is True
    assert _forbidden_value("note-male") is True
    assert _forbidden_value("note_qatari") is True
    assert _forbidden_value("note-qatari") is True


def test_a_field_cell_keeps_every_backtick_name() -> None:
    """The first markdown cell yields every backtick name, including a capital."""
    section = "Table `salary_record`\n| `Wage` `bonus` |\n"
    assert _field_tables(section) == (("salary_record", ("Wage", "bonus")),)


def test_the_contract_window_keeps_known_tables_after_an_unknown_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The first section-6 heading through the first section-7 heading is the window."""
    monkeypatch.setattr(split_policy, "_contracts_text", lambda: _WINDOW)
    found = {
        item.name: tuple(column.name for column in item.columns)
        for item in workspace_descriptors()
    }
    assert found["residence"] == ("street",)
    assert "legal_entity" not in found
    assert "not_a_feed" not in found
    assert "salary_record" not in found
    assert "employment_spell" not in found
    assert "establishment" not in found
    assert "presence_split_hourly" in found
    assert "od_split_hourly" in found


def test_contracts_text_stays_utf8_under_an_ascii_locale() -> None:
    """The contracts file is decoded as UTF-8 when the process locale is ASCII."""
    previous = locale.setlocale(locale.LC_ALL)
    try:
        locale.setlocale(locale.LC_ALL, "C")
        text = _contracts_text()
    finally:
        locale.setlocale(locale.LC_ALL, previous)
    assert "\u2014" in text
    assert "## 6. Source contracts" in text
