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


@pytest.mark.parametrize("notice", ["2027-01-02", ""], ids=["dated", "undated"])
def test_conflicting_orphan_group_refuses_companion_keys(notice):
    control = [event("SYN first", notice), event("SYN second", notice)]
    audit = InputAudit()
    assert selected_card(control, audit)["event"] is None
    assert audit.event_conflict_absences == 1

    orphan = [dict(row, qfc_number="65433") for row in control]
    with pytest.raises(RegisterError, match=r"^companion_keys$"):
        parse("fc_register", files_with_events(orphan), FRAME)


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


KNOWN_EVENT_KEYS = ("65432", "65433")
ORPHAN_EVENT_KEY = "65434"
EVENT_ROWS = st.tuples(
    st.sampled_from([*KNOWN_EVENT_KEYS, ORPHAN_EVENT_KEY]),
    st.sampled_from(["SYN alpha", "SYN beta", "SYN gamma"]),
    st.one_of(
        st.none(),
        st.dates(min_value=date(2020, 1, 1), max_value=date(2030, 12, 31)).map(
            date.isoformat
        ),
    ),
)


@pytest.mark.parametrize(
    "events",
    [
        [dict(event("SYN alpha", "2027-01-02"), qfc_number=ORPHAN_EVENT_KEY)],
        [dict(event("SYN alpha"), qfc_number=ORPHAN_EVENT_KEY)],
        [
            dict(event("SYN alpha", "2027-01-02"), qfc_number=ORPHAN_EVENT_KEY),
            dict(event("SYN alpha", "2027-01-02"), qfc_number=ORPHAN_EVENT_KEY),
        ],
        [dict(event("SYN alpha"), qfc_number=ORPHAN_EVENT_KEY)] * 2,
        [
            dict(event("SYN alpha", "2027-01-02"), qfc_number=ORPHAN_EVENT_KEY),
            dict(event("SYN beta", "2027-01-02"), qfc_number=ORPHAN_EVENT_KEY),
        ],
        [
            dict(event("SYN alpha"), qfc_number=ORPHAN_EVENT_KEY),
            dict(event("SYN beta"), qfc_number=ORPHAN_EVENT_KEY),
        ],
        [
            event("SYN known", "2027-01-02"),
            dict(event("SYN orphan", "2027-02-03"), qfc_number=ORPHAN_EVENT_KEY),
        ],
    ],
    ids=[
        "singleton-dated",
        "singleton-undated",
        "identical-pair-dated",
        "identical-pair-undated",
        "differing-pair-dated",
        "differing-pair-undated",
        "known-company-beside-orphan",
    ],
)
def test_orphan_event_shapes_refuse_before_conflict_counting(events):
    for ordered in (events, list(reversed(events))):
        audit = InputAudit()
        with pytest.raises(RegisterError, match=r"^companion_keys$"):
            selected_card(ordered, audit)
        assert audit.event_conflict_absences == 0


@given(rows=st.lists(EVENT_ROWS, max_size=8), data=st.data())
@settings(max_examples=50, deadline=None)
def test_event_selection_matches_date_oracle_for_every_row_order(rows, data):
    permutation = data.draw(st.permutations(rows))
    expected = {}
    expected_absences = 0
    for number in KNOWN_EVENT_KEYS:
        by_date = {}
        for row_number, text, notice in set(rows):
            if row_number == number:
                by_date.setdefault(notice, set()).add(text)
        winning_date = None
        conflict = False
        selected_text = None
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
                selected_text = next(iter(by_date[winning_date]))
        expected[number] = (selected_text, None if conflict else winning_date)
        expected_absences += int(conflict)

    has_orphan = any(number == ORPHAN_EVENT_KEY for number, _, _ in rows)
    files = inputs("fc_register", [fc(), fc("65433", row_key="cccccccccccccccccccc")])
    files["geocoded"] = csv_bytes(
        "geocoded",
        [geocode(), geocode("65433", row_key="cccccccccccccccccccc")],
    )
    for ordered in (rows, permutation):
        events = [
            dict(event(text, notice or ""), qfc_number=number)
            for number, text, notice in ordered
        ]
        files["events"] = csv_bytes("events", events)
        audit = InputAudit()
        if has_orphan:
            with pytest.raises(RegisterError, match=r"^companion_keys$"):
                parse("fc_register", files, FRAME, audit=audit)
            assert audit.event_conflict_absences == 0
            continue
        cards = {
            card["registration_number"]: card
            for card in parse("fc_register", files, FRAME, audit=audit)
        }
        for number, (selected_text, notice) in expected.items():
            assert cards[number]["event"] == selected_text
            assert cards[number]["notice_expiration_date"] == notice
        assert audit.event_conflict_absences == expected_absences
