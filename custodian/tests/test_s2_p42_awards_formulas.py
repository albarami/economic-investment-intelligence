"""Invented award workbooks whose 'Approved Value Number' cells are cached formulas.

The owner's sheet stores that column as formula cells, each with a cached value;
the intake reads the cached value as stored and evaluates nothing.
"""

import io
from zipfile import ZipFile

import pytest
from custodian.tests.test_awards_incremental import intake
from custodian.tests.test_s2_t29_awards import STAMP
from hypothesis import given
from hypothesis import strategies as st

from eii_custodian.publicdata.fetch import awards
from eii_custodian.publicdata.fetch.receipts import sha256_hex

NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
SHEET = "Awarded Contracts "


def schema():
    return awards.load_declaration(awards.SOURCE)["profile"]


def text(reference, value):
    return f'<c r="{reference}" t="inlineStr"><is><t>{value}</t></is></c>'


def book(h_cell, *, g_cell=None):
    """One data row; H2 (and optionally G2) carry the given raw cell XML."""
    columns = schema()["columns"]
    header = "".join(text(f"{chr(65 + i)}1", c) for i, c in enumerate(columns))
    data = "".join(
        h_cell
        if c == "Approved Value Number"
        else g_cell
        if c == "Approved Value" and g_cell is not None
        else text(f"{chr(65 + i)}2", "03/02/2024" if c == "award_date" else "SYN")
        for i, c in enumerate(columns)
    )
    stream = io.BytesIO()
    with ZipFile(stream, "w") as z:
        z.writestr(
            "xl/workbook.xml",
            f'<workbook xmlns="{NS}" xmlns:r="{REL}"><sheets>'
            f'<sheet name="{SHEET}" r:id="syn"/></sheets></workbook>',
        )
        z.writestr(
            "xl/_rels/workbook.xml.rels",
            '<Relationships><Relationship Id="syn" Target="worksheets/syn.xml"/>'
            "</Relationships>",
        )
        z.writestr(
            "xl/worksheets/syn.xml",
            f'<worksheet xmlns="{NS}"><sheetData><row r="1">{header}</row>'
            f'<row r="2">{data}</row></sheetData></worksheet>',
        )
    return stream.getvalue()


def ingest(tmp_path, body):
    path, _ = intake(tmp_path, body)
    return awards.ingest_awards(tmp_path, path, sha256_hex(body), schema(), STAMP)


@pytest.mark.parametrize(
    ("cell", "expected"),
    [
        ('<c r="H2"><f>VALUE(G2)</f><v>1007.5</v></c>', "1007.5"),
        ('<c r="H2"><f>VALUE(G2)</f><v>0</v></c>', "0"),
        ('<c r="H2" t="str"><f>TRIM(G2)</f><v>SYN text</v></c>', "SYN text"),
        ('<c r="H2"><f t="shared" ref="H2:H9" si="0">G2*1</f><v>12.5</v></c>', "12.5"),
        ('<c r="H2"><f t="shared" si="0"/><v>7</v></c>', "7"),
    ],
    ids=["numeric", "zero", "string", "shared-master", "shared-child"],
)
def test_cached_formula_value_is_read_as_stored(tmp_path, cell, expected):
    batch = ingest(tmp_path, book(cell))
    assert batch.rows[0]["original"]["Approved Value Number"] == expected
    assert batch.rows[0]["parsed"]["Approved Value Number"] == expected


@pytest.mark.parametrize(
    "cell",
    [
        '<c r="H2"><f>VALUE(G2)</f></c>',
        '<c r="H2"><f t="shared" si="0"/></c>',
        '<c r="H2" t="str"><f>TRIM(G2)</f></c>',
        '<c r="H2"><f>VALUE(G2)</f><v/></c>',
        '<c r="H2" t="str"><f>TRIM(G2)</f><v></v></c>',
    ],
    ids=["no-v", "shared-no-v", "str-no-v", "empty-v", "str-empty-v"],
)
def test_formula_without_cached_value_refuses(tmp_path, cell):
    # an empty cached value is refused like a missing one: never blank, never zero
    with pytest.raises(awards.AwardError, match=r"^schema_missing$"):
        ingest(tmp_path, book(cell))


def test_plain_blank_cell_stays_blank_never_zero(tmp_path):
    batch = ingest(tmp_path, book('<c r="H2"/>'))
    assert batch.rows[0]["original"]["Approved Value Number"] == ""
    assert batch.rows[0]["parsed"]["Approved Value Number"] is None


def test_formula_in_another_column_is_read_by_cached_value(tmp_path):
    # the shared reader is column-blind: a cached formula in G reads like H
    body = book(
        '<c r="H2"><f>VALUE(G2)</f><v>12.5</v></c>',
        g_cell='<c r="G2" t="str"><f>"12.50"</f><v>12.50</v></c>',
    )
    batch = ingest(tmp_path, body)
    assert batch.rows[0]["original"]["Approved Value"] == "12.50"


@given(
    st.one_of(
        st.decimals(allow_nan=False, allow_infinity=False, places=2).map(str),
        st.integers(min_value=-(10**12), max_value=10**12).map(str),
    ),
    st.sampled_from(["plain", "shared"]),
)
def test_cached_value_equals_plain_cell_value(tmp_path_factory, cached, form):
    """Oracle: a cached formula reads exactly as a plain cell of the same <v>."""
    formula = "<f>VALUE(G2)</f>" if form == "plain" else '<f t="shared" si="0"/>'
    plain = ingest(
        tmp_path_factory.mktemp("plain"), book(f'<c r="H2"><v>{cached}</v></c>')
    )
    cached_batch = ingest(
        tmp_path_factory.mktemp("formula"),
        book(f'<c r="H2">{formula}<v>{cached}</v></c>'),
    )
    assert cached_batch.rows == plain.rows
    assert cached_batch.rows[0]["original"]["Approved Value Number"] == cached
