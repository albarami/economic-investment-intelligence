"""Decision 0117: invented financial-centre event rows only."""

from datetime import date

import pytest
from custodian.tests.test_register_tables import _stage
from custodian.tests.test_registers import csv_bytes, fc, geocode, inputs
from hypothesis import given, settings
from hypothesis import strategies as st

from eii_custodian.publicdata.registers.bundle import BUNDLE, PIN, load_bundle
from eii_custodian.publicdata.registers.contracts import RegisterError
from eii_custodian.publicdata.registers.parse import InputAudit, parse
from eii_custodian.publicdata.registers.provenance import Frame

FRAME = Frame(frozenset())


def event(text="SYN notice", notice=""):
    return dict(qfc_number="65432", event=text, notice_expiration_date=notice)


def files_with_events(events):
    files = inputs("fc_register")
    files["events"] = csv_bytes("events", events)
    return files


def selected_card(events, audit=None):
    return parse("fc_register", files_with_events(events), FRAME, audit=audit)[0]


def test_identical_event_rows_collapse_to_one():
    audit = InputAudit()
    card = selected_card(
        [event(notice="2027-01-02"), event(notice="2027-01-02")], audit
    )
    assert card["event"] == "SYN notice"
    assert card["notice_expiration_date"] == "2027-01-02"
    assert audit.event_conflict_absences == 0


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
def test_distinct_events_on_the_winning_date_are_withheld(notice):
    control = [event("SYN first", notice), event("SYN second", "2027-02-03")]
    assert selected_card(control)["event"] == "SYN second"

    audit = InputAudit()
    planted = [event("SYN first", notice), event("SYN second", notice)]
    card = selected_card(planted, audit)
    assert card["event"] is None
    assert card["notice_expiration_date"] is None
    assert audit.event_conflict_absences == 1


def test_older_date_conflict_does_not_withhold_the_later_event():
    audit = InputAudit()
    card = selected_card(
        [
            event("SYN first", "2027-01-02"),
            event("SYN second", "2027-01-02"),
            event("SYN later", "2027-02-03"),
        ],
        audit,
    )
    assert card["event"] == "SYN later"
    assert card["notice_expiration_date"] == "2027-02-03"
    assert audit.event_conflict_absences == 0


def test_event_conflict_absence_reaches_release_coverage(tmp_path):
    files = files_with_events([event("SYN first"), event("SYN second")])
    _stage(tmp_path, tmp_path / "stage", FRAME, fc_files=files)
    bundle = load_bundle(tmp_path / BUNDLE, tmp_path / PIN, FRAME.cells)
    assert bundle.manifest["field_absences"] == [
        {
            "source_id": "fc_register",
            "period": "2026-11",
            "use": "current",
            "field": "event",
            "reason": "published_event_conflict",
            "count": 1,
        }
    ]
    card = next(
        row
        for row in bundle.tables["pub_register_company"]
        if row["source_id"] == "fc_register"
    )
    assert card["event"] is None
    assert card["notice_expiration_date"] is None


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
    by_date = {}
    for text, notice in set(rows):
        by_date.setdefault(notice, set()).add(text)
    winning_date = None
    conflict = False
    expected = None
    if by_date:
        winning_date = max(
            by_date,
            key=lambda notice: (
                notice is not None,
                date.fromisoformat(notice) if notice is not None else date.min,
            ),
        )
        conflict = len(by_date[winning_date]) > 1
        if not conflict:
            expected = next(iter(by_date[winning_date]))
    for ordered in (rows, permutation):
        events = [event(text, notice or "") for text, notice in ordered]
        audit = InputAudit()
        card = selected_card(events, audit)
        assert card["event"] == expected
        assert card["notice_expiration_date"] == (None if conflict else winning_date)
        assert audit.event_conflict_absences == int(conflict)
