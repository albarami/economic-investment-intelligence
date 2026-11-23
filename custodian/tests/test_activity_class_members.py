"""Class membership of the activity spine: only admitted signatures count.

INVENTED codes, names, roles and batches only.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace

import pytest
from hypothesis import given
from hypothesis import strategies as st

from eii_custodian.publicdata.review import activity as a

_VERSION = "licence_codes_2025_05"
_NO_SUPPLIERS = a.SupplierMembership(codes=(), complete=True)
CLASSES = (
    a.IsicClass("5610", "INVENTED restaurants class", ""),
    a.IsicClass("5630", "INVENTED beverages class", ""),
)
SIGNER = "model review: invented_signer invented-model, classification specialist"
AUDITOR = "model review: invented_auditor invented-model, classification specialist"


def _activity(code: str, active: int = 1) -> a.ActivityRow:
    return a.ActivityRow(
        code=code, name_ar="نشاط " + code, active_count=active, cancelled_count=0
    )


def _review(code: str, status: str, *, role: str = "data_reviewer") -> a.ReviewRow:
    reasons = {
        "mapped": "reviewer_approved",
        "unreviewed": "awaiting_human_review",
        "not_mappable_rejected": "reviewer_rejected",
        "not_mappable_legacy": "legacy_code_length",
        "not_mappable_invalid_prefix": "invalid_isic_prefix",
    }
    signed = status in {"mapped", "not_mappable_rejected"}
    return a.ReviewRow(
        code=code,
        code_length=len(code),
        name_ar="نشاط " + code,
        isic_class=code[:4] if status == "mapped" else "",
        status=status,
        reason=reasons[status],
        reviewed_by_role=role if signed else "",
        reviewed_on="2026-11-01" if signed else "",
    )


def _baseline_reviews() -> tuple[a.ReviewRow, ...]:
    """One mapped, one unreviewed and one rejected code of 5610, one of 5630."""
    return (
        _review("5610101", "mapped"),
        _review("5610202", "unreviewed"),
        _review("5610303", "not_mappable_rejected"),
        _review("5630111", "mapped"),
    )


def _baseline_activities() -> tuple[a.ActivityRow, ...]:
    return (
        _activity("5610101"),
        _activity("5610202"),
        _activity("5610303"),
        _activity("5630111"),
        _activity("561000"),
        _activity("4100111"),
    )


def _baseline_spine(reviews=None) -> a.Spine:
    return a.build_spine(
        _baseline_activities(),
        CLASSES,
        _baseline_reviews() if reviews is None else reviews,
        (),
        supplier_membership=_NO_SUPPLIERS,
        reviewed_binding=a.review_binding(_VERSION, CLASSES),
    )


def test_class_members_are_the_signed_mappings_of_one_class() -> None:
    """The happy path: one class holds its mapped codes, never the others."""
    spine = _baseline_spine()
    assert a.class_members(spine, CLASSES, "5610") == ("5610101",)
    assert a.class_members(spine, CLASSES, "5630") == ("5630111",)


def test_class_members_never_count_unreviewed_or_rejected_codes() -> None:
    """An unreviewed code and a rejected code of the class are never members."""
    spine = _baseline_spine()
    members = a.class_members(spine, CLASSES, "5610")
    assert "5610202" not in members  # unreviewed
    assert "5610303" not in members  # rejected
    assert spine.rows and all(
        row.status != "mapped" or row.code in members
        for row in spine.rows
        if row.isic_class == "5610"
    )


def test_class_not_in_the_classification_is_refused() -> None:
    """One changed input: the class is not one of the classification's codes."""
    spine = _baseline_spine()
    with pytest.raises(a.SpineError, match="class is not in the classification: 9999"):
        a.class_members(spine, CLASSES, "9999")


def test_malformed_class_code_is_not_in_the_classification() -> None:
    """A class code that is not four digits is not in the classification."""
    spine = _baseline_spine()
    with pytest.raises(a.SpineError, match="class is not in the classification: 56"):
        a.class_members(spine, CLASSES, "56")


def test_class_without_admitted_members_is_refused() -> None:
    """One changed input: the class's only mapped review becomes unreviewed."""
    reviews = tuple(
        replace(row, status="unreviewed", reason="awaiting_human_review")
        if row.code == "5630111"
        else row
        for row in _baseline_reviews()
    )
    spine = _baseline_spine(reviews)
    with pytest.raises(a.SpineError, match="class has no admitted mapped code: 5630"):
        a.class_members(spine, CLASSES, "5630")


def test_unsigned_mapped_row_is_refused() -> None:
    """A mapped row without an admitted signature refuses the whole call."""
    spine = a.Spine(
        rows=(
            a.SpineRow(
                code="5610404",
                code_length=7,
                name_ar="نشاط 5610404",
                isic_class="5610",
                status="mapped",
                reason="reviewer_approved",
                reviewed_by_role="",
                reviewed_on="",
            ),
        ),
        coverage=(),
        queue=(),
    )
    with pytest.raises(
        a.SpineError, match="mapped row has no admitted signature: 5610404"
    ):
        a.class_members(spine, CLASSES, "5610")


def test_model_signed_audited_batch_is_admitted(tmp_path) -> None:
    """A model-signed mapped row of an audited zero-error batch is a member."""
    reviews = (
        replace(
            _review("5610101", "mapped"),
            reviewed_by_role=SIGNER,
        ),
    )
    body = json.dumps(
        [
            dict(
                batch_id="INVENTED-batch",
                codes=[row.code for row in reviews],
                review_rows_sha256=a.audit_rows_sha256(reviews),
                seed=3141592653,
                sampled_codes=a.audit_sample(
                    tuple(row.code for row in reviews), 3141592653
                ),
                signer_role=SIGNER,
                auditor_role=AUDITOR,
                errors=0,
                audit_date="2026-11-20",
            )
        ],
        ensure_ascii=False,
    )
    audit_path = tmp_path / "activity_spine_audits.json"
    audit_path.write_text(body + "\n", encoding="utf-8")
    binding = replace(
        a.review_binding(_VERSION, CLASSES),
        audit_sha256=hashlib.sha256(audit_path.read_bytes()).hexdigest(),
    )
    spine = a.build_spine(
        (_activity("5610101"),),
        CLASSES,
        reviews,
        (),
        supplier_membership=_NO_SUPPLIERS,
        reviewed_binding=binding,
        audit_path=audit_path,
    )
    assert a.class_members(spine, CLASSES, "5610") == ("5610101",)


_STATUSES = ("mapped", "unreviewed", "not_mappable_rejected")


@st.composite
def _spines(draw):
    """Every invented spine over a fixed code set, all statuses, signed or not."""
    codes = ("5610101", "5610202", "5630111", "5610303")
    rows = []
    for code in codes:
        status = draw(st.sampled_from(_STATUSES))
        signed = status in {"mapped", "not_mappable_rejected"} and draw(st.booleans())
        rows.append(
            a.SpineRow(
                code=code,
                code_length=7,
                name_ar="نشاط " + code,
                isic_class=code[:4] if status == "mapped" else "",
                status=status,
                reason={
                    "mapped": "reviewer_approved",
                    "unreviewed": "awaiting_human_review",
                    "not_mappable_rejected": "reviewer_rejected",
                }[status],
                reviewed_by_role="data_reviewer" if signed else "",
                reviewed_on="2026-11-01" if signed else "",
            )
        )
    return a.Spine(rows=tuple(rows), coverage=(), queue=())


@given(_spines())
def test_class_members_matches_an_independent_oracle(spine: a.Spine) -> None:
    """The property: the answer is exactly the class's admitted mapped codes."""
    expected = tuple(
        sorted(
            row.code
            for row in spine.rows
            if row.status == "mapped"
            and row.isic_class == "5610"
            and row.reviewed_by_role.strip() != ""
        )
    )
    unsigned = any(
        row.status == "mapped" and row.reviewed_by_role.strip() == ""
        for row in spine.rows
        if row.isic_class == "5610"
    )
    if unsigned:
        with pytest.raises(a.SpineError, match="mapped row has no admitted signature"):
            a.class_members(spine, CLASSES, "5610")
    elif not expected:
        with pytest.raises(a.SpineError, match="class has no admitted mapped code"):
            a.class_members(spine, CLASSES, "5610")
    else:
        assert a.class_members(spine, CLASSES, "5610") == expected
