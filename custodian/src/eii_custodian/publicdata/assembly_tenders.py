"""Archive the existing tender fetcher's complete page set, without refetching."""

from __future__ import annotations

import json
from pathlib import Path

from .assembly import AssemblyError
from .assembly_io import local, read_object
from .fetch.receipts import sha256_hex, sidecar_for
from .fetch.registry import Entry
from .fetch.snapshots import publish_snapshot
from .singles.tenders import AWARD_CONTINUITY_PAGES, LIST_PATHS, TenderError


def archive_pages(cache: Path, entry: Entry, stamp: str) -> str:
    pages = []
    readings = []
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
                stop = receipt.get("stop_page")
                count = receipt.get("pages_read", bound)
                if type(count) is not int or not 1 <= count <= bound:
                    raise AssemblyError("assembly_tender_pages_incomplete")
                if stop is not None and (
                    type(stop) is not int
                    or not 1 <= stop <= count
                    or list_name != "awarded"
                    or count != min(bound, stop + AWARD_CONTINUITY_PAGES)
                ):
                    raise AssemblyError("assembly_tender_pages_incomplete")
                if stop is None and count != bound:
                    raise AssemblyError("assembly_tender_pages_incomplete")
                previous = None
                cutoff = receipt.get("award_cutoff")
                if cutoff is not None:
                    from .fetch.awards import intake_cutoff

                    selected_cutoff, reason, digest = intake_cutoff(cache, stamp)
                    if (
                        list_name != "awarded"
                        or reason
                        or selected_cutoff != cutoff
                        or receipt.get("workbook_sha256") != digest
                        or type(receipt.get("last_page_read")) is not int
                        or receipt["last_page_read"] != count
                        or type(receipt.get("continuity_pages")) is not int
                        or receipt["continuity_pages"]
                        != (count - stop if stop is not None else 0)
                    ):
                        raise AssemblyError("assembly_tender_pages_incomplete")
                for number in range(1, count + 1):
                    page_text = local(
                        cache, prefix + "/" + str(number) + ".html"
                    ).read_text(encoding="utf-8")
                    if cutoff is not None:
                        from .singles.tenders import (
                            _award_page,
                            _checked_page,
                            _require_count,
                        )

                        raw = _checked_page(page_text, language)
                        _require_count(len(raw.cards), is_last=number == bound)
                        previous, covered = _award_page(
                            raw,
                            language,
                            cutoff,
                            previous,
                            after_stop=stop is not None and number > stop,
                        )
                        if covered != (stop is not None and number >= stop):
                            raise AssemblyError("assembly_tender_pages_incomplete")
                    elif stop is not None:
                        raise AssemblyError("assembly_tender_pages_incomplete")
                    pages.append(
                        {
                            "list_name": list_name,
                            "language": language,
                            "number": number,
                            "html": page_text,
                        }
                    )
                readings.append(receipt)
            except (KeyError, OSError, UnicodeError, ValueError, TenderError):
                raise AssemblyError("assembly_tender_pages_incomplete") from None
    body = (
        json.dumps(
            {
                "method": "assembly-tender-pages.v1",
                "pages": pages,
                "readings": readings,
            },
            sort_keys=True,
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
