"""Complete award-link evidence, separate from the seeded sample (S2-T29)."""

from __future__ import annotations

import random
from collections.abc import Callable, Mapping, Sequence
from decimal import Decimal
from typing import Any

from .allowlist import approve
from .award_checks import AwardError, _same, validate_check_receipt
from .certificate_pins import PinError
from .snapshots import SnapshotError

METHOD = "awards.report_links@v1"
FETCH_REASONS = frozenset(
    {"proof_fetch_failed", "unreachable", "http_status", "body_bytes"}
)


class ProofFetchError(AwardError):
    """Retain a closed failure reason without an upstream message or body."""

    def __init__(self, reason: str) -> None:
        self.reason = reason if reason in FETCH_REASONS else "proof_fetch_failed"
        super().__init__("proof_fetch_failed")


def _frame(rows: Sequence[Mapping[str, str]]) -> dict[str, list[Mapping[str, str]]]:
    frame: dict[str, list[Mapping[str, str]]] = {}
    for row in rows:
        link = row.get("report_url", "").strip()
        if link:
            if not approve(link).ok:
                raise AwardError("blocked_host")
            frame.setdefault(link, []).append(row)
    return frame


def check_all_awards(
    rows: Sequence[Mapping[str, str]],
    profile: Mapping[str, Any],
    proof_reader: Callable[[str], Mapping[str, str] | Sequence[Mapping[str, str]]],
) -> dict[str, Any]:
    """Check every distinct nonblank link once, with all its intake winners.

    Ordinary fetch failures remain checked links with a closed reason. Trust,
    archive and schema refusals still stop publication; none becomes a match.
    """
    frame = _frame(rows)
    results: list[dict[str, str]] = []
    for url in sorted(frame):
        try:
            proof = proof_reader(url)
        except (PinError, SnapshotError):
            raise
        except AwardError as exc:
            if str(exc) != "proof_fetch_failed":
                raise
            result = "fetch_failed"
            reason = (
                exc.reason if isinstance(exc, ProofFetchError) else "proof_fetch_failed"
            )
        except OSError:
            result, reason = "fetch_failed", "unreachable"
        else:
            candidates = [proof] if isinstance(proof, Mapping) else list(proof)
            if not candidates or any(
                not isinstance(item, Mapping) for item in candidates
            ):
                raise AwardError("schema_missing")
            agrees = all(
                any(_same(row, candidate, profile) for candidate in candidates)
                for row in frame[url]
            )
            result = "matched" if agrees else "mismatched"
            reason = "matched" if agrees else "proof_mismatch"
        results.append({"report_url": url, "result": result, "reason": reason})
    totals = _totals(results)
    incomplete = not results or totals["failed_fetches"] > 0
    return {
        "method": METHOD,
        "scope": "all_links",
        "report_urls": sorted(frame),
        "distinct_frame_count": len(frame),
        "checked_count": len(results),
        **totals,
        "incomplete": incomplete,
        "status": "award_links_incomplete" if incomplete else "all_links_recorded",
        "results": results,
    }


def _totals(results: Sequence[Mapping[str, str]]) -> dict[str, Any]:
    matched = sum(item["result"] == "matched" for item in results)
    return {
        "matched": matched,
        "mismatched": sum(item["result"] == "mismatched" for item in results),
        "failed_fetches": sum(item["result"] == "fetch_failed" for item in results),
        "match_rate": str(Decimal(matched) / Decimal(len(results)))
        if results
        else None,
    }


def sample_from_links(check: Mapping[str, Any], seed: int) -> dict[str, Any]:
    """Retain the original sample contract, reusing outcomes without any fetch."""
    if type(seed) is not int:
        raise AwardError("award_seed_pending")
    urls = check["report_urls"]
    selected = random.Random(seed).sample(urls, 30) if len(urls) > 30 else urls
    by_url = {item["report_url"]: item["result"] for item in check["results"]}
    results = [{"report_url": url, "result": by_url[url]} for url in selected]
    totals = _totals(results)
    incomplete = len(selected) < 30 or totals["failed_fetches"] > 0
    return {
        "seed": seed,
        "distinct_frame_count": len(urls),
        "selected_count": len(selected),
        **totals,
        "incomplete": incomplete,
        "status": "award_check_incomplete" if incomplete else "sample_recorded",
        "results": results,
    }


def validate_links_receipt(
    receipt: Mapping[str, Any], rows: Sequence[Mapping[str, str]] | None = None
) -> None:
    """Bind complete coverage, result totals and the sample to one source receipt.

    Publication also compares the frame with the intake, so a checker that drops
    a link cannot publish even a self-consistent smaller frame.
    """
    check = receipt.get("award_links")
    counts = {
        "distinct_frame_count",
        "checked_count",
        "matched",
        "mismatched",
        "failed_fetches",
    }
    required = counts | {
        "method",
        "scope",
        "report_urls",
        "match_rate",
        "incomplete",
        "status",
        "results",
    }
    if (
        receipt.get("source_id") != "awards_owner_scrape"
        or receipt.get("award_check_scope") != "sample"
        or not isinstance(check, dict)
        or set(check) != required
        or check["method"] != METHOD
        or check["scope"] != "all_links"
        or any(type(check[key]) is not int or check[key] < 0 for key in counts)
    ):
        raise AwardError("award_links_metadata_missing")
    urls, results = check["report_urls"], check["results"]
    if (
        not isinstance(urls, list)
        or any(
            not isinstance(url, str) or not url or not approve(url).ok for url in urls
        )
        or urls != sorted(set(urls))
        or check["distinct_frame_count"] != len(urls)
        or check["checked_count"] != len(urls)
        or not isinstance(results, list)
        or len(results) != len(urls)
        or (rows is not None and urls != sorted(_frame(rows)))
    ):
        raise AwardError("award_links_metadata_missing")
    reasons = {
        "matched": {"matched"},
        "mismatched": {"proof_mismatch"},
        "fetch_failed": FETCH_REASONS,
    }
    for url, item in zip(urls, results, strict=True):
        if (
            not isinstance(item, dict)
            or set(item) != {"report_url", "result", "reason"}
            or any(not isinstance(value, str) for value in item.values())
            or item["report_url"] != url
            or item["result"] not in reasons
            or item["reason"] not in reasons[item["result"]]
        ):
            raise AwardError("award_links_metadata_missing")
    totals = _totals(results)
    incomplete = not results or totals["failed_fetches"] > 0
    if (
        any(check[key] != value for key, value in totals.items())
        or check["incomplete"] is not incomplete
        or check["status"]
        != ("award_links_incomplete" if incomplete else "all_links_recorded")
    ):
        raise AwardError("award_links_metadata_missing")
    validate_check_receipt(receipt)
    if receipt["award_check"] != sample_from_links(
        check, receipt["award_check"]["seed"]
    ):
        raise AwardError("award_links_metadata_missing")
