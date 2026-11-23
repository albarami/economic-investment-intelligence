"""S2-P66 round two: invented proofs, ruled date marker and declared headings."""

import copy
from html import escape

import pytest
from custodian.tests.test_award_page_states import (
    ABSENT,
    PROFILE,
    URL,
    intake,
    page,
    parsed,
    reader,
)
from hypothesis import example, given
from hypothesis import strategies as st

from eii_custodian.publicdata.fetch import awards
from eii_custodian.publicdata.fetch.award_checks import (
    AwardError,
    check_awards,
    validate_check_receipt,
)
from eii_custodian.publicdata.fetch.award_links import (
    ProofFetchError,
    check_all_awards,
    sample_from_links,
    valid_result,
    validate_links_receipt,
)
from eii_custodian.publicdata.fetch.page_records import PageError, load_declaration

MARKER = {"proof_date_status": "proof_date_absent"}


@pytest.mark.parametrize("date", ["", " \n\t ", "\xa0"])
def test_date_marker_survives_parser_reader_and_both_checkers(date):
    dec, body = page(dates=(date,))
    record = parsed(dec, body)[0]
    assert record["award_date"] is None
    assert record.items() >= MARKER.items()
    read = reader(dec, body)
    assert read(URL)[0].items() >= {"award_date": "", **MARKER}.items()
    check = check_all_awards([intake()], PROFILE, read)
    assert check["results"] == [
        {"report_url": URL, "result": "matched", "reason": "matched", **MARKER}
    ]
    assert check["proof_date_absent"] == check["matched"] == 1
    assert check["mismatched"] == check["failed_fetches"] == 0
    assert sample_from_links(check, 6667) == check_awards(
        [intake()], PROFILE, 6667, read
    )


@pytest.mark.parametrize(
    "field,value,reason",
    [
        ("SYN company", "SYN disagreement", "proof_mismatch"),
        ("SYN registration", "SYN disagreement", "proof_mismatch"),
        ("SYN amount", "9.00 QAR", "proof_mismatch"),
        ("SYN amount", "QAR", "intake_value_absent"),
    ],
)
def test_date_marker_does_not_replace_comparison_reason(field, value, reason):
    dec, body = page(dates=("",))
    row = dict(intake(), **{field: value})
    check = check_all_awards([row], PROFILE, reader(dec, body))
    assert check["results"] == [
        {"report_url": URL, "result": "mismatched", "reason": reason, **MARKER}
    ]
    assert check["proof_date_absent"] == check["mismatched"] == 1
    assert check["matched"] == check["failed_fetches"] == 0


def date_receipt():
    dec, body = page(dates=("",))
    check = check_all_awards([intake()], PROFILE, reader(dec, body))
    return {
        "source_id": "awards_owner_scrape",
        "award_check_scope": "sample",
        "award_links": check,
        "award_check": sample_from_links(check, 6667),
    }


def test_date_marker_receipt_passes_both_validators():
    side = date_receipt()
    validate_check_receipt(side)
    validate_links_receipt(side, [intake()])
    assert valid_result(side["award_links"]["results"][0])


@pytest.mark.parametrize("scope", ["award_links", "award_check"])
@pytest.mark.parametrize("change", ["mismatch", "missing", "boolean", "negative"])
def test_date_counter_mismatch_refuses(scope, change):
    side = date_receipt()
    if change == "missing":
        del side[scope]["proof_date_absent"]
    else:
        side[scope]["proof_date_absent"] = {
            "mismatch": 2,
            "boolean": True,
            "negative": -1,
        }[change]
    validate = (
        validate_links_receipt if scope == "award_links" else validate_check_receipt
    )
    with pytest.raises(AwardError, match=f"^{scope}_metadata_missing$"):
        validate(side)


@pytest.mark.parametrize("change", ["missing", "dated", "unknown", "no_date"])
@pytest.mark.parametrize("boundary", ["reader", "checker"])
def test_inconsistent_date_marker_refuses_one_change(monkeypatch, change, boundary):
    dec, body = page(dates=("03/02/2031" if change == "dated" else "",))
    record = parsed(dec, body)[0]
    # Start with the valid parser record; change just one field.
    if change == "missing":
        del record["proof_date_status"]
    elif change == "no_date":
        del record["award_date"]
    else:
        record["proof_date_status"] = (
            "SYN unknown" if change == "unknown" else "proof_date_absent"
        )
    if boundary == "reader":
        monkeypatch.setattr(awards, "parse_body", lambda *_: [record])
        with pytest.raises(AwardError, match=r"^schema_missing$"):
            reader(dec, body)(URL)
    else:
        proof = {
            key: "" if value is None else str(value) for key, value in record.items()
        }
        check = check_all_awards([intake()], PROFILE, lambda _: proof)
        assert check["results"] == [
            {"report_url": URL, "result": "refused", "reason": "schema_missing"}
        ]


@pytest.mark.parametrize("scope", ["award_links", "award_check"])
@pytest.mark.parametrize(
    "change", ["unknown", "missing", "fetch_failed", "award_absent"]
)
def test_receipt_date_marker_is_closed(scope, change):
    side = date_receipt()
    if change in {"fetch_failed", "award_absent"}:

        def read(_):
            if change == "fetch_failed":
                raise ProofFetchError("unreachable")
            return ABSENT

        side["award_links"] = check_all_awards([intake()], PROFILE, read)
        side["award_check"] = sample_from_links(side["award_links"], 6667)
    item = side[scope]["results"][0]
    # Each starting result is valid; mutate only its marker field.
    assert valid_result(item) is True
    if change == "missing":
        del item["proof_date_status"]
    else:
        item["proof_date_status"] = (
            "SYN unknown" if change == "unknown" else "proof_date_absent"
        )
        assert valid_result(item) is False
    validate = (
        validate_links_receipt if scope == "award_links" else validate_check_receipt
    )
    with pytest.raises(AwardError, match=f"^{scope}_metadata_missing$"):
        validate(side)


@pytest.mark.parametrize("selection", [0, 1, 2, 3, "all"])
def test_production_reviewed_headings_on_invented_pages(selection):
    dec = load_declaration("awards_owner_scrape")
    sections = dec["shape"]["sections"]
    assert len(sections) == 4
    chosen = sections if selection == "all" else [sections[selection]]
    body = (
        '<div><span id="lblAwardedDate">99/99/9999</span>'
        + "".join(f"<h3>{escape(section['heading'])}</h3>" for section in chosen)
        + "</div>"
    ).encode()
    assert parsed(dec, body) == [ABSENT]
    assert reader(dec, body)(URL) == [ABSENT]
    check = check_all_awards([intake()], PROFILE, reader(dec, body))
    assert check["results"] == [
        {"report_url": URL, "result": "mismatched", "reason": "proof_award_absent"}
    ]
    # Exactly one extra unreviewed heading; all other bytes stay valid.
    bad = body.replace(b"</div>", b"<h3>SYN unreviewed</h3></div>")
    with pytest.raises(PageError, match=r"^schema_missing$"):
        parsed(dec, bad)


@given(st.lists(st.tuples(st.booleans(), st.booleans()), max_size=40))
@example([])
@example([(True, False)])
@example([(True, True), (False, True), (True, False), (False, False)])
@example([(True, False)] * 30)
@example([(False, True)] * 31)
@example([(True, True), (False, False)] * 20)
def test_date_count_is_orthogonal_to_comparison(outcomes):
    rows = []
    proofs = {}
    for index, (absent, mismatch) in enumerate(outcomes):
        row = dict(intake(), report_url=URL + f"/{index}")
        rows.extend([row, copy.deepcopy(row)])  # Shared links count once.
        dec, body = page(dates=("" if absent else "03/02/2031",))
        proof = dict(reader(dec, body)(URL)[0])
        if mismatch:
            proof["SYN registration"] = "SYN disagreement"
        proofs[row["report_url"]] = proof
    check = check_all_awards(rows, PROFILE, proofs.__getitem__)
    assert check["proof_date_absent"] == sum(absent for absent, _ in outcomes)
    assert check["mismatched"] == sum(mismatch for _, mismatch in outcomes)
    assert check["matched"] + check["mismatched"] == len(outcomes)
    assert check["checked_count"] == len(outcomes)
    assert check["failed_fetches"] == 0
    assert sample_from_links(check, 6667) == check_awards(
        rows, PROFILE, 6667, proofs.__getitem__
    )
    side = {
        "source_id": "awards_owner_scrape",
        "award_check_scope": "sample",
        "award_links": check,
        "award_check": sample_from_links(check, 6667),
    }
    validate_links_receipt(side, rows)


def test_failed_fetch_does_not_carry_date_marker():
    def read(_):
        raise ProofFetchError("unreachable")

    check = check_all_awards([intake()], PROFILE, read)
    assert check["proof_date_absent"] == 0
    assert check["results"] == [
        {"report_url": URL, "result": "fetch_failed", "reason": "unreachable"}
    ]


def test_multiple_proof_rows_count_date_absence_once():
    dec, body = page(dates=("",))
    row_html = body.split(b"<tbody>")[1].split(b"</tbody>")[0]
    body = body.replace(b"</tbody>", row_html + b"</tbody>")
    read = reader(dec, body)
    assert len(read(URL)) == 2
    check = check_all_awards([intake()], PROFILE, read)
    assert check["proof_date_absent"] == check["matched"] == check["checked_count"] == 1
    assert check["results"][0].items() >= MARKER.items()


@pytest.mark.parametrize(
    "cells,reason,result",
    [
        (["SYN first", "SYN-reg", "", "", ""], "proof_value_absent", "mismatched"),
        (
            ["SYN Ж", "SYN-reg", "1,007.00 رق", "", ""],
            "matched_name_not_compared",
            "matched",
        ),
    ],
)
def test_other_comparison_outcomes_keep_the_date_marker(cells, reason, result):
    dec, body = page(dates=("",), cells=cells)
    check = check_all_awards([intake()], PROFILE, reader(dec, body))
    assert check["results"] == [
        {"report_url": URL, "result": result, "reason": reason, **MARKER}
    ]
    assert check["proof_date_absent"] == 1
