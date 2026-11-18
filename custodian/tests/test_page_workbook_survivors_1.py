"""Invented OOXML inputs and normalization controls for survivor groups."""

import io
from zipfile import ZipFile

import pytest

from eii_custodian.publicdata.fetch.page_workbook import Sheet, read_sheet

NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
RELNS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def book(
    sheet_xml,
    *,
    sheet_attrs="",
    rid="rId2",
    shared=None,
    rels='<Relationship Id="rId2" Target="worksheets/sheet2.xml"/>',
    entries=None,
    extra=None,
):
    """Build an invented workbook whose only sheet is the named SYN Table."""
    identity = f'r:id="{rid}"' if rid is not None else ""
    stream = io.BytesIO()
    with ZipFile(stream, "w") as z:
        z.writestr(
            "xl/workbook.xml",
            f'<workbook xmlns="{NS}" xmlns:r="{RELNS}"><sheets>'
            f'<sheet name="SYN Table" {sheet_attrs} {identity}/></sheets></workbook>',
        )
        z.writestr(
            "xl/_rels/workbook.xml.rels", f"<Relationships>{rels}</Relationships>"
        )
        if shared is not None:
            z.writestr("xl/sharedStrings.xml", shared)
        z.writestr("xl/worksheets/sheet2.xml", sheet_xml)
        for name, body in entries or {}:
            z.writestr(name, body)
    if extra:
        # Duplicate entry names are written through a second pass.
        with ZipFile(stream, "a") as z:
            for name, body in extra:
                z.writestr(name, body)
    return stream.getvalue()


def sheet(*rows_xml, merges=(), merge_xml=""):
    merge = ""
    if merges:
        cells = "".join(f'<mergeCell ref="{m}"/>' for m in merges)
        merge = f"<mergeCells>{cells}</mergeCells>"
    elif merge_xml:
        merge = f"<mergeCells>{merge_xml}</mergeCells>"
    return (
        f'<worksheet xmlns="{NS}"><sheetData>'
        + "".join(rows_xml)
        + f"</sheetData>{merge}</worksheet>"
    )


def refutes(body, name="SYN Table", **kwargs):
    with pytest.raises(ValueError, match=r"^schema_missing$"):
        read_sheet(body, name, **kwargs)


def test_read_sheet_success_contract():
    body = book(
        sheet(
            '<row r="6"><c r="A6" t="inlineStr"><is><t>End of Period</t></is></c>'
            '<c r="D6"><v>7</v></c></row>',
            merges=["A6:C6"],
        ),
        sheet_attrs='sheetId="2"',
    )
    result = read_sheet(body, "SYN Table")
    assert result == Sheet(
        cells={"A6": "End of Period", "D6": "7"},
        rows={6: ["End of Period", "", "", "7"]},
        merges=("A6:C6",),
        part="xl/worksheets/sheet2.xml",
        relationship="rId2",
        sheet_id="2",
    )


def test_read_sheet_missing_sheet_id_defaults_empty():
    body = book(sheet('<row r="6"><c r="A6"><v>7</v></c></row>'))
    assert read_sheet(body, "SYN Table").sheet_id == ""


def test_read_sheet_two_or_zero_sheets_refused():
    body = book(sheet('<row r="6"><c r="A6"><v>7</v></c></row>'))
    refutes(body, "SYN missing")
    doubled = io.BytesIO()
    with ZipFile(doubled, "w") as z:
        z.writestr(
            "xl/workbook.xml",
            f'<workbook xmlns="{NS}" xmlns:r="{RELNS}"><sheets>'
            '<sheet name="SYN Table" sheetId="2" r:id="rId2"/>'
            '<sheet name="SYN Table" sheetId="3" r:id="rId3"/>'
            "</sheets></workbook>",
        )
        z.writestr(
            "xl/_rels/workbook.xml.rels",
            "<Relationships>"
            '<Relationship Id="rId2" Target="worksheets/sheet2.xml"/>'
            '<Relationship Id="rId3" Target="worksheets/sheet3.xml"/>'
            "</Relationships>",
        )
        for name in ("sheet2.xml", "sheet3.xml"):
            z.writestr(
                "xl/worksheets/" + name,
                sheet('<row r="6"><c r="A6"><v>7</v></c></row>'),
            )
    refutes(doubled.getvalue())


def test_read_sheet_duplicate_zip_entries_refused():
    body = book(
        sheet('<row r="6"><c r="A6"><v>7</v></c></row>'),
        extra=[
            (
                "xl/worksheets/sheet2.xml",
                sheet('<row r="6"><c r="A6"><v>7</v></c></row>'),
            )
        ],
    )
    refutes(body)


def test_read_sheet_shared_strings_resolved():
    shared = (
        f'<sst xmlns="{NS}"><si><t>SYN one</t></si>'
        "<si><t></t></si><si><r><t>SYN a</t></r><r><t>SYN b</t></r></si></sst>"
    )
    body = book(
        sheet(
            '<row r="6">'
            '<c r="A6" t="s"><v>0</v></c>'
            '<c r="B6" t="s"><v>1</v></c>'
            '<c r="C6" t="s"><v>2</v></c>'
            "</row>"
        ),
        shared=shared,
    )
    result = read_sheet(body, "SYN Table")
    assert result.cells == {"A6": "SYN one", "B6": "", "C6": "SYN aSYN b"}
    refutes(
        book(
            sheet('<row r="6"><c r="A6" t="s"><v>-1</v></c></row>'),
            shared=shared,
        )
    )


def test_read_sheet_shared_string_without_table_refused():
    body = book(sheet('<row r="6"><c r="A6" t="s"><v>0</v></c></row>'))
    refutes(body)


def test_read_sheet_inline_and_plain_kinds():
    body = book(
        sheet(
            '<row r="6">'
            '<c r="A6" t="inlineStr"><is><t>SYN one</t><t>SYN two</t></is></c>'
            '<c r="B6" t="str"><v>SYN formula text</v></c>'
            '<c r="C6"><v>7</v></c>'
            "</row>"
        )
    )
    result = read_sheet(body, "SYN Table")
    assert result.cells == {
        "A6": "SYN oneSYN two",
        "B6": "SYN formula text",
        "C6": "7",
    }
    refutes(book(sheet('<row r="6"><c r="A6" t="b"><v>1</v></c></row>')))


def test_read_sheet_missing_value_keeps_empty_text():
    body = book(sheet('<row r="6"><c r="A6"/></row>'))
    assert read_sheet(body, "SYN Table").cells == {"A6": ""}


def test_read_sheet_formula_contract():
    cached = sheet('<row r="7"><c r="D7"><f>D9</f><v>7</v></c></row>')
    refutes(book(cached))  # the default call refuses to evaluate formulas
    assert read_sheet(book(cached), "SYN Table", cached_formulas=True).cells == {
        "D7": "7"
    }
    uncached = sheet('<row r="7"><c r="D7"><f>D9</f></c></row>')
    refutes(book(uncached), cached_formulas=True)


def test_read_sheet_row_and_cell_coordinates():
    body = book(
        sheet(
            '<row r="6"><c r="C6"><v>7</v></c><c r="A6"><v>9</v></c></row>',
            '<row r="6"><c r="B6"><v>1</v></c></row>',
        )
    )
    refutes(body)
    out_of_order = book(
        sheet('<row r="6"><c r="B6"><v>1</v></c><c r="A6"><v>9</v></c></row>')
    )
    refutes(out_of_order)
    wrong_row = book(sheet('<row r="6"><c r="A7"><v>1</v></c></row>'))
    refutes(wrong_row)
    duplicate_cell = book(
        sheet('<row r="6"><c r="A6"><v>1</v></c><c r="A6"><v>2</v></c></row>')
    )
    refutes(duplicate_cell)
    gaps = book(sheet('<row r="6"><c r="A6"><v>1</v></c><c r="C6"><v>3</v></c></row>'))
    assert read_sheet(gaps, "SYN Table").rows == {6: ["1", "", "3"]}
    wide = book(sheet('<row r="6"><c r="AA6"><v>1</v></c></row>'))
    assert read_sheet(wide, "SYN Table").rows == {6: [""] * 26 + ["1"]}


def test_read_sheet_row_numbers_and_hidden_rows():
    body = book(
        sheet(
            '<row r="6"><c r="A6"><v>1</v></c></row>',
            '<row><c r="A7"><v>2</v></c></row>',
        )
    )
    assert read_sheet(body, "SYN Table").rows == {6: ["1"], 7: ["2"]}
    refutes(
        book(
            sheet(
                '<row r="6"><c r="A6"><v>1</v></c></row>',
                '<row r="5"><c r="A5"><v>0</v></c></row>',
            )
        )
    )
    refutes(book(sheet('<row r="6" hidden="1"><c r="A6"><v>1</v></c></row>')))
    assert read_sheet(
        book(sheet('<row r="6" hidden="false"><c r="A6"><v>1</v></c></row>')),
        "SYN Table",
    ).rows == {6: ["1"]}


def test_read_sheet_relationship_contract():
    # The relationship id may be absent only when the rels table has the empty id.
    body = book(
        sheet('<row r="6"><c r="A6"><v>7</v></c></row>'),
        rid=None,
        rels='<Relationship Id="" Target="worksheets/sheet2.xml"/>',
    )
    assert read_sheet(body, "SYN Table").part == "xl/worksheets/sheet2.xml"
    missing = book(
        sheet('<row r="6"><c r="A6"><v>7</v></c></row>'),
        rid=None,
    )
    refutes(missing)
    no_target = book(
        sheet('<row r="6"><c r="A6"><v>7</v></c></row>'),
        rels='<Relationship Id="rId2"/>',
    )
    refutes(no_target)
    two_targets = book(
        sheet('<row r="6"><c r="A6"><v>7</v></c></row>'),
        rels=(
            '<Relationship Id="rId2" Target="worksheets/sheet2.xml"/>'
            '<Relationship Id="rId2" Target="worksheets/sheet9.xml"/>'
        ),
    )
    refutes(two_targets)
    external = book(
        sheet('<row r="6"><c r="A6"><v>7</v></c></row>'),
        rels=(
            '<Relationship Id="rId2" TargetMode="External" '
            'Target="https://invented.invalid/SYN"/>'
            '<Relationship Id="rId2" Target="worksheets/sheet2.xml"/>'
        ),
    )
    assert read_sheet(external, "SYN Table").part == "xl/worksheets/sheet2.xml"
    parent_escape = book(
        sheet('<row r="6"><c r="A6"><v>7</v></c></row>'),
        rels='<Relationship Id="rId2" Target="xl/worksheets/../worksheets/sheet2.xml"/>',
    )
    refutes(parent_escape)
    off_tree = book(
        sheet('<row r="6"><c r="A6"><v>7</v></c></row>'),
        rels='<Relationship Id="rId2" Target="xl/other.xml"/>',
        entries=[("xl/other.xml", sheet('<row r="6"><c r="A6"><v>7</v></c></row>'))],
    )
    refutes(off_tree)
    rooted = book(
        sheet('<row r="6"><c r="A6"><v>7</v></c></row>'),
        rels='<Relationship Id="rId2" Target="/worksheets/sheet2.xml"/>',
    )
    assert read_sheet(rooted, "SYN Table").part == "xl/worksheets/sheet2.xml"


def test_read_sheet_merges_default_to_empty_ref():
    body = book(
        sheet('<row r="6"><c r="A6"><v>7</v></c></row>', merge_xml="<mergeCell/>")
    )
    assert read_sheet(body, "SYN Table").merges == ("",)


def test_read_sheet_broken_inputs_refused():
    refutes(b"SYN not a workbook")
    refutes(book("SYN not xml"))
    refutes(
        book(
            sheet('<row r="6"><c r="A6"><v>7</v></c></row>'),
            rels="<Relationships>",
        )
    )
