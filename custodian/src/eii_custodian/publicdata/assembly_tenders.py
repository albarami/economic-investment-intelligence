"""Archive the existing tender fetcher's complete page set, without refetching."""

from __future__ import annotations

import json
from pathlib import Path

from .assembly import AssemblyError
from .assembly_io import local, read_object
from .fetch.receipts import sha256_hex, sidecar_for
from .fetch.registry import Entry
from .fetch.snapshots import publish_snapshot
from .singles.tenders import LIST_PATHS


def archive_pages(cache: Path, entry: Entry, stamp: str) -> str:
    pages = []
    for list_name, _ in LIST_PATHS:
        for language in ("en", "ar"):
            prefix = entry.key + "/" + list_name + "/" + language
            try:
                receipt = read_object(cache, prefix + ".receipt.json")
                bound = receipt["first_stated_last"]
                if (
                    type(bound) is not int
                    or bound <= 0
                    or receipt["last_stated_last"] != bound
                    or receipt["list_name"] != list_name
                    or receipt["language"] != language
                ):
                    raise AssemblyError("assembly_tender_pages_incomplete")
                for number in range(1, bound + 1):
                    page_text = local(
                        cache, prefix + "/" + str(number) + ".html"
                    ).read_text(encoding="utf-8")
                    pages.append(
                        {
                            "list_name": list_name,
                            "language": language,
                            "number": number,
                            "html": page_text,
                        }
                    )
            except (KeyError, OSError, UnicodeError, AssemblyError):
                raise AssemblyError("assembly_tender_pages_incomplete") from None
    body = (
        json.dumps(
            {"method": "assembly-tender-pages.v1", "pages": pages}, sort_keys=True
        )
        + "\n"
    ).encode()
    sidecar = sidecar_for(
        entry,
        digest=sha256_hex(body),
        nbytes=len(body),
        fetch_url=entry.url,
        fetch_host=entry.fetch_host,
        retrieved_utc=stamp,
        publisher=entry.publisher,
        source_modified="",
        row_count=None,
        terms_sha256="",
    )
    return publish_snapshot(local(cache, entry.key), "json", body, sidecar).sha256
