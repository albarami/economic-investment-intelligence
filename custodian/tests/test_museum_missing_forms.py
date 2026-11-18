"""S2-T08 part B, mismatch class 5: museum measure text outside the reviewed forms.

The live shape pack's Mismatches item 5 shows the museum export's ``number``
field holding notes that the reviewed list does not name; the review file keeps
them as descriptions under ``unconfirmed`` without their exact spelling. Until
the lead supplies hash-bound exact spellings, such text keeps the named refusal
``measure_unparsed``. Once a form is reviewed, a row holding it is omitted and
counted, never read as zero. Every note below is invented; no real spelling is
written here.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from custodian.tests.test_additions_property_venues import (
    _LINKS,
    _coverage,
    _entry,
    _field_map,
    _museum_row,
    _venues,
)

from eii_custodian.publicdata.additions import property_venues
from eii_custodian.publicdata.additions.common import AdditionError
from eii_custodian.publicdata.additions.property_venues import (
    missing_forms_for,
    parse_museum,
)
from eii_custodian.publicdata.fetch.kinds import _measure_failure

KEY = "visits_museum/visitors-of-museums-and-exhibition-by-month-and-museum"
URL = "https://invented.test/museum"
# An invented note standing for a reviewed exact spelling; it is not a real one.
NOTE = "SYN closed note"
NEAR = {
    "trailing_space": NOTE + " ",
    "leading_space": " " + NOTE,
    "case_folded": NOTE.lower(),
    "letter_changed": "SYN closet note",
    "double_space": "SYN closed  note",
    "dash_spaced": "- ",
    "three_dashes": "---",
    "en_dash": "\u2013",
    "word_closed": "closed",
    "zero_word": "zero",
}


def _reviewed(field_map: dict[str, object], *forms: str) -> dict[str, object]:
    block = dict(field_map["missing_measures"])  # type: ignore[call-overload]
    item = dict(block[KEY])
    item["forms"] = [*item["forms"], *forms]
    block[KEY] = item
    return {**field_map, "missing_measures": block}


def _parse(folder: Path, rows: list[dict[str, object]], field_map: dict[str, object]):
    return parse_museum(
        _entry("visits_museum"),
        rows,
        {"retrieved_utc": "2026-03-04T05:06:07Z", "sha256": "ab" * 32},
        field_map,
        {"frame": folder, "review": folder, "venues": _venues(folder, _LINKS)},
    )


def test_the_reviewed_forms_stay_the_two_dashes() -> None:
    assert missing_forms_for(KEY) == ("number", frozenset({"-", "--"}))
    item = _field_map()["missing_measures"][KEY]  # type: ignore[index]
    assert item["forms"] == ["-", "--"]
    # The unconfirmed texts are descriptions for the lead, never admitted forms.
    assert len(item["unconfirmed"]) == 3
    assert not set(item["unconfirmed"]) & set(item["forms"])


def test_an_unreviewed_note_is_refused_at_the_fetch() -> None:
    failure = _measure_failure(
        _entry("visits_museum"), [{"number": "4"}, {"number": NOTE}], URL
    )
    assert failure is not None
    assert (failure.check, failure.expected, failure.observed) == (
        "measure_unparsed",
        "number",
        "measure_unparsed",
    )


@pytest.mark.parametrize("description", range(3), ids=["first", "second", "third"])
def test_the_unconfirmed_descriptions_themselves_are_refused(description: int) -> None:
    text = _field_map()["missing_measures"][KEY]["unconfirmed"][description]  # type: ignore[index]
    failure = _measure_failure(_entry("visits_museum"), [{"number": text}], URL)
    assert failure is not None
    assert failure.check == "measure_unparsed"


def test_a_reviewed_note_is_admitted_at_the_fetch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        property_venues,
        "missing_forms_for",
        lambda key: ("number", frozenset({"-", "--", NOTE})) if key == KEY else None,
    )
    rows: list[object] = [{"number": "4"}, {"number": NOTE}, {"number": "-"}]
    assert _measure_failure(_entry("visits_museum"), rows, URL) is None


@pytest.mark.parametrize("name", sorted(NEAR))
def test_a_near_spelling_of_a_reviewed_note_is_refused(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, name: str
) -> None:
    monkeypatch.setattr(
        property_venues,
        "missing_forms_for",
        lambda key: ("number", frozenset({"-", "--", NOTE})) if key == KEY else None,
    )
    failure = _measure_failure(_entry("visits_museum"), [{"number": NEAR[name]}], URL)
    assert failure is not None
    assert failure.check == "measure_unparsed"
    with pytest.raises(AdditionError) as refused:
        _parse(
            tmp_path / name,
            [_museum_row(number=NEAR[name])],
            _reviewed(_field_map(), NOTE),
        )
    assert refused.value.name == "measure_unparsed"


def test_an_unreviewed_note_stops_the_build(tmp_path: Path) -> None:
    with pytest.raises(AdditionError) as refused:
        _parse(tmp_path / "f", [_museum_row(number=NOTE)], _field_map())
    assert refused.value.name == "measure_unparsed"


def test_a_reviewed_note_is_omitted_and_counted_never_zero(tmp_path: Path) -> None:
    parsed = _parse(
        tmp_path / "f",
        [
            _museum_row(month="January", number="4"),
            _museum_row(month="February", number=NOTE),
            _museum_row(month="March", number="-"),
            _museum_row(month="April", number="0"),
        ],
        _reviewed(_field_map(), NOTE),
    )
    # Two omitted rows are counted; the published zero stays a zero; no note
    # becomes a zero and no omitted month has a row.
    assert _coverage(parsed, "missing_measure") == 2
    assert [row["value"] for row in parsed.rows] == [4, 0]
    assert len({row["period"] for row in parsed.rows}) == 2
