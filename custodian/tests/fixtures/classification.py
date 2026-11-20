"""Invented dictionaries and review bytes; these establish no real mapping."""

import json
from copy import deepcopy
from hashlib import sha256
from pathlib import Path

REVIEW = Path("custodian/publicdata/review/product_activity_occupation.v1.json")
SCHEMA = REVIEW.with_suffix(".schema.json")
DIGEST = "a" * 64
VERSION = "cus_imp_2025:" + DIGEST


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def product(code="1000.0001.0001", *, parent=False):
    return {
        "system": "customs_tariff",
        "version": ("cus_imp_2019:" + "b" * 64) if parent else VERSION,
        "level": "tariff8" if parent else "tariff12",
        "code": "SYN-TARIFF-" + code,
    }


def industry(code="a"):
    return {
        "system": "manufacturing_industry",
        "version": "mfg_industry/syn-" + code + ":" + DIGEST,
        "level": "industry",
        "code": "mfg_industry/syn-" + code,
    }


def occupation(code="1"):
    return {
        "system": "occupation_group",
        "version": "occupation_group.v1",
        "level": "major_group",
        "code": code,
    }


def isic(code="1001"):
    return {
        "system": "isic_class",
        "version": "licence_codes_2025_05",
        "level": "class",
        "code": "SYN-ISIC-" + code,
    }


def weight(value="0.4"):
    return {
        "value": value,
        "scope": "syn-published-scope",
        "denominator": "syn-published-denominator",
        "evidence_ref": "syn-basis",
    }


def link(target, key="syn-link-a", *, official=False, split=None):
    return {
        "link_id": key,
        "target": deepcopy(target),
        "basis_kind": "official" if official else "editorial_reviewed",
        "basis_ref": "syn-basis",
        "source_refs": ["syn-basis"],
        "rationale": None
        if official
        else "Invented explicit classification judgement.",
        "configuration_sha256": None if official else "c" * 64,
        "reviewed_by_role": "classification_reviewer",
        "reviewed_on": "2026-11-20",
        "weight": split,
    }


def group(
    source, targets=(), *, kind="product_to_activity", status="mapped", reason=None
):
    reasons = {
        "mapped": "reviewer_approved",
        "unmapped": "reviewer_rejected_no_target",
        "ambiguous": "reviewer_undecided",
        "unreviewed": "awaiting_human_review",
    }
    return {
        "link_kind": kind,
        "source": deepcopy(source),
        "status": status,
        "reason": reasons[status] if reason is None else reason,
        "reviewed_by_role": "" if status == "unreviewed" else "classification_reviewer",
        "reviewed_on": "" if status == "unreviewed" else "2026-11-20",
        "links": list(targets),
    }


def documents():
    p, a, o = product(), industry(), occupation()
    review = {
        "schema_version": "product_activity_occupation.v1",
        "mapping_revision": "syn-review-a",
        "mode": "invented_fixture",
        "evidence": [
            {
                "evidence_id": "syn-basis",
                "registry_key": "cus_imp_2025",
                "snapshot_sha256": DIGEST,
                "locator": "syn-table/syn-row",
            }
        ],
        "groups": [
            group(p, [link(a)]),
            group(a, [link(o, "syn-link-b")], kind="activity_to_occupation"),
        ],
    }
    context = {
        "mode": "invented_fixture",
        "snapshots": [
            {
                "registry_key": key,
                "snapshot_sha256": digest,
                "publisher": "SYN-PUBLISHER",
                "title": "SYN-DATASET",
                "licence": "SYN-LICENCE",
                "retrieved_on": "2026-11-19",
                "url": "https://example.invalid/syn-source",
            }
            for key, digest in [
                ("cus_imp_2025", DIGEST),
                ("cus_imp_2019", "b" * 64),
                ("mfg_industry/syn-a", DIGEST),
                ("mfg_industry/syn-b", DIGEST),
            ]
        ],
        "endpoint_meanings": [],
        "tariff_families": [],
    }
    for endpoint in [p, a, o, industry("b"), occupation("2"), isic()]:
        declare(context, endpoint)
    return review, context


def declare(context, endpoint):
    if not any(row["endpoint"] == endpoint for row in context["endpoint_meanings"]):
        context["endpoint_meanings"].append(
            {"endpoint": deepcopy(endpoint), "meaning_sha256": "d" * 64}
        )


def binding(review_body, context):
    return encoded(
        {
            "schema_version": "product_activity_occupation.binding.v1",
            "review_sha256": sha256(review_body).hexdigest(),
            "schema_sha256": sha256(SCHEMA.read_bytes()).hexdigest(),
            "context_sha256": sha256(encoded(context)).hexdigest(),
        }
    )


def parse(review, context, *, binding_body=None, allow_invented=True):
    from eii_custodian.publicdata.review.classification import parse_crosswalk

    body = encoded(review)
    return parse_crosswalk(
        body,
        binding(body, context) if binding_body is None else binding_body,
        context=context,
        allow_invented=allow_invented,
    )


def family_documents():
    review, context = documents()
    parent = product("1000.0001", parent=True)
    children = [product(), product("1000.0001.0002")]
    for endpoint in [parent, *children]:
        declare(context, endpoint)
    context["tariff_families"] = [
        {
            "parent": parent,
            "children": children,
            "registry_key": "cus_imp_2025",
            "snapshot_sha256": DIGEST,
        }
    ]
    review["groups"].append(group(children[1], [link(industry(), "syn-link-c")]))
    return review, context, parent


def production_documents():
    """Invented associations against committed metadata, never actual approval.

    Requires the documented engine group: load_registry validates the full
    committed registry through its existing engine-dependent readers. No data
    cache, receipt or network is read; the hashes and meanings are invented.
    """
    from eii_custodian.publicdata.fetch.registry import load_registry

    registry = {entry.key: entry for entry in load_registry()}
    key = "mfg_industry/manufacture-of-basic-metals"
    p = product()
    p["code"] = p["code"].removeprefix("SYN-TARIFF-")
    a = {
        "system": "manufacturing_industry",
        "level": "industry",
        "code": key,
        "version": key + ":" + DIGEST,
    }
    review, _ = documents()
    review.update(mode="production", groups=[group(p, [link(a)])])
    context = {
        "mode": "production",
        "snapshots": [],
        "endpoint_meanings": [],
        "tariff_families": [],
    }
    for source in ("cus_imp_2025", key):
        entry = registry[source]
        context["snapshots"].append(
            {
                "registry_key": source,
                "snapshot_sha256": DIGEST,
                "publisher": entry.publisher,
                "title": entry.title_en,
                "licence": entry.licence_id,
                "retrieved_on": "2026-11-19",
                "url": entry.url,
            }
        )
    for item in (p, a):
        declare(context, item)
    return review, context
