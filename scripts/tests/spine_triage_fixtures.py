"""Handwritten invented cache using the S2-T04 fixture contract."""

import json
from dataclasses import replace
from pathlib import Path

from eii_custodian.publicdata.fetch.registry import load_registry
from eii_custodian.publicdata.review.activity import (
    SupplierMembership,
    load_activity_inputs,
    write_queue_csv,
    write_review_csv,
)
from eii_custodian.publicdata.review.cache_fixture import (
    class_csv,
    real_feed_body,
    write_cached,
)


def invented_cache(root: Path) -> list[str]:
    """Return command arguments for an entirely invented review queue."""
    cache = root / "data/public_cache"
    cache.mkdir(parents=True)
    bodies = {
        "lic_active": real_feed_body(
            "lic_active",
            [
                {
                    "activity_code": code,
                    "activity_name_ar": "نشاط اصطناعي للاختبار",
                    "active_count": count,
                }
                for code, count in (("5610901", 9), ("5610902", 9), ("561099", 3))
            ],
        ),
        "lic_cancelled": real_feed_body("lic_cancelled", []),
        "cls_isic4": class_csv([("5610", "Invented test class")]),
    }
    for entry in load_registry():
        if entry.key in bodies:
            write_cached(cache, entry, bodies[entry.key])
    review = cache / "review.csv"
    queue = cache / "queue.csv"
    membership = cache / "membership.json"
    write_review_csv(review, ())
    inputs = load_activity_inputs(
        cache, (), supplier_membership=SupplierMembership((), True), review_path=review
    )
    write_queue_csv(queue, inputs.spine.queue)
    membership.write_text(
        json.dumps(
            {"playbook_codes": [], "supplier_codes": [], "supplier_complete": True}
        )
    )
    return [
        "--cache",
        str(cache),
        "--review",
        str(review),
        "--queue",
        str(queue),
        "--membership",
        str(membership),
        "--run-id",
        "invented-run",
    ]


def recorded_answers(root: Path, requests: dict[str, object]) -> Path:
    """Replay confident match and mismatch for the invented pair."""
    from typing import cast

    from eii_gateway.memo import input_hash
    from eii_gateway.types import Request

    rows = []
    for index, raw in enumerate(requests.values()):
        request = replace(cast(Request, raw), input_class="synthetic")
        label = "yes" if index == 0 else "no"
        rows.append(
            {
                "case_id": request.case_id,
                "input_sha256": input_hash(request),
                "order": ["no", "yes"],
                "label": label,
                "scores": {
                    "yes": 0.99 if label == "yes" else 0.01,
                    "no": 0.01 if label == "yes" else 0.99,
                },
                "tokens": 0,
            }
        )
    path = root / "data/public_cache/recorded.json"
    path.write_text(json.dumps(rows))
    return path
