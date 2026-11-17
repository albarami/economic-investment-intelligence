"""Deterministic awards proof sampling and registration-gated exact name checks."""

from __future__ import annotations

import random
import unicodedata
from collections.abc import Callable, Mapping, Sequence
from decimal import Decimal, InvalidOperation
from typing import Any

from .allowlist import approve


class AwardError(ValueError):
    """Closed source-check reason, never a row or upstream diagnostic."""


def normalise_name(value: str) -> str:
    """L-790(a): NFKC, case fold, whitespace collapse, punctuation removal only."""
    value = " ".join(unicodedata.normalize("NFKC", value).casefold().split())
    return "".join(c for c in value if not unicodedata.category(c).startswith("P"))


def _same(
    left: Mapping[str, str], right: Mapping[str, str], profile: Mapping[str, Any]
) -> bool:
    try:
        first, second = (
            Decimal(left[profile["value"]]),
            Decimal(right[profile["value"]]),
        )
        return (
            first.is_finite()
            and second.is_finite()
            and first == second
            and bool(left[profile["registration"]].strip())
            and left[profile["registration"]] == right[profile["registration"]]
            and bool(normalise_name(left[profile["company"]]).strip())
            and normalise_name(left[profile["company"]])
            == normalise_name(right[profile["company"]])
        )
    except (KeyError, InvalidOperation, TypeError):
        return False


def check_awards(
    rows: Sequence[Mapping[str, str]],
    profile: Mapping[str, Any],
    seed: int,
    proof_reader: Callable[[str], Mapping[str, str]],
) -> dict[str, object]:
    """Sample distinct nonblank URLs; failed fetches remain in the denominator."""
    if type(seed) is not int:
        raise AwardError("award_seed_pending")
    frame: dict[str, list[Mapping[str, str]]] = {}
    for row in rows:
        link = row.get("report_url", "").strip()
        if not link:
            continue
        if not approve(link).ok:
            raise AwardError("blocked_host")
        frame.setdefault(link, []).append(row)
    eligible = sorted(frame)
    selected = (
        random.Random(seed).sample(eligible, 30) if len(eligible) > 30 else eligible
    )
    matched = mismatched = failed = 0
    results: list[dict[str, object]] = []
    for url in selected:
        try:
            proof = proof_reader(url)
        except (OSError, ValueError, RuntimeError):
            failed += 1
            results.append({"report_url": url, "result": "fetch_failed"})
            continue
        agrees = all(_same(row, proof, profile) for row in frame[url])
        matched += int(agrees)
        mismatched += int(not agrees)
        results.append(
            {"report_url": url, "result": "matched" if agrees else "mismatched"}
        )
    incomplete = len(selected) < 30 or failed > 0
    return {
        "seed": seed,
        "distinct_frame_count": len(frame),
        "selected_count": len(selected),
        "matched": matched,
        "mismatched": mismatched,
        "failed_fetches": failed,
        "match_rate": str(Decimal(matched) / Decimal(len(selected)))
        if selected
        else None,
        "incomplete": incomplete,
        "status": "award_check_incomplete" if incomplete else "sample_recorded",
        "results": results,
    }


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


def match_register(
    rows: Sequence[Mapping[str, str]],
    profile: Mapping[str, Any],
    registers: Sequence[Mapping[str, str]],
) -> dict[str, object]:
    """No name-only join; ambiguous registrations and disagreements stay unmatched."""
    by_registration: dict[str, list[str]] = {}
    for company in registers:
        registration = company.get("registration", "")
        if registration:
            by_registration.setdefault(registration, []).append(company.get("name", ""))
    report: list[dict[str, object]] = []
    matched = 0
    for row in rows:
        registration = row.get(profile["registration"], "")
        names = by_registration.get(registration, [])
        name = normalise_name(row.get(profile["company"], ""))
        reason = "registration_unmatched"
        if names:
            reason = "registration_ambiguous" if len(names) != 1 else "name_mismatch"
            if len(names) == 1 and name.strip() and name == normalise_name(names[0]):
                reason = "matched"
                matched += 1
        report.append({"original": dict(row), "reason": reason})
    return {"matched": matched, "unmatched": len(rows) - matched, "rows": report}
