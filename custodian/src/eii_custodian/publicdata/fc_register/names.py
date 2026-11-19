"""Pinned company names, including every row hidden by a possible display filter."""

from __future__ import annotations

from pathlib import Path

from ..completeness import receipt_valid
from ..fetch.page_identity import RequestIdentity, digest
from ..fetch.page_records import PageError, selected_page
from ..fetch.page_schema import json_body
from ..fetch.registry import Entry
from ..fetch.snapshots import read_snapshot
from ..name_inventory import Contribution
from .constants import PROJECTION, TARGETS, URL
from .parse import fragment


def contribution(cache: Path, entry: Entry) -> Contribution:
    if entry.source_id != "fc_register" or entry.url != URL:
        raise PageError("receipt_missing")
    selected = selected_page(cache, entry)
    payload = json_body(selected.body)
    if (
        not receipt_valid(entry, selected.sidecar)
        or not isinstance(payload, dict)
        or payload.get("version") != 2
    ):
        raise PageError("receipt_missing")
    rows: list[dict[str, object]] = []
    previous = None
    hashes: set[str] = set()
    continuation = "next"
    for ordinal, item in enumerate(payload["inputs"], start=1):
        if continuation != "next":
            raise PageError("receipt_missing")
        raw = read_snapshot(cache / entry.key / item["key"], item["identity"])
        if not receipt_valid(entry, raw.sidecar) or any(
            item.get(k) != raw.sidecar.get(k)
            for k in (
                "representation",
                "upstream_sha256",
                "request_identity",
                "upstream_evidence",
                "capture",
            )
        ):
            raise PageError("receipt_missing")
        if item.get("representation") != PROJECTION or not digest(
            item.get("upstream_sha256")
        ):
            raise PageError("receipt_missing")
        expected = RequestIdentity(
            "GET" if ordinal == 1 else "POST",
            URL,
            None if ordinal == 1 else TARGETS[0],
            None if ordinal == 1 else "",
            ordinal,
            previous,
        )
        identity = RequestIdentity.load(item.get("request_identity"))
        # Both declared Company pagers are permitted, without accepting any other control.
        if ordinal > 1 and identity.target in TARGETS:
            expected = RequestIdentity(
                "POST", URL, identity.target, "", ordinal, previous
            )
        if identity != expected or item["upstream_sha256"] in hashes:
            raise PageError("receipt_missing")
        value = fragment(raw.body)
        if value["progress"]["shown_page"] != ordinal:
            raise PageError("receipt_missing")
        continuation = value["progress"]["continuation"]
        rows.extend(value["rows"])
        previous = item["upstream_sha256"]
        hashes.add(previous)
    if continuation != "terminal" or rows != payload.get("rows"):
        raise PageError("receipt_missing")
    names = tuple(
        str(row[field])
        for row in rows
        for field in ("company_name", "company_name_ar")
        if row[field]
    )
    return Contribution(
        entry.source_id,
        names,
        {
            "snapshot_identity": selected.sha256,
            "retrieved_utc": payload["retrieved_utc"],
            "method": payload["method"],
            "inputs": payload["inputs"],
            "publisher": selected.sidecar["publisher"],
            "licence_id": selected.sidecar["licence_id"],
            "licence_basis": selected.sidecar["licence_basis"],
            "page": URL,
        },
    )
