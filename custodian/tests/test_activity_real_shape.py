"""Real export shapes for the licence feeds and the ISIC class file.

Fixtures use release columns and the series map. No value is taken from a source.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import pytest

from eii_custodian.publicdata.fetch.registry import load_registry
from eii_custodian.publicdata.fetch.snapshots import reviewed_selections
from eii_custodian.publicdata.review.activity import (
    ActivityRow,
    ClassRead,
    FeedRead,
    IsicClass,
    LeftOut,
    ReviewRow,
    SpineError,
    SupplierMembership,
    entry_by_key,
    load_activity_inputs,
    parse_feed_rows,
    parse_isic_rows,
    read_cached_classes,
    read_cached_feed,
    read_review_csv,
    release_field,
    spine_path,
    write_review_csv,
)
from eii_custodian.publicdata.review.cache_fixture import (
    class_csv,
    read_cached,
    read_rows,
    real_feed_body,
    write_cached,
)
from eii_custodian.publicdata.review.graph import build_graph
from eii_custodian.publicdata.series.parse import (
    FIELD_MAP,
    MONTH_FIELDS,
    NULLABLE,
)

ISIC_URL = (
    "https://unstats.un.org/unsd/classifications/Econ/Download/In%20Text/"
    "ISIC_Rev_4_english_structure.Txt"
)
_MARK = "EVIDENCE_ONLY:"
_NO_SUPPLIERS = SupplierMembership(codes=(), complete=True)
_MUNICIPALITY_A = "MUNI-ALPHA"
_MUNICIPALITY_B = "MUNI-BETA"
_MUNICIPALITY_C = "MUNI-GAMMA"
_YEAR = "2031"


def _entry(source_id: str):
    return entry_by_key(load_registry(), source_id)


def _source_field(feed: str, column: str) -> str:
    found = [
        name
        for name, (_table, release) in FIELD_MAP[feed].items()
        if release.removeprefix(_MARK) == column
    ]
    if len(found) != 1:
        raise AssertionError(column)
    return found[0]


def _period_fields(feed: str) -> tuple[str, str]:
    month = MONTH_FIELDS[feed]
    years = [name for name in NULLABLE[feed] if name != month]
    if len(years) != 1:
        raise AssertionError(feed)
    return years[0], month


def licence_row(feed: str, **logical: object) -> dict[str, object]:
    """One invented row whose keys are the real fields of ``feed``."""
    columns = {
        "activity_code": "activity_code",
        "activity_name_ar": "activity_name_ar",
        "active_count": "active_count",
        "cancelled_count": "cancelled_count",
        "municipality": "municipality_code",
    }
    row: dict[str, object] = {}
    year_name, month_name = (
        _period_fields(feed) if feed == "lic_cancelled" else ("", "")
    )
    for key, value in logical.items():
        if key in columns:
            row[_source_field(feed, columns[key])] = value
        elif key == "year":
            row[year_name] = value
        elif key == "month":
            row[month_name] = value
        else:
            row[key] = value
    return row


def active_row(
    code: str = "5610101",
    name: str = "مطعم",
    count: object = 10,
    municipality: str = _MUNICIPALITY_A,
    **extra: object,
) -> dict[str, object]:
    row = licence_row(
        "lic_active",
        activity_code=code,
        activity_name_ar=name,
        active_count=count,
        municipality=municipality,
    )
    row.update(extra)
    return row


def cancelled_row(
    code: str = "5610101",
    name: str = "مطعم",
    count: object = 1,
    municipality: str = _MUNICIPALITY_A,
    year: object = _YEAR,
    month: object = 1,
    **extra: object,
) -> dict[str, object]:
    row = licence_row(
        "lic_cancelled",
        activity_code=code,
        activity_name_ar=name,
        cancelled_count=count,
        municipality=municipality,
        year=year,
        month=month,
    )
    row.update(extra)
    return row


def class_body(rows: list[tuple[str, str]]) -> bytes:
    """Quoted comma-separated class bytes with the real header and CRLF ends."""
    lines = ['"Code","Description"']
    for code, title in rows:
        lines.append(
            '"' + code.replace('"', '""') + '","' + title.replace('"', '""') + '"'
        )
    return ("\r\n".join(lines) + "\r\n").encode("ascii")


def _review(folder: Path) -> Path:
    path = folder / "review.csv"
    path.write_text(
        "code,code_length,name_ar,isic_class,status,reason,"
        "reviewed_by_role,reviewed_on\n",
        encoding="utf-8",
    )
    return path


def test_release_field_reads_the_evidence_mark_from_the_map() -> None:
    """The cancelled name is the evidence-only column, and no second map is needed."""
    assert release_field("lic_active", "activity_code") == _source_field(
        "lic_active", "activity_code"
    )
    assert release_field("lic_cancelled", "activity_name_ar") == _source_field(
        "lic_cancelled", "activity_name_ar"
    )
    assert _MARK + "activity_name_ar" in {
        release for _table, release in FIELD_MAP["lic_cancelled"].values()
    }


def test_active_codes_sum_across_municipalities() -> None:
    """One code on two municipalities is one row whose count is the hand sum."""
    rows = (
        active_row(count=10, municipality=_MUNICIPALITY_A),
        active_row(count=25, municipality=_MUNICIPALITY_B),
        active_row(
            code="4100001", name="نشاط آخر", count=8, municipality=_MUNICIPALITY_C
        ),
    )
    read = parse_feed_rows(rows, _entry("lic_active"))
    assert read == FeedRead(
        rows=(
            ActivityRow("4100001", "نشاط آخر", 8, 0, ("lic_active",)),
            ActivityRow("5610101", "مطعم", 35, 0, ("lic_active",)),
        )
    )


def test_cancelled_codes_sum_across_periods_including_null() -> None:
    """One code over years, months and a null period is one row with the hand sum."""
    rows = (
        cancelled_row(count=4, year=_YEAR, month=1, municipality=_MUNICIPALITY_A),
        cancelled_row(count=6, year=_YEAR, month=2, municipality=_MUNICIPALITY_B),
        cancelled_row(count=3, year=None, month=None, municipality=_MUNICIPALITY_C),
        cancelled_row(code="4100001", name="نشاط آخر", count=2, year="2030", month=11),
    )
    read = parse_feed_rows(rows, _entry("lic_cancelled"))
    assert read.rows == (
        ActivityRow("4100001", "نشاط آخر", 0, 2, ("lic_cancelled",)),
        ActivityRow("5610101", "مطعم", 0, 13, ("lic_cancelled",)),
    )
    assert read.left_out == ()
    assert _YEAR not in json.dumps(asdict(read), ensure_ascii=False)
    assert _MUNICIPALITY_A not in json.dumps(asdict(read), ensure_ascii=False)


def test_a_non_digit_code_is_left_out_and_counted() -> None:
    """The planted code is absent, reported once, and the other row is unchanged."""
    field = _source_field("lic_cancelled", "activity_code")
    rows = (
        cancelled_row(count=8),
        cancelled_row(code="Q-7", count=4, municipality=_MUNICIPALITY_B),
    )
    read = parse_feed_rows(rows, _entry("lic_cancelled"))
    assert read.rows == (ActivityRow("5610101", "مطعم", 0, 8, ("lic_cancelled",)),)
    assert read.left_out == (LeftOut("lic_cancelled", field, "a?9", 1),)
    rendered = json.dumps(asdict(read), ensure_ascii=False)
    assert "Q-7" not in rendered


def test_pattern_classes_cover_empty_digits_letters_and_other() -> None:
    """Each pattern class is counted, and no character of a code is kept."""
    field = _source_field("lic_active", "activity_code")
    rows = (
        active_row(code="", count=1),
        active_row(code=" ", count=1, municipality=_MUNICIPALITY_B),
        active_row(code="ZZ", count=1, municipality=_MUNICIPALITY_C),
        active_row(code="YY", count=1, municipality="MUNI-DELTA"),
        active_row(code="5610101", count=7),
    )
    read = parse_feed_rows(rows, _entry("lic_active"))
    assert read.rows == (ActivityRow("5610101", "مطعم", 7, 0, ("lic_active",)),)
    assert read.left_out == (
        LeftOut("lic_active", field, "?", 1),
        LeftOut("lic_active", field, "aa", 2),
        LeftOut("lic_active", field, "empty", 1),
    )
    rendered = json.dumps(asdict(read), ensure_ascii=False)
    assert "ZZ" not in rendered
    assert "YY" not in rendered


def test_each_feed_refuses_an_unknown_a_missing_and_a_bad_null() -> None:
    """An extra field, a missing field and a null outside NULLABLE refuse the feed."""
    cases = (
        ("lic_active", active_row(planted=1), "planted"),
        (
            "lic_active",
            licence_row(
                "lic_active",
                activity_code="5610101",
                activity_name_ar="مطعم",
                active_count=1,
            ),
            _source_field("lic_active", "municipality_code"),
        ),
        ("lic_cancelled", cancelled_row(planted=1), "planted"),
        (
            "lic_cancelled",
            licence_row(
                "lic_cancelled",
                activity_code="5610101",
                activity_name_ar="مطعم",
                cancelled_count=1,
                municipality=_MUNICIPALITY_A,
                month=1,
            ),
            _period_fields("lic_cancelled")[0],
        ),
    )
    for feed, row, named in cases:
        with pytest.raises(SpineError, match=feed) as caught:
            parse_feed_rows((row,), _entry(feed))
        assert named in str(caught.value)
    null_name = active_row()
    null_name[_source_field("lic_active", "activity_name_ar")] = None
    with pytest.raises(SpineError, match="lic_active") as caught:
        parse_feed_rows((null_name,), _entry("lic_active"))
    assert _source_field("lic_active", "activity_name_ar") in str(caught.value)


def test_real_reader_refuses_two_names_a_negative_and_a_boolean() -> None:
    """The four closed cases of the retired merged reader hold on the real shape."""
    with pytest.raises(SpineError, match="conflicting activity name"):
        parse_feed_rows(
            (active_row(name="مطعم", count=2), active_row(name="مقهى", count=3)),
            _entry("lic_active"),
        )
    with pytest.raises(SpineError, match="non-negative"):
        parse_feed_rows((active_row(count=-1),), _entry("lic_active"))
    with pytest.raises(SpineError, match="lic_active") as caught:
        parse_feed_rows((active_row(count=True),), _entry("lic_active"))
    assert _source_field("lic_active", "active_count") in str(caught.value)
    with pytest.raises(SpineError, match="lic_cancelled") as caught:
        parse_feed_rows((cancelled_row(count="4"),), _entry("lic_cancelled"))
    assert _source_field("lic_cancelled", "cancelled_count") in str(caught.value)


def test_lic_active_refuses_a_non_digit_code_with_a_negative_count() -> None:
    """A non-digit code is still a row: a negative count refuses before it is left out."""
    with pytest.raises(SpineError, match="non-negative") as caught:
        parse_feed_rows((active_row(code="Q-7", count=-1),), _entry("lic_active"))
    assert "-1" not in str(caught.value)
    assert "Q-7" not in str(caught.value)


def test_lic_cancelled_refuses_a_non_digit_code_with_a_negative_count() -> None:
    """A non-digit code is still a row: a negative count refuses before it is left out."""
    with pytest.raises(SpineError, match="non-negative") as caught:
        parse_feed_rows((cancelled_row(code="Q-7", count=-1),), _entry("lic_cancelled"))
    assert "-1" not in str(caught.value)
    assert "Q-7" not in str(caught.value)


def test_lic_active_refuses_an_empty_code_with_a_negative_count() -> None:
    """An empty code is still a row: a negative count refuses before it is left out."""
    with pytest.raises(SpineError, match="non-negative") as caught:
        parse_feed_rows((active_row(code="", count=-1),), _entry("lic_active"))
    assert "-1" not in str(caught.value)


def test_lic_cancelled_refuses_an_empty_code_with_a_negative_count() -> None:
    """An empty code is still a row: a negative count refuses before it is left out."""
    with pytest.raises(SpineError, match="non-negative") as caught:
        parse_feed_rows((cancelled_row(code="", count=-1),), _entry("lic_cancelled"))
    assert "-1" not in str(caught.value)


def test_a_non_digit_code_with_a_blank_name_is_refused() -> None:
    """A non-digit code does not skip the name check a kept row gets."""
    with pytest.raises(SpineError, match="activity_name_ar is not text") as caught:
        parse_feed_rows((active_row(code="Q-7", name=""),), _entry("lic_active"))
    assert "Q-7" not in str(caught.value)


def test_a_non_digit_code_with_a_zero_count_is_left_out() -> None:
    """A valid non-digit row whose count is zero is left out and counted."""
    field = _source_field("lic_active", "activity_code")
    read = parse_feed_rows((active_row(code="Q-7", count=0),), _entry("lic_active"))
    assert read.rows == ()
    assert read.left_out == (LeftOut("lic_active", field, "a?9", 1),)
    assert "Q-7" not in json.dumps(asdict(read), ensure_ascii=False)


def test_unknown_feed_is_refused_before_its_rows_are_read() -> None:
    """A registry feed outside the two licence feeds is not a spine feed."""
    with pytest.raises(SpineError, match="unknown activity feed"):
        parse_feed_rows((), _entry("lic_issued"))


def test_isic_file_keeps_classes_and_counts_higher_levels() -> None:
    """A four-digit code is a class; a letter, two digits or three digits are counted."""
    read = parse_isic_rows(
        (
            {"Code": "A", "Description": "Section"},
            {"Code": "C", "Description": "Another section"},
            {"Code": "01", "Description": "Division"},
            {"Code": "011", "Description": "Group"},
            {"Code": "0111", "Description": "Food  service"},
            {"Code": "5610", "Description": "Food, beverages"},
            {"Code": "5610", "Description": "Food, beverages"},
        )
    )
    assert read == ClassRead(
        classes=(
            IsicClass("0111", "Food  service", ""),
            IsicClass("5610", "Food, beverages", ""),
        ),
        left_out=(
            LeftOut("cls_isic4", "Code", "99", 1),
            LeftOut("cls_isic4", "Code", "999", 1),
            LeftOut("cls_isic4", "Code", "a", 2),
        ),
    )
    assert "011" not in {row.code for row in read.classes}


def test_isic_refuses_other_patterns_aliases_and_conflicting_titles() -> None:
    """Any other code pattern, an unknown field or two titles refuse the file."""
    with pytest.raises(SpineError, match="isic code pattern") as caught:
        parse_isic_rows(({"Code": "01111", "Description": "Too long"},))
    assert "01111" not in str(caught.value)
    with pytest.raises(SpineError, match="isic code pattern"):
        parse_isic_rows(({"Code": "A1", "Description": "Mixed"},))
    with pytest.raises(SpineError, match="isic code pattern"):
        parse_isic_rows(({"Code": "", "Description": "Blank"},))
    with pytest.raises(SpineError, match="unknown isic field title_en"):
        parse_isic_rows(
            ({"Code": "5610", "Description": "Restaurants", "title_en": "Alias"},)
        )
    with pytest.raises(SpineError, match="missing isic field Description"):
        parse_isic_rows(({"Code": "5610"},))
    with pytest.raises(SpineError, match="isic field is not text"):
        parse_isic_rows(({"Code": 5610, "Description": "Restaurants"},))
    with pytest.raises(SpineError, match="isic class title is empty"):
        parse_isic_rows(({"Code": "5610", "Description": ""},))
    with pytest.raises(SpineError, match="conflicting isic title for 5610"):
        parse_isic_rows(
            (
                {"Code": "5610", "Description": "Restaurants"},
                {"Code": "5610", "Description": "Cafes"},
            )
        )


def test_cache_reads_one_feed_the_classes_and_all_three(tmp_path: Path) -> None:
    """The lead's three calls return spine rows and the same left-out report."""
    active = [
        active_row(count=10, municipality=_MUNICIPALITY_A),
        active_row(count=25, municipality=_MUNICIPALITY_B),
        active_row(code="Q-7", count=4, municipality=_MUNICIPALITY_C),
    ]
    cancelled = [
        cancelled_row(count=4, year=_YEAR, month=1),
        cancelled_row(count=6, year=_YEAR, month=2, municipality=_MUNICIPALITY_B),
        cancelled_row(count=3, year=None, month=None, municipality=_MUNICIPALITY_C),
    ]
    classes = class_body(
        [("A", "Section"), ("011", "Group"), ("5610", "Food, beverages")]
    )
    assert classes.startswith(b'"Code","Description"\r\n')
    assert b'"011","Group"\r\n' in classes
    write_cached(tmp_path, _entry("lic_active"), json.dumps(active).encode())
    write_cached(tmp_path, _entry("lic_cancelled"), json.dumps(cancelled).encode())
    write_cached(tmp_path, _entry("cls_isic4"), classes)
    cached_classes = read_cached_classes(
        tmp_path,
        _entry("cls_isic4"),
        digest=reviewed_selections(tmp_path).get((_entry("cls_isic4")).key, "0" * 64),
    )
    assert cached_classes.classes == (IsicClass("5610", "Food, beverages", ""),)
    assert cached_classes.left_out == (
        LeftOut("cls_isic4", "Code", "999", 1),
        LeftOut("cls_isic4", "Code", "a", 1),
    )
    decoded = read_rows(
        read_cached(
            tmp_path,
            _entry("cls_isic4"),
            digest=reviewed_selections(tmp_path).get(
                (_entry("cls_isic4")).key, "0" * 64
            ),
        )
    )
    assert decoded == (
        {"Code": "A", "Description": "Section"},
        {"Code": "011", "Description": "Group"},
        {"Code": "5610", "Description": "Food, beverages"},
    )
    feed = read_cached_feed(
        tmp_path,
        _entry("lic_active"),
        digest=reviewed_selections(tmp_path).get((_entry("lic_active")).key, "0" * 64),
    )
    assert feed.rows == (ActivityRow("5610101", "مطعم", 35, 0, ("lic_active",)),)
    assert feed.left_out == (
        LeftOut(
            "lic_active",
            _source_field("lic_active", "activity_code"),
            "a?9",
            1,
        ),
    )
    inputs = load_activity_inputs(
        tmp_path, (), review_path=_review(tmp_path), supplier_membership=_NO_SUPPLIERS
    )
    cancelled_feed = read_cached_feed(
        tmp_path,
        _entry("lic_cancelled"),
        digest=reviewed_selections(tmp_path).get(
            (_entry("lic_cancelled")).key, "0" * 64
        ),
    )
    assert cancelled_feed.rows == (
        ActivityRow("5610101", "مطعم", 0, 13, ("lic_cancelled",)),
    )
    assert inputs.left_out == (
        feed.left_out + cancelled_feed.left_out + cached_classes.left_out
    )
    assert inputs.activities == (
        ActivityRow(
            "5610101",
            "مطعم",
            35,
            13,
            ("lic_active", "lic_cancelled"),
        ),
    )
    blob = json.dumps(
        {
            "spine": asdict(inputs.spine),
            "activities": [asdict(row) for row in inputs.activities],
            "queue": [asdict(row) for row in inputs.spine.queue],
        },
        ensure_ascii=False,
    )
    assert _MUNICIPALITY_A not in blob
    assert _YEAR not in blob
    graph = build_graph(
        inputs.spine,
        inputs.activities,
        inputs.classes,
        (),
        (),
        load_registry(),
    )
    graph_blob = json.dumps(asdict(graph), ensure_ascii=False)
    assert _MUNICIPALITY_A not in graph_blob
    assert _YEAR not in graph_blob
    manifest = json.dumps(asdict(inputs.manifest), ensure_ascii=False)
    assert "municipality" not in manifest
    assert _MUNICIPALITY_A not in manifest


def test_cls_isic4_registry_row_records_the_confirmed_address() -> None:
    """The class row gains the address, the csv suffix and the two columns."""
    row = _entry("cls_isic4")
    assert row.url == ISIC_URL
    assert row.kind == "https_file"
    assert row.extension == "csv"
    assert row.columns == (("Code", "string"), ("Description", "string"))
    assert row.skip_reason == ""
    assert row.row_count_min is None
    assert row.row_count_max is None
    assert row.licence_basis == "owner_decision"
    assert row.decision_record == "0026"
    assert row.licence_id == "unconfirmed"
    assert row.commit_allowed is False


def _pack_document() -> Path:
    """Find the pack from this file, including the runner's mutants directory."""
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "docs" / "04_PUBLIC_DATA_PACK.md"
        if candidate.is_file():
            return candidate
    raise AssertionError("docs/04_PUBLIC_DATA_PACK.md was not found")


def test_pack_cell_names_the_confirmed_isic_address() -> None:
    """The class source's address cell names the confirmed address; its terms cell
    holds the publisher's wording recorded by S2-T21, not the earlier placeholder."""
    text = _pack_document().read_text(encoding="utf-8")
    line = next(
        item
        for item in text.splitlines()
        if item.startswith("| `cls_isic4` | ISIC Rev.4 structure")
    )
    assert ISIC_URL in line
    assert "direct machine-readable URL to be confirmed" not in line
    assert "exact publisher wording and date read to be recorded" not in line
    assert "personal, non-commercial use" in line
    assert "read 2026-11-19; basis `owner_decision`" in line


def test_committed_review_signs_every_claimed_status() -> None:
    """A committed status other than unreviewed has both sign-off fields."""
    rows = read_review_csv(spine_path())
    for position, row in enumerate(rows, start=2):
        if row.status == "unreviewed":
            continue
        if row.reviewed_by_role.strip() == "" or row.reviewed_on.strip() == "":
            pytest.fail(
                f"line {position} has an empty reviewed_by_role or an empty reviewed_on"
            )


def test_invented_review_loads_derived_legacy(tmp_path: Path) -> None:
    """An invented review loads; a six-digit code stays unsigned and higher levels are left out."""
    held = ReviewRow(
        "5610901",
        7,
        "نشاط مخترع",
        "5610",
        "unreviewed",
        "awaiting_human_review",
        "",
        "",
    )
    review = tmp_path / "review.csv"
    write_review_csv(review, (held,))
    six = "470000"
    seven = "4700001"
    write_cached(
        tmp_path,
        _entry("lic_active"),
        real_feed_body(
            "lic_active",
            (
                {
                    "activity_code": held.code,
                    "activity_name_ar": held.name_ar,
                    "active_count": 4,
                },
                {
                    "activity_code": six,
                    "activity_name_ar": "نشاط مخترع",
                    "active_count": 2,
                },
                {
                    "activity_code": seven,
                    "activity_name_ar": "نشاط آخر مخترع",
                    "active_count": 3,
                },
            ),
        ),
    )
    write_cached(tmp_path, _entry("lic_cancelled"), real_feed_body("lic_cancelled", ()))
    write_cached(
        tmp_path,
        _entry("cls_isic4"),
        class_csv(
            (
                ("G", "Invented section"),
                ("47", "Invented division"),
                ("470", "Invented group"),
                (held.isic_class, "Invented class"),
            )
        ),
    )
    inputs = load_activity_inputs(
        tmp_path, (), review_path=review, supplier_membership=_NO_SUPPLIERS
    )
    derived = {row.code: row for row in inputs.spine.rows}
    assert derived[six].status == "not_mappable_legacy"
    assert derived[six].reviewed_by_role == ""
    assert derived[six].reviewed_on == ""
    assert inputs.left_out == (
        LeftOut("cls_isic4", "Code", "99", 1),
        LeftOut("cls_isic4", "Code", "999", 1),
        LeftOut("cls_isic4", "Code", "a", 1),
    )


def test_unsigned_legacy_claim_is_refused(tmp_path: Path) -> None:
    """A temporary copy that claims not_mappable_legacy without sign-off is refused."""
    review = tmp_path / "review.csv"
    write_review_csv(
        review,
        (
            ReviewRow(
                "561099",
                6,
                "نشاط مخترع",
                "",
                "not_mappable_legacy",
                "legacy_code_length",
                "",
                "",
            ),
        ),
    )
    claimed = next(row for row in read_review_csv(review) if row.status != "unreviewed")
    write_cached(
        tmp_path,
        _entry("lic_active"),
        real_feed_body(
            "lic_active",
            (
                {
                    "activity_code": claimed.code,
                    "activity_name_ar": claimed.name_ar,
                    "active_count": 6,
                },
            ),
        ),
    )
    write_cached(tmp_path, _entry("lic_cancelled"), real_feed_body("lic_cancelled", ()))
    write_cached(
        tmp_path, _entry("cls_isic4"), class_csv((("5610", "Invented class"),))
    )
    with pytest.raises(
        SpineError, match="not_mappable_legacy decision without a reviewer role"
    ):
        load_activity_inputs(
            tmp_path, (), review_path=review, supplier_membership=_NO_SUPPLIERS
        )
