"""Class membership of the activity spine: only audited admissions count.

INVENTED codes, names, roles and batches only.
"""

from __future__ import annotations

import hashlib
import json
import re
import tempfile
from dataclasses import replace
from pathlib import Path

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
_CODES = ("5610101", "5610202", "5630111", "5610303", "561000")
_STATUSES = ("mapped", "unreviewed", "not_mappable_rejected")
_SPACE_ROLE = "   "


def _anchored(message: str) -> str:
    """Anchor a refusal reason so a longer message cannot also match."""
    return re.escape(message) + r"\Z"


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
    """Two mapped, one rejected code of 5610, one of 5630, all signed."""
    return (
        _review("5610101", "mapped"),
        _review("5610202", "mapped"),
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


def _class_members(
    reviews=None,
    *,
    isic_class: str = "5610",
    reviewed_binding=None,
    audit_path: Path | None = None,
) -> tuple[str, ...]:
    """Call ``class_members`` the way every caller must: through build_spine."""
    return a.class_members(
        _baseline_activities(),
        CLASSES,
        _baseline_reviews() if reviews is None else reviews,
        (),
        supplier_membership=_NO_SUPPLIERS,
        isic_class=isic_class,
        reviewed_binding=(
            a.review_binding(_VERSION, CLASSES)
            if reviewed_binding is None
            else reviewed_binding
        ),
        audit_path=audit_path,
    )


def test_class_members_are_the_signed_mappings_of_one_class() -> None:
    """The happy path: every signed code of the class, never the others."""
    assert _class_members() == ("5610101", "5610202")
    assert _class_members(isic_class="5630") == ("5630111",)
    # A rejected code of the class is never a member.
    assert "5610303" not in _class_members()


def test_unreviewed_code_of_the_class_refuses_the_whole_class() -> None:
    """One changed input: 5610202 back to unreviewed refuses the class."""
    reviews = tuple(
        replace(row, status="unreviewed", reason="awaiting_human_review")
        if row.code == "5610202"
        else row
        for row in _baseline_reviews()
    )
    with pytest.raises(
        a.SpineError, match=_anchored("class has an unreviewed code: 5610202")
    ):
        _class_members(reviews)


def test_class_not_in_the_classification_is_refused() -> None:
    """One changed input: the class is not one of the classification's codes."""
    with pytest.raises(
        a.SpineError,
        match=_anchored("class is not in the classification: 9999"),
    ):
        _class_members(isic_class="9999")


def test_malformed_class_code_is_not_in_the_classification() -> None:
    """A class code that is not four digits is not in the classification."""
    with pytest.raises(
        a.SpineError, match=_anchored("class is not in the classification: 56")
    ):
        _class_members(isic_class="56")


def test_non_string_class_input_is_refused() -> None:
    """One changed input: the class argument is a list, not a class code."""
    with pytest.raises(
        a.SpineError,
        match=_anchored("class is not in the classification: ['5610']"),
    ):
        _class_members(isic_class=["5610"])  # type: ignore[arg-type]


def test_class_without_admitted_members_is_refused() -> None:
    """One changed input: the class's only mapped review becomes rejected."""
    reviews = tuple(
        replace(
            row,
            status="not_mappable_rejected",
            reason="reviewer_rejected",
            isic_class="",
        )
        if row.code == "5630111"
        else row
        for row in _baseline_reviews()
    )
    with pytest.raises(
        a.SpineError, match=_anchored("class has no admitted mapped code: 5630")
    ):
        _class_members(reviews, isic_class="5630")


def test_unsigned_mapped_row_is_refused() -> None:
    """A mapped review row without a role is refused by the spine build."""
    reviews = (replace(_review("5610101", "mapped"), reviewed_by_role=""),)
    with pytest.raises(
        a.SpineError, match=_anchored("mapped decision without a reviewer role")
    ):
        _class_members(reviews)


def _audit_body(codes: list[str]) -> str:
    """One valid batch record over the given codes, as JSON text."""
    reviews = (replace(_review("5610101", "mapped"), reviewed_by_role=SIGNER),)
    body = json.dumps(
        [
            dict(
                batch_id="INVENTED-batch",
                codes=codes,
                review_rows_sha256=a.audit_rows_sha256(reviews),
                seed=3141592653,
                sampled_codes=list(a.audit_sample(tuple(codes), 3141592653)),
                signer_role=SIGNER,
                auditor_role=AUDITOR,
                errors=0,
                audit_date="2026-11-20",
            )
        ],
        ensure_ascii=False,
    )
    return body + "\n"


def _model_case(tmp_path: Path, codes: list[str]) -> tuple[Path, a.ReviewedBinding]:
    """One model-signed mapped review with an audit file bound by hash."""
    audit_path = tmp_path / "activity_spine_audits.json"
    audit_path.write_text(_audit_body(codes), encoding="utf-8")
    binding = replace(
        a.review_binding(_VERSION, CLASSES),
        audit_sha256=hashlib.sha256(audit_path.read_bytes()).hexdigest(),
    )
    return audit_path, binding


def _model_reviews() -> tuple[a.ReviewRow, ...]:
    """The baseline reviews with 5610101 signed by the model signer."""
    return tuple(
        replace(row, reviewed_by_role=SIGNER) if row.code == "5610101" else row
        for row in _baseline_reviews()
    )


def test_model_signed_audited_batch_is_admitted(tmp_path) -> None:
    """A model-signed mapped row of an audited zero-error batch is a member."""
    audit_path, binding = _model_case(tmp_path, ["5610101"])
    reviews = _model_reviews()
    assert _class_members(reviews, reviewed_binding=binding, audit_path=audit_path) == (
        "5610101",
        "5610202",
    )


def test_model_signed_code_outside_the_audited_batch_is_refused(tmp_path) -> None:
    """One changed input: the audit batch no longer lists the signed code.

    A model signature alone admits nothing (decision 0075 item 3): the row is
    a member only while a bound, zero-error audited batch holds its code.
    """
    audit_path, binding = _model_case(tmp_path, ["5610999"])
    reviews = _model_reviews()
    with pytest.raises(
        a.SpineError,
        match=_anchored("model review code has no audited batch"),
    ):
        _class_members(reviews, reviewed_binding=binding, audit_path=audit_path)


@st.composite
def _cases(draw):
    """Invented review sets over both classes, with legacy and odd roles.

    The oracle never mirrors the implementation: it states, from the review
    rows alone, which refusal the spine build or the class query owes, and
    which members the class holds.
    """
    rows = []
    model = False
    bad: dict[str, str] = {}
    unreviewed: list[str] = []
    isic_class = draw(st.sampled_from(("5610", "5630")))
    for code in _CODES:
        status = draw(st.sampled_from(_STATUSES))
        if code == "561000":
            # Legacy rows are inert: whatever their review says, they are
            # never members and never block a class.
            if status == "unreviewed":
                rows.append(_review(code, status))
                continue
            role = draw(st.sampled_from(("data_reviewer", "", _SPACE_ROLE)))
            rows.append(_review(code, status, role=role))
            continue
        if status == "unreviewed":
            rows.append(_review(code, status))
            if code[:4] == isic_class:
                unreviewed.append(code)
            continue
        role = draw(st.sampled_from(("data_reviewer", "", _SPACE_ROLE, SIGNER)))
        if role == SIGNER:
            model = True
        elif role.strip() == "":
            bad[code] = (
                "mapped decision without a reviewer role"
                if status == "mapped"
                else "rejected decision without a reviewer role"
            )
        rows.append(_review(code, status, role=role))
    return tuple(rows), isic_class, model, bad, tuple(sorted(unreviewed))


@given(_cases())
def test_class_members_matches_an_independent_oracle(case) -> None:
    """The property: the answer is the class's admitted mapped codes, or the
    first refusal the spine build or the class query owes for these rows."""
    reviews, isic_class, model, bad, unreviewed = case
    expected = tuple(
        sorted(
            row.code
            for row in reviews
            if len(row.code) == 7
            and row.status == "mapped"
            and row.isic_class == isic_class
            and row.reviewed_by_role.startswith("data_reviewer")
        )
    )
    with tempfile.TemporaryDirectory() as temporary:
        audit_path = Path(temporary) / "activity_spine_audits.json"
        audit_path.write_text(_audit_body(["5610999"]), encoding="utf-8")
        binding = a.review_binding(_VERSION, CLASSES)
        if model:
            binding = replace(
                binding,
                audit_sha256=hashlib.sha256(audit_path.read_bytes()).hexdigest(),
            )
        if model:
            with pytest.raises(
                a.SpineError, match=_anchored("model review code has no audited batch")
            ):
                _class_members(
                    reviews,
                    isic_class=isic_class,
                    reviewed_binding=binding,
                    audit_path=audit_path,
                )
        elif bad:
            first = min(bad)
            with pytest.raises(a.SpineError, match=_anchored(bad[first])):
                _class_members(reviews, isic_class=isic_class, reviewed_binding=binding)
        elif unreviewed:
            with pytest.raises(
                a.SpineError,
                match=_anchored("class has an unreviewed code: " + unreviewed[0]),
            ):
                _class_members(reviews, isic_class=isic_class, reviewed_binding=binding)
        elif not expected:
            with pytest.raises(
                a.SpineError,
                match=_anchored("class has no admitted mapped code: " + isic_class),
            ):
                _class_members(reviews, isic_class=isic_class, reviewed_binding=binding)
        else:
            assert (
                _class_members(reviews, isic_class=isic_class, reviewed_binding=binding)
                == expected
            )
