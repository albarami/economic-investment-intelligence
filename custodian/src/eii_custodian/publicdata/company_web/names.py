"""Reviewed web-name contribution to the existing complete collision inventory."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from ..name_inventory import Contribution
from .contracts import Candidate, WebError
from .review import accept


def contribution(
    candidates: Sequence[Candidate],
    reviews: Mapping[str, Mapping[str, Any]],
    extractor: Mapping[str, str],
) -> Contribution:
    names = []
    lineage = []
    for candidate in candidates:
        if candidate.field != "name":
            continue
        signed = reviews.get(candidate.digest)
        if accept(candidate, signed, extractor) is None:
            raise WebError("review_required")
        names.append(candidate.value)
        lineage.append(
            {
                "candidate_digest": candidate.digest,
                "page_sha256": candidate.page_sha256,
                "fragment_sha256": candidate.fragment_sha256,
                "parser": candidate.parser,
                "retrieved_utc": candidate.retrieved_utc,
                "url": candidate.url,
                "publisher": candidate.publisher,
                "licence_basis": candidate.licence_basis,
                "review": signed,
            }
        )
    return Contribution("company_web", tuple(names), {"inputs": lineage})


def build_inventory(
    labels: Sequence[str],
    candidates: Sequence[Candidate],
    reviews: Mapping[str, Mapping[str, Any]],
    extractor: Mapping[str, str],
    contributions: Sequence[Contribution],
    min_edit_distance: int,
) -> None:
    """Build boundary for S4-T05; the existing normaliser decides collisions."""
    from ..name_inventory import check_inventory

    result = check_inventory(
        labels,
        (*contributions, contribution(candidates, reviews, extractor)),
        min_edit_distance,
    )
    if not result.ok:
        raise WebError("name_collision")
