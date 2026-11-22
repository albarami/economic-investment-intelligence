"""Deterministic awards proof sampling and registration-gated exact name checks."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable, Mapping, Sequence
from decimal import Decimal
from typing import Any


class AwardError(ValueError):
    """Closed source-check reason, never a row or upstream diagnostic."""


def normalise_name(value: str) -> str:
    """L-790(a), decision 0064 item 41: collapse again after punctuation removal."""
    value = " ".join(unicodedata.normalize("NFKC", value).casefold().split())
    value = "".join(c for c in value if not unicodedata.category(c).startswith("P"))
    return " ".join(value.split())


MATCH_REASONS = ("matched", "matched_name_not_compared")
AWARD_ABSENT = {"proof_outcome": "proof_award_absent"}
MISMATCH_REASONS = (
    "proof_award_absent",
    "intake_value_absent",
    "proof_value_absent",
    "proof_mismatch",
)
REASON_COUNTS = ("matched_name_not_compared", *MISMATCH_REASONS)
FETCH_REASONS = frozenset(
    {"proof_fetch_failed", "unreachable", "http_status", "body_bytes"}
)
RESULT_REASONS = {
    "matched": frozenset(MATCH_REASONS),
    "mismatched": frozenset(MISMATCH_REASONS),
    "fetch_failed": FETCH_REASONS,
}


def name_script(value: str) -> str:
    """Classify normalised letters by Unicode names, ignoring nonletters.

    All letters named ARABIC => arabic; all named LATIN => latin; no letters
    => none. Any other letter or combination of scripts => mixed. Thus equal
    mixed-script names still require exact equality; digits never set a script.
    """
    scripts = {
        "arabic"
        if "ARABIC" in unicodedata.name(c, "")
        else "latin"
        if "LATIN" in unicodedata.name(c, "")
        else "mixed"
        for c in value
        if unicodedata.category(c).startswith("L")
    }
    return next(iter(scripts)) if len(scripts) == 1 else "mixed" if scripts else "none"


def comparison_reason(
    left: Mapping[str, str], right: Mapping[str, str], profile: Mapping[str, Any]
) -> str:
    """L-1423: strict declared formats, exact token sets and script-gated names.

    The proof reader supplies the awards parser's canonical two-decimal text,
    or an empty string for null. Malformed intake text was already admitted as
    a string: retain it as proof_mismatch, never as absent or a source refusal.
    """
    first = left.get(profile["value"], "")
    second = right.get(profile["value"], "")
    if isinstance(first, str) and first.strip() in {"", "QAR"}:
        return "intake_value_absent"
    if isinstance(second, str) and not second.strip():
        return "proof_value_absent"
    if (
        not isinstance(first, str)
        or re.fullmatch(r"([0-9]{1,3}(?:,[0-9]{3})*|[0-9]+)\.[0-9]{2} QAR", first)
        is None
        or not isinstance(second, str)
        or re.fullmatch(r"[0-9]+\.[0-9]{2}", second) is None
        or Decimal(first.removesuffix(" QAR").replace(",", "")) != Decimal(second)
    ):
        return "proof_mismatch"
    registrations = [
        {
            token.strip()
            for token in row.get(profile["registration"], "").split(" | ")
            if token.strip()
        }
        for row in (left, right)
    ]
    if not registrations[0] or registrations[0] != registrations[1]:
        return "proof_mismatch"
    names = [normalise_name(row.get(profile["company"], "")) for row in (left, right)]
    scripts = [name_script(name) for name in names]
    if scripts[0] != scripts[1] or scripts[0] == "none":
        return "matched_name_not_compared"
    return "matched" if names[0] == names[1] else "proof_mismatch"


def _same(
    left: Mapping[str, str], right: Mapping[str, str], profile: Mapping[str, Any]
) -> bool:
    return comparison_reason(left, right, profile) in MATCH_REASONS


def proof_reason(
    rows: Sequence[Mapping[str, str]],
    candidates: Sequence[Mapping[str, str]],
    profile: Mapping[str, Any],
) -> str:
    """Every winner needs a match; prefer a compared-name match among candidates.

    A winner without a match uses the closed mismatch precedence. Any failing
    winner defeats the link; otherwise any un-compared name labels the match.
    """
    order = (*MATCH_REASONS, *MISMATCH_REASONS)
    reasons = {
        min(
            (comparison_reason(row, item, profile) for item in candidates),
            key=order.index,
        )
        for row in rows
    }
    for reason in MISMATCH_REASONS:
        if reason in reasons:
            return reason
    return (
        "matched_name_not_compared"
        if "matched_name_not_compared" in reasons
        else "matched"
    )


def check_awards(
    rows: Sequence[Mapping[str, str]],
    profile: Mapping[str, Any],
    seed: int,
    proof_reader: Callable[[str], Mapping[str, str] | Sequence[Mapping[str, str]]],
) -> dict[str, Any]:
    """Sample distinct links through the same checker as the full-link path."""
    from .award_links import _check_links, _frame, _sample, _sample_urls

    frame = _frame(rows)
    selected = _sample_urls(sorted(frame), seed)
    return _sample(
        len(frame), _check_links(frame, profile, proof_reader, selected), seed
    )


def validate_check_receipt(receipt: Mapping[str, object]) -> None:
    """The scrape check belongs to the source receipt, not an unrelated report."""
    check = receipt.get("award_check")
    required = {
        "seed",
        "distinct_frame_count",
        "selected_count",
        "matched",
        "mismatched",
        "failed_fetches",
        "match_rate",
        "incomplete",
        "status",
        "results",
        *REASON_COUNTS,
    }
    if (
        receipt.get("source_id") != "awards_owner_scrape"
        or not isinstance(check, dict)
        or set(check) != required
    ):
        raise AwardError("award_check_metadata_missing")
    counts = (
        "distinct_frame_count",
        "selected_count",
        "matched",
        "mismatched",
        "failed_fetches",
        *REASON_COUNTS,
    )
    if (
        any(type(check[key]) is not int or check[key] < 0 for key in counts)
        or type(check["seed"]) is not int
    ):
        raise AwardError("award_check_metadata_missing")
    selected = min(check["distinct_frame_count"], 30)
    rate = str(Decimal(check["matched"]) / Decimal(selected)) if selected else None
    incomplete = selected < 30 or check["failed_fetches"] > 0
    if (
        check["selected_count"] != selected
        or sum(check[key] for key in ("matched", "mismatched", "failed_fetches"))
        != selected
        or check["match_rate"] != rate
        or check["incomplete"] is not incomplete
        or check["status"]
        != ("award_check_incomplete" if incomplete else "sample_recorded")
        or not isinstance(check["results"], list)
        or len(check["results"]) != selected
    ):
        raise AwardError("award_check_metadata_missing")

    from .award_links import _totals, valid_result

    if (
        any(not valid_result(item) for item in check["results"])
        or len({item["report_url"] for item in check["results"]}) != selected
        or any(check[key] != value for key, value in _totals(check["results"]).items())
    ):
        raise AwardError("award_check_metadata_missing")


def match_register(
    rows: Sequence[Mapping[str, str]],
    profile: Mapping[str, Any],
    registers: Sequence[Mapping[str, str]],
) -> dict[str, object]:
    """No name-only join; ambiguous registrations and disagreements stay unmatched."""
    by_registration: dict[str, list[str]] = {}
    for company in registers:
        registration = company.get("registration", "")
        if registration.strip():
            by_registration.setdefault(registration, []).append(company.get("name", ""))
    report: list[dict[str, object]] = []
    matched = 0
    for row in rows:
        registration = row.get(profile["registration"], "")
        names = by_registration.get(registration, [])
        name = normalise_name(row.get(profile["company"], ""))
        reason = "registration_unmatched"
        if registration.strip() and names:
            reason = "registration_ambiguous" if len(names) != 1 else "name_mismatch"
            if len(names) == 1 and name.strip() and name == normalise_name(names[0]):
                reason = "matched"
                matched += 1
        report.append({"original": dict(row), "reason": reason})
    return {"matched": matched, "unmatched": len(rows) - matched, "rows": report}


def double_space_only(
    match: Mapping[str, object],
    profile: Mapping[str, Any],
    registers: Sequence[Mapping[str, str]],
) -> int:
    """OI-277: retain the receipt counter for remaining spacing-only mismatches.

    Post-punctuation whitespace collapse now resolves the planted double-space
    pair. This counter still reads only unmatched names with one registration
    candidate; only a count is returned, never a name.
    """
    by_registration: dict[str, list[str]] = {}
    for company in registers:
        registration = company.get("registration", "")
        if registration.strip():
            by_registration.setdefault(registration, []).append(company.get("name", ""))
    rows = match.get("rows")
    count = 0
    for item in rows if isinstance(rows, list) else ():
        if not isinstance(item, dict) or item.get("reason") != "name_mismatch":
            continue
        original = item.get("original")
        if not isinstance(original, dict):
            continue
        names = by_registration.get(original.get(profile["registration"], ""), [])
        if len(names) != 1:
            continue
        award = normalise_name(original.get(profile["company"], ""))
        listed = normalise_name(names[0])
        if award != listed and award.split() == listed.split() and award.split():
            count += 1
    return count
