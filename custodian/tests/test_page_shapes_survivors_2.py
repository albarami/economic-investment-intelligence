"""Guard-isolating fixtures for the remaining S2-T29 page-shape survivors."""

import re

from custodian.tests.test_page_shapes_survivors_1 import (
    ANNUAL_ROW,
    CARDS_BODY,
    FOOTER_ROW,
    HEADER_ROW,
    Q1_ROW,
    STANDARD_ROWS,
    awards_dec,
    classified_body,
    insurance_spec,
    page_shape,
    refutes,
    run_workbook,
    tariff_dec,
    xlsx_book,
)
from custodian.tests.test_s2_t29_live_shapes import tariff

from eii_custodian.publicdata.fetch.page_shapes import (
    award_cards,
    awards,
    blocks,
    classified,
    page_end,
    workbook,
)


def move_row(row, old, new):
    return re.sub(rf'(?<=[A-Z]){old}(?=")', str(new), row).replace(
        f'r="{old}"', f'r="{new}"'
    )


def test_workbook_duplicate_merge_declaration_refused():
    refutes(run_workbook, STANDARD_ROWS, merged_cells=["A6:C6", "A6:C6"])


def test_workbook_absent_blank_row_is_allowed():
    rows = STANDARD_ROWS[:2] + STANDARD_ROWS[3:]
    assert [r["value"] for r in run_workbook(rows)] == ["7", "9", "11"]


def test_workbook_first_adjacency_required():
    # The declared blank row is immediately before the quarters, but there is
    # an extra empty row between annual observations and that blank row.
    rows = [HEADER_ROW, ANNUAL_ROW, '<row r="8"/>', '<row r="9"/>']
    rows += [move_row(STANDARD_ROWS[3], 9, 10), move_row(STANDARD_ROWS[4], 10, 11)]
    rows += [move_row(FOOTER_ROW, 11, 12)]
    refutes(run_workbook, rows, blank_row=9, quarter_rows=[10, 11], footer_row=12)


def test_workbook_preserves_all_annual_rows():
    rows = [HEADER_ROW, ANNUAL_ROW]
    rows += [move_row(ANNUAL_ROW, 7, 8).replace("2030", "2031"), '<row r="9"/>']
    rows += [move_row(STANDARD_ROWS[3], 9, 10), move_row(STANDARD_ROWS[4], 10, 11)]
    rows += [move_row(FOOTER_ROW, 11, 12)]
    result = run_workbook(
        rows, annual_rows=[7, 8], blank_row=9, quarter_rows=[10, 11], footer_row=12
    )
    assert [r["period"] for r in result] == ["2030", "2031", "2031-Q1", "2031-Q2"]


def test_workbook_one_based_annual_range():
    # A quarterly label also provides the period header; no cell is fabricated
    # by the parser, and row 1 is a valid independent annual observation.
    q1 = move_row(Q1_ROW, 9, 3).replace("SYN quarter", "End of Period")
    rows = [
        move_row(ANNUAL_ROW, 7, 1),
        '<row r="2"/>',
        q1,
        move_row(STANDARD_ROWS[4], 10, 4),
        move_row(FOOTER_ROW, 11, 5),
    ]
    result = run_workbook(
        rows,
        annual_rows=[1, 1],
        blank_row=2,
        quarter_rows=[3, 4],
        footer_row=5,
        header_cells={"A3": "Q1", "B3": "2031", "C3": "End of Period", "D3": "9"},
        period_cell="C3",
    )
    assert result[0]["period"] == "2030"


def test_workbook_missing_first_quarter_year_refused():
    rows = list(STANDARD_ROWS)
    rows[3] = Q1_ROW.replace('<c r="B9"><v>2031</v></c>', "")
    refutes(run_workbook, rows)


def test_workbook_invalid_quarter_year_refused():
    rows = list(STANDARD_ROWS)
    rows[3] = Q1_ROW.replace("2031", "SYN")
    refutes(run_workbook, rows)


def test_workbook_empty_measure_refused_after_sheet_read():
    rows = list(STANDARD_ROWS)
    rows[1] = '<row r="7"><c r="B7"><v>2030</v></c><c r="D7"><v></v></c></row>'
    refutes(run_workbook, rows)


def test_blocks_parent_layout_refused():
    dec = tariff_dec()
    refutes(
        blocks, tariff().replace(b"col-lg-3", b"col-lg-4"), dec["shape"], dec["url"]
    )


def test_classified_modal_must_share_table_grandparent():
    dec, body = classified_body()
    body = body.replace(b'<div class="modal fade', b'<section><div class="modal fade')
    body = body.replace(b'<div class="d-flex', b'</section><div class="d-flex')
    refutes(classified, body, dec["shape"], dec["columns"])


def test_classified_empty_modal_tables_refused():
    dec, body = classified_body()
    begin = body.index(b'<div class="alert alert-success">')
    end = body.index(b'<div class="d-flex', begin)
    body = body[:begin] + b"</div>" + body[end:]
    refutes(classified, body, dec["shape"], dec["columns"])


def test_classified_undated_section_output():
    dec, body = classified_body()
    dec["shape"]["sections"][0].update(heading="SYN contractor", date_in_heading=False)
    body = body.replace(b"SYN supplier - expiry: 03/02/2031", b"SYN contractor")
    body = body.replace(b"<td>SYN grade</td>", b"<td>03/02/2031</td>")
    assert (
        classified(body, dec["shape"], dec["columns"])[0]["activities"][0]["expiry"]
        == "2031-02-03"
    )


def test_page_end_missing_href_never_matches_invented_path():
    shape = page_shape()
    shape["path_template"] = "XXXX"
    body = b'<div class="d-flex align-items-center mx-2">SYN total: 7</div><nav aria-label="Page navigation"><a class="page-link" tabindex="-1">1</a></nav>'
    refutes(page_end, body, shape, message="paging_incomplete")


def test_awards_heading_with_no_following_sibling_refused():
    dec, _ = awards_dec()
    refutes(
        awards,
        b"<div><h3>SYN awarded companies</h3></div>",
        dec["shape"],
        dec["columns"],
    )


def test_awards_empty_table_refused():
    dec, body = awards_dec()
    body = re.sub(rb"<tbody>.*?</tbody>", b"<tbody></tbody>", body, count=1, flags=re.S)
    refutes(awards, body, dec["shape"], dec["columns"])


def test_award_card_missing_date_label_refused():
    body = CARDS_BODY.replace("تاريخ الترسية".encode(), b"SYN other date")
    refutes(award_cards, body)


def test_workbook_duplicate_physical_merges_refused():
    spec = insurance_spec()
    body = xlsx_book(STANDARD_ROWS, merge='<mergeCell ref="A6:C6"/>' * 2)
    refutes(workbook, body, spec)


def test_workbook_upper_header_text_must_match():
    rows = [
        '<row r="5"><c r="A5" t="inlineStr"><is><t>SYN title</t></is></c></row>',
        *STANDARD_ROWS,
    ]
    refutes(
        run_workbook,
        rows,
        header_cells={"A5": "SYN wrong", "A6": "End of Period", "D6": "SYN value"},
    )


def test_workbook_first_observation_may_be_second_quarter():
    rows = list(STANDARD_ROWS)
    rows[3] = rows[3].replace("<t>Q1</t>", "<t>Q2</t>")
    rows[4] = rows[4].replace("<t>Q2*</t>", "<t>Q3*</t>")
    assert [r["period"] for r in run_workbook(rows)] == ["2030", "2031-Q2", "2031-Q3"]


def test_workbook_missing_quarter_cell_refused():
    rows = list(STANDARD_ROWS)
    rows[3] = Q1_ROW.replace('<c r="A9" t="inlineStr"><is><t>Q1</t></is></c>', "")
    refutes(run_workbook, rows)


def test_workbook_upper_header_outside_data_columns_preserved():
    rows = [
        '<row r="5"><c r="E5" t="inlineStr"><is><t>SYN title</t></is></c></row>',
        *STANDARD_ROWS,
    ]
    result = run_workbook(
        rows, header_cells={"E5": "SYN title", "A6": "End of Period", "D6": "SYN value"}
    )
    assert [r["value"] for r in result] == ["7", "9", "11"]


def test_classified_valid_table_with_following_sibling():
    dec, body = classified_body()
    body = body.replace(
        b'</table></div><div class="d-flex',
        b'</table><p>SYN tail</p></div><div class="d-flex',
    )
    assert (
        classified(body, dec["shape"], dec["columns"])[0]["activities"][0]["expiry"]
        == "2031-02-03"
    )
