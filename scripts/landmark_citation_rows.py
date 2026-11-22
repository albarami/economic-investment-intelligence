"""Emit citation metadata from the supplied research, without fetching or retaining source records.

CLI: uv run --locked python scripts/landmark_citation_rows.py RESEARCH OUTPUT
OUTPUT is JSON containing source rows, keyed page declarations and fetch hosts.
Review and install these into sources.yaml, s2_t29_sources.yaml and allowlist.py.
"""

from __future__ import annotations

import argparse
import json
import re
from collections.abc import Mapping, Sequence
from datetime import date
from pathlib import Path
from typing import Any

from eii_custodian.publicdata.fetch.allowlist import host_of, safe_https_shape
from eii_custodian.publicdata.fetch.receipts import sha256_hex
from eii_custodian.publicdata.fetch.registry import TERMS_WORDS_PENDING, read_yaml
from eii_custodian.publicdata.heights.landmark_select import researched_pages

EVIDENCE = "Document 04 S2-P53 landmark hand-list placement and citation snapshots; decision 0093 item 3"
OPEN_WORDS = (
    "Text is available under the Creative Commons Attribution-ShareAlike "
    "4.0 License; additional terms may apply."
)


def _url(value: str) -> str:
    if not safe_https_shape(value) or not host_of(value):
        raise ValueError("citation_url_shape")
    return value


def _publishers(rows: list[Any]) -> dict[str, dict[str, Any]]:
    publishers: dict[str, dict[str, Any]] = {}
    sources: set[str] = set()
    for row in rows:
        if (
            not isinstance(row, dict)
            or any(
                not isinstance(row.get(k), str) or not row[k].strip()
                for k in ("publisher", "terms_words", "checked_on")
            )
            or not isinstance(row.get("terms_url"), str | type(None))
            or not isinstance(row.get("note", ""), str)
        ):
            raise ValueError("citation_publisher_shape")
        try:
            checked = date.fromisoformat(row["checked_on"]).isoformat()
        except ValueError:
            raise ValueError("citation_publisher_shape") from None
        slug = re.sub(r"[^a-z0-9]+", "_", row["publisher"].casefold()).strip("_")
        if not slug or checked != row["checked_on"]:
            raise ValueError("citation_publisher_shape")
        source = "landmark_" + slug
        if row["publisher"] in publishers or source in sources:
            raise ValueError("citation_publisher_duplicate")
        publishers[row["publisher"]] = dict(row, source_id=source)
        sources.add(source)
    return publishers


def _row(url: str, publisher: Mapping[str, Any]) -> dict[str, Any]:
    words = publisher["terms_words"]
    opened = words == OPEN_WORDS
    terms = _url(publisher["terms_url"]) if publisher.get("terms_url") else ""
    source = publisher["source_id"]
    return {
        "key": source + "/page-" + sha256_hex(url.encode("utf-8")),
        "refetch": {
            "value": "none",
            "reason": "frequency_unconfirmed",
            "evidence": EVIDENCE,
        },
        "source_id": source,
        "slug": "",
        "kind": "public_page",
        "title_en": "Landmark citation page",
        "publisher": publisher["publisher"],
        "licence_id": "CC-BY-SA-4.0" if opened else "not_stated",
        "licence_basis": "dataset" if opened else "owner_decision",
        "licence_url": terms if opened else "",
        "decision_record": "" if opened else "0026",
        "fetch_host": host_of(url),
        "url": url,
        "landing_url": url,
        "terms_url": terms,
        "terms_words": TERMS_WORDS_PENDING if words == "terms_not_found" else words,
        "terms_read_on": publisher["checked_on"],
        "basis_note": EVIDENCE + ". " + publisher.get("note", ""),
        "nightly_live_fetch": False,
        "public_splits": [],
        "commit_allowed": False,
        "release_tables": [],
        "caveat_keys": [],
        "columns": [],
        "row_count_min": None,
        "row_count_max": None,
        "period_first": "",
        "period_last": "",
        "period_field": "",
        "reconciliation": "none",
        "skip_reason": "",
        "extension": "html",
    }


def _declaration(url: str, terms_url: str) -> dict[str, Any]:
    return {
        "version": 2,
        "kind": "citation_snapshot",
        "url": url,
        "reviewed_urls": list(dict.fromkeys(u for u in (url, terms_url) if u)),
        "columns": [],
        "as_of": "retrieval_date",
        "publisher_date": None,
        "period_fields": [],
        "bounds_basis": "unconfirmed",
        "bounds_reason": "Citation snapshot; no parsed rows or statistical bounds.",
        "pins": [],
        "evidence": EVIDENCE,
        "hold": None,
        "max_bytes": 8388608,
        "shape": {},
    }


def generate(document: object) -> dict[str, Any]:
    """One source ID per publisher, one key per URL, independent of input order."""
    if (
        not isinstance(document, dict)
        or not isinstance(document.get("publishers"), list)
        or not isinstance(document.get("landmarks"), list)
        or any(not isinstance(row, dict) for row in document["landmarks"])
    ):
        raise ValueError("citation_research_shape")
    publishers = _publishers(document["publishers"])
    pages: dict[str, dict[str, Any]] = {}
    for candidate in document["landmarks"]:
        for page in researched_pages(candidate):
            if any(not isinstance(page.get(k), str) for k in ("publisher", "page_url")):
                raise ValueError("citation_page_shape")
            name = page["publisher"]
            if name not in publishers:
                raise ValueError("citation_publisher_unknown")
            url = _url(page["page_url"])
            if url in pages and pages[url]["publisher"] != name:
                raise ValueError("citation_page_publisher_conflict")
            pages[url] = _row(url, publishers[name])
    rows = sorted(pages.values(), key=lambda row: row["key"])
    hosts = {
        host_of(url) for row in rows for url in (row["url"], row["terms_url"]) if url
    }
    return {
        "sources": rows,
        "declarations": {
            row["key"]: _declaration(row["url"], row["terms_url"]) for row in rows
        },
        "hosts": sorted(hosts),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("research", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args(argv)
    output = generate(read_yaml(args.research))
    args.output.write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
