"""Accident year partitions, planned by hashed catalogue and aggregate responses."""

from __future__ import annotations

import json
from urllib.parse import urlencode

from eii_custodian.publicdata.fetch.checks import AttemptFailure, schema_failure
from eii_custodian.publicdata.fetch.kinds import Read, _call_url, _json_rows
from eii_custodian.publicdata.fetch.receipts import sha256_hex
from eii_custodian.publicdata.fetch.registry import Entry
from eii_custodian.publicdata.fetch.transport import Response


def partition_export(
    entry: Entry, meta: Response, reader: Read
) -> tuple[bytes, tuple[dict[str, object], ...], AttemptFailure | None]:
    """Validate the complete page plan and every page before returning cache bytes."""
    base = entry.url.removesuffix("/exports/json")
    plan_url = (
        base
        + "/records?"
        + urlencode(
            {
                "select": "count(*) as n",
                "group_by": "year(accident_year)",
                "limit": "50",
            }
        )
    )
    plan, failure = _call_url(plan_url, reader)
    if failure is not None or plan is None:
        return b"", (), failure
    total = _total(meta.body)
    groups = _plan(plan.body)
    if total is None or groups is None:
        return _refuse(plan_url, "partition_plan")
    if len({year for year, _ in groups}) != len(groups):
        return _refuse(plan_url, "partition_duplicate")
    if sum(count for _, count in groups) != total:
        return _refuse(plan_url, "partition_total")
    requests = [request_receipt(meta, total), request_receipt(plan, len(groups))]
    rows: list[object] = []
    hashes: set[str] = set()
    for year, expected in groups:
        url = entry.url + "?" + urlencode({"where": f"year(accident_year)={year}"})
        page, failure = _call_url(url, reader)
        if failure is not None or page is None:
            return b"", (), failure
        batch = _json_rows(page.body)
        if batch is None or len(batch) != expected:
            return _refuse(url, "partition_count")
        digest = sha256_hex(page.body)
        if digest in hashes:
            return _refuse(url, "partition_duplicate")
        hashes.add(digest)
        invalid = schema_failure(entry, batch, url)
        if invalid is not None:
            return b"", (), invalid
        requests.append(request_receipt(page, len(batch)))
        rows.extend(batch)
    return json.dumps(rows, sort_keys=True).encode(), tuple(requests), None


def request_receipt(response: Response, count: int) -> dict[str, object]:
    """Describe the actual response bytes; caller retains them until checks pass."""
    return {
        "url": response.final_url,
        "sha256": sha256_hex(response.body),
        "bytes": len(response.body),
        "row_count": count,
    }


def _refuse(
    url: str, check: str
) -> tuple[bytes, tuple[dict[str, object], ...], AttemptFailure]:
    return (
        b"",
        (),
        AttemptFailure(1, url, check, "complete distinct partitions", "invalid"),
    )


def _total(body: bytes) -> int | None:
    try:
        value = json.loads(body)
    except (ValueError, UnicodeError):
        return None
    if not isinstance(value, dict):
        return None
    count = value.get("records_count")
    return count if type(count) is int and count >= 0 else None


def _plan(body: bytes) -> list[tuple[int, int]] | None:
    try:
        value = json.loads(body)
    except (ValueError, UnicodeError):
        return None
    if not isinstance(value, dict):
        return None
    groups = value.get("results")
    if (
        not isinstance(groups, list)
        or not groups
        or len(groups) > 50
        or type(value.get("total_count")) is not int
        or value["total_count"] != len(groups)
    ):
        return None
    found: list[tuple[int, int]] = []
    for group in groups:
        if not isinstance(group, dict):
            return None
        year, count = group.get("year(accident_year)"), group.get("n")
        if (
            type(year) is not int
            or not 1000 <= year <= 9999
            or type(count) is not int
            or count <= 0
        ):
            return None
        found.append((year, count))
    return found
