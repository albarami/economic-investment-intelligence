"""Full text of the activity-spine decisions and binding refusals.

A change to the wording is a failed test. The texts below are literals.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from eii_custodian.publicdata.review.activity import (
    CODE_SYSTEM_VERSION,
    ActivityRow,
    IsicClass,
    ReviewRow,
    SpineError,
    SupplierMembership,
    _require_sign_off,
    _source_hash,
    build_spine,
    finalise_spine,
    load_recorded_binding,
    read_review_binding,
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


def test_supplier_membership_and_absent_codes_are_named() -> None:
    """A missing membership, an unfinished one, and an absent code are each named."""
    classes = (_CLASS,)
    activity = (_activity(),)
    _refuses(
        lambda: build_spine(
            activity, classes, (), (), supplier_membership=_as_any(None)
        ),
        "supplier membership is missing",
    )
    unfinished = SupplierMembership(codes=(), complete=False)
    _refuses(
        lambda: build_spine(activity, classes, (), (), supplier_membership=unfinished),
        "supplier membership is incomplete",
    )
    _refuses(
        lambda: build_spine(
            activity, classes, (), ("5610102",), supplier_membership=_NONE
        ),
        "playbook code absent from the feeds: 5610102",
    )
    membership = SupplierMembership(codes=("5610102",), complete=True)
    _refuses(
        lambda: build_spine(activity, classes, (), (), supplier_membership=membership),
        "supplier code absent from the feeds: 5610102",
    )


def test_finalise_names_every_missing_code() -> None:
    """Two unsigned in-scope codes are both named, separated by a comma."""
    spine = build_spine(
        (_activity("4100001"), _activity("4100002")),
        (IsicClass("4100", "Construction", ""),),
        (),
        (),
        supplier_membership=_NONE,
    )
    _refuses(
        lambda: finalise_spine(spine),
        "mandatory review missing: 4100001,4100002",
    )


def test_source_receipt_names_the_feed_without_a_hash() -> None:
    """A receipt whose hash is not 64 hex characters names that feed."""
    _refuses(
        lambda: _source_hash("lic_active", {"sha256": "abc"}),
        "source receipt has no hash: lic_active",
    )


def test_signed_file_without_a_binding_is_named(tmp_path: Path) -> None:
    """A signed review file with no binding beside it is refused."""
    path = tmp_path / "review.csv"
    path.write_text(_HEADER + "\n", encoding="utf-8")
    review = _row(
        status="mapped",
        reason="reviewer_approved",
        reviewed_by_role="data_reviewer",
        reviewed_on="2026-11-01",
    )
    _refuses(
        lambda: load_recorded_binding(path, (review,)),
        "review binding is missing",
    )


def test_mapped_claim_without_a_binding_object_is_named() -> None:
    """A mapped claim passed with no binding object is refused."""
    review = _row(status="mapped", reason="reviewer_approved", reviewed_by_role="")
    _refuses(lambda: _spine(review), "review binding is missing")


def test_a_different_code_system_version_is_named() -> None:
    """A binding recorded at another version is refused in full."""
    binding = review_binding("invented-codes-v2", (_CLASS,))
    review = _row(
        status="mapped",
        reason="reviewer_approved",
        reviewed_by_role="data_reviewer",
        reviewed_on="2026-11-01",
    )
    _refuses(
        lambda: _spine(review, binding=binding),
        "code-system version differs from the reviewed version",
    )


def test_a_changed_class_title_is_named() -> None:
    """A mapped approval of a title that has since changed is refused in full."""
    binding = review_binding(CODE_SYSTEM_VERSION, (_CLASS,))
    review = _row(
        status="mapped",
        reason="reviewer_approved",
        reviewed_by_role="data_reviewer",
        reviewed_on="2026-11-01",
    )
    _refuses(
        lambda: build_spine(
            (_activity(),),
            (IsicClass("5610", "Eating places", ""),),
            (review,),
            (),
            supplier_membership=_NONE,
            reviewed_binding=binding,
        ),
        "classification title differs from the reviewed title",
    )


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        (
            {"reviewed_by_role": "", "reviewed_on": ""},
            "mapped decision without a reviewer role",
        ),
        (
            {"reviewed_on": ""},
            "mapped decision without an ISO review date",
        ),
        (
            {"reason": "awaiting_human_review"},
            "mapped decision without the reviewer_approved reason",
        ),
        (
            {"name_ar": "اسم آخر"},
            "signed name differs from the cached name: 5610101",
        ),
        (
            {"isic_class": "4100"},
            "signed class differs from the prefix: 5610101",
        ),
    ],
)
def test_mapped_decision_names_the_defect(
    changes: dict[str, object], message: str
) -> None:
    """Each failed mapped sign-off is refused with its own full text."""
    fields = {
        "status": "mapped",
        "reason": "reviewer_approved",
        "isic_class": "5610",
        "reviewed_by_role": "data_reviewer",
        "reviewed_on": "2026-11-01",
    }
    fields.update(changes)
    _refuses(lambda: _spine(_row(**fields), binding=_binding()), message)


@pytest.mark.parametrize(
    ("changes", "message", "bind"),
    [
        (
            {"reviewed_by_role": "", "reviewed_on": ""},
            "rejected decision without a reviewer role",
            False,
        ),
        (
            {"reviewed_on": ""},
            "rejected decision without an ISO review date",
            True,
        ),
        (
            {"reason": "reviewer_approved"},
            "not_mappable_rejected decision without the reviewer_rejected reason",
            True,
        ),
    ],
)
def test_rejected_decision_names_the_defect(
    changes: dict[str, object], message: str, bind: bool
) -> None:
    """Each failed rejection is refused with its own full text."""
    fields = {
        "status": "not_mappable_rejected",
        "reason": "reviewer_rejected",
        "isic_class": "",
        "reviewed_by_role": "data_reviewer",
        "reviewed_on": "2026-11-01",
    }
    fields.update(changes)
    binding = _binding() if bind else None
    _refuses(lambda: _spine(_row(**fields), binding=binding), message)


def test_sign_off_names_a_malformed_date() -> None:
    """A date that matches the ISO shape and is not a day is named on the sign-off."""
    review = ReviewRow(
        code="5610101",
        code_length=7,
        name_ar="نشاط مخترع",
        isic_class="5610",
        status="mapped",
        reason="reviewer_approved",
        reviewed_by_role="data_reviewer",
        reviewed_on="2026-13-01",
    )
    _refuses(
        lambda: _require_sign_off(review, "mapped"),
        "mapped decision with a malformed date",
    )


def test_a_status_that_is_not_a_decision_is_named() -> None:
    """A legacy claim on a valid in-scope code is not a decision."""
    review = _row(
        status="not_mappable_legacy",
        reason="legacy_code_length",
        isic_class="",
    )
    _refuses(
        lambda: _spine(review),
        "review status is not a decision: 5610101",
    )


def test_an_acknowledgement_names_the_missing_reason() -> None:
    """A signed legacy code with the wrong reason names that decision."""
    review = ReviewRow(
        code="561001",
        code_length=6,
        name_ar="نشاط مخترع",
        isic_class="",
        status="not_mappable_legacy",
        reason="awaiting_human_review",
        reviewed_by_role="data_reviewer",
        reviewed_on="2026-11-01",
    )
    _refuses(
        lambda: build_spine(
            (_activity("561001"),),
            (),
            (review,),
            (),
            supplier_membership=_NONE,
            reviewed_binding=review_binding(CODE_SYSTEM_VERSION, ()),
        ),
        "not_mappable_legacy decision without the legacy_code_length reason",
    )


@pytest.mark.parametrize(
    ("active", "cancelled", "name", "message"),
    [
        (True, 0, "نشاط مخترع", "active_count is not a non-negative integer"),
        (1, -1, "نشاط مخترع", "cancelled_count is not a non-negative integer"),
        (1, 0, "", "name_ar is not text"),
    ],
)
def test_activity_fields_name_the_defect(
    active: object, cancelled: object, name: str, message: str
) -> None:
    """A bad count or a blank name is refused with the field's full text."""
    row = ActivityRow("5610101", name, _as_any(active), _as_any(cancelled))
    _refuses(
        lambda: build_spine((row,), (_CLASS,), (), (), supplier_membership=_NONE),
        message,
    )


def test_activity_sources_and_repeats_are_named() -> None:
    """An unknown source, a repeated source and a repeated code are each named."""
    _refuses(
        lambda: build_spine(
            (ActivityRow("5610101", "نشاط مخترع", 1, 0, ("invented_feed",)),),
            (_CLASS,),
            (),
            (),
            supplier_membership=_NONE,
        ),
        "unknown activity source invented_feed",
    )
    _refuses(
        lambda: build_spine(
            (ActivityRow("5610101", "نشاط مخترع", 1, 0, ("lic_active", "lic_active")),),
            (_CLASS,),
            (),
            (),
            supplier_membership=_NONE,
        ),
        "duplicate activity source 5610101",
    )
    _refuses(
        lambda: build_spine(
            (_activity(), _activity()),
            (_CLASS,),
            (),
            (),
            supplier_membership=_NONE,
        ),
        "duplicate activity code 5610101",
    )


def test_class_defects_are_named() -> None:
    """A class code of the wrong length, and a repeated class, are each named."""
    _refuses(
        lambda: build_spine(
            (_activity(),),
            (IsicClass("561", "Restaurants", ""),),
            (),
            (),
            supplier_membership=_NONE,
        ),
        "isic class is not four digits",
    )
    _refuses(
        lambda: build_spine(
            (_activity(),),
            (_CLASS, IsicClass("5610", "Eating places", "")),
            (),
            (),
            supplier_membership=_NONE,
        ),
        "duplicate isic class 5610",
    )


def test_a_repeated_review_code_is_named() -> None:
    """Two review objects for one code name that code."""
    review = _row()
    _refuses(
        lambda: build_spine(
            (_activity(),),
            (_CLASS,),
            (review, review),
            (),
            supplier_membership=_NONE,
        ),
        "duplicate review code 5610101",
    )


def test_binding_file_names_each_malformed_record(tmp_path: Path) -> None:
    """Each malformed binding is refused with its own full text."""
    digest = "a" * 64
    valid = {
        "code_system_version": CODE_SYSTEM_VERSION,
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
            json.dumps({"code_system_version": CODE_SYSTEM_VERSION}),
            "review binding fields are not the contract",
        ),
        (
            json.dumps({**valid, "code_system_version": "  "}),
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
    path = tmp_path / "invented.binding.json"
    for body, message in cases:
        path.write_text(body, encoding="utf-8")
        _refuses(lambda: read_review_binding(path), message)
