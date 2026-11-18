"""Invented records in the round-two live shapes; no live I/O or source values."""

import html
import io
import json
from dataclasses import replace
from zipfile import ZipFile

import pytest
from custodian.tests.test_s2_t29_pages import STAMP, page_entry

from eii_custodian.publicdata.fetch.page_records import fetch_page, parse_body
from eii_custodian.publicdata.fetch.transport import Response

URL = "https://www.data.gov.qa/syn-shape"


def schema(kind="string", **kwargs):
    return dict(kind=kind, nullable=False, optional=False, **kwargs)


def declaration(kind, shape, columns):
    return {
        "version": 2,
        "kind": kind,
        "url": URL,
        "reviewed_urls": [URL],
        "columns": columns,
        "as_of": "retrieval_date",
        "publisher_date": None,
        "period_fields": [],
        "bounds_basis": "unconfirmed",
        "bounds_reason": "SYN awaiting observed bounds",
        "pins": [],
        "evidence": "EVIDENCE-shapes.md synthetic shape fixture",
        "hold": None,
        "max_bytes": 65536,
        "shape": shape,
    }


def entry(dec, source="events_visit_qatar"):
    return replace(
        page_entry(),
        url=dec["url"],
        source_id=source,
        key=source,
        columns=tuple(tuple(p) for p in dec["columns"]),
    )


def embedded(mode="attribute"):
    shape = {
        "element": "vq-event-listing" if mode == "attribute" else "script",
        "attribute": ":events" if mode == "attribute" else None,
        "id": None if mode == "attribute" else "wix-warmup-data",
        "type": None if mode == "attribute" else "application/json",
        "copies": 2 if mode == "attribute" else 1,
        "record_path": []
        if mode == "attribute"
        else ["appsWarmupData", "SYN-widget", "events", "events"],
        "more_path": None
        if mode == "attribute"
        else ["appsWarmupData", "SYN-widget", "events", "hasMore"],
        "page_bound": 1,
        "record_schema": schema(
            "object",
            fields={
                "title": schema(),
                "startDate": schema("object", fields={"iso": schema()}),
                "endDate": schema("object", fields={"iso": schema()}),
                "linkToDetailPage": schema(
                    "object", fields={"url": schema(), "active": schema("boolean")}
                ),
            },
        ),
        "fields": {
            "title": ["title"],
            "start": ["startDate", "iso"],
            "end": ["endDate", "iso"],
        },
    }
    dec = declaration(
        "embedded_json",
        shape,
        [["title", "string"], ["start", "string"], ["end", "string"]],
    )
    dec["period_fields"] = ["start", "end"]
    rec = {
        "title": "SYN > event",
        "startDate": {"iso": "2031-02-03"},
        "endDate": {"iso": "2031-02-04"},
        "linkToDetailPage": {"url": "/SYN-event", "active": True},
    }
    if mode == "attribute":
        one = (
            '<vq-event-listing :events="'
            + html.escape(json.dumps([rec]), quote=True)
            + '"></vq-event-listing>'
        )
        return dec, (one + one).encode(), rec
    obj = {
        "appsWarmupData": {
            "SYN-widget": {"events": {"events": [rec], "hasMore": False}}
        }
    }
    return (
        dec,
        (
            '<script id="wix-warmup-data" type="application/json">'
            + json.dumps(obj)
            + "</script>"
        ).encode(),
        rec,
    )


@pytest.mark.parametrize("mode", ["attribute", "script"])
def test_embedded_live_shape(mode):
    dec, body, record = embedded(mode)
    rows = parse_body(body, entry(dec), dec)
    assert rows == [
        {
            "title": "SYN > event",
            "start": "2031-02-03",
            "end": "2031-02-04",
            "published_record": record,
        }
    ]
    if mode == "attribute":
        raw_attribute = body.replace(b"&gt;", b">")
        assert b"SYN > event" in raw_attribute
        assert parse_body(raw_attribute, entry(dec), dec) == rows


@pytest.mark.parametrize(
    "plant", ["disagree", "selector", "extra", "missing", "type", "non_json", "nested"]
)
def test_embedded_plants(plant):
    dec, body, rec = embedded()
    if plant == "disagree":
        body = body.replace(b"SYN &gt; event", b"SYN different", 1)
    elif plant == "selector":
        body = body.replace(b"vq-event-listing", b"vq-event-listing-results")
    elif plant == "non_json":
        body = b'<vq-event-listing :events="SYN-no-json"></vq-event-listing>' * 2
    else:
        if plant == "extra":
            rec["SYN-extra"] = "SYN"
        if plant == "missing":
            del rec["title"]
        if plant == "type":
            rec["linkToDetailPage"]["active"] = 1
        if plant == "nested":
            rec["startDate"]["extra"] = "SYN"
        tag = (
            '<vq-event-listing :events="'
            + html.escape(json.dumps([rec]), quote=True)
            + '"></vq-event-listing>'
        )
        body = (tag * 2).encode()
    with pytest.raises(ValueError, match="schema_missing"):
        parse_body(body, entry(dec), dec)


def test_qncc_nonterminal_refuses():
    dec, body, _ = embedded("script")
    body = body.replace(b'"hasMore": false', b'"hasMore": true')
    with pytest.raises(ValueError, match="paging_incomplete"):
        parse_body(body, entry(dec), dec)


@pytest.mark.parametrize(
    "plant",
    ["unknown", "kind", "shape", "schema_kind", "schema_extra", "date", "missing_date"],
)
def test_closed_contract_before_fetch(tmp_path, plant):
    dec, body, _ = embedded()
    if plant == "unknown":
        dec["SYN-unknown"] = True
    if plant == "kind":
        dec["kind"] = "SYN-unknown"
    if plant == "shape":
        dec["shape"]["SYN-extra"] = True
    if plant == "schema_kind":
        dec["shape"]["record_schema"]["kind"] = "SYN-unknown"
    if plant == "schema_extra":
        dec["shape"]["record_schema"]["SYN-extra"] = True
    if plant == "date":
        dec["as_of"] = "SYN-malformed"
    if plant == "missing_date":
        del dec["as_of"]
    calls = []
    with pytest.raises(ValueError, match=r"snapshot_date_missing|schema_missing"):
        fetch_page(
            entry(dec),
            lambda u: calls.append(u) or Response(u, body, ()),
            tmp_path,
            lambda: STAMP,
            lambda _: None,
            declaration=dec,
        )
    assert calls == []


def tariff(two=False):
    block = '<div class="price"><div class="priceHeader bg-gold">SYN  rate</div><div class="priceDetails"><h4>7 <span>QR</span></h4><p class="text-gold"><i>per square meter per year</i></p></div></div>'
    inside = (
        (
            '<div class="col-12"><h3> Pricing</h3><div class="row mb-4"><div class="col-md-6">'
            + block
            + '</div><div class="col-md-6">'
            + block.replace("7 ", "9 ")
            + "</div></div></div>"
        )
        if two
        else '<div class="col-lg-3"><h3> Pricing</h3>'
        + block.replace('class="price"', 'class="price mb-4"')
        + "</div>"
    )
    return (
        '<section class="pageSection upRound bg-grey-4"><div class="container-lg"><div class="row d-flex justify-content-between">'
        + inside
        + "</div></div></section>"
    ).encode()


def tariffs():
    return declaration(
        "html_blocks",
        {
            "heading": "Pricing",
            "scope": "section.pageSection.upRound.bg-grey-4 > div.container-lg > div.row.d-flex.justify-content-between",
            "layouts": ["single", "double"],
            "unit": "per square meter per year",
            "currency": "QR",
            "pages": [{"url": URL, "state": "tariff", "layout": "single"}],
            "discovery": None,
        },
        [
            ["label", "string"],
            ["value", "number"],
            ["currency", "string"],
            ["unit", "string"],
        ],
    )


@pytest.mark.parametrize("two", [False, True])
def test_tariff_layouts(two):
    dec = tariffs()
    dec["shape"]["pages"][0]["layout"] = "double" if two else "single"
    rows = parse_body(tariff(two), entry(dec, "manateq_tariffs"), dec)
    assert len(rows) == (2 if two else 1)
    assert rows[0]["label"] == "SYN  rate"
    assert rows[0]["value"] == "7"


@pytest.mark.parametrize(
    "plant", ["decimal", "currency", "unit", "heading", "extra_block"]
)
def test_tariff_plants(plant):
    dec, body = tariffs(), tariff()
    if plant == "decimal":
        body = body.replace(b"7 <", b"7.5 <")
    if plant == "currency":
        body = body.replace(b">QR<", b">SYN<")
    if plant == "unit":
        body = body.replace(b"per square meter", b"SYN-unit")
    if plant == "heading":
        body = body.replace(b" Pricing", b"SYN-else")
    if plant == "extra_block":
        body = tariff(True)
    with pytest.raises(ValueError, match="schema_missing"):
        parse_body(body, entry(dec, "manateq_tariffs"), dec)


def test_no_tariff_is_declared_state():
    dec = tariffs()
    dec["shape"]["pages"][0].update(state="no tariff on page", layout=None)
    assert (
        parse_body(b"<p>SYN no price published</p>", entry(dec, "manateq_tariffs"), dec)
        == []
    )
    with pytest.raises(ValueError, match="schema_missing"):
        parse_body(tariff(), entry(dec, "manateq_tariffs"), dec)


def classified():
    dec = declaration(
        "html_table",
        {
            "profile": "classified",
            "selector": "div.page-content > div.custom--table--responsive > table.custom--table.mb-2",
            "headers": [
                "SYN ordinal",
                "SYN profile",
                "SYN type",
                "SYN name",
                "SYN registration",
                "SYN size",
                "SYN evaluation",
                "SYN activities",
            ],
            "sections": [
                {
                    "heading": "SYN supplier - expiry: ",
                    "headers": [
                        "SYN ordinal",
                        "SYN activity",
                        "SYN label",
                        "SYN grade",
                    ],
                    "date_in_heading": True,
                }
            ],
            "total_selector": "div.d-flex.align-items-center.mx-2",
            "total_prefix": "SYN total: ",
            "last_selector": 'a.page-link[tabindex="-1"]',
            "path_template": "https://www.data.gov.qa/syn-shape/{page}",
        },
        [
            ["SYN ordinal", "integer"],
            ["SYN profile", "string"],
            ["SYN type", "string"],
            ["SYN name", "string"],
            ["SYN registration", "string"],
            ["SYN size", "string"],
            ["SYN evaluation", "string"],
            ["SYN activities", "string"],
        ],
    )
    dec["url"] = URL + "/1"
    dec["reviewed_urls"] = [dec["url"]]
    heads = "".join("<th>" + s + "</th>" for s in dec["shape"]["headers"])
    nested = (
        "<thead><tr>"
        + "".join("<th>" + s + "</th>" for s in dec["shape"]["sections"][0]["headers"])
        + "</tr></thead><tbody><tr><td>1</td><td>SYN-act</td><td>SYN work</td><td>SYN grade</td></tr></tbody>"
    )
    table = (
        '<div class="custom--table--responsive"><table class="custom--table mb-2"><thead><tr>'
        + heads
        + '</tr></thead><tbody><tr><td>1</td><td>SYN-profile</td><td>SYN-type</td><td>SYN company</td><td>SYN-reg</td><td>SYN-size</td><td></td><td><a href="javascript:openCompanyDataModel(7);">SYN</a></td></tr></tbody></table></div>'
    )
    modal = (
        '<div class="modal fade bd-example-modal-lg" id="CompanyData-7"><div class="alert alert-success">SYN supplier - expiry: 03/02/2031</div><table class="custom--table mb-5">'
        + nested
        + "</table></div>"
    )
    body = (
        '<div class="page-content">'
        + table
        + modal
        + '<div class="d-flex align-items-center mx-2">SYN total: 1</div><nav aria-label="Page navigation"><ul class="pagination"><li><a class="page-link" tabindex="-1" href="/syn-shape/1">1</a></li></ul></nav></div>'
    ).encode()
    return dec, body


def test_modal_binding_by_number():
    dec, body = classified()
    rows = parse_body(body, entry(dec, "monaqasat_classified"), dec)
    assert rows[0]["activities"][0]["expiry"] == "2031-02-03"
    assert rows[0]["SYN evaluation"] is None
    with pytest.raises(ValueError, match="schema_missing"):
        parse_body(body.replace(b"CompanyData-7", b"CompanyData-1"), entry(dec), dec)


@pytest.mark.parametrize("plant", ["missing", "extra", "span", "duplicate_modal"])
def test_classified_plants(plant):
    dec, body = classified()
    if plant == "missing":
        body = body.replace(b"<th>SYN type</th>", b"")
    if plant == "extra":
        body = body.replace(b"<td>SYN-size</td>", b"<td>SYN-size</td><td>SYN</td>")
    if plant == "span":
        body = body.replace(b"<td>SYN-size", b'<td colspan="2">SYN-size')
    if plant == "duplicate_modal":
        body += b'<div id="CompanyData-7"></div>'
    with pytest.raises(ValueError, match="schema_missing"):
        parse_body(body, entry(dec), dec)


def workbook():
    shape = {
        "discovery": None,
        "sheets": [
            {
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
        ],
    }
    dec = declaration(
        "xlsx_sheet",
        shape,
        [
            ["sheet", "string"],
            ["period", "string"],
            ["measure", "string"],
            ["value", "number"],
            ["preliminary", "string"],
        ],
    )
    dec["period_fields"] = ["period"]
    ns = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    with io.BytesIO() as stream:
        with ZipFile(stream, "w") as z:
            z.writestr(
                "xl/workbook.xml",
                f'<workbook xmlns="{ns}" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="SYN Table" sheetId="2" r:id="rId2"/></sheets></workbook>',
            )
            z.writestr(
                "xl/_rels/workbook.xml.rels",
                '<Relationships><Relationship Id="rId2" Target="worksheets/sheet2.xml"/></Relationships>',
            )
            z.writestr(
                "xl/worksheets/sheet2.xml",
                f'<worksheet xmlns="{ns}"><sheetData><row r="6"><c r="A6" t="inlineStr"><is><t>End of Period</t></is></c><c r="D6" t="inlineStr"><is><t>SYN value</t></is></c></row><row r="7"><c r="B7"><v>2030</v></c><c r="D7"><f>D9</f><v>7</v></c></row><row r="8"/><row r="9"><c r="A9" t="inlineStr"><is><t>Q1</t></is></c><c r="B9"><v>2031</v></c><c r="C9" t="inlineStr"><is><t>SYN quarter</t></is></c><c r="D9"><v>9</v></c></row><row r="10"><c r="A10" t="inlineStr"><is><t>Q2*</t></is></c><c r="C10" t="inlineStr"><is><t>SYN quarter</t></is></c><c r="D10"><v>11</v></c></row><row r="11"><c r="A11" t="inlineStr"><is><t>*Primary Data</t></is></c><c r="D11" t="inlineStr"><is><t>*بيانات أولية</t></is></c></row></sheetData><mergeCells><mergeCell ref="A6:C6"/></mergeCells></worksheet>',
            )
        return dec, stream.getvalue()


def test_workbook_coordinates_cached_formula_carry():
    dec, body = workbook()
    rows = parse_body(body, entry(dec, "insurance_tables"), dec)
    assert [r["period"] for r in rows] == ["2030", "2031-Q1", "2031-Q2"]
    assert rows[0]["value"] == "7"
    assert rows[-1]["preliminary"] == "true"


@pytest.mark.parametrize(
    "plant",
    [
        "non_workbook",
        "sheet",
        "part",
        "header",
        "merge",
        "range",
        "carry",
        "missing_cached",
    ],
)
def test_workbook_plants(plant):
    dec, body = workbook()
    sheet = dec["shape"]["sheets"][0]
    if plant == "non_workbook":
        body = b"SYN not a workbook"
    if plant == "sheet":
        sheet["name"] = "SYN missing"
    if plant == "part":
        sheet["part"] = "xl/worksheets/sheet1.xml"
    if plant == "header":
        sheet["header_cells"]["D6"] = "SYN changed"
    if plant == "merge":
        sheet["merged_cells"] = []
    if plant == "range":
        sheet["annual_rows"] = [7, 8]
    if plant == "carry":
        sheet["carry_year"] = "SYN guessed"
    if plant == "missing_cached":
        source = ZipFile(io.BytesIO(body))
        out = io.BytesIO()
        with source, ZipFile(out, "w") as z:
            for name in source.namelist():
                z.writestr(
                    name, source.read(name).replace(b"<f>D9</f><v>7</v>", b"<f>D9</f>")
                )
        body = out.getvalue()
    with pytest.raises(ValueError, match="schema_missing"):
        parse_body(body, entry(dec, "insurance_tables"), dec)


def test_v2_lineage_dates_and_selection(tmp_path):
    from eii_custodian.publicdata.fetch.page_records import selected_page

    dec, body, _ = embedded()
    body += b'<input name="__RequestVerificationToken" value="SYN form credential">'
    result = fetch_page(
        entry(dec),
        lambda u: Response(u, body, ()),
        tmp_path,
        lambda: STAMP,
        lambda _: None,
        declaration=dec,
    )
    assert all(
        b"SYN form credential" not in path.read_bytes()
        for path in tmp_path.rglob("*")
        if path.is_file()
    )
    payload = json.loads(result.body)
    assert payload["as_of"] == STAMP[:10]
    assert (
        payload["period_first"] == "2031-02-03"
        and payload["period_last"] == "2031-02-04"
    )
    assert payload["publisher_date"] is None
    assert len(payload["inputs"]) == 1 and payload["inputs"][0]["extension"] == "html"
    (tmp_path / "snapshot_pins.json").write_text(
        json.dumps({entry(dec).key: result.sha256})
    )
    assert selected_page(tmp_path, entry(dec)).sha256 == result.sha256
    from eii_custodian.publicdata.fetch.snapshots import read_snapshot

    raw = tmp_path / entry(dec).key / "inputs" / "input-0"
    input_snapshot = read_snapshot(raw, payload["inputs"][0]["identity"])
    assert input_snapshot.sidecar["row_count"] is None
    index = json.loads(next((raw / "index").glob("*.json")).read_text())
    (raw / index["path"]).write_bytes(b"SYN tamper")
    with pytest.raises(ValueError, match="snapshot_hash_mismatch"):
        selected_page(tmp_path, entry(dec))


def test_supplier_refusal_without_connection(tmp_path):
    from eii_custodian.publicdata.fetch.page_records import load_declaration
    from eii_custodian.publicdata.fetch.registry import load_registry

    row = next(r for r in load_registry() if r.source_id == "suppliers_tawteen")
    dec = load_declaration(row.source_id)
    calls = []
    with pytest.raises(ValueError, match="anonymous_access_not_approved"):
        fetch_page(
            row,
            lambda u: calls.append(u),
            tmp_path,
            lambda: STAMP,
            lambda _: None,
            declaration=dec,
        )
    assert calls == []
    receipts = list((tmp_path / row.key / "failures" / "index").glob("*.json"))
    assert len(receipts) == 1
    assert b"2026-11-17T23:09:19Z" in b"".join(
        p.read_bytes() for p in (tmp_path / row.key / "failures").rglob("*.json")
    )


def test_contractor_certificate_date_is_row_fact():
    dec, body = classified()
    section = dec["shape"]["sections"][0]
    section.update(heading="SYN contractor", date_in_heading=False)
    body = body.replace(
        b"SYN supplier - expiry: 03/02/2031", b"SYN contractor"
    ).replace(b"<td>SYN grade</td>", b"<td>03/02/2031</td>")
    rows = parse_body(body, entry(dec, "monaqasat_classified"), dec)
    assert rows[0]["activities"][0]["expiry"] == "2031-02-03"
    with pytest.raises(ValueError, match="schema_missing"):
        parse_body(
            body.replace(b"03/02/2031", b"SYN invalid"),
            entry(dec, "monaqasat_classified"),
            dec,
        )


def test_embedded_preserves_reviewed_record_shape():
    dec, body, record = embedded()
    rows = parse_body(body, entry(dec), dec)
    assert rows[0]["published_record"] == record


@pytest.mark.parametrize("role", ["input", "index"])
def test_selected_input_symlink_refuses_before_read(tmp_path, monkeypatch, role):
    from eii_custodian.publicdata.fetch import page_records

    dec, body, _ = embedded()
    cache = tmp_path / "SYN-cache"
    result = fetch_page(
        entry(dec),
        lambda u: Response(u, body, ()),
        cache,
        lambda: STAMP,
        lambda _: None,
        declaration=dec,
    )
    (cache / "snapshot_pins.json").write_text(
        json.dumps({entry(dec).key: result.sha256})
    )
    raw = cache / entry(dec).key / "inputs/input-0"
    target = raw if role == "input" else raw / "index"
    outside = tmp_path / "SYN-outside"
    target.rename(outside)
    target.symlink_to(outside, target_is_directory=True)
    before = {
        str(p.relative_to(outside)): p.read_bytes()
        for p in outside.rglob("*")
        if p.is_file()
    }
    original = page_records.read_snapshot
    calls = []

    def read(directory, identity):
        calls.append(directory)
        assert directory != raw, "SYN attempted input read through a symlink"
        return original(directory, identity)

    monkeypatch.setattr(page_records, "read_snapshot", read)
    with pytest.raises(ValueError, match="cache_path_refused"):
        page_records.selected_page(cache, entry(dec))
    assert calls == [cache / entry(dec).key]
    assert before == {
        str(p.relative_to(outside)): p.read_bytes()
        for p in outside.rglob("*")
        if p.is_file()
    }
