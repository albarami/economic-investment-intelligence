"""Invented page and workbook regressions for S2-T29 survivor groups."""

import io
from zipfile import ZipFile

import pytest
from custodian.tests.test_s2_t29_live_awards import report
from custodian.tests.test_s2_t29_live_shapes import (
    classified,
    declaration,
    embedded,
    tariff,
    tariffs,
)

from eii_custodian.publicdata.fetch.page_shapes import (
    award_cards,
    awards,
    blocks,
    page_end,
    parse,
)
from eii_custodian.publicdata.fetch.page_shapes import (
    classified as classified_rows,
)
from eii_custodian.publicdata.fetch.page_shapes import (
    workbook as workbook_rows,
)

URL = "https://www.data.gov.qa/syn-shape"
XLSX_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"


def refutes(call, *args, message="schema_missing", **kwargs):
    with pytest.raises(ValueError, match=r"^" + message + "$"):
        call(*args, **kwargs)


def parsed(decl, body, source="events_visit_qatar", url=None):
    return parse(body, decl, url=url) if url else parse(body, decl)


# embedded


def test_embedded_holder_id_and_type_are_both_required():
    dec, _body, _rec = embedded("script")
    body = (
        '<script id="wix-warmup-data" type="SYN-other">'
        + _body.decode().split(">", 1)[1]
    )
    refutes(parsed, dec, body.encode())
    refutes(parsed, dec, body.replace("wix-warmup-data", "SYN-other-id").encode())


def test_embedded_copies_and_records_refusals():
    dec, body, _rec = embedded()
    refutes(parsed, dec, body.replace(b"SYN &gt; event", b"SYN different", 1))
    refutes(
        parsed, dec, b'<vq-event-listing :events="SYN-no-json"></vq-event-listing>' * 2
    )
    both = embedded("script")
    refutes(
        parsed,
        both[0],
        both[1].replace(b'"hasMore": false', b'"hasMore": true'),
        message="paging_incomplete",
    )
    as_object = embedded()
    as_object[0]["shape"]["record_path"] = []
    records = '{"SYN": "invented"}'
    tag = (
        '<vq-event-listing :events="'
        + records.replace('"', "&quot;")
        + '"></vq-event-listing>'
    )
    refutes(parsed, as_object[0], (tag + tag).encode())


# workbook parser


def xlsx_book(rows, merge='<mergeCell ref="A6:C6"/>'):
    worksheet = (
        f'<worksheet xmlns="{XLSX_NS}"><sheetData>'
        + "".join(rows)
        + f"</sheetData><mergeCells>{merge}</mergeCells></worksheet>"
    )
    stream = io.BytesIO()
    with ZipFile(stream, "w") as z:
        z.writestr(
            "xl/workbook.xml",
            '<workbook xmlns="'
            + XLSX_NS
            + '" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            '<sheets><sheet name="SYN Table" sheetId="2" r:id="rId2"/></sheets></workbook>',
        )
        z.writestr(
            "xl/_rels/workbook.xml.rels",
            '<Relationships><Relationship Id="rId2" '
            'Target="worksheets/sheet2.xml"/></Relationships>',
        )
        z.writestr("xl/worksheets/sheet2.xml", worksheet)
    return stream.getvalue()


HEADER_ROW = (
    '<row r="6"><c r="A6" t="inlineStr"><is><t>End of Period</t></is></c>'
    '<c r="D6" t="inlineStr"><is><t>SYN value</t></is></c></row>'
)
ANNUAL_ROW = '<row r="7"><c r="B7"><v>2030</v></c><c r="D7"><f>D9</f><v>7</v></c></row>'
BLANK_ROW = '<row r="8"/>'
Q1_ROW = (
    '<row r="9"><c r="A9" t="inlineStr"><is><t>Q1</t></is></c><c r="B9"><v>2031</v></c>'
    '<c r="C9" t="inlineStr"><is><t>SYN quarter</t></is></c><c r="D9"><v>9</v></c></row>'
)
Q2_ROW = (
    '<row r="10"><c r="A10" t="inlineStr"><is><t>Q2*</t></is></c>'
    '<c r="C10" t="inlineStr"><is><t>SYN quarter</t></is></c><c r="D10"><v>11</v></c></row>'
)
FOOTER_ROW = (
    '<row r="11"><c r="A11" t="inlineStr"><is><t>*Primary Data</t></is></c>'
    '<c r="D11" t="inlineStr"><is><t>*بيانات أولية</t></is></c></row>'
)
STANDARD_ROWS = [HEADER_ROW, ANNUAL_ROW, BLANK_ROW, Q1_ROW, Q2_ROW, FOOTER_ROW]


def insurance_spec(**changes):
    spec = {
        "name": "SYN Table",
        "part": "xl/worksheets/sheet2.xml",
        "relationship": "rId2",
        "sheet_id": "2",
        "header_cells": {"A6": "End of Period", "D6": "SYN value"},
        "merged_cells": ["A6:C6"],
        "annual_rows": [7, 7],
        "quarter_rows": [9, 10],
        "blank_row": 8,
        "period_cell": "A6",
        "year_column": "B",
        "quarter_column": "A",
        "quarter_label_column": "C",
        "carry_year": "first_quarter",
        "footer_row": 11,
        "footer_last_column": "D",
        "columns": {"SYN value": "D"},
    }
    spec.update(changes)
    return {"discovery": None, "sheets": [spec]}


def run_workbook(rows, **changes):
    return workbook_rows(xlsx_book(rows), insurance_spec(**changes))


def test_workbook_success_contract():
    result = run_workbook(STANDARD_ROWS)
    assert result == [
        {
            "sheet": "SYN Table",
            "period": "2030",
            "measure": "SYN value",
            "value": "7",
            "preliminary": "false",
        },
        {
            "sheet": "SYN Table",
            "period": "2031-Q1",
            "measure": "SYN value",
            "value": "9",
            "preliminary": "false",
        },
        {
            "sheet": "SYN Table",
            "period": "2031-Q2",
            "measure": "SYN value",
            "value": "11",
            "preliminary": "true",
        },
    ]


@pytest.mark.parametrize(
    "changes",
    [
        {"part": "xl/worksheets/sheet1.xml"},
        {"relationship": "rId9"},
        {"sheet_id": "3"},
        {"merged_cells": ["B6:C6"]},
        {"merged_cells": ["A6:C6", "A6:C6"]},
        {"period_cell": "B6"},
        {"header_cells": {"A6": "End of Period", "D6": "SYN changed"}},
        {"header_cells": {"A6": "SYN period", "D6": "SYN value"}, "period_cell": "A6"},
    ],
)
def test_workbook_identity_mismatches_refused(changes):
    refutes(run_workbook, STANDARD_ROWS, **changes)


def test_workbook_extra_header_cell_refused():
    rows = list(STANDARD_ROWS)
    rows[0] = HEADER_ROW.replace(
        "</row>", '<c r="E6" t="inlineStr"><is><t>SYN extra</t></is></c></row>'
    )
    refutes(run_workbook, rows)


def test_workbook_footer_texts_required_on_both_ends():
    rows = list(STANDARD_ROWS)
    rows[5] = FOOTER_ROW.replace("*Primary Data", "SYN changed")
    refutes(run_workbook, rows)
    rows = list(STANDARD_ROWS)
    rows[5] = rows[5].replace(
        "*بيانات أولية",
        "SYN changed",
    )
    refutes(run_workbook, rows)


def test_workbook_no_text_below_footer():
    rows = [
        *STANDARD_ROWS,
        '<row r="12"><c r="E12" t="inlineStr"><is><t>SYN after</t></is></c></row>',
    ]
    refutes(run_workbook, rows)


def test_workbook_blank_row_stays_blank():
    rows = list(STANDARD_ROWS)
    rows[2] = '<row r="8"><c r="D8" t="inlineStr"><is><t>SYN stray</t></is></c></row>'
    refutes(run_workbook, rows)


@pytest.mark.parametrize(
    "changes",
    [
        {"annual_rows": "SYN"},
        {"annual_rows": [7]},
        {"annual_rows": [7, 8, 9]},
        {"annual_rows": ["7", "7"]},
        {"annual_rows": [7, 0]},
        {"annual_rows": [8, 7]},
        {"annual_rows": [7.0, 7.0]},
        {"annual_rows": (7, 7)},
        {"quarter_rows": [9]},
    ],
)
def test_workbook_row_spec_shapes_refused(changes):
    refutes(run_workbook, STANDARD_ROWS, **changes)


def test_workbook_adjacency_third_link_required():
    rows = [
        HEADER_ROW,
        ANNUAL_ROW,
        BLANK_ROW,
        Q1_ROW,
        Q2_ROW,
        '<row r="11"/>',
        FOOTER_ROW.replace('r="11"', 'r="12"')
        .replace("A11", "A12")
        .replace("D11", "D12"),
    ]
    refutes(run_workbook, rows, footer_row=12)


def test_workbook_adjacency_second_link_required():
    rows = [
        HEADER_ROW,
        ANNUAL_ROW,
        BLANK_ROW,
        '<row r="9"/>',
        Q1_ROW.replace('r="9"', 'r="10"')
        .replace("A9", "A10")
        .replace("B9", "B10")
        .replace("C9", "C10")
        .replace("D9", "D10"),
        FOOTER_ROW,
    ]
    refutes(run_workbook, rows, quarter_rows=[10, 10])


def test_workbook_quarter_cells_and_labels():
    rows = list(STANDARD_ROWS)
    rows[3] = Q1_ROW.replace("<t>Q1</t>", "<t>Q9</t>")
    refutes(run_workbook, rows)
    rows = list(STANDARD_ROWS)
    rows[3] = Q1_ROW.replace(
        '<c r="C9" t="inlineStr"><is><t>SYN quarter</t></is></c>', ""
    )
    refutes(run_workbook, rows)


def test_workbook_year_carry_across_two_first_quarters():
    def quarter_row(row, quarter, year=""):
        return (
            f'<row r="{row}"><c r="A{row}" t="inlineStr"><is><t>Q{quarter}</t></is></c>'
            + (f'<c r="B{row}"><v>{year}</v></c>' if year else "")
            + f'<c r="C{row}" t="inlineStr"><is><t>SYN quarter</t></is></c>'
            + f'<c r="D{row}"><v>9</v></c></row>'
        )

    rows = [HEADER_ROW, ANNUAL_ROW, BLANK_ROW]
    rows += [
        quarter_row(9, 1, "2031"),
        quarter_row(10, 2),
        quarter_row(11, 3),
        quarter_row(12, 4),
        quarter_row(13, 1, "2032"),
    ]
    rows += [
        FOOTER_ROW.replace('r="11"', 'r="14"')
        .replace("A11", "A14")
        .replace("D11", "D14")
    ]
    result = run_workbook(rows, quarter_rows=[9, 13], footer_row=14)
    assert [r["period"] for r in result] == [
        "2030",
        "2031-Q1",
        "2031-Q2",
        "2031-Q3",
        "2031-Q4",
        "2032-Q1",
    ]


def test_workbook_year_texts_refused():
    rows = list(STANDARD_ROWS)
    rows[1] = ANNUAL_ROW.replace("<v>2030</v>", "<v>SYN</v>")
    refutes(run_workbook, rows)
    rows = list(STANDARD_ROWS)
    rows[4] = (
        Q1_ROW.replace('r="9"', 'r="10"')
        .replace("A9", "A10")
        .replace("B9", "B10")
        .replace("C9", "C10")
        .replace("D9", "D10")
        .replace("2031", "2033")
    )
    refutes(run_workbook, rows)


def test_workbook_quarter_sequence_must_advance():
    q3 = (
        '<row r="10"><c r="A10" t="inlineStr"><is><t>Q3</t></is></c>'
        '<c r="C10" t="inlineStr"><is><t>SYN quarter</t></is></c><c r="D10"><v>11</v></c></row>'
    )
    rows = [HEADER_ROW, ANNUAL_ROW, BLANK_ROW, Q1_ROW, q3, FOOTER_ROW]
    refutes(run_workbook, rows)


def test_workbook_annual_rows_carry_no_quarter_or_label():
    rows = list(STANDARD_ROWS)
    rows[1] = ANNUAL_ROW.replace(
        '<c r="D7">', '<c r="C7" t="inlineStr"><is><t>SYN label</t></is></c><c r="D7">'
    )
    refutes(run_workbook, rows)
    rows = list(STANDARD_ROWS)
    rows[1] = ANNUAL_ROW.replace(
        '<c r="B7">', '<c r="A7" t="inlineStr"><is><t>Q1</t></is></c><c r="B7">'
    )
    refutes(run_workbook, rows)


def test_workbook_undeclared_column_refused():
    rows = list(STANDARD_ROWS)
    rows[1] = ANNUAL_ROW.replace(
        "</row>", '<c r="E7" t="inlineStr"><is><t>SYN stray</t></is></c></row>'
    )
    refutes(run_workbook, rows)


def test_workbook_measure_values_required():
    rows = list(STANDARD_ROWS)
    rows[1] = '<row r="7"><c r="B7"><v>2030</v></c></row>'
    refutes(run_workbook, rows)
    rows = list(STANDARD_ROWS)
    rows[1] = '<row r="7"><c r="B7"><v>2030</v></c><c r="D7"><v></v></c></row>'
    refutes(run_workbook, rows)


# tariff blocks


def tariff_dec(**shape_changes):
    dec = tariffs()
    dec["shape"].update(shape_changes)
    return dec


def test_blocks_url_must_be_reviewed():
    dec = tariff_dec()
    refutes(
        blocks,
        tariff(),
        dec["shape"],
        "https://invented.invalid/SYN-other",
        message="blocked_host",
    )


def test_blocks_no_tariff_state_refuses_any_price_or_heading():
    dec = tariff_dec()
    dec["shape"]["pages"][0].update(state="no tariff on page", layout=None)
    only_block = b'<div class="price">SYN</div>'
    refutes(blocks, only_block, dec["shape"], URL)
    only_heading = b"<h3> Pricing</h3>"
    refutes(blocks, only_heading, dec["shape"], URL)


def test_blocks_heading_scope_required():
    dec = tariff_dec()
    outside = (
        '<div><div class="row d-flex justify-content-between"><div class="col-lg-3">'
        + tariff().decode().split('<div class="col-lg-3">')[1]
    )
    refutes(blocks, outside.encode(), dec["shape"], URL)
    two_headings = tariff() + tariff()
    refutes(blocks, two_headings, dec["shape"], URL)


def test_blocks_counts_and_first_child_required():
    dec = tariff_dec()
    extra_block = tariff() + b'<div class="price">SYN</div>'
    refutes(blocks, extra_block, dec["shape"], URL)
    preceded = tariff().replace(
        b'<div class="col-lg-3"><h3> Pricing</h3>',
        b'<div class="col-lg-3"><p>SYN lead</p><h3> Pricing</h3>',
    )
    refutes(blocks, preceded, dec["shape"], URL)


def test_blocks_single_layout_class_required():
    dec = tariff_dec()
    plain_price = tariff().replace(b"price mb-4", b"price")
    refutes(blocks, plain_price, dec["shape"], URL)


def test_blocks_double_layout_containers_required():
    dec = tariff_dec()
    dec["shape"]["pages"][0]["layout"] = "double"
    retargeted = tariff(True).replace(b"col-md-6", b"col-md-5")
    refutes(blocks, retargeted, dec["shape"], URL)


def test_blocks_amount_text_and_outputs():
    split_amount = tariff().replace(b"7 <span>QR</span>", b"7<span>QR</span>9")
    dec = tariff_dec()
    rows = blocks(split_amount, dec["shape"], URL)
    assert rows == [
        {
            "label": "SYN  rate",
            "value": "79",
            "currency": "QR",
            "unit": "per square meter per year",
        }
    ]
    wrong_currency = tariff().replace(b">QR<", b">SYN<")
    refutes(blocks, wrong_currency, dec["shape"], URL)


# classified companies


def classified_body():
    dec, body = classified()
    return dec, body


def test_classified_activity_link_count_required():
    dec, body = classified_body()
    refutes(
        classified_rows,
        body.replace(b'">SYN</a>', b'">SYN</a><a href="SYN">SYN</a>'),
        dec["shape"],
        dec["columns"],
    )
    refutes(
        classified_rows,
        body.replace(b'<a href="javascript:openCompanyDataModel(7);">SYN</a>', b"SYN"),
        dec["shape"],
        dec["columns"],
    )


def test_classified_duplicate_binding_refused():
    dec, body = classified_body()
    second_row = (
        "<tr><td>2</td><td>SYN-profile</td><td>SYN-type</td><td>SYN company</td>"
        "<td>SYN-reg</td><td>SYN-size</td><td></td>"
        '<td><a href="javascript:openCompanyDataModel(7);">SYN</a></td></tr>'
    )
    body = body.replace(b"</tbody>", second_row.encode() + b"</tbody>", 1)
    refutes(classified_rows, body, dec["shape"], dec["columns"])


def test_classified_modal_shape_and_parent_required():
    dec, body = classified_body()
    unclassed = body.replace(
        b'class="modal fade bd-example-modal-lg"', b'class="modal"'
    )
    refutes(classified_rows, unclassed, dec["shape"], dec["columns"])


def test_classified_column_count_must_match():
    dec, body = classified_body()
    shorter = declaration("html_table", dec["shape"], dec["columns"][:-1])
    shorter["url"] = dec["url"]
    shorter["reviewed_urls"] = dec["reviewed_urls"]
    with pytest.raises(
        ValueError, match=r"^zip\(\) argument 2 is longer than argument 1$"
    ):
        classified_rows(body, shorter["shape"], shorter["columns"])


def test_classified_modal_tables_and_headings_required():
    dec, body = classified_body()
    bare = (
        body.replace(
            b'<div class="alert alert-success">SYN supplier - expiry: 03/02/2031</div>',
            b"",
        )
        .replace(
            b'<table class="custom--table mb-5">', b'<div class="custom--table mb-5">'
        )
        .replace(b"</table></div>", b"</div></div>")
    )
    refutes(classified_rows, bare, dec["shape"], dec["columns"])
    table_only = body.replace(
        b'<div class="alert alert-success">SYN supplier - expiry: 03/02/2031</div>', b""
    )
    refutes(classified_rows, table_only, dec["shape"], dec["columns"])


def test_classified_heading_sibling_order_required():
    dec, body = classified_body()
    last = body.replace(
        b'<div class="alert alert-success">SYN supplier - expiry: 03/02/2031</div>'
        b'<table class="custom--table mb-5">',
        b'<table class="custom--table mb-5">',
    ).replace(
        b"</table></div>",
        b'</table><div class="alert alert-success">SYN supplier - expiry: 03/02/2031</div></div>',
    )
    refutes(classified_rows, last, dec["shape"], dec["columns"])
    separated = body.replace(
        b'<div class="alert alert-success">SYN supplier - expiry: 03/02/2031</div>',
        b'<div class="alert alert-success">SYN supplier - expiry: 03/02/2031</div><p>SYN gap</p>',
    )
    refutes(classified_rows, separated, dec["shape"], dec["columns"])


def test_classified_section_heading_matched_exactly_when_undated():
    dec, body = classified_body()
    section = dict(
        dec["shape"]["sections"][0], heading="SYN contractor", date_in_heading=False
    )
    dec["shape"]["sections"] = [section]
    longer = body.replace(
        b"SYN supplier - expiry: 03/02/2031", b"SYN contractor extra"
    ).replace(b"<td>SYN grade</td>", b"<td>03/02/2031</td>")
    refutes(classified_rows, longer, dec["shape"], dec["columns"])
    unmatched = body.replace(b"SYN supplier - expiry: 03/02/2031", b"SYN other heading")
    refutes(classified_rows, unmatched, dec["shape"], dec["columns"])


def test_classified_heading_and_row_dates_parse_or_refuse():
    dec, body = classified_body()
    bad_heading = body.replace(b"expiry: 03/02/2031", b"expiry: SYN")
    refutes(classified_rows, bad_heading, dec["shape"], dec["columns"])
    section = dict(
        dec["shape"]["sections"][0], heading="SYN contractor", date_in_heading=False
    )
    dec["shape"]["sections"] = [section]
    bad_row = body.replace(
        b"SYN supplier - expiry: 03/02/2031", b"SYN contractor"
    ).replace(b"<td>SYN grade</td>", b"<td>SYN invalid</td>")
    refutes(classified_rows, bad_row, dec["shape"], dec["columns"])


def test_classified_activity_output_fields():
    dec, body = classified_body()
    rows = classified_rows(body, dec["shape"], dec["columns"])
    assert rows[0]["activities"] == [
        {
            "section": "SYN supplier - expiry: ",
            "expiry": "2031-02-03",
            "fields": {
                "SYN ordinal": "1",
                "SYN activity": "SYN-act",
                "SYN label": "SYN work",
                "SYN grade": "SYN grade",
            },
        }
    ]


def test_classified_modal_count_required():
    dec, body = classified_body()
    refutes(
        classified_rows,
        body + b'<div id="CompanyData-9"></div>',
        dec["shape"],
        dec["columns"],
    )


# page end


def page_shape():
    dec, _ = classified_body()
    return dec["shape"]


def test_page_end_total_prefix_and_digits_required():
    shape = page_shape()
    wrong_prefix = b'<div class="d-flex align-items-center mx-2">SYN other: 1</div><nav aria-label="Page navigation"><ul class="pagination"><li><a class="page-link" tabindex="-1" href="/syn-shape/1">1</a></li></ul></nav>'
    refutes(page_end, wrong_prefix, shape, message="paging_incomplete")


def test_page_end_total_digits_required():
    shape = page_shape()
    body = (
        b'<div class="d-flex align-items-center mx-2">SYN total: SYN</div>'
        b'<nav aria-label="Page navigation"><ul class="pagination"><li>'
        b'<a class="page-link" tabindex="-1" href="/syn-shape/1">1</a></li></ul></nav>'
    )
    refutes(page_end, body, shape, message="paging_incomplete")
    two_links = (
        b'<div class="d-flex align-items-center mx-2">SYN total: 1</div>'
        b'<nav aria-label="Page navigation"><ul class="pagination"><li>'
        b'<a class="page-link" tabindex="-1" href="/syn-shape/1">1</a></li>'
        b'<a class="page-link" tabindex="-1" href="/syn-shape/1">1</a></li></ul></nav>'
    )
    refutes(page_end, two_links, shape, message="paging_incomplete")


def test_page_end_last_page_digits_required():
    shape = page_shape()
    zero = (
        b'<div class="d-flex align-items-center mx-2">SYN total: 1</div>'
        b'<nav aria-label="Page navigation"><ul class="pagination"><li>'
        b'<a class="page-link" tabindex="-1" href="/syn-shape/0">0</a></li></ul></nav>'
    )
    refutes(page_end, zero, shape, message="paging_incomplete")
    letter = (
        b'<div class="d-flex align-items-center mx-2">SYN total: 1</div>'
        b'<nav aria-label="Page navigation"><ul class="pagination"><li>'
        b'<a class="page-link" tabindex="-1" href="/syn-shape/x">x</a></li></ul></nav>'
    )
    refutes(page_end, letter, shape, message="paging_incomplete")


def test_page_end_last_page_accepts_one():
    shape = page_shape()
    body = (
        b'<div class="d-flex align-items-center mx-2">SYN total: 7</div>'
        b'<nav aria-label="Page navigation"><ul class="pagination"><li>'
        b'<a class="page-link" tabindex="-1" href="/syn-shape/1">1</a></li></ul></nav>'
    )
    assert page_end(body, shape) == (7, 1)


def test_page_end_last_link_path_required():
    shape = page_shape()
    body = (
        b'<div class="d-flex align-items-center mx-2">SYN total: 7</div>'
        b'<nav aria-label="Page navigation"><ul class="pagination"><li>'
        b'<a class="page-link" tabindex="-1" href="/SYN-other/3">3</a></li></ul></nav>'
    )
    refutes(page_end, body, shape, message="paging_incomplete")


# awards


def awards_dec(**changes):
    dec, body = report()
    for name, value in changes.items():
        dec[name] = value
    return dec, body


def test_awards_heading_unique_and_followed():
    dec, body = awards_dec()
    refutes(
        awards,
        body.replace(b"SYN awarded companies", b"SYN other heading", 1),
        dec["shape"],
        dec["columns"],
    )
    duplicated = body.replace(b"SYN opened bids", b"SYN awarded companies")
    refutes(awards, duplicated, dec["shape"], dec["columns"])
    last = body.replace(
        b'<h3>SYN awarded companies</h3><div class="custom--table--responsive">',
        b'<div class="custom--table--responsive">',
    ).replace(
        b"<h3>SYN opened bids</h3>",
        b"<h3>SYN awarded companies</h3>",
    )
    last = last[: last.rindex(b"<div>")]
    refutes(awards, last, dec["shape"], dec["columns"])
    tailed = (
        body.replace(
            b"</div><h3>SYN opened bids</h3><div>",
            b"</div>",
        )
        + b"<p>SYN tail</p>"
    )
    rows = awards(tailed, dec["shape"], dec["columns"])
    assert [r["SYN company"] for r in rows] == ["SYN first", "SYN second"]


def test_awards_date_and_amount_contract():
    dec, body = awards_dec()
    refutes(
        awards,
        body.replace(b"03/02/2031", b"SYN wrong"),
        dec["shape"],
        dec["columns"],
        message="snapshot_date_missing",
    )
    refutes(
        awards,
        body.replace(b"1,007.00 \xd8\xb1\xd9\x82", b"SYN amount"),
        dec["shape"],
        dec["columns"],
    )
    with pytest.raises(
        ValueError, match=r"^zip\(\) argument 2 is shorter than argument 1$"
    ):
        awards(body, dec["shape"], dec["columns"] + [["SYN extra", "string"]])


def test_awards_output_values():
    dec, body = awards_dec()
    rows = awards(body, dec["shape"], dec["columns"])
    assert rows[0]["SYN amount"] == "1007.00"
    assert rows[0]["award_date"] == "2031-02-03"
    assert rows[1]["SYN amount"] == "9.00"


# parse dispatch


def test_parse_refusal_kind_has_no_rows_branch():
    dec = declaration(
        "refusal",
        {"reason": "SYN", "observed_utc": "SYN", "decision": "SYN"},
        [["SYN", "string"]],
    )
    refutes(parsed, dec, b"SYN body")


# award cards


CARDS_BODY = (
    b'<div class="custom--table--responsive py-2"><table class="custom--table"><tbody><tr>'
    b'<div class="row custom-cards"><div class="col-md-7 cards-col"><div class="col-header">'
    b'<span class="card-label"><label>SYN-2031</label></span></div>'
    b'<span class="card-title"><a href="/TendersOnlineServices/TenderDetails/SYN-a">SYN award</a></span>'
    b'<div class="cards-row"><span class="card-label"><label>'
    b"\xd8\xaa\xd8\xa7\xd8\xb1\xd9\x8a\xd8\xae \xd8\xa7\xd9\x84\xd8\xaa\xd8\xb1\xd8\xb3\xd9\x8a\xd8\xa9"
    b'</label></span><span class="card-title"><span><label>03/02/2031</label></span></span></div></div>'
    b'<div class="col-md-2 circle-container"><a class="btn btn-primary" '
    b'href="/TendersOnlineServices/TenderCompaniesDetails/SYN-a">SYN report</a></div></div></tr></tbody></table></div>'
)


def test_award_cards_success_contract():
    assert award_cards(CARDS_BODY) == [
        {
            "number": "SYN-2031",
            "title": "SYN award",
            "award_date": "2031-02-03",
            "report_path": "/TendersOnlineServices/TenderCompaniesDetails/SYN-a",
        }
    ]


def test_award_cards_structure_required():
    refutes(
        award_cards, CARDS_BODY.replace(b'<div class="row custom-cards">', b"<div>")
    )
    refutes(
        award_cards,
        CARDS_BODY.replace(b"/TendersOnlineServices/TenderDetails/SYN-a", b"SYN-other"),
    )
    refutes(
        award_cards,
        CARDS_BODY.replace(b"03/02/2031", b"SYN invalid"),
        message="snapshot_date_missing",
    )
    refutes(
        award_cards,
        CARDS_BODY.replace(
            b"/TendersOnlineServices/TenderCompaniesDetails/", b"SYN-other/"
        ),
    )
