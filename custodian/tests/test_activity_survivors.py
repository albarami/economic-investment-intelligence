"""Kills that change a count, a choice, or the bytes of a review file.

Expected numbers are hand sums. Expected digests are hashed in the test from
the title text, not taken from the function under test.
"""

from __future__ import annotations

import hashlib
import json
import locale
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path

import pytest

from eii_custodian.publicdata.fetch.registry import load_registry
from eii_custodian.publicdata.review.activity import (
    CODE_SYSTEM_VERSION,
    ActivityRow,
    ClassBucketCounts,
    IsicClass,
    ReviewedBinding,
    ReviewRow,
    SpineError,
    SupplierMembership,
    _class_title_sha256,
    build_spine,
    class_bucket_counts,
    entry_by_key,
    load_activity_inputs,
    merge_feed_rows,
    parse_feed_rows,
    parse_isic_rows,
    read_review_binding,
    read_review_csv,
    review_binding,
    write_review_csv,
)
from eii_custodian.publicdata.review.cache_fixture import (
    class_csv,
    real_feed_body,
    write_cached,
)

_NONE = SupplierMembership(codes=(), complete=True)
_VERSION = "invented-codes-v2"


def _refuses(call: object, message: str) -> None:
    assert callable(call)
    with pytest.raises(SpineError) as caught:
        call()
    found = caught.value
    assert str(found) == message
    assert found.detail == message


def _activity(code: str, active: int, cancelled: int = 0) -> ActivityRow:
    return ActivityRow(code, "نشاط مخترع", active, cancelled)


def _review(
    code: str,
    status: str,
    *,
    isic_class: str,
    reason: str,
    role: str = "",
    on: str = "",
) -> ReviewRow:
    return ReviewRow(
        code=code,
        code_length=len(code),
        name_ar="نشاط مخترع",
        isic_class=isic_class,
        status=status,
        reason=reason,
        reviewed_by_role=role,
        reviewed_on=on,
    )


@contextmanager
def _ascii_locale() -> Iterator[None]:
    previous = locale.setlocale(locale.LC_ALL)
    locale.setlocale(locale.LC_ALL, "C")
    try:
        yield
    finally:
        locale.setlocale(locale.LC_ALL, previous)


def test_spine_error_keeps_the_detail_it_was_given() -> None:
    """A refusal exposes the same text on the exception and on its detail."""
    error = SpineError("invented detail")
    assert error.detail == "invented detail"
    assert str(error) == "invented detail"


def test_bucket_sums_add_every_code_in_the_bucket() -> None:
    """Two non-zero counts in one bucket add; the last count is not the bucket."""
    eight_low = "5610101" + "8"
    eight_high = "5610102" + "9"
    counts = class_bucket_counts(
        (
            _activity("5610101", 2),
            _activity("5610102", 3),
            _activity("5699991", 4),
            _activity("5699992", 5),
            _activity("561001", 6),
            _activity("561002", 7),
            _activity("56101", 8),
            _activity("56102", 9),
            _activity(eight_low, 1),
            _activity(eight_high, 2),
        ),
        (IsicClass("5610", "Restaurants", ""),),
    )
    assert counts == ClassBucketCounts(
        seven_valid_prefix=5,
        seven_invalid_prefix=9,
        six_legacy=13,
        other_length=20,
        five_digit=17,
        eight_digit=3,
        total_active=47,
    )


def test_coverage_adds_the_active_counts_of_one_status() -> None:
    """Two legacy codes contribute both active counts to that status."""
    spine = build_spine(
        (_activity("561001", 2), _activity("561002", 3)),
        (),
        (),
        (),
        supplier_membership=_NONE,
    )
    found = {row.status: row for row in spine.coverage}
    assert found["not_mappable_legacy"].code_count == 2
    assert found["not_mappable_legacy"].active_count == 5


def test_merged_active_counts_add_when_the_name_agrees() -> None:
    """The same code twice in the active feed keeps the sum of the counts."""
    merged = merge_feed_rows(
        (
            ActivityRow("5610101", "مطعم", 2, 0),
            ActivityRow("5610101", "مطعم", 3, 0),
        ),
        (),
    )
    assert len(merged) == 1
    assert merged[0].active_count == 5
    assert merged[0].cancelled_count == 0


def test_signed_rejection_keeps_its_role_and_leaves_the_queue() -> None:
    """A signed rejection stores the role and the date and is not queued again."""
    classes = (IsicClass("5610", "Restaurants", ""),)
    spine = build_spine(
        (_activity("5610101", 4),),
        classes,
        (
            _review(
                "5610101",
                "not_mappable_rejected",
                isic_class="",
                reason="reviewer_rejected",
                role="data_reviewer",
                on="2026-11-01",
            ),
        ),
        (),
        supplier_membership=_NONE,
        reviewed_binding=review_binding(CODE_SYSTEM_VERSION, classes),
    )
    row = spine.rows[0]
    assert row.status == "not_mappable_rejected"
    assert row.code_length == 7
    assert row.reviewed_by_role == "data_reviewer"
    assert row.reviewed_on == "2026-11-01"
    assert spine.queue == ()


def test_one_active_licence_stays_inside_the_ranked_scope() -> None:
    """A code whose only claim on the scope is a count of one stays queued."""
    spine = build_spine(
        (_activity("4100001", 1),),
        (IsicClass("4100", "Construction", ""),),
        (),
        (),
        supplier_membership=_NONE,
    )
    assert spine.rows[0].reason == "awaiting_human_review"
    assert [row.code for row in spine.queue] == ["4100001"]


def test_food_prefix_admits_only_a_seven_digit_code() -> None:
    """A seven-digit 56 code outside the playbook classes is in scope; a six-digit one is not."""
    spine = build_spine(
        (_activity("5621001", 0), _activity("562101", 0)),
        (),
        (),
        (),
        supplier_membership=_NONE,
    )
    queued = {row.code for row in spine.queue}
    assert "5621001" in queued
    assert "562101" not in queued


def test_title_check_continues_past_a_row_that_is_not_mapped() -> None:
    """An unreviewed row does not stop the check of a later mapped title."""
    old = (IsicClass("5610", "Restaurants", ""),)
    current = (
        IsicClass("4100", "Construction", ""),
        IsicClass("5610", "Eating places", ""),
    )
    _refuses(
        lambda: build_spine(
            (_activity("4100001", 4), _activity("5610101", 4)),
            current,
            (
                _review(
                    "4100001",
                    "unreviewed",
                    isic_class="4100",
                    reason="awaiting_human_review",
                ),
                _review(
                    "5610101",
                    "mapped",
                    isic_class="5610",
                    reason="reviewer_approved",
                    role="data_reviewer",
                    on="2026-11-01",
                ),
            ),
            (),
            supplier_membership=_NONE,
            reviewed_binding=review_binding(CODE_SYSTEM_VERSION, old),
        ),
        "classification title differs from the reviewed title",
    )


def test_title_check_continues_past_an_unknown_class() -> None:
    """A mapped row whose class is absent does not hide a later changed title."""
    old = (IsicClass("5610", "Restaurants", ""),)
    current = (IsicClass("5610", "Eating places", ""),)
    signed = dict(role="data_reviewer", on="2026-11-01", reason="reviewer_approved")
    _refuses(
        lambda: build_spine(
            (_activity("5610101", 4), _activity("5610102", 4)),
            current,
            (
                _review("5610101", "mapped", isic_class="9999", **signed),
                _review("5610102", "mapped", isic_class="5610", **signed),
            ),
            (),
            supplier_membership=_NONE,
            reviewed_binding=review_binding(CODE_SYSTEM_VERSION, old),
        ),
        "classification title differs from the reviewed title",
    )


def test_binding_file_accepts_two_distinct_class_titles(tmp_path: Path) -> None:
    """Two class-title inputs are two keys; the second is not a repeat."""
    digest = "ab" * 32
    path = tmp_path / "invented.binding.json"
    path.write_text(
        json.dumps(
            {
                "code_system_version": _VERSION,
                "inputs": [
                    {"name": "class_title", "code": "5610", "sha256": digest},
                    {"name": "class_title", "code": "5621", "sha256": digest},
                ],
            }
        ),
        encoding="utf-8",
    )
    found = read_review_binding(path)
    assert found == ReviewedBinding(
        code_system_version=_VERSION,
        input_sha256=(
            ("class_title", "5610", digest),
            ("class_title", "5621", digest),
        ),
    )


def test_caller_version_is_the_version_compared_with_the_binding(
    tmp_path: Path,
) -> None:
    """A non-default version matches a binding recorded at that same version."""
    entries = {item.source_id: item for item in load_registry()}
    write_cached(
        tmp_path,
        entries["lic_active"],
        real_feed_body(
            "lic_active",
            [
                {
                    "activity_code": "5610101",
                    "activity_name_ar": "مطعم",
                    "active_count": 4,
                }
            ],
        ),
    )
    write_cached(
        tmp_path,
        entries["lic_cancelled"],
        real_feed_body("lic_cancelled", []),
    )
    write_cached(tmp_path, entries["cls_isic4"], class_csv([("5610", "Restaurants")]))
    review = tmp_path / "review.csv"
    review.write_text(
        "code,code_length,name_ar,isic_class,status,reason,"
        "reviewed_by_role,reviewed_on\n"
        "5610101,7,مطعم,5610,mapped,reviewer_approved,data_reviewer,2026-11-01\n",
        encoding="utf-8",
    )
    digest = hashlib.sha256(b"5610\tRestaurants\t").hexdigest()
    review.with_name("review.binding.json").write_text(
        json.dumps(
            {
                "code_system_version": _VERSION,
                "inputs": [{"code": "5610", "name": "class_title", "sha256": digest}],
            }
        ),
        encoding="utf-8",
    )
    loaded = load_activity_inputs(
        tmp_path,
        (),
        supplier_membership=_NONE,
        review_path=review,
        code_system_version=_VERSION,
    )
    assert loaded.spine.rows[0].status == "mapped"
    assert loaded.manifest is not None
    assert loaded.manifest.code_system_version == _VERSION


def test_a_left_out_nine_keeps_the_digit_mark() -> None:
    """The digit 9 is a digit mark in the pattern class of a left-out code."""
    found = parse_isic_rows(({"Code": "99", "Description": "invented level"},))
    assert found.classes == ()
    assert len(found.left_out) == 1
    assert found.left_out[0].pattern == "99"
    assert found.left_out[0].count == 1


def test_a_short_review_row_has_an_empty_role(tmp_path: Path) -> None:
    """A cell the row does not carry is an empty role, so the row stays unsigned."""
    path = tmp_path / "review.csv"
    path.write_text(
        "code,code_length,name_ar,isic_class,status,reason,"
        "reviewed_by_role,reviewed_on\n"
        "5610101,7,مطعم,5610,unreviewed,awaiting_human_review\n",
        encoding="utf-8",
    )
    found = read_review_csv(path)
    assert found[0].reviewed_by_role == ""
    assert found[0].reviewed_on == ""


def test_class_title_digest_uses_tab_and_newline() -> None:
    """The manifest digest joins code, English title and Arabic title with tabs."""
    body = "5610\tRestaurants\ttitle-ar\n5621\tOther eating\t"
    found = _class_title_sha256(
        (
            IsicClass("5621", "Other eating", ""),
            IsicClass("5610", "Restaurants", "title-ar"),
        )
    )
    assert found == hashlib.sha256(body.encode()).hexdigest()


def test_numeric_licence_code_is_refused_by_field_type() -> None:
    """An invented number column reaches the code-type refusal."""
    base = entry_by_key(load_registry(), "lic_active")
    entry = replace(
        base,
        columns=tuple(
            (name, "number" if name == "rmz_lnsht_ltjry" else kind)
            for name, kind in base.columns
        ),
    )
    _refuses(
        lambda: parse_feed_rows(
            [
                {
                    "lbldy": "invented-place",
                    "rmz_lnsht_ltjry": 5610101,
                    "lnsht_ltjry": "مطعم مخترع",
                    "dd_lrkhs_lnsht": 3,
                }
            ],
            entry,
        ),
        "lic_active field type: rmz_lnsht_ltjry",
    )


def test_review_read_keeps_utf8_text_and_a_carriage_return(
    tmp_path: Path,
) -> None:
    """Under an ASCII locale a UTF-8 file still yields the Arabic name and the CR."""
    path = tmp_path / "review.csv"
    path.write_bytes(
        (
            "code,code_length,name_ar,isic_class,status,reason,"
            "reviewed_by_role,reviewed_on\n"
            '5610101,7,مطعم,5610,unreviewed,awaiting_human_review,"role\rpart",\n'
        ).encode()
    )
    with _ascii_locale():
        found = read_review_csv(path)
    assert found[0].name_ar == "مطعم"
    assert found[0].reviewed_by_role == "role\rpart"


def test_review_write_is_utf8_and_lf_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The written bytes are UTF-8 with LF, and the writer is asked for newline ''."""
    seen: list[dict[str, object]] = []
    real_open = Path.open

    def spy(self: Path, *args: object, **kwargs: object) -> object:
        seen.append(kwargs)
        return real_open(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", spy)
    path = tmp_path / "review.csv"
    row = ReviewRow(
        code="5610101",
        code_length=7,
        name_ar="مطعم",
        isic_class="5610",
        status="unreviewed",
        reason="awaiting_human_review",
        reviewed_by_role="",
        reviewed_on="",
    )
    with _ascii_locale():
        write_review_csv(path, (row,))
        body = path.read_bytes()
    assert seen[0]["newline"] == ""
    assert "مطعم".encode() in body
    assert b"\r\n" not in body


def test_binding_read_keeps_utf8_under_an_ascii_locale(tmp_path: Path) -> None:
    """A UTF-8 binding is read as UTF-8 when the locale encoding is ASCII."""
    path = tmp_path / "invented.binding.json"
    path.write_bytes('{"code_system_version":"نسخة","inputs":[]}'.encode())
    with _ascii_locale():
        found = read_review_binding(path)
    assert found.code_system_version == "نسخة"
    assert found.input_sha256 == ()
