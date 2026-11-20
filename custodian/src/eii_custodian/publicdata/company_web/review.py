"""Exact-field decisions; maker labels require lead-operated independent sessions."""

from __future__ import annotations

import unicodedata
from collections.abc import Mapping
from dataclasses import asdict
from typing import Any

from ..fetch.receipts import sha256_hex
from .contracts import VERSION, Candidate, Extraction, WebError, digest, safe_text
from .scope import identity


def _maker(value: str) -> str:
    return "".join(unicodedata.normalize("NFKC", value).casefold().split())


def record(
    candidate: Candidate, reviewer: Mapping[str, str], decision: str
) -> dict[str, object]:
    if decision not in {"accepted", "rejected", "pending"}:
        raise WebError("review_refused")
    return {
        "candidate_digest": candidate.digest,
        "field": candidate.field,
        "value_sha256": digest(candidate.value),
        "page_sha256": candidate.page_sha256,
        "fragment_sha256": candidate.fragment_sha256,
        "parser": candidate.parser,
        "extractor_sha256": candidate.extractor_sha256,
        "reviewer": identity(reviewer),
        "decision": decision,
    }


def accept(
    candidate: Candidate, review: Mapping[str, Any] | None, extractor: Mapping[str, str]
) -> Candidate | None:
    candidate.validate()
    builder = identity(extractor)
    if candidate.extractor_sha256 != digest(builder):
        raise WebError("extractor_binding_refused")
    if review is None:
        return None
    try:
        reviewer = identity(review["reviewer"])
        if (
            _maker(reviewer["maker"]) == _maker(builder["maker"])
            or reviewer["run_id"] == builder["run_id"]
        ):
            raise WebError("independent_review_required")
        if record(candidate, reviewer, review["decision"]) != review:
            raise WebError("review_binding_refused")
    except (KeyError, TypeError):
        raise WebError("review_refused") from None
    return candidate if review["decision"] == "accepted" else None


def reviewer_bundle(company_name: object, result: Extraction) -> dict[str, object]:
    name = safe_text("name", company_name)
    if (
        result.status != "matched"
        or sha256_hex(result.fragment) != result.candidates[0].fragment_sha256
    ):
        raise WebError("review_bundle_refused")
    candidates = []
    for candidate in result.candidates:
        candidate.validate()
        # No register key/row/fields, conflict value or extractor input is disclosed.
        candidates.append(
            {
                k: v
                for k, v in asdict(candidate).items()
                if k not in {"company_key", "conflict"}
            }
            | {
                "candidate_digest": candidate.digest,
                "value_sha256": digest(candidate.value),
            }
        )
    return {
        "company_name": name,
        "fragment": result.fragment.decode(),
        "fragment_sha256": sha256_hex(result.fragment),
        "page_sha256": result.page_sha256,
        "url": result.url,
        "parser": VERSION,
        "candidates": candidates,
    }
