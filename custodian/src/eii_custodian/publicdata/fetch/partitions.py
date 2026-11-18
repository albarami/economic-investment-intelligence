"""Accident year partitions, planned by hashed catalogue and aggregate responses."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from typing import NoReturn
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


class PartitionError(Exception):
    """Closed bounded-reader refusal; not converted into an upstream diagnostic."""


def load_partition_spans() -> dict[int, tuple[int, int]]:
    """Only the lead's observed per-year spans may activate the live adapter."""
    from .page_records import REVIEW
    from .registry import read_yaml

    document = read_yaml(REVIEW)
    spans = document.get("accident_spans") if isinstance(document, dict) else None
    if not isinstance(spans, dict) or not spans:
        raise PartitionError("partition_byte_bound_unconfirmed")
    result: dict[int, tuple[int, int]] = {}
    for year, span in spans.items():
        if (
            type(year) is not int
            or not 1000 <= year <= 9999
            or not isinstance(span, list)
            or len(span) != 2
            or any(type(value) is not int for value in span)
            or not 0 < span[0] <= span[1]
        ):
            raise PartitionError("partition_byte_bound_unconfirmed")
        result[year] = (span[0], span[1])
    return result


def bounded_partition_reader(
    transport: Read,
    spans: dict[int, tuple[int, int]],
    sleep: Callable[[float], None],
) -> Read:
    """Adapt query-bearing exports to S2-T25's bounded metadata reader."""
    from urllib.parse import parse_qs, urlsplit

    from .allowlist import approve
    from .bounded import read_metadata, within

    def refuse(reason: str) -> NoReturn:
        raise PartitionError(reason)

    def review(url: str) -> None:
        if not approve(url).ok:
            refuse("blocked_host")

    def read(url: str) -> Response:
        query = parse_qs(urlsplit(url).query)
        if not urlsplit(url).path.endswith("/exports/json"):
            return transport(url)
        where = query.get("where", [])
        match = (
            re.fullmatch(r"year\(accident_year\)=(\d{4})", where[0])
            if len(where) == 1
            else None
        )
        if match is None or int(match[1]) not in spans:
            refuse("partition_byte_bound_unconfirmed")
        span = spans[int(match[1])]
        if (
            len(span) != 2
            or any(type(n) is not int for n in span)
            or not 0 < span[0] <= span[1]
        ):
            refuse("partition_byte_bound_unconfirmed")
        responses: list[Response] = []

        def capture(address: str) -> Response:
            response = transport(address)
            responses.append(response)
            return response

        body = read_metadata(
            url,
            capture,
            review=review,
            max_bytes=span[1],
            sleep=sleep,
            refuse=refuse,
            bounded_read=True,
        )
        if not within(len(body), span):
            refuse("metadata_bytes")
        return responses[-1]

    return read
