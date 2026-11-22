"""S2-P66 closed page states; every HTML body is invented locally."""

import copy
from html import escape

import pytest
from custodian.tests.test_s2_t29_live_awards import report
from custodian.tests.test_s2_t29_live_shapes import URL as SHAPE_URL
from custodian.tests.test_s2_t29_live_shapes import entry
from hypothesis import example, given
from hypothesis import strategies as st

from eii_custodian.publicdata.fetch import awards
from eii_custodian.publicdata.fetch.award_checks import (
    AwardError,
    check_awards,
    validate_check_receipt,
)
from eii_custodian.publicdata.fetch.award_links import (
    check_all_awards,
    sample_from_links,
    valid_result,
    validate_links_receipt,
)
from eii_custodian.publicdata.fetch.page_html import ShapeError
from eii_custodian.publicdata.fetch.page_records import PageError, parse_body
from eii_custodian.publicdata.fetch.page_shapes import awards as parse_awards
from eii_custodian.publicdata.fetch.receipts import sha256_hex

HEADINGS = (
    "SYN opened technically",
    "SYN opened financially",
    "SYN opened technically and financially",
    "SYN companies notice",
)
ABSENT = {"proof_outcome": "proof_award_absent"}
URL = SHAPE_URL + "/SYN-award-state"
PROFILE = {
    "company": "SYN company",
    "registration": "SYN registration",
    "value": "SYN amount",
    "proof_columns": {
        "company": "SYN company",
        "registration": "SYN registration",
        "value": "SYN amount",
    },
}


def page(headings=None, dates=("03/02/2031",), cells=None):
    dec, _ = report()
    dec["shape"]["sections"] = [
        {"heading": heading, "headers": [], "date_in_heading": False}
        for heading in HEADINGS
    ]
    dec["profile"] = PROFILE
    if headings is None:
        headings = [dec["shape"]["headers"][0]]
    if cells is None:
        cells = ["SYN first", "SYN-reg", "1,007.00 رق", "", ""]
    table = (
        '<div><table class="custom--table"><thead><tr>'
        + "".join(f"<th>{escape(c[0])}</th>" for c in dec["columns"])
        + "</tr></thead><tbody>"
        + (
            "<tr>" + "".join(f"<td>{escape(c)}</td>" for c in cells) + "</tr>"
            if cells
            else ""
        )
        + "</tbody></table></div>"
    )
    body = (
        "<div>"
        + "".join(f'<span id="lblAwardedDate">{escape(d)}</span>' for d in dates)
        + "".join(f"<h3>{escape(h)}</h3>{table}" for h in headings)
        + "</div>"
    ).encode()
    return dec, body


def parsed(dec, body):
    return parse_body(body, entry(dec, "awards_owner_scrape"), dec)


def intake():
    return {
        "report_url": URL,
        "SYN company": "SYN first",
        "SYN registration": "SYN-reg",
        "SYN amount": "1,007.00 QAR",
        "award_date": "2030-01-01",
    }


def reader(dec, body):
    class Store:
        def body(self, url, *, replay):
            assert url == URL and replay is True
            return body

    return awards._proof_reader(
        entry(dec, "awards_owner_scrape"),
        dec,
        Store(),
        frozenset({URL}),
        None,
        awards.ReaderPool(),
        None,
        lambda _: None,
    )


@pytest.mark.parametrize(
    "headings", [HEADINGS[:2] + HEADINGS[3:], HEADINGS[2:], HEADINGS[3:]]
)
def test_no_award_section_is_closed_mismatch(headings):
    dec, body = page(headings, dates=("99/99/9999",))
    assert parsed(dec, body) == [ABSENT]
    read = reader(dec, body)
    check = check_all_awards([intake()], PROFILE, read)
    assert check["results"] == [
        {"report_url": URL, "result": "mismatched", "reason": "proof_award_absent"}
    ]
    assert check["proof_award_absent"] == 1
    assert check["incomplete"] is False
    assert sample_from_links(check, 66) == check_awards([intake()], PROFILE, 66, read)


@pytest.mark.parametrize("date", ["", " \n\t "])
def test_empty_awarded_date_is_null_and_not_compared(date):
    dec, body = page(dates=(date,))
    assert parsed(dec, body)[0]["award_date"] is None
    read = reader(dec, body)
    assert check_all_awards([intake()], PROFILE, read)["results"][0] == {
        "report_url": URL,
        "result": "matched",
        "reason": "matched",
    }


@pytest.mark.parametrize("field", ["SYN company", "SYN registration", "SYN amount"])
def test_empty_date_still_compares_declared_fields(field):
    dec, body = page(dates=("",))
    row = intake()
    row[field] = "SYN disagreement"
    assert check_all_awards([row], PROFILE, reader(dec, body))["results"][0] == {
        "report_url": URL,
        "result": "mismatched",
        "reason": "proof_mismatch",
    }


def test_reviewed_heading_text_can_be_split_across_elements():
    dec, body = page([HEADINGS[3]])
    body = body.replace(
        b"SYN companies notice</h3>", b" SYN <b>companies</b> notice </h3>"
    )
    assert parsed(dec, body) == [ABSENT]


def test_marker_requires_the_entire_closed_record():
    proof = dict(ABSENT, **{"SYN company": "SYN first"})
    assert check_all_awards([intake()], PROFILE, lambda _: proof)["results"][0] == {
        "report_url": URL,
        "result": "mismatched",
        "reason": "proof_value_absent",
    }


@pytest.mark.parametrize(
    "change",
    ["unknown", "prefix", "two_awards", "no_date", "two_dates"],
)
def test_no_award_exception_refuses_each_other_shape(change):
    headings, dates = list(HEADINGS[3:]), ("03/02/2031",)
    if change == "unknown":
        headings.append("SYN unknown heading")
    elif change == "prefix":
        headings = [HEADINGS[3] + " SYN suffix"]
    elif change == "two_awards":
        dec, _ = report()
        headings = [dec["shape"]["headers"][0]] * 2
    elif change == "no_date":
        dates = ()
    else:
        dates *= 2
    dec, body = page(headings, dates)
    with pytest.raises(PageError, match=r"^schema_missing$"):
        parsed(dec, body)


def test_malformed_nonempty_awarded_date_refuses():
    dec, body = page(dates=("99/99/9999",))
    with pytest.raises(PageError, match=r"^snapshot_date_missing$"):
        parsed(dec, body)


def test_empty_table_with_empty_date_refuses():
    dec, body = page(dates=("",), cells=[])
    with pytest.raises(PageError, match=r"^schema_missing$"):
        parsed(dec, body)


@pytest.mark.parametrize("change", ["no_sibling", "no_table", "currency"])
def test_existing_award_structure_and_value_refusals(change):
    dec, body = page()
    if change == "no_sibling":
        body = b'<div><span id="lblAwardedDate">03/02/2031</span><h3>SYN awarded companies</h3></div>'
    elif change == "no_table":
        body = body.replace(b'class="custom--table"', b'class="SYN-other"')
    else:
        body = body.replace("1,007.00 رق".encode(), b"SYN malformed")
    with pytest.raises(PageError, match=r"^schema_missing$"):
        parsed(dec, body)


@pytest.mark.parametrize("dates", [(), ("", "")])
def test_present_award_requires_exactly_one_date_span(dates):
    dec, body = page(dates=dates)
    with pytest.raises(PageError, match=r"^schema_missing$"):
        parsed(dec, body)


def receipt():
    check = check_all_awards([intake()], PROFILE, lambda _: ABSENT)
    return {
        "source_id": "awards_owner_scrape",
        "award_check_scope": "sample",
        "award_links": check,
        "award_check": sample_from_links(check, 66),
    }


def test_closed_absence_reason_passes_both_receipt_readers():
    side = receipt()
    assert side["award_links"]["results"][0]["reason"] == "proof_award_absent"
    assert valid_result(side["award_links"]["results"][0]) is True
    validate_check_receipt(side)
    validate_links_receipt(side, [intake()])


@pytest.mark.parametrize("scope", ["award_links", "award_check"])
def test_unknown_reason_refuses_each_receipt_reader(scope):
    side = receipt()
    side[scope]["results"][0]["reason"] = "SYN unknown reason"
    assert valid_result(side[scope]["results"][0]) is False
    validate = (
        validate_links_receipt if scope == "award_links" else validate_check_receipt
    )
    with pytest.raises(AwardError, match=f"^{scope}_metadata_missing$"):
        validate(side)


@pytest.mark.parametrize("scope", ["award_links", "award_check"])
def test_absence_counter_is_recomputed(scope):
    side = copy.deepcopy(receipt())
    side[scope]["proof_award_absent"] += 1
    validate = (
        validate_links_receipt if scope == "award_links" else validate_check_receipt
    )
    with pytest.raises(AwardError, match=f"^{scope}_metadata_missing$"):
        validate(side)


@given(
    st.lists(st.sampled_from(HEADINGS), max_size=8), st.integers(0, 2), st.booleans()
)
@example([], 1, True)
@example([], 1, False)
@example([HEADINGS[3]], 1, False)
@example([HEADINGS[3], HEADINGS[3]], 1, False)
def test_absence_shape_partition(headings, date_count, unknown):
    if unknown:
        headings = [*headings, "SYN unknown"]
    dec, body = page(headings, dates=("99/99/9999",) * date_count)
    if unknown or date_count != 1:
        with pytest.raises(ShapeError, match=r"^schema_missing$"):
            parse_awards(body, dec["shape"], dec["columns"])
    else:
        assert parse_awards(body, dec["shape"], dec["columns"]) == [ABSENT]


@given(st.lists(st.booleans(), max_size=40))
@example([])
@example([True])
@example([False, True, True, False])
def test_absence_counts_partition_the_checked_frame(outcomes):
    rows = [dict(intake(), report_url=URL + f"/{i}") for i in range(len(outcomes))]
    proof = dict(intake(), **{"SYN amount": "1007.00"})
    by_url = {
        row["report_url"]: absent for row, absent in zip(rows, outcomes, strict=True)
    }

    def read(url):
        return ABSENT if by_url[url] else proof

    check = check_all_awards(rows, PROFILE, read)
    assert check["proof_award_absent"] == outcomes.count(True)
    assert check["mismatched"] == outcomes.count(True)
    assert check["matched"] == outcomes.count(False)
    assert check["matched"] + check["mismatched"] == check["checked_count"]
    assert check["incomplete"] is (not outcomes)
    assert sample_from_links(check, 66) == check_awards(rows, PROFILE, 66, read)


@pytest.mark.parametrize("absent", [True, False])
def test_closed_states_publish_and_pass_assembly(tmp_path, absent):
    from eii_custodian.publicdata.assembly import AssemblyError
    from eii_custodian.publicdata.assembly_reports import awards_evidence

    dec, body = page(HEADINGS[3:] if absent else None, dates=("",))
    proof = reader(dec, body)(URL)
    rows = tuple(
        {
            "original": dict(intake(), report_url=URL + f"/{i}"),
            "retrieved_utc": "2031-02-03T00:00:00Z",
        }
        for i in range(30)
    )
    batch = awards.AwardBatch(rows, {}, sha256_hex(b"SYN intake"), b"SYN intake", "csv")
    snapshot = awards.publish_awards(
        entry(dec, "awards_owner_scrape"),
        tmp_path,
        batch,
        PROFILE,
        "2031-02-03T00:00:00Z",
        66,
        lambda _: proof,
        [],
    )
    summary = awards_evidence(snapshot.sidecar, 66)["award_links"]
    assert summary["proof_award_absent"] == (30 if absent else 0)
    assert summary["mismatched"] == (30 if absent else 0)
    assert summary["matched"] == (0 if absent else 30)
    assert summary["incomplete"] is False
    for scope in ("award_links", "award_check"):
        bad = copy.deepcopy(snapshot.sidecar)
        bad[scope]["results"][0]["reason"] = "SYN unknown reason"
        with pytest.raises(AssemblyError, match=r"^assembly_t29_refused$"):
            awards_evidence(bad, 66)
