"""Decision 0075: INVENTED codes, roles, names and batches only."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, replace

import pytest

from eii_custodian.publicdata.review import activity as a

SIGNER = (
    "model review: invented_signer invented-model, bilingual classification specialist"
)
AUDITOR = (
    "model review: invented_auditor invented-model, bilingual classification specialist"
)
SEED = 3141592653
CLASSES = (a.IsicClass("5610", "INVENTED class title", ""),)
NONE = a.SupplierMembership((), True)


def rows(count=40, *, rejected=False):
    return tuple(
        a.ReviewRow(
            code=f"5610{index:03d}",
            code_length=7,
            name_ar="نشاط مخترع",
            isic_class="" if rejected else "5610",
            status="not_mappable_rejected" if rejected else "mapped",
            reason="reviewer_rejected" if rejected else "reviewer_approved",
            reviewed_by_role=SIGNER,
            reviewed_on="2026-11-19",
        )
        for index in range(count)
    )


def draw(codes, seed=SEED):
    # Independent statement of the recorded SHA-256 rank draw, then code order.
    ranked = sorted(
        codes,
        key=lambda code: (hashlib.sha256(f"{seed}:{code}".encode()).digest(), code),
    )
    return sorted(ranked[: min(30, len(codes))])


def digest(reviews):
    body = json.dumps(
        [asdict(row) for row in sorted(reviews, key=lambda row: row.code)],
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(body).hexdigest()


def batch(reviews):
    codes = [row.code for row in reviews]
    return dict(
        batch_id="INVENTED-batch",
        codes=codes,
        review_rows_sha256=digest(reviews),
        seed=SEED,
        sampled_codes=draw(codes),
        signer_role=SIGNER,
        auditor_role=AUDITOR,
        errors=0,
        audit_date="2026-11-20",
    )


def audit_file(tmp_path, batches):
    path = tmp_path / "activity_spine_audits.json"
    path.write_text(json.dumps(batches, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def build(reviews, path, *, bound_hash=None):
    binding = replace(
        a.review_binding(a.CODE_SYSTEM_VERSION, CLASSES),
        audit_sha256=bound_hash
        if bound_hash is not None
        else hashlib.sha256(path.read_bytes()).hexdigest(),
    )
    return a.build_spine(
        tuple(a.ActivityRow(row.code, row.name_ar, 1, 0) for row in reviews),
        CLASSES,
        reviews,
        (),
        supplier_membership=NONE,
        reviewed_binding=binding,
        audit_path=path,
    )


def test_model_signature_without_audit_is_refused():
    reviews = rows(1)
    with pytest.raises(a.SpineError, match="model audit binding is missing"):
        a.build_spine(
            (a.ActivityRow(reviews[0].code, reviews[0].name_ar, 1, 0),),
            CLASSES,
            reviews,
            (),
            supplier_membership=NONE,
            reviewed_binding=a.review_binding(a.CODE_SYSTEM_VERSION, CLASSES),
        )


@pytest.mark.parametrize(
    "role",
    [
        SIGNER.replace("model review:", "Model review:"),
        " " + SIGNER,
        SIGNER.replace("model review:", "model  review:"),
        SIGNER.replace("model review:", "model_review:"),
    ],
)
@pytest.mark.parametrize("rejected", [False, True])
def test_malformed_model_role_cannot_bypass_audit(role, rejected):
    reviews = (replace(rows(1, rejected=rejected)[0], reviewed_by_role=role),)
    with pytest.raises(a.SpineError, match="model review role is malformed"):
        a.build_spine(
            (a.ActivityRow(reviews[0].code, reviews[0].name_ar, 1, 0),),
            CLASSES,
            reviews,
            (),
            supplier_membership=NONE,
            reviewed_binding=a.review_binding(a.CODE_SYSTEM_VERSION, CLASSES),
        )


@pytest.mark.parametrize("count", [40, 12])
@pytest.mark.parametrize("rejected", [False, True])
def test_audited_batch_is_admitted(tmp_path, count, rejected):
    reviews = rows(count, rejected=rejected)
    record = batch(reviews)
    assert len(record["sampled_codes"]) == min(30, count)
    spine = build(reviews, audit_file(tmp_path, [record]))
    assert len(spine.rows) == count
    assert {row.status for row in spine.rows} == {reviews[0].status}
    assert {row.reviewed_by_role for row in spine.rows} == {SIGNER}
    assert spine.queue == ()
    assert a.audit_sample(tuple(reversed(record["codes"])), SEED) == tuple(
        record["sampled_codes"]
    )
    assert a.audit_rows_sha256(tuple(reversed(reviews))) == digest(reviews)


# Each row isolates one guard; the other batch metadata and binding stay valid.
PLANTS = [
    ("no_records", "model audit has no records"),
    ("no_batch", "model review code has no audited batch"),
    ("two_batches", "model review code has multiple audited batches"),
    ("changed_row", "model audit review rows hash differs"),
    ("short_sample", "model audit sample size differs"),
    ("wrong_draw", "model audit sample differs from seed draw"),
    ("errors", "model audit errors are not zero"),
    ("same_maker", "model audit makers are not different"),
    ("early_date", "model audit predates signing"),
    ("bad_seed", "model audit seed is out of range"),
]


@pytest.mark.parametrize("plant,reason", PLANTS, ids=[item[0] for item in PLANTS])
def test_audit_planted_refusals(tmp_path, plant, reason):
    reviews = rows()
    record = batch(reviews)
    records = [record]
    if plant == "no_records":
        records = []
    elif plant == "no_batch":
        records = [batch(reviews[1:])]
    elif plant == "two_batches":
        records.append({**record, "batch_id": "INVENTED-second"})
    elif plant == "changed_row":
        reviews = (replace(reviews[0], name_ar="نشاط مخترع معدل"), *reviews[1:])
    elif plant == "short_sample":
        record["sampled_codes"] = record["sampled_codes"][:-1]
    elif plant == "wrong_draw":
        sampled = record["sampled_codes"]
        other = next(code for code in record["codes"] if code not in sampled)
        record["sampled_codes"] = sorted([*sampled[:-1], other])
    elif plant == "errors":
        record["errors"] = 1
    elif plant == "same_maker":
        record["auditor_role"] = SIGNER.replace("invented-model", "other-model")
    elif plant == "early_date":
        record["audit_date"] = "2026-11-18"
    elif plant == "bad_seed":
        record["seed"] = 999999999
        record["sampled_codes"] = draw(record["codes"], 999999999)
    with pytest.raises(a.SpineError, match=reason):
        build(reviews, audit_file(tmp_path, records))


def test_changed_audit_bytes_refused_by_binding(tmp_path):
    reviews = rows()
    path = audit_file(tmp_path, [batch(reviews)])
    signed_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    path.write_text(path.read_text() + "\n", encoding="utf-8")
    with pytest.raises(
        a.SpineError, match="model audit file hash differs from binding"
    ):
        build(reviews, path, bound_hash=signed_hash)


def test_missing_audit_file_refused(tmp_path):
    path = tmp_path / "absent.json"
    with pytest.raises(a.SpineError, match="model audit file is not readable"):
        build(rows(), path, bound_hash="a" * 64)


def test_person_signature_keeps_existing_path():
    reviews = tuple(
        replace(row, reviewed_by_role="INVENTED person reviewer") for row in rows(1)
    )
    spine = a.build_spine(
        (a.ActivityRow(reviews[0].code, reviews[0].name_ar, 1, 0),),
        CLASSES,
        reviews,
        (),
        supplier_membership=NONE,
        reviewed_binding=a.review_binding(a.CODE_SYSTEM_VERSION, CLASSES),
    )
    assert spine.rows[0].status == "mapped"


def test_empty_invented_audits_admit_nothing(tmp_path):
    path = audit_file(tmp_path, [])
    assert json.loads(path.read_text()) == []
    with pytest.raises(a.SpineError, match="model audit has no records"):
        build(rows(1), path)


@pytest.mark.parametrize("seed", [True, 1.5, "3141592653", 4294967296, 999999999])
def test_seed_type_and_bounds_refused(tmp_path, seed):
    reviews = rows()
    record = {**batch(reviews), "seed": seed}
    with pytest.raises(a.SpineError, match="model audit seed is out of range"):
        build(reviews, audit_file(tmp_path, [record]))


@pytest.mark.parametrize("seed", [1000000000, 4294967295])
def test_seed_endpoints_admitted(tmp_path, seed):
    reviews = rows()
    record = {
        **batch(reviews),
        "seed": seed,
        "sampled_codes": draw([row.code for row in reviews], seed),
    }
    assert len(build(reviews, audit_file(tmp_path, [record])).rows) == 40


@pytest.mark.parametrize(
    "field,value,reason",
    [
        ("batch_id", "", "model audit batch id is invalid"),
        ("codes", [], "model audit codes are invalid"),
        ("codes", ["5610000", "5610000"], "model audit codes are invalid"),
        ("sampled_codes", "INVENTED", "model audit sampled codes are invalid"),
        ("signer_role", "INVENTED", "model audit role is malformed"),
        (
            "signer_role",
            SIGNER.replace("invented-model", "other-model"),
            "model audit signer differs from review",
        ),
        ("auditor_role", "INVENTED", "model audit role is malformed"),
        (
            "auditor_role",
            SIGNER.replace("invented_signer", "INVENTED_SIGNER"),
            "model audit makers are not different",
        ),
        ("audit_date", "2026-02-30", "model audit date is invalid"),
        ("audit_date", "2026-1-2", "model audit date is invalid"),
        ("errors", False, "model audit errors are not zero"),
        ("errors", "0", "model audit errors are not zero"),
        ("review_rows_sha256", "bad", "model audit review rows hash is invalid"),
    ],
)
def test_malformed_audit_record_refused(tmp_path, field, value, reason):
    reviews = rows()
    with pytest.raises(a.SpineError, match=reason):
        build(reviews, audit_file(tmp_path, [{**batch(reviews), field: value}]))


@pytest.mark.parametrize("payload", [{}, ["INVENTED"], [{"unknown": "INVENTED"}]])
def test_closed_audit_schema(tmp_path, payload):
    with pytest.raises(
        a.SpineError, match=r"model audit (list|record fields) (is|are) invalid"
    ):
        build(rows(), audit_file(tmp_path, payload))


def test_binding_reader_preserves_audit_hash(tmp_path):
    path = tmp_path / "invented.binding.json"
    path.write_text(
        json.dumps(
            {
                "code_system_version": a.CODE_SYSTEM_VERSION,
                "inputs": [],
                "audit_sha256": "b" * 64,
            }
        )
    )
    assert a.read_review_binding(path).audit_sha256 == "b" * 64
    path.write_text(
        json.dumps(
            {
                "code_system_version": a.CODE_SYSTEM_VERSION,
                "inputs": [],
                "audit_sha256": "bad",
            }
        )
    )
    with pytest.raises(a.SpineError, match="review binding audit hash is not a sha256"):
        a.read_review_binding(path)


def test_loader_reads_adjacent_bound_audit_file(tmp_path):
    """The normal loader cannot bypass the audited-model admission path."""
    from eii_custodian.publicdata.fetch.registry import load_registry
    from eii_custodian.publicdata.review.cache_fixture import (
        class_csv,
        real_feed_body,
        write_cached,
    )

    reviews = rows(12)
    path = audit_file(tmp_path, [batch(reviews)])
    review_path = tmp_path / "invented.csv"
    a.write_review_csv(review_path, reviews)
    old_binding = a.review_binding(a.CODE_SYSTEM_VERSION, CLASSES)
    a.binding_path(review_path).write_text(
        json.dumps(
            {
                "code_system_version": old_binding.code_system_version,
                "inputs": [
                    dict(name=name, code=code, sha256=sha)
                    for name, code, sha in old_binding.input_sha256
                ],
                "audit_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        )
    )
    entries = {entry.key: entry for entry in load_registry()}
    selections = {}
    for feed, body in (
        (
            "lic_active",
            real_feed_body(
                "lic_active",
                [
                    dict(
                        activity_code=row.code,
                        activity_name_ar=row.name_ar,
                        active_count=1,
                    )
                    for row in reviews
                ],
            ),
        ),
        ("lic_cancelled", real_feed_body("lic_cancelled", [])),
        ("cls_isic4", class_csv([("5610", "INVENTED class title")])),
    ):
        write_cached(tmp_path, entries[feed], body)
        selections[feed] = hashlib.sha256(body).hexdigest()
    loaded = a.load_activity_inputs(
        tmp_path,
        (),
        supplier_membership=NONE,
        review_path=review_path,
        selections=selections,
    )
    assert len(loaded.spine.rows) == 12
    assert {row.status for row in loaded.spine.rows} == {"mapped"}
    path.write_text("[]\n")
    with pytest.raises(
        a.SpineError, match="model audit file hash differs from binding"
    ):
        a.load_activity_inputs(
            tmp_path,
            (),
            supplier_membership=NONE,
            review_path=review_path,
            selections=selections,
        )


def test_separate_batches_and_person_review_admitted(tmp_path):
    signed = rows(52)
    human = replace(rows(53)[-1], reviewed_by_role="INVENTED person reviewer")
    path = audit_file(
        tmp_path,
        [
            batch(signed[:40]),
            {**batch(signed[40:]), "batch_id": "INVENTED-small-batch"},
        ],
    )
    spine = build((*signed, human), path)
    assert len(spine.rows) == 53
    assert {row.status for row in spine.rows} == {"mapped"}


def test_duplicate_batch_id_refused(tmp_path):
    signed = rows(52)
    path = audit_file(tmp_path, [batch(signed[:40]), batch(signed[40:])])
    with pytest.raises(a.SpineError, match="model audit batch id is duplicated"):
        build(signed, path)


def test_unsigned_batch_member_refused(tmp_path):
    reviews = rows(12)
    path = audit_file(tmp_path, [batch(rows(13))])
    with pytest.raises(
        a.SpineError, match="model audit code is not a signed model decision"
    ):
        build(reviews, path)


def test_audit_date_covers_latest_signing(tmp_path):
    reviews = (replace(rows()[0], reviewed_on="2026-11-21"), *rows()[1:])
    path = audit_file(tmp_path, [batch(reviews)])
    with pytest.raises(a.SpineError, match="model audit predates signing"):
        build(reviews, path)


def test_changed_rejected_row_refused(tmp_path):
    reviews = rows(rejected=True)
    path = audit_file(tmp_path, [batch(reviews)])
    changed = (replace(reviews[0], reviewed_on="2026-11-18"), *reviews[1:])
    with pytest.raises(a.SpineError, match="model audit review rows hash differs"):
        build(changed, path)


def test_bound_audit_hash_is_checked_before_any_model_signing(tmp_path):
    """An unsigned review does not waive a recorded audit-file binding."""
    reviews = tuple(
        replace(
            row,
            status="unreviewed",
            reason="awaiting_human_review",
            reviewed_by_role="",
            reviewed_on="",
        )
        for row in rows(1)
    )
    path = audit_file(tmp_path, [])
    bound_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    assert build(reviews, path).rows[0].status == "unreviewed"
    path.write_text("[]\n\n")
    with pytest.raises(
        a.SpineError, match="model audit file hash differs from binding"
    ):
        build(reviews, path, bound_hash=bound_hash)


def test_changed_rejected_title_refused(tmp_path):
    reviews = rows(1, rejected=True)
    path = audit_file(tmp_path, [batch(reviews)])
    binding = replace(
        a.review_binding(a.CODE_SYSTEM_VERSION, CLASSES),
        audit_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
    )
    with pytest.raises(
        a.SpineError, match="classification title differs from the reviewed title"
    ):
        a.build_spine(
            (a.ActivityRow(reviews[0].code, reviews[0].name_ar, 1, 0),),
            (replace(CLASSES[0], label_en="INVENTED changed title"),),
            reviews,
            (),
            supplier_membership=NONE,
            reviewed_binding=binding,
            audit_path=path,
        )


def test_missing_rejected_title_refused(tmp_path):
    reviews = rows(1, rejected=True)
    path = audit_file(tmp_path, [batch(reviews)])
    binding = replace(
        a.review_binding(a.CODE_SYSTEM_VERSION, CLASSES),
        audit_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
    )
    with pytest.raises(
        a.SpineError, match="classification title differs from the reviewed title"
    ):
        a.build_spine(
            (a.ActivityRow(reviews[0].code, reviews[0].name_ar, 1, 0),),
            (),
            reviews,
            (),
            supplier_membership=NONE,
            reviewed_binding=binding,
            audit_path=path,
        )


# Decision 0103: a model-signed derived acknowledgement row is audited exactly
# like a model-signed mapped or rejected row. Invented codes and roles only.

ACK_LEGACY = a.ReviewRow(
    code="300101",
    code_length=6,
    name_ar="نشاط مخترع",
    isic_class="",
    status="not_mappable_legacy",
    reason="legacy_code_length",
    reviewed_by_role=SIGNER,
    reviewed_on="2026-11-19",
)
ACK_INVALID_PREFIX = replace(
    replace(ACK_LEGACY, code="9900001", code_length=7),
    status="not_mappable_invalid_prefix",
    reason="invalid_isic_prefix",
)


def ack_build(reviews, path):
    return build(reviews, path)


def test_model_signed_acknowledgement_is_admitted_with_a_batch(tmp_path):
    reviews = (*rows(3), ACK_LEGACY, ACK_INVALID_PREFIX)
    spine = ack_build(reviews, audit_file(tmp_path, [batch(reviews)]))
    ack = {row.code: row for row in spine.rows}
    assert ack["300101"].reviewed_by_role == SIGNER
    assert ack["300101"].status == "not_mappable_legacy"
    assert ack["9900001"].status == "not_mappable_invalid_prefix"


def test_model_signed_acknowledgement_without_a_batch_is_refused(tmp_path):
    reviews = (*rows(3), ACK_LEGACY)
    record = batch(rows(3))
    with pytest.raises(a.SpineError, match="model review code has no audited batch"):
        ack_build(reviews, audit_file(tmp_path, [record]))


def test_model_signed_acknowledgement_in_two_batches_is_refused(tmp_path):
    reviews = (*rows(3), ACK_LEGACY)
    record = batch((*rows(3), ACK_LEGACY))
    records = [record, {**record, "batch_id": "INVENTED-second"}]
    with pytest.raises(
        a.SpineError, match="model review code has multiple audited batches"
    ):
        ack_build(reviews, audit_file(tmp_path, records))


def test_malformed_model_role_on_acknowledgement_is_refused(tmp_path):
    with pytest.raises(a.SpineError, match="model review role is malformed"):
        ack_build(
            (replace(ACK_LEGACY, reviewed_by_role=" model review: invented"),),
            audit_file(tmp_path, []),
        )


def test_person_signed_acknowledgement_keeps_its_existing_path():
    reviews = (replace(ACK_LEGACY, reviewed_by_role="INVENTED person reviewer"),)
    spine = a.build_spine(
        (a.ActivityRow(reviews[0].code, reviews[0].name_ar, 1, 0),),
        CLASSES,
        reviews,
        (),
        supplier_membership=NONE,
        reviewed_binding=a.review_binding(a.CODE_SYSTEM_VERSION, CLASSES),
    )
    assert spine.rows[0].status == "not_mappable_legacy"
    assert spine.rows[0].reviewed_by_role == "INVENTED person reviewer"
