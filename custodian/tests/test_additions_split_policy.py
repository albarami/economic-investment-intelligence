"""Closed checks for Public split columns and for what may read them."""

from __future__ import annotations

from pathlib import Path

import pytest

from eii_custodian.publicdata.additions.split_policy import (
    PUBLIC_SPLIT_TABLES,
    ColumnSpec,
    TableSpec,
    UseRequest,
    _repository_root,
    validate_split_use,
    validate_table_dimensions,
    workspace_descriptors,
)

PUBLIC = (
    "pub_wage_table",
    "pub_labour_sex_municipality",
    "pub_population_age_sex",
    "pub_active_sex_age",
    "pub_active_nationality_occupation",
    "pub_compensation_nationality",
    "pub_students",
    "pub_visitor_markets",
    "pub_pop_agesex_grid",
)


def test_workspace_contracts_admit_only_the_named_nationality_fields() -> None:
    """Section 6 tables are read from the document. The two nationality fields pass."""
    found = {item.name: item for item in workspace_descriptors()}
    spell = found["employment_spell"]
    establishment = found["establishment"]
    assert spell.kind == "worker_source"
    assert "nationality_group" in {column.name for column in spell.columns}
    assert establishment.kind == "company_source"
    assert "establishment_nationality" in {
        column.name for column in establishment.columns
    }
    assert validate_table_dimensions(spell).reason == "admitted"
    assert validate_table_dimensions(establishment).reason == "admitted"
    assert validate_table_dimensions(found["residence"]).reason == "admitted"
    assert validate_table_dimensions(found["salary_record"]).reason == "admitted"
    assert found["presence_hourly"].kind == "mobility_feed"
    assert found["presence_split_hourly"].kind == "movement_split"
    assert (
        validate_table_dimensions(found["presence_split_hourly"]).reason == "admitted"
    )
    assert validate_table_dimensions(found["od_split_hourly"]).reason == "admitted"
    assert "resident_pay" not in found
    assert "worker_generator" not in found
    assert set(found) == {
        "legal_entity",
        "establishment",
        "establishment_activity",
        "employment_spell",
        "salary_file",
        "salary_record",
        "residence",
        "presence_hourly",
        "od_hourly",
        "presence_split_hourly",
        "od_split_hourly",
    }


def test_a_sex_column_on_a_worker_table_fails_and_the_clean_table_passes() -> None:
    """A forbidden word in a column name is refused. A table without one is kept."""
    clean = TableSpec(
        "employment_spell",
        "worker_source",
        (ColumnSpec("occupation_code"), ColumnSpec("employer_sector")),
    )
    assert validate_table_dimensions(clean).reason == "admitted"
    planted = TableSpec(
        "employment_spell",
        "worker_source",
        (ColumnSpec("occupation_code"), ColumnSpec("sex")),
    )
    assert validate_table_dimensions(planted).reason == "forbidden_dimension"
    gender = TableSpec("residence", "residence_source", (ColumnSpec("gender"),))
    assert validate_table_dimensions(gender).reason == "forbidden_dimension"
    age = TableSpec(
        "salary_record",
        "worker_source",
        (ColumnSpec("age_band"),),
    )
    assert validate_table_dimensions(age).reason == "forbidden_dimension"


def test_a_closed_sex_or_nationality_value_fails_off_the_exceptions() -> None:
    """A closed list is checked as values, not as prose. The movement list may hold them."""
    planted = TableSpec(
        "residence",
        "residence_source",
        (ColumnSpec("housing_class", ("family_housing", "female")),),
    )
    assert validate_table_dimensions(planted).reason == "forbidden_closed_value"
    clean = TableSpec(
        "residence",
        "residence_source",
        (ColumnSpec("housing_class", ("family_housing", "unknown")),),
    )
    assert validate_table_dimensions(clean).reason == "admitted"
    visitors = TableSpec(
        "employment_spell",
        "worker_source",
        (ColumnSpec("nationality_group", ("qatari", "international_visitors")),),
    )
    assert (
        validate_table_dimensions(visitors).reason == "international_visitors_on_worker"
    )
    allowed = TableSpec(
        "employment_spell",
        "worker_source",
        (ColumnSpec("nationality_group", ("qatari", "non_qatari")),),
    )
    assert validate_table_dimensions(allowed).reason == "admitted"
    company = TableSpec(
        "establishment",
        "company_source",
        (ColumnSpec("establishment_nationality", ("qatari",)),),
    )
    assert validate_table_dimensions(company).reason == "admitted"


def test_public_split_columns_need_the_listed_table_and_every_declaration() -> None:
    """Sex and nationality_group are admitted only on the named tables, and only when declared."""
    declared = TableSpec(
        "pub_labour_sex_municipality",
        "public_split",
        (ColumnSpec("sex"), ColumnSpec("age_group")),
        source_splits=(("lf_muni_sex/female", ("sex",)),),
    )
    assert validate_table_dimensions(declared).reason == "admitted"
    missing = TableSpec(
        "pub_labour_sex_municipality",
        "public_split",
        (ColumnSpec("sex"),),
        source_splits=(("lf_muni_sex/female", ()),),
    )
    assert validate_table_dimensions(missing).reason == "split_undeclared"
    unlisted = TableSpec(
        "pub_place",
        "public_split",
        (ColumnSpec("sex"),),
        source_splits=(("somewhere", ("sex",)),),
    )
    assert validate_table_dimensions(unlisted).reason == "split_table_unlisted"
    half = TableSpec(
        "pub_students",
        "public_split",
        (ColumnSpec("sex"), ColumnSpec("nationality_group")),
        source_splits=(("students_muni/one", ("sex",)),),
    )
    assert validate_table_dimensions(half).reason == "split_undeclared"
    both = TableSpec(
        "pub_visitor_markets",
        "public_split",
        (ColumnSpec("nationality_group"),),
        breakdown_dimensions=("hotel_rating",),
        source_splits=(
            ("visitors_markets/hotel", ("nationality",)),
            ("visitors_markets/mode", ("nationality",)),
        ),
    )
    assert validate_table_dimensions(both).reason == "admitted"
    breakdown = TableSpec(
        "pub_visitor_markets",
        "public_split",
        (),
        breakdown_dimensions=("sex",),
        source_splits=(("visitors_markets/hotel", ("nationality",)),),
    )
    assert validate_table_dimensions(breakdown).reason == "split_undeclared"
    gender = TableSpec(
        "pub_labour_sex_municipality",
        "public_split",
        (ColumnSpec("gender"),),
        source_splits=(("lf_muni_sex/female", ("sex",)),),
    )
    assert validate_table_dimensions(gender).reason == "forbidden_dimension"
    assert PUBLIC_SPLIT_TABLES == frozenset(PUBLIC)


def test_movement_gender_passes_and_a_worker_gender_fails() -> None:
    """DAT-169 admits gender on a movement split. The same column on a worker table fails."""
    movement = TableSpec(
        "presence_split",
        "movement_split",
        (ColumnSpec("gender"), ColumnSpec("split_kind")),
    )
    assert validate_table_dimensions(movement).reason == "admitted"
    worker = TableSpec("employment_spell", "worker_source", (ColumnSpec("gender"),))
    assert validate_table_dimensions(worker).reason == "forbidden_dimension"
    sex_on_movement = TableSpec(
        "flow_split",
        "movement_split",
        (ColumnSpec("sex"),),
    )
    assert validate_table_dimensions(sex_on_movement).reason == "forbidden_dimension"


def test_protected_and_generator_descriptors_refuse_a_planted_column() -> None:
    """Tables that are not in this workspace yet are still refused by an explicit descriptor."""
    protected = TableSpec("resident_pay", "protected_derived", (ColumnSpec("sex"),))
    assert validate_table_dimensions(protected).reason == "forbidden_dimension"
    protected_clean = TableSpec(
        "resident_pay",
        "protected_derived",
        (ColumnSpec("unit_id"), ColumnSpec("period")),
    )
    assert validate_table_dimensions(protected_clean).reason == "admitted"
    generated = TableSpec(
        "worker_generator",
        "generator_output",
        (ColumnSpec("nationality_group"),),
    )
    assert validate_table_dimensions(generated).reason == "forbidden_dimension"
    generated_clean = TableSpec(
        "worker_generator",
        "generator_output",
        (ColumnSpec("occupation_group"),),
    )
    assert validate_table_dimensions(generated_clean).reason == "admitted"


def test_public_display_on_the_source_geography_passes() -> None:
    """A Public fact on the source's own geography and categories is admitted."""
    assert validate_split_use(_public()).reason == "admitted_public"


def test_each_refused_use_fails_and_the_public_control_passes() -> None:
    """Every named refusal has one planted request and the public display beside it."""
    expected = {
        "join_to": {
            "worker": "join_worker",
            "residence": "join_residence",
            "company": "join_company",
        },
        "segments": {
            "worker": "segment_worker",
            "residence": "segment_residence",
            "company": "segment_company",
        },
    }
    for field, cases in expected.items():
        for value, reason in cases.items():
            assert validate_split_use(_public(**{field: value})).reason == reason
            assert validate_split_use(_public()).reason == "admitted_public"
    assert validate_split_use(_public(person_key=True)).reason == "person_key"
    assert validate_split_use(_public(device_key=True)).reason == "device_key"
    assert validate_split_use(_public(trip_key=True)).reason == "trip_key"
    assert validate_split_use(_public()).reason == "admitted_public"
    assert (
        validate_split_use(_public(combines_protected=True)).reason
        == "protected_composite"
    )
    assert (
        validate_split_use(_public(apportions=True)).reason == "tabulated_apportionment"
    )
    assert validate_split_use(_public(geography="drawn_area")).reason == (
        "invented_geography"
    )
    assert validate_split_use(_public(categories="merged")).reason == "merged_category"
    assert (
        validate_split_use(_public(categories="renamed")).reason == "renamed_category"
    )
    assert validate_split_use(_public(categories="summed_unpublished")).reason == (
        "unpublished_total"
    )
    assert validate_split_use(_public(categories="invented")).reason == (
        "invented_category"
    )
    assert validate_split_use(_public(lineage="mixed")).reason == "mixed_lineage"
    assert validate_split_use(_public(lineage="protected")).reason == "mixed_lineage"


def test_tst_209_anchor_passes_and_worker_and_joining_key_fail() -> None:
    """The movement-anchor case passes. The worker-record case and the joining-key case fail."""
    population = _anchor("mob.split_anchor.population_age_sex")
    arrivals = _anchor("mob.split_anchor.visitor_arrivals")
    assert validate_split_use(population).reason == "admitted_movement_anchor"
    assert validate_split_use(arrivals).reason == "admitted_movement_anchor"
    assert (
        validate_split_use(_public(consumer="worker_record")).reason == "worker_record"
    )
    assert validate_split_use(_public(consumer="joining_key")).reason == "joining_key"
    assert (
        validate_split_use(_anchor("mob.split_anchor.other")).reason == "anchor_uncited"
    )
    assert (
        validate_split_use(
            _anchor(
                "mob.split_anchor.population_age_sex",
                summed_over_source_categories=False,
            )
        ).reason
        == "anchor_not_summed"
    )


def test_whole_grid_cells_are_reserved_and_not_an_apportionment() -> None:
    """The grid sum is admitted as a reserved use. An apportioned tabulated figure is refused."""
    reserved = _public(
        table="pub_pop_agesex_grid",
        geography="area_shape",
        reserved_use="grid_whole_cells",
    )
    assert validate_split_use(reserved).reason == "reserved_grid_cells"
    apportioned = _public(
        table="pub_pop_agesex_grid",
        geography="area_shape",
        reserved_use="grid_whole_cells",
        apportions=True,
    )
    assert validate_split_use(apportioned).reason == "tabulated_apportionment"
    other = _public(
        table="pub_population_age_sex",
        geography="area_shape",
        reserved_use="grid_whole_cells",
    )
    assert validate_split_use(other).reason == "reserved_wrong_table"


def test_unlisted_consumers_and_reserved_flags_stop() -> None:
    """A use outside the closed consumers, joins and reserved flags is refused."""
    assert validate_split_use(_public(consumer="other")).reason == "consumer_unlisted"
    assert validate_split_use(_public(join_to="other")).reason == "join_worker"
    assert validate_split_use(_public(segments="other")).reason == "segment_worker"
    assert (
        validate_split_use(_public(reserved_use="other")).reason == "reserved_unknown"
    )
    reserved = {
        "table": "pub_pop_agesex_grid",
        "geography": "area_shape",
        "reserved_use": "grid_whole_cells",
    }
    assert (
        validate_split_use(_public(**reserved, combines_protected=True)).reason
        == "protected_composite"
    )
    assert (
        validate_split_use(_public(**reserved, join_to="worker")).reason
        == "join_worker"
    )
    assert (
        validate_split_use(_public(**reserved, person_key=True)).reason == "person_key"
    )
    assert (
        validate_split_use(_public(**reserved, lineage="mixed")).reason
        == "mixed_lineage"
    )
    joined = UseRequest(
        table="pub_population_age_sex",
        source_splits=(("pop_muni_age_sex/females", ("sex",)),),
        consumer="movement_anchor",
        geography="source",
        categories="source",
        lineage="public",
        join_to="worker",
        anchor="mob.split_anchor.population_age_sex",
        summed_over_source_categories=True,
    )
    assert validate_split_use(joined).reason == "join_worker"
    gendered = TableSpec(
        "pub_visitor_markets",
        "public_split",
        (ColumnSpec("nationality_group"), ColumnSpec("breakdown_key")),
        ("gender",),
        (("visitors_markets/hotel", ("nationality",)),),
    )
    assert validate_table_dimensions(gendered).reason == "forbidden_dimension"


def test_names_are_judged_without_regard_to_letter_case() -> None:
    """A capitalised sex or gender word is the same word as the lower-case rule."""
    gender = TableSpec(
        "employment_spell",
        "worker_source",
        (ColumnSpec("Gender"),),
    )
    assert validate_table_dimensions(gender).reason == "forbidden_dimension"
    unlisted = TableSpec(
        "pub_place",
        "public_split",
        (ColumnSpec("Sex"),),
        source_splits=(("somewhere", ("sex",)),),
    )
    assert validate_table_dimensions(unlisted).reason == "split_table_unlisted"
    undeclared = TableSpec(
        "pub_labour_sex_municipality",
        "public_split",
        (ColumnSpec("Sex"),),
    )
    assert validate_table_dimensions(undeclared).reason == "split_undeclared"
    movement = TableSpec(
        "presence_split",
        "movement_split",
        (ColumnSpec("SEX"),),
    )
    assert validate_table_dimensions(movement).reason == "forbidden_dimension"
    admitted_movement = TableSpec(
        "presence_split",
        "movement_split",
        (ColumnSpec("Gender"),),
    )
    assert validate_table_dimensions(admitted_movement).reason == "admitted"
    exception = TableSpec(
        "employment_spell",
        "worker_source",
        (ColumnSpec("Nationality_Group"),),
    )
    assert validate_table_dimensions(exception).reason == "admitted"
    dimension = TableSpec(
        "pub_place",
        "public_split",
        (),
        breakdown_dimensions=("Sex",),
        source_splits=(("somewhere", ("sex",)),),
    )
    assert validate_table_dimensions(dimension).reason == "split_table_unlisted"
    sex_column = TableSpec(
        "pub_labour_sex_municipality",
        "public_split",
        (ColumnSpec("Sex"),),
        source_splits=(("lf_muni_sex/female", ("nationality",)),),
    )
    assert validate_table_dimensions(sex_column).reason == "split_undeclared"
    sex_dimension = TableSpec(
        "pub_labour_sex_municipality",
        "public_split",
        (),
        breakdown_dimensions=("Sex",),
        source_splits=(("lf_muni_sex/female", ("nationality",)),),
    )
    assert validate_table_dimensions(sex_dimension).reason == "split_undeclared"


def test_reserved_grid_refuses_worker_use_and_other_categories() -> None:
    """A reserved grid sum still refuses a worker consumer and a changed category."""
    base = {
        "table": "pub_pop_agesex_grid",
        "geography": "area_shape",
        "reserved_use": "grid_whole_cells",
    }
    assert (
        validate_split_use(_public(**base, consumer="worker_record")).reason
        == "worker_record"
    )
    assert (
        validate_split_use(_public(**base, consumer="joining_key")).reason
        == "joining_key"
    )
    assert (
        validate_split_use(_public(**base, categories="merged")).reason
        == "merged_category"
    )
    assert (
        validate_split_use(_public(**base, categories="renamed")).reason
        == "renamed_category"
    )
    assert (
        validate_split_use(_public(**base, categories="summed_unpublished")).reason
        == "unpublished_total"
    )
    assert (
        validate_split_use(_public(**base, categories="invented")).reason
        == "invented_category"
    )
    assert validate_split_use(_public(**base)).reason == "reserved_grid_cells"


def test_nationality_exception_refuses_a_sex_or_gender_value() -> None:
    """Both spellings of the worker nationality field refuse a sex value. The allowed values pass."""
    allowed = TableSpec(
        "employment_spell",
        "worker_source",
        (ColumnSpec("nationality_group", ("qatari", "non_qatari")),),
    )
    assert validate_table_dimensions(allowed).reason == "admitted"
    for name in ("nationality_group", "Nationality_Group"):
        planted = TableSpec(
            "employment_spell",
            "worker_source",
            (ColumnSpec(name, ("female",)),),
        )
        assert validate_table_dimensions(planted).reason == "forbidden_closed_value"
    female_case = TableSpec(
        "employment_spell",
        "worker_source",
        (ColumnSpec("nationality_group", ("Female",)),),
    )
    assert validate_table_dimensions(female_case).reason == "forbidden_closed_value"


def test_reserved_grid_admits_only_public_display_on_a_drawn_area() -> None:
    """After the two named refusals, only public display on a drawn area is admitted."""
    base = {
        "table": "pub_pop_agesex_grid",
        "geography": "area_shape",
        "reserved_use": "grid_whole_cells",
    }
    assert validate_split_use(_public(**base)).reason == "reserved_grid_cells"
    for consumer in (
        "rank_criterion",
        "feature",
        "movement_anchor",
        "Worker_Record",
        "",
    ):
        assert (
            validate_split_use(_public(**base, consumer=consumer)).reason
            == "consumer_unlisted"
        )
    for geography in ("release_units", "user_scenario"):
        drawn = dict(base)
        drawn["geography"] = geography
        assert validate_split_use(_public(**drawn)).reason == "invented_geography"


def test_closed_values_are_compared_exactly() -> None:
    """White space, a zero-width character or a look-alike letter is not a closed value."""
    base = {
        "table": "pub_pop_agesex_grid",
        "geography": "area_shape",
        "reserved_use": "grid_whole_cells",
    }
    assert (
        validate_split_use(_public(**base, consumer="public_display ")).reason
        == "consumer_unlisted"
    )
    spaced_area = dict(base)
    spaced_area["geography"] = "area_shape "
    assert validate_split_use(_public(**spaced_area)).reason == "invented_geography"
    assert (
        validate_split_use(_public(**base, categories="source ")).reason
        == "invented_category"
    )
    assert (
        validate_split_use(_public(**base, categories="source\u200b")).reason
        == "invented_category"
    )
    lookalike = "s\u043eurce"
    assert (
        validate_split_use(_public(**base, categories=lookalike)).reason
        == "invented_category"
    )


def test_a_name_outside_ascii_snake_case_is_unreadable() -> None:
    """A name that is not ASCII letters, digits and underscores after case folding is refused."""
    full_width = TableSpec(
        "employment_spell",
        "worker_source",
        (ColumnSpec("\uff33ex"),),
    )
    assert validate_table_dimensions(full_width).reason == "name_unreadable"
    zero_width = TableSpec(
        "employment_spell",
        "worker_source",
        (ColumnSpec("sex\u200b"),),
    )
    assert validate_table_dimensions(zero_width).reason == "name_unreadable"
    hyphenated = TableSpec(
        "employment_spell",
        "worker_source",
        (ColumnSpec("worker-sex"),),
    )
    assert validate_table_dimensions(hyphenated).reason == "name_unreadable"
    camel = TableSpec(
        "employment_spell",
        "worker_source",
        (ColumnSpec("workerSex"),),
    )
    assert validate_table_dimensions(camel).reason == "forbidden_dimension"
    table = TableSpec("pub-place", "public_split", (ColumnSpec("period"),))
    assert validate_table_dimensions(table).reason == "name_unreadable"
    dimension = TableSpec(
        "pub_labour_sex_municipality",
        "public_split",
        (),
        breakdown_dimensions=("worker-sex",),
        source_splits=(("lf_muni_sex/female", ("sex",)),),
    )
    assert validate_table_dimensions(dimension).reason == "name_unreadable"


_PRESENCE_SPLIT_FIELDS = (
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
_OD_SPLIT_FIELDS = (
    "observation_start",
    "observation_end",
    "origin_cell",
    "destination_cell",
    "day_type",
    "summer",
    "hour",
    "split_kind",
    "split_value",
    "count",
    "panel_devices",
)


def test_movement_split_tables_admit_exactly_the_feed_columns() -> None:
    """The two movement split tables take the section 6.5 columns and no worker key."""
    found = {item.name: item for item in workspace_descriptors()}
    assert (
        tuple(column.name for column in found["presence_split_hourly"].columns)
        == _PRESENCE_SPLIT_FIELDS
    )
    assert (
        tuple(column.name for column in found["od_split_hourly"].columns)
        == _OD_SPLIT_FIELDS
    )
    extra = TableSpec(
        "presence_split_hourly",
        "movement_split",
        (
            *(ColumnSpec(name) for name in _PRESENCE_SPLIT_FIELDS),
            ColumnSpec("cell_worker_id"),
        ),
    )
    assert validate_table_dimensions(extra).reason == "movement_column_unlisted"


def _public(**overrides: object) -> UseRequest:
    values: dict[str, object] = {
        "table": "pub_population_age_sex",
        "source_splits": (("pop_muni_age_sex/females", ("sex",)),),
        "consumer": "public_display",
        "geography": "source",
        "categories": "source",
        "lineage": "public",
    }
    values.update(overrides)
    return UseRequest(**values)  # type: ignore[arg-type]


def _anchor(anchor: str, summed_over_source_categories: bool = True) -> UseRequest:
    return UseRequest(
        table="pub_population_age_sex",
        source_splits=(("pop_muni_age_sex/females", ("sex",)),),
        consumer="movement_anchor",
        geography="source",
        categories="source",
        lineage="public",
        anchor=anchor,
        summed_over_source_categories=summed_over_source_categories,
    )


_CHECKOUT_TAIL = (
    "custodian",
    "src",
    "eii_custodian",
    "publicdata",
    "additions",
    "split_policy.py",
)
_COPY_TAIL = (
    "custodian",
    "mutants",
    "src",
    "eii_custodian",
    "publicdata",
    "additions",
    "split_policy.py",
)
_MISSING_CONTRACTS = (
    "docs/03_DATA_CONTRACTS.md: no parent folder of the module "
    "holds it beside AGENTS.md"
)


def _plant(folder: Path, *, agents: bool, contracts: bool) -> None:
    """Write one invented line for each marker this folder is supposed to hold."""
    folder.mkdir(parents=True, exist_ok=True)
    if agents:
        (folder / "AGENTS.md").write_text("invented\n", encoding="utf-8")
    if contracts:
        document = folder / "docs" / "03_DATA_CONTRACTS.md"
        document.parent.mkdir(parents=True, exist_ok=True)
        document.write_text("invented\n", encoding="utf-8")


def _module(folder: Path, *tail: str) -> Path:
    start = folder.joinpath(*tail)
    start.parent.mkdir(parents=True, exist_ok=True)
    start.write_text("invented\n", encoding="utf-8")
    return start


def test_checkout_depth_finds_the_folder_holding_both_markers(
    tmp_path: Path,
) -> None:
    """The checkout layout resolves to the folder above custodian/src."""
    _plant(tmp_path, agents=True, contracts=True)
    start = _module(tmp_path, *_CHECKOUT_TAIL)
    assert _repository_root(start) == tmp_path.resolve()


def test_mutation_copy_depth_finds_the_same_folder(tmp_path: Path) -> None:
    """The mutants copy is one folder deeper and still resolves to that folder."""
    _plant(tmp_path, agents=True, contracts=True)
    start = _module(tmp_path, *_COPY_TAIL)
    assert _repository_root(start) == tmp_path.resolve()


def test_the_nearest_folder_holding_both_markers_wins(tmp_path: Path) -> None:
    """When two parents hold both files, the nearer parent is the folder."""
    _plant(tmp_path, agents=True, contracts=True)
    near = tmp_path / "near"
    _plant(near, agents=True, contracts=True)
    start = _module(near / "level", *_CHECKOUT_TAIL)
    assert _repository_root(start) == near.resolve()


def test_a_parent_holding_only_one_marker_is_passed_over(tmp_path: Path) -> None:
    """A parent that holds only one of the two files is not the folder."""
    _plant(tmp_path, agents=True, contracts=True)
    agents_only = tmp_path / "agents_only"
    contracts_only = tmp_path / "contracts_only"
    _plant(agents_only, agents=True, contracts=False)
    _plant(contracts_only, agents=False, contracts=True)
    for partial in (agents_only, contracts_only):
        start = _module(partial, *_CHECKOUT_TAIL)
        assert _repository_root(start) == tmp_path.resolve()


def test_no_parent_holding_both_markers_is_refused() -> None:
    """No parent holding both files raises FileNotFoundError with that message."""
    assert not Path("/eii-invented-folder-that-does-not-exist").exists()
    start = Path("/eii-invented-folder-that-does-not-exist").joinpath(*_CHECKOUT_TAIL)
    with pytest.raises(FileNotFoundError) as caught:
        _repository_root(start)
    assert type(caught.value) is FileNotFoundError
    assert str(caught.value) == _MISSING_CONTRACTS
