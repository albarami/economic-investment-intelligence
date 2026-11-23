"""S2-T08 part B, mismatch class 5: museum measure text outside the reviewed forms.

L-1141 supplies the four exact missing-note forms, bound to the lead's public
export hash in the S2-LR3F brief. Counts, venue names and rows here are invented.
A reviewed missing cell is counted and omitted, never read as zero; every
unreviewed text retains the named refusal ``measure_unparsed``.
"""

from __future__ import annotations

from dataclasses import replace
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
from eii_custodian.publicdata.additions.common import (
    AdditionError,
    MeasureKind,
    read_measure,
)
from eii_custodian.publicdata.additions.property_venues import (
    missing_forms_for,
    parse_health_centres,
    parse_museum,
)
from eii_custodian.publicdata.fetch.kinds import _measure_failure

KEY = "visits_museum/visitors-of-museums-and-exhibition-by-month-and-museum"
URL = "https://invented.test/museum"
CLOSURE_NOTES = (
    "مغلق",
    "مغلق للتجديد Closed of Renovation",
    "مغلق للتجديد Closed For Renovation",
    "يفتح للزوار الرسميين Only Open ToOfficial Visitors",
)
REVIEWED_FORMS = ("-", "--", *CLOSURE_NOTES)
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


def _parse(
    folder: Path,
    rows: list[dict[str, object]],
    field_map: dict[str, object],
    *,
    field: str = "number",
):
    entry = _entry("visits_museum")
    entry = replace(
        entry,
        columns=tuple(
            (field if name == "number" else name, kind) for name, kind in entry.columns
        ),
    )
    return parse_museum(
        entry,
        rows,
        {"retrieved_utc": "2026-03-04T05:06:07Z", "sha256": "ab" * 32},
        field_map,
        {"frame": folder, "review": folder, "venues": _venues(folder, _LINKS)},
    )


@pytest.mark.parametrize("value", ["7", NOTE])
def test_parser_reads_the_yaml_declared_measure_field(
    tmp_path: Path, value: str
) -> None:
    # INVENTED renamed source field and cells; no production mapping changes.
    field_map = _reviewed(_field_map(), NOTE)
    field_map["missing_measures"][KEY]["field"] = "syn_visits"  # type: ignore[index]
    source_row = _museum_row()
    source_row.pop("number")
    source_row["syn_visits"] = value
    parsed = _parse(tmp_path, [source_row], field_map, field="syn_visits")
    assert [row["value"] for row in parsed.rows] == ([7] if value == "7" else [])
    assert _coverage(parsed, "missing_measure") == (0 if value == "7" else 1)


@pytest.mark.parametrize("text", [" ", "  ", "\t", "\n", "\u00a0"])
@pytest.mark.parametrize("stage", ["fetch", "build"])
def test_whitespace_only_cell_is_refused_at_fetch_and_build(
    tmp_path: Path, text: str, stage: str
) -> None:
    # INVENTED cells: whitespace is not one of the exact reviewed missing forms.
    if stage == "build":
        with pytest.raises(AdditionError, match=r"^measure_unparsed$"):
            _parse(tmp_path, [_museum_row(number=text)], _field_map())
    else:
        failure = _measure_failure(_entry("visits_museum"), [{"number": text}], URL)
        assert failure is not None
        assert failure.check == "measure_unparsed"


@pytest.mark.parametrize("field", [None, "", 7, []])
def test_invalid_yaml_measure_field_is_refused(tmp_path: Path, field: object) -> None:
    # INVENTED malformed configuration: never fall back to the literal number.
    field_map = _field_map()
    field_map["missing_measures"][KEY]["field"] = field  # type: ignore[index]
    with pytest.raises(AdditionError, match=r"^field_map_unreadable$"):
        _parse(tmp_path, [_museum_row()], field_map)


@pytest.mark.parametrize("value", [None, ""])
def test_null_and_empty_cells_stay_missing(tmp_path: Path, value: object) -> None:
    parsed = _parse(tmp_path, [_museum_row(number=value)], _field_map())
    assert parsed.rows == ()
    assert _coverage(parsed, "missing_measure") == 1


def test_the_reviewed_forms_are_exact_and_scoped_to_number() -> None:
    assert missing_forms_for(KEY) == ("number", frozenset(REVIEWED_FORMS))
    item = _field_map()["missing_measures"][KEY]  # type: ignore[index]
    assert item["forms"] == list(REVIEWED_FORMS)
    assert "unconfirmed" not in item


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


@pytest.mark.parametrize(
    "text",
    [
        "Arabic word for closed; the inventory counts 4 rows and does not quote the word",
        "closed-for-renovation note, two English spellings; the inventory counts 4 rows",
        "open-to-official-visitors-only note; the inventory counts 1 row",
    ],
    ids=["first", "second", "third"],
)
def test_the_unconfirmed_descriptions_themselves_are_refused(text: str) -> None:
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


def test_source_reviewed_forms_preserve_counts_and_period_coverage(
    tmp_path: Path,
) -> None:
    rows = [
        _museum_row(month="January", number="7"),
        _museum_row(month="February", number=CLOSURE_NOTES[0]),
        _museum_row(month="March", number=CLOSURE_NOTES[1]),
        _museum_row(month="April", number=CLOSURE_NOTES[2]),
        _museum_row(month="May", number=CLOSURE_NOTES[3]),
        _museum_row(month="June", number="-"),
        _museum_row(month="July", number="--"),
        _museum_row(month="August", number="0"),
        _museum_row(month="September", number=CLOSURE_NOTES[0]),
    ]
    assert _measure_failure(_entry("visits_museum"), rows, URL) is None
    parsed = _parse(tmp_path, rows, _field_map())
    assert [(row["period"], row["value"]) for row in parsed.rows] == [
        ("2024-01", 7),
        ("2024-08", 0),
    ]
    assert _coverage(parsed, "missing_measure") == 7
    assert (parsed.period_first, parsed.period_last) == ("2024-01", "2024-09")


@pytest.mark.parametrize("text", REVIEWED_FORMS)
def test_source_reviewed_cell_has_no_number_or_value_row(
    tmp_path: Path, text: str
) -> None:
    measure = read_measure(text, missing_forms=frozenset(REVIEWED_FORMS), integral=True)
    assert measure.kind is MeasureKind.MISSING
    assert measure.number is None
    parsed = _parse(tmp_path, [_museum_row(number=text)], _field_map())
    assert parsed.rows == ()
    assert _coverage(parsed, "missing_measure") == 1
    assert (parsed.period_first, parsed.period_last) == ("2024-01", "2024-01")


@pytest.mark.parametrize(
    "text",
    [
        "مفتوح",
        *(note + " " for note in CLOSURE_NOTES),
        *(" " + note for note in CLOSURE_NOTES),
        "مغلق  للتجديد Closed of Renovation",
        "مغلق للتجديد Closed  For Renovation",
        "يفتح للزوار الرسميين Only Open To Official Visitors",
    ],
)
def test_source_note_unknown_text_and_space_changes_are_refused(
    tmp_path: Path, text: str
) -> None:
    failure = _measure_failure(_entry("visits_museum"), [{"number": text}], URL)
    assert failure is not None
    assert (failure.check, failure.expected, failure.observed) == (
        "measure_unparsed",
        "number",
        "measure_unparsed",
    )
    with pytest.raises(AdditionError) as refused:
        _parse(tmp_path, [_museum_row(number=text)], _field_map())
    assert refused.value.name == "measure_unparsed"


@pytest.mark.parametrize("text", CLOSURE_NOTES)
def test_source_note_does_not_apply_to_another_registry_key_or_field(
    tmp_path: Path, text: str
) -> None:
    assert missing_forms_for("visits_museum/SYN-other-slug") is None
    entry = _entry("visits_phcc")
    assert missing_forms_for(entry.key) is None
    links = _venues(
        tmp_path,
        f"{entry.key},SYN Centre,venue:visits_phcc:1,,reviewer,2026-01-02\n",
    )
    with pytest.raises(AdditionError) as refused:
        parse_health_centres(
            entry,
            [
                {
                    "health_center_name": "SYN Centre",
                    "region": "SYN Region",
                    "2020": text,
                }
            ],
            {"retrieved_utc": "2026-03-04T05:06:07Z", "sha256": "ab" * 32},
            _field_map(),
            {"venues": links},
        )
    assert refused.value.name == "measure_unparsed"
