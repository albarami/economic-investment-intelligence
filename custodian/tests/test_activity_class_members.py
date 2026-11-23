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
from custodian.tests.test_baskets import invented_review
from hypothesis import given
from hypothesis import strategies as st

from eii_custodian.publicdata.fetch.receipts import sha256_hex
from eii_custodian.publicdata.fetch.registry import load_registry
from eii_custodian.publicdata.fetch.snapshots import reviewed_selections
from eii_custodian.publicdata.review import activity as a
from eii_custodian.publicdata.review.cache_fixture import (
    CacheError,
    class_csv,
    real_feed_body,
    write_cached,
)

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
    activities=None,
    classes=CLASSES,
) -> tuple[str, ...]:
    """Call ``class_members`` the way every caller must: through build_spine."""
    return a.class_members(
        _baseline_activities() if activities is None else activities,
        classes,
        _baseline_reviews() if reviews is None else reviews,
        (),
        supplier_membership=_NO_SUPPLIERS,
        isic_class=isic_class,
        reviewed_binding=(
            a.review_binding(_VERSION, classes)
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


def test_5610_code_claimed_outside_the_review_scope_refuses_the_whole_class() -> None:
    """One changed input: the review row claims 5610101 is out of scope.

    The spine recomputes status from the feeds and its own scope, never from a
    claimed reason, and a seven-digit 56-prefixed code is always inside the
    spine's review scope (FOOD_PREFIX). So for class 5610 "out of scope" is
    this claim, and the claimed reason can never narrow the class silently:
    the row stays unreviewed and the whole class refuses.
    """
    claimed = replace(_review("5610101", "unreviewed"), reason="outside_review_scope")
    reviews = (
        claimed,
        *(row for row in _baseline_reviews() if row.code != "5610101"),
    )
    with pytest.raises(
        a.SpineError, match=_anchored("class has an unreviewed code: 5610101")
    ):
        _class_members(reviews)


def test_5610_activity_without_a_review_row_refuses_the_whole_class() -> None:
    """One changed input: 5610202 is in the feeds with no review row at all."""
    reviews = tuple(row for row in _baseline_reviews() if row.code != "5610202")
    with pytest.raises(
        a.SpineError, match=_anchored("class has an unreviewed code: 5610202")
    ):
        _class_members(reviews)


def test_out_of_scope_code_of_the_queried_class_refuses_the_whole_class() -> None:
    """One changed input: the queried class holds a code outside the scope.

    The spine's own outside_review_scope path, unreachable for a 56-prefixed
    code (FOOD_PREFIX puts every seven-digit one inside the scope), shown on a
    non-food class: 4100111 has no active licences and no review row, is
    unreviewed outside the scope, and class 4100 refuses with the same reason
    instead of answering with part of the class.
    """
    classes = (*CLASSES, a.IsicClass("4100", "INVENTED construction class", ""))
    with pytest.raises(
        a.SpineError, match=_anchored("class has an unreviewed code: 4100111")
    ):
        _class_members(
            (_review("5610101", "mapped"), _review("5610202", "mapped")),
            isic_class="4100",
            activities=(
                _activity("5610101"),
                _activity("5610202"),
                _activity("4100111", 0),
            ),
            classes=classes,
        )


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


def _committed_cache(tmp_path: Path) -> tuple[Path, Path, dict[str, str], str]:
    """An invented cache with two lic_active snapshots and its committed review.

    The pinned first snapshot holds 5610101 and 5610202; the second snapshot,
    written unselected, holds 5610303 and is reachable only through a
    selections map that names its digest. Returns the cache, the review file,
    the reviewed selections of the pinned snapshots and the second lic_active
    digest.
    """
    entries = load_registry()
    cache = tmp_path / "cache"
    write_cached(
        cache,
        a.entry_by_key(entries, "lic_active"),
        real_feed_body(
            "lic_active",
            [
                {
                    "activity_code": "5610101",
                    "activity_name_ar": "نشاط 5610101",
                    "active_count": 10,
                },
                {
                    "activity_code": "5610202",
                    "activity_name_ar": "نشاط 5610202",
                    "active_count": 6,
                },
            ],
        ),
    )
    write_cached(
        cache,
        a.entry_by_key(entries, "lic_cancelled"),
        real_feed_body(
            "lic_cancelled",
            [
                {
                    "activity_code": "4630001",
                    "activity_name_ar": "نشاط 4630001",
                    "cancelled_count": 4,
                }
            ],
        ),
    )
    write_cached(
        cache,
        a.entry_by_key(entries, "cls_isic4"),
        class_csv(
            [
                ("5610", "INVENTED restaurants class"),
                ("5630", "INVENTED beverages class"),
            ]
        ),
    )
    selected = reviewed_selections(cache)
    other_body = real_feed_body(
        "lic_active",
        [
            {
                "activity_code": "5610303",
                "activity_name_ar": "نشاط 5610303",
                "active_count": 7,
            }
        ],
    )
    write_cached(cache, a.entry_by_key(entries, "lic_active"), other_body, select=False)
    review = tmp_path / "review" / "activity_spine.csv"
    review.parent.mkdir()
    a.write_review_csv(
        review,
        (
            _review("5610101", "mapped"),
            _review("5610202", "mapped"),
            _review("5610303", "mapped"),
        ),
    )
    binding = a.review_binding(_VERSION, CLASSES)
    review.with_name("activity_spine.binding.json").write_text(
        json.dumps(
            {
                "code_system_version": binding.code_system_version,
                "inputs": [
                    {"name": name, "code": code, "sha256": sha}
                    for name, code, sha in binding.input_sha256
                ],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    baskets = invented_review()
    baskets["status"] = "reviewed: invented fixture"
    review.with_name("baskets.yaml").write_text(
        json.dumps(baskets, ensure_ascii=False), encoding="utf-8"
    )
    return cache, review, selected, sha256_hex(other_body)


def test_committed_class_members_uses_the_selections_map_given(tmp_path) -> None:
    """The map given is the map used; a different map reads a different snapshot.

    With no map the pinned selections are used unchanged. The map the data
    test passes after checking it against the method pins is the map that
    decides which snapshots the spine reads, so the F3 guarantee no longer
    depends on two reads of the same file.
    """
    cache, review, selected, other_digest = _committed_cache(tmp_path)
    assert a.committed_class_members(cache, "5610", review_path=review) == (
        "5610101",
        "5610202",
    )
    assert a.committed_class_members(
        cache, "5610", selections=selected, review_path=review
    ) == ("5610101", "5610202")
    other = {**selected, "lic_active": other_digest}
    assert other["lic_active"] != selected["lic_active"]
    assert a.committed_class_members(
        cache, "5610", selections=other, review_path=review
    ) == ("5610303",)


def test_committed_class_members_refuses_a_map_without_the_named_snapshot(
    tmp_path,
) -> None:
    """One changed input: the map names a snapshot the cache does not hold."""
    cache, review, selected, _ = _committed_cache(tmp_path)
    missing = {**selected, "lic_active": "b" * 64}
    with pytest.raises(
        CacheError, match=_anchored("lic_active: snapshot_index_invalid")
    ):
        a.committed_class_members(cache, "5610", selections=missing, review_path=review)


def test_committed_class_members_refuses_an_empty_selections_map(tmp_path) -> None:
    """One changed input: an empty map names no snapshot for any feed."""
    cache, review, _, _ = _committed_cache(tmp_path)
    with pytest.raises(
        CacheError, match=_anchored("lic_active: snapshot_path_invalid")
    ):
        a.committed_class_members(cache, "5610", selections={}, review_path=review)


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
