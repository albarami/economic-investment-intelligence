"""Reconcile every company, search result, page and field before safe counts."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from .contracts import DIGEST, FIELDS, Candidate, WebError
from .review import accept

PAGE_STATES = frozenset(
    {
        "matched",
        "name_mismatch",
        "ambiguous",
        "no_declared_block",
        "field_refused",
        "unavailable",
        "obstacle",
        "not_selected",
    }
)
ARCHIVED = frozenset(
    {"matched", "name_mismatch", "ambiguous", "no_declared_block", "field_refused"}
)


@dataclass(frozen=True)
class PageOutcome:
    url: str = field(repr=False)
    status: str
    candidates: tuple[Candidate, ...] = field(repr=False)
    identity: str = ""


@dataclass(frozen=True)
class Outcome:
    company_key: str = field(repr=False)
    search_status: str
    pages: tuple[PageOutcome, ...]


@dataclass(frozen=True)
class Evidence:
    counts: dict[str, int]
    retained: tuple[Candidate, ...] = field(repr=False)


def reconcile(
    expected_keys: Sequence[str],
    expected_urls: Mapping[str, Sequence[str]],
    outcomes: Sequence[Outcome],
    reviews: Mapping[str, Mapping[str, Any]],
    extractor: Mapping[str, str],
) -> Evidence:
    if (
        len(set(expected_keys)) != len(expected_keys)
        or set(expected_urls) != set(expected_keys)
        or len(outcomes) != len(expected_keys)
        or {o.company_key for o in outcomes} != set(expected_keys)
    ):
        raise WebError("company_counts_refused")
    counts = dict.fromkeys(
        (
            "companies",
            "searched",
            "search_obstacle",
            "search_unavailable",
            "pages",
            "fetched",
            "proposed",
            "missing",
            "block_refused_slots",
            "accepted",
            "rejected",
            "pending",
            "retained",
            "conflicts",
            *sorted(PAGE_STATES),
        ),
        0,
    )
    counts["companies"] = len(expected_keys)
    retained = []
    all_digests = set()
    for outcome in outcomes:
        if outcome.search_status not in {"searched", "obstacle", "unavailable"}:
            raise WebError("search_counts_refused")
        counts[
            "searched"
            if outcome.search_status == "searched"
            else "search_" + outcome.search_status
        ] += 1
        urls = tuple(expected_urls[outcome.company_key])
        if (
            len(set(urls)) != len(urls)
            or len(outcome.pages) != len(urls)
            or len({p.url for p in outcome.pages}) != len(outcome.pages)
            or {p.url for p in outcome.pages} != set(urls)
            or (outcome.search_status != "searched" and urls)
        ):
            raise WebError("page_counts_refused")
        for page in outcome.pages:
            if page.status not in PAGE_STATES:
                raise WebError("page_counts_refused")
            if (page.status in ARCHIVED and not DIGEST.fullmatch(page.identity)) or (
                page.identity
                and (
                    not DIGEST.fullmatch(page.identity)
                    or page.status not in ARCHIVED | {"obstacle"}
                )
            ):
                raise WebError("archive_counts_refused")
            if (page.status == "matched") != bool(page.candidates) or len(
                {c.field for c in page.candidates}
            ) != len(page.candidates):
                raise WebError("field_counts_refused")
            counts["pages"] += 1
            counts[page.status] += 1
            counts["fetched"] += int(bool(page.identity))
            if page.status == "matched":
                counts["missing"] += len(FIELDS) - len(page.candidates)
            if page.status == "field_refused":
                counts["block_refused_slots"] += len(FIELDS)
            for candidate in page.candidates:
                if (
                    candidate.company_key != outcome.company_key
                    or candidate.digest in all_digests
                ):
                    raise WebError("field_counts_refused")
                all_digests.add(candidate.digest)
                review = reviews.get(candidate.digest)
                accepted = accept(candidate, review, extractor)
                status = "pending" if review is None else str(review["decision"])
                counts["proposed"] += 1
                counts[status] += 1
                counts["conflicts"] += int(candidate.conflict)
                if accepted is not None:
                    retained.append(accepted)
    if set(reviews) - all_digests:
        raise WebError("orphan_review_refused")
    counts["retained"] = len(retained)
    if counts["retained"] != counts["accepted"] or counts["proposed"] != sum(
        counts[k] for k in ("accepted", "rejected", "pending")
    ):
        raise WebError("field_counts_refused")
    return Evidence(counts, tuple(retained))
