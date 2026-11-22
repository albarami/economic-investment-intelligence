"""Activity spine: the legacy trap and the sign-off rule come first."""

from __future__ import annotations

import csv
import json
from dataclasses import replace
from pathlib import Path

import pytest
from custodian.tests.test_baskets import invented_review
from hypothesis import example, given
from hypothesis import strategies as st

from eii_custodian.publicdata.fetch.registry import load_registry
from eii_custodian.publicdata.review.activity import (
    STATUSES,
    ActivityRow,
    ClassBucketCounts,
    IsicClass,
    ReviewRow,
    SpineError,
    SupplierMembership,
    build_spine,
    class_bucket_counts,
    entry_by_key,
    finalise_spine,
    load_activity_inputs,
    load_seed_reviews,
    merge_feed_rows,
    parse_feed_rows,
    parse_isic_rows,
    read_review_csv,
    review_binding,
    spine_path,
    write_queue_csv,
    write_review_csv,
)
from eii_custodian.publicdata.review.cache_fixture import (
    CacheError,
    class_csv,
    real_feed_body,
    real_feed_row,
    write_cached,
)
from eii_custodian.publicdata.review.graph import build_graph

_NO_SUPPLIERS = SupplierMembership(codes=(), complete=True)
_VERSION = "licence_codes_2025_05"


def test_six_digit_legacy_code_never_maps_to_its_prefix() -> None:
    """561000 is spare-parts trade; a claimed 5610 mapping is overridden."""
    activities = (
        ActivityRow(
            code="561000",
            name_ar="تجارة قطع الغيار",
            active_count=12,
            cancelled_count=3,
        ),
    )
    classes = (
        IsicClass(
            code="5610",
            label_en="Restaurants and mobile food service activities",
            label_ar="",
        ),
    )
    reviews = (
        ReviewRow(
            code="561000",
            code_length=6,
            name_ar="تجارة قطع الغيار",
            isic_class="5610",
            status="mapped",
            reason="reviewer_approved",
            reviewed_by_role="data_reviewer",
            reviewed_on="2026-11-01",
        ),
    )
    spine = build_spine(
        activities,
        classes,
        reviews,
        (),
        supplier_membership=_NO_SUPPLIERS,
        reviewed_binding=review_binding(_VERSION, classes),
    )
    row = spine.rows[0]
    assert row.status == "not_mappable_legacy"
    assert row.reason == "legacy_code_length"
    assert row.isic_class == ""


def test_mapped_row_without_sign_off_fails_closed() -> None:
    """A mapped claim with no reviewer role can never emit mapped."""
    activities = (
        ActivityRow(
            code="5610101", name_ar="مطعم", active_count=4782, cancelled_count=0
        ),
    )
    classes = (
        IsicClass(
            code="5610",
            label_en="Restaurants and mobile food service activities",
            label_ar="",
        ),
    )
    reviews = (
        ReviewRow(
            code="5610101",
            code_length=7,
            name_ar="مطعم",
            isic_class="5610",
            status="mapped",
            reason="reviewer_approved",
            reviewed_by_role="",
            reviewed_on="2026-11-01",
        ),
    )
    with pytest.raises(SpineError):
        build_spine(
            activities,
            classes,
            reviews,
            (),
            supplier_membership=_NO_SUPPLIERS,
            reviewed_binding=review_binding(_VERSION, classes),
        )


def test_unknown_seven_digit_prefix_is_invalid() -> None:
    """A 7-digit code whose four digits are no ISIC class is invalid."""
    spine = build_spine(
        (_activity("5699999", 10),),
        _classes("5610"),
        (),
        (),
        supplier_membership=_NO_SUPPLIERS,
    )
    row = spine.rows[0]
    assert row.status == "not_mappable_invalid_prefix"
    assert row.reason == "invalid_isic_prefix"
    assert row.isic_class == ""


def test_signed_mapping_with_the_wrong_class_fails() -> None:
    """A signed mapped row must name the prefix itself."""
    reviews = (_review("5610101", "mapped", isic_class="5630"),)
    with pytest.raises(SpineError):
        build_spine(
            (_activity("5610101", 10),),
            _classes("5610", "5630"),
            reviews,
            (),
            supplier_membership=_NO_SUPPLIERS,
            reviewed_binding=review_binding(_VERSION, _classes("5610", "5630")),
        )


def test_out_of_scope_claimed_mapping_stays_unreviewed() -> None:
    """A signed mapping outside the review scope is not adopted."""
    reviews = (_review("4100001", "mapped", isic_class="4100"),)
    spine = build_spine(
        (_activity("4100001", 0, 5),),
        _classes("4100"),
        reviews,
        (),
        supplier_membership=_NO_SUPPLIERS,
        reviewed_binding=review_binding(_VERSION, _classes("4100")),
    )
    row = spine.rows[0]
    assert row.status == "unreviewed"
    assert row.reason == "outside_review_scope"
    assert row.isic_class == ""


def test_unsigned_candidate_stays_unreviewed() -> None:
    """An in-scope code with no review row is unreviewed, not mapped."""
    spine = build_spine(
        (_activity("5610101", 10),),
        _classes("5610"),
        (),
        (),
        supplier_membership=_NO_SUPPLIERS,
    )
    row = spine.rows[0]
    assert row.status == "unreviewed"
    assert row.reason == "awaiting_human_review"
    assert row.isic_class == ""


def test_signed_valid_mapping_is_mapped() -> None:
    """A signed in-scope row naming its own prefix is mapped."""
    reviews = (_review("5610101", "mapped", isic_class="5610"),)
    spine = build_spine(
        (_activity("5610101", 10),),
        _classes("5610"),
        reviews,
        (),
        supplier_membership=_NO_SUPPLIERS,
        reviewed_binding=review_binding(_VERSION, _classes("5610")),
    )
    row = spine.rows[0]
    assert row.status == "mapped"
    assert row.reason == "reviewer_approved"
    assert row.isic_class == "5610"
    assert row.reviewed_by_role == "data_reviewer"
    assert row.reviewed_on == "2026-11-01"


def test_signed_rejection_is_not_mappable_rejected() -> None:
    """A signed rejection emits the rejected status and no class."""
    reviews = (_review("5610101", "not_mappable_rejected"),)
    spine = build_spine(
        (_activity("5610101", 10),),
        _classes("5610"),
        reviews,
        (),
        supplier_membership=_NO_SUPPLIERS,
        reviewed_binding=review_binding(_VERSION, _classes("5610")),
    )
    row = spine.rows[0]
    assert row.status == "not_mappable_rejected"
    assert row.reason == "reviewer_rejected"
    assert row.isic_class == ""


def test_rejection_without_sign_off_fails() -> None:
    """A rejected decision needs both sign-off fields."""
    reviews = (_review("5610101", "not_mappable_rejected", role=""),)
    with pytest.raises(SpineError):
        build_spine(
            (_activity("5610101", 10),),
            _classes("5610"),
            reviews,
            (),
            supplier_membership=_NO_SUPPLIERS,
            reviewed_binding=review_binding(_VERSION, _classes("5610")),
        )


def test_top_two_hundred_codes_form_the_queue() -> None:
    """The queue is the 200 largest active counts, count then code."""
    activities = tuple(
        _activity(f"4100{index:03d}", 300 - index) for index in range(1, 206)
    )
    spine = build_spine(
        activities, _classes("4100"), (), (), supplier_membership=_NO_SUPPLIERS
    )
    assert len(spine.queue) == 200
    assert spine.queue[0].code == "4100001"
    assert spine.queue[-1].code == "4100200"
    assert "4100201" not in {row.code for row in spine.queue}
    assert all(row.status == "unreviewed" for row in spine.queue)


def test_queue_tie_breaks_on_the_code() -> None:
    """Equal counts order by code ascending."""
    activities = (_activity("4100002", 7), _activity("4100001", 7))
    spine = build_spine(
        activities, _classes("4100"), (), (), supplier_membership=_NO_SUPPLIERS
    )
    assert [row.code for row in spine.queue] == ["4100001", "4100002"]


def test_food_service_and_playbook_codes_join_the_queue() -> None:
    """A 56 code and a playbook code are in scope below the top 200."""
    activities = (
        *(_activity(f"4100{index:03d}", 300 - index) for index in range(1, 206)),
        _activity("5610301", 1),
        _activity("4100300", 2),
    )
    spine = build_spine(
        activities,
        _classes("4100", "5610"),
        (),
        ("4100300",),
        supplier_membership=_NO_SUPPLIERS,
    )
    queued = {row.code for row in spine.queue}
    assert "5610301" in queued
    assert "4100300" in queued
    assert len(spine.queue) == 202


def test_cancelled_only_codes_follow_the_same_scope() -> None:
    """A cancelled-only 56 code is queued; another cancelled-only code is not."""
    activities = (_activity("5610401", 0, 9), _activity("4100401", 0, 9))
    spine = build_spine(
        activities, _classes("4100", "5610"), (), (), supplier_membership=_NO_SUPPLIERS
    )
    queued = {row.code for row in spine.queue}
    assert "5610401" in queued
    assert "4100401" not in queued
    outside = {row.code: row for row in spine.rows}["4100401"]
    assert outside.reason == "outside_review_scope"


def test_low_count_playbook_class_stays_in_scope() -> None:
    """A low-count 5510 activity is in scope without being one of the largest."""
    activities = (
        *(_activity(f"4100{index:03d}", 300 - index) for index in range(1, 206)),
        _activity("5510001", 1),
    )
    spine = build_spine(
        activities, _classes("4100", "5510"), (), (), supplier_membership=_NO_SUPPLIERS
    )
    assert "5510001" in {row.code for row in spine.queue}
    row = {item.code: item for item in spine.rows}["5510001"]
    assert row.status == "unreviewed"


def test_cancelled_only_supplier_stays_in_scope() -> None:
    """A cancelled-only basket supplier is queued from the typed membership."""
    from eii_custodian.publicdata.review.activity import SupplierMembership

    activities = (
        *(_activity(f"4100{index:03d}", 300 - index) for index in range(1, 201)),
        _activity("4630001", 0, 4),
    )
    membership = SupplierMembership(codes=("4630001",), complete=True)
    spine = build_spine(
        activities,
        _classes("4100", "4630"),
        (),
        (),
        supplier_membership=membership,
    )
    assert "4630001" in {row.code for row in spine.queue}
    row = {item.code: item for item in spine.rows}["4630001"]
    assert row.status == "unreviewed"


def test_missing_supplier_membership_is_refused() -> None:
    """A missing supplier membership is refused and is not read as empty."""
    with pytest.raises(SpineError, match="supplier membership is missing"):
        build_spine(
            (_activity("5610101", 10),),
            _classes("5610"),
            (),
            (),
            supplier_membership=None,
        )


def test_incomplete_supplier_membership_is_refused() -> None:
    """An incomplete supplier membership is refused before its codes are used."""
    from eii_custodian.publicdata.review.activity import SupplierMembership

    with pytest.raises(SpineError, match="supplier membership is incomplete"):
        build_spine(
            (_activity("5610101", 10),),
            _classes("5610"),
            (),
            (),
            supplier_membership=SupplierMembership(codes=("4630001",), complete=False),
        )


def test_build_spine_requires_a_supplier_membership() -> None:
    """Omitting the membership is a missing argument, not a complete empty set."""
    with pytest.raises(TypeError, match="supplier_membership"):
        build_spine((_activity("5610101", 10),), _classes("5610"), (), ())


def test_load_activity_inputs_requires_a_supplier_membership(tmp_path: Path) -> None:
    """The cache loader also refuses an omitted membership."""
    _write_feeds(
        tmp_path,
        active=[
            {
                "activity_code": "5610101",
                "activity_name_ar": "مطعم",
                "active_count": 10,
            }
        ],
        classes=[("5610", "Restaurants")],
    )
    with pytest.raises(TypeError, match="supplier_membership"):
        load_activity_inputs(tmp_path, (), review_path=_review_file(tmp_path))


def test_cached_cancelled_only_supplier_reaches_the_mandatory_queue(
    tmp_path: Path,
) -> None:
    """A supplied membership puts a cancelled-only supplier into the queue."""
    from eii_custodian.publicdata.review.activity import SupplierMembership

    _write_feeds(
        tmp_path,
        active=[
            {
                "activity_code": f"4100{index:03d}",
                "activity_name_ar": "نشاط قائم",
                "active_count": 400 - index,
            }
            for index in range(1, 201)
        ],
        cancelled=[
            {
                "activity_code": "4630001",
                "activity_name_ar": "مورد ملغى",
                "cancelled_count": 4,
            }
        ],
        classes=[
            ("4100", "Class 4100"),
            ("4630", "Class 4630"),
        ],
    )
    membership = SupplierMembership(codes=("4630001",), complete=True)
    inputs = load_activity_inputs(
        tmp_path,
        (),
        review_path=_review_file(tmp_path),
        supplier_membership=membership,
    )
    assert "4630001" in {row.code for row in inputs.spine.queue}
    row = {item.code: item for item in inputs.spine.rows}["4630001"]
    assert row.status == "unreviewed"
    assert row.reason == "awaiting_human_review"


def test_supplier_code_absent_from_the_feeds_fails() -> None:
    """A supplier code with no feed row is refused, never treated as absent."""
    from eii_custodian.publicdata.review.activity import SupplierMembership

    membership = SupplierMembership(codes=("4630001",), complete=True)
    with pytest.raises(SpineError, match="supplier code absent from the feeds"):
        build_spine(
            (_activity("5610101", 10),),
            _classes("5610"),
            (),
            (),
            supplier_membership=membership,
        )


def test_playbook_code_absent_from_the_feeds_fails() -> None:
    """A playbook code with no feed row is refused, never named."""
    with pytest.raises(SpineError):
        build_spine(
            (_activity("5610101", 10),),
            _classes("5610"),
            (),
            ("5610201",),
            supplier_membership=_NO_SUPPLIERS,
        )


def test_mandatory_non_mappable_codes_stay_pending_until_reviewed() -> None:
    """In-scope legacy and invalid-prefix codes stay pending and unmappable."""
    activities = (
        _activity("561000", 20),
        _activity("5699999", 10),
        _activity("5610101", 5),
    )
    classes = _classes("5610")
    spine = build_spine(activities, classes, (), (), supplier_membership=_NO_SUPPLIERS)
    by_code = {row.code: row for row in spine.rows}
    assert by_code["561000"].status == "not_mappable_legacy"
    assert by_code["5699999"].status == "not_mappable_invalid_prefix"
    queued = {row.code: row for row in spine.queue}
    assert "561000" in queued
    assert queued["561000"].status == "not_mappable_legacy"
    assert "5699999" in queued
    assert queued["5699999"].status == "not_mappable_invalid_prefix"
    _assert_unmappable(spine, activities, classes)
    with pytest.raises(SpineError, match="mandatory review missing"):
        finalise_spine(spine)
    reviews = (
        _review("561000", "not_mappable_legacy"),
        _review("5699999", "not_mappable_invalid_prefix"),
        _review("5610101", "mapped", isic_class="5610"),
    )
    reviewed = build_spine(
        activities,
        classes,
        reviews,
        (),
        supplier_membership=_NO_SUPPLIERS,
        reviewed_binding=review_binding(_VERSION, classes),
    )
    done = {row.code: row for row in reviewed.rows}
    assert done["561000"].status == "not_mappable_legacy"
    assert done["5699999"].status == "not_mappable_invalid_prefix"
    assert done["561000"].reviewed_by_role == "data_reviewer"
    assert done["5699999"].reviewed_on == "2026-11-01"
    assert "561000" not in {row.code for row in reviewed.queue}
    assert "5699999" not in {row.code for row in reviewed.queue}
    _assert_unmappable(reviewed, activities, classes)
    assert finalise_spine(reviewed) == reviewed


def test_coverage_counts_every_status() -> None:
    """Coverage sums codes and national active counts by status."""
    activities = (
        _activity("5610101", 100),
        _activity("5610201", 50),
        _activity("4100001", 0, 5),
        _activity("561000", 20),
        _activity("5699999", 10),
        _activity("5610301", 5),
    )
    reviews = (
        _review("5610101", "mapped", isic_class="5610"),
        _review("5610301", "not_mappable_rejected"),
    )
    spine = build_spine(
        activities,
        _classes("4100", "5610"),
        reviews,
        (),
        supplier_membership=_NO_SUPPLIERS,
        reviewed_binding=review_binding(_VERSION, _classes("4100", "5610")),
    )
    assert tuple(row.status for row in spine.coverage) == STATUSES
    got = {row.status: (row.code_count, row.active_count) for row in spine.coverage}
    assert got["mapped"] == (1, 100)
    assert got["unreviewed"] == (2, 50)
    assert got["not_mappable_legacy"] == (1, 20)
    assert got["not_mappable_invalid_prefix"] == (1, 10)
    assert got["not_mappable_rejected"] == (1, 5)


def test_class_buckets_reconcile_to_the_published_total() -> None:
    """The four PUB-67 buckets and the other-length split sum to the total."""
    activities = (
        _activity("9900001", 211277),
        _activity("9800001", 11276),
        _activity("980001", 26844),
        _activity("98001", 169),
        _activity("9900" + "0001", 56),
    )
    counts = class_bucket_counts(activities, _classes("9900"))
    assert counts.seven_valid_prefix == 211277
    assert counts.seven_invalid_prefix == 11276
    assert counts.six_legacy == 26844
    assert counts.other_length == 225
    assert counts.five_digit == 169
    assert counts.eight_digit == 56
    assert counts.total_active == 249622
    assert (
        counts.seven_valid_prefix
        + counts.seven_invalid_prefix
        + counts.six_legacy
        + counts.other_length
        == counts.total_active
    )
    assert counts.five_digit + counts.eight_digit == counts.other_length


def test_cancelled_only_rows_add_nothing_to_the_buckets() -> None:
    """A cancelled count never enters an active bucket."""
    activities = (
        _activity("9900001", 0, 40),
        _activity("9800001", 0, 30),
        _activity("980001", 0, 20),
        _activity("98001", 0, 10),
        _activity("9900" + "0001", 0, 5),
    )
    counts = class_bucket_counts(activities, _classes("9900"))
    assert counts == ClassBucketCounts(0, 0, 0, 0, 0, 0, 0)


def test_activity_rows_aggregate_and_refuse_conflicts() -> None:
    """Repeated codes sum; a conflicting name, a bad count or an extra field fails."""
    active = parse_feed_rows(
        (
            real_feed_row(
                "lic_active",
                {
                    "activity_code": "5610101",
                    "activity_name_ar": "مطعم",
                    "active_count": 2,
                    "municipality": "أ",
                },
            ),
            real_feed_row(
                "lic_active",
                {
                    "activity_code": "5610101",
                    "activity_name_ar": "مطعم",
                    "active_count": 3,
                    "municipality": "ب",
                },
            ),
        ),
        entry_by_key(load_registry(), "lic_active"),
    )
    cancelled = parse_feed_rows(
        (
            real_feed_row(
                "lic_cancelled",
                {
                    "activity_code": "5610101",
                    "activity_name_ar": "مطعم",
                    "cancelled_count": 1,
                },
            ),
        ),
        entry_by_key(load_registry(), "lic_cancelled"),
    )
    assert merge_feed_rows(active.rows, cancelled.rows) == (
        ActivityRow("5610101", "مطعم", 5, 1, ("lic_active", "lic_cancelled")),
    )
    with pytest.raises(SpineError):
        parse_feed_rows(
            (
                real_feed_row(
                    "lic_active",
                    {
                        "activity_code": "5610101",
                        "activity_name_ar": "مطعم",
                        "active_count": 2,
                    },
                ),
                real_feed_row(
                    "lic_active",
                    {
                        "activity_code": "5610101",
                        "activity_name_ar": "مقهى",
                        "active_count": 3,
                    },
                ),
            ),
            entry_by_key(load_registry(), "lic_active"),
        )
    with pytest.raises(SpineError):
        parse_feed_rows(
            (
                real_feed_row(
                    "lic_active",
                    {
                        "activity_code": "5610101",
                        "activity_name_ar": "مطعم",
                        "active_count": -1,
                    },
                ),
            ),
            entry_by_key(load_registry(), "lic_active"),
        )
    with pytest.raises(SpineError):
        parse_feed_rows(
            (
                real_feed_row(
                    "lic_active",
                    {
                        "activity_code": "5610101",
                        "activity_name_ar": "مطعم",
                        "active_count": True,
                    },
                ),
            ),
            entry_by_key(load_registry(), "lic_active"),
        )
    with pytest.raises(SpineError):
        parse_feed_rows(
            (
                real_feed_row(
                    "lic_active",
                    {
                        "activity_code": "5610101",
                        "activity_name_ar": "مطعم",
                        "active_count": 1,
                        "planted": 1,
                    },
                ),
            ),
            entry_by_key(load_registry(), "lic_active"),
        )


def test_isic_rows_read_code_and_description() -> None:
    """A class row is Code and Description; a title alias is an unknown field."""
    parsed = parse_isic_rows(({"Code": "5610", "Description": "Restaurants"},))
    assert parsed.classes == (IsicClass("5610", "Restaurants", ""),)
    with pytest.raises(SpineError, match="unknown isic field title_en"):
        parse_isic_rows(
            ({"Code": "5610", "Description": "Restaurants", "title_en": "Alias"},)
        )


def test_review_code_round_trip_uses_the_dotted_form(tmp_path: Path) -> None:
    """An eight-digit and an eleven-digit code leave the file in dotted form."""
    eight = "1234" + "5678"
    eleven = "123" + "4567" + "8901"
    path = tmp_path / "review.csv"
    write_review_csv(path, (_dotted_review(eight), _dotted_review(eleven)))
    text = path.read_text(encoding="utf-8")
    assert eight not in text
    assert eleven not in text
    assert ("1234" + "." + "5678") in text
    assert ("1234" + "." + "5678" + "." + "901") in text
    restored = read_review_csv(path)
    assert tuple(row.code for row in restored) == (eight, eleven)
    assert tuple(row.code_length for row in restored) == (len(eight), len(eleven))


def test_review_code_rejects_a_colliding_dotted_form(tmp_path: Path) -> None:
    """Only the canonical dotted form decodes; another grouping is refused."""
    eight = "1234" + "5678"
    colliding = "12" + "." + "3456" + "78"
    path = tmp_path / "review.csv"
    path.write_text(
        "code,code_length,name_ar,isic_class,status,reason,"
        "reviewed_by_role,reviewed_on\n"
        f"{colliding},{len(eight)},اسم,,not_mappable_legacy,legacy_code_length,,\n",
        encoding="utf-8",
    )
    with pytest.raises(
        SpineError, match="review code is not the reversible dotted form"
    ):
        read_review_csv(path)
    canonical = "1234" + "." + "5678"
    assert canonical != colliding
    path.write_text(
        "code,code_length,name_ar,isic_class,status,reason,"
        "reviewed_by_role,reviewed_on\n"
        f"{canonical},{len(eight)},اسم,,not_mappable_legacy,legacy_code_length,,\n",
        encoding="utf-8",
    )
    assert read_review_csv(path)[0].code == eight


def test_review_file_refuses_a_bare_prohibited_digit_run(tmp_path: Path) -> None:
    """A bare run of eight or eleven digits in a review file is refused."""
    eight = "1234" + "5678"
    eleven = "1234567" + "8901"
    for code in (eight, eleven):
        path = tmp_path / "bare.csv"
        path.write_text(
            "code,code_length,name_ar,isic_class,status,reason,"
            "reviewed_by_role,reviewed_on\n"
            f"{code},{len(code)},اسم,,not_mappable_legacy,legacy_code_length,,\n",
            encoding="utf-8",
        )
        with pytest.raises(SpineError, match="bare digit run"):
            read_review_csv(path)


def test_review_file_refuses_bad_rows(tmp_path: Path) -> None:
    """Unknown keys, free text, a length mismatch and a bad date all fail."""
    good = "5610101,7,مطعم,5610,mapped,reviewer_approved,data_reviewer,2026-11-01"
    for planted in (
        "5610101,7,مطعم,5610,mapped,looks fine to me,data_reviewer,2026-11-01",
        "5610101,7,مطعم,5610,mapped,reviewer_approved,data_reviewer,01/11/2026",
        "5610101,6,مطعم,5610,mapped,reviewer_approved,data_reviewer,2026-11-01",
        "5610101,7,مطعم,5610,approved,reviewer_approved,data_reviewer,2026-11-01",
    ):
        path = tmp_path / "planted.csv"
        path.write_text(
            "code,code_length,name_ar,isic_class,status,reason,"
            "reviewed_by_role,reviewed_on\n" + planted + "\n",
            encoding="utf-8",
        )
        with pytest.raises(SpineError):
            read_review_csv(path)
    path = tmp_path / "good.csv"
    path.write_text(
        "code,code_length,name_ar,isic_class,status,reason,"
        "reviewed_by_role,reviewed_on\n" + good + "\n",
        encoding="utf-8",
    )
    assert read_review_csv(path)[0].status == "mapped"


def test_queue_csv_round_trip(tmp_path: Path) -> None:
    """The queue writes the fixed header and every queued row."""
    spine = build_spine(
        (_activity("5610101", 10),),
        _classes("5610"),
        (),
        (),
        supplier_membership=_NO_SUPPLIERS,
    )
    path = tmp_path / "queue.csv"
    write_queue_csv(path, spine.queue)
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.reader(handle))
    assert tuple(rows[0]) == (
        "code",
        "code_length",
        "name_ar",
        "isic_class",
        "status",
        "reason",
        "reviewed_by_role",
        "reviewed_on",
    )
    assert rows[1][0] == "5610101"


def test_committed_seed_has_no_mapped_row() -> None:
    """The committed file holds one unreviewed row and no claimed decision."""
    reviews = load_seed_reviews()
    assert len(reviews) == 1
    assert all(row.status == "unreviewed" for row in reviews)
    assert all(row.reviewed_by_role == "" for row in reviews)
    assert all(row.reviewed_on == "" for row in reviews)
    restaurant = reviews[0]
    assert restaurant.name_ar == "مطعم"
    assert restaurant.isic_class == "5610"
    assert restaurant.status == "unreviewed"
    assert spine_path().name == "activity_spine.csv"


def test_changed_classification_title_requires_a_new_review() -> None:
    """A new class title cannot reuse an approval of the same code and name."""
    from eii_custodian.publicdata.review.activity import review_binding

    classes = _classes("5610")
    binding = review_binding("licence_codes_2025_05", classes)
    reviews = (_review("5610101", "mapped", isic_class="5610"),)
    activities = (_activity("5610101", 10),)
    kept = build_spine(
        activities,
        classes,
        reviews,
        (),
        reviewed_binding=binding,
        supplier_membership=_NO_SUPPLIERS,
    )
    assert kept.rows[0].status == "mapped"
    changed = (IsicClass("5610", "Eating places", ""),)
    with pytest.raises(
        SpineError, match="classification title differs from the reviewed title"
    ):
        build_spine(
            activities,
            changed,
            reviews,
            (),
            reviewed_binding=binding,
            supplier_membership=_NO_SUPPLIERS,
        )


def test_unreviewed_row_is_not_bound_to_the_class_title() -> None:
    """A title change blocks a mapped approval and leaves an unreviewed row."""
    from eii_custodian.publicdata.review.activity import review_binding

    classes = _classes("5610")
    binding = review_binding("licence_codes_2025_05", classes)
    changed = (IsicClass("5610", "Eating places", ""),)
    spine = build_spine(
        (_activity("5610101", 10),),
        changed,
        (_review("5610101", "unreviewed", isic_class="5610"),),
        (),
        reviewed_binding=binding,
        supplier_membership=_NO_SUPPLIERS,
    )
    assert spine.rows[0].status == "unreviewed"


def test_source_receipt_without_a_hash_is_refused() -> None:
    """A selected receipt with no hash is not carried into the manifest."""
    from eii_custodian.publicdata.review.activity import _source_hash

    with pytest.raises(SpineError, match="source receipt has no hash"):
        _source_hash("lic_active", {"sha256": "abc"})


def test_changed_code_system_version_requires_a_new_review() -> None:
    """A new code-system version cannot reuse the recorded approval."""
    from eii_custodian.publicdata.review.activity import review_binding

    classes = _classes("5610")
    binding = review_binding("licence_codes_2025_05", classes)
    with pytest.raises(
        SpineError, match="code-system version differs from the reviewed version"
    ):
        build_spine(
            (_activity("5610101", 10),),
            classes,
            (_review("5610101", "mapped", isic_class="5610"),),
            (),
            code_system_version="licence_codes_2026_06",
            reviewed_binding=binding,
            supplier_membership=_NO_SUPPLIERS,
        )


def test_unsigned_review_loads_without_a_binding_and_a_signed_row_demands_one(
    tmp_path: Path,
) -> None:
    """An unsigned review file needs no binding; the first signed row demands it."""
    from eii_custodian.publicdata.review.activity import SupplierMembership

    _write_restaurant_cache(tmp_path)
    membership = SupplierMembership(codes=(), complete=True)
    unsigned = _review_file(
        tmp_path, "5610101,7,مطعم,5610,unreviewed,awaiting_human_review,,"
    )
    loaded = load_activity_inputs(
        tmp_path, (), review_path=unsigned, supplier_membership=membership
    )
    assert loaded.spine.rows[0].status == "unreviewed"
    assert not unsigned.with_name(unsigned.stem + ".binding.json").exists()
    signed = _review_file(tmp_path, _MAPPED_ROW)
    with pytest.raises(SpineError, match="review binding is missing"):
        load_activity_inputs(
            tmp_path, (), review_path=signed, supplier_membership=membership
        )


def test_cache_to_spine_refuses_a_changed_class_title(tmp_path: Path) -> None:
    """A new class title cannot reuse an approval of the same code and name."""
    from eii_custodian.publicdata.review.activity import SupplierMembership

    _write_restaurant_cache(tmp_path, label_en="Eating places")
    review = _review_file(tmp_path, _MAPPED_ROW)
    _binding_beside(review, titles=(("5610", "Restaurants", ""),))
    with pytest.raises(
        SpineError, match="classification title differs from the reviewed title"
    ):
        load_activity_inputs(
            tmp_path,
            (),
            review_path=review,
            supplier_membership=SupplierMembership(codes=(), complete=True),
        )


def test_cache_to_spine_refuses_a_changed_code_system_version(
    tmp_path: Path,
) -> None:
    """A binding recorded against another code-system version is refused."""
    from eii_custodian.publicdata.review.activity import SupplierMembership

    _write_restaurant_cache(tmp_path)
    review = _review_file(tmp_path, _MAPPED_ROW)
    _binding_beside(review, version="licence_codes_2026_06")
    with pytest.raises(
        SpineError, match="code-system version differs from the reviewed version"
    ):
        load_activity_inputs(
            tmp_path,
            (),
            review_path=review,
            supplier_membership=SupplierMembership(codes=(), complete=True),
        )


def test_cache_to_spine_accepts_a_matching_recorded_binding(tmp_path: Path) -> None:
    """A signed row whose recorded inputs still match is mapped."""
    from eii_custodian.publicdata.review.activity import SupplierMembership

    _write_restaurant_cache(tmp_path)
    review = _review_file(tmp_path, _MAPPED_ROW)
    _binding_beside(review)
    inputs = load_activity_inputs(
        tmp_path,
        (),
        review_path=review,
        supplier_membership=SupplierMembership(codes=(), complete=True),
    )
    assert inputs.spine.rows[0].status == "mapped"
    assert inputs.spine.rows[0].isic_class == "5610"


def test_mapped_claim_without_a_binding_is_refused() -> None:
    """A mapped claim demands a binding even when the reviewer role is blank."""
    reviews = (_review("5610101", "mapped", isic_class="5610", role=""),)
    with pytest.raises(SpineError, match="review binding is missing"):
        build_spine(
            (_activity("5610101", 10),),
            _classes("5610"),
            reviews,
            (),
            supplier_membership=_NO_SUPPLIERS,
        )


def test_signed_rejection_without_a_binding_is_refused() -> None:
    """A signed row that is not a mapping still demands the binding."""
    reviews = (_review("5610101", "not_mappable_rejected"),)
    with pytest.raises(SpineError, match="review binding is missing"):
        build_spine(
            (_activity("5610101", 10),),
            _classes("5610"),
            reviews,
            (),
            supplier_membership=_NO_SUPPLIERS,
        )


def test_review_binding_file_refuses_each_malformed_record(tmp_path: Path) -> None:
    """Each malformed binding record is refused for its own reason."""
    from eii_custodian.publicdata.review.activity import read_review_binding

    digest = "a" * 64
    valid = {
        "code_system_version": "licence_codes_2025_05",
        "inputs": [{"code": "5610", "name": "class_title", "sha256": digest}],
    }
    cases = (
        ("{", "review binding is not readable"),
        ("[]", "review binding is not an object"),
        (
            json.dumps({**valid, "extra": 1}),
            "review binding fields are not the contract",
        ),
        (
            json.dumps({"code_system_version": "licence_codes_2025_05"}),
            "review binding fields are not the contract",
        ),
        (
            json.dumps({**valid, "code_system_version": ""}),
            "review binding has no code-system version",
        ),
        (
            json.dumps({**valid, "code_system_version": 1}),
            "review binding has no code-system version",
        ),
        (
            json.dumps({**valid, "inputs": {}}),
            "review binding inputs are not a list",
        ),
        (
            json.dumps({**valid, "inputs": ["5610"]}),
            "review binding input fields are not the contract",
        ),
        (
            json.dumps(
                {
                    **valid,
                    "inputs": [{"code": "5610", "name": "class_title"}],
                }
            ),
            "review binding input fields are not the contract",
        ),
        (
            json.dumps(
                {
                    **valid,
                    "inputs": [
                        {"code": "5610", "name": "activity_name", "sha256": digest}
                    ],
                }
            ),
            "review binding input is not a class title",
        ),
        (
            json.dumps(
                {
                    **valid,
                    "inputs": [{"code": 5610, "name": "class_title", "sha256": digest}],
                }
            ),
            "review binding class code is not four digits",
        ),
        (
            json.dumps(
                {
                    **valid,
                    "inputs": [
                        {"code": "561", "name": "class_title", "sha256": digest}
                    ],
                }
            ),
            "review binding class code is not four digits",
        ),
        (
            json.dumps(
                {
                    **valid,
                    "inputs": [
                        {"code": "5610", "name": "class_title", "sha256": "abc"}
                    ],
                }
            ),
            "review binding hash is not a sha256",
        ),
        (
            json.dumps(
                {
                    **valid,
                    "inputs": [
                        {"code": "5610", "name": "class_title", "sha256": digest},
                        {"code": "5610", "name": "class_title", "sha256": digest},
                    ],
                }
            ),
            "review binding repeats an input",
        ),
    )
    for body, reason in cases:
        path = tmp_path / "review.binding.json"
        path.write_text(body, encoding="utf-8")
        with pytest.raises(SpineError, match=reason):
            read_review_binding(path)


def test_loaded_spine_records_complete_lineage(tmp_path: Path) -> None:
    """The build manifest keeps the version and every meaning-bearing hash."""
    import hashlib

    from eii_custodian.publicdata.fetch.receipts import sha256_hex

    active = [
        {
            "activity_code": "5610101",
            "activity_name_ar": "مطعم",
            "active_count": 10,
        }
    ]
    cancelled: list[dict[str, object]] = []
    classes = [("5610", "Restaurants")]
    _write_feeds(tmp_path, active=active, cancelled=cancelled, classes=classes)
    review = _review_file(tmp_path)
    inputs = load_activity_inputs(
        tmp_path, (), review_path=review, supplier_membership=_NO_SUPPLIERS
    )
    manifest = inputs.manifest
    assert manifest is not None
    assert manifest.code_system_version == "licence_codes_2025_05"
    assert manifest.method_version == "activity_spine.v1"
    sources = dict(manifest.source_hashes)
    assert set(sources) == {"lic_active", "lic_cancelled", "cls_isic4"}
    assert sources["lic_active"] == sha256_hex(real_feed_body("lic_active", active))
    assert sources["cls_isic4"] == sha256_hex(class_csv(classes))
    assert manifest.review_sha256 == hashlib.sha256(review.read_bytes()).hexdigest()
    assert len(manifest.class_title_sha256) == 64


def test_cache_to_spine_reads_the_three_keys(tmp_path: Path) -> None:
    """The cached active, cancelled and class keys give the spine and its inputs."""
    _write_feeds(
        tmp_path,
        active=[
            {
                "activity_code": "5610101",
                "activity_name_ar": "مطعم",
                "active_count": 10,
            },
            {
                "activity_code": "561000",
                "activity_name_ar": "تجارة قطع الغيار",
                "active_count": 5,
            },
        ],
        cancelled=[
            {
                "activity_code": "5610201",
                "activity_name_ar": "كافيتيريا",
                "cancelled_count": 4,
            },
        ],
        classes=[("5610", "Restaurants")],
    )
    review = _review_file(tmp_path, _MAPPED_ROW)
    _binding_beside(review)
    inputs = load_activity_inputs(
        tmp_path,
        ("5610101",),
        review_path=review,
        supplier_membership=_NO_SUPPLIERS,
    )
    assert tuple(row.code for row in inputs.activities) == (
        "561000",
        "5610101",
        "5610201",
    )
    assert inputs.classes == (IsicClass("5610", "Restaurants", ""),)
    statuses = {row.code: row.status for row in inputs.spine.rows}
    assert statuses == {
        "561000": "not_mappable_legacy",
        "5610101": "mapped",
        "5610201": "unreviewed",
    }
    assert tuple(row.code for row in inputs.spine.queue) == ("561000", "5610201")


def test_cache_to_spine_records_source_presence(tmp_path: Path) -> None:
    """A code in both feeds keeps both sources even at a zero count."""
    _write_feeds(
        tmp_path,
        active=[
            {
                "activity_code": "5610101",
                "activity_name_ar": "مطعم",
                "active_count": 10,
            },
            {
                "activity_code": "5610201",
                "activity_name_ar": "كافيتيريا",
                "active_count": 0,
            },
        ],
        cancelled=[
            {
                "activity_code": "5610101",
                "activity_name_ar": "مطعم",
                "cancelled_count": 0,
            },
            {
                "activity_code": "5610301",
                "activity_name_ar": "مقهى",
                "cancelled_count": 7,
            },
        ],
        classes=[("5610", "Restaurants")],
    )
    inputs = load_activity_inputs(
        tmp_path,
        (),
        review_path=_review_file(tmp_path),
        supplier_membership=_NO_SUPPLIERS,
    )
    sources = {row.code: row.source_ids for row in inputs.activities}
    assert sources["5610101"] == ("lic_active", "lic_cancelled")
    assert sources["5610201"] == ("lic_active",)
    assert sources["5610301"] == ("lic_cancelled",)


def test_cache_to_spine_refuses_a_malformed_row(tmp_path: Path) -> None:
    """An extra field, a missing field and a bad count each fail closed."""
    planted_rows = (
        {
            "activity_code": "5610101",
            "activity_name_ar": "مطعم",
            "active_count": 1,
            "planted": 1,
        },
        {"activity_code": "5610101", "activity_name_ar": "مطعم"},
        {"activity_code": "5610101", "activity_name_ar": "مطعم", "active_count": "ten"},
        {"activity_code": "5610101", "activity_name_ar": "مطعم", "active_count": -1},
        {"activity_code": "5610101", "activity_name_ar": "مطعم", "active_count": True},
    )
    for index, planted in enumerate(planted_rows):
        cache = tmp_path / f"case-{index}"
        _write_feeds(
            cache,
            active=[planted],
            classes=[("5610", "Restaurants")],
        )
        with pytest.raises(SpineError):
            load_activity_inputs(
                cache,
                (),
                review_path=_review_file(cache),
                supplier_membership=_NO_SUPPLIERS,
            )


def test_cache_to_spine_refuses_conflicting_feed_names(tmp_path: Path) -> None:
    """The two feeds must agree on the name of a shared code."""
    _write_feeds(
        tmp_path,
        active=[
            {
                "activity_code": "5610101",
                "activity_name_ar": "مطعم",
                "active_count": 1,
            },
        ],
        cancelled=[
            {
                "activity_code": "5610101",
                "activity_name_ar": "مقهى",
                "cancelled_count": 1,
            },
        ],
        classes=[("5610", "Restaurants")],
    )
    with pytest.raises(SpineError):
        load_activity_inputs(
            tmp_path,
            (),
            review_path=_review_file(tmp_path),
            supplier_membership=_NO_SUPPLIERS,
        )


def test_cache_to_spine_refuses_a_non_list_json_body(tmp_path: Path) -> None:
    """A JSON body that is not a list of row objects fails closed."""
    write_cached(tmp_path, _cache_entry("lic_active"), b'{"rows": []}')
    with pytest.raises(CacheError):
        load_activity_inputs(
            tmp_path,
            (),
            review_path=_review_file(tmp_path),
            supplier_membership=_NO_SUPPLIERS,
        )


def test_cache_to_spine_refuses_a_missing_registry_key(tmp_path: Path) -> None:
    """A registry without the cancelled key cannot build the spine."""
    registry = tuple(entry for entry in load_registry() if entry.key != "lic_cancelled")
    _write_feeds(
        tmp_path,
        active=[
            {
                "activity_code": "5610101",
                "activity_name_ar": "مطعم",
                "active_count": 1,
            },
        ],
        classes=[("5610", "Restaurants")],
    )
    with pytest.raises(SpineError):
        load_activity_inputs(
            tmp_path,
            (),
            registry=registry,
            review_path=_review_file(tmp_path),
            supplier_membership=_NO_SUPPLIERS,
        )


def test_manual_review_row_is_validated_like_a_csv_row() -> None:
    """A hand-built review row passes the same closed checks as a CSV row."""
    activities = (_activity("5610101", 10),)
    classes = _classes("5610")
    good = _review("5610101", "mapped", isic_class="5610")
    for planted in (
        replace(good, code_length=6),
        replace(good, status="approved"),
        replace(good, reason="looks fine"),
        replace(good, isic_class="561"),
        replace(good, reviewed_on="01/11/2026"),
        replace(good, reviewed_on="2026-02-30"),
    ):
        with pytest.raises(SpineError):
            build_spine(
                activities,
                classes,
                (planted,),
                (),
                supplier_membership=_NO_SUPPLIERS,
                reviewed_binding=review_binding(_VERSION, classes),
            )


def test_mapped_decision_requires_the_cached_name() -> None:
    """A mapped decision must name the cached activity exactly."""
    reviews = (
        replace(_review("5610101", "mapped", isic_class="5610"), name_ar="مقهى"),
    )
    with pytest.raises(SpineError):
        build_spine(
            (_activity("5610101", 10),),
            _classes("5610"),
            reviews,
            (),
            supplier_membership=_NO_SUPPLIERS,
            reviewed_binding=review_binding(_VERSION, _classes("5610")),
        )


def test_mapped_decision_requires_the_approved_reason() -> None:
    """A mapped status with the rejected reason is refused."""
    reviews = (
        replace(
            _review("5610101", "mapped", isic_class="5610"),
            reason="reviewer_rejected",
        ),
    )
    with pytest.raises(SpineError):
        build_spine(
            (_activity("5610101", 10),),
            _classes("5610"),
            reviews,
            (),
            supplier_membership=_NO_SUPPLIERS,
            reviewed_binding=review_binding(_VERSION, _classes("5610")),
        )


def test_rejected_decision_requires_the_rejected_reason() -> None:
    """A rejected status with the approved reason is refused."""
    reviews = (
        replace(
            _review("5610101", "not_mappable_rejected"),
            reason="reviewer_approved",
        ),
    )
    with pytest.raises(SpineError):
        build_spine(
            (_activity("5610101", 10),),
            _classes("5610"),
            reviews,
            (),
            supplier_membership=_NO_SUPPLIERS,
            reviewed_binding=review_binding(_VERSION, _classes("5610")),
        )


def test_in_scope_unreviewed_row_keeps_the_candidate_class() -> None:
    """A proposed class is kept as a candidate and never mapped."""
    reviews = (_review("5610101", "unreviewed", isic_class="5610"),)
    spine = build_spine(
        (_activity("5610101", 10),),
        _classes("5610"),
        reviews,
        (),
        supplier_membership=_NO_SUPPLIERS,
        reviewed_binding=review_binding(_VERSION, _classes("5610")),
    )
    row = spine.rows[0]
    assert row.status == "unreviewed"
    assert row.reason == "awaiting_human_review"
    assert row.isic_class == "5610"
    assert row.reviewed_by_role == ""
    assert row.reviewed_on == ""


def test_out_of_scope_row_keeps_no_candidate_class() -> None:
    """An outside-scope code stays classless and unsigned."""
    reviews = (_review("4100001", "unreviewed", isic_class="4100"),)
    spine = build_spine(
        (_activity("4100001", 0, 5),),
        _classes("4100"),
        reviews,
        (),
        supplier_membership=_NO_SUPPLIERS,
        reviewed_binding=review_binding(_VERSION, _classes("4100")),
    )
    row = spine.rows[0]
    assert row.status == "unreviewed"
    assert row.reason == "outside_review_scope"
    assert row.isic_class == ""
    assert row.reviewed_by_role == ""
    assert row.reviewed_on == ""


def test_sign_off_fields_only_on_derived_decisions() -> None:
    """A claimed mapping on a legacy, invalid or outside-scope code keeps no sign-off."""
    activities = (
        _activity("561000", 20),
        _activity("5699999", 10),
        _activity("4100001", 0, 5),
    )
    reviews = (
        _review("561000", "mapped", isic_class="5610"),
        _review("5699999", "mapped", isic_class="5699"),
        _review("4100001", "mapped", isic_class="4100"),
    )
    spine = build_spine(
        activities,
        _classes("4100", "5610"),
        reviews,
        (),
        supplier_membership=_NO_SUPPLIERS,
        reviewed_binding=review_binding(_VERSION, _classes("4100", "5610")),
    )
    for row in spine.rows:
        assert row.reviewed_by_role == ""
        assert row.reviewed_on == ""
    assert {row.code: row.status for row in spine.rows} == {
        "561000": "not_mappable_legacy",
        "5699999": "not_mappable_invalid_prefix",
        "4100001": "unreviewed",
    }


def _assert_unmappable(spine, activities, classes) -> None:
    graph = build_graph(spine, activities, classes, (), (), load_registry())
    targets = {
        edge.from_node_id: edge.to_node_id
        for edge in graph.edges
        if edge.edge_type == "classified_as"
    }
    assert targets["activity:561000"] == "activity_class:UNMAPPABLE"
    assert targets["activity:5699999"] == "activity_class:UNMAPPABLE"


def _dotted_review(code: str) -> ReviewRow:
    return ReviewRow(
        code=code,
        code_length=len(code),
        name_ar="اسم مخترع",
        isic_class="",
        status="not_mappable_legacy",
        reason="legacy_code_length",
        reviewed_by_role="data_reviewer",
        reviewed_on="2026-11-01",
    )


def _activity(code: str, active: int, cancelled: int = 0) -> ActivityRow:
    return ActivityRow(
        code=code,
        name_ar="نشاط " + code,
        active_count=active,
        cancelled_count=cancelled,
    )


def _classes(*codes: str) -> tuple[IsicClass, ...]:
    return tuple(
        IsicClass(code=code, label_en="Class " + code, label_ar="") for code in codes
    )


def _review(
    code: str,
    status: str,
    *,
    isic_class: str = "",
    role: str = "data_reviewer",
    on: str = "2026-11-01",
) -> ReviewRow:
    reasons = {
        "mapped": "reviewer_approved",
        "unreviewed": "awaiting_human_review",
        "not_mappable_rejected": "reviewer_rejected",
        "not_mappable_legacy": "legacy_code_length",
        "not_mappable_invalid_prefix": "invalid_isic_prefix",
    }
    return ReviewRow(
        code=code,
        code_length=len(code),
        name_ar="نشاط " + code,
        isic_class=isic_class,
        status=status,
        reason=reasons[status],
        reviewed_by_role=role,
        reviewed_on=on,
    )


_MAPPED_ROW = "5610101,7,مطعم,5610,mapped,reviewer_approved,data_reviewer,2026-11-01"


def _cache_entry(source_id: str):
    for entry in load_registry():
        if entry.source_id == source_id:
            return entry
    raise AssertionError("registry row missing: " + source_id)


def _write_feeds(
    cache: Path,
    *,
    active: list[dict[str, object]] | None = None,
    cancelled: list[dict[str, object]] | None = None,
    classes: list[dict[str, object]] | list[tuple[str, str]] | None = None,
) -> None:
    write_cached(
        cache, _cache_entry("lic_active"), real_feed_body("lic_active", active or [])
    )
    write_cached(
        cache,
        _cache_entry("lic_cancelled"),
        real_feed_body("lic_cancelled", cancelled or []),
    )
    write_cached(cache, _cache_entry("cls_isic4"), class_csv(classes or []))


def _write_restaurant_cache(folder: Path, *, label_en: str = "Restaurants") -> None:
    _write_feeds(
        folder,
        active=[
            {
                "activity_code": "5610101",
                "activity_name_ar": "مطعم",
                "active_count": 10,
            }
        ],
        classes=[("5610", label_en)],
    )


def _binding_beside(
    review: Path,
    *,
    version: str = "licence_codes_2025_05",
    titles: tuple[tuple[str, str, str], ...] = (("5610", "Restaurants", ""),),
) -> Path:
    import hashlib

    payload = {
        "code_system_version": version,
        "inputs": [
            {
                "code": code,
                "name": "class_title",
                "sha256": hashlib.sha256(
                    f"{code}\t{label_en}\t{label_ar}".encode()
                ).hexdigest(),
            }
            for code, label_en, label_ar in titles
        ],
    }
    path = review.with_name(review.stem + ".binding.json")
    path.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def _review_file(folder: Path, *rows: str) -> Path:
    path = folder / "review.csv"
    path.write_text(
        "code,code_length,name_ar,isic_class,status,reason,"
        "reviewed_by_role,reviewed_on\n" + "".join(row + "\n" for row in rows),
        encoding="utf-8",
    )
    return path


BASKET_REFUSALS = (
    ("R1", "basket file is not reviewed"),
    ("R2", "incomplete review fields"),
    ("R3", "supplier class is not four digits: 463"),
    ("R4", "supplier class has no activity code: 9999"),
    ("R5", "playbook classes differ from the baskets"),
)


def invalid_basket(refusal, monkeypatch):
    from eii_custodian.publicdata.review import activity

    document = invented_review()
    document["status"] = "reviewed: invented fixture"
    item = document["activities"][0]["inputs"][0]
    if refusal == "R1":
        document["status"] = "pending"
    elif refusal == "R2":
        del item["reviewer_role"]
    elif refusal == "R3":
        item["supplier_isic"] = "463"
    elif refusal == "R4":
        item["supplier_isic"] = "9999"
    elif refusal == "R5":
        monkeypatch.setattr(activity, "PLAYBOOK_CLASSES", frozenset({"5610", "5630"}))
    return document


@pytest.mark.parametrize(
    "refusal,detail", BASKET_REFUSALS, ids=[r[0] for r in BASKET_REFUSALS]
)
def test_basket_membership_refusals(refusal, detail, monkeypatch):
    from eii_custodian.publicdata.review import activity

    document = invalid_basket(refusal, monkeypatch)
    with pytest.raises(SpineError) as error:
        activity.basket_membership(document, (_activity("4630001", 0, 1),))
    assert error.value.detail == detail


def test_playbook_classes_match_reviewed_basket_activities():
    from eii_custodian.publicdata.review.activity import PLAYBOOK_CLASSES
    from eii_custodian.publicdata.series.baskets import ACTIVITIES

    assert PLAYBOOK_CLASSES == ACTIVITIES


@given(
    st.lists(
        st.tuples(
            st.sampled_from(("4630", "5610", "5510", "5630", "4100")),
            st.text(alphabet="0123456789", min_size=0, max_size=9),
        ),
        max_size=30,
    )
)
@example([])
@example([("4630", "001"), ("4630", "001"), ("4100", "999")])
@example([("4630", "000"), ("4630", "999")])
@example([("5510", "000"), ("5630", "999"), ("4630", "00"), ("4630", "0000")])
def test_basket_membership_selection_and_order(candidates):
    from eii_custodian.publicdata.review.activity import basket_membership

    document = invented_review()
    document["status"] = "reviewed: invented fixture"
    rows = [_activity("4630001", 0, 1)] + [
        _activity(group + suffix, 0, 1) for group, suffix in candidates
    ]
    playbook, suppliers = basket_membership(document, rows)
    expected_playbook = set()
    expected_suppliers = {"4630001"}
    for group, suffix in candidates:
        if len(suffix) == 3:
            if group == "4630":
                expected_suppliers.add(group + suffix)
            elif group != "4100":
                expected_playbook.add(group + suffix)
    assert playbook == tuple(sorted(expected_playbook))
    assert suppliers == SupplierMembership(tuple(sorted(expected_suppliers)), True)
    assert basket_membership(document, list(reversed(rows))) == (playbook, suppliers)
    assert basket_membership(document, rows + rows) == (playbook, suppliers)


def test_basket_membership_empty_baskets_have_complete_empty_suppliers():
    from eii_custodian.publicdata.review.activity import basket_membership

    document = invented_review()
    document["status"] = "reviewed: invented fixture"
    for row in document["activities"]:
        row["inputs"] = []
    assert basket_membership(document, ()) == ((), SupplierMembership((), True))


@pytest.mark.parametrize("suffix", (None, "", "00", "0000", "0000000"))
def test_basket_membership_requires_seven_digit_supplier(suffix):
    from eii_custodian.publicdata.review.activity import basket_membership

    document = invented_review()
    document["status"] = "reviewed: invented fixture"
    with pytest.raises(SpineError) as error:
        basket_membership(
            document, () if suffix is None else (_activity("4630" + suffix, 0, 1),)
        )
    assert error.value.detail == "supplier class has no activity code: 4630"


@pytest.mark.parametrize(
    "status", (None, "unreviewed", "reviewed", " reviewed: fixture")
)
def test_basket_membership_requires_reviewed_document(status):
    from eii_custodian.publicdata.review.activity import basket_membership

    document = invented_review()
    document["status"] = status
    with pytest.raises(SpineError) as error:
        basket_membership(document, (_activity("4630001", 0, 1),))
    assert error.value.detail == "basket file is not reviewed"
