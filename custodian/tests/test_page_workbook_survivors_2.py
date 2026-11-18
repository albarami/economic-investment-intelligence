"""Independent OOXML coordinate and relationship boundary fixtures."""

from custodian.tests.test_page_workbook_survivors_1 import book, refutes, sheet

from eii_custodian.publicdata.fetch.page_workbook import read_sheet

CELL = '<row r="6"><c r="A6"><v>7</v></c></row>'


def test_workbook_repeated_row_number_with_distinct_cells_refused():
    body = book(sheet(CELL, '<row r="6"><c r="B6"><v>9</v></c></row>'))
    refutes(body)


def test_workbook_missing_cell_reference_refused():
    refutes(book(sheet('<row r="6"><c><v>7</v></c></row>')))


def test_workbook_explicit_xl_target_preserved():
    body = book(
        sheet(CELL), rels='<Relationship Id="rId2" Target="xl/worksheets/sheet2.xml"/>'
    )
    assert read_sheet(body, "SYN Table").cells == {"A6": "7"}


def test_workbook_parent_target_refused_even_if_member_exists():
    target = "xl/worksheets/../worksheets/sheet2.xml"
    body = book(
        sheet(CELL),
        rels=f'<Relationship Id="rId2" Target="{target}"/>',
        entries=[(target, sheet(CELL))],
    )
    refutes(body)


def test_workbook_lstrip_does_not_remove_non_slash_characters():
    body = book(
        sheet(CELL), rels='<Relationship Id="rId2" Target="Xxl/worksheets/sheet2.xml"/>'
    )
    refutes(body)


def test_workbook_no_target_cannot_alias_a_zip_member():
    body = book(
        sheet(CELL),
        rels='<Relationship Id="rId2"/>',
        entries=[("xl/XXXX", sheet(CELL))],
    )
    refutes(body)


def test_workbook_inline_empty_text_preserved():
    body = book(sheet('<row r="6"><c r="A6" t="inlineStr"><is><t/></is></c></row>'))
    assert read_sheet(body, "SYN Table").cells == {"A6": ""}


def test_workbook_empty_cached_formula_refused():
    refutes(
        book(sheet('<row r="6"><c r="A6"><f>1</f><v/></c></row>')), cached_formulas=True
    )
