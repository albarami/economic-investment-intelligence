"""Decision 0117: invented financial-centre event rows only."""

from datetime import date

import pytest
from custodian.tests.test_registers import csv_bytes, fc, geocode, inputs
from hypothesis import given, settings
from hypothesis import strategies as st

from eii_custodian.publicdata.registers.contracts import RegisterError
from eii_custodian.publicdata.registers.parse import parse
from eii_custodian.publicdata.registers.provenance import Frame

FRAME = Frame(frozenset())


def event(text="SYN notice", notice=""):
    return dict(qfc_number="65432", event=text, notice_expiration_date=notice)


def files_with_events(events):
    files = inputs("fc_register")
    files["events"] = csv_bytes("events", events)
    return files


def selected_card(events):
    return parse("fc_register", files_with_events(events), FRAME)[0]


def test_identical_event_rows_collapse_to_one():
    card = selected_card([event(notice="2027-01-02"), event(notice="2027-01-02")])
    assert card["event"] == "SYN notice"
    assert card["notice_expiration_date"] == "2027-01-02"


@pytest.mark.parametrize("reverse", [False, True], ids=["forward", "reversed"])
def test_later_event_date_wins_in_either_row_order(reverse):
    events = [
        event("SYN earlier", "2027-01-02"),
        event("SYN later", "2027-02-03"),
    ]
    if reverse:
        events.reverse()
    card = selected_card(events)
    assert card["event"] == "SYN later"
    assert card["notice_expiration_date"] == "2027-02-03"


@pytest.mark.parametrize("reverse", [False, True], ids=["forward", "reversed"])
def test_dated_event_wins_over_undated_in_either_row_order(reverse):
    events = [event("SYN undated"), event("SYN dated", "2027-01-02")]
    if reverse:
        events.reverse()
    card = selected_card(events)
    assert card["event"] == "SYN dated"
    assert card["notice_expiration_date"] == "2027-01-02"


@pytest.mark.parametrize("notice", ["2027-01-02", ""], ids=["dated", "undated"])
def test_distinct_events_with_the_same_date_refuse(notice):
    control = [event("SYN first", notice), event("SYN second", "2027-02-03")]
    assert selected_card(control)["event"] == "SYN second"
    planted = [event("SYN first", notice), event("SYN second", notice)]
    with pytest.raises(RegisterError, match=r"^duplicate_registration_key$"):
        selected_card(planted)


def test_minimum_calendar_date_still_wins_over_undated():
    card = selected_card([event("SYN undated"), event("SYN earliest", "0001-01-01")])
    assert card["event"] == "SYN earliest"
    assert card["notice_expiration_date"] == "0001-01-01"


@pytest.mark.parametrize("role", ["companies", "geocoded"])
def test_non_event_companion_duplicates_still_refuse(role):
    files = inputs("fc_register")
    rows = [fc(), fc()] if role == "companies" else [geocode(), geocode()]
    files[role] = csv_bytes(role, rows)
    with pytest.raises(RegisterError, match=r"^duplicate_registration_key$"):
        parse("fc_register", files, FRAME)


EVENT_ROWS = st.tuples(
    st.sampled_from(["SYN alpha", "SYN beta", "SYN gamma"]),
    st.one_of(
        st.none(),
        st.dates(min_value=date(2020, 1, 1), max_value=date(2030, 12, 31)).map(
            date.isoformat
        ),
    ),
)


@given(rows=st.lists(EVENT_ROWS, max_size=8), data=st.data())
@settings(max_examples=50, deadline=None)
def test_event_selection_matches_date_oracle_for_every_row_order(rows, data):
    permutation = data.draw(st.permutations(rows))
    distinct = set(rows)
    dates = [notice for _, notice in distinct]
    ambiguous = len(dates) != len(set(dates))
    expected = None
    if distinct and not ambiguous:
        expected = max(
            distinct,
            key=lambda row: (
                row[1] is not None,
                date.fromisoformat(row[1]) if row[1] is not None else date.min,
            ),
        )[0]
    for ordered in (rows, permutation):
        events = [event(text, notice or "") for text, notice in ordered]
        if ambiguous:
            with pytest.raises(RegisterError, match=r"^duplicate_registration_key$"):
                selected_card(events)
        else:
            assert selected_card(events)["event"] == expected
