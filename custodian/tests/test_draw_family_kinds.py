"""L-2309 declared cell kinds; invented registry entries and phase rows only."""

from dataclasses import replace
from pathlib import Path

import pytest
from custodian.tests.test_assembly_reports import build
from custodian.tests.test_production_adapters import context
from custodian.tests.test_source_completeness import entry, receipt
from hypothesis import given, settings
from hypothesis import strategies as st

from eii_custodian.publicdata.assembly import AssemblyError
from eii_custodian.publicdata.assembly_reports import draw_tables
from eii_custodian.publicdata.draw import Figure, validate_figure
from eii_custodian.publicdata.figures_review import compare


def family(tmp_path, *, kind="number", name="measure", value="1.25"):
    source = entry(
        "price_ext", key="price_ext/syn", slug="syn", columns=((name, kind),)
    )
    state = context(tmp_path, (source,))
    state.receipts[source.key] = receipt(source)
    row = {
        "source_id": source.source_id,
        "source_key": source.key,
        "slug": source.slug,
        "field_name": name,
        "field_value": value,
    }
    state.table("pub_price_ext", [row], (source.key,))
    return state, state.tables["pub_price_ext"][0]


def read(state):
    state.record("gis_property_singles", {"tables": state.tables})
    return draw_tables(state)["pub_price_ext"]()


@pytest.mark.parametrize(
    "kind,name,value,expected",
    [
        ("number", "measure", "1.2500", [("1.2500", "number")]),
        ("integer", "measure", "3", [("3", "count")]),
        ("string", "measure", '"123"', []),
        ("date", "measure", "2026", []),
        ("integer", "year", "2026", []),
        *[
            (kind, "measure", "null", [])
            for kind in ("number", "integer", "string", "date")
        ],
    ],
)
def test_family_dispatch(tmp_path, kind, name, value, expected):
    state, _ = family(tmp_path, kind=kind, name=name, value=value)
    assert [(f.value, f.kind) for f in read(state)] == expected


@pytest.mark.parametrize(
    "kind,value",
    [
        ("number", '"1.25"'),
        ("integer", "1.5"),
        ("integer", "true"),
        ("string", "123"),
        ("date", '"2026"'),
        ("number", "NaN"),
        ("number", "Infinity"),
        ("number", "-Infinity"),
        ("number", "{}"),
        ("number", "[]"),
        ("number", "broken"),
        ("number", ""),
    ],
)
def test_family_kind_disagreement_refuses(tmp_path, kind, value):
    state, _ = family(tmp_path, kind=kind, value=value)
    with pytest.raises(AssemblyError, match=r"^assembly_draw_value_invalid$"):
        read(state)


def test_family_unknown_field_refuses_even_null(tmp_path):
    state, row = family(tmp_path, value="null")
    row["field_name"] = "undeclared"
    with pytest.raises(AssemblyError, match=r"^assembly_draw_field_unknown$"):
        read(state)


@pytest.mark.parametrize(
    "change",
    [
        "missing",
        "slug",
        "source_id",
        "duplicate",
        "foreign_slug",
        "source_key",
        "missing_source_key",
    ],
)
def test_family_entry_resolution_refuses(tmp_path, change):
    state, row = family(tmp_path)
    if change == "missing":
        state.entries = ()
    elif change == "duplicate":
        state.entries += (replace(state.entries[0], key="price_ext/other"),)
    elif change == "foreign_slug":
        state.entries += (
            replace(state.entries[0], key="price_ext/other", slug="other"),
        )
        row["slug"] = "other"
    elif change == "missing_source_key":
        row.pop("source_key")
    else:
        row[change] = "other"
    with pytest.raises(AssemblyError, match=r"^assembly_draw_lineage_ambiguous$"):
        read(state)


def test_number_compares_exactly_without_ratio_rounding():
    figure = Figure("syn", "syn", "https://example.org", "syn", "1.25", "number")
    validate_figure(figure)
    assert compare([figure], {"syn": "1.251"})[0]["result"] == "no match"
    assert compare([figure], {"syn": "1.25"})[0]["result"] == "match"
    with pytest.raises(ValueError, match=r"^figure_invalid$"):
        validate_figure(replace(figure, kind="numbr"))


@pytest.mark.parametrize("field", ["tariff_code", "tax_registration_number", "company"])
def test_numeric_text_identifiers_stay_skipped(tmp_path, field):
    state = build(tmp_path)
    state.tables["pub_invented"][0][field] = "123"
    state.record("gis_property_singles", {"tables": state.tables})
    assert len(draw_tables(state)["pub_invented"]()) == 25


def test_confidence_stays_a_ratio(tmp_path):
    state = build(tmp_path)
    state.tables["pub_invented"][0]["confidence"] = "0.7500"
    state.record("gis_property_singles", {"tables": state.tables})
    assert [
        (f.value, f.kind)
        for f in draw_tables(state)["pub_invented"]()
        if f.figure_id.endswith(":confidence")
    ] == [("0.7500", "ratio")]


@pytest.mark.parametrize("field", ["syn_unknown", "heading"])
def test_unclassified_numeric_field_still_refuses(tmp_path, field):
    state = build(tmp_path)
    state.tables["pub_invented"][0][field] = "123"
    state.record("gis_property_singles", {"tables": state.tables})
    with pytest.raises(AssemblyError, match=r"^assembly_draw_field_unknown$"):
        draw_tables(state)


def test_numeric_text_string_property(tmp_path: Path):
    @settings(deadline=None)
    @given(st.integers())
    def check(value):
        import json

        state, _ = family(tmp_path, kind="string", value=json.dumps(str(value)))
        assert read(state) == []

    check()


@pytest.mark.parametrize("value", [None, 1, True, {}, [], "1e" + "9" * 30])
def test_family_malformed_token_refuses(tmp_path, value):
    state, _ = family(tmp_path, value=value)
    with pytest.raises(AssemblyError, match=r"^assembly_draw_value_invalid$"):
        read(state)


@pytest.mark.parametrize("field", [None, [], {}, "undeclared"])
def test_family_malformed_field_refuses(tmp_path, field):
    state, row = family(tmp_path)
    row["field_name"] = field
    with pytest.raises(AssemblyError, match=r"^assembly_draw_field_unknown$"):
        read(state)


@pytest.mark.parametrize("name", ["year", "lat", "lon"])
def test_number_under_admin_name_is_skipped(tmp_path, name):
    state, _ = family(tmp_path, kind="number", name=name, value="1.25")
    assert read(state) == []


def test_family_missing_untagged_entry_cannot_be_excluded(tmp_path):
    state, row = family(tmp_path)
    other = replace(state.entries[0], key="price_ext/other", slug="other")
    state.entries += (other,)
    state.receipts[other.key] = receipt(other)
    state.table_sources["pub_price_ext"].add(other.key)
    assert len(read(state)) == 1
    row.pop("source_key")  # Only this input changes after the valid control.
    with pytest.raises(AssemblyError, match=r"^assembly_draw_lineage_ambiguous$"):
        read(state)


@pytest.mark.parametrize("slug", [[], {}, None, 1, True])
def test_family_malformed_slug_refuses(tmp_path, slug):
    state, row = family(tmp_path)
    row["slug"] = slug
    with pytest.raises(AssemblyError, match=r"^assembly_draw_lineage_ambiguous$"):
        read(state)
