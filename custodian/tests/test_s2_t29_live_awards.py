"""Invented multi-winner proofs and malformed portal card nesting."""

import pytest
from custodian.tests.test_s2_t29_awards import profile, row
from custodian.tests.test_s2_t29_live_shapes import declaration, entry

from eii_custodian.publicdata.fetch.award_checks import check_awards
from eii_custodian.publicdata.fetch.page_records import parse_body


def report():
    cols = [
        ["SYN company", "string"],
        ["SYN registration", "string"],
        ["SYN amount", "number"],
        ["SYN result", "string"],
        ["SYN items", "string"],
    ]
    shape = dict(
        profile="awards",
        selector="table.custom--table",
        headers=["SYN awarded companies", *[c[0] for c in cols]],
        sections=[],
        total_selector="",
        total_prefix="",
        last_selector="",
        path_template="",
    )
    dec = declaration("html_table", shape, cols)
    table = (
        '<table class="custom--table"><thead><tr>'
        + "".join("<th>" + c[0] + "</th>" for c in cols)
        + "</tr></thead><tbody><tr><td>SYN first</td><td>SYN-reg</td><td>1,007.00 رق</td><td></td><td></td></tr><tr><td>SYN second</td><td>SYN-other</td><td>9.00 رق</td><td></td><td></td></tr></tbody></table>"
    )
    body = (
        '<div class="inner-page"><span id="lblAwardedDate">03/02/2031</span><h3>SYN awarded companies</h3><div class="custom--table--responsive">'
        + table
        + "</div><h3>SYN opened bids</h3><div>"
        + table.replace("SYN first", "SYN decoy")
        + "</div></div>"
    ).encode()
    return dec, body


def test_award_heading_and_multiple_winners():
    dec, body = report()
    parsed = parse_body(body, entry(dec, "awards_owner_scrape"), dec)
    assert len(parsed) == 2 and parsed[0]["SYN amount"] == "1007.00"
    assert parsed[0]["award_date"] == "2031-02-03"
    assert all(r["SYN company"] != "SYN decoy" for r in parsed)


@pytest.mark.parametrize("plant", ["heading", "zero", "date", "header", "extra_column"])
def test_award_shape_plants(plant):
    dec, body = report()
    if plant == "heading":
        body = body.replace(b"SYN awarded companies", b"SYN not awards")
    if plant == "date":
        body = body.replace(b"03/02/2031", b"SYN wrong date")
    if plant == "header":
        body = body.replace(b"<th>SYN result</th>", b"<th>SYN changed</th>")
    if plant == "extra_column":
        body = body.replace(
            b"<td>SYN first</td>", b"<td>SYN first</td><td>SYN extra</td>"
        )
    if plant == "zero":
        begin = body.index(b"<tbody>")
        end = body.index(b"</tbody>", begin) + len(b"</tbody>")
        body = body[:begin] + b"<tbody></tbody>" + body[end:]
    with pytest.raises(ValueError, match=r"schema_missing|snapshot_date_missing"):
        parse_body(body, entry(dec, "awards_owner_scrape"), dec)


def test_sample_matches_every_intake_winner_without_selecting_one():
    first = row()
    second = dict(row(), syn_company="SYN Other", syn_reg="SYN-other", syn_value="7")
    result = check_awards([first, second], profile(), 73, lambda _: [second, first])
    assert result["matched"] == 1 and result["mismatched"] == 0
    mismatch = check_awards([first, second], profile(), 73, lambda _: [first])
    assert mismatch["matched"] == 0 and mismatch["mismatched"] == 1


def test_award_list_div_inside_tr():
    from eii_custodian.publicdata.fetch.page_shapes import award_cards

    body = b'<div class="custom--table--responsive py-2"><table class="custom--table"><tbody><tr><div class="row custom-cards"><div class="col-md-7 cards-col"><div class="col-header"><span class="card-label"><label>SYN-2031</label></span></div><span class="card-title"><a href="/TendersOnlineServices/TenderDetails/SYN-a">SYN award</a></span><div class="cards-row"><span class="card-label"><label>\xd8\xaa\xd8\xa7\xd8\xb1\xd9\x8a\xd8\xae \xd8\xa7\xd9\x84\xd8\xaa\xd8\xb1\xd8\xb3\xd9\x8a\xd8\xa9</label></span><span class="card-title"><span><label>03/02/2031</label></span></span></div></div><div class="col-md-2 circle-container"><a class="btn btn-primary" href="/TendersOnlineServices/TenderCompaniesDetails/SYN-a">SYN report</a></div></div></tr></tbody></table></div>'
    result = award_cards(body)
    assert result == [
        {
            "number": "SYN-2031",
            "title": "SYN award",
            "award_date": "2031-02-03",
            "report_path": "/TendersOnlineServices/TenderCompaniesDetails/SYN-a",
        }
    ]


def test_awards_snapshot_date_is_retrieval_date(tmp_path):
    import json

    from custodian.tests.test_s2_t29_awards import STAMP

    from eii_custodian.publicdata.fetch.awards import AwardBatch, publish_awards
    from eii_custodian.publicdata.fetch.registry import load_registry

    row_entry = next(r for r in load_registry() if r.source_id == "awards_owner_scrape")
    batch = AwardBatch(
        (),
        {"completeness": "unknown", "date_first": None, "date_last": None},
        "SYN",
        b"SYN intake",
        "csv",
    )
    from eii_custodian.publicdata.fetch.receipts import sha256_hex

    batch = AwardBatch(
        batch.rows, batch.summary, sha256_hex(batch.body), batch.body, batch.extension
    )
    result = publish_awards(
        row_entry, tmp_path, batch, profile(), STAMP, 73, lambda _: [], []
    )
    assert result.sidecar["as_of"] == STAMP[:10]
    payload = json.loads(result.body)
    assert payload["as_of"] == STAMP[:10]
    assert payload["period_first"] is None and payload["period_last"] is None
