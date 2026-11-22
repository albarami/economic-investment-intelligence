"""PO-S2-48 release production on the lead-described INVENTED Table 76 only."""

import io
from dataclasses import replace
from decimal import Decimal
from fractions import Fraction
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import pytest
from custodian.tests.test_frame_census import entry
from custodian.tests.test_frame_seventh import seventh_build
from custodian.tests.test_pinned_c8 import workbook, write_source
from hypothesis import example, given
from hypothesis import strategies as st

from eii_custodian.publicdata.fetch.page_html import ShapeError
from eii_custodian.publicdata.fetch.page_workbook import NS
from eii_custodian.publicdata.fetch.registry import load_registry
from eii_custodian.publicdata.frame import census
from eii_custodian.publicdata.frame.build import build_frame
from eii_custodian.publicdata.frame.checks import FrameError

TABLE = "pub_census_national"
RETRIEVED = "2026-11-21T00:00:00Z"


def changed_workbook(body, cells=None, *, missing_table=False):
    """Change one physical cell or sheet name; keep the other OOXML intact."""
    output = io.BytesIO()
    with ZipFile(io.BytesIO(body)) as original, ZipFile(output, "w") as target:
        for name in original.namelist():
            value = original.read(name)
            if name == "xl/workbook.xml" and missing_table:
                value = value.replace(b'name="76"', b'name="INVENTED other"')
            if name == "xl/worksheets/sheet1.xml" and cells:
                root = ET.fromstring(value)
                for row in root.findall("s:sheetData/s:row", NS):
                    for cell in list(row):
                        ref = cell.get("r")
                        if ref in cells:
                            if cells[ref] is None:
                                row.remove(cell)
                            else:
                                cell.clear()
                                cell.set("r", ref)
                                cell.set("t", "inlineStr")
                                ET.SubElement(cell, "{" + NS["s"] + "}is").append(
                                    ET.Element("{" + NS["s"] + "}t")
                                )
                                cell[0][0].text = str(cells[ref])
                value = ET.tostring(root)
            target.writestr(name, value)
    return output.getvalue()


def release_rows(body):
    return census.census_rows(
        entry("census_2020_workbook"), census.workbook_rows(body), RETRIEVED, TABLE
    )[0]


@pytest.mark.parametrize("both_row", [8, 12, 23])
def test_table_76_release_rows(both_row):
    assert release_rows(workbook(both_row=both_row)) == [
        {
            "period": "2020",
            "indicator": indicator,
            "value": Decimal(value),
            "unit": "persons",
            "source_id": "census_2020_workbook",
        }
        for indicator, value in [
            ("private_employed_residents", 30),
            ("employed_residents", 60),
        ]
    ]


def test_missing_table_76_refuses():
    with pytest.raises(ShapeError, match=r"^schema_missing$"):
        release_rows(changed_workbook(workbook(), missing_table=True))


@pytest.mark.parametrize(
    "ref,value,reason",
    [
        ("F7", "INVENTED other", "national_header"),
        ("J7", None, "national_header"),
        ("B8", None, "national_block"),
        ("B8", "BothSexes", "national_block"),
        ("B9", "Both Sexes", "national_block"),
        ("K8", "Both Sexes", "national_block"),
        ("B29", None, "sex_block"),
        ("B50", None, "sex_block"),
        ("F8", None, "national_count"),
        ("J8", None, "national_count"),
        ("F8", "INVENTED not a number", "national_count"),
        ("F8", "", "national_count"),
        ("F8", "-1", "national_denominator"),
        ("F8", "1.5", "national_denominator"),
        ("F8", "NaN", "national_denominator"),
        ("J8", "Infinity", "national_denominator"),
        ("J8", "0", "national_denominator"),
    ],
)
def test_each_table_76_refusal_changes_one_cell(ref, value, reason):
    with pytest.raises(FrameError, match=f"^C8:{reason}$"):
        release_rows(changed_workbook(workbook(), {ref: value}))


@pytest.mark.parametrize(
    "plant,reason",
    [
        ("misplaced_both_C", "national_block"),
        ("misplaced_male_K", "sex_block"),
        ("misplaced_female_L", "sex_block"),
        ("uncached_formula", "schema_missing"),
    ],
)
def test_moved_labels_and_uncached_formula_refuse(plant, reason):
    error = ShapeError if reason == "schema_missing" else FrameError
    expected = reason if error is ShapeError else "C8:" + reason
    with pytest.raises(error, match=f"^{expected}$"):
        release_rows(workbook(plant=plant))


def test_split_whitespace_and_case_are_normalised():
    body = changed_workbook(workbook(), {"B8": "  BoTh\t SeXeS\n"})
    assert release_rows(body) == release_rows(workbook())


@pytest.mark.parametrize(
    "indicator,unit",
    [
        ("INVENTED_unknown", "persons"),
        ("Private_Employed_Residents", "persons"),
        ("private_employed_residents", "establishments"),
    ],
)
def test_closed_indicator_unit_refuses(indicator, unit):
    row = census.workbook_rows(workbook())[0] | {"indicator": indicator, "unit": unit}
    with pytest.raises(
        FrameError, match=r"^census_2020_workbook: invalid indicator/unit$"
    ):
        census.census_rows(entry("census_2020_workbook"), [row], RETRIEVED, TABLE)


def test_c8_vocabulary_is_national_only_and_not_an_audit_selector():
    assert census.UNITS == {
        "residents": "persons",
        "households": "households",
        "establishments": "establishments",
        "employees": "persons",
    }
    for indicator in ("private_employed_residents", "employed_residents"):
        assert census.unit_for(TABLE, indicator) == "persons"
        for table in census.GEOGRAPHY.keys() - {TABLE}:
            assert census.unit_for(table, indicator) is None


@given(
    counts=st.integers(min_value=1, max_value=99999999999999).flatmap(
        lambda total: st.tuples(
            st.just(total), st.integers(min_value=0, max_value=total)
        )
    ),
    both_row=st.integers(min_value=8, max_value=40),
)
@example(counts=(1, 0), both_row=8)
@example(counts=(99999999999999, 99999999999998), both_row=40)
def test_counts_preserve_exact_rational_values(counts, both_row):
    total, drawn_private = counts
    # Arbitrary interior and both boundaries, including zero and a tie.
    for private in (0, drawn_private, total):
        rows = release_rows(
            changed_workbook(
                workbook(both_row=both_row),
                {f"F{both_row}": private, f"J{both_row}": total},
            )
        )
        assert tuple(Fraction(row["value"]) for row in rows) == (
            Fraction(private),
            Fraction(total),
        )


@pytest.mark.parametrize("mode", ["active", "skipped", "missing"])
def test_live_frame_appends_workbook_without_losing_establishments(tmp_path, mode):
    prepared = seventh_build.__wrapped__(tmp_path)
    baseline = prepared()
    source = next(e for e in load_registry() if e.key == "census_2020_workbook")
    digest = write_source(prepared.cache, source.key, workbook())
    entries = prepared.entries
    if mode != "missing":
        entries += (
            replace(source, skip_reason="INVENTED unavailable")
            if mode == "skipped"
            else source,
        )
    from eii_custodian.publicdata.fetch.snapshots import reviewed_selections

    selections = reviewed_selections(prepared.cache) | {source.key: digest}
    result = build_frame(
        prepared.cache, entries, prepared.review, selections=selections
    )
    expected = baseline.tables[TABLE] + (
        release_rows(workbook()) if mode == "active" else []
    )
    assert result.tables[TABLE] == expected
    if mode == "active":
        chain = result.sources[source.source_id]
        assert chain["sha256"] == digest
        assert chain["retrieved_utc"] == RETRIEVED
        assert chain["publisher"] == source.publisher
        assert chain["licence_id"] == source.licence_id
        assert chain["fetch_url"] == source.url
        assert chain["method"] == "frame.census.table76.v1: Both Sexes Private / Total"
    else:
        assert source.source_id not in result.sources
