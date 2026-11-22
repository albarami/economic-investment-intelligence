"""Deterministic selection of researched height tokens, without transcription."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

REASONS = (
    "not_building",
    "kind_not_admitted",
    "excerpt_mismatch",
    "same_kind_disagreement",
)
KINDS = ("roof", "architectural")
VALUE_TOKEN = re.compile(r"[0-9]+(?:\.[0-9]+)?")
UNITS = frozenset({"m", "metre", "metres", "meter", "meters"})


@dataclass(frozen=True)
class SelectedLandmark:
    landmark_id: str
    name_en: str
    page: Mapping[str, Any]


@dataclass(frozen=True)
class Selection:
    admitted: tuple[SelectedLandmark, ...]
    outcomes: tuple[tuple[str, str], ...]
    counts: dict[str, int]
    by_kind: dict[str, int]


def researched_pages(candidate: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    """The primary page and its second page, in the research's declared order."""
    second = candidate.get("second_page")
    return (candidate, second) if isinstance(second, dict) else (candidate,)


def height_mentions(page: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    return (page, *page.get("additional_heights", ()))


def kind_of(page: Mapping[str, Any]) -> str:
    return str(page.get("height_kind", "")).casefold()


def excerpt_matches(page: Mapping[str, Any]) -> bool:
    """Exact decimal token followed by the page's literal metric unit."""
    token = page.get("height_m")
    unit = page.get("unit_as_written")
    if not isinstance(token, str) or VALUE_TOKEN.fullmatch(token) is None:
        return False
    if not isinstance(unit, str) or unit.casefold() not in UNITS:
        return False
    pattern = (
        r"(?<![\w.,+~-])" + re.escape(token) + r"\s+" + re.escape(unit) + r"(?!\w)"
    )
    return (
        re.search(pattern, str(page.get("height_excerpt", "")), re.IGNORECASE)
        is not None
    )


def _page_reason(page: Mapping[str, Any]) -> str:
    kind = kind_of(page)
    excerpt = str(page.get("height_excerpt", ""))
    if (
        kind not in KINDS
        or page.get("height_qualifier")
        or re.search(r"\b" + re.escape(kind) + r"\b", excerpt, re.IGNORECASE) is None
    ):
        return "kind_not_admitted"
    if not excerpt_matches(page):
        return "excerpt_mismatch"
    return ""


def _select(candidate: Mapping[str, Any]) -> tuple[Mapping[str, Any] | None, str]:
    if candidate.get("subject_kind") != "completed high-rise" or not candidate.get(
        "completed"
    ):
        return None, "not_building"
    pages = researched_pages(candidate)
    eligible = [page for page in pages if not _page_reason(page)]
    if not eligible:
        # The first failing rule, independent of the order of the pages.
        reason = min((_page_reason(p) for p in pages), key=REASONS.index)
        return None, reason
    for page in eligible:
        if any(
            kind_of(mention) == kind_of(page)
            and isinstance(mention.get("height_m"), str)
            and VALUE_TOKEN.fullmatch(mention["height_m"]) is not None
            and mention["height_m"] != page["height_m"]
            for other in pages
            for mention in height_mentions(other)
        ):
            return None, "same_kind_disagreement"
    return eligible[0], "admitted"


def select_landmarks(candidates: Sequence[Mapping[str, Any]]) -> Selection:
    """One outcome per candidate; no licence admission or numeric conversion."""
    admitted = []
    outcomes = []
    counts = dict.fromkeys(("admitted", *REASONS), 0)
    by_kind = dict.fromkeys(KINDS, 0)
    for candidate in candidates:
        page, reason = _select(candidate)
        landmark_id = candidate["landmark_id"]
        outcomes.append((landmark_id, reason))
        counts[reason] += 1
        if page is not None:
            admitted.append(SelectedLandmark(landmark_id, candidate["name_en"], page))
            by_kind[kind_of(page)] += 1
    return Selection(tuple(admitted), tuple(outcomes), counts, by_kind)
