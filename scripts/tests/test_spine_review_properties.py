"""Domain-wide invariants of offline review packets, using invented identities."""

from dataclasses import replace

import pytest
from hypothesis import example, given
from hypothesis import strategies as st

from eii_custodian.publicdata.review.activity import ReviewRow, audit_sample
from spine_review import append_audit, audit_record, require_fresh_seed
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
        assert audit_record(signed, (changed, *audited[1:]), makers)["errors"] == 1


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


JSON_VALUES = st.recursive(
    st.none()
    | st.booleans()
    | st.integers()
    | st.floats(allow_nan=False, allow_infinity=False)
    | st.text(),
    lambda children: (
        st.lists(children, max_size=5)
        | st.dictionaries(st.text(), children, max_size=5)
    ),
    max_leaves=10,
)


@given(
    st.lists(JSON_VALUES, max_size=15),
    st.sampled_from((b"", b" ", b"\n\t", b"\r\n")),
    st.booleans(),
)
@example([], b"\n\t", False)
@example([{"text": ' ] , [ " نشاط'}], b"\r\n", True)
def test_audit_append_preserves_bytes_and_decoded_history(
    history: list[object], whitespace: bytes, add: bool
) -> None:
    import json

    # Pretty Unicode and escaped compact JSON are both legitimate earlier bytes.
    body = (
        whitespace
        + json.dumps(history, ensure_ascii=False, indent=2).encode()
        + whitespace
    )
    batch: dict[str, object] | None = {"new": "independent"} if add else None
    result = append_audit(body, history, batch)
    assert json.loads(result) == history + ([batch] if add else [])
    if add:
        end = body.rfind(b"]")
        assert result.startswith(body[:end])
        assert result.endswith(body[end:])
    else:
        assert result == body


@given(
    st.lists(st.integers(min_value=1000000000, max_value=4294967295), max_size=40),
    st.integers(min_value=1000000000, max_value=4294967295),
)
@example([], 1000000000)
@example([4294967295], 4294967295)
@example([1000000000, 1000000000], 1000000000)
def test_seed_freshness_against_entire_history(
    seeds: list[int], candidate: int
) -> None:
    records = [{"seed": seed} for seed in seeds]
    if candidate in seeds:
        with pytest.raises(Refusal, match=r"^audit_seed_reused$"):
            require_fresh_seed(records, candidate)
    else:
        require_fresh_seed(records, candidate)


def test_draw_hash_ties_break_by_code() -> None:
    from types import SimpleNamespace
    from unittest.mock import patch

    codes = tuple(f"5610{index:03d}" for index in range(35))
    tied = SimpleNamespace(digest=lambda: b"same digest")
    with patch(
        "eii_custodian.publicdata.review.activity.hashlib.sha256", return_value=tied
    ):
        assert audit_sample(tuple(reversed(codes)), 3141592653) == codes[:30]


@given(
    st.lists(st.booleans(), max_size=50),
    st.text(),
    st.integers(min_value=1, max_value=30),
)
@example([], "", 1)
@example([False], "نشاط مخترع", 1)
@example([True] * 30, "fused split\n\t", 30)
@example([False] * 31, " ] , [ ", 3)
def test_derived_seed_projection_and_latest_refusal(
    rejected: list[bool], text: str, errors: int
) -> None:
    from dataclasses import asdict

    from test_spine_review_seed import seed_oracle

    from eii_custodian.publicdata.review.activity import audit_rows_sha256
    from spine_review import derived_audit_seed

    signed = tuple(
        ReviewRow(
            f"5610{index:03d}",
            7,
            text,
            "" if reject else "5610",
            "not_mappable_rejected" if reject else "mapped",
            text,
            text,
            text,
        )
        for index, reject in enumerate(rejected)
    )
    projected = [
        dict(code=row.code, status=row.status, isic_class=row.isic_class)
        for row in signed
    ]
    codes = [row.code for row in signed]
    first: dict[str, object] = dict(
        codes=codes,
        review_rows_sha256=audit_rows_sha256(signed),
        seed=seed_oracle(projected),
        errors=min(errors, len(codes), 30),
        review_rows=[asdict(row) for row in signed],
    )
    first["sampled_codes"] = list(audit_sample(codes, seed_oracle(projected)))
    if not signed:
        assert derived_audit_seed(signed, []) == seed_oracle([])
        with pytest.raises(Refusal, match=r"^refusal_record_invalid$"):
            derived_audit_seed(signed, [first])
        return
    latest = {**first, "seed": seed_oracle(projected, first)}
    latest["sampled_codes"] = list(audit_sample(codes, seed_oracle(projected, first)))
    assert derived_audit_seed(signed, []) == seed_oracle(projected)
    expected = seed_oracle(projected, latest)
    assert derived_audit_seed(signed, [first, latest]) == expected
    altered = tuple(
        replace(
            row,
            name_ar=text + "x",
            reason="different",
            reviewed_on="different",
            reviewed_by_role="different",
        )
        for row in reversed(signed)
    )
    assert derived_audit_seed(altered, [first, latest]) == expected
    reordered = {**latest, "codes": list(reversed(codes))}
    assert derived_audit_seed(signed, [first, reordered]) == expected
    assert 1000000000 <= expected <= 4294967295


def test_derived_seed_range_endpoints() -> None:
    from types import SimpleNamespace
    from unittest.mock import patch

    from spine_review import derived_audit_seed

    for digest, expected in (("0", 1000000000), (format(3294967295, "x"), 4294967295)):
        with patch(
            "spine_review.hashlib.sha256",
            return_value=SimpleNamespace(hexdigest=lambda digest=digest: digest),
        ):
            assert derived_audit_seed((), []) == expected
