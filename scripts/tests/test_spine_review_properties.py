"""Domain-wide invariants of offline review packets, using invented identities."""

from dataclasses import replace

import pytest
from hypothesis import example, given
from hypothesis import strategies as st

from eii_custodian.publicdata.review.activity import ReviewRow, audit_sample
from spine_review import audit_record
from spine_triage_io import Refusal

SIGNER = "model review: invented_signer model, specialist"
AUDITOR = "model review: invented_auditor model, specialist"


@given(
    st.lists(st.booleans(), max_size=50),
    st.integers(min_value=1000000000, max_value=4294967295),
)
@example([], 1000000000)
@example([False], 4294967295)
@example([True] * 30, 1000000000)
@example([False] * 31, 4294967295)
def test_audit_order_and_decision_integrity(rejected: list[bool], seed: int) -> None:
    signed = tuple(
        ReviewRow(
            f"5610{index:03d}",
            7,
            "نشاط مخترع",
            "" if reject else "5610",
            "not_mappable_rejected" if reject else "mapped",
            "reviewer_rejected" if reject else "reviewer_approved",
            SIGNER,
            "2026-11-21",
        )
        for index, reject in enumerate(rejected)
    )
    makers = dict(
        batch_id="invented",
        seed=seed,
        signer_role=SIGNER,
        auditor_role=AUDITOR,
        audit_date="2026-11-22",
    )
    sample = audit_sample([row.code for row in signed], seed)
    audited = tuple(
        replace(row, reviewed_by_role=AUDITOR, reviewed_on="2026-11-22")
        for row in signed
        if row.code in sample
    )
    result = audit_record(signed, audited, makers)
    assert result == audit_record(
        tuple(reversed(signed)), tuple(reversed(audited)), makers
    )
    assert result["errors"] == 0
    assert len(sample) == min(30, len(signed))
    assert set(sample) <= {row.code for row in signed}
    if audited:
        row = audited[0]
        changed = replace(
            row,
            isic_class="5610" if row.isic_class == "" else "",
            status="mapped"
            if row.status == "not_mappable_rejected"
            else "not_mappable_rejected",
            reason="reviewer_approved"
            if row.reason == "reviewer_rejected"
            else "reviewer_rejected",
        )
        with pytest.raises(Refusal, match=r"^audit_decision_differs$"):
            audit_record(signed, (changed, *audited[1:]), makers)


@given(st.lists(st.sampled_from(("5610", "9999", "56", "561099")), max_size=40))
@example([])
@example(["5610"])
@example(["5610", "5610", "9999", "56", "561099"])
def test_eligibility_partitions_queue(prefixes: list[str]) -> None:
    from eii_custodian.publicdata.review.activity import (
        ActivityInputs,
        IsicClass,
        Spine,
        SpineRow,
    )
    from spine_review import eligible_rows

    queue = tuple(
        SpineRow(
            prefix + f"{index:03d}",
            len(prefix) + 3,
            "نشاط مخترع",
            "",
            "unreviewed",
            "awaiting_human_review",
            "",
            "",
        )
        for index, prefix in enumerate(prefixes)
    )
    inputs = ActivityInputs(
        Spine(queue, (), queue), (), (IsicClass("5610", "Invented", ""),)
    )
    eligible = eligible_rows(inputs)
    assert len(eligible) == prefixes.count("5610")
    assert tuple(row.code for row in eligible) == tuple(
        queue[index].code for index, prefix in enumerate(prefixes) if prefix == "5610"
    )
    assert len(queue) - len(eligible) == sum(prefix != "5610" for prefix in prefixes)
