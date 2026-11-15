"""Full text of every activity-spine refusal.

A change to the wording is a failed test. The texts below are literals.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from eii_custodian.publicdata.fetch.registry import load_registry
from eii_custodian.publicdata.review.activity import (
    CODE_SYSTEM_VERSION,
    ActivityRow,
    IsicClass,
    ReviewRow,
    SpineError,
    SupplierMembership,
    _review_row,
    build_spine,
    decode_review_code,
    entry_by_key,
    merge_feed_rows,
    parse_feed_rows,
    parse_isic_rows,
    read_cached_classes,
    read_review_csv,
    release_field,
    review_binding,
)

_NONE = SupplierMembership(codes=(), complete=True)
_HEADER = (
    "code,code_length,name_ar,isic_class,status,reason,reviewed_by_role,reviewed_on"
)
_CLASS = IsicClass("5610", "Restaurants", "")


def _as_any(value: Any) -> Any:
    """Return the argument unchanged."""
    return value


def _refuses(call: object, message: str) -> None:
    assert callable(call)
    with pytest.raises(SpineError) as caught:
        call()
    found = caught.value
    assert str(found) == message
    assert found.detail == message


def _activity(
    code: str = "5610101", active: object = 1, cancelled: object = 0
) -> ActivityRow:
    return ActivityRow(code, "نشاط مخترع", _as_any(active), _as_any(cancelled))


def _row(**changes: object) -> ReviewRow:
    values: dict[str, object] = {
        "code": "5610101",
        "code_length": 7,
        "name_ar": "نشاط مخترع",
        "isic_class": "5610",
        "status": "unreviewed",
        "reason": "awaiting_human_review",
        "reviewed_by_role": "",
        "reviewed_on": "",
    }
    values.update(changes)
    return ReviewRow(**_as_any(values))


def _spine(
    review: ReviewRow,
    *,
    binding: object = None,
    activities: tuple[ActivityRow, ...] | None = None,
) -> None:
    build_spine(
        activities if activities is not None else (_activity(),),
        (_CLASS,),
        (review,),
        (),
        supplier_membership=_NONE,
        reviewed_binding=_as_any(binding),
    )


def _binding() -> object:
    return review_binding(CODE_SYSTEM_VERSION, (_CLASS,))


def test_release_field_names_the_column() -> None:
    """A release column that is not exactly one source field is refused."""
    _refuses(
        lambda: release_field("lic_active", "invented_column"),
        "activity column is not one field: invented_column",
    )


def test_registry_key_names_a_missing_key() -> None:
    """A key that the registry does not hold is named in the refusal."""
    _refuses(
        lambda: entry_by_key((), "invented_key"),
        "registry key missing: invented_key",
    )


def test_registry_key_names_a_doubled_key() -> None:
    """A key that occurs twice is refused; the first entry is not returned."""
    base = entry_by_key(load_registry(), "lic_active")
    _refuses(
        lambda: entry_by_key((base, base), "lic_active"),
        "registry key is not unique: lic_active",
    )


def test_unknown_feeds_are_named() -> None:
    """A feed that is not one of the two licence feeds is named."""
    base = entry_by_key(load_registry(), "lic_active")
    entry = replace(base, source_id="invented_feed")
    _refuses(
        lambda: parse_feed_rows([], entry),
        "unknown activity feed invented_feed",
    )
    _refuses(
        lambda: read_cached_classes(Path("invented-cache"), entry),
        "unknown class feed invented_feed",
    )


def test_conflicting_activity_names_are_named() -> None:
    """The same code with two names is refused in a feed and in the merge."""
    entry = entry_by_key(load_registry(), "lic_active")
    rows = [
        {
            "lbldy": "invented-place",
            "rmz_lnsht_ltjry": "5610101",
            "lnsht_ltjry": "مطعم",
            "dd_lrkhs_lnsht": 1,
        },
        {
            "lbldy": "invented-place",
            "rmz_lnsht_ltjry": "5610101",
            "lnsht_ltjry": "مخبز",
            "dd_lrkhs_lnsht": 1,
        },
    ]
    _refuses(
        lambda: parse_feed_rows(rows, entry),
        "conflicting activity name for 5610101",
    )
    _refuses(
        lambda: merge_feed_rows(
            (ActivityRow("5610101", "مطعم", 1, 0),),
            (ActivityRow("5610101", "مخبز", 0, 1),),
        ),
        "conflicting activity name for 5610101",
    )


@pytest.mark.parametrize(
    ("rows", "message"),
    [
        (
            (
                {
                    "Code": "5610",
                    "Description": "Restaurants",
                    "Extra": "1",
                    "Other": "2",
                },
            ),
            "unknown isic field Extra,Other",
        ),
        (({},), "missing isic field Code,Description"),
        (
            ({"Code": 1, "Description": "Restaurants"},),
            "isic field is not text",
        ),
        (({"Code": "5610", "Description": ""},), "isic class title is empty"),
        (
            ({"Code": "56101", "Description": "invented"},),
            "isic code pattern is not a class or a higher level",
        ),
    ],
)
def test_isic_rows_name_the_defect(
    rows: tuple[dict[str, object], ...], message: str
) -> None:
    """Each malformed class row is refused with its own full text."""
    _refuses(lambda: parse_isic_rows(rows), message)


@pytest.mark.parametrize(
    ("body", "message"),
    [
        ("code\n", "review header is not the spine header"),
        (
            _HEADER + "\n5610101,7,مطعم,5610,unreviewed,awaiting_human_review,,\n" * 2,
            "duplicate review code",
        ),
        (
            _HEADER + "\n5610101,6,مطعم,5610,unreviewed,awaiting_human_review,,\n",
            "code_length does not match the code 5610101",
        ),
        (
            _HEADER + "\n5610101,7,,5610,unreviewed,awaiting_human_review,,\n",
            "name_ar is not text",
        ),
        (
            _HEADER + "\n5610101,7,مطعم,5610,,awaiting_human_review,,\n",
            "status is not text",
        ),
        (
            _HEADER + "\n5610101,7,مطعم,5610,invented,awaiting_human_review,,\n",
            "unknown status invented",
        ),
        (
            _HEADER + "\n5610101,7,مطعم,5610,unreviewed,,,\n",
            "reason is not text",
        ),
        (
            _HEADER + "\n5610101,7,مطعم,5610,unreviewed,invented,,\n",
            "reason is not a closed key",
        ),
        (
            _HEADER + "\n5610101,7,مطعم,561,unreviewed,awaiting_human_review,,\n",
            "isic_class is not four digits",
        ),
        (
            _HEADER
            + "\n5610101,7,مطعم,5610,unreviewed,awaiting_human_review,,2026/01/01\n",
            "reviewed_on is not an ISO date",
        ),
        (
            _HEADER + "\n5610101,no,مطعم,5610,unreviewed,awaiting_human_review,,\n",
            "code_length is not a non-negative integer",
        ),
        (
            _HEADER + "\n12a,3,مطعم,,unreviewed,awaiting_human_review,,\n",
            "code is not a digit string",
        ),
        (
            _HEADER
            + "\n"
            + ("1" * 8)
            + ",8,مطعم,,unreviewed,awaiting_human_review,,\n",
            "review file holds a bare digit run",
        ),
        (
            _HEADER + "\n12.3,3,مطعم,,unreviewed,awaiting_human_review,,\n",
            "review code is not the reversible dotted form",
        ),
    ],
)
def test_review_csv_names_the_defect(tmp_path: Path, body: str, message: str) -> None:
    """Each malformed review file is refused with its own full text."""
    path = tmp_path / "review.csv"
    path.write_text(body, encoding="utf-8")
    _refuses(lambda: read_review_csv(path), message)


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"isic_class": 1}, "isic_class is not text"),
        ({"reviewed_on": 1}, "reviewed_on is not text"),
        ({"reviewed_by_role": 1}, "role is not text"),
    ],
)
def test_review_row_rejects_a_cell_that_is_not_text(
    changes: dict[str, object], message: str
) -> None:
    """A non-text optional cell names the field that failed."""
    item = {
        "code": "5610101",
        "code_length": "7",
        "name_ar": "مطعم",
        "isic_class": "",
        "status": "unreviewed",
        "reason": "awaiting_human_review",
        "reviewed_by_role": "",
        "reviewed_on": "",
    }
    item.update(changes)
    _refuses(lambda: _review_row(item), message)


@pytest.mark.parametrize(
    ("token", "message"),
    [
        ("12a", "code is not a digit string"),
        (15, "code is not a digit string"),
        ("1" * 8, "review file holds a bare digit run"),
        ("12.3", "review code is not the reversible dotted form"),
    ],
)
def test_decode_names_the_defect(token: object, message: str) -> None:
    """A review-file token that is not a reversible digit code is refused."""
    _refuses(lambda: decode_review_code(token), message)


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"code": "12a", "code_length": 3}, "code is not a digit string"),
        ({"code_length": 6}, "code_length does not match the code 5610101"),
        ({"name_ar": ""}, "name_ar is not text"),
        ({"status": "invented"}, "unknown status invented"),
        ({"reason": "invented"}, "reason is not a closed key"),
        ({"isic_class": "561"}, "isic_class is not four digits"),
        ({"reviewed_on": "2026/01/01"}, "reviewed_on is not an ISO date"),
        ({"reviewed_on": "2026-13-01"}, "reviewed_on is not a real date"),
        ({"reviewed_by_role": 1}, "role is not text"),
        ({"code_length": -1}, "code_length is not a non-negative integer"),
    ],
)
def test_direct_review_names_the_defect(
    changes: dict[str, object], message: str
) -> None:
    """A review object given to the spine is refused with the same full text."""
    _refuses(lambda: _spine(_row(**changes)), message)
